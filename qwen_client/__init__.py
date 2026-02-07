"""Qwen Web Client - 通义千问网页版自动化工具"""
from .browser import QwenBrowser
from .chat import QwenChat
from .config import DEBUG, QWEN_URL

__all__ = ['QwenBrowser', 'QwenChat', 'DEBUG', 'QWEN_URL']
__version__ = '0.1.0'
