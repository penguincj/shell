"""Baidu AI Client - 百度文心助手网页版自动化工具"""
from .browser import BaiduBrowser
from .chat import BaiduChat
from .config import DEBUG, BAIDU_URL

__all__ = ['BaiduBrowser', 'BaiduChat', 'DEBUG', 'BAIDU_URL']
__version__ = '0.1.0'
