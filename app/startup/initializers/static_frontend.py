"""
前端静态资源（SPA）服务：frontend-dist 存在时挂载，无需 nginx。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST_ROOT = Path(__file__).resolve().parents[3] / "frontend-dist"


def init_frontend_static(app: FastAPI) -> None:
    """
    挂载前端 SPA。必须在所有 API 路由注册之后调用；
    /api 前缀之外且未命中静态文件时回退到 index.html。
    """
    dist = _DIST_ROOT
    if not (dist / "index.html").is_file():
        return
    if (dist / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=dist / "assets"),
            name="frontend_assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):  # noqa: ANN202
        # /api 等接口前缀不进入 SPA 回退，未知接口保持 404 语义
        if full_path == "api" or full_path.startswith(("api/", "api/v1/", "api/v3/")):
            raise HTTPException(status_code=404)
        candidate = (dist / full_path).resolve()
        if (
            full_path
            and str(candidate).startswith(str(dist.resolve()))
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
