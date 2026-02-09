"""FastAPI 应用"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from qwen_client.manager import BrowserManager
from .routes import router, set_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化浏览器
    mgr = BrowserManager()
    await mgr.startup()
    set_manager(mgr)
    yield
    # 关闭：释放浏览器
    await mgr.shutdown()


app = FastAPI(title="Qwen Web Client API", lifespan=lifespan)
app.include_router(router)
