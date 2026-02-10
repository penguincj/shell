"""工具函数 - 复用 qwen_client 的通用函数"""
import json
import re

from qwen_client.utils import find_element, find_all_elements, save_cookies, load_cookies


def extract_json(text: str):
    """从 AI 回复中提取 JSON 对象

    AI 回复可能包含 JSON 以外的多余文字，用正则提取最外层 {} 并解析。
    """
    # 匹配最外层 { ... }（贪婪匹配，取最长的）
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def print_banner():
    """打印启动横幅"""
    banner = """
╔═══════════════════════════════════════╗
║       Baidu AI Client                 ║
║   百度文心助手网页版自动化工具        ║
╚═══════════════════════════════════════╝
    """
    print(banner)
