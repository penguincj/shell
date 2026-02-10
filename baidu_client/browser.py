"""浏览器核心模块"""
import asyncio
import time
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .config import (
    BAIDU_URL,
    STATE_FILE,
    STATE_DIR,
    TIMEOUT,
    SELECTORS,
    BROWSER_CONFIG,
    DEBUG,
)
from .utils import find_element, save_cookies, load_cookies


class BaiduBrowser:
    """百度文心助手浏览器管理器"""

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

        t_start = time.time()
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
        if DEBUG:
            print(f"  [TIMING] 浏览器启动: {time.time() - t_start:.1f}s")
        print("✓ 浏览器已启动")

    async def load_cookies_and_goto(self) -> bool:
        """加载状态并跳转到百度文心页面"""
        t_start = time.time()

        # 使用 storage_state（包含 cookies + localStorage）
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
                for c in loaded_cookies[:5]:
                    print(f"    - {c.get('name')}: domain={c.get('domain')}")

            t_nav = time.time()
            print("→ 正在加载页面...")
            await self.page.goto(BAIDU_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])

            if DEBUG:
                print(f"  [TIMING] 页面导航(domcontentloaded): {time.time() - t_nav:.1f}s")

            t_login_check = time.time()
            if await self._check_logged_in():
                self._is_logged_in = True
                if DEBUG:
                    print(f"  [TIMING] 登录检查: {time.time() - t_login_check:.1f}s")
                    print(f"  [TIMING] load_cookies_and_goto 总耗时: {time.time() - t_start:.1f}s")
                print("✓ 登录状态有效")
                return True
            else:
                print("✗ 状态已过期，需要重新登录")
                return False

        print("→ 未找到登录状态，需要登录")
        await self.page.goto(BAIDU_URL, wait_until="domcontentloaded", timeout=TIMEOUT["navigation"])
        return False

    async def _check_logged_in(self) -> bool:
        """检查是否已登录

        策略：先等输入框出现（确认页面渲染完成，不论是否登录都有），
        再用即时 query_selector 检查"登录"按钮。
        避免对不存在的元素做 wait_for_selector 长时间等待。
        """
        try:
            if DEBUG:
                print("→ 检查登录状态...")

            # 1. 等待页面渲染完成（输入框出现，不论登录与否都有）
            page_ready = False
            for sel in SELECTORS["logged_in_indicator"]:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=1000)
                    if el:
                        page_ready = True
                        break
                except Exception:
                    continue

            if not page_ready:
                if DEBUG:
                    print("  ✗ 页面未渲染完成")
                return False

            # 2. 页面已渲染，即时检查"登录"按钮（不等待）
            for sel in SELECTORS["not_logged_in_indicator"]:
                try:
                    el = await self.page.query_selector(sel)
                    if el and await el.is_visible():
                        if DEBUG:
                            print(f"  ✗ 检测到未登录标识: {sel}")
                        return False
                except Exception:
                    continue

            if DEBUG:
                print("  ✓ 页面已加载且无登录按钮")
            return True
        except Exception as e:
            if DEBUG:
                print(f"  ✗ 检查登录状态异常: {e}")
            return False

    async def wait_for_login(self) -> None:
        """等待用户手动登录"""
        print("\n" + "=" * 50)
        print("请在浏览器中完成登录操作")
        print("支持: 扫码登录 / 账号密码登录 / 短信登录")
        print("=" * 50 + "\n")

        try:
            print("→ 等待用户完成登录...")

            # 核心逻辑：等待"登录"按钮消失（说明用户已登录）
            start_time = time.time()
            timeout_seconds = TIMEOUT["login_wait"] / 1000

            while (time.time() - start_time) < timeout_seconds:
                # 检查"登录"按钮是否还存在
                not_logged_in, _ = await find_element(
                    self.page,
                    SELECTORS["not_logged_in_indicator"],
                    timeout=2000,
                    debug=False
                )

                if not not_logged_in:
                    # "登录"按钮消失了，说明已登录
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
