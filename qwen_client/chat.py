"""聊天逻辑模块"""
import asyncio
from playwright.async_api import Page

from .config import SELECTORS, TIMEOUT
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
        await self._ensure_selectors()

        print(f"→ 发送消息: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

        # 获取发送前的消息数量
        messages_before = await self._get_message_count()

        # 输入消息
        input_box = await self.page.wait_for_selector(
            self._input_selector,
            timeout=TIMEOUT["element"]
        )

        # 清空并输入新内容
        await input_box.click()
        await input_box.fill("")
        await input_box.fill(prompt)

        # 短暂等待确保输入完成
        await asyncio.sleep(0.3)

        # 发送消息
        if self._send_selector:
            try:
                send_btn = await self.page.wait_for_selector(
                    self._send_selector,
                    timeout=3000
                )
                if send_btn:
                    await send_btn.click()
            except Exception:
                # 发送按钮不可用，尝试回车
                await input_box.press("Enter")
        else:
            # 没有发送按钮，使用回车
            await input_box.press("Enter")

        print("→ 等待 AI 响应...")

        # 等待新消息出现
        await self._wait_for_new_message(messages_before)

        # 等待响应完成
        response = await self._wait_for_response_complete()

        return response

    async def _get_message_count(self) -> int:
        """获取当前消息数量"""
        messages, _ = await find_all_elements(
            self.page,
            SELECTORS["assistant_message"]
        )
        return len(messages)

    async def _wait_for_new_message(self, count_before: int, max_wait: int = 30) -> None:
        """等待新消息出现"""
        for _ in range(max_wait * 2):  # 每0.5秒检查一次
            messages, _ = await find_all_elements(
                self.page,
                SELECTORS["assistant_message"]
            )
            if len(messages) > count_before:
                return
            await asyncio.sleep(0.5)
        print("  [WARN] 等待新消息超时，继续尝试获取响应...")

    async def _wait_for_response_complete(self) -> str:
        """等待响应完成并返回内容"""
        last_content = ""
        stable_count = 0
        max_stable = 6  # 内容稳定3秒（每0.5秒检查）
        timeout_counter = 0
        max_timeout = TIMEOUT["response_wait"] // 500  # 转换为检查次数

        while timeout_counter < max_timeout:
            # 检查是否有停止按钮或加载指示器
            is_generating = await self._is_generating()

            # 获取最新回复内容
            current_content = await self._get_latest_response()

            if current_content:
                if current_content == last_content and not is_generating:
                    stable_count += 1
                    if stable_count >= max_stable:
                        print("✓ 响应完成")
                        return current_content
                else:
                    stable_count = 0
                    last_content = current_content

            await asyncio.sleep(0.5)
            timeout_counter += 1

        # 超时但有内容，返回当前内容
        if last_content:
            print("  [WARN] 响应超时，返回当前内容")
            return last_content

        raise Exception("获取响应超时")

    async def _is_generating(self) -> bool:
        """检查是否正在生成响应"""
        # 检查停止按钮
        stop_btn, _ = await find_element(
            self.page,
            SELECTORS["stop_button"],
            timeout=500
        )
        if stop_btn:
            return True

        # 检查加载指示器
        loading, _ = await find_element(
            self.page,
            SELECTORS["loading"],
            timeout=500
        )
        if loading:
            return True

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

    async def new_chat(self) -> None:
        """开启新对话（如果页面支持）"""
        # 尝试查找新对话按钮
        new_chat_selectors = [
            'button[aria-label*="新对话"]',
            'button[aria-label*="新建"]',
            '[class*="new-chat"]',
            'a[href="/chat"]',
        ]
        btn, _ = await find_element(self.page, new_chat_selectors, timeout=3000)
        if btn:
            await btn.click()
            await asyncio.sleep(1)
            print("✓ 已开启新对话")
        else:
            print("  [INFO] 未找到新对话按钮，刷新页面...")
            await self.page.reload()
            await asyncio.sleep(2)
