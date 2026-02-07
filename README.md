# Qwen Web Client

通义千问网页版自动化工具，通过 Playwright 模拟浏览器访问 https://www.qianwen.com/chat

## 为什么使用网页版？

网页版千问是一个完整的 Agent，具备 API 不具备的能力：
- 联网搜索
- 代码执行
- 图片生成
- 文件分析
- 等等...

## 环境要求

- Python 3.10+
- Mac / Linux / Windows

## 安装

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

### 1. 首次登录

首次使用需要登录，会打开浏览器窗口让你手动完成登录：

```bash
DEBUG=1 python main.py --login
```

登录成功后，Cookie 会保存到 `cookies/qwen_cookies.json`，后续使用无需重复登录。

### 2. 单次提问

```bash
# 无头模式（后台运行）
python main.py "你好，介绍一下你自己"

# 调试模式（可见浏览器）
DEBUG=1 python main.py "帮我搜索今天的科技新闻"

# 慢速调试（每步操作间隔500ms）
DEBUG=1 SLOW_MO=500 python main.py "写一段Python代码"
```

### 3. 交互模式

```bash
python main.py -i
# 或
python main.py --interactive
```

交互模式命令：
- `quit` / `exit` / `q` - 退出
- `new` - 开启新对话

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEBUG` | 设为 `1` 启用有头模式（可见浏览器） | `0` |
| `SLOW_MO` | 操作间隔毫秒数，方便调试观察 | `0` |

## 项目结构

```
shell/
├── qwen_client/
│   ├── __init__.py      # 包入口
│   ├── config.py        # 配置管理
│   ├── browser.py       # 浏览器核心
│   ├── chat.py          # 聊天逻辑
│   └── utils.py         # 工具函数
├── cookies/             # Cookie 存储目录
├── main.py              # CLI 入口
├── requirements.txt
└── README.md
```

## 常见问题

### Q: 提示找不到输入框？

页面结构可能已更新，需要修改 `qwen_client/config.py` 中的 `SELECTORS` 配置。

使用浏览器开发者工具 (F12) 检查页面元素，更新对应的选择器。

### Q: Cookie 过期了？

重新运行登录流程：

```bash
DEBUG=1 python main.py --login
```

### Q: 响应获取不完整？

可能是响应判断逻辑问题，尝试调整 `config.py` 中的超时配置，或检查 `SELECTORS["loading"]` 和 `SELECTORS["stop_button"]` 选择器是否正确。

## License

MIT
