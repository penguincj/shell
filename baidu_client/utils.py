"""工具函数 - 复用 qwen_client 的通用函数"""
from qwen_client.utils import find_element, find_all_elements, save_cookies, load_cookies


def print_banner():
    """打印启动横幅"""
    banner = """
╔═══════════════════════════════════════╗
║       Baidu AI Client                 ║
║   百度文心助手网页版自动化工具        ║
╚═══════════════════════════════════════╝
    """
    print(banner)
