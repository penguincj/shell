"""API 路由"""
from fastapi import APIRouter, HTTPException

from qwen_client.manager import BrowserManager
from .models import ChatRequest, ChatResponse, HealthResponse, RestartResponse

router = APIRouter(prefix="/v1")

# 全局 BrowserManager 实例，由 app.py lifespan 注入
manager: BrowserManager | None = None


def set_manager(m: BrowserManager) -> None:
    global manager
    manager = m


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not manager or not manager.is_ready:
        raise HTTPException(status_code=503, detail="浏览器未就绪")
    try:
        response = await manager.chat(req.prompt, req.image_path)
        return ChatResponse(response=response, request_count=manager.request_count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok" if manager and manager.is_ready else "unavailable",
        browser_ready=manager.is_ready if manager else False,
        request_count=manager.request_count if manager else 0,
    )


@router.post("/restart", response_model=RestartResponse)
async def restart():
    if not manager:
        raise HTTPException(status_code=503, detail="BrowserManager 未初始化")
    try:
        await manager.restart()
        return RestartResponse(status="ok", message="浏览器已重启")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
