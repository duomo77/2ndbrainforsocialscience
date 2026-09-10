from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from api.runtime import WebAnalysisRequest, run_web_analysis
from core import ros_engine

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {
    ".pdf", ".txt", ".md", ".rst", ".tex",
    ".csv", ".tsv", ".xlsx", ".xls",
    ".srt", ".vtt", ".py", ".r", ".do", ".jl",
}
ALLOWED_INPUT_TYPES = {"paper", "transcript", "dataset", "equation", "notes", "code"}


class AnalyzeRequest(BaseModel):
    input_type: str = Field(default="notes")
    raw_text: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)
    api_key: str = Field(default="")
    base_url: str = Field(default="")
    model: str = Field(default="demo-local")
    vault_path: str = Field(default="")
    auto_save: bool = Field(default=False)
    topic_override: str = Field(default="")

    @field_validator("input_type")
    @classmethod
    def validate_input_type(cls, value: str) -> str:
        if value not in ALLOWED_INPUT_TYPES:
            raise ValueError("unsupported input_type")
        return value


class ValidateRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"


def _analysis_payload(result, events: list) -> dict[str, Any]:
    outcome = result.value
    return {
        "markdown": outcome.markdown,
        "title": outcome.title,
        "topic": outcome.topic,
        "cached": outcome.cached,
        "saved_path": outcome.saved_path,
        "events": [event.__dict__ for event in events],
    }


async def _store_upload(file: UploadFile) -> tuple[str, str]:
    original_name = Path(file.filename or "uploaded").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        await file.close()
        raise HTTPException(status_code=415, detail={"error": "Unsupported file type"})

    temp_path = ""
    total = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = temp.name
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail={"error": f"Upload exceeds {MAX_UPLOAD_BYTES} bytes"},
                    )
                temp.write(chunk)
        return temp_path, original_name
    except Exception:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def _frontend_file(path: str) -> Path | None:
    root = FRONTEND_DIST.resolve()
    target = (root / path).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target if target.is_file() else None


def create_app() -> FastAPI:
    app = FastAPI(title="ROS Web API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "runtime": "fastapi",
            "frontend_dist": FRONTEND_DIST.exists(),
            "demo_model": "demo-local",
        }

    @app.post("/api/analyze")
    def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
        result, events = run_web_analysis(WebAnalysisRequest(**payload.model_dump()))
        if not result.ok:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": result.error,
                    "events": [event.__dict__ for event in events],
                },
            )
        return _analysis_payload(result, events)

    @app.post("/api/analyze-file")
    async def analyze_file(
        file: UploadFile = File(...),
        input_type: str = Form("paper"),
        title: str = Form(""),
        api_key: str = Form(""),
        base_url: str = Form(""),
        model: str = Form("demo-local"),
        vault_path: str = Form(""),
        auto_save: bool = Form(False),
        topic_override: str = Form(""),
    ) -> dict[str, Any]:
        if input_type not in ALLOWED_INPUT_TYPES:
            raise HTTPException(status_code=422, detail={"error": "Unsupported input_type"})
        temp_path, original_name = await _store_upload(file)
        try:
            result, events = run_web_analysis(
                WebAnalysisRequest(
                    input_type=input_type,
                    file_path=temp_path,
                    metadata={
                        "title": title or original_name or "Uploaded Document",
                        "source_ref": original_name,
                    },
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    vault_path=vault_path,
                    auto_save=auto_save,
                    topic_override=topic_override,
                )
            )
            if not result.ok:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": result.error,
                        "events": [event.__dict__ for event in events],
                    },
                )
            return _analysis_payload(result, events)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @app.post("/api/validate-provider")
    def validate_provider(payload: ValidateRequest) -> dict[str, Any]:
        ok, message = ros_engine.validate_api(payload.api_key, payload.base_url, payload.model)
        return {"ok": ok, "message": message}

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            target = _frontend_file(path) if path else None
            if target:
                return FileResponse(target)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
