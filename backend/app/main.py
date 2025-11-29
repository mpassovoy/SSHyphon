from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config_store
from . import auth
from .versioning import get_version_payload, read_version
from .activity_log import (
    ACTIVITY_LOG_FILE,
    clear_entries as clear_activity_entries,
    read_entries as read_activity_entries,
)
from .auto_sync import controller as auto_sync_controller
from . import jellyfin_service
from .models import AuthRequest, AuthStatus, JellyfinConfig, JellyfinTask, JellyfinTestRequest, SftpConfig
from .sync_service import (
    MissingCredentialsError,
    SyncInProgressError,
    sync_service,
)

app = FastAPI(title="SSHyphon API", version=read_version())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    auto_sync_controller.update_config(config_store.export_unmasked_config())
    auto_sync_controller.ensure_start_on_restart()


@app.on_event("shutdown")
async def on_shutdown():
    auto_sync_controller.shutdown()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/version")
def read_version_info():
    return get_version_payload()


@app.get("/api/auth/status", response_model=AuthStatus)
def read_auth_status(token: str | None = Depends(auth.optional_token)):
    return auth.get_status(token)


@app.post("/api/auth/setup", response_model=auth.AuthResponse)
def setup_auth(payload: AuthRequest):
    return auth.setup_credentials(payload.username, payload.password, payload.remember_me)


@app.post("/api/auth/login", response_model=auth.AuthResponse)
def login(payload: AuthRequest):
    return auth.login(payload.username, payload.password, payload.remember_me)


@app.post("/api/auth/logout")
def logout(session: auth.SessionInfo = Depends(auth.require_auth)):
    auth.logout(session.token)
    return {"status": "ok"}


@app.get("/api/config")
def read_config(reveal: bool = False, session: auth.SessionInfo = Depends(auth.require_auth)):
    return config_store.get_config(mask_secrets=not reveal)


@app.put("/api/config")
def update_config(payload: SftpConfig, session: auth.SessionInfo = Depends(auth.require_auth)):
    response = config_store.save_config(payload)
    auto_sync_controller.update_config(config_store.export_unmasked_config())
    return response


@app.get("/api/status")
def read_status(session: auth.SessionInfo = Depends(auth.require_auth)):
    return sync_service.status()


@app.post("/api/sync/start")
def start_sync(session: auth.SessionInfo = Depends(auth.require_auth)):
    try:
        config = config_store.export_unmasked_config()
        status = sync_service.start(config)
        auto_sync_controller.schedule_next_run(config)
        return status
    except MissingCredentialsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SyncInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sync/stop")
def stop_sync(session: auth.SessionInfo = Depends(auth.require_auth)):
    auto_sync_controller.cancel_schedule()
    return sync_service.stop()


@app.get("/api/errors")
def list_errors(limit: int = 200, session: auth.SessionInfo = Depends(auth.require_auth)):
    return {"errors": config_store.tail_errors(limit)}


@app.get("/api/activity/log")
def list_activity_entries(limit: int = 1000, session: auth.SessionInfo = Depends(auth.require_auth)):
    return {"entries": read_activity_entries(limit)}


@app.post("/api/activity/clear")
def clear_activity_log(session: auth.SessionInfo = Depends(auth.require_auth)):
    clear_activity_entries()
    return {"status": "ok"}


@app.get("/api/activity/download")
def download_activity_log(session: auth.SessionInfo = Depends(auth.require_auth)):
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"activity-{timestamp}.log"
    ACTIVITY_LOG_FILE.touch(exist_ok=True)
    return FileResponse(ACTIVITY_LOG_FILE, media_type="text/plain", filename=filename)


@app.post("/api/errors/clear")
def clear_error_log(session: auth.SessionInfo = Depends(auth.require_auth)):
    config_store.ERROR_LOG_FILE.write_text("", encoding="utf-8")
    return {"status": "ok"}


@app.get("/api/errors/download")
def download_error_log(session: auth.SessionInfo = Depends(auth.require_auth)):
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"errors-{timestamp}.log"
    config_store.ERROR_LOG_FILE.touch(exist_ok=True)
    return FileResponse(config_store.ERROR_LOG_FILE, media_type="text/plain", filename=filename)


@app.get("/api/jellyfin/config")
def read_jellyfin_config(
    reveal: bool = False, session: auth.SessionInfo = Depends(auth.require_auth)
):
    return config_store.get_jellyfin_config(mask_secrets=not reveal)


@app.put("/api/jellyfin/config")
def update_jellyfin_config(payload: JellyfinConfig, session: auth.SessionInfo = Depends(auth.require_auth)):
    return config_store.save_jellyfin_config(payload)


@app.post("/api/jellyfin/test")
def test_jellyfin(
    payload: JellyfinTestRequest | None = None, session: auth.SessionInfo = Depends(auth.require_auth)
):
    try:
        jellyfin_service.test_connection(payload)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jellyfin/tasks", response_model=list[JellyfinTask])
def list_jellyfin_tasks(session: auth.SessionInfo = Depends(auth.require_auth)):
    try:
        return jellyfin_service.list_tasks()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jellyfin/tasks/run")
def run_jellyfin_tasks(session: auth.SessionInfo = Depends(auth.require_auth)):
    try:
        return sync_service.start_jellyfin_tasks()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_dist_env = os.getenv("SYNC_MONITOR_FRONTEND_DIST")
if _dist_env:
    FRONTEND_DIST = Path(_dist_env).resolve()
else:
    candidates = [
        Path(__file__).resolve().parent / "static",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    ]
    FRONTEND_DIST = next((c for c in candidates if c.exists()), Path())

ICON_DIR = Path(__file__).resolve().parents[1].parent / "resources" / "icons"
if ICON_DIR.exists():
    app.mount("/icons", StaticFiles(directory=ICON_DIR), name="icons")

if FRONTEND_DIST and FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    def _spa_response():
        index = FRONTEND_DIST / "index.html"
        if not index.exists():
            raise HTTPException(status_code=404, detail="Frontend build missing")
        return FileResponse(index)

    @app.get("/", include_in_schema=False)
    def read_root():
        return _spa_response()

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        return _spa_response()
