"""浏览器核心模块"""
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .config import (
    QWEN_URL,
    COOKIES_FILE,
    TIMEOUT,
    SELECTORS,
    BROWSER_CONFIG,
    DEBUG,
)
from .utils import find_element, save_cookies, load_cookies


class QwenBrowser:
    """千问浏览器管理器"""

    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self._is_logged_in = False

    async def launch(self, headless: bool = None) -> None:
        """启动浏览器"""
        if headless is None:
            headless = BROWSER_CONFIG["headless"]

        print(f"→ 启动浏览器 (headless={headless})...")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            slow_mo=BROWSER_CONFIG["slow_mo"],
            args=BROWSER_CONFIG["args"],
        )

        # 创建上下文，设置反检测参数
        self.context = await self.browser.new_context(
            user_agent=BROWSER_CONFIG["user_agent"],
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # 注入反检测脚本
        await self.context.add_init_script("""
            // 隐藏 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 模拟真实的 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 模拟真实的 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)

        self.page = await self.context.new_page()
        print("✓ 浏览器已启动")

    async def load_cookies_and_goto(self) -> bool:
        """加载 cookies 并跳转到千问页面"""
        cookies = load_cookies(COOKIES_FILE)

        if cookies:
            await self.context.add_cookies(cookies)
            print("→ 正在加载页面...")
            await self.page.goto(QWEN_URL, timeout=TIMEOUT["navigation"])

            # 检查是否已登录
            if await self._check_logged_in():
                self._is_logged_in = True
                print("✓ 登录状态有效")
                return True
            else:
                print("✗ Cookies 已过期，需要重新登录")
                return False
        else:
            print("→ 未找到 Cookies，需要登录")
            await self.page.goto(QWEN_URL, timeout=TIMEOUT["navigation"])
            return False

    async def _check_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            element, _ = await find_element(
                self.page,
                SELECTORS["logged_in_indicator"],
                timeout=5000
            )
            return element is not None
        except Exception:
            return False

    async def wait_for_login(self) -> None:
        """等待用户手动登录"""
        print("\n" + "=" * 50)
        print("请在浏览器中完成登录操作")
        print("支持: 扫码登录 / 账号密码登录")
        print("=" * 50 + "\n")

        # 等待登录成功标识出现
        try:
            print("→ 开始检测登录状态...")
            element, selector = await find_element(
                self.page,
                SELECTORS["logged_in_indicator"],
                timeout=TIMEOUT["login_wait"],
                debug=DEBUG
            )
            if element:
                print(f"✓ 检测到登录成功 (selector: {selector})")
                self._is_logged_in = True

                # 保存 cookies
                await self.save_current_cookies()
            else:
                raise Exception("登录超时")
        except Exception as e:
            print(f"✗ 登录失败: {e}")
            raise

    async def save_current_cookies(self) -> None:
        """保存当前 cookies"""
        cookies = await self.context.cookies()
        save_cookies(cookies, COOKIES_FILE)

    async def refresh_page(self) -> None:
        """刷新页面"""
        await self.page.reload(timeout=TIMEOUT["navigation"])
        await asyncio.sleep(1)

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    async def close(self) -> None:
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("✓ 浏览器已关闭")
