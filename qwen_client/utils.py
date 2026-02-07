"""工具函数"""
import json
from pathlib import Path
from typing import Optional
from playwright.async_api import Page


async def find_element(page: Page, selectors: list[str], timeout: int = 5000, debug: bool = False):
    """尝试多个选择器，返回第一个找到的元素

    对于长超时场景，会循环快速尝试所有选择器，而不是每个选择器等待全部超时时间
    """
    import time
    start_time = time.time()
    per_selector_timeout = min(2000, timeout)  # 每个选择器最多等 2 秒

    attempt = 0
    while (time.time() - start_time) * 1000 < timeout:
        attempt += 1
        if debug and attempt == 1:
            print(f"  尝试选择器列表: {selectors}")

        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=per_selector_timeout)
                if element:
                    if debug:
                        print(f"  ✓ 匹配成功: {selector}")
                    return element, selector
            except Exception:
                continue

        if debug and attempt == 1:
            print(f"  ✗ 第一轮所有选择器均未匹配，继续轮询...")

    if debug:
        print(f"  ✗ 超时，共尝试 {attempt} 轮")
    return None, None


async def find_all_elements(page: Page, selectors: list[str]):
    """尝试多个选择器，返回第一个有结果的元素列表"""
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                return elements, selector
        except Exception:
            continue
    return [], None


def save_cookies(cookies: list[dict], filepath: Path) -> None:
    """保存 cookies 到文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✓ Cookies 已保存到 {filepath}")


def load_cookies(filepath: Path) -> Optional[list[dict]]:
    """从文件加载 cookies"""
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        print(f"✓ 已加载 Cookies: {filepath}")
        return cookies
    except Exception as e:
        print(f"✗ 加载 Cookies 失败: {e}")
        return None


def print_banner():
    """打印启动横幅"""
    banner = """
╔═══════════════════════════════════════╗
║         Qwen Web Client               ║
║   通义千问网页版自动化工具            ║
╚═══════════════════════════════════════╝
    """
    print(banner)
