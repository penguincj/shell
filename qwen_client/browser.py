"""浏览器核心模块"""
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .config import (
    QWEN_URL,
    COOKIES_FILE,
    STATE_FILE,
    STATE_DIR,
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
        """加载状态并跳转到千问页面"""
        # 优先使用 storage_state（包含 cookies + localStorage）
        if STATE_FILE.exists():
            print(f"✓ 已找到状态文件: {STATE_FILE}")
            # 需要重新创建 context 来加载 storage_state
            await self.page.close()
            await self.context.close()

            self.context = await self.browser.new_context(
                user_agent=BROWSER_CONFIG["user_agent"],
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                storage_state=str(STATE_FILE),
            )
            self.page = await self.context.new_page()

            # 调试：打印加载的 cookies
            if DEBUG:
                loaded_cookies = await self.context.cookies()
                print(f"  [DEBUG] 从状态文件加载了 {len(loaded_cookies)} 个 cookies")
                for c in loaded_cookies[:5]:  # 只打印前5个
                    print(f"    - {c.get('name')}: domain={c.get('domain')}")

            print("→ 正在加载页面...")
            await self.page.goto(QWEN_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
            await self.page.wait_for_load_state("networkidle", timeout=30000)

            # 调试：打印页面加载后的 cookies
            if DEBUG:
                current_cookies = await self.context.cookies()
                print(f"  [DEBUG] 页面加载后有 {len(current_cookies)} 个 cookies")

            if await self._check_logged_in():
                self._is_logged_in = True
                print("✓ 登录状态有效")
                return True
            else:
                print("✗ 状态已过期，需要重新登录")
                return False

        # 兼容旧的 cookies 文件
        cookies = load_cookies(COOKIES_FILE)
        if cookies:
            if DEBUG:
                print(f"  [DEBUG] 从文件加载了 {len(cookies)} 个 cookies")

            await self.context.add_cookies(cookies)
            print("→ 正在加载页面...")
            await self.page.goto(QWEN_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
            await self.page.wait_for_load_state("networkidle", timeout=30000)

            # 调试：打印页面加载后的 cookies
            if DEBUG:
                current_cookies = await self.context.cookies()
                print(f"  [DEBUG] 页面加载后有 {len(current_cookies)} 个 cookies")

            if await self._check_logged_in():
                self._is_logged_in = True
                print("✓ 登录状态有效")
                return True
            else:
                print("✗ Cookies 已过期，需要重新登录")
                return False

        print("→ 未找到登录状态，需要登录")
        await self.page.goto(QWEN_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
        await self.page.wait_for_load_state("networkidle", timeout=30000)
        return False

    async def _check_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            if DEBUG:
                print("→ 检查登录状态...")

            # 先检查是否有"立即登录"按钮（未登录标识）
            not_logged_in, selector = await find_element(
                self.page,
                SELECTORS["not_logged_in_indicator"],
                timeout=3000,
                debug=False
            )
            if not_logged_in:
                if DEBUG:
                    print(f"  ✗ 检测到未登录标识: {selector}")
                return False

            # 再检查是否有登录后才出现的元素
            element, selector = await find_element(
                self.page,
                SELECTORS["logged_in_indicator"],
                timeout=5000,
                debug=DEBUG
            )
            if element and DEBUG:
                print(f"  ✓ 检测到登录元素: {selector}")
            return element is not None
        except Exception as e:
            if DEBUG:
                print(f"  ✗ 检查登录状态异常: {e}")
            return False

    async def wait_for_login(self) -> None:
        """等待用户手动登录"""
        print("\n" + "=" * 50)
        print("请在浏览器中完成登录操作")
        print("支持: 扫码登录 / 账号密码登录")
        print("=" * 50 + "\n")

        try:
            print("→ 等待用户完成登录...")

            # 核心逻辑：等待"立即登录"按钮消失（说明用户已登录）
            # 使用轮询方式检测
            import time
            start_time = time.time()
            timeout_seconds = TIMEOUT["login_wait"] / 1000

            while (time.time() - start_time) < timeout_seconds:
                # 检查"立即登录"按钮是否还存在
                not_logged_in, _ = await find_element(
                    self.page,
                    SELECTORS["not_logged_in_indicator"],
                    timeout=2000,
                    debug=False
                )

                if not not_logged_in:
                    # "立即登录"按钮消失了，说明已登录
                    print("✓ 检测到登录成功（登录按钮已消失）")
                    self._is_logged_in = True

                    # 等待一段时间确保登录状态完全生效
                    print("→ 等待登录状态稳定...")
                    await asyncio.sleep(3)

                    # 刷新页面确保状态完整
                    await self.page.reload()
                    await self.page.wait_for_load_state("networkidle", timeout=30000)
                    await asyncio.sleep(2)

                    # 再次确认登录状态
                    not_logged_in_check, _ = await find_element(
                        self.page,
                        SELECTORS["not_logged_in_indicator"],
                        timeout=3000,
                        debug=False
                    )
                    if not_logged_in_check:
                        print("  [WARN] 刷新后登录状态丢失，继续等待...")
                        continue

                    # 保存完整状态
                    await self.save_current_cookies()
                    return

                await asyncio.sleep(1)

            raise Exception("登录超时")
        except Exception as e:
            print(f"✗ 登录失败: {e}")
            raise

    async def save_current_cookies(self) -> None:
        """保存当前状态"""
        # 确保目录存在
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        # 获取当前 cookies
        cookies = await self.context.cookies()

        if DEBUG:
            print(f"  [DEBUG] 保存 {len(cookies)} 个 cookies:")
            for c in cookies:
                print(f"    - {c.get('name')}: {c.get('value')[:20]}... (domain: {c.get('domain')})")

        # 保存完整的 storage state
        await self.context.storage_state(path=str(STATE_FILE))
        print(f"✓ 状态已保存到 {STATE_FILE}")

        # 同时保存 cookies（兼容）
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
