#!/usr/bin/env python3
"""Qwen Web Client API 服务启动入口

Usage:
    python server.py
    API_PORT=9000 python server.py
    DEBUG=1 python server.py
"""
import uvicorn

from qwen_client.config import API_CONFIG

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        log_level="info",
    )
