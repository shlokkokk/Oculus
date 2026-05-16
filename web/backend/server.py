"""
Oculus Web API — FastAPI server with REST endpoints and WebSocket streaming.
"""

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import engine, VERSION
from .models import (
    ScanRequest,
    ScanStatusResponse,
    HealthResponse,
    ScanState,
    ConfigResponse,
)

app = FastAPI(
    title="Oculus Web API",
    version=VERSION,
    description="Web interface for the Oculus Recon Framework",
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static build if it exists
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static-assets")


# ─── Health ───────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version=VERSION,
        scan_state=ScanState(engine.state),
    )


# ─── Tools ────────────────────────────────────────────────────────────

@app.get("/api/tools")
async def get_tools():
    tools = engine.check_tools()
    return {"tools": list(tools.values())}


# ─── Config ───────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    config = engine.get_config()
    return ConfigResponse(
        threads=config.get("threads", 50),
        timeout=config.get("timeout", 300),
        rate_limit=config.get("rate_limit", 150),
        retry_count=config.get("retry_count", 2),
        retry_delay=config.get("retry_delay", 5),
        parallel=config.get("parallel", True),
        jitter=config.get("jitter", False),
        nuclei_severity=config.get("nuclei", {}).get("severity", "low,medium,high,critical"),
        nuclei_concurrency=config.get("nuclei", {}).get("concurrency", 25),
        naabu_ports=config.get("naabu", {}).get("ports", "1-65535"),
        naabu_rate=config.get("naabu", {}).get("rate", 2000),
        ffuf_extensions=config.get("ffuf", {}).get("extensions", "php,html,js,json,txt,bak,old"),
        ffuf_recursion_depth=config.get("ffuf", {}).get("recursion_depth", 2),
    )


# ─── Scan Control ────────────────────────────────────────────────────

@app.post("/api/scan/start")
async def start_scan(req: ScanRequest):
    ok = engine.start_scan(
        domain=req.domain,
        mode=req.mode.value,
        modules=req.modules,
        threads=req.threads,
        rate_limit=req.rate_limit,
        timeout=req.timeout,
        jitter=req.jitter,
        severity=req.severity,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="A scan is already running")
    return {"status": "started", "domain": req.domain, "mode": req.mode.value}


@app.post("/api/scan/stop")
async def stop_scan():
    ok = engine.stop_scan()
    if not ok:
        raise HTTPException(status_code=409, detail="No scan is currently running")
    return {"status": "aborted"}


@app.get("/api/scan/status")
async def scan_status():
    return engine.get_status()


@app.get("/api/scan/logs")
async def scan_logs(since: int = Query(0, ge=0)):
    lines = engine.get_logs(since=since)
    return {"lines": lines, "total": since + len(lines)}


# ─── Sessions ─────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": engine.list_sessions()}


@app.get("/api/sessions/{domain}")
async def get_session(domain: str):
    session = engine.get_session(domain)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ─── Results / Artifacts ──────────────────────────────────────────────

@app.get("/api/results/{domain}")
async def list_results(domain: str):
    artifacts = engine.list_artifacts(domain)
    if not artifacts:
        raise HTTPException(status_code=404, detail="No results found for this domain")
    return {"domain": domain, "artifacts": artifacts}


@app.get("/api/results/{domain}/file/{file_path:path}")
async def get_artifact_file(domain: str, file_path: str):
    resolved = engine.get_artifact_path(domain, file_path)
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found")

    mime, _ = mimetypes.guess_type(str(resolved))
    suffix = resolved.suffix.lower()

    # Text-like files: return content as JSON for easy frontend rendering
    text_extensions = {
        ".txt", ".json", ".jsonl", ".md", ".log", ".csv", ".xml",
        ".yaml", ".yml", ".html", ".htm", ".cfg", ".conf", ".ini",
    }
    if suffix in text_extensions:
        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
            return JSONResponse({
                "name": resolved.name,
                "path": file_path,
                "content": content,
                "size": len(content),
                "type": "text",
            })
        except Exception:
            pass

    # Binary files: serve directly
    return FileResponse(
        path=str(resolved),
        media_type=mime or "application/octet-stream",
        filename=resolved.name,
    )


# ─── Reports ──────────────────────────────────────────────────────────

@app.get("/api/reports/{domain}/{fmt}")
async def get_report(domain: str, fmt: str):
    file_map = {
        "html": "report.html",
        "json": "findings.json",
        "md": "report.md",
        "summary": "summary.txt",
    }
    filename = file_map.get(fmt)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}. Use: {', '.join(file_map.keys())}")

    resolved = engine.get_artifact_path(domain, filename)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    content = resolved.read_text(encoding="utf-8", errors="replace")
    return {"format": fmt, "filename": filename, "content": content}


# ─── WebSocket — Live Log Streaming ──────────────────────────────────

@app.websocket("/ws/scan")
async def websocket_scan(websocket: WebSocket):
    await websocket.accept()
    cursor = 0
    try:
        while True:
            # Send new log lines
            lines = engine.get_logs(since=cursor)
            if lines:
                cursor += len(lines)
                await websocket.send_json({
                    "type": "logs",
                    "lines": lines,
                    "total": cursor,
                })

            # Send status update
            status = engine.get_status()
            await websocket.send_json({
                "type": "status",
                "data": status,
            })

            # Check for client messages (abort, etc.)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                data = json.loads(msg)
                if data.get("action") == "abort":
                    engine.stop_scan()
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ─── Frontend SPA Fallback ────────────────────────────────────────────

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve the frontend SPA. Falls back to index.html for client-side routing."""
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        raise HTTPException(status_code=404)

    if _frontend_dist.is_dir():
        # Try exact file first
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Fallback to index.html for SPA routing
        index = _frontend_dist / "index.html"
        if index.is_file():
            return FileResponse(str(index))

    return HTMLResponse(
        content="<h1>Oculus Web</h1><p>Frontend not built. Run <code>npm run build</code> in web/frontend/</p>",
        status_code=200,
    )
