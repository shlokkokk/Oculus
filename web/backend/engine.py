"""
Oculus Scan Engine — wraps the CLI Oculus class for web use.
Captures stdout, manages scan lifecycle in background threads.
"""

import sys
import os
import io
import time
import threading
import queue
import re
from pathlib import Path
from typing import Optional

# Add project root to path so we can import oculus.py
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from oculus import Oculus, load_config, MODULE_MAP, VERSION


# ANSI escape code stripper
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class OutputCapture:
    """Thread-safe stdout capture that feeds lines to a queue."""

    def __init__(self, log_queue: queue.Queue, original_stdout):
        self._queue = log_queue
        self._original = original_stdout
        self._lock = threading.Lock()

    def write(self, text: str):
        if text and text.strip():
            clean = strip_ansi(text.rstrip())
            if clean:
                with self._lock:
                    self._queue.put(clean)
        # Also write to original stdout so server logs still work
        if self._original:
            try:
                self._original.write(text)
                self._original.flush()
            except Exception:
                pass

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass


class ScanEngine:
    """Manages Oculus scan lifecycle for the web interface."""

    def __init__(self):
        self._state = "idle"  # idle, running, completed, failed, aborted
        self._domain: Optional[str] = None
        self._mode: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._log_queue: queue.Queue = queue.Queue(maxsize=50000)
        self._log_lines: list[str] = []
        self._log_lock = threading.Lock()
        self._start_time: float = 0
        self._modules_completed: list[str] = []
        self._modules_failed: list[str] = []
        self._current_module: Optional[str] = None
        self._total_modules: int = 0
        self._abort_flag = threading.Event()
        self._oculus: Optional[Oculus] = None
        self._tools_status: dict = {}
        self._tools_checked = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def domain(self) -> Optional[str]:
        return self._domain

    @property
    def elapsed(self) -> int:
        if self._start_time and self._state == "running":
            return int(time.time() - self._start_time)
        return 0

    def get_status(self) -> dict:
        self._drain_queue()
        completed = list(self._modules_completed)
        failed = list(self._modules_failed)
        
        current_phase = None
        # Merge tracking from full spectrum scan
        if self._oculus and hasattr(self._oculus, "completed_modules"):
            # Use dict.fromkeys to keep order and deduplicate
            completed = list(dict.fromkeys(completed + self._oculus.completed_modules))
        if self._oculus and hasattr(self._oculus, "failed_modules"):
            failed_names = [f[0] for f in self._oculus.failed_modules]
            failed = list(dict.fromkeys(failed + failed_names))
        if self._oculus and hasattr(self._oculus, "current_phase"):
            current_phase = self._oculus.current_phase
            
        return {
            "state": self._state,
            "domain": self._domain,
            "mode": self._mode,
            "current_module": self._current_module,
            "current_phase": current_phase,
            "elapsed_seconds": self.elapsed,
            "modules_completed": completed,
            "modules_failed": failed,
            "total_modules": self._total_modules,
            "log_line_count": len(self._log_lines),
        }

    def get_logs(self, since: int = 0) -> list[str]:
        """Return log lines since the given index."""
        self._drain_queue()
        with self._log_lock:
            return self._log_lines[since:]

    def _drain_queue(self):
        """Move lines from queue to permanent log list."""
        with self._log_lock:
            while not self._log_queue.empty():
                try:
                    line = self._log_queue.get_nowait()
                    self._log_lines.append(line)
                except queue.Empty:
                    break

    def check_tools(self, force: bool = False) -> dict:
        """Run tool initialization and cache the results."""
        if not force and self._tools_checked and self._tools_status:
            return self._tools_status

        config = load_config()
        config["auto_confirm"] = True
        oc = Oculus(config=config)
        oc._setup_logging_basic()

        # Capture stdout during tool check
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            oc.initialize_tools()
        finally:
            sys.stdout = old_stdout

        self._tools_status = {}
        for name, info in oc.tools_status.items():
            if isinstance(info, dict):
                self._tools_status[name] = {
                    "name": name,
                    "installed": info.get("installed", False),
                    "path": info.get("path", ""),
                    "install_command": info.get("install_command", ""),
                }
            else:
                self._tools_status[name] = {
                    "name": name,
                    "installed": bool(info),
                    "path": "",
                    "install_command": "",
                }
        self._tools_checked = True
        return self._tools_status

    def get_config(self) -> dict:
        """Load and return current config with API keys redacted."""
        config = load_config()
        # Redact API keys
        api_keys = config.get("api_keys", {})
        for key in api_keys:
            val = api_keys[key]
            if val and len(str(val)) > 4:
                api_keys[key] = str(val)[:4] + "****"
        return config

    def list_sessions(self) -> list[dict]:
        """Find all output-* directories and read their session.json."""
        import json
        sessions = []
        cwd = Path(_project_root)
        for d in sorted(cwd.glob("output-*")):
            if d.is_dir():
                session_file = d / "session.json"
                domain = d.name.replace("output-", "", 1)
                info = {
                    "domain": domain,
                    "output_dir": str(d),
                    "timestamp": None,
                    "version": None,
                    "results": {},
                    "completed_modules": [],
                }
                if session_file.exists():
                    try:
                        with open(session_file, encoding="utf-8") as f:
                            data = json.load(f)
                        info.update({
                            "timestamp": data.get("timestamp"),
                            "version": data.get("version"),
                            "results": data.get("results", {}),
                            "completed_modules": data.get("completed_modules", []),
                        })
                    except Exception:
                        pass
                sessions.append(info)
        return sessions

    def get_session(self, domain: str) -> Optional[dict]:
        """Get session details for a specific domain."""
        import json
        output_dir = Path(_project_root) / f"output-{domain}"
        if not output_dir.is_dir():
            return None
        session_file = output_dir / "session.json"
        info = {
            "domain": domain,
            "output_dir": str(output_dir),
            "timestamp": None,
            "version": None,
            "results": {},
            "completed_modules": [],
        }
        if session_file.exists():
            try:
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)
                info.update({
                    "timestamp": data.get("timestamp"),
                    "version": data.get("version"),
                    "results": data.get("results", {}),
                    "completed_modules": data.get("completed_modules", []),
                })
            except Exception:
                pass
        return info

    def list_artifacts(self, domain: str) -> list[dict]:
        """List all files in output-{domain}/ recursively."""
        output_dir = Path(_project_root) / f"output-{domain}"
        if not output_dir.is_dir():
            return []

        def _scan_dir(path: Path, rel_base: Path) -> list[dict]:
            entries = []
            try:
                for item in sorted(path.iterdir()):
                    rel = str(item.relative_to(rel_base)).replace("\\", "/")
                    if item.is_dir():
                        children = _scan_dir(item, rel_base)
                        entries.append({
                            "name": item.name,
                            "path": rel,
                            "is_dir": True,
                            "size": 0,
                            "children": children,
                        })
                    else:
                        try:
                            size = item.stat().st_size
                        except OSError:
                            size = 0
                        entries.append({
                            "name": item.name,
                            "path": rel,
                            "is_dir": False,
                            "size": size,
                        })
            except PermissionError:
                pass
            return entries

        return _scan_dir(output_dir, output_dir)

    def search_artifacts(self, domain: str, query: str) -> list[dict]:
        """Search recursively inside all text-like artifacts for a given string query."""
        output_dir = Path(_project_root) / f"output-{domain}"
        if not output_dir.is_dir():
            return []

        text_extensions = {
            ".txt", ".json", ".jsonl", ".md", ".log", ".csv", ".xml",
            ".yaml", ".yml", ".html", ".htm", ".cfg", ".conf", ".ini",
        }
        
        results = []
        
        def _search_dir(path: Path):
            try:
                for item in sorted(path.iterdir()):
                    if item.is_dir():
                        _search_dir(item)
                    elif item.is_file() and item.suffix.lower() in text_extensions:
                        # Skip massive files to prevent CPU/RAM denial of service
                        try:
                            if item.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                                continue
                        except OSError:
                            continue
                            
                        try:
                            content = item.read_text(encoding="utf-8", errors="replace")
                            if query.lower() in content.lower():
                                rel_path = str(item.relative_to(output_dir)).replace("\\", "/")
                                
                                # Extract matching line snippets
                                lines = content.splitlines()
                                snippets = []
                                matches_count = 0
                                for idx, line in enumerate(lines):
                                    if query.lower() in line.lower():
                                        matches_count += 1
                                        if len(snippets) < 5:  # Keep payloads lightweight (max 5 snippets)
                                            # Clean up line snippets from binary/strange characters
                                            snippets.append({
                                                "line": idx + 1,
                                                "text": line.strip()[:200]  # Limit length of snippet text
                                            })
                                
                                results.append({
                                    "name": item.name,
                                    "path": rel_path,
                                    "size": len(content),
                                    "matches": matches_count,
                                    "snippets": snippets
                                })
                        except Exception:
                            pass
            except PermissionError:
                pass

        _search_dir(output_dir)
        # Sort by highest matches count first
        results.sort(key=lambda x: x["matches"], reverse=True)
        return results

    def get_artifact_path(self, domain: str, file_path: str) -> Optional[Path]:
        """Resolve and validate an artifact file path (prevent traversal)."""
        output_dir = Path(_project_root) / f"output-{domain}"
        target = (output_dir / file_path).resolve()
        # Security: must be within output dir
        if not str(target).startswith(str(output_dir.resolve())):
            return None
        if target.is_file():
            return target
        return None

    def start_scan(
        self,
        domain: str,
        mode: str = "quick",
        modules: list[str] | None = None,
        threads: int | None = None,
        rate_limit: int | None = None,
        timeout: int | None = None,
        sqlmap_level: int | None = None,
        sqlmap_risk: int | None = None,
        sqlmap_threads: int | None = None,
        jitter: bool = False,
        severity: str | None = None,
        resume: bool = True,
    ) -> bool:
        """Start a scan in a background thread. Returns False if already running."""
        if self._state == "running":
            return False

        # Reset state
        self._state = "running"
        self._domain = domain
        self._mode = mode
        self._log_queue = queue.Queue(maxsize=50000)
        with self._log_lock:
            self._log_lines = []
        self._modules_completed = []
        self._modules_failed = []
        self._current_module = None
        self._total_modules = 0
        self._abort_flag.clear()
        self._start_time = time.time()

        self._thread = threading.Thread(
            target=self._run_scan,
            args=(domain, mode, modules or [], threads, rate_limit, timeout, sqlmap_level, sqlmap_risk, sqlmap_threads, jitter, severity, resume),
            daemon=True,
        )
        self._thread.start()
        return True

    def stop_scan(self) -> bool:
        """Signal the running scan to abort."""
        if self._state != "running":
            return False
        self._abort_flag.set()
        if self._oculus:
            self._oculus.abort_requested = True
        self._state = "aborted"
        return True

    def _run_scan(
        self,
        domain: str,
        mode: str,
        modules: list[str],
        threads: int | None,
        rate_limit: int | None,
        timeout: int | None,
        sqlmap_level: int | None,
        sqlmap_risk: int | None,
        sqlmap_threads: int | None,
        jitter: bool,
        severity: str | None,
        resume: bool,
    ):
        """Background thread: configure Oculus and run the scan."""
        # Build config
        config = load_config()
        config["auto_confirm"] = True
        if threads:
            config["threads"] = threads
        if rate_limit:
            config["rate_limit"] = rate_limit
        if timeout:
            config["timeout"] = timeout
        sqlmap_config = config.setdefault("sqlmap", {})
        if sqlmap_level is not None:
            sqlmap_config["level"] = sqlmap_level
        if sqlmap_risk is not None:
            sqlmap_config["risk"] = sqlmap_risk
        if sqlmap_threads is not None:
            sqlmap_config["threads"] = sqlmap_threads
        config["jitter"] = jitter
        if severity:
            config.setdefault("nuclei", {})["severity"] = severity

        # Redirect stdout to capture output
        original_stdout = sys.stdout
        capture = OutputCapture(self._log_queue, original_stdout)
        sys.stdout = capture

        try:
            oc = Oculus(config=config)
            oc._setup_logging_basic()
            self._oculus = oc

            # Initialize tools (captured)
            self._current_module = "Initializing tools"
            oc.initialize_tools()

            # Setup domain and use absolute path for output to prevent cwd mismatch
            oc.domain = domain
            oc.output_dir = str(Path(_project_root) / f"output-{domain}")
            Path(oc.output_dir).mkdir(exist_ok=True, parents=True)
            Path(f"{oc.output_dir}/logs").mkdir(exist_ok=True, parents=True)
            oc._setup_logging_full()
            oc.setup_complete = True
            oc.load_session()

            if self._abort_flag.is_set():
                self._state = "aborted"
                return

            # Determine what to run
            if mode == "quick":
                self._total_modules = 7
                steps = [
                    ("Subdomain Enumeration", oc.run_subdomain_enumeration),
                    ("DNS Resolution", oc.run_dns_resolution),
                    ("Alive Hosts Check", oc.run_alive_hosts_check),
                    ("Fast Port Scan", oc.run_fast_port_scan),
                    ("URL Collection", oc.run_url_collection),
                    ("WAF Detection", oc.run_waf_detection),
                    ("Vulnerability Scan", oc.run_vulnerability_scan),
                ]
            elif mode == "deep":
                self._total_modules = 14
                steps = [
                    ("ASN Discovery", oc.run_asn_discovery),
                    ("Parameter Discovery", oc.run_parameter_discovery),
                    ("JS Endpoint Extraction", oc.run_js_endpoint_extraction),
                    ("Directory Fuzzing", oc.run_directory_fuzzing),
                    ("API Fuzzing", oc.run_api_fuzzing),
                    ("Subdomain Takeover", oc.run_subdomain_takeover_check),
                    ("Advanced URL Enum", oc.run_advanced_url_enum),
                    ("Screenshot Capture", oc.run_screenshot_capture),
                    ("GF Filters", oc.run_gf_filters),
                    ("Tech Scan", oc.run_tech_scan),
                    ("XSS Scan", oc.run_xss_scan),
                    ("CORS Scanner", oc.run_cors_scan),
                    ("HTTP Smuggling", oc.run_http_smuggling),
                    ("SQLi Scan", oc.run_sqlmap_scan),
                ]
            elif mode == "full_spectrum":
                self._total_modules = 29
                # Use the built-in full spectrum method
                self._current_module = "Full Spectrum Scan"
                oc.run_full_spectrum_scan(force_fresh=not resume)
                if not self._abort_flag.is_set():
                    self._modules_completed.append("Full Spectrum Scan")
                    self._state = "completed"
                return
            elif mode == "custom" and modules:
                steps = []
                for mod_name in modules:
                    method_name = MODULE_MAP.get(mod_name)
                    if method_name and hasattr(oc, method_name):
                        nice_name = mod_name.replace("_", " ").title()
                        steps.append((nice_name, getattr(oc, method_name)))
                self._total_modules = len(steps)
            else:
                self._state = "failed"
                return

            # Execute steps sequentially
            if mode != "full_spectrum":
                for step_name, step_func in steps:
                    if self._abort_flag.is_set():
                        self._state = "aborted"
                        return
                    self._current_module = step_name
                    try:
                        step_func()
                        self._modules_completed.append(step_name)
                    except KeyboardInterrupt:
                        self._state = "aborted"
                        return
                    except Exception as e:
                        self._modules_failed.append(step_name)
                        self._log_queue.put(f"[ERROR] {step_name} failed: {e}")

                # Generate reports
                self._current_module = "Generating Reports"
                try:
                    oc.generate_summary()
                    oc.generate_html_report()
                    oc.generate_json_report()
                    oc.generate_markdown_report()
                except Exception:
                    pass

            self._current_module = None
            self._state = "completed"

        except Exception as e:
            self._log_queue.put(f"[FATAL] Scan engine error: {e}")
            self._state = "failed"
        finally:
            sys.stdout = original_stdout
            self._oculus = None


# Singleton engine instance
engine = ScanEngine()
