# CLAUDE.md

> **⚠️ 重要：本服务器只做开发，没有 GPU，禁止运行测试、启动服务或部署。只能编辑代码。**

> **⚠️ 重要：用中文和我对话**

> **⚠️ 重要：修改完代码之后，自动commit相关修改的代码，然后 push**

> **⚠️ 重要：git commit 时不要添加 Co-Authored-By 行**
 
 

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qwen Web Client - 通过 Playwright 自动化访问通义千问网页版 (https://www.qianwen.com/chat)，获取完整 Agent 能力（联网搜索、代码执行、图片生成等），而非仅使用受限的 API。

## Commands

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 首次登录（有头模式，手动完成登录）
DEBUG=1 python main.py --login

# 单次提问
python main.py "你的问题"

# 交互模式
python main.py -i

# 调试模式（有头浏览器 + 慢速操作）
DEBUG=1 SLOW_MO=500 python main.py "测试"
```

## Architecture

```
main.py (CLI入口)
    │
    ├── login_only()      → 登录流程
    ├── single_query()    → 单次提问
    └── interactive_mode() → 交互模式
           │
           ▼
┌─────────────────────────────────────┐
│  QwenBrowser (browser.py)           │
│  - 浏览器生命周期管理               │
│  - Cookie 持久化 (cookies/)         │
│  - 反自动化检测                     │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  QwenChat (chat.py)                 │
│  - 消息发送                         │
│  - 响应等待（轮询检测生成状态）     │
└─────────────────────────────────────┘
```

## Key Configuration

所有配置集中在 `qwen_client/config.py`：

- **SELECTORS**: 页面元素选择器（多备选），页面结构变化时需更新
- **TIMEOUT**: 各类操作超时配置
- **BROWSER_CONFIG**: 浏览器启动参数和反检测设置

环境变量：
- `DEBUG=1`: 有头模式，可见浏览器窗口
- `SLOW_MO=N`: 操作间隔毫秒数

## Selector Debugging

当页面元素找不到时：
1. 用 `DEBUG=1` 启动查看浏览器
2. F12 打开 DevTools 检查实际元素
3. 更新 `config.py` 中的 `SELECTORS`
