"""配置管理"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# 状态存储路径（包含 Cookies + localStorage + sessionStorage）
STATE_DIR = ROOT_DIR / "state"
STATE_FILE = STATE_DIR / "baidu_state.json"

# 百度文心助手网址
BAIDU_URL = "https://chat.baidu.com/"

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
    # 输入框 - 百度使用 textarea
    "input_box": [
        '[class*="chat-input"] textarea',  # ✓ 已验证命中
        'textarea[class*="input"]',
        'div[contenteditable="true"]',
        '[class*="ChatInput"] textarea',
        'textarea',
    ],

    # 发送按钮 - 紫色圆形箭头按钮
    "send_button": [
        '[class*="submit"]',               # ✓ 已验证命中
        'button[class*="send"]',
        'button[class*="Send"]',
        'button[class*="submit"]',
        '[class*="send-btn"]',
        '[class*="sendBtn"]',
    ],

    # AI回复消息容器 - markdown 格式内容区
    "assistant_message": [
        '[class*="markdown"]',             # ✓ 已验证命中
        '[class*="Markdown"]',
        '[class*="assistant"]',
        '[class*="bot-message"]',
        '[class*="answer"]',
        '[data-role="assistant"]',
    ],

    # 停止按钮 - 生成时出现的蓝色方形按钮
    "stop_button": [
        'button[class*="stop"]',
        'button[class*="Stop"]',
        '[class*="stop-generating"]',
        '[class*="stopBtn"]',
    ],

    # 加载指示器 - "图片解析中" 等生成中状态
    # 注意：[class*="typing"] 在生成完成后仍命中（页面常驻元素），已移除
    "loading": [
        '[class*="loading"]',
        '[class*="generating"]',
    ],

    # 登录成功标识 - 输入框可用说明已登录
    "logged_in_indicator": [
        '[class*="chat-input"]',           # ✓ 已验证命中
        'textarea[class*="input"]',
        '[class*="ChatInput"]',
    ],

    # 未登录标识 - 右上角蓝色"登录"按钮
    "not_logged_in_indicator": [
        'a:has-text("登录")',
        'button:has-text("登录")',
        '[class*="login-btn"]',
        '[class*="LoginBtn"]',
    ],

    # 图片上传按钮 - 山景图标
    "image_upload_button": [
        'button[aria-label*="图片"]',
        '[class*="image-btn"]',
        '[class*="imageBtn"]',
        '[class*="img-upload"]',
    ],

    # 上传本地图片菜单项
    "upload_local_image": [
        'text=上传本地图片',
        ':text("上传本地图片")',
        'span:has-text("上传本地图片")',
        '[class*="menu"] >> text=上传本地图片',
    ],

    # 图片预览（上传完成标识）
    "image_preview": [
        '[class*="image-preview"]',
        '[class*="imagePreview"]',
        '[class*="preview"] img',
        'img[class*="upload"]',
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
