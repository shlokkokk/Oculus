import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

WEB_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = WEB_DIR.parent
CATALOG = json.loads((WEB_DIR / "shared" / "modules.json").read_text(encoding="utf-8"))
MODULE_IDS = {item["id"] for item in CATALOG["modules"]}
MODE_IDS = set(CATALOG["modes"].keys())
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")

app = FastAPI(title="Oculus Web API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanOptions(BaseModel):
    threads: int = Field(default=50, ge=1, le=500)
    timeout: int = Field(default=300, ge=10, le=7200)
    rate_limit: int = Field(default=150, ge=1, le=5000)
    auto_confirm: bool = True
    jitter: bool = False


class ScanRequest(BaseModel):
    domain: str
    mode: str = "custom"
    modules: list[str] = Field(default_factory=list)
    options: ScanOptions = Field(default_factory=ScanOptions)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        clean = value.strip().lower()
        if not DOMAIN_RE.match(clean) or ".." in clean:
            raise ValueError("Enter a valid domain name.")
        return clean

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in MODE_IDS:
            raise ValueError("Unknown scan mode.")
        return value

    @field_validator("modules")
    @classmethod
    def validate_modules(cls, values: list[str]) -> list[str]:
        bad = [item for item in values if item not in MODULE_IDS]
        if bad:
            raise ValueError(f"Unknown modules: {', '.join(bad)}")
        return values


@dataclass
class ScanJob:
    id: str
    request: ScanRequest
    command: list[str]
    status: str = "starting"
    output_dir: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    return_code: int | None = None
    process: asyncio.subprocess.Process | None = None
    logs: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "command": " ".join(self.command),
            "domain": self.request.domain,
            "mode": self.request.mode,
            "modules": self.request.modules,
            "output_dir": self.output_dir,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "return_code": self.return_code,
        }


jobs: dict[str, ScanJob] = {}


@app.get("/api/catalog")
def get_catalog() -> dict[str, Any]:
    return CATALOG


@app.get("/api/scans")
def list_scans() -> list[dict[str, Any]]:
    return [job.public() for job in reversed(list(jobs.values()))]


@app.post("/api/scans")
async def create_scan(request: ScanRequest) -> dict[str, Any]:
    command = build_command(request)
    job = ScanJob(
        id=uuid.uuid4().hex[:12],
        request=request,
        command=command,
        output_dir=f"output-{request.domain}",
    )
    jobs[job.id] = job
    asyncio.create_task(run_scan(job))
    return job.public()


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str) -> dict[str, Any]:
    return require_job(scan_id).public()


@app.post("/api/scans/{scan_id}/stop")
async def stop_scan(scan_id: str) -> dict[str, Any]:
    job = require_job(scan_id)
    if job.process and job.status == "running":
        job.status = "stopping"
        publish(job, {"type": "status", "scan": job.public()})
        terminate_process(job.process)
    return job.public()


@app.get("/api/scans/{scan_id}/events")
async def scan_events(scan_id: str) -> StreamingResponse:
    job = require_job(scan_id)
    queue: asyncio.Queue = asyncio.Queue()
    job.subscribers.append(queue)

    async def stream():
        try:
            yield encode_event({"type": "status", "scan": job.public()})
            for line in job.logs[-200:]:
                yield encode_event({"type": "log", "line": line})
            while True:
                event = await queue.get()
                yield encode_event(event)
                if event.get("type") == "status" and event.get("scan", {}).get("status") in {"completed", "failed", "stopped"}:
                    yield encode_event({"type": "report", "report": report_summary(job)})
        finally:
            if queue in job.subscribers:
                job.subscribers.remove(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/scans/{scan_id}/report")
def get_report(scan_id: str) -> dict[str, Any]:
    return report_summary(require_job(scan_id))


def require_job(scan_id: str) -> ScanJob:
    if scan_id not in jobs:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return jobs[scan_id]


def build_command(request: ScanRequest) -> list[str]:
    command = [sys.executable, "oculus.py", "-d", request.domain]
    if request.mode != "custom":
        flag = CATALOG["modes"][request.mode].get("flag")
        if flag:
            command.append(flag)
    else:
        selected = request.modules or CATALOG["modes"]["custom"]["modules"]
        command.extend(["--module", ",".join(selected)])
    if request.options.auto_confirm:
        command.append("--no-confirm")
    command.extend(["--threads", str(request.options.threads), "--timeout", str(request.options.timeout)])
    if request.options.jitter:
        command.append("--jitter")
    return command


async def run_scan(job: ScanJob) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    job.status = "running"
    publish(job, {"type": "status", "scan": job.public()})
    publish(job, {"type": "log", "line": f"$ {' '.join(job.command)}"})
    try:
        job.process = await asyncio.create_subprocess_exec(
            *job.command,
            cwd=REPO_ROOT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            creationflags=subprocess_creation_flags(),
            start_new_session=os.name != "nt",
        )
        assert job.process.stdout is not None
        async for raw in job.process.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                publish(job, {"type": "log", "line": line})
        job.return_code = await job.process.wait()
        if job.status == "stopping":
            job.status = "stopped"
        else:
            job.status = "completed" if job.return_code == 0 else "failed"
    except Exception as exc:
        job.status = "failed"
        publish(job, {"type": "log", "line": f"[web] backend error: {exc}"})
    finally:
        job.finished_at = datetime.now(timezone.utc).isoformat()
        publish(job, {"type": "status", "scan": job.public()})


def publish(job: ScanJob, event: dict[str, Any]) -> None:
    if event.get("type") == "log":
        job.logs.append(event["line"])
    for queue in list(job.subscribers):
        queue.put_nowait(event)


def encode_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def report_summary(job: ScanJob) -> dict[str, Any]:
    output_dir = REPO_ROOT / job.output_dir
    findings_path = output_dir / "findings.json"
    html_path = output_dir / "report.html"
    finding_count = 0
    if findings_path.exists():
        try:
            data = json.loads(findings_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, list):
                finding_count = len(data)
            elif isinstance(data, dict):
                findings = data.get("findings") or data.get("vulnerabilities") or []
                finding_count = len(findings) if isinstance(findings, list) else 0
        except json.JSONDecodeError:
            finding_count = 0
    return {
        "finding_count": finding_count,
        "output_dir": str(output_dir),
        "findings_json": f"/artifacts/{job.output_dir}/findings.json" if findings_path.exists() else None,
        "report_html": f"/artifacts/{job.output_dir}/report.html" if html_path.exists() else None,
    }


def terminate_process(process: asyncio.subprocess.Process) -> None:
    if os.name == "nt":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)


def subprocess_creation_flags() -> int:
    if os.name == "nt":
        return subprocess.CREATE_NEW_PROCESS_GROUP
    return 0


app.mount("/artifacts", StaticFiles(directory=REPO_ROOT), name="artifacts")
