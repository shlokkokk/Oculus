"""
Pydantic models for the Oculus Web API.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ScanMode(str, Enum):
    QUICK = "quick"
    DEEP = "deep"
    FULL_SPECTRUM = "full_spectrum"
    CUSTOM = "custom"


class ScanState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ScanRequest(BaseModel):
    domain: str = Field(..., pattern=r"^[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    mode: ScanMode = ScanMode.QUICK
    modules: list[str] = Field(default_factory=list)
    threads: Optional[int] = Field(None, ge=1, le=500)
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    timeout: Optional[int] = Field(None, ge=10, le=7200)
    jitter: bool = False
    severity: Optional[str] = None


class ScanStatusResponse(BaseModel):
    state: ScanState
    domain: Optional[str] = None
    mode: Optional[str] = None
    current_module: Optional[str] = None
    elapsed_seconds: int = 0
    modules_completed: list[str] = Field(default_factory=list)
    modules_failed: list[str] = Field(default_factory=list)
    total_modules: int = 0
    log_line_count: int = 0


class ToolInfo(BaseModel):
    name: str
    installed: bool
    path: Optional[str] = None
    install_command: Optional[str] = None


class SessionInfo(BaseModel):
    domain: str
    timestamp: Optional[str] = None
    version: Optional[str] = None
    results: dict = Field(default_factory=dict)
    completed_modules: list[str] = Field(default_factory=list)
    output_dir: str = ""


class ConfigResponse(BaseModel):
    threads: int = 50
    timeout: int = 300
    rate_limit: int = 150
    retry_count: int = 2
    retry_delay: int = 5
    parallel: bool = True
    jitter: bool = False
    nuclei_severity: str = "low,medium,high,critical"
    nuclei_concurrency: int = 25
    naabu_ports: str = "1-65535"
    naabu_rate: int = 2000
    ffuf_extensions: str = "php,html,js,json,txt,bak,old"
    ffuf_recursion_depth: int = 2


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: Optional[list["FileEntry"]] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    scan_state: ScanState
