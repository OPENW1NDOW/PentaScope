from fastapi import FastAPI
from src.api.routes import router
from src.utils.logger import init_logging

init_logging()

app = FastAPI(title="竞品分析 Agent 系统", version="1.0.0")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
