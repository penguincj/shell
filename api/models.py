"""请求/响应数据模型"""
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str
    image_path: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    request_count: int


class HealthResponse(BaseModel):
    status: str
    browser_ready: bool
    request_count: int


class RestartResponse(BaseModel):
    status: str
    message: str
