#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                              O C U L U S                                     ║
║                    Full-Spectrum Recon Orchestration                         ║
║                                                                              ║
║          recon through exploitation  ·  Kali Linux  ·  bug bounty            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import json
import time
import re
import shutil
import shlex
import socket
import random
import logging
import argparse
import inspect
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import urllib.parse
import urllib.request
import urllib.error

# Optional: rich for enhanced output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich import print as rprint
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# Optional: YAML config
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

VERSION = "4.2.0"

DEFAULT_CONFIG = {
    'threads': 50,
    'timeout': 300,
    'rate_limit': 150,
    'retry_count': 2,
    'retry_delay': 5,
    'sqlmap': {
        'level': 5,
        'risk': 3,
        'threads': 50,
    },
    'wordlists': {
        'dns': '/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt',
        'dirs': '/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt',
        'dirs_fallback': '/usr/share/wordlists/dirb/common.txt',
        'resolvers': '/opt/recontools/massdns/resolvers.txt',
        'resolvers_fallback': '/usr/share/massdns/resolvers.txt',
    },
    'api_keys': {
        'shodan': '',
        'github': '',
        'chaos': '',
    },
    'nuclei': {
        'severity': 'low,medium,high,critical',
        'rate_limit': 150,
        'concurrency': 25,
        'templates': '',
    },
    'naabu': {
        'ports': '1-65535',
        'rate': 2000,
    },
    'nmap': {
        'full_port_timeout_base': 3600,
        'full_port_timeout_per_host': 900,
        'full_port_timeout_max': 43200,
    },
    'ffuf': {
        'extensions': 'php,html,js,json,txt,bak,old',
        'status_filter': '200,204,301,302,307,401,403',
        'recursion_depth': 2,
        'max_hosts': 999999,
    },
    'arjun': {
        'max_hosts': 999999,
    },
    'notify': {
        'enabled': False,
        'provider_config': '',
        'bulk': True,
    },
    'ntfy': {
        'enabled': False,
        'url': '',
        'server': 'https://ntfy.sh',
        'topic': '',
        'token': '',
        'username': '',
        'password': '',
        'priority': 'default',
        'tags': 'rocket',
        'send_scan_start': True,
        'send_scan_complete': True,
        'send_module_start': False,
        'send_module_complete': True,
        'send_findings': True,
        'send_errors': True,
        'send_skips': False,
        'timeout': 8,
        'dedupe_window': 20,
    },
    'jaeles': {
        'concurrency': 20,
        'signatures': '',
        'max_hosts': 999999,
    },
    'nikto': {
        'tuning': '1234',
        'timeout': 600,
        'max_hosts': 999999,
    },
    'whatwaf': {
        'max_hosts': 999999,
    },
    'crlfuzz': {
        'concurrency': 25,
    },
    'internetdb': {
        'max_ips': 999999,
    },
    'tplmap': {
        'max_urls': 999999,
    },
    'nomore403': {
        'max_urls': 999999,
        'fallback_hosts': 999999,
    },
    'puredns': {
        'threads': 100,
        'wildcard_batch': 1000000,
    },
    'parallel': True,
    'auto_confirm': False,
    'jitter': False,
}


def load_config():
    """Load config from ~/.config/oculus/config.yaml with defaults"""
    config = DEFAULT_CONFIG.copy()
    config_paths = [
        Path.home() / '.config' / 'oculus' / 'config.yaml',
        Path.home() / '.config' / 'oculus' / 'config.yml',
        Path('config.yaml'),
    ]
    if YAML_AVAILABLE:
        for p in config_paths:
            if p.exists():
                try:
                    with open(p) as f:
                        user_config = yaml.safe_load(f) or {}
                    for k, v in user_config.items():
                        if isinstance(v, dict) and k in config:
                            config[k].update(v)
                        else:
                            config[k] = v
                    break
                except Exception:
                    pass
    return config


class Colors:
    """Professional color scheme for beautiful terminal output"""
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    BRIGHT_CYAN = '\033[36m'
    BRIGHT_GREEN = '\033[32m'
    BRIGHT_YELLOW = '\033[33m'
    BRIGHT_RED = '\033[31m'
    BG_BLUE = '\033[44m'
    BG_GREEN = '\033[42m'
    BG_RED = '\033[41m'
    BG_YELLOW = '\033[43m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    RESET = '\033[0m'


class Oculus:
    """Main reconnaissance framework class"""

    # Module return status constants — used by _run_step to route correctly
    MODULE_OK = 'ok'             # Ran successfully with results
    MODULE_SKIPPED = 'skipped'   # Skipped (missing API key, missing tool, no input)
    MODULE_PARTIAL = 'partial'   # Ran but with degraded/incomplete results
    MODULE_FAILED = 'failed'     # Critical error during execution

    def __init__(self, config=None):
        self.domain = ""
        self.output_dir = ""
        self.tools_status = {}
        self.results = {}
        self.setup_complete = False
        self.config = config or load_config()
        self.logger = None
        self.session_file = ""
        self._path_augmented = False
        self._session_lock = threading.Lock()
        self.active_processes = []
        self._proc_lock = threading.Lock()
        self._ntfy_lock = threading.Lock()
        self._ntfy_sent = {}
        self._last_notified_results = {}
        self._thread_local = threading.local()
        self.skipped_modules = []       # Modules that bailed (missing key/tool)
        self._skip_reasons = {}         # module_name -> reason string
        self._augment_path()

    @property
    def _current_module(self):
        return getattr(self._thread_local, 'current_module', None)

    @_current_module.setter
    def _current_module(self, value):
        self._thread_local.current_module = value

    def kill_all_active_processes(self):
        """Kill all child processes that are currently running"""
        with self._proc_lock:
            for proc in self.active_processes:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                except Exception:
                    pass
            self.active_processes.clear()

    def _augment_path(self, force=False):
        """Ensure common tool install locations are on PATH (pip --user, Go, etc.)."""
        if self._path_augmented and not force:
            return
        home = os.path.expanduser('~')
        gopath = os.environ.get('GOPATH', os.path.join(home, 'go'))
        extra = [
            os.path.join(home, '.local', 'bin'),
            '/usr/local/bin',
            os.path.join(gopath, 'bin'),
            os.path.join(home, 'go', 'bin'),
            '/usr/local/go/bin',
        ]
        parts = [p for p in os.environ.get('PATH', '').split(os.pathsep) if p]
        for p in extra:
            if p and p not in parts:
                parts.insert(0, p)
        os.environ['PATH'] = os.pathsep.join(parts)
        self._path_augmented = True

    def _local_bin_path(self, name):
        """Absolute path to ~/.local/bin/<name> when pip --user installed the CLI."""
        p = os.path.join(os.path.expanduser('~'), '.local', 'bin', name)
        return p if os.path.isfile(p) else None

    def _which_tool(self, name):
        self._augment_path()
        return shutil.which(name) or self._local_bin_path(name)

    def _resolve_cli_tool(self, name):
        """Find pip/Go CLI: PATH, ~/.local/bin, /usr/local/bin (no shell reload needed)."""
        self._augment_path()
        cli = 'kr' if name.lower() == 'kr' else name.lower()
        for candidate in (
            self._which_tool(cli),
            self._local_bin_path(cli),
            f'/usr/local/bin/{cli}',
        ):
            if candidate and (os.path.isfile(candidate) or shutil.which(candidate)):
                return candidate
        return None

    def _pip_package_installed(self, name):
        try:
            r = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', name],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _first_existing_file(self, candidates):
        for p in candidates:
            if p and os.path.isfile(p):
                return p
        return None

    def perform_health_check(self):
        """Pre-flight check for disk space and internet"""
        print(f"{Colors.CYAN}[*] Performing environment health check...{Colors.RESET}")
        
        # Disk Check (500MB)
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        if free_gb < 0.5:
            print(f"{Colors.RED}[!] CRITICAL: Low disk space ({free_gb:.2f} GB free). Scan may fail!{Colors.RESET}")
        else:
            print(f"  {Colors.GREEN}[✔] Disk Space: {free_gb:.2f} GB free{Colors.RESET}")
            
        # Connectivity Check
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            print(f"  {Colors.GREEN}[✔] Internet Connectivity: OK{Colors.RESET}")
        except Exception:
            print(f"{Colors.YELLOW}[!] WARNING: No internet connectivity detected!{Colors.RESET}")
        
        print("")
        self._setup_logging_basic()

    def _setup_logging_basic(self):
        """Basic logging before output dir is known"""
        self.logger = logging.getLogger('oculus')
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            sh = logging.StreamHandler()
            sh.setLevel(logging.WARNING)
            sh.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            self.logger.addHandler(sh)

    def _setup_logging_full(self):
        """Full logging with file handlers once output dir exists"""
        log_dir = Path(self.output_dir) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        # Main log
        fh = logging.FileHandler(str(log_dir / 'oculus.log'))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.logger.addHandler(fh)
        # Error log
        eh = logging.FileHandler(str(log_dir / 'errors.log'))
        eh.setLevel(logging.ERROR)
        eh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.logger.addHandler(eh)

    def _rotate_output_to_backup(self):
        """Move output-<domain>/ to backup-<domain>/, preserving previous scan data.

        Safe to call any time before starting a fresh scan.  The method:
          1. Closes any open file-log handlers so the directory can be moved.
          2. Moves output-<domain>/ → backup-<domain>/ (replacing any prior backup).
          3. Re-creates a clean output-<domain>/logs/ tree.
          4. Re-attaches file logging to the new directory.

        If the move fails (e.g. cross-device filesystem), it falls back to a
        plain deletion with a clearly visible warning.
        """
        if not self.output_dir or not os.path.isdir(self.output_dir):
            return

        # 1. Detach file logging handlers before touching the directory
        if self.logger:
            for handler in list(self.logger.handlers):
                if isinstance(handler, logging.FileHandler):
                    try:
                        handler.close()
                    except Exception:
                        pass
                    self.logger.removeHandler(handler)

        # 2. Determine backup path (sibling of output_dir)
        output_path = Path(self.output_dir).resolve()
        backup_path = output_path.parent / f"backup-{self.domain}"

        try:
            if backup_path.exists():
                shutil.rmtree(str(backup_path))
            shutil.move(str(output_path), str(backup_path))
            print(f"{Colors.CYAN}[*] Previous output backed up → {backup_path.name}/{Colors.RESET}")
        except Exception as e:
            # Fall back: delete in-place with a visible warning
            print(f"{Colors.YELLOW}[!] Could not back up previous output ({e}). Deleting instead.{Colors.RESET}")
            if self.logger:
                self.logger.warning(f"Backup rotation failed: {e}")
            shutil.rmtree(str(output_path), ignore_errors=True)

        # 3. Re-create fresh output directory
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / 'logs').mkdir(parents=True, exist_ok=True)

        # 4. Re-attach file logging to the new directory
        self._setup_logging_full()

    def _crtsh_passive(self):
        """Query crt.sh for subdomains via certificate transparency logs."""
        url = f"https://crt.sh/?q=%.{self.domain}&output=json"
        subs = set()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Oculus/4.2'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                for entry in data:
                    name = entry.get('name_value', '')
                    for sub in name.split('\n'):
                        sub = sub.strip().lower()
                        if sub and '*' not in sub and self.domain in sub:
                            subs.add(sub)
        except Exception as e:
            self.logger.warning(f"crt.sh query failed: {e}")
        return subs

    def _internetdb_lookup(self, ip):
        """Query InternetDB for open ports, CPEs, vulns (zero-auth)."""
        url = f"https://internetdb.shodan.io/{ip}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Oculus/4.2'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def find_tool(self, name):
        """Unified cross-platform path detection with intelligent priority"""
        name_lower = name.lower()
        self._augment_path()

        if name_lower in ('paramspider', 'arjun', 'kr'):
            found = self._resolve_cli_tool(name_lower)
            if found:
                return found

        if name_lower == 'paramspider':
            script = self._first_existing_file([
                "/opt/recontools/ParamSpider/paramspider/main.py",
                "/opt/recontools/paramspider/paramspider/main.py",
                "/opt/recontools/ParamSpider/paramspider.py",
            ])
            if script:
                return script
            if self._pip_package_installed('paramspider'):
                return self._which_tool('paramspider') or 'paramspider'

        elif name_lower == 'arjun':
            script = self._first_existing_file([
                "/opt/recontools/Arjun/arjun.py",
                "/opt/recontools/arjun/arjun.py",
            ])
            if script:
                return script
            if self._pip_package_installed('arjun'):
                return self._which_tool('arjun') or 'arjun'

        elif name_lower == 'kr':
            kr_bin = self._first_existing_file([
                "/usr/local/bin/kr",
                "/opt/recontools/kiterunner/dist/kr",
                "/opt/recontools/Kiterunner/dist/kr",
            ])
            if kr_bin:
                return kr_bin

        # Legacy /opt script paths for other Python recon tools
        special_paths = []
        if name_lower == 'xsstrike':
            special_paths.extend([
                "/opt/recontools/XSStrike/xsstrike.py",
                "/opt/recontools/xsstrike/xsstrike.py",
            ])
        elif name_lower == 'linkfinder':
            special_paths.extend([
                "/opt/recontools/LinkFinder/linkfinder.py",
                "/opt/recontools/linkfinder/linkfinder.py",
            ])
        elif name_lower == 'theharvester':
            special_paths.extend([
                "/opt/recontools/theHarvester/theHarvester.py",
                "/opt/recontools/theharvester/theHarvester.py",
            ])
        elif name_lower == 'eyewitness':
            special_paths.extend([
                "/opt/recontools/EyeWitness/Python/EyeWitness.py",
                "/opt/recontools/EyeWitness/Python/eyewitness.py",
                "/opt/recontools/eyewitness/Python/EyeWitness.py",
                "/opt/recontools/eyewitness/Python/eyewitness.py",
            ])
        elif name_lower == 'smuggler':
            special_paths.extend([
                "/opt/recontools/smuggler/smuggler.py",
                "/opt/recontools/Smuggler/smuggler.py",
            ])
        elif name_lower == 'subzy':
            special_paths.extend([
                "/opt/recontools/subzy/subzy",
            ])
        elif name_lower == 'tplmap':
            special_paths.extend([
                "/opt/recontools/tplmap/tplmap.py",
                "/opt/recontools/Tplmap/tplmap.py",
            ])
        elif name_lower == 'whatwaf':
            special_paths.extend([
                "/opt/recontools/WhatWaf/whatwaf.py",
                "/opt/recontools/whatwaf/whatwaf.py",
            ])

        found = self._first_existing_file(special_paths)
        if found:
            return found

        # Build ordered list of binary paths
        paths = []
        
        # Special case for HTTPx to avoid Conda collision
        if name_lower == 'httpx':
            paths.extend([
                os.path.expanduser("~/go/bin/httpx"),
                "/home/kali/go/bin/httpx",
                "/usr/bin/httpx-toolkit",
                "/usr/local/bin/httpx-toolkit",
            ])

        # Add system PATH version (try both original case and lowercase)
        sys_path = shutil.which(name)
        if sys_path:
            paths.append(sys_path)
        if name != name_lower:
            sys_path_lower = shutil.which(name_lower)
            if sys_path_lower:
                paths.append(sys_path_lower)
            
        # Add pip-installed / user-local locations
        paths.extend([
            os.path.expanduser(f"~/.local/bin/{name}"),
            os.path.expanduser(f"~/.local/bin/{name_lower}"),
        ])

        # Add standard Recon/Go locations
        paths.extend([
            os.path.expanduser(f"~/go/bin/{name}"),
            os.path.expanduser(f"~/go/bin/{name_lower}"),
            f"/home/kali/go/bin/{name}",
            f"/home/kali/go/bin/{name_lower}",
            f"/usr/local/bin/{name}",
            f"/usr/local/bin/{name_lower}",
            f"/usr/bin/{name}",
            f"/usr/bin/{name_lower}",
            f"/root/go/bin/{name}",
            f"/root/go/bin/{name_lower}",
            f"/opt/recontools/{name}/{name}",
            f"/opt/recontools/{name_lower}/{name_lower}",
        ])

        seen = set()
        for p in paths:
            if p and p not in seen:
                seen.add(p)
                if os.path.exists(p) and not os.path.isdir(p):
                    return p
        return None

    def get_tool(self, name, fallback=None):
        """Return the best path to a tool"""
        info = self.tools_status.get(name)
        if isinstance(info, dict):
            path = info.get('path')
            if path:
                if os.path.isfile(path):
                    return path
                if os.path.sep not in path and not path.startswith('.'):
                    resolved = self._which_tool(path) or self._which_tool(name)
                    return resolved or path
        resolved = self._which_tool(fallback or name)
        return resolved or fallback or name

    def get_timeout(self):
        """Return the default configuration timeout, fallback to 300 seconds"""
        return self.config.get('timeout') or self.config.get('default_timeout') or 300

    def run_command(self, command, output_file=None, timeout=None, stream=True, label=None, get_code=False):
        """Execute a shell command with optional real-time streaming and output redirection"""
        if getattr(self, 'abort_requested', False):
            return -1 if get_code else False

        if self.config.get('jitter'):
            time.sleep(random.uniform(0.1, 0.5))

        timeout = timeout or self.config.get('default_timeout', 300)
        self.logger.debug(f"CMD: {command}")
        
        try:
            if stream and not output_file:
                proc = subprocess.Popen(
                    command, shell=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                with self._proc_lock:
                    self.active_processes.append(proc)
                output_lines = []
                done_evt = threading.Event()
                
                def _reader():
                    try:
                        for line in proc.stdout:
                            if done_evt.is_set():
                                break
                            stripped = line.rstrip()
                            if stripped:
                                output_lines.append(stripped)
                                prefix = f"[{label}] " if label else ""
                                # Stream all command output lines to standard output for rich, real-time Web UI scrolling.
                                # (For pure CLI use, to throttle log flooding on the console, you can uncomment the following condition):
                                # if len(output_lines) <= 50 or len(output_lines) % 100 == 0:
                                print(f"  {Colors.DIM}{prefix}{stripped[:120]}{Colors.RESET}")
                                self.logger.debug(stripped)
                    except Exception:
                        pass
                
                reader = threading.Thread(target=_reader, daemon=True)
                reader.start()
                reader.join(timeout=timeout)
                
                if reader.is_alive():
                    done_evt.set()
                    proc.kill()
                    reader.join(timeout=5)
                    print(f"{Colors.RED}[!] Command timed out after {timeout}s{Colors.RESET}")
                    self.logger.error(f"Timeout: {command}")
                    with self._proc_lock:
                        if proc in self.active_processes:
                            self.active_processes.remove(proc)
                    return -1 if get_code else False
                
                proc.wait()
                with self._proc_lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)
                return proc.returncode if get_code else (proc.returncode == 0)
                
            elif output_file:
                with open(output_file, 'w') as f:
                    proc = subprocess.Popen(
                        command, shell=True,
                        stdin=subprocess.DEVNULL,
                        stdout=f, stderr=subprocess.STDOUT,
                        text=True
                    )
                    with self._proc_lock:
                        self.active_processes.append(proc)
                    try:
                        proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        print(f"{Colors.RED}[!] Command timed out after {timeout}s{Colors.RESET}")
                        self.logger.error(f"Timeout: {command}")
                        with self._proc_lock:
                            if proc in self.active_processes:
                                self.active_processes.remove(proc)
                        return -1 if get_code else False
                    finally:
                        with self._proc_lock:
                            if proc in self.active_processes:
                                self.active_processes.remove(proc)
                return proc.returncode if get_code else (proc.returncode == 0)
                
            else:
                proc = subprocess.Popen(
                    command, shell=True, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True
                )
                with self._proc_lock:
                    self.active_processes.append(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    print(f"{Colors.RED}[!] Command timed out after {timeout}s{Colors.RESET}")
                    self.logger.error(f"Timeout: {command}")
                    with self._proc_lock:
                        if proc in self.active_processes:
                            self.active_processes.remove(proc)
                    return -1 if get_code else False
                finally:
                    with self._proc_lock:
                        if proc in self.active_processes:
                            self.active_processes.remove(proc)
                return proc.returncode if get_code else (proc.returncode == 0)
                
        except subprocess.TimeoutExpired:
            print(f"{Colors.RED}[!] Command timed out after {timeout} seconds{Colors.RESET}")
            self.logger.error(f"Timeout: {command}")
            if 'proc' in locals():
                with self._proc_lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)
            return -1 if get_code else False
        except Exception as e:
            print(f"{Colors.RED}[!] Command failed: {e}{Colors.RESET}")
            self.logger.error(f"Command failed: {e}")
            if 'proc' in locals():
                with self._proc_lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)
            return -1 if get_code else False

    def run_command_with_retry(self, command, output_file=None, timeout=300, retries=None, label=None):
        """Run command with retry logic"""
        retries = retries or self.config.get('retry_count', 2)
        for attempt in range(retries + 1):
            if getattr(self, 'abort_requested', False):
                return False
            if self.run_command(command, output_file=output_file, timeout=timeout, label=label):
                return True
            if getattr(self, 'abort_requested', False):
                return False
            if attempt < retries:
                delay = self.config.get('retry_delay', 5) * (attempt + 1)
                # Check abort during retry delay sleep
                for _ in range(delay):
                    if getattr(self, 'abort_requested', False):
                        return False
                    time.sleep(1)
                print(f"{Colors.YELLOW}[!] Retry {attempt+1}/{retries} in {delay}s...{Colors.RESET}")
                self.logger.warning(f"Retry {attempt+1}: {command}")
        return False

    def safe_domain(self):
        """Return shell-safe quoted domain"""
        return shlex.quote(self.domain)

    def merge_and_dedup_files(self, input_files, output_file):
        """Merge multiple files and remove duplicates"""
        try:
            unique_lines = set()
            for file_path in input_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        unique_lines.update(line.strip() for line in f if line.strip())
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in sorted(unique_lines):
                    f.write(f"{line}\n")
            return len(unique_lines)
        except Exception as e:
            print(f"{Colors.RED}[!] Error merging files: {e}{Colors.RESET}")
            self.logger.error(f"Merge error: {e}")
            return 0

    @staticmethod
    def _path_has_output(path):
        """True if path is a non-empty file or a directory containing a non-empty file."""
        if os.path.isfile(path):
            return os.path.getsize(path) > 0
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for name in files:
                    fp = os.path.join(root, name)
                    try:
                        if os.path.getsize(fp) > 0:
                            return True
                    except OSError:
                        continue
        return False

    def _ntfy_config(self):
        cfg = self.config.get('ntfy', {}) or {}
        return cfg if isinstance(cfg, dict) else {}

    def _ntfy_enabled_for(self, event_key):
        cfg = self._ntfy_config()
        if not cfg.get('enabled', False):
            return False
        flag_map = {
            'scan_start': 'send_scan_start',
            'scan_complete': 'send_scan_complete',
            'module_start': 'send_module_start',
            'module_complete': 'send_module_complete',
            'finding': 'send_findings',
            'error': 'send_errors',
            'skip': 'send_skips',
        }
        flag = flag_map.get(event_key)
        return True if flag is None else bool(cfg.get(flag, True))

    def _ntfy_endpoint(self):
        cfg = self._ntfy_config()
        explicit = str(cfg.get('url', '')).strip()
        if explicit:
            return explicit
        topic = str(cfg.get('topic', '')).strip()
        if not topic:
            return None
        server = str(cfg.get('server', 'https://ntfy.sh')).strip().rstrip('/')
        if not server:
            server = 'https://ntfy.sh'
        return f"{server}/{urllib.parse.quote(topic, safe='')}"

    @staticmethod
    def _ntfy_metric(value):
        if isinstance(value, bool):
            return (1 if value else 0, 'true' if value else 'false')
        if isinstance(value, (int, float)):
            return (int(value), str(value))
        if isinstance(value, dict):
            return (len(value), f"{len(value)} entries")
        if isinstance(value, (list, tuple, set)):
            return (len(value), f"{len(value)} items")
        text = str(value).strip()
        return (1 if text else 0, text)

    def _notify_ntfy(self, event_key, title, message, priority=None, tags=None, dedupe_key=None):
        cfg = self._ntfy_config()
        if not self._ntfy_enabled_for(event_key):
            return False

        endpoint = self._ntfy_endpoint()
        if not endpoint:
            return False

        dedupe_window = max(int(cfg.get('dedupe_window', 20) or 0), 0)
        cache_key = dedupe_key or f"{event_key}:{title}:{message}"
        now = time.time()
        with self._ntfy_lock:
            last_sent = self._ntfy_sent.get(cache_key)
            if last_sent is not None and dedupe_window and (now - last_sent) < dedupe_window:
                return False
            self._ntfy_sent[cache_key] = now

        payload = message.encode('utf-8')
        headers = {
            'Title': title[:256],
            'Priority': str(priority or cfg.get('priority', 'default')),
        }
        tag_value = tags if tags is not None else cfg.get('tags', '')
        if isinstance(tag_value, (list, tuple)):
            tag_value = ','.join(str(tag).strip() for tag in tag_value if str(tag).strip())
        if tag_value:
            headers['Tags'] = str(tag_value)

        token = str(cfg.get('token', '')).strip()
        username = str(cfg.get('username', '')).strip()
        password = str(cfg.get('password', '')).strip()
        request = urllib.request.Request(endpoint, data=payload, method='POST', headers=headers)
        if token:
            request.add_header('Authorization', f'Bearer {token}')
        elif username or password:
            creds = f"{username}:{password}".encode('utf-8')
            request.add_header('Authorization', f"Basic {base64.b64encode(creds).decode('ascii')}")

        timeout = max(int(cfg.get('timeout', 8) or 8), 1)
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"ntfy delivery failed: {e}")
            return False

    def notify_scan_event(self, event_key, title, message, priority=None, tags=None, dedupe_key=None):
        """Public wrapper so the web engine can emit ntfy events through the core notifier."""
        return self._notify_ntfy(event_key, title, message, priority=priority, tags=tags, dedupe_key=dedupe_key)

    def _notify_result_changes(self, module_name=None):
        current = dict(self.results)
        previous = self._last_notified_results
        changes = []
        for key, value in current.items():
            if previous.get(key) == value:
                continue
            metric, summary = self._ntfy_metric(value)
            if metric > 0:
                changes.append((key, metric, summary))

        if changes:
            scope = module_name or self._current_module or self.domain or 'Oculus'
            top_key, top_metric, top_summary = changes[0]
            detail_bits = [f"{key}={metric}" for key, metric, _ in changes[:5]]
            detail = ', '.join(detail_bits)
            if len(changes) > 5:
                detail += f" (+{len(changes) - 5} more)"
            message = f"{scope}: {detail}"
            if top_summary and top_summary != str(top_metric):
                message += f"\nTop result: {top_key} -> {top_summary}"
            self._notify_ntfy(
                'finding',
                f"Oculus findings: {scope}",
                message,
                priority='high',
                tags=['rotating_light'],
                dedupe_key=f"finding:{scope}:{detail}",
            )

        self._last_notified_results = current

    def _notify_module_done(self, module_name, result_key=None, marker_files=None, status=None):
        """Send a detailed, status-aware completion notification.

        status: 'ok' | 'partial' | 'skipped' | 'failed' | None (defaults to ok)
        """
        # --- Route skipped/failed to their own notifiers ---
        if status == self.MODULE_SKIPPED:
            reason = self._skip_reasons.get(module_name, 'not available')
            self._notify_module_skipped(module_name, reason)
            return
        if status == self.MODULE_FAILED:
            self._notify_module_error(module_name, 'module returned failure status')
            return

        # --- Build result detail from metrics ---
        detail_parts = []
        if result_key and result_key in self.results:
            metric, summary = self._ntfy_metric(self.results[result_key])
            detail_parts.append(f"{result_key}: {summary}")
        if marker_files:
            for rel in (marker_files or []):
                if self.output_dir and Oculus._path_has_output(os.path.join(self.output_dir, rel)):
                    detail_parts.append(f"output: {rel}")
                    break
        if not detail_parts:
            detail_parts.append('completed (no new findings)')

        detail = ' | '.join(detail_parts)
        is_partial = (status == self.MODULE_PARTIAL)

        if is_partial:
            self._notify_ntfy(
                'module_complete',
                f"⚠️ Oculus partial: {module_name}",
                f"[PARTIAL] {module_name} for {self.domain or 'target'}\n{detail}\nSome results may be incomplete.",
                priority='default',
                tags=['warning'],
                dedupe_key=f"module_partial:{module_name}:{detail}",
            )
        else:
            self._notify_ntfy(
                'module_complete',
                f"✅ Oculus done: {module_name}",
                f"[DONE] {module_name} for {self.domain or 'target'}\n{detail}",
                priority='default',
                tags=['white_check_mark'],
                dedupe_key=f"module_done:{module_name}:{detail}",
            )

    def _notify_module_skipped(self, module_name, reason='not available'):
        """Send a skip notification — routed to 'skip' event (off by default)."""
        self._notify_ntfy(
            'skip',
            f"⏩ Oculus skipped: {module_name}",
            f"[SKIPPED] {module_name} for {self.domain or 'target'}\nReason: {reason}\nNo scan was performed for this module.",
            priority='min',
            tags=['fast_forward'],
            dedupe_key=f"module_skipped:{module_name}:{reason}",
        )

    def _notify_module_start(self, module_name):
        self._notify_ntfy(
            'module_start',
            f"▶️ Oculus started: {module_name}",
            f"[STARTED] {module_name} for {self.domain or 'target'}",
            priority='low',
            tags=['play_arrow'],
            dedupe_key=f"module_start:{module_name}:{self.domain}",
        )

    def _notify_module_error(self, module_name, error_text):
        self._notify_ntfy(
            'error',
            f"❌ Oculus error: {module_name}",
            f"[FAILED] {module_name} for {self.domain or 'target'}\nError: {error_text}",
            priority='high',
            tags=['warning'],
            dedupe_key=f"module_error:{module_name}:{error_text}",
        )

    def save_session(self):
        """Save session state to JSON for resume capability"""
        if not self.output_dir:
            return
        try:
            session_path = Path(self.output_dir) / 'session.json'
            with self._session_lock:
                session_data = {
                    'domain': self.domain,
                    'output_dir': self.output_dir,
                    'results': dict(self.results),
                    'completed_modules': list(self.results.keys()),
                    'timestamp': datetime.now().isoformat(),
                    'version': VERSION,
                }
                with open(session_path, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2)
            self._notify_result_changes(self._current_module)
        except Exception as e:
            self.logger.error(f"Session save failed: {e}")

    def load_session(self):
        """Load previous session state if available and show diff"""
        session_path = Path(self.output_dir) / 'session.json'
        if session_path.exists():
            try:
                with self._session_lock:
                    with open(session_path, encoding='utf-8') as f:
                        data = json.load(f)
                completed = data.get('completed_modules', [])
                if completed:
                    print(f"\n{Colors.CYAN}[*] Previous session found ({data.get('timestamp', 'unknown')}){Colors.RESET}")
                    print(f"  {Colors.WHITE}Completed: {', '.join(completed)}{Colors.RESET}")
                    if self.config.get('auto_confirm', False):
                        resume = 'y'
                        print(f"  {Colors.YELLOW}[*] Auto-confirm enabled: Resuming session{Colors.RESET}")
                    else:
                        resume = input(f"{Colors.YELLOW}[?] Load previous results and resume? (y/n): {Colors.RESET}").lower().strip()
                    if resume == 'y':
                        old_results = data.get('results', {})
                        self.results = old_results.copy()
                        self._prev_results = old_results.copy()
                        print(f"{Colors.GREEN}[✔] Session restored{Colors.RESET}")
                        return True
            except Exception as e:
                self.logger.error(f"Session load failed: {e}")
        return False

    def show_diff(self):
        """Compare current results against previous session and highlight changes"""
        prev = getattr(self, '_prev_results', {})
        if not prev:
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] DIFF vs Previous Session:{Colors.RESET}")
        for key, new_val in self.results.items():
            old_val = prev.get(key, 0)
            if isinstance(new_val, int) and isinstance(old_val, int):
                diff = new_val - old_val
                if diff > 0:
                    print(f"  {Colors.GREEN}[+] {key}: {old_val} -> {new_val} (+{diff} NEW){Colors.RESET}")
                elif diff < 0:
                    print(f"  {Colors.YELLOW}[-] {key}: {old_val} -> {new_val} ({diff}){Colors.RESET}")
        for key in prev:
            if key not in self.results:
                print(f"  {Colors.RED}[!] {key} no longer found in new scan{Colors.RESET}")
        print()

    def read_file_lines(self, filepath):
        """Safely read lines from a file"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    return [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.logger.error(f"Read error {filepath}: {e}")
        return []

    def count_file_lines(self, filepath):
        """Count non-empty lines in a file"""
        return len(self.read_file_lines(filepath))

    def display_banner(self):
        """Display beautiful rich ASCII banner"""
        if RICH_AVAILABLE:
            from rich.panel import Panel
            from rich.align import Align
            from rich.text import Text
            from rich import print as rprint
            
            ascii_art = """[bold cyan]    ██████╗  ██████╗██╗   ██╗██╗     ██╗   ██╗███████╗
   ██╔═══██╗██╔════╝██║   ██║██║     ██║   ██║██╔════╝
   ██║   ██║██║     ██║   ██║██║     ██║   ██║███████╗
   ██║   ██║██║     ██║   ██║██║     ██║   ██║╚════██║
   ╚██████╔╝╚██████╗╚██████╔╝███████╗╚██████╔╝███████║
     ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝"""
            
            desc = f"\n[bold white]Full-Spectrum Attack Surface Intelligence  v{VERSION}[/]\n[dim cyan]36 modules  |  5-phase pipeline  |  concurrent execution  |  Kali Linux[/]\n"
            
            panel_content = Align.center(Text.from_markup(ascii_art + "\n" + desc), vertical="middle")
            
            panel = Panel(
                panel_content,
                border_style="cyan",
                padding=(1, 2)
            )
            rprint(panel)
        else:
            banner = f"""
{Colors.CYAN}{Colors.BOLD}
================================================================================
    ██████╗  ██████╗██╗   ██╗██╗     ██╗   ██╗███████╗
   ██╔═══██╗██╔════╝██║   ██║██║     ██║   ██║██╔════╝
   ██║   ██║██║     ██║   ██║██║     ██║   ██║███████╗
   ██║   ██║██║     ██║   ██║██║     ██║   ██║╚════██║
   ╚██████╔╝╚██████╗╚██████╔╝███████╗╚██████╔╝███████║
    ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝
     
         {Colors.WHITE}Full-Spectrum Attack Surface Intelligence  v{VERSION}{Colors.CYAN}
         {Colors.DIM}36 modules  |  5-phase pipeline  |  Kali Linux{Colors.CYAN}
