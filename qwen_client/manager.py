"""浏览器生命周期管理 + 请求串行化"""
import asyncio
import time
from typing import Optional

from .browser import QwenBrowser
from .chat import QwenChat
from .config import DEBUG


class BrowserManager:
    """浏览器常驻管理器

    - asyncio.Lock 串行化请求（一个浏览器同时只处理一个对话）
    - 每 N 次请求做一次 new_chat 清理上下文
    - 请求前 page.title() 探活，失败则自动重启
    """

    NEW_CHAT_INTERVAL = 50  # 每 50 次请求清理一次对话

    def __init__(self):
        self._browser: Optional[QwenBrowser] = None
        self._chat: Optional[QwenChat] = None
        self._lock = asyncio.Lock()
        self._request_count = 0
        self._started = False

    @property
    def is_ready(self) -> bool:
        return self._started and self._browser is not None and self._chat is not None

    @property
    def request_count(self) -> int:
        return self._request_count

    async def startup(self) -> None:
        """启动浏览器并加载登录状态"""
        print("→ BrowserManager 启动中...")
        self._browser = QwenBrowser()
        await self._browser.launch()
        logged_in = await self._browser.load_cookies_and_goto()
        if not logged_in:
            raise RuntimeError("未登录，请先运行: DEBUG=1 python main.py --login")
        self._chat = QwenChat(self._browser.page)
        self._request_count = 0
        self._started = True
        print("✓ BrowserManager 就绪")

    async def shutdown(self) -> None:
        """关闭浏览器"""
        self._started = False
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._chat = None
        print("✓ BrowserManager 已关闭")

    async def restart(self) -> None:
        """重启浏览器"""
        print("→ BrowserManager 重启中...")
        await self.shutdown()
        await self.startup()

    async def _health_check(self) -> bool:
        """探活：尝试获取页面 title"""
        try:
            await self._browser.page.title()
            return True
        except Exception:
            return False

    async def chat(self, prompt: str, image_path: Optional[str] = None) -> str:
        """发送消息并返回 AI 回复

        Args:
            prompt: 消息文本
            image_path: 可选，服务器本地图片路径

        Returns:
            AI 回复文本
        """
        async with self._lock:
            # 探活
            if not await self._health_check():
                print("  [WARN] 页面不可用，自动重启浏览器...")
                await self.restart()

            # 每 N 次请求清理对话上下文
            if self._request_count > 0 and self._request_count % self.NEW_CHAT_INTERVAL == 0:
                print(f"  [INFO] 已处理 {self._request_count} 次请求，清理对话上下文...")
                await self._chat.new_chat()

            t_start = time.time()

            if image_path:
                response = await self._chat.send_message_with_image(prompt, image_path)
            else:
                response = await self._chat.send_message(prompt)

            self._request_count += 1

            if DEBUG:
                print(f"  [TIMING] BrowserManager.chat 耗时: {time.time() - t_start:.1f}s")

            return response
