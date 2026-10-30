"""Local-only presentation API for the published multimodal workflow."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .dify_client import DifyClient, DifyError


STATIC_ROOT = Path(__file__).parent / "static"
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
DEMO_USER = "portfolio-demo"
FILE_EXTENSIONS = {
    "video": {".mp4", ".mov"},
    "image": {".jpg", ".jpeg", ".png", ".webp"},
}


def _matches_signature(asset_type: str, extension: str, content: bytes) -> bool:
    if asset_type == "video":
        return len(content) >= 12 and content[4:8] == b"ftyp"
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


def create_demo_app(client: DifyClient | None = None) -> FastAPI:
    app = FastAPI(title="AI-Ad-QA Portfolio Demo", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_ROOT, check_dir=False), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_ROOT / "index.html")

    @app.post("/api/evaluate")
    async def evaluate(
        asset_type: str = Form(...),
        video: UploadFile | None = File(None),
        image: UploadFile | None = File(None),
        script: str = Form(""),
        product_context: str = Form(""),
        target_audience: str = Form(""),
        conversion_goal: str = Form(""),
        additional_requirements: str = Form(""),
    ):
        if asset_type not in {"video", "image", "script"}:
            raise HTTPException(status_code=400, detail="请选择视频、图片或脚本类型")
        if asset_type == "script" and not script.strip():
            raise HTTPException(status_code=400, detail="请输入广告脚本")
        if asset_type == "video" and video is None:
            raise HTTPException(status_code=400, detail="请上传广告视频")
        if asset_type == "image" and image is None:
            raise HTTPException(status_code=400, detail="请上传广告图片")
        if asset_type == "script" and (video or image):
            raise HTTPException(status_code=400, detail="脚本模式不接收文件")
        if asset_type == "video" and image or asset_type == "image" and video:
            raise HTTPException(status_code=400, detail="一次只能提交所选类型的一份素材")

        upload = video if asset_type == "video" else image if asset_type == "image" else None
        content = None
        if upload is not None:
            extension = Path(upload.filename or "").suffix.lower()
            if extension not in FILE_EXTENSIONS[asset_type]:
                raise HTTPException(status_code=415, detail="文件格式不符合所选素材类型")
            limit = MAX_VIDEO_BYTES if asset_type == "video" else MAX_IMAGE_BYTES
            content = await upload.read(limit + 1)
            if len(content) > limit:
                raise HTTPException(status_code=413, detail="文件超过演示页大小限制")
            if not _matches_signature(asset_type, extension, content):
                raise HTTPException(status_code=415, detail="文件内容与扩展名不符")

        try:
            active_client = client or DifyClient(os.getenv("DIFY_DEMO_API_KEY", ""))
            inputs = {
                "asset_type": asset_type,
                "product_context": product_context.strip(),
                "target_audience": target_audience.strip(),
                "conversion_goal": conversion_goal.strip(),
                "additional_requirements": additional_requirements.strip(),
                "script": script.strip() if asset_type == "script" else "",
            }
            if upload is not None and content is not None:
                file_id = await run_in_threadpool(
                    active_client.upload_file, content, upload.filename or "upload", DEMO_USER
                )
                inputs[asset_type] = {
                    "type": asset_type,
                    "transfer_method": "local_file",
                    "upload_file_id": file_id,
                }
            output = await run_in_threadpool(active_client.run_workflow, inputs, DEMO_USER)
        except DifyError as exc:
            status = 503 if not os.getenv("DIFY_DEMO_API_KEY") and client is None else 502
            raise HTTPException(status_code=status, detail=str(exc)) from None
        return {
            "report_markdown": output["report_markdown"],
            "final_status": output["final_status"],
        }

    return app


app = create_demo_app()