================================================================================
{Colors.RESET}"""
            print(banner)

    def check_tool_installation(self, tool_name, install_command=None):
        """Check if a tool is installed"""
        path = self.find_tool(tool_name)
        if path:
            self.tools_status[tool_name] = {
                'installed': True,
                'path': path
            }
            return True
        self.tools_status[tool_name] = {
            'installed': False,
            'install_command': install_command or f'sudo apt install {tool_name}'
        }
        return False

    def initialize_tools(self):
        """Initialize and check all required tools"""
        self._path_augmented = False
        self._augment_path(force=True)

        tools_to_check = [
            ('subfinder', 'go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest'),
            ('amass', 'sudo apt install amass'),
            ('assetfinder', 'go install github.com/tomnomnom/assetfinder@latest'),
            ('dnsx', 'go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest'),
            ('httpx', 'go install github.com/projectdiscovery/httpx/cmd/httpx@latest'),
            ('httprobe', 'go install github.com/tomnomnom/httprobe@latest'),
            ('naabu', 'go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest'),
            ('nmap', 'sudo apt install nmap'),
            ('katana', 'go install github.com/projectdiscovery/katana/cmd/katana@latest'),
            ('gau', 'go install github.com/lc/gau@latest'),
            ('waybackurls', 'go install github.com/tomnomnom/waybackurls@latest'),
            ('wafw00f', 'sudo apt install wafw00f'),
            ('whatweb', 'sudo apt install whatweb'),
            ('sqlmap', 'sudo apt install sqlmap'),
            ('chromium', 'sudo apt install chromium'),
            ('nuclei', 'go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest'),
            ('hakrawler', 'go install github.com/hakluke/hakrawler@latest'),
            ('ffuf', 'go install github.com/ffuf/ffuf@latest'),
            ('dalfox', 'go install github.com/hahwul/dalfox/v2@latest'),
            ('asnmap', 'go install github.com/projectdiscovery/asnmap/cmd/asnmap@latest'),
            ('gowitness', 'go install github.com/sensepost/gowitness@latest'),
            ('gf', 'go install github.com/tomnomnom/gf@latest'),
            ('massdns', 'binary expected at /usr/local/bin/massdns'),
            ('puredns', 'go install github.com/d3mondev/puredns/v2@latest'),
            ('cariddi', 'go install github.com/edoardottt/cariddi/cmd/cariddi@latest'),
            ('jaeles', 'go install github.com/jaeles-project/jaeles@latest'),
            ('crlfuzz', 'go install github.com/dwisiswant0/crlfuzz/cmd/crlfuzz@latest'),
            ('qsreplace', 'go install github.com/tomnomnom/qsreplace@latest'),
            ('tlsx', 'go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest'),
            ('alterx', 'go install github.com/projectdiscovery/alterx/cmd/alterx@latest'),
            ('nomore403', 'go install github.com/devploit/nomore403@latest'),
            ('notify', 'go install github.com/projectdiscovery/notify/cmd/notify@latest'),
            ('nikto', 'sudo apt install nikto'),
        ]

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Tool Installation Status...{Colors.RESET}\n")

        installed_count = 0
        for tool, install_cmd in tools_to_check:
            status = "✔" if self.check_tool_installation(tool, install_cmd) else "✘"
            color = Colors.GREEN if status == "✔" else Colors.RED
            if status == "✔":
                installed_count += 1
            print(f"  {color}[{status}] {tool.capitalize()}{Colors.RESET}")

        special_tools = [
            'paramspider', 'arjun', 'xsstrike', 'smuggler',
            'linkfinder', 'theharvester', 'subzy', 'kr', 'eyewitness',
            'tplmap', 'whatwaf',
        ]

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Python/Opt-based Tools...{Colors.RESET}\n")

        pip_cli_tools = {'paramspider', 'arjun', 'kr'}
        for name in special_tools:
            lookup = 'theHarvester' if name == 'theharvester' else name
            if name in pip_cli_tools:
                resolved = self._resolve_cli_tool(name) or self.find_tool(lookup)
            else:
                resolved = self.find_tool(lookup)
            exists = bool(resolved)

            self.tools_status[name] = {
                'installed': exists,
                'path': resolved or '',
                'install_command': 'Run ./install.sh --update (see INSTALLATION.md)',
            }
            status = "✔" if exists else "✘"
            color = Colors.GREEN if exists else Colors.RED
            if exists:
                installed_count += 1
            print(f"  {color}[{status}] {name.capitalize()}{Colors.RESET}")

        total = len(tools_to_check) + len(special_tools)
        print(f"\n{Colors.GREEN}[✔] {installed_count}/{total} tools available{Colors.RESET}")
        if installed_count < total:
            print(f"{Colors.YELLOW}[!] Missing tools detected. Run: ./install.sh --update{Colors.RESET}")
            print(f"{Colors.DIM}    See INSTALLATION.md for manual recovery steps.{Colors.RESET}")
            print(f"{Colors.DIM}    Ensure $HOME/.local/bin is on PATH: export PATH=\"$HOME/.local/bin:$PATH\"{Colors.RESET}\n")

    def setup_domain(self):
        """Setup domain and create output directory"""
        if self.setup_complete:
            change = input(f"\n{Colors.YELLOW}[?] Current domain: {self.domain}. Change domain? (y/n): {Colors.RESET}").lower().strip()
            if change != 'y':
                return True

        domain = input(f"\n{Colors.CYAN}[+] Enter target domain (e.g., example.com): {Colors.RESET}").strip()
        if not domain:
            print(f"{Colors.RED}[!] Domain cannot be empty!{Colors.RESET}")
            return False

        domain_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, domain):
            print(f"{Colors.RED}[!] Invalid domain format!{Colors.RESET}")
            return False

        self.domain = domain
        self.output_dir = f"output-{domain}"

        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            Path(f"{self.output_dir}/logs").mkdir(parents=True, exist_ok=True)
            self._setup_logging_full()
            self.logger.info(f"Target domain set: {domain}")
            print(f"\n{Colors.GREEN}[✔] Created output directory: {self.output_dir}/{Colors.RESET}")
            self.setup_complete = True
            self.load_session()
            return True
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to create directory: {e}{Colors.RESET}")
            return False

    def _require_setup(self):
        """Check if domain setup is complete, print error if not"""
        if not self.setup_complete:
            print(f"{Colors.RED}[!] Please set up domain first!{Colors.RESET}")
            if self._current_module:
                self._skip_reasons[self._current_module] = "Domain setup not completed"
            return False
        return True

    def _require_file(self, filepath, msg="Required file not found"):
        """Check if a file exists and has content"""
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"{Colors.RED}[!] {msg}{Colors.RESET}")
            if self._current_module:
                self._skip_reasons[self._current_module] = f"Required file '{os.path.basename(filepath)}' not found: {msg}"
            return False
        return True

    def _require_tool(self, tool_name):
        """Check if a tool is installed"""
        if not self.tools_status.get(tool_name, {}).get('installed'):
            cmd = self.tools_status.get(tool_name, {}).get('install_command', f'Install {tool_name}')
            print(f"{Colors.RED}[!] {tool_name} not installed! {cmd}{Colors.RESET}")
            if self._current_module:
                self._skip_reasons[self._current_module] = f"Tool '{tool_name}' not installed"
            return False
        return True

    def _get_hosts(self, prefer_alive=True):
        """Get scan targets with intelligent fallback chain"""
        sources = []
        if prefer_alive:
            sources = [
                f"{self.output_dir}/alive.txt",
                f"{self.output_dir}/subdomains.txt",
            ]
        else:
            sources = [f"{self.output_dir}/subdomains.txt"]

        final_hosts = []
        for src in sources:
            hosts = self.read_file_lines(src)
            if hosts:
                # Scope enforcement — exact match or valid subdomain suffix only
                # (prevents "evil-example.com" matching when domain="example.com")
                for h in hosts:
                    bare = h.replace('https://', '').replace('http://', '').split('/')[0]
                    if bare == self.domain or bare.endswith('.' + self.domain):
                        final_hosts.append(h)
                break
        return final_hosts if final_hosts else [self.domain]

    def _strip_protocol(self, url):
        """Remove http(s):// prefix and trailing path"""
        return url.replace("https://", "").replace("http://", "").split("/")[0]

    def _config_limit(self, section, key, default):
        """Read a positive integer limit from config, falling back safely."""
        try:
            value = int((self.config.get(section, {}) or {}).get(key, default))
            return value if value > 0 else default
        except Exception:
            return default

    def _run_qsreplace_to_file(self, input_file, output_file, payload, label):
        """Run qsreplace and only return output_file when it produced usable content."""
        qsreplace_bin = self.get_tool('qsreplace')
        if not qsreplace_bin or not os.path.exists(input_file):
            return input_file

        cmd = f"cat {shlex.quote(input_file)} | {shlex.quote(qsreplace_bin)} {shlex.quote(payload)} | sort -u > {shlex.quote(output_file)}"
        if self.run_command(cmd, timeout=60, label=label) and Oculus._path_has_output(output_file):
            return output_file

        print(f"{Colors.YELLOW}[!] {label} produced no usable output; keeping original input list{Colors.RESET}")
        try:
            if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
                os.remove(output_file)
        except OSError:
            pass
        return input_file

    def _merge_cariddi_secrets_into_js(self):
        """Merge Cariddi secret-looking findings into JS secret artifacts."""
        cariddi_txt = f"{self.output_dir}/cariddi/cariddi_results.txt"
        if not os.path.exists(cariddi_txt):
            return 0

        js_dir = f"{self.output_dir}/js_endpoints"
        Path(js_dir).mkdir(parents=True, exist_ok=True)
        targets = [f"{js_dir}/secrets.txt", f"{js_dir}/js_secrets.txt"]
        keywords = ['secret', 'api_key', 'apikey', 'token', 'private_key', 'aws_key', 'stripe', 'password', 'credential']
        additions = set()
        for line in self.read_file_lines(cariddi_txt):
            if any(kw in line.lower() for kw in keywords):
                additions.add(f"Cariddi -> {line.strip()}")

        if not additions:
            return 0

        merged_count = 0
        for target in targets:
            existing = set(self.read_file_lines(target))
            merged = existing | additions
            with open(target, 'w', encoding='utf-8') as f:
                for item in sorted(merged):
                    f.write(item + "\n")
            merged_count = max(merged_count, len(merged) - len(existing))

        self.results['js_secrets'] = self.count_file_lines(targets[0])
        self.save_session()
        return merged_count

    def suggest_next_steps(self, completed_task):
        """Intelligently suggest next steps based on completed task"""
        suggestions = {
            'subdomains': [('DNS Resolution', '2'), ('Alive Hosts Check', '3'), ('Full Automated Recon', '9')],
            'dns_resolution': [('Alive Hosts Check', '3'), ('Fast Port Scan', '4')],
            'alive_hosts': [('Fast Port Scan', '4'), ('URL Collection', '6'), ('WAF Detection', '7')],
            'port_scan': [('URL Collection', '6'), ('WAF Detection', '7'), ('Vulnerability Scan', '8')],
            'urls': [('WAF Detection', '7'), ('Vulnerability Scan', '8'), ('GF Filters', '18')],
            'waf_detection': [('Vulnerability Scan', '8'), ('Deep Recon Mode', 'D')],
        }
        if completed_task in suggestions:
            print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Recommended Next Steps:{Colors.RESET}")
            for desc, option in suggestions[completed_task]:
                print(f"  {Colors.YELLOW}→ {desc} (Option {option}){Colors.RESET}")
            print()


    # CORE MODULE 1: SUBDOMAIN ENUMERATION (CONCURRENT)

    def _run_single_subdomain_tool(self, tool_name, cmd, output_file):
        """Worker for concurrent subdomain enumeration"""
        print(f"{Colors.YELLOW}[*] Running {tool_name}...{Colors.RESET}")
        if self.run_command_with_retry(cmd, output_file=output_file, timeout=600, label=tool_name):
            print(f"{Colors.GREEN}[✔] {tool_name} completed{Colors.RESET}")
            return output_file
        else:
            print(f"{Colors.RED}[!] {tool_name} failed{Colors.RESET}")
            return None

    def run_subdomain_enumeration(self):
        """Run comprehensive subdomain enumeration with concurrent execution"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Subdomain Enumeration...{Colors.RESET}\n")
        sd = self.safe_domain()
        tasks = []
        if self.tools_status.get('subfinder', {}).get('installed'):
            out = f"{self.output_dir}/subfinder_raw.txt"
            b = self.get_tool('subfinder')
            tasks.append(('Subfinder', f"{b} -d {sd} -all -recursive", out))
        if self.tools_status.get('amass', {}).get('installed'):
            out = f"{self.output_dir}/amass_raw.txt"
            b = self.get_tool('amass')
            tasks.append(('Amass', f"{b} enum -passive -d {sd}", out))
        if self.tools_status.get('assetfinder', {}).get('installed'):
            out = f"{self.output_dir}/assetfinder_raw.txt"
            b = self.get_tool('assetfinder')
            tasks.append(('Assetfinder', f"{b} --subs-only {sd}", out))

        if not tasks:
            print(f"{Colors.RED}[!] No subdomain tools available!{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Subdomain Enumeration'] = 'No subdomain tools installed (subfinder, amass, assetfinder)'
            return self.MODULE_SKIPPED

        raw_files = []
        if self.config.get('parallel', True) and len(tasks) > 1:
            print(f"{Colors.CYAN}[*] Running {len(tasks)} tools concurrently...{Colors.RESET}")
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                futures = {executor.submit(self._run_single_subdomain_tool, t[0], t[1], t[2]): t[0] for t in tasks}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        raw_files.append(result)
        else:
            for name, cmd, out in tasks:
                result = self._run_single_subdomain_tool(name, cmd, out)
                if result:
                    raw_files.append(result)

        # --- crt.sh passive (zero-install, pure Python) ---
        print(f"{Colors.CYAN}[*] Querying crt.sh certificate transparency...{Colors.RESET}")
        crtsh_subs = self._crtsh_passive()
        if crtsh_subs:
            crtsh_file = f"{self.output_dir}/crtsh_subs.txt"
            try:
                with open(crtsh_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(sorted(crtsh_subs)) + '\n')
                raw_files.append(crtsh_file)
                print(f"{Colors.GREEN}[✔] crt.sh: {len(crtsh_subs)} subdomains{Colors.RESET}")
            except Exception as e:
                self.logger.error(f"Failed to write crt.sh results: {e}")

        if not raw_files:
            print(f"{Colors.RED}[!] All subdomain tools failed!{Colors.RESET}")
            return self.MODULE_FAILED

        final_output = f"{self.output_dir}/subdomains.txt"
        raw_combined = f"{self.output_dir}/subdomains_raw.txt"
        self.merge_and_dedup_files(raw_files, raw_combined)

        print(f"{Colors.YELLOW}[*] Cleaning and validating subdomains...{Colors.RESET}")
        try:
            subdomains = set()
            for line in self.read_file_lines(raw_combined):
                subdomain = line.lower()
                if self.domain in subdomain and re.match(r'^[a-zA-Z0-9.-]+$', subdomain):
                    subdomains.add(subdomain)
            with open(final_output, 'w', encoding='utf-8') as f:
                for s in sorted(subdomains):
                    f.write(f"{s}\n")
            count = len(subdomains)
            print(f"{Colors.GREEN}[✔] Found {count} unique subdomains{Colors.RESET}")
            self.results['subdomains'] = count
            print(f"\n{Colors.CYAN}[*] Sample subdomains found:{Colors.RESET}")
            for s in list(subdomains)[:10]:
                print(f"  {Colors.WHITE}• {s}{Colors.RESET}")
            if count > 10:
                print(f"  {Colors.DIM}... and {count-10} more{Colors.RESET}")
            self.save_session()
            self.suggest_next_steps('subdomains')
            return self.MODULE_OK
        except Exception as e:
            print(f"{Colors.RED}[!] Error processing subdomains: {e}{Colors.RESET}")
            self.logger.error(f"Subdomain processing: {e}")
            return self.MODULE_FAILED

    # CORE MODULE 2: DNS RESOLUTION

    def run_dns_resolution(self):
        """Run DNS resolution on found subdomains"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file, "No subdomains found! Run subdomain enumeration first."):
            return self.MODULE_SKIPPED
        if not self._require_tool('dnsx'):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting DNS Resolution...{Colors.RESET}\n")
        output_file = f"{self.output_dir}/dns_resolved.txt"
        dnsx_bin = self.get_tool('dnsx')
        cmd = f"{dnsx_bin} -l {subs_file} -a -aaaa -cname -ns -ptr -mx -soa -resp -o {output_file}"
        if self.run_command_with_retry(cmd, timeout=300, label="dnsx"):
            count = self.count_file_lines(output_file)
            print(f"{Colors.GREEN}[✔] DNS resolution completed — {count} records{Colors.RESET}")
            self.results['dns_resolved'] = count
            self.save_session()
            self.suggest_next_steps('dns_resolution')
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] DNS resolution failed{Colors.RESET}")
            return self.MODULE_FAILED

    # CORE MODULE 3: ALIVE HOSTS CHECK (httpx JSON)

    def run_alive_hosts_check(self):
        """Check which hosts are alive using HTTPx and httprobe concurrently for redundancy"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file, "No subdomains found! Run subdomain enumeration first."):
            return self.MODULE_SKIPPED
            
        has_httpx = self.tools_status.get('httpx', {}).get('installed')
        has_httprobe = self.tools_status.get('httprobe', {}).get('installed')
        
        if not has_httpx and not has_httprobe:
            print(f"{Colors.RED}[!] No alive checking tools available (need httpx or httprobe).{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Alive Hosts Check'] = 'No alive checking tools installed (httpx, httprobe)'
            return self.MODULE_SKIPPED
            
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Alive Hosts (Dual Engine)...{Colors.RESET}\n")
        
        def _run_httpx():
            raw_output = f"{self.output_dir}/httpx_raw.json"
            httpx_bin = self.get_tool('httpx')
            threads = self.config.get('threads', 50)
            rl = self.config.get('rate_limit', 150)
            cmd = (f"{httpx_bin} -l {subs_file} -sc -title -ip -cdn -json "
                   f"-threads {threads} -rl {rl} -timeout 10 -o {raw_output}")
            self.run_command_with_retry(cmd, timeout=600, label="httpx")
            
        def _run_httprobe():
            out_file = f"{self.output_dir}/httprobe_raw.txt"
            probe_bin = self.get_tool('httprobe')
            threads = self.config.get('threads', 50)
            cmd = f"cat {shlex.quote(subs_file)} | {probe_bin} -c {threads} -t 10000 > {shlex.quote(out_file)}"
            self.run_command_with_retry(cmd, timeout=600, label="httprobe")
            
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if has_httpx:
                executor.submit(_run_httpx)
            if has_httprobe:
                executor.submit(_run_httprobe)

        clean_hosts = set()
        
        # Parse HTTPx
        if has_httpx:
            raw_output = f"{self.output_dir}/httpx_raw.json"
            try:
                for line in self.read_file_lines(raw_output):
                    try:
                        j = json.loads(line)
                        clean_hosts.add(j["url"])
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception as e:
                print(f"{Colors.RED}[!] Failed parsing HTTPx JSON: {e}{Colors.RESET}")
                
        # Parse HTTPProbe
        if has_httprobe:
            out_file = f"{self.output_dir}/httprobe_raw.txt"
            try:
                for line in self.read_file_lines(out_file):
                    line = line.strip()
                    if line.startswith("http://") or line.startswith("https://"):
                        clean_hosts.add(line)
            except Exception as e:
                print(f"{Colors.RED}[!] Failed parsing httprobe output: {e}{Colors.RESET}")

        alive_file = f"{self.output_dir}/alive.txt"
        with open(alive_file, "w", encoding='utf-8') as f:
            for h in sorted(clean_hosts):
                f.write(h + "\n")
                
        count = len(clean_hosts)
        print(f"{Colors.GREEN}[✔] Found {count} alive hosts{Colors.RESET}")
        if count == 0:
            print(f"{Colors.YELLOW}[*] No alive hosts — will fallback to main domain for scanning{Colors.RESET}")
        else:
            print(f"\n{Colors.CYAN}[*] Sample alive hosts:{Colors.RESET}")
            for h in list(clean_hosts)[:5]:
                print(f"  {Colors.WHITE}• {h}{Colors.RESET}")
            if count > 5:
                print(f"  {Colors.DIM}... and {count-5} more{Colors.RESET}")
        self.results['alive_hosts'] = count
        self.save_session()
        self.suggest_next_steps('alive_hosts')
        return self.MODULE_OK

    # CORE MODULE 4: FAST PORT SCAN (Naabu + CDN detection + Nmap fallback)

    def run_fast_port_scan(self):
        """Run fast port scan with CDN detection and smart fallback"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        hosts_to_scan = [self._strip_protocol(h) for h in self._get_hosts(prefer_alive=True)]
        if not hosts_to_scan:
            hosts_to_scan = [self.domain]
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Fast Port Scan ({len(hosts_to_scan)} targets)...{Colors.RESET}\n")
        # Write input file
        final_input = f"{self.output_dir}/ports_input.txt"
        with open(final_input, 'w', encoding='utf-8') as f:
            for h in hosts_to_scan:
                f.write(h.strip() + "\n")
        # CDN Detection
        cdn_providers = ["cloudflare", "akamai", "imperva", "sucuri", "fastly", "cloudfront"]
        cdn_detected = False
        detected_provider = "Unknown"
        print(f"{Colors.YELLOW}[*] Checking for CDN...{Colors.RESET}")
        try:
            for host in hosts_to_scan[:3]:
                dig_res = subprocess.run(f"dig +short {shlex.quote(host)}", shell=True, capture_output=True, text=True, timeout=15)
                for ip in dig_res.stdout.strip().split("\n"):
                    if not ip.strip():
                        continue
                    whois_res = subprocess.run(f"whois {shlex.quote(ip.strip())}", shell=True, capture_output=True, text=True, timeout=15)
                    whois_data = whois_res.stdout.lower()
                    for provider in cdn_providers:
                        if provider in whois_data:
                            cdn_detected = True
                            detected_provider = provider.capitalize()
                            break
                    if cdn_detected:
                        break
                if cdn_detected:
                    break
        except Exception as e:
            self.logger.warning(f"CDN check failed: {e}")

        use_naabu = self.tools_status.get('naabu', {}).get('installed')
        use_nmap = self.tools_status.get('nmap', {}).get('installed')

        if cdn_detected:
            print(f"{Colors.RED}[!] CDN Detected: {detected_provider} — switching to Nmap{Colors.RESET}")
            use_naabu = False
        if not cdn_detected:
            print(f"{Colors.GREEN}[✔] No CDN detected{Colors.RESET}")
        if not use_naabu and not use_nmap:
            print(f"{Colors.RED}[!] No port scanning tools available!{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Fast Port Scan'] = 'No port scanning tools installed (naabu, nmap)'
            return self.MODULE_SKIPPED

        scanner = "Naabu" if use_naabu else "Nmap"
        output_file = f"{self.output_dir}/ports_fast.txt"

        if use_naabu:
            naabu_bin = self.get_tool('naabu')
            ports = self.config.get('naabu', {}).get('ports', '1-65535')
            rate = self.config.get('naabu', {}).get('rate', 2000)
            cmd = (f"{naabu_bin} -list {final_input} -p {ports} -rate {rate} "
                   f"-scan-all-ips -nc -o {output_file}")
            timeout = 300
        else:
            nmap_bin = self.get_tool('nmap')
            cmd = f"{nmap_bin} -iL {final_input} -p 1-1000 -T4 --open -oG {output_file}"
            timeout = 600

        print(f"{Colors.CYAN}[*] Scanning with {scanner}...{Colors.RESET}")
        if self.run_command_with_retry(cmd, timeout=timeout, label=scanner):
            results = []
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if use_naabu and ':' in line:
                            results.append(line)
                        elif not use_naabu and '/open/' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                host = parts[1]
                                pm = re.search(r'(\d+)/open/', line)
                                if pm:
                                    results.append(f"{host}:{pm.group(1)}")
                with open(output_file, 'w', encoding='utf-8') as f:
                    for r in sorted(results):
                        f.write(f"{r}\n")
                count = len(results)
                print(f"{Colors.GREEN}[✔] Found {count} open ports{Colors.RESET}")
                self.results['fast_ports'] = count
            except Exception as e:
                self.logger.error(f"Port scan parse: {e}")
            self.save_session()
            self.suggest_next_steps('port_scan')
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] Fast port scan failed{Colors.RESET}")
            return self.MODULE_FAILED

    # CORE MODULE 5: FULL PORT SCAN (Nmap -sV -sC with safe XML parsing)

    def _full_port_scan_timeout(self, target_count):
        """Scale the outer Nmap timeout by target count without slowing small scans."""
        nmap_cfg = self.config.get('nmap', {})
        base = int(nmap_cfg.get('full_port_timeout_base', 3600))
        per_host = int(nmap_cfg.get('full_port_timeout_per_host', 900))
        max_timeout = int(nmap_cfg.get('full_port_timeout_max', 43200))
        target_count = max(1, int(target_count or 1))
        return min(max_timeout, max(base, target_count * per_host))

    def run_full_port_scan(self):
        """Comprehensive port scan with Nmap — fixed XML parsing"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('nmap'):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Full Port Scan with Nmap...{Colors.RESET}")
        print(f"{Colors.YELLOW}[!] This may take a while. Press Ctrl+C to skip.{Colors.RESET}\n")
        hosts = self._get_hosts(prefer_alive=True)
        if not hosts:
            hosts = [self.domain]
        hosts = [self._strip_protocol(h.strip()) for h in hosts if h and h.strip()]
        timeout = self._full_port_scan_timeout(len(hosts))
        hours, remainder = divmod(timeout, 3600)
        minutes = remainder // 60
        budget = f"{hours}h {minutes}m" if hours else f"{minutes}m"
        print(f"{Colors.CYAN}[*] Nmap timeout budget: {budget} for {len(hosts)} target(s){Colors.RESET}")
        final_input = f"{self.output_dir}/ports_full_input.txt"
        with open(final_input, 'w', encoding='utf-8') as f:
            for h in hosts:
                f.write(h + "\n")
        output_base = f"{self.output_dir}/ports_full"
        nmap_bin = self.get_tool('nmap')
        cmd = (
            f"{shlex.quote(nmap_bin)} -iL {shlex.quote(final_input)} "
            f"-p- -sV -sC --open -T4 -oA {shlex.quote(output_base)}"
        )
        if self.run_command(cmd, timeout=timeout, label="nmap"):
            xml_file = f"{output_base}.xml"
            results = []
            if os.path.exists(xml_file):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    for host in root.findall('host'):
                        addr_el = host.find('address')
                        address = addr_el.get('addr', 'unknown') if addr_el is not None else 'unknown'
                        ports_el = host.find('ports')
                        if ports_el is None:
                            continue
                        for port in ports_el.findall('port'):
                            state_el = port.find('state')
                            if state_el is None or state_el.get('state') != 'open':
                                continue
                            port_num = port.get('portid')
                            svc = port.find('service')
                            svc_name = svc.get('name', 'unknown') if svc is not None else 'unknown'
                            product = svc.get('product', '') if svc is not None else ''
                            version = svc.get('version', '') if svc is not None else ''
                            info = svc_name
                            if product:
                                info += f" {product}"
                            if version:
                                info += f" {version}"
                            results.append(f"{address}:{port_num} ({info})")
                except Exception as e:
                    self.logger.error(f"Nmap XML parse: {e}")
                    print(f"{Colors.RED}[!] XML parsing error: {e}{Colors.RESET}")
            output_file = f"{output_base}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                for r in sorted(results):
                    f.write(f"{r}\n")
            count = len(results)
            print(f"{Colors.GREEN}[✔] Found {count} services{Colors.RESET}")
            self.results['full_ports'] = count
            self.save_session()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] Full port scan failed{Colors.RESET}")
            return self.MODULE_FAILED


    # CORE MODULE 6: URL COLLECTION (CONCURRENT)

    def _run_single_url_tool(self, tool_name, cmd, output_file):
        """Worker for concurrent URL collection"""
        print(f"{Colors.YELLOW}[*] Running {tool_name}...{Colors.RESET}")
        if self.run_command_with_retry(cmd, output_file=output_file, timeout=300, label=tool_name):
            print(f"{Colors.GREEN}[✔] {tool_name} completed{Colors.RESET}")
            return output_file
        print(f"{Colors.RED}[!] {tool_name} failed{Colors.RESET}")
        return None

    def run_url_collection(self):
        """Collect URLs from multiple sources concurrently"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting URL Collection...{Colors.RESET}\n")
        sd = self.safe_domain()
        tasks = []
        if self.tools_status.get('katana', {}).get('installed'):
            out = f"{self.output_dir}/katana_raw.txt"
            b = self.get_tool('katana')
            tasks.append(('Katana', f"{b} -u https://{sd} -d 3", out))
        if self.tools_status.get('gau', {}).get('installed'):
            out = f"{self.output_dir}/gau_raw.txt"
            b = self.get_tool('gau')
            tasks.append(('Gau', f"{b} {sd}", out))
        if self.tools_status.get('waybackurls', {}).get('installed'):
            out = f"{self.output_dir}/waybackurls_raw.txt"
            b = self.get_tool('waybackurls')
            tasks.append(('Waybackurls', f"{b} {sd}", out))
        if not tasks:
            print(f"{Colors.RED}[!] No URL collection tools available!{Colors.RESET}")
            self._skip_reasons[self._current_module or 'URL Collection'] = 'No URL collection tools installed (katana, gau, waybackurls)'
            return self.MODULE_SKIPPED

        raw_files = []
        if self.config.get('parallel', True) and len(tasks) > 1:
            print(f"{Colors.CYAN}[*] Running {len(tasks)} tools concurrently...{Colors.RESET}")
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                futures = {executor.submit(self._run_single_url_tool, t[0], t[1], t[2]): t[0] for t in tasks}
                for future in as_completed(futures):
                    r = future.result()
                    if r:
                        raw_files.append(r)
        else:
            for name, cmd, out in tasks:
                r = self._run_single_url_tool(name, cmd, out)
                if r:
                    raw_files.append(r)
        if not raw_files:
            print(f"{Colors.RED}[!] No URL collection succeeded!{Colors.RESET}")
            return self.MODULE_FAILED

        final_output = f"{self.output_dir}/urls.txt"
        try:
            unique_urls = set()
            for fp in raw_files:
                for line in self.read_file_lines(fp):
                    url = line.split('#')[0].strip()
                    try:
                        parsed = urllib.parse.urlparse(url)
                        netloc = parsed.netloc.lower()
                        # Only skip if the actual domain/hostname is corrupted by double-encoded slop
                        if "25252f" in netloc or "253d" in netloc or "%2f" in netloc or "%3d" in netloc or "252f" in netloc:
                            continue
                    except Exception:
                        continue
                    
                    # Match domain bounds and valid scheme
                    if url.startswith(('http://', 'https://')):
                        path_lower = parsed.path.lower()
                        if not path_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico', '.css', '.woff', '.woff2', '.ttf', '.svg')):
                            unique_urls.add(url)
            with open(final_output, 'w', encoding='utf-8') as f:
                for url in sorted(unique_urls):
                    f.write(f"{url}\n")
            count = len(unique_urls)
            print(f"{Colors.GREEN}[✔] Found {count} unique URLs{Colors.RESET}")
            self.results['urls'] = count
            self.save_session()
            self.suggest_next_steps('urls')
            self.merge_all_urls()
            return self.MODULE_OK
        except Exception as e:
            print(f"{Colors.RED}[!] Error processing URLs: {e}{Colors.RESET}")
            self.logger.error(f"URL processing: {e}")
            return self.MODULE_FAILED

    # CORE MODULE 7: WAF DETECTION (CONCURRENT)

    def _check_single_waf(self, host):
        """Worker for concurrent WAF detection"""
        host = re.sub(r'^https?://', '', host).split('/')[0]
        wafw00f_bin = self.get_tool('wafw00f')
        cmd = f"{wafw00f_bin} {shlex.quote(host)}"
        known_wafs = {
            "cloudflare": "Cloudflare", "akamai": "Akamai", "sucuri": "Sucuri",
            "imperva": "Imperva", "incapsula": "Imperva", "f5": "F5 Big-IP",
            "barracuda": "Barracuda", "citrix": "Citrix Netscaler",
            "fastly": "Fastly", "aws": "AWS WAF", "cloudfront": "AWS CloudFront",
        }
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out_low = (result.stdout + result.stderr).lower()
            if "no waf detected" in out_low or "generic detection" in out_low:
                return f"{host}: No WAF"
            for key, nice_name in known_wafs.items():
                if re.search(rf"\b{key}\b", out_low):
                    return f"{host}: {nice_name}"
            return f"{host}: Unknown/Error"
        except subprocess.TimeoutExpired:
            return f"{host}: Timeout"
        except Exception as e:
            return f"{host}: Error - {str(e)}"

    def run_waf_detection(self):
        """Detect WAFs with concurrent scanning"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        has_wafw00f = self.tools_status.get('wafw00f', {}).get('installed')
        whatwaf_bin = self.find_tool('whatwaf')
        if not has_wafw00f and not whatwaf_bin:
            print(f"{Colors.RED}[!] No WAF detection tools available (need wafw00f or WhatWaf).{Colors.RESET}")
            self._skip_reasons[self._current_module or 'WAF Detection'] = 'No WAF detection tools installed (wafw00f, whatwaf)'
            return self.MODULE_SKIPPED
        hosts = self._get_hosts(prefer_alive=True)
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting WAF Detection ({len(hosts)} hosts)...{Colors.RESET}\n")
        results = []
        if has_wafw00f:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self._check_single_waf, h): h for h in hosts}
                for i, future in enumerate(as_completed(futures)):
                    r = future.result()
                    results.append(r)
                    if 'No WAF' not in r and 'Unknown' not in r and 'Error' not in r and 'Timeout' not in r:
                        print(f"  {Colors.RED}[WAF] {r}{Colors.RESET}")
                    print(f"  Progress: {i+1}/{len(hosts)}", end='\r')
            print()
        output_file = f"{self.output_dir}/waf_summary.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            for r in results:
                f.write(f"{r}\n")
        waf_found = len([r for r in results if ':' in r and 'No WAF' not in r and 'Unknown' not in r and 'Error' not in r and 'Timeout' not in r])
        print(f"{Colors.GREEN}[✔] WAF detection completed{Colors.RESET}")
        print(f"  {Colors.RED}• Hosts with WAF: {waf_found}{Colors.RESET}")
        print(f"  {Colors.GREEN}• Total tested: {len(hosts)}{Colors.RESET}")

        # --- WhatWaf (deep WAF fingerprinting + bypass suggestions) ---
        if whatwaf_bin:
            whatwaf_limit = self._config_limit('whatwaf', 'max_hosts', 999999)
            print(f"\n{Colors.CYAN}[*] Running WhatWaf detection on up to {whatwaf_limit} alive hosts...{Colors.RESET}")
            alive_file = f"{self.output_dir}/alive.txt"
            if os.path.exists(alive_file):
                whatwaf_dir = f"{self.output_dir}/whatwaf"
                Path(whatwaf_dir).mkdir(parents=True, exist_ok=True)
                whatwaf_summary = f"{whatwaf_dir}/whatwaf_results.txt"
                open(whatwaf_summary, 'w', encoding='utf-8').close()
                whatwaf_hosts = self.read_file_lines(alive_file)[:whatwaf_limit]
                whatwaf_findings = 0
                for idx, host in enumerate(whatwaf_hosts):
                    safe_host = host.replace('://', '_').replace(':', '_').replace('/', '_')
                    out_file = f"{whatwaf_dir}/whatwaf_{idx}_{safe_host}.txt"
                    cmd = f"python3 {whatwaf_bin} -u {shlex.quote(host)} --json --skip"
                    self.run_command(cmd, output_file=out_file, timeout=120, label=f"whatwaf:{host[:40]}")
                    lines = self.read_file_lines(out_file)
                    if lines:
                        with open(whatwaf_summary, 'a', encoding='utf-8') as sf:
                            sf.write(f"===== {host} =====\n")
                            for line in lines:
                                sf.write(line + "\n")
                            sf.write("\n")
                        joined = "\n".join(lines).lower()
                        if not any(skip in joined for skip in ['no waf', 'not behind', 'unable to detect']):
                            whatwaf_findings += 1
                self.results['whatwaf_findings'] = whatwaf_findings
                print(f"{Colors.GREEN}[✔] WhatWaf: {whatwaf_findings} hosts with possible WAF/bypass signal{Colors.RESET}")

        self.results['waf_detected'] = waf_found
        self.results['waf_total'] = len(hosts)
        self.save_session()
        self.suggest_next_steps('waf_detection')
        return self.MODULE_OK

    # CORE MODULE 8: NUCLEI VULNERABILITY SCAN (FIXED — JSONL parsing)

    def run_vulnerability_scan(self):
        """Run Nuclei with JSONL output for reliable parsing"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file, "No alive hosts! Run alive hosts check first."):
            return self.MODULE_SKIPPED
        if not self._require_tool('nuclei'):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Vulnerability Scan...{Colors.RESET}\n")
        nuclei_bin = self.get_tool('nuclei')
        # Update templates
        confirm = self.config.get('auto_confirm', False)
        if confirm or input(f"{Colors.YELLOW}[?] Update Nuclei templates? (y/n): {Colors.RESET}").lower().strip() == 'y':
            print(f"{Colors.YELLOW}[*] Updating templates...{Colors.RESET}")
            self.run_command(f"{nuclei_bin} -ut", timeout=600, stream=False)

        nc = self.config.get('nuclei', {})
        severity = nc.get('severity', 'low,medium,high,critical')
        rl = nc.get('rate_limit', 150)
        conc = nc.get('concurrency', 25)
        jsonl_output = f"{self.output_dir}/nuclei_output.jsonl"
        txt_output = f"{self.output_dir}/nuclei_output.txt"

        cmd = (f"{nuclei_bin} -l {alive_file} -severity {severity} "
               f"-rl {rl} -c {conc} -no-color -jsonl -o {jsonl_output}")
        templates = nc.get('templates', '')
        if templates:
            cmd += f" -t {templates}"

        print(f"{Colors.YELLOW}[*] Running Nuclei...{Colors.RESET}")
        if self.run_command(cmd, timeout=3600, label="nuclei"):
            vulns = {'critical': [], 'high': [], 'medium': [], 'low': [], 'info': []}
            try:
                for line in self.read_file_lines(jsonl_output):
                    try:
                        j = json.loads(line)
                        sev = j.get('info', {}).get('severity', 'info').lower()
                        name = j.get('info', {}).get('name', 'Unknown')
                        matched = j.get('matched-at', j.get('host', 'N/A'))
                        tid = j.get('template-id', '')
                        entry = f"[{sev.upper()}] {name} | {tid} | {matched}"
                        vulns.get(sev, vulns['info']).append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception as e:
                self.logger.error(f"Nuclei parse: {e}")

            # Write human-readable txt
            with open(txt_output, 'w', encoding='utf-8') as f:
                for sev in ['critical', 'high', 'medium', 'low', 'info']:
                    for v in vulns[sev]:
                        f.write(v + "\n")

            total = sum(len(v) for v in vulns.values())
            print(f"\n{Colors.GREEN}[✔] Vulnerability scan completed{Colors.RESET}")
            print(f"\n{Colors.CYAN}[*] Vulnerability Summary:{Colors.RESET}")
            sev_colors = {'critical': Colors.RED + Colors.BOLD, 'high': Colors.RED,
                         'medium': Colors.YELLOW, 'low': Colors.GREEN, 'info': Colors.BLUE}
            for sev in ['critical', 'high', 'medium', 'low', 'info']:
                c = sev_colors[sev]
                print(f"  {c}[{sev.upper():8}] {len(vulns[sev])}{Colors.RESET}")
            print(f"  {Colors.WHITE}Total:     {total}{Colors.RESET}")

            if vulns['critical'] or vulns['high']:
                print(f"\n{Colors.RED}[!] Critical/High Findings:{Colors.RESET}")
                for v in (vulns['critical'] + vulns['high'])[:10]:
                    print(f"  {Colors.RED}• {v[:120]}{Colors.RESET}")

            self.results['vulnerabilities'] = total
            self.results['critical_vulns'] = len(vulns['critical'])
            self.results['high_vulns'] = len(vulns['high'])
            self.save_session()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] Nuclei scan failed{Colors.RESET}")
            return self.MODULE_FAILED

    # MODULE 10: PARAMETER DISCOVERY

    def run_parameter_discovery(self):
        """Discover parameters using ParamSpider + Arjun"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        has_ps = self.tools_status.get('paramspider', {}).get('installed')
        has_arjun = self.tools_status.get('arjun', {}).get('installed')
        if not has_ps and not has_arjun:
            print(f"{Colors.RED}[!] No parameter discovery tools available (need ParamSpider or Arjun).{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Parameter Discovery'] = 'No parameter discovery tools installed (paramspider, arjun)'
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Parameter Discovery...{Colors.RESET}\n")
        param_dir = f"{self.output_dir}/parameters"
        Path(param_dir).mkdir(parents=True, exist_ok=True)
        sd = self.safe_domain()

        if has_ps:
            print(f"{Colors.YELLOW}[*] Running ParamSpider...{Colors.RESET}")
            ps_bin = self.get_tool('paramspider', 'paramspider')
            if isinstance(ps_bin, str) and ps_bin.endswith('.py'):
                cmd = f"python3 {ps_bin} -d {sd}"
            else:
                cmd = f"{ps_bin} -d {sd}"
            
            # Ensure results directory exists in case ParamSpider outputs to results/ relative to cwd
            Path("results").mkdir(parents=True, exist_ok=True)
            
            if self.run_command(cmd, timeout=500, label="paramspider"):
                print(f"{Colors.GREEN}[✔] ParamSpider completed{Colors.RESET}")
                
                # Find and move the file from its default output location
                script_dir = os.path.dirname(os.path.abspath(__file__))
                potential_paths = [
                    os.path.join(os.getcwd(), "results", f"{self.domain}.txt"),
                    os.path.join(script_dir, "results", f"{self.domain}.txt"),
                    os.path.join(script_dir, "web", "backend", "results", f"{self.domain}.txt")
                ]
                found_ps_file = None
                for path in potential_paths:
                    if os.path.exists(path):
                        found_ps_file = path
                        break
                if found_ps_file:
                    shutil.move(found_ps_file, f"{param_dir}/paramspider.txt")
                    # Clean up empty directory
                    res_dir = os.path.dirname(found_ps_file)
                    try:
                        if not os.listdir(res_dir):
                            os.rmdir(res_dir)
                    except Exception:
                        pass
                else:
                    self.logger.warning("ParamSpider completed but no output file was detected in any path.")
            else:
                print(f"{Colors.RED}[!] ParamSpider failed{Colors.RESET}")

        if has_arjun:
            urls_file = f"{self.output_dir}/urls.txt"
            if os.path.exists(urls_file):
                print(f"{Colors.YELLOW}[*] Optimizing targets for Arjun active brute-force...{Colors.RESET}")
                
                alive_domains = set()
                alive_file = f"{self.output_dir}/alive.txt"
                if os.path.exists(alive_file):
                    try:
                        for line in self.read_file_lines(alive_file):
                            domain_only = self._strip_protocol(line.strip())
                            if domain_only:
                                alive_domains.add(domain_only)
                    except Exception:
                        pass
                
                arjun_targets = set()
                limit = self._config_limit('arjun', 'max_hosts', 999999)
                
                for line in self.read_file_lines(urls_file):
                    url = line.strip()
                    if not url.startswith(('http://', 'https://')):
                        continue
                    try:
                        parsed = urllib.parse.urlparse(url)
                        host_only = self._strip_protocol(parsed.netloc)
                        if self.domain not in host_only:
                            continue
                        if alive_domains and host_only not in alive_domains:
                            continue
                    except Exception:
                        continue
                    
                    if '?' in url:
                        base = url.split('?')[0]
                        arjun_targets.add(base)
                
                if not arjun_targets and os.path.exists(alive_file):
                    arjun_targets = set(self.read_file_lines(alive_file)[:limit])
                
                targets_list = list(arjun_targets)[:limit]
                if targets_list:
                    print(f"{Colors.CYAN}[*] Arjun: Scanning {len(targets_list)} targets...{Colors.RESET}")
                    arjun_bin = self.get_tool('arjun')
                    tmp_targets_file = f"{param_dir}/arjun_targets.txt"
                    with open(tmp_targets_file, 'w', encoding='utf-8') as tf:
                        for t in targets_list:
                            tf.write(t + "\n")
                    
                    cmd = f"{arjun_bin} -i {tmp_targets_file} -oJ {param_dir}/arjun.json --stable"
                    self.run_command(cmd, timeout=900, label="arjun")
                    try:
                        os.remove(tmp_targets_file)
                    except Exception:
                        pass
                else:
                    print(f"{Colors.YELLOW}[*] No suitable targets found for Arjun.{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}[*] urls.txt missing — skipping Arjun active parameters scan.{Colors.RESET}")

        final_output = f"{param_dir}/params_combined.txt"
        found = set()
        ps_file = f"{param_dir}/paramspider.txt"
        if os.path.exists(ps_file):
            for line in self.read_file_lines(ps_file):
                line = line.strip()
                if line and '=' in line:
                    found.add(line)
        arjun_file = f"{param_dir}/arjun.json"
        if os.path.exists(arjun_file):
            try:
                with open(arjun_file, 'r', encoding='utf-8') as af:
                    data = json.load(af)
                def extract_params(struct):
                    extracted = []
                    if isinstance(struct, list):
                        for item in struct:
                            if isinstance(item, str):
                                extracted.append(item)
                            elif isinstance(item, dict):
                                name = item.get("name") or item.get("parameter")
                                if name:
                                    extracted.append(str(name))
                    elif isinstance(struct, dict):
                        for k, v in struct.items():
                            extracted.append(str(k))
                    return extracted
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict):
                            url = entry.get("url")
                            if not url:
                                for k, v in entry.items():
                                    if isinstance(v, str) and v.startswith("http"):
                                        url = v
                                        break
                            if url:
                                base = url.split("?")[0]
                                params_key = entry.get("params") or entry.get("parameters") or []
                                for p in extract_params(params_key):
                                    found.add(f"{base}?{p}=FUZZ")
                elif isinstance(data, dict):
                    for url, val in data.items():
                        if not isinstance(url, str) or not url.startswith("http"):
                            continue
                        base = url.split("?")[0]
                        if isinstance(val, list):
                            for p in extract_params(val):
                                found.add(f"{base}?{p}=FUZZ")
                        elif isinstance(val, dict):
                            params_struct = val.get("params") or val.get("parameters") or val
                            for p in extract_params(params_struct):
                                found.add(f"{base}?{p}=FUZZ")
            except Exception as e:
                self.logger.error(f"Arjun merge error: {e}")
        with open(final_output, 'w', encoding='utf-8') as f:
            for p in sorted(found):
                f.write(p + "\n")
        print(f"{Colors.GREEN}[✔] Parameters discovered: {len(found)}{Colors.RESET}")
        self.results['parameters'] = len(found)
        self.save_session()
        return self.MODULE_OK

    # MODULE 11: JS ENDPOINT EXTRACTION

    def run_js_endpoint_extraction(self):
        """Extract endpoints and secrets from JS files"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        urls_file = f"{self.output_dir}/urls.txt"
        if not self._require_file(urls_file, "No URLs found! Run URL collection first."):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting JS Endpoint Extraction...{Colors.RESET}\n")
        js_dir = f"{self.output_dir}/js_endpoints"
        Path(js_dir).mkdir(parents=True, exist_ok=True)
        js_urls_file = f"{js_dir}/js_urls.txt"
        js_count = 0
        try:
            with open(js_urls_file, 'w', encoding='utf-8') as out_f:
                for line in self.read_file_lines(urls_file):
                    if line.endswith('.js') or '.js?' in line:
                        out_f.write(line + '\n')
                        js_count += 1
        except Exception as e:
            self.logger.error(f"JS filter: {e}")
            return self.MODULE_FAILED
        print(f"{Colors.YELLOW}[*] Found {js_count} JavaScript files{Colors.RESET}")
        if js_count == 0:
            merged_cariddi = self._merge_cariddi_secrets_into_js()
            if merged_cariddi:
                print(f"{Colors.GREEN}[✔] Merged {merged_cariddi} Cariddi secret findings into JS secrets{Colors.RESET}")
            return self.MODULE_OK
        if self.tools_status.get('linkfinder', {}).get('installed'):
            print(f"{Colors.YELLOW}[*] Running LinkFinder...{Colors.RESET}")
            lf_bin = self.get_tool('linkfinder', "/opt/recontools/LinkFinder/linkfinder.py")
            endpoints_output = f"{js_dir}/endpoints.txt"
            Path(endpoints_output).touch()
            # LinkFinder -i expects a single URL, not a file of URLs.
            # Loop through each JS URL individually (capped at 200) and append results.
            js_urls = self.read_file_lines(js_urls_file)[:200]
            total_endpoints = 0
            for js_url in js_urls:
                tmp_out = f"{js_dir}/_lf_tmp.txt"
                cmd = f"python3 {lf_bin} -i {shlex.quote(js_url)} -o cli"
                self.run_command(cmd, output_file=tmp_out, timeout=30, stream=False, label="linkfinder")
                if os.path.exists(tmp_out):
                    lines = self.read_file_lines(tmp_out)
                    total_endpoints += len(lines)
                    with open(endpoints_output, 'a', encoding='utf-8') as ef:
                        for ep in lines:
                            ef.write(ep + '\n')
                    try:
                        os.remove(tmp_out)
                    except Exception:
                        pass
            count = self.count_file_lines(endpoints_output)
            print(f"{Colors.GREEN}[✔] LinkFinder extracted {count} endpoints{Colors.RESET}")
            self.results['js_endpoints'] = count
        # Secret extraction
        print(f"{Colors.YELLOW}[*] Scanning JS files for secrets...{Colors.RESET}")
        secrets_file = f"{js_dir}/secrets.txt"
        secret_patterns = {
            "API Key": r"(?i)(api_key|apikey|secret|token|password)[\s]*[=:]*[\s]*['\"]([^'\"]+)['\"]",
            "AWS Key": r"(?i)AKIA[0-9A-Z]{16}",
            "Stripe": r"(?i)sk_live_[0-9a-zA-Z]{24}",
            "Google API": r"(?i)AIza[0-9A-Za-z-_]{35}",
            "Twilio SID": r"AC[a-f0-9]{32}",
            "Slack Token": r"xox[bapts]-[0-9a-zA-Z]{10,12}-[0-9a-zA-Z]{10,12}-[a-zA-Z0-9]{24}",
            "Slack Webhook": r"https://hooks\.slack\.com/services/[T][A-Z0-9_]{8}/[B][A-Z0-9_]{8}/[A-Za-z0-9_]{24}",
            "Private Key": r"-----BEGIN RSA PRIVATE KEY-----",
            "SendGrid API": r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}",
            "Firebase URL": r"https://[a-zA-Z0-9_-]+\.firebaseio\.com",
            "Database Connection": r"(mongodb|postgres|mysql|sqlite|oracle|mssql)://[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@[a-zA-Z0-9.-]+:\d+/[a-zA-Z0-9_-]+",
        }
        found_secrets = []
        # urllib.request imported at top level
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ThreadPoolExecutor(max_workers=20) as executor:
            def fetch_and_scan(url):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                        content = response.read().decode('utf-8', errors='ignore')
                        res = []
                        for name, pat in secret_patterns.items():
                            for match in re.finditer(pat, content):
                                val = match.group(2) if len(match.groups()) > 1 else match.group(0)
                                if len(val) > 8:
                                    res.append(f"{url} -> {name}: {val[:20]}***")
                        return res
                except Exception:
                    return []
            futures = {executor.submit(fetch_and_scan, url): url for url in self.read_file_lines(js_urls_file)[:500]}
            for future in as_completed(futures):
                found_secrets.extend(future.result())

        with open(secrets_file, 'w', encoding='utf-8') as f:
            for s in set(found_secrets):
                f.write(s + "\n")
        
        # Also write to js_secrets.txt to sync with frontend or specific references
        js_secrets_file = f"{js_dir}/js_secrets.txt"
        try:
            with open(js_secrets_file, 'w', encoding='utf-8') as f:
                for s in set(found_secrets):
                    f.write(s + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write js_secrets.txt: {e}")

        merged_cariddi = self._merge_cariddi_secrets_into_js()
        if merged_cariddi:
            print(f"{Colors.GREEN}[✔] Merged {merged_cariddi} Cariddi secret findings into JS secrets{Colors.RESET}")

        print(f"{Colors.GREEN}[✔] Found {self.count_file_lines(secrets_file)} potential secrets{Colors.RESET}")
        self.save_session()
        return self.MODULE_OK

    # MODULE 12: DIRECTORY FUZZING

    def _fuzz_single_host(self, host, wordlist, ext, status, depth):
        """Worker for concurrent directory fuzzing"""
        host = host if host.startswith('http') else f"http://{host}"
        safe_host = host.replace('://', '_').replace(':', '_').replace('/', '')
        out_file = f"{self.output_dir}/fuzzing/ffuf_{safe_host}.json"
        ffuf_bin = self.get_tool('ffuf')
        cmd = (f"{ffuf_bin} -w {wordlist} -u {host}/FUZZ -e {ext} "
               f"-mc {status} -recursion -recursion-depth {depth} "
               f"-t 20 -o {out_file}")
        if self.run_command(cmd, timeout=1800, label=f"ffuf:{safe_host}"):
            return out_file
        return None

    def run_directory_fuzzing(self):
        """Directory fuzzing using FFUF concurrently"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('ffuf'):
            return self.MODULE_SKIPPED
        fuzz_dir = f"{self.output_dir}/fuzzing"
        Path(fuzz_dir).mkdir(parents=True, exist_ok=True)
        hosts = self._get_hosts(prefer_alive=True)
        max_hosts = self._config_limit('ffuf', 'max_hosts', 25)
        hosts_to_scan = hosts[:max_hosts]
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Directory Fuzzing on {len(hosts_to_scan)} hosts...{Colors.RESET}\n")

        conf = self.config.get('ffuf', {})
        # Ensure each extension has a leading dot (FFUF requires .ext format)
        raw_ext = conf.get('extensions', 'php,html,js,json,txt,bak,old')
        ext = ','.join(
            e if e.startswith('.') else f'.{e}'
            for e in raw_ext.split(',')
        )
        status = conf.get('status_filter', '200,204,301,302,307,401,403')
        depth = conf.get('recursion_depth', 2)
        wordlist = self.config.get('wordlists', {}).get('dirs') or ''
        if not wordlist or not os.path.exists(wordlist):
            wordlist = self.config.get('wordlists', {}).get('dirs_fallback') or ''
        if not wordlist or not os.path.exists(wordlist):
            print(f"{Colors.RED}[!] Wordlist not found! Tried primary and fallback paths.{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Directory Fuzzing'] = 'Wordlist not found for directory fuzzing'
            return self.MODULE_SKIPPED

        fuzzed_json_files = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self._fuzz_single_host, h, wordlist, ext, status, depth): h for h in hosts_to_scan}
            for future in as_completed(futures):
                h = futures[future]
                res = future.result()
                if res and os.path.exists(res):
                    print(f"{Colors.GREEN}[✔] Fuzzing complete for {h}{Colors.RESET}")
                    fuzzed_json_files.append(res)
                else:
                    print(f"{Colors.RED}[!] Fuzzing failed for {h}{Colors.RESET}")

        # --- nomore403 Auto-feed from ffuf 403/401 results ---
        forbidden_urls = []
        for f_path in fuzzed_json_files:
            try:
                data = json.loads(Path(f_path).read_text())
                for result in data.get('results', []):
                    if result.get('status') in [403, 401]:
                        forbidden_urls.append(result.get('url', ''))
            except Exception:
                pass
        if forbidden_urls:
            forbidden_urls = list(set(forbidden_urls))[:200]
            print(f"{Colors.CYAN}[*] Auto-feeding {len(forbidden_urls)} forbidden (403/401) URLs into nomore403...{Colors.RESET}")
            nomore403_bin = self.get_tool('nomore403')
            if nomore403_bin:
                nomore403_out_dir = f"{self.output_dir}/nomore403"
                Path(nomore403_out_dir).mkdir(parents=True, exist_ok=True)
                out_file = f"{nomore403_out_dir}/bypass_results.txt"
                # Keep track of bypass count
                for url in forbidden_urls[:50]:
                    cmd = f"{nomore403_bin} -u {shlex.quote(url)} -o {out_file}"
                    self.run_command(cmd, timeout=120, label=f"nomore403:{url[:40]}")
                count = self.count_file_lines(out_file)
                self.results['bypass_403'] = count
                print(f"{Colors.GREEN}[✔] nomore403 auto-feed: {count} potential bypasses found{Colors.RESET}")

        fuzz_count = 0
        for f_path in fuzzed_json_files:
            try:
                data = json.loads(Path(f_path).read_text())
                fuzz_count += len(data.get('results', []))
            except Exception:
                pass
        self.results['fuzz_findings'] = fuzz_count

        self.save_session()
        return self.MODULE_OK

    # MODULE 13: API FUZZING

    def run_api_fuzzing(self):
        """API specific fuzzing using kr (Kiterunner)"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('kr'):
            return self.MODULE_SKIPPED
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting API Fuzzing...{Colors.RESET}\n")
        api_dir = f"{self.output_dir}/api_fuzzing"
        Path(api_dir).mkdir(parents=True, exist_ok=True)
        kr_bin = self.get_tool('kr')
        output = f"{api_dir}/kr_results.txt"
        # Kiterunner: target file is positional, wordlist via -w or Assetnote alias via -A
        kite_wordlist = "/opt/recontools/kiterunner/routes-large.kite"
        if not os.path.exists(kite_wordlist):
            kite_wordlist = "/opt/recontools/routes-large.kite"
        if os.path.exists(kite_wordlist):
            cmd = f"{kr_bin} scan {alive_file} -w {kite_wordlist} -x 5 -j 50 --fail-status-codes 400,401,404,403,501,502,503"
        else:
            # Fall back to Assetnote built-in alias
            cmd = f"{kr_bin} scan {alive_file} -A=apiroutes-210228 -x 5 -j 50 --fail-status-codes 400,401,404,403,501,502,503"
        if self.run_command(cmd, output_file=output, timeout=1200, label="kr"):
            print(f"{Colors.GREEN}[✔] API fuzzing completed{Colors.RESET}")
            self.results['api_fuzz'] = self.count_file_lines(output)
            self.save_session()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] kr scan failed or routes wordlist missing{Colors.RESET}")
            self.results['api_fuzz'] = 0
            self.save_session()
            return self.MODULE_FAILED

    # MODULE 14: SUBDOMAIN TAKEOVER CHECK

    def run_subdomain_takeover_check(self):
        """Check for subdomain takeover using subzy"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file):
            return self.MODULE_SKIPPED
        if not self._require_tool('subzy'):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Subdomain Takeovers...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/takeover"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        subzy_bin = self.get_tool('subzy')
        out_file = f"{out_dir}/takeovers.txt"
        cmd = f"{subzy_bin} run --targets {subs_file} --hide_fails"
        subzy_success = self.run_command(cmd, output_file=out_file, timeout=300, label="subzy")
        if subzy_success:
            lines = self.count_file_lines(out_file)
            print(f"{Colors.GREEN}[✔] Subzy check completed — {lines} potential issues{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] Subzy failed{Colors.RESET}")
            
        print(f"  {Colors.BLUE}[>] Running deep CNAME fallback check...{Colors.RESET}")
        cname_file = f"{out_dir}/cname_fallback.txt"
        takeovers = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            def check_cname(sub):
                try:
                    res = subprocess.run(f"dig +short CNAME {shlex.quote(sub)}", shell=True, capture_output=True, text=True, timeout=5)
                    cname = res.stdout.strip().lower()
                    if cname:
                        # Strip trailing dot for comparison
                        clean_cname = cname[:-1] if cname.endswith('.') else cname
                        if not clean_cname.endswith(self.domain.lower()):
                            return f"{sub} -> {cname}"
                except Exception:
                    pass
                return None
            futures = [executor.submit(check_cname, sub) for sub in self.read_file_lines(subs_file)]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    takeovers.append(res)
                    
        with open(cname_file, 'w', encoding='utf-8') as f:
            for t in takeovers:
                f.write(t + "\n")
                
        subzy_count = self.count_file_lines(out_file)
        self.results['takeover'] = subzy_count + len(takeovers)
        if takeovers:
            print(f"{Colors.YELLOW}[!] Found {len(takeovers)} external CNAMEs pointing outside domain!{Colors.RESET}")
        self.save_session()
        return self.MODULE_OK if subzy_success else self.MODULE_PARTIAL

    # MODULE 15: ADVANCED URL ENUMERATION (hakrawler)

    def run_advanced_url_enum(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('hakrawler'):
            return self.MODULE_SKIPPED
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Advanced URL Enum (Hakrawler)...{Colors.RESET}\n")
        out_file = f"{self.output_dir}/hakrawler.txt"
        hakrawler_bin = self.get_tool('hakrawler')
        cmd = f"cat {alive_file} | {hakrawler_bin} -d 2 -subs"
        if self.run_command(cmd, output_file=out_file, timeout=600, stream=False, label="hakrawler"):
            print(f"{Colors.GREEN}[✔] Hakrawler completed: {self.count_file_lines(out_file)} URLs{Colors.RESET}")
            self.merge_all_urls()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] Hakrawler failed{Colors.RESET}")
            return self.MODULE_FAILED

    def merge_all_urls(self):
        """Merge all URL sources into urls_final.txt"""
        sources = [
            f"{self.output_dir}/urls.txt",
            f"{self.output_dir}/hakrawler.txt",
            f"{self.output_dir}/js_endpoints/endpoints.txt"
        ]
        final = f"{self.output_dir}/urls_final.txt"
        count = self.merge_and_dedup_files(sources, final)
        self.results['urls_final'] = count
        return count

    # MODULE 16: SCREENSHOT CAPTURE (gowitness + EyeWitness)

    def _screenshot_images(self, path):
        screenshot_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        root = Path(path)
        if not root.exists():
            return []
        return [
            p for p in root.rglob('*')
            if p.is_file() and p.suffix.lower() in screenshot_exts
        ]

    def _capture_with_gowitness(self, alive_file, out_dir):
        tool = self.find_tool('gowitness')
        if not tool:
            print(f"{Colors.YELLOW}[*] gowitness not found; skipping primary screenshot pass{Colors.RESET}")
            return None

        target_dir = Path(out_dir) / 'gowitness'
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"{Colors.CYAN}[*] gowitness binary: {tool}{Colors.RESET}")
        print(f"{Colors.CYAN}[*] gowitness output: {target_dir}{Colors.RESET}")
        
        threads = self.config.get('threads', 10)
        cmd = (
            f"{shlex.quote(tool)} scan file -f {shlex.quote(alive_file)} "
            f"-s {shlex.quote(str(target_dir))} -T 15 -t {threads} "
            f"--write-jsonl --write-db"
        )
        return self.run_command(cmd, timeout=900, label='gowitness')

    def _python_has_module(self, python_bin, module_name):
        try:
            r = subprocess.run(
                [str(python_bin), "-c", f"import {module_name}"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _prepare_eyewitness_python(self, script_path):
        script_path = Path(script_path).resolve()
        eyew_root = script_path.parent.parent
        venv_python = eyew_root / 'eyewitness-venv' / 'bin' / 'python'

        # Fast path: existing venv with selenium works.
        if venv_python.exists() and self._python_has_module(venv_python, 'selenium'):
            return str(venv_python)

        print(f"{Colors.CYAN}[*] EyeWitness environment not ready; attempting auto-setup...{Colors.RESET}")

        setup_script = eyew_root / 'setup' / 'setup.sh'
        if setup_script.exists():
            for cmd in (["bash", str(setup_script)], ["sudo", "bash", str(setup_script)]):
                try:
                    r = subprocess.run(
                        cmd,
                        cwd=str(eyew_root),
                        capture_output=True,
                        text=True,
                        timeout=900,
                    )
                    if r.returncode == 0 and venv_python.exists() and self._python_has_module(venv_python, 'selenium'):
                        print(f"{Colors.GREEN}[✔] EyeWitness venv auto-setup completed{Colors.RESET}")
                        return str(venv_python)
                except Exception:
                    continue

        # Fallback: build venv manually and install requirements.
        py_req = eyew_root / 'Python' / 'requirements.txt'
        sys_python = shutil.which('python3') or sys.executable
        try:
            subprocess.run([sys_python, '-m', 'venv', str(eyew_root / 'eyewitness-venv')], capture_output=True, text=True, timeout=180)
            if venv_python.exists() and py_req.exists():
                subprocess.run([str(venv_python), '-m', 'pip', 'install', '-r', str(py_req)], capture_output=True, text=True, timeout=900)
                if self._python_has_module(venv_python, 'selenium'):
                    print(f"{Colors.GREEN}[✔] EyeWitness manual venv bootstrap completed{Colors.RESET}")
                    return str(venv_python)
        except Exception:
            pass

        # Last resort: system python if selenium is available there.
        if self._python_has_module(sys_python, 'selenium'):
            return str(sys_python)

        print(f"{Colors.YELLOW}[!] EyeWitness prerequisites missing (selenium/venv). Install with ./install.sh and retry.{Colors.RESET}")
        return None

    def _capture_with_eyewitness(self, alive_file, out_dir):
        script = self.find_tool('eyewitness')
        if not script or not os.path.isfile(script):
            print(f"{Colors.YELLOW}[*] EyeWitness not found; skipping secondary screenshot pass{Colors.RESET}")
            return None

        target_dir = Path(out_dir) / 'eyewitness'
        # EyeWitness prompts for overwrite if output dir exists at startup.
        # Remove it and keep it absent so execution remains non-interactive.
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir)
            except Exception:
                pass

        venv_python = self._prepare_eyewitness_python(script)
        if not venv_python:
            return None
        
        print(f"{Colors.CYAN}[*] EyeWitness script: {script}{Colors.RESET}")
        print(f"{Colors.CYAN}[*] EyeWitness output: {target_dir}{Colors.RESET}")
        cmd = (
            f"{shlex.quote(str(venv_python))} {shlex.quote(script)} -f {shlex.quote(alive_file)} "
            f"-d {shlex.quote(str(target_dir))} --timeout 15 --no-prompt"
        )
        
        # Calculate dynamic, scaled timeout based on number of active web domains
        target_count = 1
        if alive_file and os.path.exists(alive_file):
            target_count = max(1, self.count_file_lines(alive_file))
            
        base_timeout = 600
        per_target = 60
        timeout = min(18000, max(900, base_timeout + (target_count * per_target)))
        
        hours, remainder = divmod(timeout, 3600)
        minutes, seconds = divmod(remainder, 60)
        budget = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        print(f"{Colors.CYAN}[*] EyeWitness timeout budget: {budget} for {target_count} target(s){Colors.RESET}")

        return self.run_command(cmd, timeout=timeout, label='eyewitness')

    def run_screenshot_capture(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        alive_file = f"{self.output_dir}/alive.txt"
        has_alive = os.path.exists(alive_file) and os.path.getsize(alive_file) > 0
        if not has_alive:
            fallback_file = f"{self.output_dir}/screenshot_targets.txt"
            hosts = self._get_hosts(prefer_alive=True)
            targets = set()
            for h in hosts:
                h = h.strip()
                if not h:
                    continue
                if h.startswith('http://') or h.startswith('https://'):
                    targets.add(h)
                else:
                    targets.add(f"https://{h}")
                    targets.add(f"http://{h}")
            if not targets:
                print(f"{Colors.RED}[!] No hosts available for screenshot capture{Colors.RESET}")
                self._skip_reasons[self._current_module or 'Screenshots'] = 'No hosts available for screenshot capture'
                return self.MODULE_SKIPPED
            with open(fallback_file, 'w', encoding='utf-8') as f:
                for t in sorted(targets):
                    f.write(t + "\n")
            alive_file = fallback_file
            print(f"{Colors.YELLOW}[*] alive.txt missing; using fallback targets from discovered hosts/domain{Colors.RESET}")
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Capturing Screenshots...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/screenshots"
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        engines = [
            ("gowitness", self._capture_with_gowitness),
            ("eyewitness", self._capture_with_eyewitness),
        ]
        attempted_any = False
        engine_counts = {}
        for engine_name, runner in engines:
            print(f"{Colors.CYAN}[*] Running {engine_name}...{Colors.RESET}")
            engine_dir = Path(out_dir) / engine_name
            before = len(self._screenshot_images(engine_dir))
            result = runner(alive_file, out_dir)
            if result is not None:
                attempted_any = True
            imgs = len(self._screenshot_images(engine_dir))
            engine_counts[engine_name] = imgs
            new_imgs = max(0, imgs - before)
            if result:
                print(f"{Colors.GREEN}[✔] {engine_name} captured {imgs} screenshots in {engine_dir}{Colors.RESET}")
            elif result is None:
                print(f"{Colors.YELLOW}[!] {engine_name} unavailable; skipped{Colors.RESET}")
            elif imgs:
                print(f"{Colors.YELLOW}[!] {engine_name} exited with errors, but {imgs} screenshot files exist ({new_imgs} new){Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}[!] {engine_name} did not produce screenshots{Colors.RESET}")

        all_imgs = self._screenshot_images(out_dir)
        self.results['screenshots'] = len(all_imgs)
        self.results['screenshot_engines'] = engine_counts
        self.save_session()
        if all_imgs:
            print(f"{Colors.GREEN}[✔] Captured {len(all_imgs)} total screenshots in {out_dir}{Colors.RESET}")
            return self.MODULE_OK
        elif not attempted_any:
            print(f"{Colors.RED}[!] No screenshot engines were available{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Screenshots'] = 'No screenshot tools installed (gowitness, eyewitness)'
            return self.MODULE_SKIPPED
        else:
            print(f"{Colors.YELLOW}[!] Screenshot engines ran, but no images were found{Colors.RESET}")
            return self.MODULE_PARTIAL

    # MODULE 17: DNS BRUTEFORCE

    def run_dns_bruteforce(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('massdns'):
            return self.MODULE_SKIPPED
        resolvers = self.config.get('wordlists', {}).get('resolvers')
        if not resolvers or not os.path.exists(resolvers):
            resolvers = self.config.get('wordlists', {}).get('resolvers_fallback', '/usr/share/massdns/resolvers.txt')
        if not os.path.exists(resolvers):
            auto_resolvers = os.path.join(self.output_dir, "auto_resolvers.txt")
            print(f"{Colors.YELLOW}[*] Resolvers file not found. Generating high-performance public resolvers list...{Colors.RESET}")
            trusted_resolvers = [
                # 1. Cloudflare (Standard, Security, Family)
                "1.1.1.1", "1.0.0.1", "1.1.1.2", "1.0.0.2", "1.1.1.3", "1.0.0.3",
                # 2. Google Public DNS
                "8.8.8.8", "8.8.4.4",
                # 3. Quad9 (Filtered, Unfiltered, ECS)
                "9.9.9.9", "149.112.112.112", "9.9.9.10", "149.112.112.10", "9.9.9.11", "149.112.112.11", "9.9.9.99", "149.112.112.99",
                # 4. Cisco OpenDNS (Standard & Family)
                "208.67.222.222", "208.67.220.220", "208.67.222.220", "208.67.220.222", "208.67.220.123", "208.67.222.123",
                # 5. CenturyLink / Level3 (Legends of brute-force speed)
                "4.2.2.1", "4.2.2.2", "4.2.2.3", "4.2.2.4", "4.2.2.5", "4.2.2.6", "209.244.0.3", "209.244.0.4",
                # 6. AdGuard DNS (Standard, Family, Non-filtered)
                "94.140.14.14", "94.140.15.15", "94.140.14.15", "94.140.15.16", "94.140.14.140", "94.140.14.141",
                # 7. CleanBrowsing (Security, Family, Adult)
                "185.228.168.9", "185.228.169.9", "185.228.168.168", "185.228.169.168", "185.228.168.10", "185.228.169.11",
                # 8. Comodo Secure DNS / Sectigo
                "8.26.56.26", "8.20.247.20",
                # 9. DNS.WATCH
                "84.200.69.80", "84.200.70.40",
                # 10. Verisign Public DNS
                "64.6.64.6", "64.6.65.6",
                # 11. Neustar UltraDNS (Standard, Threat, Family)
                "156.154.70.1", "156.154.71.1", "156.154.70.2", "156.154.71.2", "156.154.70.3", "156.154.71.3", "156.154.70.4", "156.154.71.4", "156.154.70.5", "156.154.71.5",
                # 12. Freenom World
                "80.80.80.80", "80.80.81.81",
                # 13. Hurricane Electric
                "74.82.42.42",
                # 14. Yandex.DNS (Standard, Safe, Family)
                "77.88.8.8", "77.88.8.1", "77.88.8.2", "77.88.8.3", "77.88.8.7", "77.88.8.88",
                # 15. Dyn / Oracle DNS
                "216.146.35.35", "216.146.36.36",
                # 16. Control D (Uncensored, Standard)
                "76.76.2.0", "76.76.10.0", "76.76.2.1", "76.76.10.1", "76.76.2.2", "76.76.10.2", "76.76.2.3", "76.76.10.3",
                # 17. Gandi DNS
                "217.70.186.1", "217.70.186.2",
                # 18. AliDNS (Alibaba)
                "223.5.5.5", "223.6.6.6",
                # 19. NextDNS Premium Nodes
                "45.90.28.0", "45.90.30.0", "45.90.28.1", "45.90.30.1", "45.90.28.2", "45.90.30.2",
                # 20. DNS.SB
                "185.222.222.222", "45.11.45.11", "185.222.222.223", "185.222.222.9",
                # 21. OpenNIC (Decentralized, Trusted DNS Nodes)
                "193.183.98.154", "172.104.136.243", "87.98.175.85", "94.130.180.225", "185.121.177.177", "185.121.177.53", "209.141.53.53", "51.75.173.177", "185.19.105.6", "142.4.204.111", "142.4.205.47",
                # 22. Surfshark Secure DNS
                "162.252.172.57", "149.154.159.92",
                # 23. NordVPN Secure DNS
                "103.86.96.100", "103.86.99.100",
                # 24. UncensoredDNS (Denmark Premium Nodes)
                "91.239.100.100", "89.233.43.71",
                # 25. GreenTeamDNS
                "81.218.119.11", "209.88.198.133",
                # 26. CyberGhost Private DNS
                "38.132.106.139", "194.187.251.67",
                # 27. Mullvad Secure DNS
                "194.242.2.2", "194.242.2.3", "194.242.2.4", "194.242.2.9",
                # 28. FreeDNS (Premium Uncensored)
                "37.235.1.174", "37.235.1.177",
                # 29. SafeDNS
                "195.46.39.39", "195.46.39.40",
                # 30. Quad101 (Taiwan High Speed)
                "101.101.101.101", "101.102.103.104",
                # 31. UUNET / Verizon Global Backbone (Legendary speed & availability)
                "198.6.1.4", "198.6.1.5"
            ]
            try:
                with open(auto_resolvers, 'w', encoding='utf-8') as rf:
                    rf.write("\n".join(trusted_resolvers) + "\n")
                resolvers = auto_resolvers
                print(f"{Colors.GREEN}[✔] Temporary resolvers list successfully created!{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}[!] Failed to generate fallback resolvers: {e}{Colors.RESET}")
        if not self._require_file(resolvers, "Resolvers list not found!"):
            return self.MODULE_SKIPPED
        wordlist = self.config.get('wordlists', {}).get('dns')
        if not self._require_file(wordlist, "DNS wordlist not found!"):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting DNS Bruteforce...{Colors.RESET}\n")

        # --- alterx smart wordlist generation ---
        alterx_bin = self.get_tool('alterx')
        subs_file = f"{self.output_dir}/subdomains.txt"
        if alterx_bin and os.path.exists(subs_file):
            alterx_out = f"{self.output_dir}/alterx_wordlist.txt"
            print(f"{Colors.CYAN}[*] Generating smart wordlist with AlterX...{Colors.RESET}")
            cmd = f"cat {subs_file} | {alterx_bin} -enrich -limit 50000 -o {alterx_out}"
            self.run_command(cmd, timeout=300, label="alterx")

        # Generate FQDNs from wordlist (massdns needs full domain names, not bare words)
        fqdn_file = f"{self.output_dir}/massdns_fqdns.txt"
        try:
            with open(wordlist, 'r', encoding='utf-8', errors='ignore') as wf, \
                 open(fqdn_file, 'w', encoding='utf-8') as ff:
                for line in wf:
                    word = line.strip()
                    if word and not word.startswith('#'):
                        ff.write(f"{word}.{self.domain}\n")
            print(f"{Colors.YELLOW}[*] Generated FQDN list from wordlist{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to generate FQDNs: {e}{Colors.RESET}")
            return self.MODULE_FAILED
        out = f"{self.output_dir}/massdns_out.txt"
        cmd = f"{self.get_tool('massdns')} -r {resolvers} -t A -o S -w {out} {fqdn_file}"
        massdns_success = self.run_command(cmd, timeout=1200, label="massdns")
        
        new_found_massdns = 0
        if massdns_success:
            new_subs = set()
            for line in self.read_file_lines(out):
                parts = line.split()
                if parts:
                    sub = parts[0].rstrip('.')
                    if self.domain in sub:
                        new_subs.add(sub)
            if new_subs:
                subs_file = f"{self.output_dir}/subdomains.txt"
                existing = set(self.read_file_lines(subs_file))
                merged = existing | new_subs
                new_found_massdns = len(merged) - len(existing)
                with open(subs_file, 'w', encoding='utf-8') as f:
                    for s in sorted(merged):
                        f.write(s + '\n')
                self.results['dns_brute'] = new_found_massdns
                print(f"{Colors.GREEN}[✔] DNS bruteforce (massdns) — {len(new_subs)} resolved, {new_found_massdns} new subdomains added{Colors.RESET}")
            else:
                self.results['dns_brute'] = 0
                print(f"{Colors.GREEN}[✔] DNS bruteforce (massdns) completed — no new subdomains found{Colors.RESET}")
        else:
            self.results['dns_brute'] = 0
            print(f"{Colors.RED}[!] DNS bruteforce (massdns) failed{Colors.RESET}")

        # --- puredns validation ---
        puredns_bin = self.get_tool('puredns')
        if puredns_bin:
            puredns_out = f"{self.output_dir}/puredns_resolved.txt"
            target_wordlist = wordlist
            if os.path.exists(f"{self.output_dir}/alterx_wordlist.txt"):
                target_wordlist = f"{self.output_dir}/alterx_wordlist.txt"
            print(f"{Colors.CYAN}[*] Running PureDNS bruteforce with wildcard-aware resolution...{Colors.RESET}")
            cmd = (f"{puredns_bin} bruteforce {target_wordlist} {self.domain} "
                   f"-r {resolvers} -w {puredns_out} "
                   f"--wildcard-batch {self.config.get('puredns', {}).get('wildcard_batch', 1000000)} "
                   f"-l {self.config.get('puredns', {}).get('threads', 100)}")
            if self.run_command(cmd, timeout=1800, label="puredns"):
                if os.path.exists(puredns_out):
                    puredns_subs = set()
                    for line in self.read_file_lines(puredns_out):
                        sub = line.strip().lower()
                        if self.domain in sub:
                            puredns_subs.add(sub)
                    if puredns_subs:
                        subs_file = f"{self.output_dir}/subdomains.txt"
                        existing = set(self.read_file_lines(subs_file))
                        merged = existing | puredns_subs
                        new_found_puredns = len(merged) - len(existing)
                        with open(subs_file, 'w', encoding='utf-8') as f:
                            for s in sorted(merged):
                                f.write(s + '\n')
                        self.results['dns_brute'] = self.results.get('dns_brute', 0) + new_found_puredns
                        print(f"{Colors.GREEN}[✔] PureDNS resolved {len(puredns_subs)} subdomains, adding {new_found_puredns} new unique records{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] PureDNS bruteforce failed{Colors.RESET}")

        self.save_session()
        return self.MODULE_OK

    # MODULE 18: GF FILTERS

    def run_gf_filters(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('gf'):
            return self.MODULE_SKIPPED
        urls = f"{self.output_dir}/urls_final.txt"
        if not os.path.exists(urls):
            urls = f"{self.output_dir}/urls.txt"
        if not self._require_file(urls, "No URLs found!"):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Running GF Filters...{Colors.RESET}\n")
        gf_dir = f"{self.output_dir}/gf"
        Path(gf_dir).mkdir(parents=True, exist_ok=True)
        patterns = ['xss', 'sqli', 'ssrf', 'lfi', 'redirect', 'rce']
        gf_bin = self.get_tool('gf')
        res = {}
        for p in patterns:
            out = f"{gf_dir}/{p}.txt"
            cmd = f"cat {urls} | {gf_bin} {p}"
            code = self.run_command(cmd, output_file=out, timeout=120, stream=False, label=f"gf-{p}", get_code=True)
            c = self.count_file_lines(out)
            res[p] = c
            if code == 0:
                print(f"  {Colors.YELLOW}[{p.upper()}] {c} endpoints{Colors.RESET}")
            elif code == 1:
                print(f"  {Colors.BLUE}[{p.upper()}] 0 endpoints{Colors.RESET}")
            else:
                print(f"  {Colors.RED}[{p.upper()}] failed/crashed (code {code}){Colors.RESET}")
        self.results['gf_filters'] = res
        print(f"{Colors.GREEN}[✔] GF filters completed{Colors.RESET}")
        self.save_session()
        return self.MODULE_OK

    # MODULE 19: TECH SCAN (WhatWeb)

    def run_tech_scan(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('whatweb'):
            return self.MODULE_SKIPPED
        alive = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Tech Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/tech_scan"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_file = f"{out_dir}/whatweb_results.json"
        cmd = f"{self.get_tool('whatweb')} -i {alive} --log-json={out_file}"
        if self.run_command(cmd, timeout=300, label="whatweb"):
            print(f"{Colors.GREEN}[✔] WhatWeb scan completed{Colors.RESET}")
            tech_count = 0
            if os.path.exists(out_file):
                try:
                    with open(out_file, encoding='utf-8') as f:
                        data = json.load(f)
                        tech_count = len(data)
                except Exception:
                    pass
            self.results['tech_scan'] = tech_count
            self.save_session()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] WhatWeb scan failed{Colors.RESET}")
            self.results['tech_scan'] = 0
            self.save_session()
            return self.MODULE_FAILED

    # MODULE 20: SQLI SCAN (SQLMap)

    def _filter_to_alive_hosts(self, input_file, output_file):
        """Filter a URL list to only include URLs whose host is in alive.txt.
        Returns (filtered_count, original_count) tuple.
        Dead Wayback subdomains waste 90%+ of scan time on non-existent hosts."""
        alive_file = f"{self.output_dir}/alive.txt"
        alive_hosts = set()
        if os.path.exists(alive_file):
            for line in self.read_file_lines(alive_file):
                host = re.sub(r'^https?://', '', line.strip()).split(':')[0].split('/')[0].lower()
                if host:
                    alive_hosts.add(host)

        all_urls = self.read_file_lines(input_file)
        if not alive_hosts:
            # No alive.txt — can't filter, use all URLs as-is
            print(f"{Colors.YELLOW}[*] No alive.txt found — skipping host pre-filter (will test all {len(all_urls)} URLs){Colors.RESET}")
            import shutil as _shutil
            _shutil.copy2(input_file, output_file)
            return len(all_urls), len(all_urls)

        def is_alive(h):
            if h in alive_hosts:
                return True
            for ah in alive_hosts:
                if h.endswith("." + ah) or ah.endswith("." + h):
                    return True
            return False

        filtered = []
        skipped = 0
        for url in all_urls:
            try:
                parsed = urllib.parse.urlparse(url)
                host = parsed.netloc.split(':')[0].lower()
                if is_alive(host):
                    filtered.append(url)
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        with open(output_file, 'w', encoding='utf-8') as f:
            for url in filtered:
                f.write(url + '\n')

        return len(filtered), len(all_urls)

    def run_sqlmap_scan(self):
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('sqlmap'):
            return self.MODULE_SKIPPED
        gf_sqli = f"{self.output_dir}/gf/sqli.txt"
        if not self._require_file(gf_sqli, "No SQLi parameterized URLs found by GF!"):
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting SQLMap Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/sqlmap"
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        # Pre-filter to alive hosts — dead Wayback subdomains waste all scan time
        filtered_sqli = f"{out_dir}/sqli_alive.txt"
        filtered_sqli = f"{out_dir}/sqli_alive.txt"
        kept, total = self._filter_to_alive_hosts(gf_sqli, filtered_sqli)
        print(f"{Colors.GREEN}[✔] Pre-filter: {kept}/{total} SQLi URLs are on alive hosts{Colors.RESET}")
        if kept == 0:
            print(f"{Colors.YELLOW}[!] No SQLi URLs match alive hosts — running full list as fallback{Colors.RESET}")
            filtered_sqli = gf_sqli

        # --- qsreplace parameter prepping for SQLi ---
        filtered_sqli = self._run_qsreplace_to_file(
            filtered_sqli,
            f"{out_dir}/sqli_qsreplaced.txt",
            'FUZZ',
            "qsreplace:sqli",
        )

        # Use configured SQLMap settings (defaults defined in DEFAULT_CONFIG)
        sqlmap_cfg = self.config.get('sqlmap', {}) or {}
        level = int(sqlmap_cfg.get('level', 5) or 5)
        risk = int(sqlmap_cfg.get('risk', 3) or 3)
        sqlmap_threads = int(sqlmap_cfg.get('threads', self.config.get('threads', 50)) or self.config.get('threads', 50) or 50)
        # SQLMap strictly enforces a maximum of 10 threads to avoid connection issues and startup crashes
        sqlmap_threads = min(sqlmap_threads, 10)

        # Full-power SQLMap: configurable level, risk, threads, forms detection, crawl, tamper scripts
        # Timeout 7200s (2hrs) — large target lists need time to run fully
        cmd = (
            f"{self.get_tool('sqlmap')} -m {filtered_sqli} --batch --random-agent "
            f"--level {level} --risk {risk} --forms --crawl=3 --threads={sqlmap_threads} "
            f"--tamper=space2comment,between,charunicodeencode "
            f"--output-dir={out_dir}"
        )
        sqlmap_success = self.run_command(cmd, timeout=7200, label="sqlmap")
        if sqlmap_success:
            print(f"{Colors.GREEN}[✔] SQLMap scan completed{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] SQLMap scan failed{Colors.RESET}")
        sqlmap_vulns = 0
        if os.path.exists(out_dir):
            for log in Path(out_dir).rglob('log'):
                if Oculus._path_has_output(str(log)):
                    sqlmap_vulns += 1
        self.results['sqlmap'] = sqlmap_vulns
        self.save_session()
        return self.MODULE_OK if sqlmap_success else self.MODULE_FAILED


    # MODULE 21: XSS SCAN (Dalfox)

    def run_xss_scan(self):
        """Automated XSS scanning using Dalfox — pre-filtered to alive hosts"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('dalfox'):
            return self.MODULE_SKIPPED
        gf_xss = f"{self.output_dir}/gf/xss.txt"
        if not os.path.exists(gf_xss):
            self.run_gf_filters()
        if not self._require_file(gf_xss, "No XSS parameterized URLs found! Run GF filters first."):
            return self.MODULE_SKIPPED

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Automated XSS Scan (Dalfox)...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/xss_findings"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_file = f"{out_dir}/dalfox_results.txt"

        # Pre-filter to alive hosts — dead Wayback subdomains cause mass connection failures
        filtered_xss = f"{out_dir}/xss_alive.txt"
        kept, total = self._filter_to_alive_hosts(gf_xss, filtered_xss)
        print(f"{Colors.GREEN}[✔] Pre-filter: {kept}/{total} XSS URLs are on alive hosts{Colors.RESET}")
        if kept == 0:
            print(f"{Colors.YELLOW}[!] No XSS URLs match alive hosts — running full list as fallback{Colors.RESET}")
            filtered_xss = gf_xss

        # --- qsreplace parameter prepping for XSS ---
        filtered_xss = self._run_qsreplace_to_file(
            filtered_xss,
            f"{out_dir}/xss_qsreplaced.txt",
            'FUZZ',
            "qsreplace:xss",
        )

        dalfox_bin = self.get_tool('dalfox')
        # Full-power Dalfox: 100 workers, DOM mining, blind XSS callback, 15s timeout per request
        cmd = (f"{dalfox_bin} file {filtered_xss} "
               f"-b hahwul.xss.ht "
               f"--worker 100 "
               f"--timeout 15 "
               f"--delay 0 "
               f"--mining-dom "
               f"--deep-domxss "
               f"--follow-redirects "
               f"-o {out_file}")
        if self.run_command(cmd, timeout=3600, label="dalfox"):
            count = self.count_file_lines(out_file)
            print(f"{Colors.GREEN}[✔] Dalfox XSS scan completed — {count} potential findings{Colors.RESET}")
            self.results['xss_findings'] = count
            self.save_session()
            return self.MODULE_OK
        else:
            print(f"{Colors.RED}[!] Dalfox scan failed{Colors.RESET}")
            self.save_session()
            return self.MODULE_FAILED

    # MODULE 22: CORS SCANNER

    def _cors_worker(self, host):
        # urllib.request imported at top level
        host_url = host if host.startswith('http') else f"https://{host}"
        base_domain = host_url.split('://')[-1].split('/')[0]
        test_origins = [
            "https://evil.com",
            "null",
            f"https://evil{base_domain}"
        ]
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        findings = []
        for origin in test_origins:
            try:
                req = urllib.request.Request(host_url, headers={'Origin': origin, 'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    acao = resp.getheader('Access-Control-Allow-Origin')
                    acac = resp.getheader('Access-Control-Allow-Credentials')
                    if acao == origin:
                        findings.append(f"[VULN] {host_url} reflects Origin: {origin} (Credentials: {acac})")
                    elif acao == "*" and origin == "https://evil.com":
                        findings.append(f"[INFO] {host_url} wildcard CORS (Credentials: {acac})")
            except urllib.error.HTTPError as e:
                # Still check headers on error pages
                acao = e.headers.get('Access-Control-Allow-Origin')
                acac = e.headers.get('Access-Control-Allow-Credentials')
                if acao == origin:
                    findings.append(f"[VULN] {host_url} reflects Origin: {origin} (Credentials: {acac})")
            except Exception:
                pass
        return findings

    def run_cors_scan(self):
        """Multi-vector CORS misconfiguration scanner"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        hosts = self._get_hosts(prefer_alive=True)
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting CORS Scan ({len(hosts)} targets, 3 origin vectors)...{Colors.RESET}\n")
        all_results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._cors_worker, h): h for h in hosts}
            for i, future in enumerate(as_completed(futures)):
                findings = future.result()
                if findings:
                    all_results.extend(findings)
                    for r in findings:
                        color = Colors.RED if "[VULN]" in r else Colors.YELLOW
                        print(f"  {color}{r}{Colors.RESET}")
                print(f"  Progress: {i+1}/{len(hosts)}", end='\r')
        print()
        out_dir = f"{self.output_dir}/cors_findings"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        with open(f"{out_dir}/cors_results.txt", 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(r + '\n')
        vuln_count = len([r for r in all_results if '[VULN]' in r])
        warn_count = len([r for r in all_results if '[WARN]' in r])
        print(f"{Colors.GREEN}[✔] CORS Scan completed — {vuln_count} VULN, {warn_count} WARN, {len(all_results)} total findings{Colors.RESET}")
        self.results['cors_findings'] = vuln_count
        self.save_session()
        return self.MODULE_OK

    # MODULE 23: HTTP SMUGGLING

    def run_http_smuggling(self):
        """Smuggler integration for HTTP request smuggling"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('smuggler'):
            return self.MODULE_SKIPPED
        hosts = self._get_hosts(prefer_alive=True)
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting HTTP Smuggling Scan ({len(hosts)} targets)...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/smuggling"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        smuggler_bin = self.get_tool('smuggler', "/opt/recontools/smuggler/smuggler.py")
        all_results = []
        for i, host in enumerate(hosts):
            host_url = host if host.startswith('http') else f"https://{host}"
            safe_host = shlex.quote(host_url)
            out_file = f"{out_dir}/smuggler_{i}.txt"
            cmd = f"python3 {smuggler_bin} -u {safe_host} -q"
            print(f"  {Colors.YELLOW}[{i+1}/{len(hosts)}] Testing {host_url}...{Colors.RESET}")
            if self.run_command(cmd, output_file=out_file, timeout=120, stream=False, label="smuggler"):
                results = self.read_file_lines(out_file)
                if results:
                    all_results.extend(results)
                    for r in results:
                        if 'VULNERABLE' in r.upper() or 'DESYNC' in r.upper():
                            print(f"    {Colors.RED}[!] {r}{Colors.RESET}")
        # Merge all results
        final = f"{out_dir}/smuggler_results.txt"
        with open(final, 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(r + '\n')
        print(f"{Colors.GREEN}[✔] Smuggler scan completed — {len(all_results)} results across {len(hosts)} hosts{Colors.RESET}")
        self.results['smuggler'] = len(all_results)
        self.save_session()
        return self.MODULE_OK

    # MODULE 24: ASN DISCOVERY

    def run_asn_discovery(self):
        """Discover ASN and IP ranges using asnmap, with a high-fidelity Python WHOIS fallback"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        
        # Check and attempt to verify/install asnmap, but don't hard abort if it's missing
        has_asnmap = self._require_tool('asnmap')
        
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting ASN & IP Range Discovery...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/asn"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_file = f"{out_dir}/asn_ranges.txt"
        
        asnmap_bin = self.get_tool('asnmap') if has_asnmap else None
        success = False
        
        if asnmap_bin:
            sd = self.safe_domain()
            cmd = f"{asnmap_bin} -d {sd} -silent"
            success = self.run_command(cmd, output_file=out_file, timeout=300, label="asnmap")
            
        if not success:
            sd = self.safe_domain()
            print(f"{Colors.YELLOW}[*] asnmap not available or failed; launching high-fidelity BGP/WHOIS fallback...{Colors.RESET}")
            try:
                import socket
                ip = socket.gethostbyname(sd)
                print(f"  {Colors.CYAN}[+] Resolved {sd} to {ip}{Colors.RESET}")
                
                import subprocess
                import re
                whois_cmd = f"whois {shlex.quote(ip)}"
                r = subprocess.run(whois_cmd, shell=True, capture_output=True, text=True, timeout=20)
                if r.returncode == 0:
                    output = r.stdout
                    ranges = set()
                    asns = set()
                    
                    cidr_pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}\b')
                    for block in cidr_pattern.findall(output):
                        ranges.add(block)
                        
                    netrange_match = re.search(r'(?i)(NetRange|inetnum):\s*([0-9.]+)\s*-\s*([0-9.]+)', output)
                    if netrange_match and not ranges:
                        ranges.add(f"{netrange_match.group(2)} - {netrange_match.group(3)}")
                        
                    asn_match = re.findall(r'(?i)(origin|ASNumber|ASN):\s*(AS\d+|\d+)', output)
                    for item in asn_match:
                        asn_val = item[1]
                        if not asn_val.upper().startswith('AS'):
                            asn_val = f"AS{asn_val}"
                        asns.add(asn_val)
                        
                    if ranges or asns:
                        with open(out_file, 'w', encoding='utf-8') as f:
                            if asns:
                                f.write(f"# Discovered ASNs: {', '.join(sorted(asns))}\n")
                            for rng in sorted(ranges):
                                f.write(f"{rng}\n")
                        success = True
            except Exception as e:
                self.logger.error(f"ASN fallback failed: {e}")
                
        if success:
            count = self.count_file_lines(out_file)
            if count > 0:
                with open(out_file, 'r', encoding='utf-8') as f:
                    first = f.read(100)
                if '# Discovered ASNs' in first:
                    count = max(0, count - 1)
            print(f"{Colors.GREEN}[✔] ASN Discovery completed — found {count} CIDR range(s){Colors.RESET}")
            self.results['asn_ranges'] = count
            if count > 0:
                print(f"{Colors.YELLOW}[!] Use these ranges in Nmap for full attack surface scanning{Colors.RESET}")
            self.save_session()
            return self.MODULE_OK
        else:
            self.results['asn_ranges'] = 0
            print(f"{Colors.RED}[!] ASN Discovery failed{Colors.RESET}")
            self.save_session()
            return self.MODULE_FAILED

    # ORCHESTRATION: FULL AND DEEP RECON


    # MODULE 25: CLOUD ASSET DISCOVERY

    def run_cloud_asset_discovery(self):
        """Discover S3 buckets, GCP/Azure blobs associated with domain"""
        if not self._require_setup():
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Cloud Asset Discovery...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/cloud"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        # Using simple permutations for S3 bucket checking
        baseword = self.domain.split('.')[0]
        perms = [
            baseword, f"{baseword}-dev", f"{baseword}-staging",
            f"{baseword}-prod", f"{baseword}-assets", f"{baseword}-cdn",
            f"{baseword}-backup", f"{baseword}-logs", f"{baseword}-data",
        ]
        # urllib.request imported at top level
        def check_s3(name):
            url = f"https://{name}.s3.amazonaws.com"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("s3", "open", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return ("s3", "private", f"[EXISTS/PRIVATE] {url}")
            except Exception:
                pass
            return None
        def check_gcp(name):
            url = f"https://storage.googleapis.com/{name}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("gcp", "open", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return ("gcp", "private", f"[EXISTS/PRIVATE] {url}")
            except Exception:
                pass
            return None
        def check_azure(name):
            url = f"https://{name}.blob.core.windows.net"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("azure", "open", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code in (400, 403, 404):
                    return ("azure", "private", f"[EXISTS] {url}")
            except Exception:
                pass
            return None
        all_checks = [(check_s3, p) for p in perms] + [(check_gcp, p) for p in perms] + [(check_azure, p) for p in perms]
        open_buckets = []
        private_buckets = []
        with ThreadPoolExecutor(max_workers=15) as ex:
            futs = {ex.submit(fn, p): (fn.__name__, p) for fn, p in all_checks}
            for fut in as_completed(futs):
                res = fut.result()
                if res:
                    provider, access, label = res
                    if access == "open":
                        open_buckets.append(label)
                        print(f"  {Colors.RED}🔓 {label}{Colors.RESET}")
                    else:
                        private_buckets.append(label)
                        print(f"  {Colors.DIM}🔒 {label}{Colors.RESET}")

        # Write open buckets (actual findings) to canonical output file
        with open(f"{out_dir}/s3_buckets.txt", 'w', encoding='utf-8') as f:
            for b in open_buckets:
                f.write(b + '\n')
        # Write private/exists-only to separate informational file
        if private_buckets:
            with open(f"{out_dir}/cloud_exists_private.txt", 'w', encoding='utf-8') as f:
                for b in private_buckets:
                    f.write(b + '\n')

        self.results['cloud_assets'] = len(open_buckets)
        self.results['cloud_assets_private'] = len(private_buckets)
        self.save_session()

        if open_buckets:
            print(f"{Colors.GREEN}[✔] Cloud Discovery — {len(open_buckets)} OPEN buckets, {len(private_buckets)} private/exists{Colors.RESET}")
            return self.MODULE_OK
        elif private_buckets:
            print(f"{Colors.YELLOW}[~] Cloud Discovery — 0 open, {len(private_buckets)} private/exists (informational only){Colors.RESET}")
            return self.MODULE_PARTIAL
        else:
            print(f"{Colors.GREEN}[✔] Cloud Discovery — no cloud assets found{Colors.RESET}")
            return self.MODULE_OK

    # MODULE 26: GITHUB DORKING

    def run_github_dorking(self):
        """Search GitHub for leaked secrets related to domain"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        gh_token = self.config.get('api_keys', {}).get('github', '')
        if not gh_token:
            print(f"{Colors.YELLOW}[!] GitHub API token not found in config.yaml — skipping GitHub Dorking{Colors.RESET}")
            self._skip_reasons[self._current_module or 'GitHub Dorking'] = 'GitHub API token not configured in config.yaml'
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting GitHub Secret Scanning...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/github"

        headers = {'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github.v3+json'}
        query = urllib.parse.quote(f'"{self.domain}" password OR secret OR key OR token')
        url = f'https://api.github.com/search/code?q={query}&per_page=10'
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read())
                items = data.get('items', [])
                Path(out_dir).mkdir(parents=True, exist_ok=True)
                with open(f"{out_dir}/github_secrets.txt", 'w', encoding='utf-8') as f:
                    for item in items:
                        repo = item.get('repository', {}).get('full_name', '')
                        file = item.get('path', '')
                        html_url = item.get('html_url', '')
                        entry = f"Repo: {repo} | File: {file} | URL: {html_url}"
                        f.write(entry + '\n')
                        print(f"  {Colors.YELLOW}• {repo}/{file}{Colors.RESET}")
                print(f"{Colors.GREEN}[✔] Found {len(items)} potentially interesting files on GitHub{Colors.RESET}")
                self.results['github_secrets'] = len(items)
                self.save_session()
                return self.MODULE_OK
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"{Colors.RED}[!] GitHub API Rate limit exceeded or invalid token.{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] GitHub API Error: {e}{Colors.RESET}")
            return self.MODULE_FAILED
        except Exception as e:
            print(f"{Colors.RED}[!] GitHub Dorking failed: {e}{Colors.RESET}")
            return self.MODULE_FAILED

    def _sync_harvester_keys(self):
        """Sync Oculus config API keys to theHarvester's user configuration directory"""
        try:
            import yaml
            keys_dir = Path.home() / ".config" / "theHarvester"
            keys_dir.mkdir(parents=True, exist_ok=True)
            keys_path = keys_dir / "api-keys.yaml"
            
            # Load existing keys if present, else empty
            data = {}
            if keys_path.exists():
                try:
                    with open(keys_path, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh) or {}
                except Exception:
                    pass
            
            if not isinstance(data, dict) or "apikeys" not in data:
                data = {"apikeys": {}}
                
            apikeys = data["apikeys"] or {}
            
            # Map Oculus config keys to theHarvester keys
            api_keys = self.config.get("api_keys", {}) or {}
            
            # Define mappings: Oculus key name -> (Harvester key name, subkey name)
            mappings = {
                "shodan": ("shodan", "key"),
                "virustotal": ("virustotal", "key"),
                "github": ("github", "key"),
                "securitytrails": ("securityTrails", "key"),
                "chaos": ("chaos", "key"),
                "intelx": ("intelx", "key"),
            }
            
            updated = False
            for oc_key, (harv_sec, harv_key) in mappings.items():
                val = api_keys.get(oc_key, "")
                if val:
                    if harv_sec not in apikeys:
                        apikeys[harv_sec] = {}
                    if apikeys[harv_sec].get(harv_key) != val:
                        apikeys[harv_sec][harv_key] = val
                        updated = True
                        
            # Handle Censys mapping specifically (id + secret)
            censys_id = api_keys.get("censys_id", "")
            censys_sec = api_keys.get("censys_secret", "")
            if censys_id or censys_sec:
                if "censys" not in apikeys:
                    apikeys["censys"] = {}
                if censys_id and apikeys["censys"].get("id") != censys_id:
                    apikeys["censys"]["id"] = censys_id
                    updated = True
                if censys_sec and apikeys["censys"].get("secret") != censys_sec:
                    apikeys["censys"]["secret"] = censys_sec
                    updated = True
            
            if updated:
                data["apikeys"] = apikeys
                with open(keys_path, "w", encoding="utf-8") as fh:
                    yaml.safe_dump(data, fh, sort_keys=False)
                if self.logger:
                    self.logger.info(f"Synchronized API keys to {keys_path}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to sync API keys to theHarvester config: {e}")

    # MODULE 27: OSINT HARVESTING (theHarvester)

    def run_osint_harvesting(self):
        """Gather emails and OSINT using theHarvester"""
        if not self._require_setup():
            return
        if not self._require_tool('theharvester'):
            self._skip_reasons[self._current_module or 'OSINT Harvesting'] = 'theHarvester not installed'
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting OSINT Harvesting...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/osint"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        bin_path = self.get_tool('theharvester', '/opt/recontools/theHarvester/theHarvester.py')
        if not bin_path or not os.path.exists(bin_path):
            # Fallback to system command name
            bin_path = "theHarvester"
            
        out_file = f"{out_dir}/theharvester.html"
        
        # Sync configured API keys into theHarvester's configuration
        self._sync_harvester_keys()
        
        # Base keyless sources
        sources = [
            "anubis", "baidu", "certspotter", "commoncrawl", "crtsh", 
            "dnsdumpster", "duckduckgo", "dymo", "gitlab", "hackertarget", 
            "hudsonrock", "mojeek", "otx", "rapiddns", "robtex", 
            "shodanInternetDB", "subdomaincenter", "subdomainfinderc99", 
            "thc", "threatcrowd", "waybackarchive", "yahoo"
        ]
        
        # Dynamically append key-dependent sources if keys are configured in Oculus
        api_keys = self.config.get("api_keys", {}) or {}
        if api_keys.get("shodan"):
            sources.append("shodan")
        if api_keys.get("virustotal"):
            sources.append("virustotal")
        if api_keys.get("github"):
            sources.extend(["github-code", "github"])
        if api_keys.get("securitytrails"):
            sources.append("securityTrails")
        if api_keys.get("chaos"):
            sources.append("chaos")
        if api_keys.get("intelx"):
            sources.append("intelx")
        if api_keys.get("censys_id") or api_keys.get("censys_secret"):
            sources.append("censys")
            
        sources_str = ",".join(sources)
        prefix = "python3 " if isinstance(bin_path, str) and bin_path.endswith('.py') else ""
        cmd = f"{prefix}{bin_path} -d {self.safe_domain()} -b {sources_str} -f {out_file}"
        if self.run_command(cmd, timeout=600, label="harvester"):
            print(f"{Colors.GREEN}[✔] OSINT Harvesting completed{Colors.RESET}")
            self.results['osint_findings'] = 1 if os.path.exists(out_file) else 0
        else:
            print(f"{Colors.RED}[!] OSINT Harvesting failed{Colors.RESET}")
            self.results['osint_findings'] = 0
        self.save_session()

    # MODULE 28: SHODAN INTEGRATION

    def run_shodan_integration(self):
        """Passive IP/Port recon via Shodan API"""
        if not self._require_setup():
            return
        shodan_key = self.config.get('api_keys', {}).get('shodan', '')
        if not shodan_key:
            print(f"{Colors.YELLOW}[!] Shodan API key not found in config.yaml — skipping Shodan Recon{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Shodan Recon'] = 'Shodan API key not configured in config.yaml'
            return self.MODULE_SKIPPED
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Passive Shodan Recon...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/shodan"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        # urllib.request/json imported at top level
        url = f'https://api.shodan.io/shodan/host/search?key={shodan_key}&query=hostname:{self.safe_domain()}'
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read())
                matches = data.get('matches', [])
                with open(f"{out_dir}/shodan_results.txt", 'w', encoding='utf-8') as f:
                    for m in matches:
                        ip = m.get('ip_str')
                        port = m.get('port')
                        org = m.get('org', '')
                        entry = f"{ip}:{port} ({org})"
                        f.write(entry + '\n')
                        print(f"  {Colors.YELLOW}• {entry}{Colors.RESET}")
                print(f"{Colors.GREEN}[✔] Found {len(matches)} open ports via Shodan{Colors.RESET}")
                self.results['shodan_results'] = len(matches)
                self.save_session()
        except Exception as e:
            print(f"{Colors.RED}[!] Shodan API Error: {e}{Colors.RESET}")


    # MODULE 29: OPEN REDIRECT SCANNER

    def run_open_redirect_scan(self):
        """Scan for open redirects using GF filtered URLs — pre-filtered to alive hosts"""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        gf_redirect = f"{self.output_dir}/gf/redirect.txt"
        if not os.path.exists(gf_redirect):
            self.run_gf_filters()
        if not self._require_file(gf_redirect, "No redirect parameterized URLs found! Run GF filters first."):
            return self.MODULE_SKIPPED

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Open Redirect Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/redirects"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_file = f"{out_dir}/open_redirects.txt"

        # Pre-filter to alive hosts — dead subdomains produce only false negatives
        filtered_redirect = f"{out_dir}/redirect_alive.txt"
        kept, total = self._filter_to_alive_hosts(gf_redirect, filtered_redirect)
        print(f"{Colors.GREEN}[✔] Pre-filter: {kept}/{total} redirect URLs are on alive hosts{Colors.RESET}")
        src = filtered_redirect if kept > 0 else gf_redirect

        # --- qsreplace parameter prepping for Open Redirect ---
        src = self._run_qsreplace_to_file(
            src,
            f"{out_dir}/redirect_qsreplaced.txt",
            'FUZZ',
            "qsreplace:redirect",
        )

        urls = self.read_file_lines(src)
        payloads = ["https://evil.com", "//evil.com", "/\\evil.com"]
        found = []
        def check_redirect(url):
            for payload in payloads:
                # Use lambda to avoid backslash escape issues in replacement string
                target = re.sub(r'=[^&]+', lambda m: f'={payload}', url)
                try:
                    req = urllib.request.Request(
                        target,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    # Build an opener that does NOT follow redirects
                    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
                    class NoRedirect(urllib.request.HTTPRedirectHandler):
                        def redirect_request(self, *args, **kwargs):
                            return None
                    no_redir_opener = urllib.request.build_opener(NoRedirect)
                    try:
                        no_redir_opener.open(req, timeout=5)
                    except urllib.error.HTTPError as e:
                        loc = e.headers.get('Location', '')
                        if loc and ('evil.com' in loc or loc.startswith('/\\')):
                            return f"[VULN] {target} -> Location: {loc}"
                except Exception:
                    pass
            return None

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(check_redirect, u): u for u in urls}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    found.append(res)
                    print(f"  {Colors.RED}{res}{Colors.RESET}")
        
        with open(out_file, 'w', encoding='utf-8') as f:
            for r in found:
                f.write(r + '\n')
        print(f"{Colors.GREEN}[✔] Open Redirect Scan completed — {len(found)} vulnerabilities found{Colors.RESET}")
        self.results['open_redirects'] = len(found)
        self.save_session()
        return self.MODULE_OK

    def _detect_existing_data(self, key_map):
        """Check self.results for existing scan data. Returns dict of label->value for keys found."""
        return {label: self.results[key] for key, label in key_map.items() if key in self.results}

    def _warn_existing_data(self, existing, mode_name):
        """Show existing data warning and ask y/n. Returns True if user wants to continue."""
        if not existing:
            return True
        if self.config.get('auto_confirm', False):
            return True
        print(f"\n{Colors.YELLOW}[!] Existing scan data detected:{Colors.RESET}")
        parts = " | ".join(f"{k}: {v}" for k, v in existing.items())
        print(f"    {Colors.WHITE}{parts}{Colors.RESET}")
        print(f"    {Colors.YELLOW}{mode_name} will re-run all steps and overwrite this data.{Colors.RESET}")
        yn = input(f"{Colors.YELLOW}[?] Continue and overwrite? (y/n): {Colors.RESET}")
        return yn.lower().strip() == 'y'

    def run_full_automated_recon(self):
        """Run the core Oculus chain"""
        if not self._require_setup():
            return

        self.notify_scan_event(
            'scan_start',
            f"Oculus scan started: {self.domain}",
            f"Full Auto Recon started for {self.domain}",
            priority='default',
            tags=['rocket'],
            dedupe_key=f"scan_start:full_recon:{self.domain}",
        )

        core_keys = {
            'subdomains': 'Subs', 'dns_resolved': 'DNS', 'alive_hosts': 'Alive',
            'fast_ports': 'Ports', 'urls': 'URLs', 'waf_detected': 'WAF',
            'vulnerabilities': 'Vulns'
        }
        existing = self._detect_existing_data(core_keys)
        if not self._warn_existing_data(existing, "Full Auto Recon"):
            return
        # User confirmed overwrite — back up previous output first
        if existing:
            self._rotate_output_to_backup()
            self.results.clear()

        print(f"\n{Colors.MAGENTA}{Colors.BOLD}╔══════════════════════════════════════════════════════╗")
        print(f"║          STARTING FULL AUTOMATED RECON (CORE)        ║")
        print(f"╚══════════════════════════════════════════════════════╝{Colors.RESET}\n")
        steps = [
            self.run_subdomain_enumeration,
            self.run_dns_resolution,
            self.run_alive_hosts_check,
            self.run_fast_port_scan,
            self.run_url_collection,
            self.run_waf_detection,
            self.run_vulnerability_scan
        ]
        for step in steps:
            module_name = step.__name__.replace('run_', '').replace('_', ' ').title()
            previous_module = self._current_module
            self._current_module = module_name
            self.notify_scan_event(
                'module_start',
                f"Oculus module started: {module_name}",
                f"{module_name} started for {self.domain}",
                priority='low',
                tags=['play_arrow'],
                dedupe_key=f"full_recon_start:{module_name}:{self.domain}",
            )
            try:
                step()
                self._notify_module_done(module_name)
            except Exception as e:
                self._notify_module_error(module_name, str(e))
                self.logger.error(f"Auto-recon step failed: {e}")
            finally:
                self._current_module = previous_module
        self.show_diff()
        self.generate_summary()
        self.generate_html_report()
        self.generate_json_report()
        self.notify_scan_event(
            'scan_complete',
            f"Oculus scan complete: {self.domain}",
            f"Full Auto Recon completed for {self.domain}",
            priority='default',
            tags=['check'],
            dedupe_key=f"scan_complete:full_recon:{self.domain}",
        )
        print(f"\n{Colors.GREEN}{Colors.BOLD}[+] FULL AUTOMATED RECON COMPLETED!{Colors.RESET}\n")

    def run_deep_recon_mode(self):
        """Run all advanced modules"""
        if not self._require_setup():
            return

        self.notify_scan_event(
            'scan_start',
            f"Oculus scan started: {self.domain}",
            f"Deep Recon started for {self.domain}",
            priority='default',
            tags=['rocket'],
            dedupe_key=f"scan_start:deep_recon:{self.domain}",
        )

        deep_keys = {
            'parameters': 'Params', 'js_endpoints': 'JS', 'urls_final': 'URLs Final',
            'gf_filters': 'GF', 'xss_findings': 'XSS', 'cors_findings': 'CORS'
        }
        existing = self._detect_existing_data(deep_keys)

        confirm = self.config.get('auto_confirm', False)
        if not confirm:
            print(f"\n{Colors.MAGENTA}{Colors.BOLD}╔══════════════════════════════════════════════════════╗")
            print(f"║               STARTING DEEP RECON MODE               ║")
            print(f"╚══════════════════════════════════════════════════════╝{Colors.RESET}\n")
            if existing:
                print(f"{Colors.YELLOW}[!] Existing advanced scan data detected:{Colors.RESET}")
                parts = " | ".join(f"{k}: {v}" for k, v in existing.items())
                print(f"    {Colors.WHITE}{parts}{Colors.RESET}")
                print(f"    {Colors.YELLOW}Deep Recon will re-run all 14 steps and overwrite this data.{Colors.RESET}")
            yn = input(f"{Colors.YELLOW}[!] Launch Deep Recon on {self.domain}? (y/n): {Colors.RESET}")
            if yn.lower().strip() != 'y':
                return
            # Back up previous output before overwriting
            if existing:
                self._rotate_output_to_backup()
                self.results.clear()

        print(f"\n{Colors.MAGENTA}{Colors.BOLD}╔══════════════════════════════════════════════════════╗")
        print(f"║               STARTING DEEP RECON MODE               ║")
        print(f"╚══════════════════════════════════════════════════════╝{Colors.RESET}\n")
        steps = [
            self.run_asn_discovery,
            self.run_parameter_discovery,
            self.run_js_endpoint_extraction,
            self.run_directory_fuzzing,
            self.run_api_fuzzing,
            self.run_subdomain_takeover_check,
            self.run_advanced_url_enum,
            self.run_screenshot_capture,
            self.run_gf_filters,
            self.run_tech_scan,
            self.run_xss_scan,
            self.run_cors_scan,
            self.run_http_smuggling,
            self.run_sqlmap_scan
        ]
        for step in steps:
            module_name = step.__name__.replace('run_', '').replace('_', ' ').title()
            previous_module = self._current_module
            self._current_module = module_name
            self.notify_scan_event(
                'module_start',
                f"Oculus module started: {module_name}",
                f"{module_name} started for {self.domain}",
                priority='low',
                tags=['play_arrow'],
                dedupe_key=f"deep_recon_start:{module_name}:{self.domain}",
            )
            try:
                step()
                self._notify_module_done(module_name)
            except Exception as e:
                self._notify_module_error(module_name, str(e))
                self.logger.error(f"Deep recon step failed: {e}")
            finally:
                self._current_module = previous_module
        self.show_diff()
        self.generate_summary()
        self.notify_scan_event(
            'scan_complete',
            f"Oculus scan complete: {self.domain}",
            f"Deep Recon completed for {self.domain}",
            priority='default',
            tags=['check'],
            dedupe_key=f"scan_complete:deep_recon:{self.domain}",
        )
        print(f"\n{Colors.GREEN}{Colors.BOLD}[+] DEEP RECON COMPLETED!{Colors.RESET}\n")

    def run_cariddi_scan(self):
        """Module 30: Cariddi — crawl URLs for secrets, endpoints, juicy extensions."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        cariddi_bin = self.get_tool('cariddi')
        if not cariddi_bin:
            print(f"{Colors.RED}[!] cariddi not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Cariddi Scan'] = 'cariddi not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/cariddi"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return self.MODULE_SKIPPED
        
        out_txt = f"{out_dir}/cariddi_results.txt"
        out_html = f"{out_dir}/cariddi_report.html"
        
        cmd = (f"cat {alive_file} | {cariddi_bin} "
               f"-s -e -err -ext 1 -info -intensive "
               f"-c 20 -ot {out_txt} -oh {out_html}")
        self.run_command(cmd, timeout=1800, label="cariddi")
        
        count = self.count_file_lines(out_txt)
        self.results['cariddi_findings'] = count
        self.save_session()
        print(f"{Colors.GREEN}[✔] Cariddi: {count} findings{Colors.RESET}")
        return self.MODULE_OK

    def run_jaeles_scan(self):
        """Module 31: Jaeles — signature-based vulnerability scanner."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        jaeles_bin = self.get_tool('jaeles')
        if not jaeles_bin:
            print(f"{Colors.RED}[!] jaeles not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Jaeles Scan'] = 'jaeles not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/jaeles"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return self.MODULE_SKIPPED
        
        # Reload/sync signatures first
        self.run_command(f"{jaeles_bin} config reload --signDir ~/.jaeles", timeout=120, label="jaeles:reload")
        
        conc = self.config.get('jaeles', {}).get('concurrency', 20)
        custom_sigs = self.config.get('jaeles', {}).get('signatures', '')
        sig_flag = f"-s {custom_sigs}" if custom_sigs else ""
        
        hosts = self.read_file_lines(alive_file)
        max_hosts = self.config.get('jaeles', {}).get('max_hosts', 100)
        jaeles_success = True
        for host in hosts[:max_hosts]:
            cmd = (f"{jaeles_bin} scan -u {shlex.quote(host)} "
                   f"{sig_flag} -c {conc} "
                   f"-o {out_dir} --no-output-url -v")
            if not self.run_command(cmd, timeout=600, label=f"jaeles:{host[:40]}"):
                jaeles_success = False
        
        results_count = sum(1 for f in Path(out_dir).rglob('*.txt') if f.stat().st_size > 0)
        self.results['jaeles_findings'] = results_count
        self.save_session()
        print(f"{Colors.GREEN}[✔] Jaeles: {results_count} findings{Colors.RESET}")
        return self.MODULE_OK if jaeles_success else self.MODULE_FAILED

    def run_tplmap_scan(self):
        """Module 32: Tplmap — Server-Side Template Injection scanner (safe detection)."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        tplmap_path = self.find_tool('tplmap')
        if not tplmap_path:
            print(f"{Colors.RED}[!] tplmap not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'Tplmap Scan'] = 'tplmap not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/tplmap"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        ssti_candidates = []
        for gf_pattern in ['ssrf', 'rce', 'ssti']:
            gf_file = f"{self.output_dir}/gf/{gf_pattern}.txt"
            if os.path.exists(gf_file):
                ssti_candidates.extend(self.read_file_lines(gf_file))
        
        if not ssti_candidates:
            urls_file = f"{self.output_dir}/urls_final.txt"
            if os.path.exists(urls_file):
                for url in self.read_file_lines(urls_file):
                    if any(p in url.lower() for p in ['template', 'render', 'view', 'page', 'name=', 'input=']):
                        ssti_candidates.append(url)
        
        max_urls = self._config_limit('tplmap', 'max_urls', 999999)
        ssti_candidates = list(set(ssti_candidates))[:max_urls]
        if not ssti_candidates:
            print(f"{Colors.YELLOW}[!] No SSTI candidate URLs found.{Colors.RESET}")
            self.results['ssti_findings'] = 0
            self.save_session()
            return self.MODULE_OK
        
        findings = 0
        out_file = f"{out_dir}/tplmap_results.txt"
        open(out_file, 'w', encoding='utf-8').close()
        tplmap_success = True
        for url in ssti_candidates:
            # Safe detection only - no --os-cmd execution to avoid target bans
            temp_log = f"{out_dir}/tplmap_temp.log"
            cmd = f"python3 {tplmap_path} -u {shlex.quote(url)} --level 5"
            if self.run_command(cmd, output_file=temp_log, timeout=120, label=f"tplmap:{url[:40]}"):
                if os.path.exists(temp_log):
                    try:
                        with open(temp_log, 'r', encoding='utf-8', errors='ignore') as lf:
                            content = lf.read()
                        if any(marker in content for marker in ["vulnerable", "[+]", "Engine:", "Injection"]):
                            with open(out_file, 'a', encoding='utf-8') as f:
                                f.write(f"[DETECTED] {url}\n")
                            findings += 1
                    except Exception as e:
                        self.logger.error(f"Error parsing tplmap log: {e}")
                    try:
                        os.remove(temp_log)
                    except OSError:
                        pass
            else:
                tplmap_success = False
        
        self.results['ssti_findings'] = findings
        self.save_session()
        print(f"{Colors.GREEN}[✔] Tplmap: tested {len(ssti_candidates)} URLs, found {findings} vulnerabilities{Colors.RESET}")
        return self.MODULE_OK if tplmap_success else self.MODULE_PARTIAL

    def run_crlfuzz_scan(self):
        """Module 33: CRLFuzz — CRLF injection vulnerability scanner."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        crlfuzz_bin = self.get_tool('crlfuzz')
        if not crlfuzz_bin:
            print(f"{Colors.RED}[!] crlfuzz not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'CRLFuzz Scan'] = 'crlfuzz not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/crlfuzz"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return self.MODULE_SKIPPED
        
        conc = self.config.get('crlfuzz', {}).get('concurrency', 25)
        out_file = f"{out_dir}/crlfuzz_results.txt"
        
        cmd = (f"{crlfuzz_bin} -l {alive_file} "
               f"-c {conc} -s -o {out_file}")
        crlfuzz_success = self.run_command(cmd, timeout=1200, label="crlfuzz")
        
        count = self.count_file_lines(out_file)
        self.results['crlf_findings'] = count
        self.save_session()
        print(f"{Colors.GREEN}[✔] CRLFuzz: {count} CRLF injection findings{Colors.RESET}")
        return self.MODULE_OK if crlfuzz_success else self.MODULE_FAILED

    def run_internetdb_scan(self):
        """Module 34: InternetDB — zero-auth Shodan passive port/vuln lookup."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/internetdb"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        dns_file = f"{self.output_dir}/dns_resolved.txt"
        ips = set()
        if os.path.exists(dns_file):
            for line in self.read_file_lines(dns_file):
                parts = line.split()
                for part in parts:
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', part):
                        ips.add(part)
        
        if not ips:
            try:
                for info in socket.getaddrinfo(self.domain, None):
                    ip = info[4][0]
                    if ':' not in ip:
                        ips.add(ip)
            except Exception:
                pass
        
        if not ips:
            print(f"{Colors.YELLOW}[!] No IPs found for InternetDB lookup{Colors.RESET}")
            self.results['internetdb_hosts'] = 0
            self.save_session()
            return self.MODULE_SKIPPED
        
        print(f"{Colors.CYAN}[*] Querying InternetDB for {len(ips)} IPs...{Colors.RESET}")
        results_all = []
        out_file = f"{out_dir}/internetdb_results.json"
        
        def lookup_ip(ip):
            return (ip, self._internetdb_lookup(ip))
        
        max_ips = self._config_limit('internetdb', 'max_ips', 999999)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(lookup_ip, ip): ip for ip in list(ips)[:max_ips]}
            for future in as_completed(futures):
                ip, data = future.result()
                if data and data.get('ports'):
                    results_all.append(data)
        
        with open(out_file, 'w') as f:
            json.dump(results_all, f, indent=2)
        
        self.results['internetdb_hosts'] = len(results_all)
        self.save_session()
        print(f"{Colors.GREEN}[✔] InternetDB: {len(results_all)} hosts with data{Colors.RESET}")
        return self.MODULE_OK

    def run_nikto_scan(self):
        """Module 35: Nikto — comprehensive web server vulnerability scanner."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        if not self._require_tool('nikto'):
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/nikto"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        max_hosts = self._config_limit('nikto', 'max_hosts', 999999)
        hosts = self._get_hosts()[:max_hosts]
        if not hosts:
            self.results['nikto_scanned'] = 0
            self.save_session()
            return self.MODULE_SKIPPED
        
        tuning = self.config.get('nikto', {}).get('tuning', '1234')
        timeout = self.config.get('nikto', {}).get('timeout', 600)
        
        nikto_success = True
        for host in hosts:
            safe_host = re.sub(r'[^A-Za-z0-9_.-]+', '_', self._strip_protocol(host))
            # Use txt format as a safer fallback to avoid missing JSON plugin issues
            out_txt = f"{out_dir}/nikto_{safe_host}.txt"
            
            cmd = (f"nikto -h {shlex.quote(host)} "
                   f"-Tuning {tuning} "
                   f"-Format txt -o {out_txt} "
                   f"-Display 1234VP -timeout 15 -nolookup")
            if not self.run_command(cmd, timeout=timeout, label=f"nikto:{host[:40]}"):
                nikto_success = False
        
        total = sum(1 for f in Path(out_dir).glob('*.txt') if f.stat().st_size > 0)
        self.results['nikto_scanned'] = total
        self.save_session()
        print(f"{Colors.GREEN}[✔] Nikto scan completed — {total} hosts scanned{Colors.RESET}")
        return self.MODULE_OK if nikto_success else self.MODULE_FAILED

    def run_tlsx_scan(self):
        """Module 36: TLSX — TLS certificate scanning + SAN subdomain discovery."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        tlsx_bin = self.get_tool('tlsx')
        if not tlsx_bin:
            print(f"{Colors.RED}[!] tlsx not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'TLSX Scan'] = 'tlsx not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/tlsx"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        hosts = self._get_hosts()
        if not hosts:
            self.results['tlsx_sans'] = 0
            self.save_session()
            return self.MODULE_SKIPPED
        
        hosts_file = f"{out_dir}/tlsx_input.txt"
        with open(hosts_file, 'w') as f:
            for h in hosts:
                f.write(self._strip_protocol(h) + '\n')
        
        out_json = f"{out_dir}/tlsx_results.json"
        out_sans = f"{out_dir}/tlsx_sans.txt"
        
        # Expanded port list to include 9443 and other important ports
        cmd = (f"{tlsx_bin} -l {hosts_file} -p 80,443,8000,8080,8081,8443,4443,9443,8888 "
               f"-san -cn -json -resp-only -silent -o {out_json}")
        tlsx_success = self.run_command(cmd, timeout=600, label="tlsx")
        
        new_subs = set()
        if os.path.exists(out_json):
            for line in self.read_file_lines(out_json):
                try:
                    data = json.loads(line)
                    for san in data.get('san', []):
                        san = san.strip().lower()
                        if self.domain in san and '*' not in san:
                            new_subs.add(san)
                    cn = data.get('cn', '').strip().lower()
                    if cn and self.domain in cn and '*' not in cn:
                        new_subs.add(cn)
                except Exception:
                    pass
        
        if new_subs:
            with open(out_sans, 'w') as f:
                f.write('\n'.join(sorted(new_subs)) + '\n')
            subs_file = f"{self.output_dir}/subdomains.txt"
            existing = set(self.read_file_lines(subs_file))
            merged = existing | new_subs
            added = len(merged) - len(existing)
            with open(subs_file, 'w') as f:
                f.write('\n'.join(sorted(merged)) + '\n')
            self.results['tlsx_sans'] = len(new_subs)
            self.save_session()
            print(f"{Colors.GREEN}[✔] TLSX: {len(new_subs)} SANs found, {added} new subdomains added{Colors.RESET}")
            return self.MODULE_OK
        else:
            self.results['tlsx_sans'] = 0
            self.save_session()
            print(f"{Colors.GREEN}[✔] TLSX: scan complete, no new SANs{Colors.RESET}")
            return self.MODULE_OK if tlsx_success else self.MODULE_FAILED

    def run_nomore403_scan(self):
        """Module 37: nomore403 — 403/401 Forbidden bypass scanner."""
        if not self._require_setup():
            return self.MODULE_SKIPPED
        nomore403_bin = self.get_tool('nomore403')
        if not nomore403_bin:
            print(f"{Colors.RED}[!] nomore403 not installed{Colors.RESET}")
            self._skip_reasons[self._current_module or 'nomore403 Scan'] = 'nomore403 not installed'
            return self.MODULE_SKIPPED
        out_dir = f"{self.output_dir}/nomore403"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        forbidden_urls = []
        ffuf_dir = Path(f"{self.output_dir}/fuzzing")
        if ffuf_dir.exists():
            for f in ffuf_dir.rglob('*.json'):
                try:
                    data = json.loads(f.read_text())
                    for result in data.get('results', []):
                        if result.get('status') in [403, 401]:
                            forbidden_urls.append(result.get('url', ''))
                except Exception:
                    pass
        
        if not forbidden_urls:
            fallback_hosts = self._config_limit('nomore403', 'fallback_hosts', 999999)
            hosts = self._get_hosts()[:fallback_hosts]
            admin_paths = ['/admin', '/wp-admin', '/administrator', '/dashboard',
                           '/api', '/config', '/internal', '/management']
            for host in hosts:
                for path in admin_paths:
                    forbidden_urls.append(f"{host.rstrip('/')}{path}")
        
        max_urls = self._config_limit('nomore403', 'max_urls', 999999)
        forbidden_urls = list(set(forbidden_urls))[:max_urls]
        if not forbidden_urls:
            print(f"{Colors.YELLOW}[!] No 403 URLs to test{Colors.RESET}")
            self.results['bypass_403'] = 0
            self.save_session()
            return self.MODULE_SKIPPED
        
        main_out = f"{out_dir}/bypass_results.txt"
        open(main_out, 'w', encoding='utf-8').close()
        nomore_success = True
        for idx, url in enumerate(forbidden_urls):
            temp_out = f"{out_dir}/temp_nomore403_{idx}.txt"
            cmd = f"{nomore403_bin} -u {shlex.quote(url)} -o {temp_out}"
            if self.run_command(cmd, timeout=120, label=f"nomore403:{url[:40]}"):
                if os.path.exists(temp_out):
                    try:
                        lines = self.read_file_lines(temp_out)
                        if lines:
                            with open(main_out, 'a', encoding='utf-8') as f:
                                f.write(f"--- RESULTS FOR: {url} ---\n")
                                for l in lines:
                                    f.write(l + '\n')
                                f.write("\n")
                    except Exception as e:
                        self.logger.error(f"Error merging nomore403 temp output: {e}")
                    try:
                        os.remove(temp_out)
                    except OSError:
                        pass
            else:
                nomore_success = False
        
        count = 0
        if os.path.exists(main_out):
            for line in self.read_file_lines(main_out):
                if "by-pass" in line.lower() or "bypass" in line.lower() or "200 ok" in line.lower():
                    count += 1
        
        self.results['bypass_403'] = count
        self.save_session()
        print(f"{Colors.GREEN}[✔] nomore403: {count} potential bypasses found{Colors.RESET}")
        return self.MODULE_OK if nomore_success else self.MODULE_FAILED

    def run_full_spectrum_scan(self, force_fresh=False):
        """Run every single Oculus module in perfect dependency order with concurrency where safe.
        Supports smart resume: if previous data exists, user can skip completed steps.
        """
        if not self._require_setup():
            return
        
        # Initialize abort_requested flag for Web API
        self.abort_requested = getattr(self, 'abort_requested', False)

        # Detect existing scan data
        scan_keys = {
            'subdomains': 'Subs', 'dns_brute': 'DNS Brute', 'dns_resolved': 'DNS',
            'alive_hosts': 'Alive', 'fast_ports': 'Fast Ports', 'full_ports': 'Full Ports',
            'urls': 'URLs', 'urls_final': 'URLs Final', 'waf_detected': 'WAF',
            'whatwaf_findings': 'WhatWaf',
            'vulnerabilities': 'Vulns', 'parameters': 'Params',
            'js_endpoints': 'JS', 'gf_filters': 'GF',
            'xss_findings': 'XSS', 'cors_findings': 'CORS',
            'cariddi_findings': 'Cariddi', 'jaeles_findings': 'Jaeles',
            'ssti_findings': 'SSTI', 'crlf_findings': 'CRLF',
            'internetdb_hosts': 'InternetDB', 'nikto_scanned': 'Nikto',
            'tlsx_sans': 'TLSX', 'bypass_403': '403 Bypass'
        }
        existing = self._detect_existing_data(scan_keys)
        skip_completed = False

        if existing:
            if force_fresh:
                skip_completed = False
                self.results.clear()
                self._prev_results = {}
                print(f"{Colors.YELLOW}[*] Force fresh scan — previous result counters cleared.{Colors.RESET}")
            elif self.config.get('auto_confirm', False):
                skip_completed = True  # CI / Web default: resume without prompting
            else:
                parts = " | ".join(f"{k}: {v}" for k, v in existing.items())
                print(f"\n{Colors.YELLOW}[!] Existing scan data detected for {self.domain}:{Colors.RESET}")
                print(f"    {Colors.WHITE}{parts}{Colors.RESET}")
                print(f"\n    {Colors.CYAN}[1]{Colors.RESET} Resume  -- skip completed steps, continue from where it stopped")
                print(f"    {Colors.CYAN}[2]{Colors.RESET} Fresh   -- re-run everything from scratch (overwrites data)")
                print(f"    {Colors.CYAN}[3]{Colors.RESET} Cancel")
                choice = input(f"\n{Colors.YELLOW}[?] Choose (1/2/3): {Colors.RESET}").strip()
                if choice == '1':
                    skip_completed = True
                elif choice == '2':
                    skip_completed = False
                    # Rotate old output to backup-<domain>/ so data is never lost
                    self._rotate_output_to_backup()
                    self.results.clear()
                    self._prev_results = {}
                    print(f"{Colors.YELLOW}[*] Fresh scan — previous data backed up to backup-{self.domain}/.{Colors.RESET}")
                else:
                    return
        else:
            if not self.config.get('auto_confirm', False):
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}")
                print(f"  FULL SPECTRUM SCAN will run ALL 36 modules across 5 phases.")
                print(f"  Estimated runtime: 2-6 hours depending on target size.")
                print(f"{Colors.RESET}")
                yn = input(f"{Colors.YELLOW}[!] Launch Full Spectrum Scan on {self.domain}? (y/n): {Colors.RESET}")
                if yn.lower().strip() != 'y':
                    return

        self.notify_scan_event(
            'scan_start',
            f"Oculus scan started: {self.domain}",
            f"Full Spectrum started for {self.domain}",
            priority='default',
            tags=['rocket'],
            dedupe_key=f"scan_start:full_spectrum:{self.domain}",
        )

        start_time = time.time()
        mode_label = "RESUME" if skip_completed else "FULL"

        print(f"\n{Colors.MAGENTA}{Colors.BOLD}")
        print(f"======================================================================")
        print(f"   FULL SPECTRUM SCAN [{mode_label}] -- {self.domain}")
        print(f"======================================================================")
        print(f"{Colors.RESET}\n")

        # Thread-safe tracking lists
        _lock = threading.Lock()
        self.failed_modules = []
        self.completed_modules = []
        skipped_steps = []
        aborted = False

        def _step_already_done(result_key=None, marker_files=None):
            """Resume: skip if results key exists or non-empty output artifacts exist."""
            if not skip_completed:
                return False, None
            if result_key and result_key in self.results:
                return True, self.results[result_key]
            if marker_files and self.output_dir:
                for rel in marker_files:
                    p = os.path.join(self.output_dir, rel)
                    if Oculus._path_has_output(p):
                        return True, rel
            return False, None

        def _run_step(name, func, result_key=None, marker_files=None):
            """Run a single step with skip-check, error handling, and thread-safe tracking."""
            nonlocal aborted
            if aborted or getattr(self, 'abort_requested', False):
                return
            done, hint = _step_already_done(result_key, marker_files)
            if done:
                print(f"\n{Colors.BLUE}[SKIP] {name} -- already completed ({hint}){Colors.RESET}")
                with _lock:
                    skipped_steps.append(name)
                    self.completed_modules.append(name)
                self._notify_ntfy(
                    'skip',
                    f"⏩ Oculus resumed: {name}",
                    f"[RESUMED] {name} for {self.domain or 'target'}\nAlready completed in prior session ({hint}). Skipping re-run.",
                    priority='min',
                    tags=['fast_forward'],
                    dedupe_key=f"skip:{name}:{hint}",
                )
                return
            try:
                previous_module = self._current_module
                self._current_module = name
                self._notify_module_start(name)
                print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}")
                print(f"  STEP: {name}")
                print(f"{'='*60}{Colors.RESET}")
                result_status = func()

                # --- Route based on module return status ---
                if result_status == self.MODULE_SKIPPED:
                    reason = self._skip_reasons.get(name, 'precondition not met')
                    print(f"{Colors.YELLOW}[SKIP] {name} — {reason}{Colors.RESET}")
                    with _lock:
                        self.skipped_modules.append(name)
                    self._notify_module_done(name, result_key=result_key,
                                             marker_files=marker_files, status=self.MODULE_SKIPPED)
                elif result_status == self.MODULE_PARTIAL:
                    print(f"{Colors.YELLOW}[~] {name} — partial results{Colors.RESET}")
                    with _lock:
                        self.completed_modules.append(name)
                    self._notify_module_done(name, result_key=result_key,
                                             marker_files=marker_files, status=self.MODULE_PARTIAL)
                elif result_status == self.MODULE_FAILED:
                    print(f"{Colors.RED}[✘] {name} — module reported failure{Colors.RESET}")
                    with _lock:
                        self.failed_modules.append((name, 'module returned failure'))
                    self._notify_module_done(name, result_key=result_key,
                                             marker_files=marker_files, status=self.MODULE_FAILED)
                else:
                    # MODULE_OK or None (backward-compatible)
                    self._notify_module_done(name, result_key=result_key,
                                             marker_files=marker_files, status=self.MODULE_OK)
                    with _lock:
                        self.completed_modules.append(name)

            except KeyboardInterrupt:
                with _lock:
                    aborted = True
                print(f"\n{Colors.YELLOW}[!] Ctrl+C detected during: {name} -- aborting pipeline{Colors.RESET}")
            except Exception as e:
                with _lock:
                    self.failed_modules.append((name, str(e)))
                self.logger.error(f"Full Spectrum step failed [{name}]: {e}")
                self._notify_module_error(name, str(e))
                print(f"{Colors.RED}[!] STEP FAILED: {name} -- {e}{Colors.RESET}")
            finally:
                self._current_module = previous_module

        def step(name, func, result_key=None, marker_files=None):
            """Queue one sequential step (keyword args — no positional None)."""
            _run_step(name, func, result_key=result_key, marker_files=marker_files)

        def cstep(name, func, result_key=None, marker_files=None):
            """Build one concurrent step spec as a dict."""
            return {
                'name': name,
                'func': func,
                'result_key': result_key,
                'marker_files': marker_files,
            }

        def _run_concurrent(step_list):
            """Run multiple steps concurrently (each entry from cstep())."""
            nonlocal aborted
            if aborted or getattr(self, 'abort_requested', False):
                return
            if not self.config.get('parallel', True) or len(step_list) <= 1:
                for spec in step_list:
                    if aborted or getattr(self, 'abort_requested', False):
                        break
                    _run_step(
                        spec['name'], spec['func'],
                        result_key=spec.get('result_key'),
                        marker_files=spec.get('marker_files'),
                    )
                return

            names = ', '.join(spec['name'] for spec in step_list)
            print(f"\n{Colors.CYAN}[*] Running {len(step_list)} tasks concurrently: {names}{Colors.RESET}")
            with ThreadPoolExecutor(max_workers=len(step_list)) as executor:
                futures = {}
                for spec in step_list:
                    futures[executor.submit(
                         _run_step,
                         spec['name'],
                         spec['func'],
                         spec.get('result_key'),
                         spec.get('marker_files'),
                    )] = spec['name']
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        pass  # Already handled inside _run_step

        try:
            # PHASE 1: DISCOVERY
            self.current_phase = "Phase 1/5: Discovery"
            print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 1/5: DISCOVERY ---{Colors.RESET}")

            step("Subdomain Enumeration", self.run_subdomain_enumeration, result_key="subdomains")
            step("DNS Bruteforce", self.run_dns_bruteforce, result_key="dns_brute",
                 marker_files=["massdns_out.txt"])
            step("DNS Resolution", self.run_dns_resolution, result_key="dns_resolved")
            step("Alive Hosts Check", self.run_alive_hosts_check, result_key="alive_hosts")
            subs_before_tlsx = set(self.read_file_lines(f"{self.output_dir}/subdomains.txt"))
            step("TLS Certificate Scan", self.run_tlsx_scan, result_key="tlsx_sans")
            subs_after_tlsx = set(self.read_file_lines(f"{self.output_dir}/subdomains.txt"))
            tlsx_new_subs = subs_after_tlsx - subs_before_tlsx
            if tlsx_new_subs and not aborted and not getattr(self, 'abort_requested', False):
                print(f"\n{Colors.CYAN}[*] TLSX added {len(tlsx_new_subs)} new subdomains; refreshing DNS and alive hosts for this run...{Colors.RESET}")
                self.results.pop('dns_resolved', None)
                self.results.pop('alive_hosts', None)
                step("DNS Resolution (TLSX refresh)", self.run_dns_resolution, result_key="dns_resolved")
                step("Alive Hosts Check (TLSX refresh)", self.run_alive_hosts_check, result_key="alive_hosts")

            _run_concurrent([
                cstep("ASN Discovery", self.run_asn_discovery, marker_files=["asn/asn_ranges.txt"]),
                cstep("Cloud Asset Discovery", self.run_cloud_asset_discovery,
                      marker_files=["cloud/s3_buckets.txt"]),
                cstep("OSINT Harvesting", self.run_osint_harvesting,
                      marker_files=["osint/theharvester.html"]),
                cstep("Shodan Recon", self.run_shodan_integration,
                      marker_files=["shodan/shodan_results.txt"]),
                cstep("GitHub Dorking", self.run_github_dorking,
                      marker_files=["github/github_secrets.txt"]),
            ])

            self.save_session()

            # PHASE 2: INFRASTRUCTURE
            if not aborted and not getattr(self, 'abort_requested', False):
                self.current_phase = "Phase 2/5: Infrastructure"
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 2/5: INFRASTRUCTURE ---{Colors.RESET}")

                # Start Nmap and Nikto in background threads concurrently if not already completed
                nmap_done, _ = _step_already_done("full_ports", ["ports_full.txt"])
                if nmap_done:
                    print(f"\n{Colors.BLUE}[SKIP] Full Port Scan (Nmap) -- already completed{Colors.RESET}")
                    self.completed_modules.append("Full Port Scan")
                else:
                    self._nmap_thread = threading.Thread(target=self.run_full_port_scan, daemon=True)
                    self._nmap_thread.start()
                    self.logger.info("[*] Full Port Scan (Nmap) started in background.")

                nikto_done, _ = _step_already_done("nikto_scanned", ["nikto/"])
                if nikto_done:
                    print(f"\n{Colors.BLUE}[SKIP] Nikto Web Server Scan -- already completed{Colors.RESET}")
                    self.completed_modules.append("Nikto Scanner")
                else:
                    self._nikto_thread = threading.Thread(target=self.run_nikto_scan, daemon=True)
                    self._nikto_thread.start()
                    self.logger.info("[*] Web Server Scan (Nikto) started in background.")

                _run_concurrent([
                    cstep("Fast Port Scan", self.run_fast_port_scan, result_key="fast_ports"),
                    cstep("Tech Scan", self.run_tech_scan,
                          marker_files=["tech_scan/whatweb_results.json"]),
                    cstep("WAF Detection", self.run_waf_detection, result_key="waf_detected"),
                    cstep("Screenshot Capture", self.run_screenshot_capture, marker_files=["screenshots"]),
                    cstep("InternetDB Lookup", self.run_internetdb_scan, result_key="internetdb_hosts"),
                ])

                self.save_session()

            # PHASE 3: CONTENT DISCOVERY
            if not aborted and not getattr(self, 'abort_requested', False):
                self.current_phase = "Phase 3/5: Content Discovery"
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 3/5: CONTENT DISCOVERY ---{Colors.RESET}")

                step("URL Collection", self.run_url_collection, result_key="urls")
                step("Advanced URL Enum", self.run_advanced_url_enum, result_key="urls_final")

                # Start Cariddi scan in the background if not already done
                cariddi_done, _ = _step_already_done("cariddi_findings", ["cariddi/cariddi_results.txt"])
                if cariddi_done:
                    print(f"\n{Colors.BLUE}[SKIP] Cariddi Crawl -- already completed{Colors.RESET}")
                    self.completed_modules.append("Cariddi Scan")
                else:
                    self._cariddi_thread = threading.Thread(target=self.run_cariddi_scan, daemon=True)
                    self._cariddi_thread.start()
                    self.logger.info("[*] URL Crawl (Cariddi) started in background.")

                _run_concurrent([
                    cstep("Parameter Discovery", self.run_parameter_discovery, result_key="parameters"),
                    cstep("JS Endpoint Extraction", self.run_js_endpoint_extraction,
                          result_key="js_endpoints"),
                ])

                step("Subdomain Takeover Check", self.run_subdomain_takeover_check,
                     marker_files=["takeover/takeovers.txt", "takeover/cname_fallback.txt"])

                self.save_session()

            # PHASE 4: VULNERABILITY ANALYSIS
            if not aborted and not getattr(self, 'abort_requested', False):
                self.current_phase = "Phase 4/5: Vulnerability Analysis"
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 4/5: VULNERABILITY ANALYSIS ---{Colors.RESET}")

                step("Vulnerability Scan (Nuclei)", self.run_vulnerability_scan, result_key="vulnerabilities")
                step("GF Filters", self.run_gf_filters, result_key="gf_filters")

                # Start Jaeles scan in the background if not already completed
                jaeles_done, _ = _step_already_done("jaeles_findings", ["jaeles/"])
                if jaeles_done:
                    print(f"\n{Colors.BLUE}[SKIP] Jaeles Vuln Scan -- already completed{Colors.RESET}")
                    self.completed_modules.append("Jaeles Scan")
                else:
                    self._jaeles_thread = threading.Thread(target=self.run_jaeles_scan, daemon=True)
                    self._jaeles_thread.start()
                    self.logger.info("[*] Vulnerability Scan (Jaeles) started in background.")

                _run_concurrent([
                    cstep("Directory Fuzzing", self.run_directory_fuzzing, marker_files=["fuzzing"]),
                    cstep("API Fuzzing", self.run_api_fuzzing, marker_files=["api_fuzzing"]),
                ])

                self.save_session()

            # PHASE 5: TARGETED EXPLOITATION
            if not aborted and not getattr(self, 'abort_requested', False):
                self.current_phase = "Phase 5/5: Targeted Exploitation"
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 5/5: TARGETED EXPLOITATION ---{Colors.RESET}")

                _run_concurrent([
                    cstep("SQLi Scan", self.run_sqlmap_scan, marker_files=["sqlmap"]),
                    cstep("XSS Scan (Dalfox)", self.run_xss_scan, result_key="xss_findings"),
                    cstep("Open Redirect Scan", self.run_open_redirect_scan, marker_files=["redirects"]),
                    cstep("CRLF Injection (CRLFuzz)", self.run_crlfuzz_scan, result_key="crlf_findings"),
                    cstep("SSTI Scan (Tplmap)", self.run_tplmap_scan, result_key="ssti_findings"),
                    cstep("403 Bypass (nomore403)", self.run_nomore403_scan, result_key="bypass_403"),
                ])

                _run_concurrent([
                    cstep("CORS Scanner", self.run_cors_scan, result_key="cors_findings"),
                    cstep("HTTP Smuggling", self.run_http_smuggling, marker_files=["smuggling"]),
                ])

                self.save_session()

        except KeyboardInterrupt:
            aborted = True
            print(f"\n{Colors.YELLOW}[!] Scan aborted by user (Ctrl+C){Colors.RESET}")
            
        if getattr(self, 'abort_requested', False):
            aborted = True
            print(f"\n{Colors.YELLOW}[!] Scan aborted via API request{Colors.RESET}")
            
        # Join/wait for all background tasks
        for thread_attr, tool_name, module_name in [
            ('_nmap_thread', 'Nmap', 'Full Port Scan'),
            ('_nikto_thread', 'Nikto', 'Nikto Scanner'),
            ('_cariddi_thread', 'Cariddi', 'Cariddi Scan'),
            ('_jaeles_thread', 'Jaeles', 'Jaeles Scan')
        ]:
            if not aborted and hasattr(self, thread_attr):
                t = getattr(self, thread_attr)
                if t.is_alive():
                    msg = f"[*] Waiting for background {tool_name} scan to finish..."
                    print(f"\n{Colors.CYAN}{msg}{Colors.RESET}")
                    self.logger.info(msg)
                    t.join()
                    self.logger.info(f"[✔] Background {tool_name} scan completed.")
                result_key = {
                    'Full Port Scan': 'full_ports',
                    'Nikto Scanner': 'nikto_scanned',
                    'Cariddi Scan': 'cariddi_findings',
                    'Jaeles Scan': 'jaeles_findings',
                }.get(module_name)
                self._notify_module_done(module_name, result_key=result_key)
                if module_name == "Cariddi Scan":
                    merged_cariddi = self._merge_cariddi_secrets_into_js()
                    if merged_cariddi:
                        print(f"{Colors.GREEN}[✔] Merged {merged_cariddi} late Cariddi secret findings into JS reports{Colors.RESET}")
                if module_name not in self.completed_modules:
                    self.completed_modules.append(module_name)
                self.save_session()

        # FINAL: REPORTING (always runs, even on abort)
        duration = int(time.time() - start_time)
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s"

        self.show_diff()
        try:
            self.generate_summary(duration=duration)
            self.generate_html_report()
            self.generate_json_report()
            self.generate_markdown_report()
            self.notify_scan_event(
                'scan_complete',
                f"Oculus scan complete: {self.domain}",
                f"Full Spectrum completed for {self.domain}",
                priority='default',
                tags=['check'],
                dedupe_key=f"scan_complete:full_spectrum:{self.domain}",
            )
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")

        # Final Summary
        status = "ABORTED" if aborted else "COMPLETED"
        color = Colors.YELLOW if aborted else Colors.GREEN
        print(f"\n{color}{Colors.BOLD}")
        print(f"======================================================================")
        print(f"   FULL SPECTRUM SCAN {status} -- {self.domain}")
        print(f"======================================================================{Colors.RESET}")
        print(f"\n  {Colors.WHITE}Duration    : {duration_str}{Colors.RESET}")
        print(f"  {Colors.GREEN}Completed   : {len(self.completed_modules) - len(skipped_steps)} steps run{Colors.RESET}")
        if skipped_steps:
            print(f"  {Colors.BLUE}Resumed     : {len(skipped_steps)} steps skipped (already completed){Colors.RESET}")
        if self.failed_modules:
            print(f"  {Colors.RED}Failed      : {len(self.failed_modules)} steps{Colors.RESET}")
            for name, err in self.failed_modules:
                print(f"    {Colors.RED}- {name}: {err[:80]}{Colors.RESET}")
        print(f"  {Colors.CYAN}Output Dir  : {self.output_dir}/{Colors.RESET}")
        print(f"  {Colors.CYAN}Reports     : HTML, JSON, Markdown{Colors.RESET}")
        print()


    # ═══════════════════════════════════════════════════════════════
    #  REPORTING — SUMMARY / HTML / JSON / MARKDOWN
    # ═══════════════════════════════════════════════════════════════

    def generate_summary(self, duration=None):
        """Generate comprehensive text summary"""
        summary_file = f"{self.output_dir}/summary.txt"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"                        OCULUS v{VERSION} SUMMARY REPORT\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Target Domain: {self.domain}\n")
                f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if duration:
                    f.write(f"Total Duration: {duration} seconds\n")
                f.write(f"Output Directory: {self.output_dir}\n\n")
                f.write("-" * 80 + "\n")
                f.write("                           DISCOVERY RESULTS\n")
                f.write("-" * 80 + "\n\n")
                
                # Check WAF details
                waf_d = self.results.get('waf_detected', 0)
                waf_t = self.results.get('waf_total', 0)
                waf_str = f"{waf_d}/{waf_t}" if waf_t > 0 else "0"

                metrics = [
                    ('Subdomains Discovered', 'subdomains', f'{self.output_dir}/subdomains.txt'),
                    ('DNS Bruteforce Checked', 'dns_brute', f'{self.output_dir}/massdns_out.txt'),
                    ('DNS Records Resolved', 'dns_resolved', f'{self.output_dir}/dns_resolved.txt'),
                    ('Alive Hosts Found', 'alive_hosts', f'{self.output_dir}/alive.txt'),
                    ('TLS Certificate SANs', 'tlsx_sans', f'{self.output_dir}/tlsx/tlsx_sans.txt'),
                    ('Open Ports (Fast)', 'fast_ports', f'{self.output_dir}/ports_fast.txt'),
                    ('Service Details (Full)', 'full_ports', f'{self.output_dir}/ports_full.txt'),
                    ('Tech Scan Results', 'tech_scan', f'{self.output_dir}/tech_scan/whatweb_results.json'),
                    ('WAF Protected Hosts', 'waf_detected', ''),
                    ('WhatWaf Findings', 'whatwaf_findings', f'{self.output_dir}/whatwaf/whatwaf_results.txt'),
                    ('InternetDB Hosts', 'internetdb_hosts', f'{self.output_dir}/internetdb/internetdb_results.json'),
                    ('Nikto Scanned Hosts', 'nikto_scanned', f'{self.output_dir}/nikto/'),
                    ('Screenshot Capture', 'screenshots', f'{self.output_dir}/screenshots/'),
                    ('ASN IP Ranges', 'asn_ranges', f'{self.output_dir}/asn/asn_ranges.txt'),
                    ('URLs Collected', 'urls', f'{self.output_dir}/urls.txt'),
                    ('Advanced URLs Enum', 'urls_final', f'{self.output_dir}/urls_final.txt'),
                    ('JS Endpoints', 'js_endpoints', f'{self.output_dir}/js_endpoints/endpoints.txt'),
                    ('Parameters Discovered', 'parameters', f'{self.output_dir}/parameters/parameters_final.txt'),
                    ('Directory Fuzz Findings', 'fuzz_findings', f'{self.output_dir}/fuzzing/'),
                    ('API Endpoints Fuzzed', 'api_fuzz', f'{self.output_dir}/api_fuzzing/'),
                    ('Cariddi Findings', 'cariddi_findings', f'{self.output_dir}/cariddi/cariddi_results.txt'),
                    ('Cloud Assets', 'cloud_assets', f'{self.output_dir}/cloud/s3_buckets.txt'),
                    ('Leaked Secrets (GitHub)', 'github_secrets', f'{self.output_dir}/github/github_secrets.txt'),
                    ('OSINT Harvesting', 'osint_findings', f'{self.output_dir}/osint/theharvester.html'),
                    ('Shodan Recon', 'shodan_results', f'{self.output_dir}/shodan/shodan_results.txt'),
                    ('Vulnerabilities (Nuclei)', 'vulnerabilities', f'{self.output_dir}/nuclei_output.jsonl'),
                    ('Jaeles Vulns', 'jaeles_findings', f'{self.output_dir}/jaeles/'),
                    ('XSS Findings', 'xss_findings', f'{self.output_dir}/xss_findings/'),
                    ('SQLMap Findings', 'sqlmap', f'{self.output_dir}/sqlmap/'),
                    ('Open Redirect Vulns', 'open_redirects', f'{self.output_dir}/redirects/open_redirects.txt'),
                    ('SSTI Vulns (tplmap)', 'ssti_findings', f'{self.output_dir}/tplmap/tplmap_results.txt'),
                    ('CRLF Vulns (crlfuzz)', 'crlf_findings', f'{self.output_dir}/crlfuzz/crlfuzz_results.txt'),
                    ('403 Bypasses (nomore403)', 'bypass_403', f'{self.output_dir}/nomore403/bypass_results.txt'),
                    ('CORS Findings', 'cors_findings', f'{self.output_dir}/cors_findings/'),
                    ('HTTP Smuggling', 'smuggler', f'{self.output_dir}/smuggling/smuggler_results.txt'),
                    ('Takeover Findings', 'takeover', f'{self.output_dir}/takeover/'),
                ]
                for label, key, path in metrics:
                    val = self.results.get(key, 0)
                    if key == 'waf_detected':
                        f.write(f"{label}: {waf_str}\n")
                    else:
                        f.write(f"{label}: {val}\n")
                    if val and path:
                        f.write(f"  • {path}\n")

                # Vulns summary breakdown
                vulns = self.results.get('vulnerabilities', 0)
                if vulns:
                    f.write(f"\nVulnerability Details:\n")
                    f.write(f"  • Critical: {self.results.get('critical_vulns', 0)}\n")
                    f.write(f"  • High: {self.results.get('high_vulns', 0)}\n")
                # GF
                gf = self.results.get('gf_filters', {})
                if gf:
                    f.write("\nGF Findings:\n")
                    for k, v in gf.items():
                        f.write(f"  • {k.upper()}: {v}\n")
                f.write("\n" + "-" * 80 + "\n")
                f.write("                            TOOL STATUS\n")
                f.write("-" * 80 + "\n\n")
                for tool, status in self.tools_status.items():
                    sym = "✔" if status.get('installed') else "✘"
                    f.write(f"{sym} {tool.capitalize()}\n")
                f.write("\n" + "=" * 80 + "\n")
            print(f"\n{Colors.GREEN}[✔] Summary: {summary_file}{Colors.RESET}")
            # Print quick stats
            print(f"\n{Colors.CYAN}{Colors.BOLD}[*] RECON SUMMARY:{Colors.RESET}")
            for label, key, _ in metrics[:8]:
                val = self.results.get(key, 0)
                if key == 'waf_detected':
                    print(f"  {Colors.WHITE}• {label}: {waf_str}{Colors.RESET}")
                elif val:
                    print(f"  {Colors.WHITE}• {label}: {val}{Colors.RESET}")
        except Exception as e:
            self.logger.error(f"Summary generation: {e}")

    def generate_html_report(self):
        """Generate enhanced dark-themed HTML report with charts and sortable tables"""
        if not self._require_setup():
            return
        report_path = f"{self.output_dir}/report.html"
        print(f"\n{Colors.CYAN}[*] Generating HTML report...{Colors.RESET}")
        
        # Collect data
        subs = self.read_file_lines(f"{self.output_dir}/subdomains.txt")
        dns_brute = self.read_file_lines(f"{self.output_dir}/massdns_out.txt")
        dns_resolved = self.read_file_lines(f"{self.output_dir}/dns_resolved.txt")
        alive = self.read_file_lines(f"{self.output_dir}/alive.txt")
        ports = self.read_file_lines(f"{self.output_dir}/ports_full.txt")
        if not ports:
            ports = self.read_file_lines(f"{self.output_dir}/ports_fast.txt")
        params = self.read_file_lines(f"{self.output_dir}/parameters/parameters_final.txt")
        urls = self.read_file_lines(f"{self.output_dir}/urls_final.txt")
        asn_ranges = self.read_file_lines(f"{self.output_dir}/asn/asn_ranges.txt")
        js_endpoints = self.read_file_lines(f"{self.output_dir}/js_endpoints/endpoints.txt")
        
        dalfox = self.read_file_lines(f"{self.output_dir}/xss_findings/dalfox_results.txt")
        cors = self.read_file_lines(f"{self.output_dir}/cors_findings/cors_results.txt")
        takeovers = self.read_file_lines(f"{self.output_dir}/takeover/takeovers.txt")
        smuggler = self.read_file_lines(f"{self.output_dir}/smuggling/smuggler_results.txt")
        s3_buckets = self.read_file_lines(f"{self.output_dir}/cloud/s3_buckets.txt")
        github_secrets = self.read_file_lines(f"{self.output_dir}/github/github_secrets.txt")
        shodan_results = self.read_file_lines(f"{self.output_dir}/shodan/shodan_results.txt")
        open_redirects = self.read_file_lines(f"{self.output_dir}/redirects/open_redirects.txt")
        whatwaf = self.read_file_lines(f"{self.output_dir}/whatwaf/whatwaf_results.txt")
        
        cariddi = self.read_file_lines(f"{self.output_dir}/cariddi/cariddi_results.txt")
        tplmap = self.read_file_lines(f"{self.output_dir}/tplmap/tplmap_results.txt")
        crlfuzz = self.read_file_lines(f"{self.output_dir}/crlfuzz/crlfuzz_results.txt")
        nomore403 = self.read_file_lines(f"{self.output_dir}/nomore403/bypass_results.txt")
        tlsx = self.read_file_lines(f"{self.output_dir}/tlsx/tlsx_sans.txt")
        
        # Parse FFUF directory fuzzing JSONs
        fuzz_endpoints = []
        fuzz_dir = Path(f"{self.output_dir}/fuzzing")
        if fuzz_dir.exists():
            for json_file in fuzz_dir.glob('ffuf_*.json'):
                try:
                    data = json.loads(json_file.read_text(encoding='utf-8'))
                    for res in data.get('results', []):
                        fuzz_endpoints.append(f"[{res.get('status')}] {res.get('url')}")
                except Exception:
                    pass

        # OSINT report link
        osint_report = []
        if os.path.exists(f"{self.output_dir}/osint/theharvester.html"):
            osint_report.append(f'<a href="osint/theharvester.html" target="_blank" style="color: #00ffcc; text-decoration: underline;">View theHarvester HTML Report</a>')

        internetdb = []
        idb_path = Path(f"{self.output_dir}/internetdb/internetdb_results.json")
        if idb_path.exists():
            try:
                idb_data = json.loads(idb_path.read_text(encoding='utf-8'))
                for host in idb_data:
                    ip = host.get('ip', '')
                    ports_list = ', '.join(str(p) for p in host.get('ports', []))
                    cpes = ', '.join(host.get('cpes', []))
                    vulns_list = ', '.join(host.get('vulns', []))
                    internetdb.append(f"IP: {ip} | Ports: {ports_list} | CPEs: {cpes} | Vulns: {vulns_list}")
            except Exception:
                pass

        jaeles = []
        jaeles_dir = Path(f"{self.output_dir}/jaeles")
        if jaeles_dir.exists():
            for txt_file in jaeles_dir.rglob('*.txt'):
                jaeles.extend(self.read_file_lines(str(txt_file)))

        nikto = []
        nikto_dir = Path(f"{self.output_dir}/nikto")
        if nikto_dir.exists():
            for txt_file in nikto_dir.glob('*.txt'):
                nikto.extend(self.read_file_lines(str(txt_file)))
        
        sqlmap = []
        sqlmap_dir = Path(f"{self.output_dir}/sqlmap")
        if sqlmap_dir.exists():
            for log in sqlmap_dir.rglob('log'):
                sqlmap.extend(self.read_file_lines(str(log)))
        
        vulns_file = f"{self.output_dir}/nuclei_output.jsonl"
        vulns = []
        sev_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        if os.path.exists(vulns_file):
            for line in self.read_file_lines(vulns_file):
                try:
                    j = json.loads(line)
                    vulns.append(j)
                    sev = j.get('info', {}).get('severity', 'info').lower()
                    if sev in sev_counts:
                        sev_counts[sev] += 1
                except Exception:
                    pass
                    
        screenshots_dir = Path(f"{self.output_dir}/screenshots")
        screenshot_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        screenshots = []
        if screenshots_dir.exists():
            screenshots = [
                img for img in sorted(screenshots_dir.rglob('*'))
                if img.is_file() and img.suffix.lower() in screenshot_exts
            ]

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oculus Report — {self.domain}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#e0e0e0;font-family:'Courier New',monospace;padding:20px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{color:#00ffcc;font-size:28px;border-bottom:2px solid #00ffcc;padding-bottom:10px;margin-bottom:20px;display:flex;align-items:center}}
h2{{color:#00aaff;font-size:20px;margin:25px 0 10px;display:flex;align-items:center}}
.card{{background:#12121a;border:1px solid #1a1a2e;border-radius:8px;padding:15px;margin:5px 0 15px}}
.stat{{display:inline-block;background:#1a1a2e;border-radius:6px;padding:12px 20px;margin:5px;text-align:center;min-width:150px}}
.stat .num{{font-size:24px;font-weight:bold;color:#00ffcc}}
.stat .label{{font-size:11px;color:#888;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th{{background:#1a1a2e;color:#00aaff;padding:8px;text-align:left;font-size:12px;cursor:pointer}}
th:hover{{background:#2a2a3e}}
td{{padding:6px 8px;border-bottom:1px solid #1a1a2e;font-size:12px;word-break:break-all}}
tr:hover{{background:#1a1a2e}}
.critical{{color:#ff4444;font-weight:bold}} .high{{color:#ff8800}} .medium{{color:#ffcc00}} .low{{color:#44cc44}} .info{{color:#4488ff}}
details{{margin:6px 0}}
summary{{cursor:pointer;color:#00aaff;padding:10px 14px;font-weight:bold;background:#12121a;border:1px solid #1a1a2e;border-radius:6px;display:flex;align-items:center;list-style:none;transition:background 0.15s ease,color 0.15s ease}}
summary::-webkit-details-marker{{display:none}}
summary:hover{{background:#1a1a2e;color:#00ffcc}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.gallery a{{display:block;background:#0f0f18;border:1px solid #1a1a2e;border-radius:10px;overflow:hidden;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}}
.gallery a:hover{{border-color:#00ffcc;transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,255,204,.12)}}
.gallery img{{width:100%;height:100%;max-height:240px;object-fit:cover;display:block}}
.chart-container{{width:400px;margin:0 auto;padding:20px}}
.footer{{text-align:center;padding:30px 0;margin-top:60px;border-top:1px solid #1a1a2e;color:#555;font-size:11px;letter-spacing:1px}}
.icon-inline{{width:16px;height:16px;margin-right:10px;flex-shrink:0}}
.title-icon{{width:24px;height:24px;color:#00ffcc;margin-right:12px;flex-shrink:0}}
</style></head><body><div class="container">
<h1><i data-lucide="shield" class="title-icon"></i> Oculus v{VERSION} — {self.domain}</h1>
<p style="color:#666">Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<div style="margin:20px 0;text-align:center;">
<div class="stat"><div class="num">{len(subs)}</div><div class="label">Subdomains</div></div>
<div class="stat"><div class="num">{len(alive)}</div><div class="label">Alive Hosts</div></div>
<div class="stat"><div class="num">{self.results.get('fast_ports',0)}</div><div class="label">Open Ports</div></div>
<div class="stat"><div class="num">{len(urls)}</div><div class="label">URLs</div></div>
<div class="stat"><div class="num">{len(vulns)}</div><div class="label">Vulnerabilities</div></div>
<div class="stat"><div class="num">{self.results.get('xss_findings',0)}</div><div class="label">XSS</div></div>
<div class="stat"><div class="num">{self.results.get('cors_findings',0)}</div><div class="label">CORS</div></div>
</div>"""

        if vulns:
            html += f"""
<div class="card chart-container">
    <canvas id="vulnChart"></canvas>
</div>
<script>
new Chart(document.getElementById('vulnChart'), {{
    type: 'doughnut',
    data: {{
        labels: ['Critical', 'High', 'Medium', 'Low', 'Info'],
        datasets: [{{
            data: [{sev_counts['critical']}, {sev_counts['high']}, {sev_counts['medium']}, {sev_counts['low']}, {sev_counts['info']}],
            backgroundColor: ['#ff4444', '#ff8800', '#ffcc00', '#44cc44', '#4488ff'],
            borderWidth: 0
        }}]
    }},
    options: {{ plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }} }}
}});
</script>"""

            html += """<h2><i data-lucide="shield-alert" class="icon-inline" style="color:#ff4444"></i> Vulnerabilities</h2><div class="card">
<table id="vulnTable">
<thead><tr><th onclick="sortTable(0)">Severity ↕</th><th onclick="sortTable(1)">Name ↕</th><th onclick="sortTable(2)">Template ↕</th><th onclick="sortTable(3)">Matched At ↕</th></tr></thead>
<tbody>"""
            for v in sorted(vulns, key=lambda x: {'critical':0, 'high':1, 'medium':2, 'low':3, 'info':4}.get(x.get('info',{}).get('severity','info').lower(), 5)):
                sev = v.get('info',{}).get('severity','info').lower()
                html += f'<tr><td class="{sev}">{sev.upper()}</td><td>{v.get("info",{}).get("name","")}</td><td>{v.get("template-id","")}</td><td>{v.get("matched-at","")[:80]}</td></tr>'
            html += """</tbody></table></div>
<script>
function sortTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("vulnTable"); switching = true; dir = "asc"; 
  while (switching) {
    switching = false; rows = table.rows;
    for (i = 1; i < (rows.length - 1); i++) {
      shouldSwitch = false;
      x = rows[i].getElementsByTagName("TD")[n]; y = rows[i + 1].getElementsByTagName("TD")[n];
      if (dir == "asc") { if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) { shouldSwitch = true; break; } } 
      else if (dir == "desc") { if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) { shouldSwitch = true; break; } }
    }
    if (shouldSwitch) { rows[i].parentNode.insertBefore(rows[i + 1], rows[i]); switching = true; switchcount ++; } 
    else { if (switchcount == 0 && dir == "asc") { dir = "desc"; switching = true; } }
  }
}
</script>"""

        if screenshots:
            html += f'<details><summary><i data-lucide="image" class="icon-inline"></i> Screenshots ({len(screenshots)})</summary><div class="card gallery">'
            for img in screenshots[:50]:
                rel_img = str(img.relative_to(screenshots_dir)).replace(os.sep, '/')
                rel_path = f"screenshots/{rel_img}"
                html += f'<a href="{rel_path}" target="_blank"><img src="{rel_path}" loading="lazy" alt="Screenshot"></a>'
            if len(screenshots) > 50:
                html += f'<p>... and {len(screenshots)-50} more in screenshots/ directory</p>'
            html += '</div></details>'

        sections = [
            ("Subdomains", "globe", subs, 200),
            ("DNS Bruteforce", "search", dns_brute, 200),
            ("DNS Records Resolved", "search", dns_resolved, 200),
            ("Alive Hosts", "activity", alive, 200),
            ("Open Ports", "plug", ports, 200),
            ("URLs", "link", urls, 200),
            ("Parameters", "file-text", params, 200),
            ("JS Endpoints", "terminal", js_endpoints, 200),
            ("ASN IP Ranges", "network", asn_ranges, 200),
            ("Cross-Site Scripting (XSS)", "code", dalfox, 200),
            ("SQL Injections", "database", sqlmap, 200),
            ("Subdomain Takeovers", "flag", takeovers, 200),
            ("CORS Misconfigurations", "refresh-cw", cors, 200),
            ("HTTP Smuggling", "shield-alert", smuggler, 200),
            ("Cloud Buckets / Assets", "cloud", s3_buckets, 200),
            ("Leaked Secrets (GitHub)", "key", github_secrets, 200),
            ("Shodan Host Intelligence", "radar", shodan_results, 200),
            ("OSINT Harvesting", "users", osint_report, 200),
            ("Open Redirects", "external-link", open_redirects, 200),
            ("WhatWaf WAF Intelligence", "shield", whatwaf, 200),
            ("Directory Fuzzing", "folder", fuzz_endpoints, 200),
            ("Cariddi Crawl Findings", "link-2", cariddi, 200),
            ("Jaeles Vulnerabilities", "shield-alert", jaeles, 200),
            ("SSTI Vulnerabilities (Tplmap)", "cpu", tplmap, 200),
            ("CRLF Vulnerabilities (CRLFuzz)", "alert-triangle", crlfuzz, 200),
            ("InternetDB Passive Lookup", "database", internetdb, 200),
            ("Nikto Web Server Scan", "server", nikto, 200),
            ("TLS Certificate SANs", "lock", tlsx, 200),
            ("403 Bypasses (nomore403)", "unlock", nomore403, 200)
        ]
        
        for title, icon, data, limit in sections:
            if data:
                try:
                    html += f'<details><summary><i data-lucide="{icon}" class="icon-inline"></i> {title} ({len(data)})</summary><div class="card">'
                    for item in data[:limit]:
                        html += f'{item}<br>'
                    if len(data) > limit:
                        html += f'<br><i>... and {len(data)-limit} more</i>'
                    html += '</div></details>'
                except Exception as e:
                    self.logger.error(f"Error appending HTML section {title}: {e}")

        html += f'<div class="footer">Generated by Oculus v{VERSION}</div></div><script>lucide.createIcons();</script></body></html>'
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"{Colors.GREEN}[✔] Enhanced HTML report: {report_path}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to write HTML report: {e}{Colors.RESET}")

    def generate_json_report(self):
        """Generate machine-readable JSON report"""
        if not self._require_setup():
            return
        
        ports = self.read_file_lines(f"{self.output_dir}/ports_full.txt")
        if not ports:
            ports = self.read_file_lines(f"{self.output_dir}/ports_fast.txt")
            
        sqlmap = []
        sqlmap_dir = Path(f"{self.output_dir}/sqlmap")
        if sqlmap_dir.exists():
            for log in sqlmap_dir.rglob('log'):
                sqlmap.extend(self.read_file_lines(str(log)))

        jaeles = []
        jaeles_dir = Path(f"{self.output_dir}/jaeles")
        if jaeles_dir.exists():
            for txt_file in jaeles_dir.rglob('*.txt'):
                jaeles.extend(self.read_file_lines(str(txt_file)))

        nikto = []
        nikto_dir = Path(f"{self.output_dir}/nikto")
        if nikto_dir.exists():
            for txt_file in nikto_dir.glob('*.txt'):
                nikto.extend(self.read_file_lines(str(txt_file)))

        # Parse FFUF directory fuzzing JSONs
        fuzz_endpoints = []
        fuzz_dir = Path(f"{self.output_dir}/fuzzing")
        if fuzz_dir.exists():
            for json_file in fuzz_dir.glob('ffuf_*.json'):
                try:
                    data = json.loads(json_file.read_text(encoding='utf-8'))
                    for res in data.get('results', []):
                        fuzz_endpoints.append(f"[{res.get('status')}] {res.get('url')}")
                except Exception:
                    pass

        # Capture screenshots list
        screenshots_dir = Path(f"{self.output_dir}/screenshots")
        screenshot_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        screenshots_list = []
        if screenshots_dir.exists():
            screenshots_list = [
                str(img.relative_to(self.output_dir)).replace(os.sep, '/')
                for img in sorted(screenshots_dir.rglob('*'))
                if img.is_file() and img.suffix.lower() in screenshot_exts
            ]

        report = {
            'domain': self.domain,
            'version': VERSION,
            'scan_date': datetime.now().isoformat(),
            'results': self.results,
            'subdomains': self.read_file_lines(f"{self.output_dir}/subdomains.txt"),
            'dns_brute': self.read_file_lines(f"{self.output_dir}/massdns_out.txt"),
            'dns_resolved': self.read_file_lines(f"{self.output_dir}/dns_resolved.txt"),
            'alive_hosts': self.read_file_lines(f"{self.output_dir}/alive.txt"),
            'open_ports': ports,
            'urls': self.read_file_lines(f"{self.output_dir}/urls_final.txt")[:1000],
            'parameters': self.read_file_lines(f"{self.output_dir}/parameters/parameters_final.txt")[:1000],
            'js_endpoints': self.read_file_lines(f"{self.output_dir}/js_endpoints/endpoints.txt")[:1000],
            'asn_ranges': self.read_file_lines(f"{self.output_dir}/asn/asn_ranges.txt"),
            'xss_findings': self.read_file_lines(f"{self.output_dir}/xss_findings/dalfox_results.txt"),
            'sql_injections': sqlmap,
            'takeovers': self.read_file_lines(f"{self.output_dir}/takeover/takeovers.txt"),
            'cors': self.read_file_lines(f"{self.output_dir}/cors_findings/cors_results.txt"),
            'smuggler': self.read_file_lines(f"{self.output_dir}/smuggling/smuggler_results.txt"),
            'cloud_assets': self.read_file_lines(f"{self.output_dir}/cloud/s3_buckets.txt"),
            'leaked_secrets': self.read_file_lines(f"{self.output_dir}/github/github_secrets.txt"),
            'shodan_results': self.read_file_lines(f"{self.output_dir}/shodan/shodan_results.txt"),
            'osint_report': f"osint/theharvester.html" if os.path.exists(f"{self.output_dir}/osint/theharvester.html") else None,
            'open_redirects': self.read_file_lines(f"{self.output_dir}/redirects/open_redirects.txt"),
            'whatwaf_findings': self.read_file_lines(f"{self.output_dir}/whatwaf/whatwaf_results.txt"),
            'fuzz_findings': fuzz_endpoints,
            'cariddi_findings': self.read_file_lines(f"{self.output_dir}/cariddi/cariddi_results.txt"),
            'jaeles_vulns': jaeles,
            'ssti_findings': self.read_file_lines(f"{self.output_dir}/tplmap/tplmap_results.txt"),
            'crlf_findings': self.read_file_lines(f"{self.output_dir}/crlfuzz/crlfuzz_results.txt"),
            'internetdb_findings': self.read_file_lines(f"{self.output_dir}/internetdb/internetdb_results.json"),
            'nikto_results': nikto,
            'tlsx_sans': self.read_file_lines(f"{self.output_dir}/tlsx/tlsx_sans.txt"),
            'bypass_403': self.read_file_lines(f"{self.output_dir}/nomore403/bypass_results.txt"),
            'screenshots': screenshots_list,
        }
        # Parse vulnerabilities
        vulns_file = f"{self.output_dir}/nuclei_output.jsonl"
        if os.path.exists(vulns_file):
            vulns = []
            for line in self.read_file_lines(vulns_file):
                try:
                    vulns.append(json.loads(line))
                except Exception:
                    pass
            report['vulnerabilities'] = vulns
        path = f"{self.output_dir}/findings.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"{Colors.GREEN}[✔] JSON report: {path}{Colors.RESET}")

    def generate_markdown_report(self):
        """Generate markdown report for bug bounty submissions"""
        if not self._require_setup():
            return
        path = f"{self.output_dir}/report.md"
        
        subs = self.read_file_lines(f"{self.output_dir}/subdomains.txt")
        dns_brute = self.read_file_lines(f"{self.output_dir}/massdns_out.txt")
        dns_resolved = self.read_file_lines(f"{self.output_dir}/dns_resolved.txt")
        alive = self.read_file_lines(f"{self.output_dir}/alive.txt")
        ports = self.read_file_lines(f"{self.output_dir}/ports_full.txt")
        if not ports:
            ports = self.read_file_lines(f"{self.output_dir}/ports_fast.txt")
        params = self.read_file_lines(f"{self.output_dir}/parameters/parameters_final.txt")
        js_endpoints = self.read_file_lines(f"{self.output_dir}/js_endpoints/endpoints.txt")
        urls = self.read_file_lines(f"{self.output_dir}/urls_final.txt")
        asn_ranges = self.read_file_lines(f"{self.output_dir}/asn/asn_ranges.txt")
        dalfox = self.read_file_lines(f"{self.output_dir}/xss_findings/dalfox_results.txt")
        cors = self.read_file_lines(f"{self.output_dir}/cors_findings/cors_results.txt")
        takeovers = self.read_file_lines(f"{self.output_dir}/takeover/takeovers.txt")
        smuggler = self.read_file_lines(f"{self.output_dir}/smuggling/smuggler_results.txt")
        
        sqlmap = []
        sqlmap_dir = Path(f"{self.output_dir}/sqlmap")
        if sqlmap_dir.exists():
            for log in sqlmap_dir.rglob('log'):
                sqlmap.extend(self.read_file_lines(str(log)))
        
        s3_buckets = self.read_file_lines(f"{self.output_dir}/cloud/s3_buckets.txt")
        github_secrets = self.read_file_lines(f"{self.output_dir}/github/github_secrets.txt")
        shodan_results = self.read_file_lines(f"{self.output_dir}/shodan/shodan_results.txt")
        open_redirects = self.read_file_lines(f"{self.output_dir}/redirects/open_redirects.txt")
        whatwaf = self.read_file_lines(f"{self.output_dir}/whatwaf/whatwaf_results.txt")

        cariddi = self.read_file_lines(f"{self.output_dir}/cariddi/cariddi_results.txt")
        tplmap = self.read_file_lines(f"{self.output_dir}/tplmap/tplmap_results.txt")
        crlfuzz = self.read_file_lines(f"{self.output_dir}/crlfuzz/crlfuzz_results.txt")
        nomore403 = self.read_file_lines(f"{self.output_dir}/nomore403/bypass_results.txt")
        tlsx = self.read_file_lines(f"{self.output_dir}/tlsx/tlsx_sans.txt")
        
        # Parse FFUF directory fuzzing JSONs
        fuzz_endpoints = []
        fuzz_dir = Path(f"{self.output_dir}/fuzzing")
        if fuzz_dir.exists():
            for json_file in fuzz_dir.glob('ffuf_*.json'):
                try:
                    data = json.loads(json_file.read_text(encoding='utf-8'))
                    for res in data.get('results', []):
                        fuzz_endpoints.append(f"[{res.get('status')}] {res.get('url')}")
                except Exception:
                    pass

        internetdb = []
        idb_path = Path(f"{self.output_dir}/internetdb/internetdb_results.json")
        if idb_path.exists():
            try:
                idb_data = json.loads(idb_path.read_text(encoding='utf-8'))
                for host in idb_data:
                    ip = host.get('ip', '')
                    ports_list = ', '.join(str(p) for p in host.get('ports', []))
                    cpes = ', '.join(host.get('cpes', []))
                    vulns_list = ', '.join(host.get('vulns', []))
                    internetdb.append(f"IP: {ip} | Ports: {ports_list} | CPEs: {cpes} | Vulns: {vulns_list}")
            except Exception:
                pass

        jaeles = []
        jaeles_dir = Path(f"{self.output_dir}/jaeles")
        if jaeles_dir.exists():
            for txt_file in jaeles_dir.rglob('*.txt'):
                jaeles.extend(self.read_file_lines(str(txt_file)))

        nikto = []
        nikto_dir = Path(f"{self.output_dir}/nikto")
        if nikto_dir.exists():
            for txt_file in nikto_dir.glob('*.txt'):
                nikto.extend(self.read_file_lines(str(txt_file)))
        
        # Collect screenshots
        screenshots_dir = Path(f"{self.output_dir}/screenshots")
        screenshot_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        screenshots = []
        if screenshots_dir.exists():
            screenshots = [
                img for img in sorted(screenshots_dir.rglob('*'))
                if img.is_file() and img.suffix.lower() in screenshot_exts
            ]

        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Oculus Report — {self.domain}\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Version:** {VERSION}\n\n---\n\n")
            
            # Summary Table
            f.write("## Summary\n\n| Metric | Count |\n|---|---|\n")
            for k, v in sorted(self.results.items()):
                if isinstance(v, (int, float)):
                    f.write(f"| {k.replace('_', ' ').title()} | {v} |\n")
            f.write("\n---\n\n")
            
            # Vulnerabilities
            vulns_file = f"{self.output_dir}/nuclei_output.jsonl"
            if os.path.exists(vulns_file):
                vulns_list = []
                for line in self.read_file_lines(vulns_file):
                    try:
                        vulns_list.append(json.loads(line))
                    except Exception:
                        pass
                if vulns_list:
                    f.write("## 🔴 Vulnerabilities\n\n")
                    f.write("| Severity | Name | Template | Matched At |\n|---|---|---|---|\n")
                    for v in sorted(vulns_list, key=lambda x: {'critical':0, 'high':1, 'medium':2, 'low':3, 'info':4}.get(x.get('info',{}).get('severity','info').lower(), 5)):
                        sev = v.get('info',{}).get('severity','info').lower().upper()
                        name = v.get("info",{}).get("name","")
                        template = v.get("template-id","")
                        matched = v.get("matched-at","")
                        f.write(f"| **{sev}** | {name} | {template} | `{matched}` |\n")
                    f.write("\n---\n\n")
            
            # Screenshots
            if screenshots:
                f.write(f"## 📸 Captured Screenshots ({len(screenshots)})\n\n")
                for img in screenshots[:20]:
                    rel_img = str(img.relative_to(screenshots_dir)).replace(os.sep, '/')
                    f.write(f"### {img.name}\n")
                    f.write(f"![{img.name}](screenshots/{rel_img})\n\n")
                if len(screenshots) > 20:
                    f.write(f"*... and {len(screenshots) - 20} more in screenshots/ directory*\n\n")
                f.write("---\n\n")

            # Subdomains
            if subs:
                f.write(f"## 📡 Subdomains ({len(subs)})\n\n")
                for s in subs[:100]:
                    f.write(f"- {s}\n")
                if len(subs) > 100:
                    f.write(f"\n*... and {len(subs) - 100} more subdomains*\n")
                f.write("\n---\n\n")

            # DNS Bruteforce
            if dns_brute:
                f.write(f"## 🔎 DNS Bruteforce ({len(dns_brute)})\n\n")
                for db in dns_brute[:100]:
                    f.write(f"- {db}\n")
                if len(dns_brute) > 100:
                    f.write(f"\n*... and {len(dns_brute) - 100} more DNS bruteforce records*\n")
                f.write("\n---\n\n")
                
            # Alive Hosts
            if alive:
                f.write(f"## 🟢 Alive Hosts ({len(alive)})\n\n")
                for a in alive[:100]:
                    f.write(f"- {a}\n")
                if len(alive) > 100:
                    f.write(f"\n*... and {len(alive) - 100} more alive hosts*\n")
                f.write("\n---\n\n")

            # DNS Records
            if dns_resolved:
                f.write(f"## 🔎 DNS Records Resolved ({len(dns_resolved)})\n\n")
                for d in dns_resolved[:100]:
                    f.write(f"- {d}\n")
                if len(dns_resolved) > 100:
                    f.write(f"\n*... and {len(dns_resolved) - 100} more DNS records*\n")
                f.write("\n---\n\n")

            # Open Ports
            if ports:
                f.write(f"## 🔌 Open Ports ({len(ports)})\n\n")
                for p in ports[:100]:
                    f.write(f"- {p}\n")
                if len(ports) > 100:
                    f.write(f"\n*... and {len(ports) - 100} more open ports*\n")
                f.write("\n---\n\n")

            # ASN IP Ranges
            if asn_ranges:
                clean_ranges = [r for r in asn_ranges if not r.startswith('#')]
                comments = [r for r in asn_ranges if r.startswith('#')]
                f.write(f"## 🌐 ASN IP Ranges ({len(clean_ranges)})\n\n")
                for c in comments:
                    f.write(f"*{c.lstrip('#').strip()}*\n\n")
                for r in clean_ranges[:100]:
                    f.write(f"- {r}\n")
                if len(clean_ranges) > 100:
                    f.write(f"\n*... and {len(clean_ranges) - 100} more ASN IP ranges*\n")
                f.write("\n---\n\n")

            # URLs
            if urls:
                f.write(f"## 🔗 Discovered URLs ({len(urls)})\n\n")
                for u in urls[:100]:
                    f.write(f"- {u}\n")
                if len(urls) > 100:
                    f.write(f"\n*... and {len(urls) - 100} more URLs*\n")
                f.write("\n---\n\n")

            # Parameters
            if params:
                f.write(f"## 📝 Parameters ({len(params)})\n\n")
                for pa in params[:100]:
                    f.write(f"- {pa}\n")
                if len(params) > 100:
                    f.write(f"\n*... and {len(params) - 100} more parameters*\n")
                f.write("\n---\n\n")

            # JS Endpoints
            if js_endpoints:
                f.write(f"## 📜 JS Endpoints ({len(js_endpoints)})\n\n")
                for j in js_endpoints[:100]:
                    f.write(f"- {j}\n")
                if len(js_endpoints) > 100:
                    f.write(f"\n*... and {len(js_endpoints) - 100} more JS endpoints*\n")
                f.write("\n---\n\n")

            # XSS Findings (Dalfox)
            if dalfox:
                f.write(f"## 🦊 Cross-Site Scripting (XSS) ({len(dalfox)})\n\n")
                for d in dalfox[:100]:
                    f.write(f"- `{d}`\n")
                if len(dalfox) > 100:
                    f.write(f"\n*... and {len(dalfox) - 100} more XSS findings*\n")
                f.write("\n---\n\n")

            # SQL Injections (SQLMap)
            if sqlmap:
                f.write(f"## 💉 SQL Injections ({len(sqlmap)})\n\n")
                f.write("```text\n")
                for sql in sqlmap[:200]:
                    f.write(f"{sql}\n")
                if len(sqlmap) > 200:
                    f.write(f"\n... and {len(sqlmap) - 200} more SQLMap log lines\n")
                f.write("```\n\n---\n\n")

            # Subdomain Takeovers
            if takeovers:
                f.write(f"## 🏴‍☠️ Subdomain Takeovers ({len(takeovers)})\n\n")
                for t in takeovers[:100]:
                    f.write(f"- {t}\n")
                if len(takeovers) > 100:
                    f.write(f"\n*... and {len(takeovers) - 100} more takeover records*\n")
                f.write("\n---\n\n")

            # CORS Misconfigurations
            if cors:
                f.write(f"## 🔄 CORS Misconfigurations ({len(cors)})\n\n")
                for c in cors[:100]:
                    f.write(f"- {c}\n")
                if len(cors) > 100:
                    f.write(f"\n*... and {len(cors) - 100} more CORS issues*\n")
                f.write("\n---\n\n")

            # HTTP Smuggling
            if smuggler:
                f.write(f"## 🕵️ HTTP Smuggling ({len(smuggler)})\n\n")
                for s in smuggler[:100]:
                    f.write(f"- {s}\n")
                if len(smuggler) > 100:
                    f.write(f"\n*... and {len(smuggler) - 100} more Smuggler results*\n")
                f.write("\n---\n\n")

            # Cloud Assets
            if s3_buckets:
                f.write(f"## ☁️ Cloud Buckets / Assets ({len(s3_buckets)})\n\n")
                for s in s3_buckets[:100]:
                    f.write(f"- {s}\n")
                if len(s3_buckets) > 100:
                    f.write(f"\n*... and {len(s3_buckets) - 100} more cloud assets*\n")
                f.write("\n---\n\n")

            # Leaked Secrets (GitHub)
            if github_secrets:
                f.write(f"## 🔑 Leaked Secrets (GitHub) ({len(github_secrets)})\n\n")
                for g in github_secrets[:100]:
                    f.write(f"- {g}\n")
                if len(github_secrets) > 100:
                    f.write(f"\n*... and {len(github_secrets) - 100} more leaked secrets*\n")
                f.write("\n---\n\n")

            # Shodan Host Intelligence
            if shodan_results:
                f.write(f"## 🔎 Shodan Host Intelligence ({len(shodan_results)})\n\n")
                for sh in shodan_results[:100]:
                    f.write(f"- {sh}\n")
                if len(shodan_results) > 100:
                    f.write(f"\n*... and {len(shodan_results) - 100} more Shodan results*\n")
                f.write("\n---\n\n")

            # OSINT
            if os.path.exists(f"{self.output_dir}/osint/theharvester.html"):
                f.write("## 👥 OSINT Harvesting (theHarvester)\n\n")
                f.write("- [theHarvester HTML Report](osint/theharvester.html)\n\n---\n\n")

            # Open Redirects
            if open_redirects:
                f.write(f"## ↩️ Open Redirects ({len(open_redirects)})\n\n")
                for o in open_redirects[:100]:
                    f.write(f"- {o}\n")
                if len(open_redirects) > 100:
                    f.write(f"\n*... and {len(open_redirects) - 100} more open redirects*\n")
                f.write("\n---\n\n")

            # WhatWaf
            if whatwaf:
                f.write(f"## WhatWaf WAF Intelligence ({len(whatwaf)})\n\n")
                for w in whatwaf[:100]:
                    f.write(f"- {w}\n")
                if len(whatwaf) > 100:
                    f.write(f"\n*... and {len(whatwaf) - 100} more WhatWaf lines*\n")
                f.write("\n---\n\n")

            # Directory Fuzzing
            if fuzz_endpoints:
                f.write(f"## 📁 Directory Fuzzing ({len(fuzz_endpoints)})\n\n")
                for fe in fuzz_endpoints[:100]:
                    f.write(f"- {fe}\n")
                if len(fuzz_endpoints) > 100:
                    f.write(f"\n*... and {len(fuzz_endpoints) - 100} more fuzz findings*\n")
                f.write("\n---\n\n")

            # Cariddi
            if cariddi:
                f.write(f"## 🕷️ Cariddi Crawl Findings ({len(cariddi)})\n\n")
                for c in cariddi[:100]:
                    f.write(f"- {c}\n")
                if len(cariddi) > 100:
                    f.write(f"\n*... and {len(cariddi) - 100} more crawl findings*\n")
                f.write("\n---\n\n")

            # Jaeles
            if jaeles:
                f.write(f"## 🛡️ Jaeles Vulnerability Findings ({len(jaeles)})\n\n")
                for j in jaeles[:100]:
                    f.write(f"- {j}\n")
                if len(jaeles) > 100:
                    f.write(f"\n*... and {len(jaeles) - 100} more Jaeles vulnerabilities*\n")
                f.write("\n---\n\n")

            # Tplmap
            if tplmap:
                f.write(f"## ⚙️ SSTI Vulnerabilities (Tplmap) ({len(tplmap)})\n\n")
                for t in tplmap[:100]:
                    f.write(f"- {t}\n")
                if len(tplmap) > 100:
                    f.write(f"\n*... and {len(tplmap) - 100} more SSTI vulnerabilities*\n")
                f.write("\n---\n\n")

            # CRLF
            if crlfuzz:
                f.write(f"## 🧬 CRLF Vulnerabilities (CRLFuzz) ({len(crlfuzz)})\n\n")
                for cr in crlfuzz[:100]:
                    f.write(f"- {cr}\n")
                if len(crlfuzz) > 100:
                    f.write(f"\n*... and {len(crlfuzz) - 100} more CRLF vulnerabilities*\n")
                f.write("\n---\n\n")

            # InternetDB
            if internetdb:
                f.write(f"## 🗄️ InternetDB Passive Lookup ({len(internetdb)})\n\n")
                for i in internetdb[:100]:
                    f.write(f"- {i}\n")
                if len(internetdb) > 100:
                    f.write(f"\n*... and {len(internetdb) - 100} more Shodan InternetDB records*\n")
                f.write("\n---\n\n")

            # Nikto
            if nikto:
                f.write(f"## 🗃️ Nikto Web Server Scan ({len(nikto)})\n\n")
                for ni in nikto[:100]:
                    f.write(f"- {ni}\n")
                if len(nikto) > 100:
                    f.write(f"\n*... and {len(nikto) - 100} more Nikto results*\n")
                f.write("\n---\n\n")

            # TLSX
            if tlsx:
                f.write(f"## 🔒 TLS Certificate SANs ({len(tlsx)})\n\n")
                for tl in tlsx[:100]:
                    f.write(f"- {tl}\n")
                if len(tlsx) > 100:
                    f.write(f"\n*... and {len(tlsx) - 100} more TLS certificate SANs*\n")
                f.write("\n---\n\n")

            # Nomore403
            if nomore403:
                f.write(f"## 🔓 403 Bypasses (nomore403) ({len(nomore403)})\n\n")
                for no in nomore403[:100]:
                    f.write(f"- {no}\n")
                if len(nomore403) > 100:
                    f.write(f"\n*... and {len(nomore403) - 100} more 403 bypass records*\n")
                f.write("\n\n")

        print(f"{Colors.GREEN}[✔] Markdown report: {path}{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MENU / HELP / MAIN LOOP
    # ═══════════════════════════════════════════════════════════════

    def display_menu(self):
        """Display main menu"""
        if RICH_AVAILABLE:
            from rich.table import Table
            from rich.panel import Panel
            from rich.console import Group
            from rich import print as rprint
            from rich.text import Text

            def get_status(key, name):
                if key in self.results:
                    val = self.results[key]
                    if isinstance(val, int) and val == 0:
                        return f"[bold dim]✔[/] {name} [dim]({val})[/]"
                    return f"[bold green]✔[/] {name} [bold green]({val})[/]"
                return f"  {name}"

            table = Table(show_header=False, box=None, padding=(0, 2, 1, 2))
            table.add_column(justify="right", style="bold cyan")
            table.add_column(justify="left", ratio=1)
            table.add_column(justify="right", style="bold cyan")
            table.add_column(justify="left", ratio=1)

            # Core Reconnaissance
            table.add_row(
                "", "[bold yellow]CORE RECONNAISSANCE WORKFLOW[/]",
                "", ""
            )
            table.add_row(
                "[1]", get_status("subdomains", "Subdomain Enumeration"),
                "[2]", get_status("dns_resolved", "DNS Resolution")
            )
            table.add_row(
                "[3]", get_status("alive_hosts", "Alive Hosts Check"),
                "[4]", get_status("fast_ports", "Fast Port Scan")
            )
            table.add_row(
                "[5]", get_status("full_ports", "Full Port Scan"),
                "[6]", get_status("urls", "URL Collection")
            )
            table.add_row(
                "[7]", get_status("waf_detected", "WAF Detection"),
                "[8]", get_status("vulnerabilities", "Vulnerability Scan")
            )

            table.add_row("", "", "", "")

            # Advanced Modules
            table.add_row(
                "", "[bold yellow]ADVANCED MODULES[/]",
                "", ""
            )
            table.add_row(
                "[10]", get_status("parameters", "Parameter Discovery"),
                "[11]", get_status("js_endpoints", "JS Endpoint Extraction")
            )
            table.add_row(
                "[12]", "Directory Fuzzing",
                "[13]", "API Fuzzing"
            )
            table.add_row(
                "[14]", "Subdomain Takeover",
                "[15]", get_status("urls_final", "Advanced URL Enum")
            )
            table.add_row(
                "[16]", "Screenshot Capture",
                "[17]", "DNS Bruteforce"
            )
            table.add_row(
                "[18]", get_status("gf_filters", "GF Filters"),
                "[19]", "Tech Scan"
            )
            table.add_row(
                "[20]", "SQLi Scan",
                "[21]", get_status("xss_findings", "XSS Scan (Dalfox)")
            )
            table.add_row(
                "[22]", get_status("cors_findings", "CORS Scanner"),
                "[23]", "HTTP Smuggling"
            )
            table.add_row(
                "[24]", "ASN Discovery",
                "[25]", "Cloud Assets"
            )
            table.add_row(
                "[26]", "GitHub Dorking",
                "[27]", "OSINT Harvesting"
            )
            table.add_row(
                "[28]", "Shodan Recon",
                "[29]", "Open Redirect Scan"
            )
            table.add_row(
                "[30]", get_status("cariddi_findings", "Cariddi Scan"),
                "[31]", get_status("jaeles_findings", "Jaeles Scan")
            )
            table.add_row(
                "[32]", get_status("ssti_findings", "Tplmap SSTI Scan"),
                "[33]", get_status("crlf_findings", "CRLFuzz CRLF Scan")
            )
            table.add_row(
                "[34]", get_status("internetdb_hosts", "InternetDB Lookup"),
                "[35]", get_status("nikto_scanned", "Nikto Scanner")
            )
            table.add_row(
                "[36]", get_status("tlsx_sans", "TLSX Cert Scan"),
                "[37]", get_status("bypass_403", "Nomore403 Bypass")
            )

            table.add_row("", "", "", "")

            # Core Automation
            table.add_row(
                "", "[bold yellow]CORE AUTOMATION & SYSTEM[/]",
                "", ""
            )
            table.add_row(
                "[9]", "[bold bright_green]Full Auto Recon    (Core 1-8)[/]",
                "[D]", "[bold bright_magenta]Deep Recon         (Advanced)[/]"
            )
            table.add_row(
                "[U]", "[bold bright_red]Full Spectrum Scan (All 36)[/]",
                "[R]", "Generate Reports"
            )
            table.add_row(
                "[I]", "Initialize Tools",
                "[C]", "Change Domain"
            )
            table.add_row(
                "[H]", "Help",
                "[Q]", "Quit"
            )

            # Stats Header inside panel
            stats_text = Text()
            if self.domain:
                stats_text.append(f"TARGET: {self.domain} ", style="bold green")
                stats_text.append(f"| OUT: {self.output_dir}/ ", style="dim")
                
                # Active Metrics
                metrics = []
                if "subdomains" in self.results: metrics.append(f"Subs: {self.results['subdomains']}")
                if "alive_hosts" in self.results: metrics.append(f"Alive: {self.results['alive_hosts']}")
                if "urls" in self.results: metrics.append(f"URLs: {self.results['urls']}")
                if "vulnerabilities" in self.results: metrics.append(f"Vulns: {self.results['vulnerabilities']}")
                
                if metrics:
                    stats_text.append(" | STATS: " + " - ".join(metrics), style="bold cyan")
                
                # Suggest Next Step logic — cascaded so advanced overrides only fire if core is done
                if "cors_findings" in self.results:
                    suggestion = "[R] Generate Reports -- All scans complete!"
                elif "xss_findings" in self.results:
                    suggestion = "[22] CORS Scanner OR [23] HTTP Smuggling"
                elif "gf_filters" in self.results:
                    suggestion = "[20] SQLi Scan OR [21] XSS Scan (Dalfox)"
                elif "urls_final" in self.results:
                    suggestion = "[16] Screenshot Capture OR [18] GF Filters"
                elif "parameters" in self.results or "js_endpoints" in self.results:
                    suggestion = "[12] Directory Fuzzing OR [13] API Fuzzing"
                elif "vulnerabilities" in self.results:
                    suggestion = "[D] Deep Recon OR [U] Full Spectrum Scan"
                elif "waf_detected" in self.results:
                    suggestion = "[8] Vulnerability Scan"
                elif "urls" in self.results:
                    suggestion = "[7] WAF Detection OR [8] Vulnerability Scan"
                elif "fast_ports" in self.results or "full_ports" in self.results:
                    suggestion = "[6] URL Collection"
                elif "alive_hosts" in self.results:
                    suggestion = "[4] Fast Port Scan OR [6] URL Collection"
                elif "dns_resolved" in self.results:
                    suggestion = "[3] Alive Hosts Check"
                elif "subdomains" in self.results:
                    suggestion = "[2] DNS Resolution OR [3] Alive Hosts Check"
                else:
                    suggestion = "[1] Subdomain Enumeration OR [9] Full Auto Recon OR [U] Full Spectrum"
                
                stats_text.append("\nSUGGESTED NEXT STEP: ", style="bold yellow")
                stats_text.append(suggestion, style="bold white")
            else:
                stats_text.append("NO DOMAIN SELECTED. CHOOSE OPTION C FIRST.", style="bold yellow")
                
            panel = Panel(
                Group(stats_text, Text(""), table),
                title=f"[bold cyan]OCULUS v{VERSION} MAIN MENU[/]",
                border_style="cyan",
                padding=(1, 2)
            )
            rprint(panel)
            print("")
        else:
            print(f"\n{Colors.CYAN}--- OCULUS v{VERSION} ---{Colors.RESET}")
            print(f"{Colors.YELLOW}[ CORE RECON ]{Colors.RESET}")
            print("1. Subdomains  | 2. DNS Resolv  | 3. Alive Hosts | 4. Fast Ports  | 5. Full Ports")
            print(f"{Colors.YELLOW}[ DISCOVERY ]{Colors.RESET}")
            print("6. URLs        | 10. Parameters | 11. JS Endpoints| 12. Dir Fuzz  | 13. API Fuzz")
            print(f"{Colors.YELLOW}[ VULNERABILITY ]{Colors.RESET}")
            print("7. WAF Detect  | 8. Vuln Scan   | 20. SQLi Scan  | 21. XSS Scan   | 22. CORS")
            print(f"{Colors.YELLOW}[ OSINT & MORE ]{Colors.RESET}")
            print("14. Takeover   | 17. DNS Brute  | 24. ASN        | 25. Cloud      | 26-29. OSINT")
            print(f"{Colors.YELLOW}[ ADVANCED SCAFFOLDING ]{Colors.RESET}")
            print("30. Cariddi    | 31. Jaeles     | 32. Tplmap     | 33. CRLFuzz    | 34. InternetDB")
            print("35. Nikto      | 36. TLSX       | 37. Nomore403")
            print(f"{Colors.YELLOW}[ AUTOMATION & SYSTEM ]{Colors.RESET}")
            print("9. Full Auto   | D. Deep Recon  | U. Full Spectrum (All 36)| C. Domain     | Q. Quit")
            print(f"{Colors.CYAN}-------------------{Colors.RESET}\n")
            
            if self.domain:
                print(f"{Colors.GREEN}[+] Domain: {self.domain}  |  Output: {self.output_dir}/{Colors.RESET}\n")
            else:
                print(f"{Colors.YELLOW}[!] No domain selected. Choose option C first.{Colors.RESET}\n")

    def show_help(self):
        """Display help"""
        if RICH_AVAILABLE:
            from rich.panel import Panel
            from rich.text import Text
            from rich import print as rprint
            
            t = Text()
            t.append("CORE WORKFLOW:\n", style="bold white")
            t.append("  1->2->3->4->6->7->8  or  9 (Full Automated)\n\n")
            
            t.append("ADVANCED MODULES:\n", style="bold white")
            t.append("  10-20: Parameter discovery, JS extraction, fuzzing, etc.\n")
            t.append("  21-24: XSS scan, CORS scan, HTTP smuggling, ASN discovery\n\n")
            
            t.append("DEEP RECON (D):\n", style="bold white")
            t.append("  Chains 13 advanced modules automatically.\n\n")
            
            t.append("REPORTS (R):\n", style="bold white")
            t.append("  Generates HTML, JSON, and Markdown reports.\n\n")
            
            t.append("CLI MODE:\n", style="bold white")
            t.append("  oculus -d domain.com --full-recon --no-confirm\n")
            t.append("  oculus -d domain.com --full-spectrum --no-confirm\n")
            t.append("  oculus -d domain.com --module subdomain,alive,vuln\n")
            t.append("  oculus -d domain.com --deep\n\n")
            
            t.append("CONFIG:\n", style="bold white")
            t.append("  ~/.config/oculus/config.yaml\n")
            
            panel = Panel(t, title=f"[bold cyan]OCULUS v{VERSION} HELP[/]", border_style="cyan", padding=(1, 2))
            rprint(panel)
            print(f"{Colors.CYAN}Press Enter to return...{Colors.RESET}")
            input()
        else:
            print(f"\n{Colors.CYAN}--- OCULUS HELP ---{Colors.RESET}")
            print("1-8: Core | 9: Full Auto | D: Deep Recon | CLI: oculus -d domain.com --deep")
            input(f"{Colors.CYAN}Press Enter to return...{Colors.RESET}")

    def run(self):
        """Main execution loop"""
        self.display_banner()
        self.initialize_tools()
        while True:
            self.display_menu()
            choice = input(f"{Colors.CYAN}[+] Select option: {Colors.RESET}").strip().upper()
            dispatch = {
                '1': self.run_subdomain_enumeration,
                '2': self.run_dns_resolution,
                '3': self.run_alive_hosts_check,
                '4': self.run_fast_port_scan,
                '5': self.run_full_port_scan,
                '6': self.run_url_collection,
                '7': self.run_waf_detection,
                '8': self.run_vulnerability_scan,
                '9': self.run_full_automated_recon,
                '10': self.run_parameter_discovery,
                '11': self.run_js_endpoint_extraction,
                '12': self.run_directory_fuzzing,
                '13': self.run_api_fuzzing,
                '14': self.run_subdomain_takeover_check,
                '15': self.run_advanced_url_enum,
                '16': self.run_screenshot_capture,
                '17': self.run_dns_bruteforce,
                '18': self.run_gf_filters,
                '19': self.run_tech_scan,
                '20': self.run_sqlmap_scan,
                '21': self.run_xss_scan,
                '22': self.run_cors_scan,
                '23': self.run_http_smuggling,
                '24': self.run_asn_discovery,
                '25': self.run_cloud_asset_discovery,
                '26': self.run_github_dorking,
                '27': self.run_osint_harvesting,
                '28': self.run_shodan_integration,
                '29': self.run_open_redirect_scan,
                '30': self.run_cariddi_scan,
                '31': self.run_jaeles_scan,
                '32': self.run_tplmap_scan,
                '33': self.run_crlfuzz_scan,
                '34': self.run_internetdb_scan,
                '35': self.run_nikto_scan,
                '36': self.run_tlsx_scan,
                '37': self.run_nomore403_scan,
                'D': self.run_deep_recon_mode,
                'U': self.run_full_spectrum_scan,
                'R': lambda: (self.generate_html_report(), self.generate_json_report(), self.generate_markdown_report()),
                'C': self.setup_domain,
                'I': self.initialize_tools,
                'H': self.show_help,
            }
            if choice == 'Q':
                print(f"\n{Colors.GREEN}[✔] Thank you for using Oculus!{Colors.RESET}")
                print(f"{Colors.CYAN}    Happy hunting! 🎯{Colors.RESET}\n")
                break
            elif choice in dispatch:
                try:
                    func = dispatch[choice]
                    if choice.isdigit() and choice not in {'9'}:
                        module_name = func.__name__.replace('run_', '').replace('_', ' ').title()
                        previous_module = self._current_module
                        self._current_module = module_name
                        self.notify_scan_event(
                            'module_start',
                            f"Oculus module started: {module_name}",
                            f"{module_name} started for {self.domain}",
                            priority='low',
                            tags=['play_arrow'],
                            dedupe_key=f"tui_module_start:{module_name}:{self.domain}",
                        )
                        try:
                            func()
                            self._notify_module_done(module_name)
                        except Exception as e:
                            self._notify_module_error(module_name, str(e))
                            raise
                        finally:
                            self._current_module = previous_module
                    else:
                        func()
                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}[!] Module interrupted{Colors.RESET}")
                except Exception as e:
                    print(f"{Colors.RED}[!] Error: {e}{Colors.RESET}")
                    self.logger.error(f"Module {choice}: {e}")
            else:
                print(f"{Colors.RED}[!] Invalid option!{Colors.RESET}")
            if choice != 'H':
                input(f"\n{Colors.CYAN}[*] Press Enter to continue...{Colors.RESET}")


def build_parser():
    """Build argparse CLI"""
    parser = argparse.ArgumentParser(
        prog='oculus',
        description=f'Oculus v{VERSION} — Professional Recon Framework'
    )
    parser.add_argument('-d', '--domain', help='Target domain')
    parser.add_argument('--full-recon', action='store_true', help='Run full automated recon (core modules 1–8)')
    parser.add_argument('--full-spectrum', action='store_true', help='Run full spectrum scan (all modules, 5 phases)')
    parser.add_argument('--deep', action='store_true', help='Run deep recon mode (14 advanced steps)')
    parser.add_argument('--module', help='Comma-separated modules: subdomain,dns,alive,ports,urls,waf,vuln,xss,cors,asn')
    parser.add_argument('--no-confirm', action='store_true', help='Skip all confirmation prompts')
    parser.add_argument('--threads', type=int, help='Thread count')
    parser.add_argument('--timeout', type=int, help='Default timeout in seconds')
    parser.add_argument('--setup-ntfy', action='store_true', help='Run the interactive ntfy setup wizard')
    parser.add_argument('--update', action='store_true', help='Update Oculus framework and dependencies')
    parser.add_argument('--jitter', action='store_true', help='Enable random delays between tool calls')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    return parser


MODULE_MAP = {
    'subdomain': 'run_subdomain_enumeration',
    'dns': 'run_dns_resolution',
    'alive': 'run_alive_hosts_check',
    'ports': 'run_fast_port_scan',
    'fullports': 'run_full_port_scan',
    'urls': 'run_url_collection',
    'waf': 'run_waf_detection',
    'vuln': 'run_vulnerability_scan',
    'params': 'run_parameter_discovery',
    'js': 'run_js_endpoint_extraction',
    'fuzz': 'run_directory_fuzzing',
    'api': 'run_api_fuzzing',
    'takeover': 'run_subdomain_takeover_check',
    'hakrawler': 'run_advanced_url_enum',
    'screenshots': 'run_screenshot_capture',
    'dnsbrute': 'run_dns_bruteforce',
    'gf': 'run_gf_filters',
    'tech': 'run_tech_scan',
    'sqli': 'run_sqlmap_scan',
    'xss': 'run_xss_scan',
    'cors': 'run_cors_scan',
    'smuggling': 'run_http_smuggling',
    'asn': 'run_asn_discovery',
    'cloud': 'run_cloud_asset_discovery',
    'github': 'run_github_dorking',
    'osint': 'run_osint_harvesting',
    'shodan': 'run_shodan_integration',
    'redirect': 'run_open_redirect_scan',
    'cariddi': 'run_cariddi_scan',
    'jaeles': 'run_jaeles_scan',
    'tplmap': 'run_tplmap_scan',
    'crlfuzz': 'run_crlfuzz_scan',
    'internetdb': 'run_internetdb_scan',
    'nikto': 'run_nikto_scan',
    'tlsx': 'run_tlsx_scan',
    'nomore403': 'run_nomore403_scan',
}


def main():
    """Main entry point with CLI support"""
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, 'setup_ntfy', False):
        from ntfy_setup import setup_ntfy
        setup_ntfy()
        sys.exit(0)

    if getattr(args, 'update', False):
        print(f"{Colors.CYAN}[*] Updating Oculus framework from GitHub...{Colors.RESET}")
        os.system("git pull")
        if os.path.exists("install.sh"):
            print(f"{Colors.CYAN}[*] Updating dependencies...{Colors.RESET}")
            os.system("sudo ./install.sh --update")
        sys.exit(0)

    config = load_config()
    if args.no_confirm:
        config['auto_confirm'] = True
    if args.threads:
        config['threads'] = args.threads
    if args.timeout:
        config['timeout'] = args.timeout
    if getattr(args, 'jitter', False):
        config['jitter'] = True

    recon = Oculus(config=config)
    recon.perform_health_check()

    if args.domain:
        # CLI mode
        recon.display_banner()
        recon.initialize_tools()
        recon.domain = args.domain
        recon.output_dir = f"output-{args.domain}"
        Path(recon.output_dir).mkdir(parents=True, exist_ok=True)
        Path(f"{recon.output_dir}/logs").mkdir(parents=True, exist_ok=True)
        recon._setup_logging_full()
        recon.setup_complete = True
        recon.load_session()

        # Run CLI with automatic process termination on Interrupt
        try:
            if args.full_recon and args.full_spectrum:
                print(f"{Colors.YELLOW}[!] Both --full-recon and --full-spectrum set; running full spectrum.{Colors.RESET}")
            if args.full_spectrum:
                recon.run_full_spectrum_scan()
            elif args.full_recon:
                recon.run_full_automated_recon()
            elif args.deep:
                recon.run_deep_recon_mode()
            elif args.module:
                modules = [m.strip() for m in args.module.split(',')]
                for mod in modules:
                    method = MODULE_MAP.get(mod)
                    if method and hasattr(recon, method):
                        print(f"\n{Colors.CYAN}[*] Running module: {mod}{Colors.RESET}")
                        module_name = method.replace('run_', '').replace('_', ' ').title()
                        previous_module = recon._current_module
                        recon._current_module = module_name
                        recon.notify_scan_event(
                            'module_start',
                            f"Oculus module started: {module_name}",
                            f"{module_name} started for {recon.domain}",
                            priority='low',
                            tags=['play_arrow'],
                            dedupe_key=f"cli_module_start:{module_name}:{recon.domain}",
                        )
                        try:
                            getattr(recon, method)()
                            recon._notify_module_done(module_name)
                        except Exception as e:
                            recon._notify_module_error(module_name, str(e))
                            raise
                        finally:
                            recon._current_module = previous_module
                    else:
                        print(f"{Colors.RED}[!] Unknown module: {mod}{Colors.RESET}")
                        print(f"    Available: {', '.join(MODULE_MAP.keys())}")
            else:
                recon.run()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}[!] Ctrl+C detected. Terminating active scanner processes...{Colors.RESET}")
            recon.kill_all_active_processes()
            sys.exit(130)
        except Exception as e:
            print(f"\n{Colors.RED}[!] Fatal error: {e}{Colors.RESET}")
            recon.kill_all_active_processes()
            sys.exit(1)
    else:
        # Interactive mode
        try:
            recon.run()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}[!] Interrupted. Terminating active scanner processes...{Colors.RESET}")
            recon.kill_all_active_processes()
            sys.exit(130)
        except Exception as e:
            print(f"\n{Colors.RED}[!] Fatal error: {e}{Colors.RESET}")
            recon.kill_all_active_processes()
            sys.exit(1)


if __name__ == "__main__":
    main()
