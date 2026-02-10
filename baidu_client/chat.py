"""聊天逻辑模块"""
import asyncio
import time
from pathlib import Path
from playwright.async_api import Page

from .config import SELECTORS, TIMEOUT, BAIDU_URL, DEBUG
from .utils import find_element, find_all_elements


class BaiduChat:
    """百度文心助手聊天管理器"""

    def __init__(self, page: Page):
        self.page = page
        self._input_selector = None
        self._send_selector = None
        self._stop_selector = None       # 缓存首次命中的停止按钮选择器
        self._loading_selector = None    # 缓存首次命中的加载指示器选择器
        self._response_selector = None   # 缓存首次命中的回复消息选择器

    async def _quick_find(self, selectors: list[str], label: str = "") -> tuple:
        """快速查找元素：先即时扫描全部选择器（0ms），找不到再短暂等待

        Args:
            selectors: 候选选择器列表
            label: DEBUG 日志标签（如 "输入框"、"发送按钮"）

        Returns:
            (element, selector) 或 (None, None)
        """
        if DEBUG and label:
            print(f"  [DEBUG] === 扫描{label}选择器 ===")

        # 第一轮：即时查询，不等待
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    if DEBUG:
                        print(f"  [DEBUG]   ✓ {sel}")
                    return el, sel
                else:
                    if DEBUG:
                        print(f"  [DEBUG]   ✗ {sel}")
            except Exception as e:
                if DEBUG:
                    print(f"  [DEBUG]   ✗ {sel} (异常: {e})")
                continue

        # 第二轮：短暂等待（元素可能还在渲染）
        if DEBUG and label:
            print(f"  [DEBUG]   即时扫描未命中，等待重试...")
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=500)
                if el:
                    if DEBUG:
                        print(f"  [DEBUG]   ✓ (等待后) {sel}")
                    return el, sel
            except Exception:
                continue

        return None, None

    async def send_message(self, prompt: str) -> str:
        """发送消息并等待响应"""
        t_start = time.time()

        print(f"→ 发送消息: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

        # 查找输入框（有缓存直接用，否则快速扫描）
        input_box = None
        if self._input_selector:
            input_box = await self.page.query_selector(self._input_selector)

        if not input_box:
            input_box, self._input_selector = await self._quick_find(SELECTORS["input_box"], "输入框")

        if not input_box:
            # 最后兜底：用 wait_for_selector 等页面加载
            input_box, self._input_selector = await find_element(
                self.page, SELECTORS["input_box"], timeout=TIMEOUT["element"]
            )

        if not input_box:
            raise Exception("找不到输入框，请检查页面是否加载完成或更新选择器配置")

        if DEBUG:
            print(f"  [DEBUG] 输入框选择器: {self._input_selector}")

        # 清空并输入 — fill() 最快，直接设置 value
        await input_box.click()
        try:
            await input_box.fill(prompt)
        except Exception:
            await self.page.keyboard.press("Control+a")
            await self.page.keyboard.press("Backspace")
            await self.page.keyboard.type(prompt, delay=0)

        if DEBUG:
            print(f"  [TIMING] 输入消息: {time.time() - t_start:.1f}s")

        # 发送前记录页面已有内容，用于区分新旧响应
        pre_content = await self._get_latest_response()
        if pre_content:
            print(f"  [DEBUG] 发送前页面已有内容: {pre_content[:80]!r}")

        # 查找并点击发送按钮（缓存 > 即时扫描 > 回车兜底）
        sent = False
        all_send_selectors = SELECTORS["send_button"] + [
            '[class*="submit"]',
            'button:has(svg[class*="arrow"])',
        ]

        if self._send_selector:
            # 已缓存，即时查询
            try:
                btn = await self.page.query_selector(self._send_selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    sent = True
                    print(f"  [DEBUG] 点击发送按钮(缓存): {self._send_selector}")
            except Exception:
                self._send_selector = None

        if not sent:
            btn, sel = await self._quick_find(all_send_selectors, "发送按钮")
            if btn:
                try:
                    if await btn.is_visible():
                        await btn.click()
                        sent = True
                        self._send_selector = sel
                        print(f"  [DEBUG] 点击发送按钮: {sel}")
                except Exception:
                    pass

        if not sent:
            print("  [DEBUG] 尝试使用回车发送")
            await self.page.keyboard.press("Enter")

        t_sent = time.time()
        if DEBUG:
            print(f"  [TIMING] 发送消息: {t_sent - t_start:.1f}s")

        print("→ 等待 AI 响应...")

        # 等待响应完成（跳过发送前已有的内容）
        response = await self._wait_for_response_complete(pre_content)
        if DEBUG:
            print(f"  [TIMING] 等待响应: {time.time() - t_sent:.1f}s")
            print(f"  [TIMING] send_message 总耗时: {time.time() - t_start:.1f}s")

        return response

    async def _wait_for_response_complete(self, pre_content: str = "") -> str:
        """等待响应完成并返回内容

        双重稳定检测：
        - 快速路径：内容稳定 + 未在生成 → 0.6秒内返回
        - 兜底路径：内容稳定3秒（即使生成指示器误报）→ 仍视为完成

        Args:
            pre_content: 发送前页面已有的内容，用于跳过旧内容
        """
        t_start = time.time()
        t_first_content = None
        last_content = ""
        stable_count = 0        # 快速路径计数（内容稳定 + 非生成状态）
        stable_count_slow = 0   # 兜底路径计数（内容稳定，忽略生成状态）
        max_stable = 2          # 快速路径：2次 × 0.3s = 0.6s
        max_stable_slow = 3     # 兜底路径：3次 × 0.3s ≈ 1s
        check_interval = 0.3
        timeout_ms = TIMEOUT["response_wait"]
        max_checks = int(timeout_ms / (check_interval * 1000))

        for i in range(max_checks):
            # 检查是否有停止按钮或加载指示器（即时查询，不等待）
            is_generating = await self._is_generating()

            # 获取最新回复内容
            current_content = await self._get_latest_response()

            # 跳过发送前已有的内容（页面残留的旧响应/UI文本）
            if current_content and current_content == pre_content:
                await asyncio.sleep(check_interval)
                continue

            if current_content:
                if t_first_content is None:
                    t_first_content = time.time()
                    if DEBUG:
                        print(f"  [TIMING] 首次检测到新内容: {t_first_content - t_start:.1f}s")
                    print(f"  [DEBUG] 新内容预览: {current_content[:80]!r}")

                if current_content == last_content:
                    if not is_generating:
                        # 快速路径：内容稳定 + 无生成指示器
                        stable_count += 1
                        if stable_count >= max_stable:
                            if DEBUG:
                                print(f"  [TIMING] 内容稳定确认: {time.time() - t_start:.1f}s (检查 {i+1} 轮)")
                            print("✓ 响应完成")
                            return current_content
                    else:
                        # 兜底路径：内容稳定但生成指示器仍在（可能是误报）
                        stable_count_slow += 1
                        if stable_count_slow >= max_stable_slow:
                            if DEBUG:
                                print(f"  [TIMING] 内容稳定确认(兜底): {time.time() - t_start:.1f}s (检查 {i+1} 轮)")
                                print(f"  [DEBUG] 生成指示器仍存在但内容已稳定3秒，视为完成")
                            print("✓ 响应完成")
                            return current_content
                else:
                    stable_count = 0
                    stable_count_slow = 0
                    last_content = current_content

            await asyncio.sleep(check_interval)

        # 超时但有内容，返回当前内容
        if last_content:
            print("  [WARN] 响应超时，返回当前内容")
            return last_content

        raise Exception("获取响应超时")

    async def _is_generating(self) -> bool:
        """检查是否正在生成响应

        使用即时 query_selector 代替 wait_for_selector，
        避免每次调用耗费 ~1 秒的超时等待。
        """
        # 检查停止按钮
        for selector in SELECTORS["stop_button"]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    if self._stop_selector != selector and DEBUG:
                        print(f"  [DEBUG] 停止按钮命中: {selector}")
                        self._stop_selector = selector
                    return True
            except Exception:
                continue

        # 检查加载指示器
        for selector in SELECTORS["loading"]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    if self._loading_selector != selector and DEBUG:
                        print(f"  [DEBUG] 加载指示器命中: {selector}")
                        self._loading_selector = selector
                    return True
            except Exception:
                continue

        return False

    async def _get_latest_response(self) -> str:
        """获取最新的 AI 回复内容"""
        messages, selector = await find_all_elements(
            self.page,
            SELECTORS["assistant_message"]
        )

        if messages:
            if self._response_selector != selector and DEBUG:
                print(f"  [DEBUG] 回复消息选择器命中: {selector}")
                self._response_selector = selector
            last_message = messages[-1]
            try:
                content = await last_message.inner_text()
                return content.strip()
            except Exception:
                return ""
        return ""

    async def _dump_input_area_elements(self) -> None:
        """诊断：dump 输入区域附近所有可点击元素的标签、class、aria-label"""
        print("  [DEBUG] === 诊断：输入区域附近的可点击元素 ===")
        elements = await self.page.evaluate("""() => {
            const results = [];
            // 查找输入区域容器
            const container = document.querySelector('[class*="chat-input"]')
                || document.querySelector('textarea')?.parentElement?.parentElement?.parentElement;
            if (!container) {
                return ['未找到输入区域容器'];
            }
            // 遍历容器及其父元素中的所有可点击元素
            const root = container.parentElement || container;
            const clickables = root.querySelectorAll('button, a, [role="button"], svg, [onclick], div[class*="btn"], div[class*="icon"], span[class*="btn"], span[class*="icon"]');
            clickables.forEach(el => {
                const tag = el.tagName.toLowerCase();
                const cls = el.className && typeof el.className === 'string' ? el.className : '';
                const aria = el.getAttribute('aria-label') || '';
                const title = el.getAttribute('title') || '';
                const text = el.textContent?.trim()?.substring(0, 20) || '';
                results.push(`<${tag}> class="${cls}" aria="${aria}" title="${title}" text="${text}"`);
            });
            return results;
        }""")
        for el in elements:
            print(f"    {el}")
        print("  [DEBUG] === 诊断结束 ===")

    async def upload_image(self, image_path: str) -> bool:
        """上传图片

        百度的流程：点击图片图标 → 弹出菜单 → 点击"上传本地图片" → file_chooser 选择文件

        Args:
            image_path: 图片文件路径

        Returns:
            是否上传成功
        """
        if not Path(image_path).exists():
            print(f"  ✗ 图片文件不存在: {image_path}")
            return False

        print(f"→ 上传图片: {image_path}")
        t_upload_start = time.time()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 1. 点击图片上传按钮
                img_btn, selector = await find_element(
                    self.page,
                    SELECTORS["image_upload_button"],
                    timeout=5000,
                    debug=DEBUG and attempt == 0
                )
                if not img_btn:
                    # 诊断：dump 输入区域附近的可点击元素，帮助定位正确选择器
                    if DEBUG:
                        await self._dump_input_area_elements()
                    print("  ✗ 找不到图片上传按钮")
                    return False

                await img_btn.click()
                if DEBUG:
                    print(f"  [DEBUG] 点击图片上传按钮: {selector}")

                # 2. 等待菜单出现，点击"上传本地图片"
                menu_item, _ = await find_element(
                    self.page,
                    SELECTORS["upload_local_image"],
                    timeout=3000,
                    debug=False
                )

                if not menu_item:
                    if DEBUG:
                        print(f"  [DEBUG] 上传菜单未出现 (尝试 {attempt + 1}/{max_retries})")
                    try:
                        await self.page.mouse.click(10, 10)
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)
                    continue

                # 3. 使用 file chooser 拦截文件选择
                async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                    await menu_item.click()
                    if DEBUG:
                        print("  [DEBUG] 点击上传本地图片菜单成功")

                # 4. 设置文件
                file_chooser = await fc_info.value
                await file_chooser.set_files(image_path)
                print("  → 图片已选择，等待上传...")

                # 5. 等待图片预览出现（确认上传完成）
                preview, _ = await find_element(
                    self.page,
                    SELECTORS["image_preview"],
                    timeout=15000,
                    debug=DEBUG
                )
                if preview:
                    if DEBUG:
                        print(f"  [TIMING] 图片上传: {time.time() - t_upload_start:.1f}s")
                    print("  ✓ 图片上传完成")
                    return True
                else:
                    print("  [WARN] 未检测到图片预览，但继续执行")
                    return True

            except Exception as e:
                if attempt < max_retries - 1:
                    if DEBUG:
                        print(f"  [DEBUG] 上传尝试 {attempt + 1} 失败: {e}，重试中...")
                    try:
                        await self.page.mouse.click(10, 10)
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                else:
                    print(f"  ✗ 上传图片失败: {e}")
                    return False

        print("  ✗ 上传图片失败：多次重试后仍无法打开上传菜单")
        return False

    async def send_message_with_image(self, prompt: str, image_path: str) -> str:
        """发送带图片的消息

        Args:
            prompt: 文字内容
            image_path: 图片路径

        Returns:
            AI 回复内容
        """
        t_total = time.time()

        # 上传图片
        if not await self.upload_image(image_path):
            raise Exception("图片上传失败")

        # 短暂等待
        await asyncio.sleep(0.5)

        # 发送消息
        response = await self.send_message(prompt)
        if DEBUG:
            print(f"  [TIMING] send_message_with_image 总耗时: {time.time() - t_total:.1f}s")
        return response

    async def new_chat(self) -> None:
        """开启新对话"""
        # 重置缓存的选择器
        self._input_selector = None
        self._send_selector = None

        # 尝试查找新对话按钮
        new_chat_selectors = [
            'button[aria-label*="新对话"]',
            'button[aria-label*="新建"]',
            '[class*="new-chat"]',
            '[class*="newChat"]',
        ]
        btn, _ = await find_element(self.page, new_chat_selectors, timeout=3000)
        if btn:
            await btn.click()
        else:
            # 直接导航到首页
            print("  [INFO] 未找到新对话按钮，导航到首页...")
            await self.page.goto(BAIDU_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
            await self.page.wait_for_load_state("networkidle", timeout=30000)

        # 等待输入框出现，确认页面已就绪
        await find_element(self.page, SELECTORS["logged_in_indicator"], timeout=5000)
        print("✓ 已开启新对话")
