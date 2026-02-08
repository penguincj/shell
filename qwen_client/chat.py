"""聊天逻辑模块"""
import asyncio
import time
from pathlib import Path
from playwright.async_api import Page

from .config import SELECTORS, TIMEOUT, DEBUG
from .utils import find_element, find_all_elements


class QwenChat:
    """千问聊天管理器"""

    def __init__(self, page: Page):
        self.page = page
        self._input_selector = None
        self._send_selector = None

    async def _ensure_selectors(self) -> None:
        """确保已找到输入框和发送按钮的选择器"""
        if not self._input_selector:
            _, self._input_selector = await find_element(
                self.page,
                SELECTORS["input_box"],
                timeout=TIMEOUT["element"]
            )
            if not self._input_selector:
                raise Exception("找不到输入框，请检查页面是否加载完成或更新选择器配置")
            print(f"  [DEBUG] 输入框选择器: {self._input_selector}")

        if not self._send_selector:
            _, self._send_selector = await find_element(
                self.page,
                SELECTORS["send_button"],
                timeout=TIMEOUT["element"]
            )
            # 发送按钮可能不存在（有些是按回车发送）
            if self._send_selector:
                print(f"  [DEBUG] 发送按钮选择器: {self._send_selector}")

    async def send_message(self, prompt: str) -> str:
        """发送消息并等待响应"""
        t_start = time.time()
        await self._ensure_selectors()

        print(f"→ 发送消息: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

        # 输入消息
        input_box = await self.page.wait_for_selector(
            self._input_selector,
            timeout=TIMEOUT["element"]
        )

        # 清空并输入新内容
        await input_box.click()
        # 对于 contenteditable 元素，先选中全部再删除
        await self.page.keyboard.press("Control+a")
        await self.page.keyboard.press("Backspace")
        # 使用 type 而不是 fill，更适合 contenteditable 元素
        await self.page.keyboard.type(prompt, delay=50)

        # 短暂等待确保输入完成
        await asyncio.sleep(0.5)
        if DEBUG:
            print(f"  [TIMING] 输入消息: {time.time() - t_start:.1f}s")

        # 发送消息 - 优先尝试点击发送按钮
        sent = False
        if self._send_selector:
            try:
                send_btn = await self.page.wait_for_selector(
                    self._send_selector,
                    timeout=3000
                )
                if send_btn and await send_btn.is_visible():
                    await send_btn.click()
                    sent = True
                    print("  [DEBUG] 点击发送按钮")
            except Exception as e:
                print(f"  [DEBUG] 发送按钮点击失败: {e}")

        # 如果没有发送按钮或点击失败，尝试直接查找并点击页面上可见的发送按钮
        if not sent:
            # 尝试更多发送按钮选择器
            fallback_selectors = [
                '[class*="sendBtn"]',
                '[class*="send-btn"]',
                '[class*="submit"]',
                'button:has(svg[class*="arrow"])',
                '[class*="chatInput"] ~ button',
                '[class*="text-area-slot-container"] button',
            ]
            for sel in fallback_selectors:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=1000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        sent = True
                        print(f"  [DEBUG] 使用备选按钮发送: {sel}")
                        break
                except Exception:
                    continue

        # 最后尝试回车发送
        if not sent:
            print("  [DEBUG] 尝试使用回车发送")
            await self.page.keyboard.press("Enter")

        t_sent = time.time()
        if DEBUG:
            print(f"  [TIMING] 发送消息: {t_sent - t_start:.1f}s")
        print("→ 等待 AI 响应...")

        # 等待响应完成
        response = await self._wait_for_response_complete()
        if DEBUG:
            print(f"  [TIMING] 等待响应: {time.time() - t_sent:.1f}s")
            print(f"  [TIMING] send_message 总耗时: {time.time() - t_start:.1f}s")

        return response

    async def _wait_for_response_complete(self) -> str:
        """等待响应完成并返回内容

        使用即时 DOM 查询检测生成状态，避免 wait_for_selector 超时带来的延迟。
        AI 完成后预计 ~0.6 秒内返回（2 次稳定检查 × 0.3 秒间隔）。
        """
        t_start = time.time()
        t_first_content = None
        last_content = ""
        stable_count = 0
        max_stable = 2  # 内容稳定 0.6 秒即认为完成（每 0.3 秒检查）
        check_interval = 0.3
        timeout_ms = TIMEOUT["response_wait"]
        max_checks = int(timeout_ms / (check_interval * 1000))

        for i in range(max_checks):
            # 检查是否有停止按钮或加载指示器（即时查询，不等待）
            is_generating = await self._is_generating()

            # 获取最新回复内容
            current_content = await self._get_latest_response()

            if current_content:
                if t_first_content is None:
                    t_first_content = time.time()
                    if DEBUG:
                        print(f"  [TIMING] 首次检测到内容: {t_first_content - t_start:.1f}s")

                if current_content == last_content and not is_generating:
                    stable_count += 1
                    if stable_count >= max_stable:
                        if DEBUG:
                            print(f"  [TIMING] 内容稳定确认: {time.time() - t_start:.1f}s (检查 {i+1} 轮)")
                        print("✓ 响应完成")
                        return current_content
                else:
                    stable_count = 0
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
                    return True
            except Exception:
                continue

        # 检查加载指示器
        for selector in SELECTORS["loading"]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
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
            last_message = messages[-1]
            try:
                content = await last_message.inner_text()
                return content.strip()
            except Exception:
                return ""
        return ""

    async def upload_image(self, image_path: str) -> bool:
        """上传图片

        Args:
            image_path: 图片文件路径

        Returns:
            是否上传成功
        """
        # 检查文件是否存在
        if not Path(image_path).exists():
            print(f"  ✗ 图片文件不存在: {image_path}")
            return False

        print(f"→ 上传图片: {image_path}")
        t_upload_start = time.time()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 1. 点击附件按钮
                attach_btn, selector = await find_element(
                    self.page,
                    SELECTORS["attachment_button"],
                    timeout=5000,
                    debug=DEBUG and attempt == 0
                )
                if not attach_btn:
                    print("  ✗ 找不到附件按钮")
                    return False

                # 点击展开菜单
                await attach_btn.click()
                if DEBUG:
                    print(f"  [DEBUG] 点击附件按钮: {selector}")

                # 验证下拉菜单是否出现（wait_for_selector 自带等待）
                menu_item = None
                try:
                    menu_item = await self.page.wait_for_selector('text=上传图片', timeout=3000)
                    if menu_item and not await menu_item.is_visible():
                        menu_item = None
                except Exception:
                    pass

                if not menu_item:
                    if DEBUG:
                        print(f"  [DEBUG] 下拉菜单未出现 (尝试 {attempt + 1}/{max_retries})")
                    # 点击空白处关闭可能的弹出状态，然后重试
                    try:
                        await self.page.mouse.click(10, 10)
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)
                    continue

                # 调试：打印页面上包含"上传"文字的元素
                if DEBUG and attempt == 0:
                    print("  [DEBUG] 查找包含'上传'的元素...")
                    try:
                        elements = await self.page.query_selector_all('*')
                        for el in elements:
                            try:
                                text = await el.inner_text()
                                if '上传' in text and len(text) < 20:
                                    tag = await el.evaluate('el => el.tagName')
                                    class_name = await el.evaluate('el => el.className')
                                    print(f"    - <{tag}> class=\"{class_name}\" text=\"{text}\"")
                            except:
                                pass
                    except Exception as e:
                        print(f"  [DEBUG] 查找元素失败: {e}")

                # 2. 使用 file chooser 拦截文件选择，直接点击已找到的菜单项
                async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                    await menu_item.click()
                    if DEBUG:
                        print("  [DEBUG] 点击上传图片菜单成功")

                # 3. 设置文件
                file_chooser = await fc_info.value
                await file_chooser.set_files(image_path)
                print("  → 图片已选择，等待上传...")

                # 4. 等待图片预览出现（确认上传完成）
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

        # 先开启新对话，确保在干净的聊天页面（避免已有对话影响元素匹配）
        await self.new_chat()
        if DEBUG:
            print(f"  [TIMING] new_chat: {time.time() - t_total:.1f}s")

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
        """开启新对话（如果页面支持）"""
        # 重置缓存的选择器（新页面可能需要重新查找）
        self._input_selector = None
        self._send_selector = None

        # 尝试查找新对话按钮
        new_chat_selectors = [
            'button[aria-label*="新对话"]',
            'button[aria-label*="新建"]',
            '[class*="new-chat"]',
            '[class*="newChat"]',
            'a[href="/chat"]',
        ]
        btn, _ = await find_element(self.page, new_chat_selectors, timeout=3000)
        if btn:
            await btn.click()
        else:
            # 直接导航到聊天首页，确保获得干净的对话页面
            from .config import QWEN_URL, TIMEOUT
            print("  [INFO] 未找到新对话按钮，导航到聊天首页...")
            await self.page.goto(QWEN_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
            await self.page.wait_for_load_state("networkidle", timeout=30000)

        # 等待输入框出现，确认页面已就绪（而非固定 sleep）
        await find_element(self.page, SELECTORS["logged_in_indicator"], timeout=5000)
        print("✓ 已开启新对话")
