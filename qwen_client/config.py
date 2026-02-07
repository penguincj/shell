"""配置管理"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# Cookie 存储路径
COOKIES_DIR = ROOT_DIR / "cookies"
COOKIES_FILE = COOKIES_DIR / "qwen_cookies.json"

# 千问网址
QWEN_URL = "https://www.qianwen.com/chat"

# 环境变量配置
DEBUG = os.getenv("DEBUG", "0") == "1"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))

# 超时配置（毫秒）
TIMEOUT = {
    "navigation": 30000,      # 页面加载超时
    "login_wait": 300000,     # 等待登录超时（5分钟）
    "response_wait": 120000,  # 等待AI响应超时（2分钟）
    "element": 10000,         # 元素等待超时
}

# 页面元素选择器（需要根据实际页面调整）
# 可以使用多个备选选择器
SELECTORS = {
    # 输入框 - 多个备选
    "input_box": [
        'textarea[id="chat-input"]',
        'textarea[placeholder*="输入"]',
        'textarea[placeholder*="消息"]',
        'div[contenteditable="true"]',
        '#chat-input',
    ],
    # 发送按钮
    "send_button": [
        'button[id="send-button"]',
        'button[type="submit"]',
        'button[aria-label*="发送"]',
        'button[class*="send"]',
    ],
    # 消息容器
    "message_container": [
        '.message-list',
        '.chat-messages',
        '[class*="message-container"]',
        '[class*="chat-container"]',
    ],
    # AI回复消息
    "assistant_message": [
        '[class*="assistant"]',
        '[class*="bot-message"]',
        '[data-role="assistant"]',
        '.response-content',
    ],
    # 停止生成按钮（用于判断是否还在生成）
    "stop_button": [
        'button[aria-label*="停止"]',
        'button[class*="stop"]',
        '[class*="stop-generating"]',
    ],
    # 加载指示器
    "loading": [
        '[class*="loading"]',
        '[class*="typing"]',
        '[class*="generating"]',
        '.spinner',
    ],
    # 登录成功标识（确认已登录的元素）
    "logged_in_indicator": [
        'textarea[id="chat-input"]',
        'textarea[placeholder*="输入"]',
        '[class*="chat-input"]',
        '#chat-input',
    ],
}

# 浏览器配置
BROWSER_CONFIG = {
    "headless": not DEBUG,
    "slow_mo": SLOW_MO,
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
