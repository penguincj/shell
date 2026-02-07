"""工具函数"""
import json
from pathlib import Path
from typing import Optional
from playwright.async_api import Page


async def find_element(page: Page, selectors: list[str], timeout: int = 5000):
    """尝试多个选择器，返回第一个找到的元素"""
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element:
                return element, selector
        except Exception:
            continue
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
