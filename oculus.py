#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 Oculus - Professional Recon Framework v3.0                   ║
║                              for Kali Linux                                  ║
║                                                                              ║
║    A beautiful, powerful, automated, and intelligent reconnaissance tool     ║
║                    for bug bounty hunters and pentesters                     ║
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

VERSION = "3.0"

DEFAULT_CONFIG = {
    'threads': 50,
    'timeout': 300,
    'rate_limit': 150,
    'retry_count': 2,
    'retry_delay': 5,
    'wordlists': {
        'dns': '/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt',
        'dirs': '/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt',
        'dirs_fallback': '/usr/share/wordlists/dirb/common.txt',
        'resolvers': '/opt/recontools/massdns/resolvers.txt',
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
    'ffuf': {
        'extensions': 'php,html,js,json,txt,bak,old',
        'status_filter': '200,204,301,302,307,401,403',
        'recursion_depth': 2,
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

    def __init__(self, config=None):
        self.domain = ""
        self.output_dir = ""
        self.tools_status = {}
        self.results = {}
        self.setup_complete = False
        self.config = config or load_config()
        self.logger = None
        self.session_file = ""

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

    def find_tool(self, name):
        """Unified cross-platform path detection for all Oculus tools"""
        paths = [
            shutil.which(name),
            os.path.expanduser(f"~/go/bin/{name}"),
            f"/home/kali/go/bin/{name}",
            f"/usr/local/bin/{name}",
            f"/usr/bin/{name}",
            f"/root/go/bin/{name}",
            # Case-sensitive Opt paths
            f"/opt/recontools/{name}/{name}",
            f"/opt/recontools/{name.lower()}/{name.lower()}",
            f"/opt/recontools/ParamSpider/paramspider.py",
            f"/opt/recontools/Arjun/arjun.py",
            f"/opt/recontools/XSStrike/xsstrike.py",
            f"/opt/recontools/LinkFinder/linkfinder.py",
            f"/opt/recontools/theHarvester/theHarvester.py",
        ]
        for p in paths:
            if p and os.path.exists(p) and not os.path.isdir(p):
                return p
        return None

    def get_tool(self, name, fallback=None):
        """Return the best path to a tool"""
        info = self.tools_status.get(name)
        if isinstance(info, dict):
            path = info.get('path')
            if path and os.path.exists(path):
                return path
        return fallback or name

    def run_command(self, command, output_file=None, timeout=None, stream=True, label=None, get_code=False):
        """Execute a shell command with optional real-time streaming and output redirection"""
        if self.config.get('jitter'):
            time.sleep(random.uniform(0.1, 0.5))

        timeout = timeout or self.config.get('default_timeout', 300)
        self.logger.debug(f"CMD: {command}")
        
        try:
            if stream and not output_file:
                proc = subprocess.Popen(
                    command, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, universal_newlines=True
                )
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
                                if len(output_lines) <= 50 or len(output_lines) % 100 == 0:
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
                    return -1 if get_code else False
                
                proc.wait()
                return proc.returncode if get_code else (proc.returncode == 0)
                
            elif output_file:
                with open(output_file, 'w') as f:
                    result = subprocess.run(
                        command, shell=True, stdout=f, stderr=subprocess.STDOUT,
                        timeout=timeout, text=True
                    )
                return result.returncode if get_code else (result.returncode == 0)
                
            else:
                result = subprocess.run(
                    command, shell=True, capture_output=True,
                    timeout=timeout, text=True
                )
                return result.returncode if get_code else (result.returncode == 0)
                
        except subprocess.TimeoutExpired:
            print(f"{Colors.RED}[!] Command timed out after {timeout} seconds{Colors.RESET}")
            self.logger.error(f"Timeout: {command}")
            return -1 if get_code else False
        except Exception as e:
            print(f"{Colors.RED}[!] Command failed: {e}{Colors.RESET}")
            self.logger.error(f"Command failed: {e}")
            return -1 if get_code else False

    def run_command_with_retry(self, command, output_file=None, timeout=300, retries=None, label=None):
        """Run command with retry logic"""
        retries = retries or self.config.get('retry_count', 2)
        for attempt in range(retries + 1):
            if self.run_command(command, output_file=output_file, timeout=timeout, label=label):
                return True
            if attempt < retries:
                delay = self.config.get('retry_delay', 5) * (attempt + 1)
                print(f"{Colors.YELLOW}[!] Retry {attempt+1}/{retries} in {delay}s...{Colors.RESET}")
                self.logger.warning(f"Retry {attempt+1}: {command}")
                time.sleep(delay)
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
            with open(output_file, 'w') as f:
                for line in sorted(unique_lines):
                    f.write(f"{line}\n")
            return len(unique_lines)
        except Exception as e:
            print(f"{Colors.RED}[!] Error merging files: {e}{Colors.RESET}")
            self.logger.error(f"Merge error: {e}")
            return 0

    def save_session(self):
        """Save session state to JSON for resume capability"""
        if not self.output_dir:
            return
        session_data = {
            'domain': self.domain,
            'output_dir': self.output_dir,
            'results': self.results,
            'completed_modules': list(self.results.keys()),
            'timestamp': datetime.now().isoformat(),
            'version': VERSION,
        }
        try:
            session_path = Path(self.output_dir) / 'session.json'
            with open(session_path, 'w') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Session save failed: {e}")

    def load_session(self):
        """Load previous session state if available and show diff"""
        session_path = Path(self.output_dir) / 'session.json'
        if session_path.exists():
            try:
                with open(session_path) as f:
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
            
            desc = f"\n[bold white]Full-Spectrum Attack Surface Intelligence  v{VERSION}[/]\n[dim cyan]29 modules  |  5-phase pipeline  |  concurrent execution  |  Kali Linux[/]\n"
            
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
         {Colors.DIM}29 modules  |  5-phase pipeline  |  Kali Linux{Colors.CYAN}
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
        tools_to_check = [
            ('subfinder', 'go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest'),
            ('amass', 'sudo apt install amass'),
            ('assetfinder', 'go install github.com/tomnomnom/assetfinder@latest'),
            ('dnsx', 'go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest'),
            ('httpx', 'go install github.com/projectdiscovery/httpx/cmd/httpx@latest'),
            ('naabu', 'go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest'),
            ('nmap', 'sudo apt install nmap'),
            ('katana', 'go install github.com/projectdiscovery/katana/cmd/katana@latest'),
            ('gau', 'go install github.com/lc/gau@latest'),
            ('waybackurls', 'go install github.com/tomnomnom/waybackurls@latest'),
            ('wafw00f', 'sudo apt install wafw00f'),
            ('whatweb', 'sudo apt install whatweb'),
            ('sqlmap', 'sudo apt install sqlmap'),
            ('nuclei', 'go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest'),
            ('hakrawler', 'go install github.com/hakluke/hakrawler@latest'),
            ('ffuf', 'go install github.com/ffuf/ffuf@latest'),
            ('dalfox', 'go install github.com/hahwul/dalfox/v2@latest'),
            ('asnmap', 'go install github.com/projectdiscovery/asnmap/cmd/asnmap@latest'),
            ('gowitness', 'go install github.com/sensepost/gowitness@latest'),
            ('gf', 'go install github.com/tomnomnom/gf@latest'),
            ('massdns', 'binary expected at /usr/local/bin/massdns'),
        ]

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Tool Installation Status...{Colors.RESET}\n")

        installed_count = 0
        for tool, install_cmd in tools_to_check:
            status = "✔" if self.check_tool_installation(tool, install_cmd) else "✘"
            color = Colors.GREEN if status == "✔" else Colors.RED
            if status == "✔":
                installed_count += 1
            print(f"  {color}[{status}] {tool.capitalize()}{Colors.RESET}")

        special_tools = {
            'paramspider': self.find_tool('paramspider'),
            'arjun': self.find_tool('arjun'),
            'xsstrike': self.find_tool('xsstrike'),
            'smuggler': self.find_tool('smuggler'),
            'linkfinder': self.find_tool('linkfinder'),
            'theharvester': self.find_tool('theharvester'),
            'subzy': self.find_tool('subzy'),
            'kr': self.find_tool('kr'),
        }

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Python/Opt-based Tools...{Colors.RESET}\n")

        for name, path in special_tools.items():
            # Check if hardcoded path exists OR if it's available in system PATH
            path_exists = os.path.exists(path) if isinstance(path, str) and path and os.path.isabs(path) else False
            in_path = self.find_tool(name)
            
            exists = path_exists or bool(in_path)
            
            self.tools_status[name] = {
                'installed': exists,
                'path': path if path_exists else (in_path if in_path else ''),
                'install_command': 'Installed via install.sh or pip'
            }
            status = "✔" if exists else "✘"
            color = Colors.GREEN if exists else Colors.RED
            if exists:
                installed_count += 1
            print(f"  {color}[{status}] {name.capitalize()}{Colors.RESET}")

        total = len(tools_to_check) + len(special_tools)
        print(f"\n{Colors.GREEN}[✔] {installed_count}/{total} tools available{Colors.RESET}")
        if installed_count < total:
            print(f"{Colors.YELLOW}[!] Install missing tools using the suggested commands{Colors.RESET}\n")

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
            Path(self.output_dir).mkdir(exist_ok=True)
            Path(f"{self.output_dir}/logs").mkdir(exist_ok=True)
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
            return False
        return True

    def _require_file(self, filepath, msg="Required file not found"):
        """Check if a file exists and has content"""
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"{Colors.RED}[!] {msg}{Colors.RESET}")
            return False
        return True

    def _require_tool(self, tool_name):
        """Check if a tool is installed"""
        if not self.tools_status.get(tool_name, {}).get('installed'):
            cmd = self.tools_status.get(tool_name, {}).get('install_command', f'Install {tool_name}')
            print(f"{Colors.RED}[!] {tool_name} not installed! {cmd}{Colors.RESET}")
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
                # Scope enforcement
                for h in hosts:
                    if self.domain in h:
                        final_hosts.append(h)
                break
        return final_hosts if final_hosts else [self.domain]

    def _strip_protocol(self, url):
        """Remove http(s):// prefix and trailing path"""
        return url.replace("https://", "").replace("http://", "").split("/")[0]

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


    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 1: SUBDOMAIN ENUMERATION (CONCURRENT)
    # ═══════════════════════════════════════════════════════════════

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
            return
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
            return

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

        if not raw_files:
            print(f"{Colors.RED}[!] All subdomain tools failed!{Colors.RESET}")
            return

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
        except Exception as e:
            print(f"{Colors.RED}[!] Error processing subdomains: {e}{Colors.RESET}")
            self.logger.error(f"Subdomain processing: {e}")

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 2: DNS RESOLUTION
    # ═══════════════════════════════════════════════════════════════

    def run_dns_resolution(self):
        """Run DNS resolution on found subdomains"""
        if not self._require_setup():
            return
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file, "No subdomains found! Run subdomain enumeration first."):
            return
        if not self._require_tool('dnsx'):
            return
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
        else:
            print(f"{Colors.RED}[!] DNS resolution failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 3: ALIVE HOSTS CHECK (httpx JSON)
    # ═══════════════════════════════════════════════════════════════

    def run_alive_hosts_check(self):
        """Check which hosts are alive using HTTPx with JSON parsing"""
        if not self._require_setup():
            return
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file, "No subdomains found! Run subdomain enumeration first."):
            return
        if not self._require_tool('httpx'):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Alive Hosts...{Colors.RESET}\n")
        raw_output = f"{self.output_dir}/httpx_raw.json"
        httpx_bin = self.get_tool('httpx')
        threads = self.config.get('threads', 50)
        rl = self.config.get('rate_limit', 150)
        cmd = (f"{httpx_bin} -l {subs_file} -sc -title -ip -cdn -json "
               f"-threads {threads} -rl {rl} -timeout 10 -o {raw_output}")
        if not self.run_command_with_retry(cmd, timeout=600, label="httpx"):
            print(f"{Colors.RED}[!] HTTPx scan failed{Colors.RESET}")
            return
        clean_hosts = []
        try:
            for line in self.read_file_lines(raw_output):
                try:
                    j = json.loads(line)
                    clean_hosts.append(j["url"])
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception as e:
            print(f"{Colors.RED}[!] Failed parsing HTTPx JSON: {e}{Colors.RESET}")
            return
        alive_file = f"{self.output_dir}/alive.txt"
        with open(alive_file, "w", encoding='utf-8') as f:
            for h in sorted(set(clean_hosts)):
                f.write(h + "\n")
        count = len(set(clean_hosts))
        print(f"{Colors.GREEN}[✔] Found {count} alive hosts{Colors.RESET}")
        if count == 0:
            print(f"{Colors.YELLOW}[*] No alive hosts — will fallback to main domain for scanning{Colors.RESET}")
        else:
            print(f"\n{Colors.CYAN}[*] Sample alive hosts:{Colors.RESET}")
            for h in list(set(clean_hosts))[:5]:
                print(f"  {Colors.WHITE}• {h}{Colors.RESET}")
            if count > 5:
                print(f"  {Colors.DIM}... and {count-5} more{Colors.RESET}")
        self.results['alive_hosts'] = count
        self.save_session()
        self.suggest_next_steps('alive_hosts')

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 4: FAST PORT SCAN (Naabu + CDN detection + Nmap fallback)
    # ═══════════════════════════════════════════════════════════════

    def run_fast_port_scan(self):
        """Run fast port scan with CDN detection and smart fallback"""
        if not self._require_setup():
            return
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
            return

        scanner = "Naabu" if use_naabu else "Nmap"
        output_file = f"{self.output_dir}/ports_fast.txt"

        if use_naabu:
            naabu_bin = self.get_tool('naabu')
            ports = self.config.get('naabu', {}).get('ports', '1-65535')
            rate = self.config.get('naabu', {}).get('rate', 2000)
            cmd = (f"{naabu_bin} -l {final_input} -p {ports} -rate {rate} "
                   f"-scan-all-ips -host-retry 3 -no-color -o {output_file}")
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
        else:
            print(f"{Colors.RED}[!] Fast port scan failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 5: FULL PORT SCAN (Nmap -sV -sC with safe XML parsing)
    # ═══════════════════════════════════════════════════════════════

    def run_full_port_scan(self):
        """Comprehensive port scan with Nmap — fixed XML parsing"""
        if not self._require_setup():
            return
        if not self._require_tool('nmap'):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Full Port Scan with Nmap...{Colors.RESET}")
        print(f"{Colors.YELLOW}[!] This may take a while. Press Ctrl+C to skip.{Colors.RESET}\n")
        hosts = self._get_hosts(prefer_alive=True)
        final_input = f"{self.output_dir}/ports_full_input.txt"
        with open(final_input, 'w', encoding='utf-8') as f:
            for h in hosts:
                f.write(self._strip_protocol(h.strip()) + "\n")
        output_base = f"{self.output_dir}/ports_full"
        nmap_bin = self.get_tool('nmap')
        cmd = f"{nmap_bin} -iL {final_input} -p- -sV -sC -O --open -T4 -oA {output_base}"
        if self.run_command(cmd, timeout=3600, label="nmap"):
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
        else:
            print(f"{Colors.RED}[!] Full port scan failed{Colors.RESET}")


    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 6: URL COLLECTION (CONCURRENT)
    # ═══════════════════════════════════════════════════════════════

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
            return
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
            return

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
            return

        final_output = f"{self.output_dir}/urls.txt"
        try:
            unique_urls = set()
            for fp in raw_files:
                for line in self.read_file_lines(fp):
                    url = line.split('#')[0].strip()
                    if url.startswith(('http://', 'https://')) and not url.endswith(('.jpg', '.png', '.gif', '.css', '.ico')):
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
        except Exception as e:
            print(f"{Colors.RED}[!] Error processing URLs: {e}{Colors.RESET}")
            self.logger.error(f"URL processing: {e}")

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 7: WAF DETECTION (CONCURRENT)
    # ═══════════════════════════════════════════════════════════════

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
            return
        if not self._require_tool('wafw00f'):
            return
        hosts = self._get_hosts(prefer_alive=True)
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting WAF Detection ({len(hosts)} hosts)...{Colors.RESET}\n")
        results = []
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
        waf_count = len([r for r in results if 'WAF' not in r or 'No WAF' in r])
        waf_found = len([r for r in results if ':' in r and 'No WAF' not in r and 'Unknown' not in r and 'Error' not in r and 'Timeout' not in r])
        print(f"{Colors.GREEN}[✔] WAF detection completed{Colors.RESET}")
        print(f"  {Colors.RED}• Hosts with WAF: {waf_found}{Colors.RESET}")
        print(f"  {Colors.GREEN}• Total tested: {len(hosts)}{Colors.RESET}")
        self.results['waf_detected'] = waf_found
        self.results['waf_total'] = len(hosts)
        self.save_session()
        self.suggest_next_steps('waf_detection')

    # ═══════════════════════════════════════════════════════════════
    #  CORE MODULE 8: NUCLEI VULNERABILITY SCAN (FIXED — JSONL parsing)
    # ═══════════════════════════════════════════════════════════════

    def run_vulnerability_scan(self):
        """Run Nuclei with JSONL output for reliable parsing"""
        if not self._require_setup():
            return
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file, "No alive hosts! Run alive hosts check first."):
            return
        if not self._require_tool('nuclei'):
            return
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
        else:
            print(f"{Colors.RED}[!] Nuclei scan failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 10: PARAMETER DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    def run_parameter_discovery(self):
        """Discover parameters using ParamSpider + Arjun"""
        if not self._require_setup():
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Parameter Discovery...{Colors.RESET}\n")
        param_dir = f"{self.output_dir}/parameters"
        Path(param_dir).mkdir(exist_ok=True)
        sd = self.safe_domain()

        if self.tools_status.get('paramspider', {}).get('installed'):
            print(f"{Colors.YELLOW}[*] Running ParamSpider...{Colors.RESET}")
            ps_bin = self.get_tool('paramspider', "/opt/recontools/ParamSpider/paramspider.py")
            cmd = f"python3 {ps_bin} -d {sd} --subs --exclude woff,css,png,jpg,gif,svg --level high -o {param_dir}"
            if self.run_command(cmd, timeout=500, label="paramspider"):
                print(f"{Colors.GREEN}[✔] ParamSpider completed{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] ParamSpider failed{Colors.RESET}")

        if self.tools_status.get('arjun', {}).get('installed'):
            urls_file = f"{self.output_dir}/urls.txt"
            if os.path.exists(urls_file):
                print(f"{Colors.YELLOW}[*] Running Arjun...{Colors.RESET}")
                arjun_bin = self.get_tool('arjun', "/opt/recontools/Arjun/arjun.py")
                output_arjun = f"{param_dir}/arjun.json"
                cmd = f"python3 {arjun_bin} -i {urls_file} -t 20 --json -o {output_arjun}"
                if self.run_command(cmd, timeout=1200, label="arjun"):
                    print(f"{Colors.GREEN}[✔] Arjun completed{Colors.RESET}")

        # Merge results
        final_output = f"{param_dir}/parameters_final.txt"
        found = set()
        ps_file = f"{param_dir}/paramspider.txt"
        if os.path.exists(ps_file):
            for line in self.read_file_lines(ps_file):
                if "=" in line:
                    found.add(line)
        arjun_file = f"{param_dir}/arjun.json"
        if os.path.exists(arjun_file):
            try:
                data = json.load(open(arjun_file, encoding='utf-8'))
                for entry in data:
                    url = entry.get("url", "")
                    base = url.split("?")[0]
                    for p in entry.get("params", []):
                        found.add(f"{base}?{p}=FUZZ")
            except Exception:
                pass
        with open(final_output, 'w', encoding='utf-8') as f:
            for p in sorted(found):
                f.write(p + "\n")
        print(f"{Colors.GREEN}[✔] Parameters discovered: {len(found)}{Colors.RESET}")
        self.results['parameters'] = len(found)
        self.save_session()


    # ═══════════════════════════════════════════════════════════════
    #  MODULE 11: JS ENDPOINT EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def run_js_endpoint_extraction(self):
        """Extract endpoints and secrets from JS files"""
        if not self._require_setup():
            return
        urls_file = f"{self.output_dir}/urls.txt"
        if not self._require_file(urls_file, "No URLs found! Run URL collection first."):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting JS Endpoint Extraction...{Colors.RESET}\n")
        js_dir = f"{self.output_dir}/js_endpoints"
        Path(js_dir).mkdir(exist_ok=True)
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
            return
        print(f"{Colors.YELLOW}[*] Found {js_count} JavaScript files{Colors.RESET}")
        if js_count == 0:
            return
        if self.tools_status.get('linkfinder', {}).get('installed'):
            print(f"{Colors.YELLOW}[*] Running LinkFinder...{Colors.RESET}")
            lf_bin = self.get_tool('linkfinder', "/opt/recontools/LinkFinder/linkfinder.py")
            endpoints_output = f"{js_dir}/endpoints.txt"
            Path(endpoints_output).touch()
            cmd = f"python3 {lf_bin} -i {js_urls_file} -o cli"
            if self.run_command(cmd, output_file=endpoints_output, timeout=600, label="linkfinder"):
                count = self.count_file_lines(endpoints_output)
                print(f"{Colors.GREEN}[✔] LinkFinder extracted {count} endpoints{Colors.RESET}")
                self.results['js_endpoints'] = count
            else:
                print(f"{Colors.RED}[!] LinkFinder failed{Colors.RESET}")
        # Secret extraction
        print(f"{Colors.YELLOW}[*] Scanning JS files for secrets...{Colors.RESET}")
        secrets_file = f"{js_dir}/secrets.txt"
        secret_patterns = {
            "API Key": r"(?i)(api_key|apikey|secret|token|password)[\s]*[=:]*[\s]*['\"]([^'\"]+)['\"]",
            "AWS Key": r"(?i)AKIA[0-9A-Z]{16}",
            "Stripe": r"(?i)sk_live_[0-9a-zA-Z]{24}",
            "Google API": r"(?i)AIza[0-9A-Za-z-_]{35}",
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
        print(f"{Colors.GREEN}[✔] Found {len(set(found_secrets))} potential secrets{Colors.RESET}")
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 12: DIRECTORY FUZZING
    # ═══════════════════════════════════════════════════════════════

    def _fuzz_single_host(self, host, wordlist, ext, status, depth):
        """Worker for concurrent directory fuzzing"""
        host = host if host.startswith('http') else f"http://{host}"
        safe_host = host.replace('://', '_').replace(':', '_').replace('/', '')
        out_file = f"{self.output_dir}/fuzzing/ffuf_{safe_host}.json"
        ffuf_bin = self.get_tool('ffuf')
        cmd = (f"{ffuf_bin} -w {wordlist} -u {host}/FUZZ -e {ext} "
               f"-mc {status} -recursion -recursion-depth {depth} "
               f"-t 40 -o {out_file}")
        if self.run_command(cmd, timeout=900, label=f"ffuf:{safe_host}"):
            return out_file
        return None

    def run_directory_fuzzing(self):
        """Directory fuzzing using FFUF concurrently"""
        if not self._require_setup():
            return
        if not self._require_tool('ffuf'):
            return
        fuzz_dir = f"{self.output_dir}/fuzzing"
        Path(fuzz_dir).mkdir(exist_ok=True)
        hosts = self._get_hosts(prefer_alive=True)
        hosts_to_scan = hosts[:10]  # Limit to top 10 alive hosts to save time
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Directory Fuzzing on {len(hosts_to_scan)} hosts...{Colors.RESET}\n")

        conf = self.config.get('ffuf', {})
        ext = conf.get('extensions', '.php,.html,.txt')
        status = conf.get('status_filter', '200,204,301,302,307,401,403')
        depth = conf.get('recursion_depth', 1)
        wordlist = self.config.get('wordlists', {}).get('dirs')
        if not os.path.exists(wordlist):
            wordlist = self.config.get('wordlists', {}).get('dirs_fallback')
        if not os.path.exists(wordlist):
            print(f"{Colors.RED}[!] Wordlist not found at {wordlist}!{Colors.RESET}")
            return

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self._fuzz_single_host, h, wordlist, ext, status, depth): h for h in hosts_to_scan}
            for future in as_completed(futures):
                h = futures[future]
                res = future.result()
                if res and os.path.exists(res):
                    print(f"{Colors.GREEN}[✔] Fuzzing complete for {h}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}[!] Fuzzing failed for {h}{Colors.RESET}")
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 13: API FUZZING
    # ═══════════════════════════════════════════════════════════════

    def run_api_fuzzing(self):
        """API specific fuzzing using kr (Kiterunner)"""
        if not self._require_setup():
            return
        if not self._require_tool('kr'):
            return
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting API Fuzzing...{Colors.RESET}\n")
        api_dir = f"{self.output_dir}/api_fuzzing"
        Path(api_dir).mkdir(exist_ok=True)
        kr_bin = self.get_tool('kr')
        output = f"{api_dir}/kr_results.txt"
        cmd = f"{kr_bin} scan -i {alive_file} -A routes-large.kite -o text"
        if self.run_command(cmd, output_file=output, timeout=1200, label="kr"):
            print(f"{Colors.GREEN}[✔] API fuzzing completed{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] kr scan failed or routes wordlist missing{Colors.RESET}")
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 14: SUBDOMAIN TAKEOVER CHECK
    # ═══════════════════════════════════════════════════════════════

    def run_subdomain_takeover_check(self):
        """Check for subdomain takeover using subzy"""
        if not self._require_setup():
            return
        subs_file = f"{self.output_dir}/subdomains.txt"
        if not self._require_file(subs_file):
            return
        if not self._require_tool('subzy'):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Checking Subdomain Takeovers...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/takeover"
        Path(out_dir).mkdir(exist_ok=True)
        subzy_bin = self.get_tool('subzy')
        out_file = f"{out_dir}/takeovers.txt"
        cmd = f"{subzy_bin} run --targets {subs_file} --hide_fails"
        if self.run_command(cmd, output_file=out_file, timeout=300, label="subzy"):
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
                    
        with open(cname_file, 'w') as f:
            for t in takeovers:
                f.write(t + "\n")
                
        if takeovers:
            print(f"{Colors.YELLOW}[!] Found {len(takeovers)} external CNAMEs pointing outside domain!{Colors.RESET}")
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 15: ADVANCED URL ENUMERATION (hakrawler)
    # ═══════════════════════════════════════════════════════════════

    def run_advanced_url_enum(self):
        if not self._require_setup():
            return
        if not self._require_tool('hakrawler'):
            return
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Advanced URL Enum (Hakrawler)...{Colors.RESET}\n")
        out_file = f"{self.output_dir}/hakrawler.txt"
        cmd = f"{self.get_tool('hakrawler')} -list {alive_file} -depth 2 -plain"
        if self.run_command(cmd, output_file=out_file, timeout=600, stream=False, label="hakrawler"):
            print(f"{Colors.GREEN}[✔] Hakrawler completed: {self.count_file_lines(out_file)} URLs{Colors.RESET}")
            self.merge_all_urls()
        else:
            print(f"{Colors.RED}[!] Hakrawler failed{Colors.RESET}")

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

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 16: SCREENSHOT CAPTURE (gowitness)
    # ═══════════════════════════════════════════════════════════════

    def run_screenshot_capture(self):
        if not self._require_setup() or not self._require_tool('gowitness'):
            return
        alive_file = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive_file):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Capturing Screenshots...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/screenshots"
        Path(out_dir).mkdir(exist_ok=True)
        cmd = f"{self.get_tool('gowitness')} file -f {alive_file} -P {out_dir} --timeout 15"
        if self.run_command(cmd, timeout=600, label="gowitness"):
            imgs = len(list(Path(out_dir).glob("*.png")))
            print(f"{Colors.GREEN}[✔] Captured {imgs} screenshots in {out_dir}{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] Gowitness failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 17: DNS BRUTEFORCE
    # ═══════════════════════════════════════════════════════════════

    def run_dns_bruteforce(self):
        if not self._require_setup() or not self._require_tool('massdns'):
            return
        resolvers = self.config.get('wordlists', {}).get('resolvers')
        if not self._require_file(resolvers, "Resolvers list not found!"):
            return
        wordlist = self.config.get('wordlists', {}).get('dns')
        if not self._require_file(wordlist, "DNS wordlist not found!"):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting DNS Bruteforce...{Colors.RESET}\n")
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
            return
        out = f"{self.output_dir}/massdns_out.txt"
        cmd = f"{self.get_tool('massdns')} -r {resolvers} -t A -o S -w {out} {fqdn_file}"
        if self.run_command(cmd, timeout=1200, label="massdns"):
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
                new_found = len(merged) - len(existing)
                with open(subs_file, 'w', encoding='utf-8') as f:
                    for s in sorted(merged):
                        f.write(s + '\n')
                print(f"{Colors.GREEN}[✔] DNS bruteforce — {len(new_subs)} resolved, {new_found} new subdomains added{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[✔] DNS bruteforce completed — no new subdomains found{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] DNS bruteforce failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 18: GF FILTERS
    # ═══════════════════════════════════════════════════════════════

    def run_gf_filters(self):
        if not self._require_setup() or not self._require_tool('gf'):
            return
        urls = f"{self.output_dir}/urls_final.txt"
        if not os.path.exists(urls):
            urls = f"{self.output_dir}/urls.txt"
        if not self._require_file(urls, "No URLs found!"):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Running GF Filters...{Colors.RESET}\n")
        gf_dir = f"{self.output_dir}/gf"
        Path(gf_dir).mkdir(exist_ok=True)
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

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 19: TECH SCAN (WhatWeb)
    # ═══════════════════════════════════════════════════════════════

    def run_tech_scan(self):
        if not self._require_setup() or not self._require_tool('whatweb'):
            return
        alive = f"{self.output_dir}/alive.txt"
        if not self._require_file(alive):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Tech Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/tech_scan"
        Path(out_dir).mkdir(exist_ok=True)
        out_file = f"{out_dir}/whatweb_results.json"
        cmd = f"{self.get_tool('whatweb')} -i {alive} --log-json={out_file}"
        if self.run_command(cmd, timeout=300, label="whatweb"):
            print(f"{Colors.GREEN}[✔] WhatWeb scan completed{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] WhatWeb scan failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 20: SQLI SCAN (SQLMap)
    # ═══════════════════════════════════════════════════════════════

    def run_sqlmap_scan(self):
        if not self._require_setup() or not self._require_tool('sqlmap'):
            return
        gf_sqli = f"{self.output_dir}/gf/sqli.txt"
        if not self._require_file(gf_sqli, "No SQLi parameterized URLs found by GF!"):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting SQLMap Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/sqlmap"
        cmd = f"{self.get_tool('sqlmap')} -m {gf_sqli} --batch --random-agent --level 1 --risk 1 --output-dir={out_dir}"
        if self.run_command(cmd, timeout=1200, label="sqlmap"):
            print(f"{Colors.GREEN}[✔] SQLMap scan completed{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] SQLMap scan failed{Colors.RESET}")


    # ═══════════════════════════════════════════════════════════════
    #  MODULE 21: XSS SCAN (Dalfox)
    # ═══════════════════════════════════════════════════════════════

    def run_xss_scan(self):
        """Automated XSS scanning using Dalfox"""
        if not self._require_setup() or not self._require_tool('dalfox'):
            return
        gf_xss = f"{self.output_dir}/gf/xss.txt"
        if not os.path.exists(gf_xss):
            self.run_gf_filters()
        if not self._require_file(gf_xss, "No XSS parameterized URLs found! Run GF filters first."):
            return

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Automated XSS Scan (Dalfox)...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/xss_findings"
        Path(out_dir).mkdir(exist_ok=True)
        out_file = f"{out_dir}/dalfox_results.txt"

        dalfox_bin = self.get_tool('dalfox')
        cmd = f"{dalfox_bin} file {gf_xss} -b hahwul.xss.ht --skip-bav -o {out_file}"
        if self.run_command(cmd, timeout=1800, label="dalfox"):
            count = self.count_file_lines(out_file)
            print(f"{Colors.GREEN}[✔] Dalfox XSS scan completed — {count} potential findings{Colors.RESET}")
            self.results['xss_findings'] = count
            self.save_session()
        else:
            print(f"{Colors.RED}[!] Dalfox scan failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 22: CORS SCANNER
    # ═══════════════════════════════════════════════════════════════

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
            return
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
        Path(out_dir).mkdir(exist_ok=True)
        with open(f"{out_dir}/cors_results.txt", 'w') as f:
            for r in all_results:
                f.write(r + '\n')
        vuln_count = len([r for r in all_results if '[VULN]' in r])
        warn_count = len([r for r in all_results if '[WARN]' in r])
        print(f"{Colors.GREEN}[✔] CORS Scan completed — {vuln_count} VULN, {warn_count} WARN, {len(all_results)} total findings{Colors.RESET}")
        self.results['cors_findings'] = vuln_count
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 23: HTTP SMUGGLING
    # ═══════════════════════════════════════════════════════════════

    def run_http_smuggling(self):
        """Smuggler integration for HTTP request smuggling"""
        if not self._require_setup() or not self._require_tool('smuggler'):
            return
        hosts = self._get_hosts(prefer_alive=True)
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting HTTP Smuggling Scan ({len(hosts)} targets)...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/smuggling"
        Path(out_dir).mkdir(exist_ok=True)
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
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 24: ASN DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    def run_asn_discovery(self):
        """Discover ASN and IP ranges using asnmap"""
        if not self._require_setup() or not self._require_tool('asnmap'):
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting ASN & IP Range Discovery...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/asn"
        Path(out_dir).mkdir(exist_ok=True)
        asnmap_bin = self.get_tool('asnmap')
        sd = self.safe_domain()
        cmd = f"{asnmap_bin} -d {sd} -silent"
        if self.run_command(cmd, output_file=f"{out_dir}/asn_ranges.txt", timeout=60, label="asnmap"):
            count = self.count_file_lines(f"{out_dir}/asn_ranges.txt")
            print(f"{Colors.GREEN}[✔] ASN Discovery completed — found {count} CIDR ranges{Colors.RESET}")
            if count > 0:
                print(f"{Colors.YELLOW}[!] Use these ranges in Nmap for full attack surface scanning{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] ASN Discovery failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  ORCHESTRATION: FULL AND DEEP RECON
    # ═══════════════════════════════════════════════════════════════


    # ═══════════════════════════════════════════════════════════════
    #  MODULE 25: CLOUD ASSET DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    def run_cloud_asset_discovery(self):
        """Discover S3 buckets, GCP/Azure blobs associated with domain"""
        if not self._require_setup():
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Cloud Asset Discovery...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/cloud"
        Path(out_dir).mkdir(exist_ok=True)
        # Using simple permutations for S3 bucket checking
        baseword = self.domain.split('.')[0]
        perms = [
            baseword, f"{baseword}-dev", f"{baseword}-staging",
            f"{baseword}-prod", f"{baseword}-assets", f"{baseword}-cdn",
            f"{baseword}-backup", f"{baseword}-logs", f"{baseword}-data",
        ]
        s3_found, gcp_found, azure_found = [], [], []
        # urllib.request imported at top level
        def check_s3(name):
            url = f"https://{name}.s3.amazonaws.com"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("s3", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return ("s3", f"[EXISTS/PRIVATE] {url}")
            except Exception:
                pass
            return None
        def check_gcp(name):
            url = f"https://storage.googleapis.com/{name}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("gcp", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return ("gcp", f"[EXISTS/PRIVATE] {url}")
            except Exception:
                pass
            return None
        def check_azure(name):
            url = f"https://{name}.blob.core.windows.net"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return ("azure", f"[OPEN] {url}")
            except urllib.error.HTTPError as e:
                if e.code in (400, 403, 404):
                    return ("azure", f"[EXISTS] {url}")
            except Exception:
                pass
            return None
        all_checks = [(check_s3, p) for p in perms] + [(check_gcp, p) for p in perms] + [(check_azure, p) for p in perms]
        found_buckets = []
        with ThreadPoolExecutor(max_workers=15) as ex:
            futs = {ex.submit(fn, p): (fn.__name__, p) for fn, p in all_checks}
            for fut in as_completed(futs):
                res = fut.result()
                if res:
                    found_buckets.append(res[1])
                    print(f"  {Colors.YELLOW}{res[1]}{Colors.RESET}")
                    
        with open(f"{out_dir}/s3_buckets.txt", 'w') as f:
            for b in found_buckets:
                f.write(b + '\n')
        print(f"{Colors.GREEN}[✔] Cloud Discovery completed — found {len(found_buckets)} buckets{Colors.RESET}")
        self.save_session()

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 26: GITHUB DORKING
    # ═══════════════════════════════════════════════════════════════

    def run_github_dorking(self):
        """Search GitHub for leaked secrets related to domain"""
        if not self._require_setup():
            return
        gh_token = self.config.get('api_keys', {}).get('github', '')
        if not gh_token:
            print(f"{Colors.RED}[!] GitHub API token not found in config.yaml!{Colors.RESET}")
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting GitHub Secret Scanning...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/github"
        Path(out_dir).mkdir(exist_ok=True)
        
        # urllib.request/json imported at top level
        headers = {'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github.v3+json'}
        query = urllib.parse.quote(f'"{self.domain}" password OR secret OR key OR token')
        url = f'https://api.github.com/search/code?q={query}&per_page=10'
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read())
                items = data.get('items', [])
                with open(f"{out_dir}/github_secrets.txt", 'w') as f:
                    for item in items:
                        repo = item.get('repository', {}).get('full_name', '')
                        file = item.get('path', '')
                        html_url = item.get('html_url', '')
                        entry = f"Repo: {repo} | File: {file} | URL: {html_url}"
                        f.write(entry + '\n')
                        print(f"  {Colors.YELLOW}• {repo}/{file}{Colors.RESET}")
                print(f"{Colors.GREEN}[✔] Found {len(items)} potentially interesting files on GitHub{Colors.RESET}")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"{Colors.RED}[!] GitHub API Rate limit exceeded or invalid token.{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] GitHub API Error: {e}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] GitHub Dorking failed: {e}{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 27: OSINT HARVESTING (theHarvester)
    # ═══════════════════════════════════════════════════════════════

    def run_osint_harvesting(self):
        """Gather emails and OSINT using theHarvester"""
        if not self._require_setup():
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting OSINT Harvesting...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/osint"
        Path(out_dir).mkdir(exist_ok=True)
        bin_path = self.get_tool('theHarvester', '/opt/recontools/theHarvester/theHarvester.py')
        out_file = f"{out_dir}/theharvester.html"
        cmd = f"python3 {bin_path} -d {self.safe_domain()} -b all -f {out_file}"
        if self.run_command(cmd, timeout=600, label="harvester"):
            print(f"{Colors.GREEN}[✔] OSINT Harvesting completed{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] OSINT Harvesting failed{Colors.RESET}")

    # ═══════════════════════════════════════════════════════════════
    #  MODULE 28: SHODAN INTEGRATION
    # ═══════════════════════════════════════════════════════════════

    def run_shodan_integration(self):
        """Passive IP/Port recon via Shodan API"""
        if not self._require_setup():
            return
        shodan_key = self.config.get('api_keys', {}).get('shodan', '')
        if not shodan_key:
            print(f"{Colors.RED}[!] Shodan API key not found in config.yaml!{Colors.RESET}")
            return
        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Passive Shodan Recon...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/shodan"
        Path(out_dir).mkdir(exist_ok=True)
        # urllib.request/json imported at top level
        url = f'https://api.shodan.io/shodan/host/search?key={shodan_key}&query=hostname:{self.safe_domain()}'
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read())
                matches = data.get('matches', [])
                with open(f"{out_dir}/shodan_results.txt", 'w') as f:
                    for m in matches:
                        ip = m.get('ip_str')
                        port = m.get('port')
                        org = m.get('org', '')
                        entry = f"{ip}:{port} ({org})"
                        f.write(entry + '\n')
                        print(f"  {Colors.YELLOW}• {entry}{Colors.RESET}")
                print(f"{Colors.GREEN}[✔] Found {len(matches)} open ports via Shodan{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Shodan API Error: {e}{Colors.RESET}")


    # ═══════════════════════════════════════════════════════════════
    #  MODULE 29: OPEN REDIRECT SCANNER
    # ═══════════════════════════════════════════════════════════════

    def run_open_redirect_scan(self):
        """Scan for open redirects using GF filtered URLs"""
        if not self._require_setup():
            return
        gf_redirect = f"{self.output_dir}/gf/redirect.txt"
        if not os.path.exists(gf_redirect):
            self.run_gf_filters()
        if not self._require_file(gf_redirect, "No redirect parameterized URLs found! Run GF filters first."):
            return

        print(f"\n{Colors.CYAN}{Colors.BOLD}[*] Starting Open Redirect Scan...{Colors.RESET}\n")
        out_dir = f"{self.output_dir}/redirects"
        Path(out_dir).mkdir(exist_ok=True)
        out_file = f"{out_dir}/open_redirects.txt"

        # Basic fuzzing for redirects using standard payload
        # This could be improved with a full tool like Oralyzer, but simple requests work well too.
        urls = self.read_file_lines(gf_redirect)
        payloads = ["https://evil.com", "//evil.com", "/\\evil.com"]
        found = []
        def check_redirect(url):
            for payload in payloads:
                target = re.sub(r'=[^&]+', f'={payload}', url)
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
        
        with open(out_file, 'w') as f:
            for r in found:
                f.write(r + '\n')
        print(f"{Colors.GREEN}[✔] Open Redirect Scan completed — {len(found)} vulnerabilities found{Colors.RESET}")
        self.save_session()

    def run_full_automated_recon(self):
        """Run the core Oculus chain"""
        if not self._require_setup():
            return
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
            try:
                step()
            except Exception as e:
                self.logger.error(f"Auto-recon step failed: {e}")
        self.show_diff()
        self.generate_summary()
        self.generate_html_report()
        self.generate_json_report()
        print(f"\n{Colors.GREEN}{Colors.BOLD}[✔] FULL AUTOMATED RECON COMPLETED!{Colors.RESET}\n")

    def run_deep_recon_mode(self):
        """Run all advanced modules"""
        if not self._require_setup():
            return
        print(f"\n{Colors.MAGENTA}{Colors.BOLD}╔══════════════════════════════════════════════════════╗")
        print(f"║               STARTING DEEP RECON MODE               ║")
        print(f"╚══════════════════════════════════════════════════════╝{Colors.RESET}\n")
        confirm = self.config.get('auto_confirm', False)
        if not confirm:
            yn = input(f"{Colors.YELLOW}[!] Deep Recon will run 10+ advanced tools and take a very long time. Continue? (y/n): {Colors.RESET}")
            if yn.lower() != 'y':
                return
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
            try:
                step()
            except Exception as e:
                self.logger.error(f"Deep recon step failed: {e}")
        self.show_diff()
        self.generate_summary()
        print(f"\n{Colors.GREEN}{Colors.BOLD}[+] DEEP RECON COMPLETED!{Colors.RESET}\n")

    def run_full_spectrum_scan(self):
        """Run every single Oculus module in perfect dependency order with concurrency where safe.
        
        Pipeline Architecture:
        
        PHASE 1 - DISCOVERY (Foundation)
            [Sequential] Subdomain Enum -> DNS Bruteforce (merges back) -> DNS Resolution -> Alive Hosts
            [Concurrent]  ASN Discovery + Cloud Assets + OSINT + Shodan + GitHub Dorking (independent, domain-only)
        
        PHASE 2 - INFRASTRUCTURE ANALYSIS
            [Concurrent]  Fast Port Scan + Full Port Scan + Tech Scan + WAF Detection + Screenshots
            (all need alive.txt, none depend on each other)
        
        PHASE 3 - CONTENT DISCOVERY
            [Sequential]  URL Collection -> Advanced URL Enum (produces urls_final.txt)
            [Concurrent]  Parameter Discovery + JS Endpoint Extraction (need urls.txt)
            [Sequential]  Subdomain Takeover Check (needs subdomains.txt)
        
        PHASE 4 - VULNERABILITY ANALYSIS
            [Sequential]  Nuclei Vulnerability Scan (needs alive.txt)
            [Sequential]  GF Filters (needs urls_final.txt, gates Phase 5)
            [Concurrent]  Directory Fuzzing + API Fuzzing (need alive.txt, independent)
        
        PHASE 5 - TARGETED EXPLOITATION
            [Concurrent]  SQLi Scan + XSS Scan + Open Redirect Scan (all need gf/*.txt)
            [Concurrent]  CORS Scanner + HTTP Smuggling (need alive.txt, independent)
        """
        if not self._require_setup():
            return
        
        confirm = self.config.get('auto_confirm', False)
        if not confirm:
            print(f"\n{Colors.MAGENTA}{Colors.BOLD}")
            print(f"  FULL SPECTRUM SCAN will run ALL 29 modules across 5 phases.")
            print(f"  This covers Recon, Infrastructure, Discovery, Vulnerability, and Exploitation.")
            print(f"  Estimated runtime: 2-6 hours depending on target size and tool availability.")
            print(f"{Colors.RESET}")
            yn = input(f"{Colors.YELLOW}[!] Launch Full Spectrum Scan on {self.domain}? (y/n): {Colors.RESET}")
            if yn.lower().strip() != 'y':
                return
        
        start_time = time.time()
        
        print(f"\n{Colors.MAGENTA}{Colors.BOLD}")
        print(f"======================================================================")
        print(f"   FULL SPECTRUM SCAN -- {self.domain}")
        print(f"======================================================================")
        print(f"{Colors.RESET}\n")
        
        # Thread-safe tracking lists
        _lock = threading.Lock()
        failed_steps = []
        completed_steps = []
        aborted = False
        
        def _run_step(name, func):
            """Run a single step with error handling and thread-safe tracking"""
            nonlocal aborted
            if aborted:
                return
            try:
                print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}")
                print(f"  STEP: {name}")
                print(f"{'='*60}{Colors.RESET}")
                func()
                with _lock:
                    completed_steps.append(name)
            except KeyboardInterrupt:
                aborted = True
                print(f"\n{Colors.YELLOW}[!] Ctrl+C detected during: {name} -- aborting pipeline{Colors.RESET}")
            except Exception as e:
                with _lock:
                    failed_steps.append((name, str(e)))
                self.logger.error(f"Full Spectrum step failed [{name}]: {e}")
                print(f"{Colors.RED}[!] STEP FAILED: {name} -- {e}{Colors.RESET}")
        
        def _run_concurrent(step_list):
            """Run multiple steps concurrently using threads"""
            nonlocal aborted
            if aborted:
                return
            if not self.config.get('parallel', True) or len(step_list) <= 1:
                for name, func in step_list:
                    if aborted:
                        break
                    _run_step(name, func)
                return
            
            names = ', '.join(n for n, _ in step_list)
            print(f"\n{Colors.CYAN}[*] Running {len(step_list)} tasks concurrently: {names}{Colors.RESET}")
            with ThreadPoolExecutor(max_workers=len(step_list)) as executor:
                futures = {executor.submit(_run_step, name, func): name for name, func in step_list}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        pass  # Already handled inside _run_step
        
        try:
            # ── PHASE 1: DISCOVERY (Foundation) ──────────────────────────
            print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 1/5: DISCOVERY ---{Colors.RESET}")
            
            # Sequential: subdomain pipeline (each feeds the next)
            _run_step("Subdomain Enumeration", self.run_subdomain_enumeration)
            _run_step("DNS Bruteforce", self.run_dns_bruteforce)
            _run_step("DNS Resolution", self.run_dns_resolution)
            _run_step("Alive Hosts Check", self.run_alive_hosts_check)
            
            # Concurrent: independent domain-only tasks
            _run_concurrent([
                ("ASN Discovery", self.run_asn_discovery),
                ("Cloud Asset Discovery", self.run_cloud_asset_discovery),
                ("OSINT Harvesting", self.run_osint_harvesting),
                ("Shodan Recon", self.run_shodan_integration),
                ("GitHub Dorking", self.run_github_dorking),
            ])
            
            self.save_session()
            
            # ── PHASE 2: INFRASTRUCTURE ANALYSIS ─────────────────────────
            if not aborted:
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 2/5: INFRASTRUCTURE ---{Colors.RESET}")
                
                # Concurrent: all need alive.txt but are independent of each other
                _run_concurrent([
                    ("Fast Port Scan", self.run_fast_port_scan),
                    ("Full Port Scan", self.run_full_port_scan),
                    ("Tech Scan", self.run_tech_scan),
                    ("WAF Detection", self.run_waf_detection),
                    ("Screenshot Capture", self.run_screenshot_capture),
                ])
                
                self.save_session()
            
            # ── PHASE 3: CONTENT DISCOVERY ───────────────────────────────
            if not aborted:
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 3/5: CONTENT DISCOVERY ---{Colors.RESET}")
                
                # URL Collection first (produces urls.txt needed by params/JS)
                _run_step("URL Collection", self.run_url_collection)
                _run_step("Advanced URL Enum", self.run_advanced_url_enum)
                
                # Concurrent: both need urls.txt, independent of each other
                _run_concurrent([
                    ("Parameter Discovery", self.run_parameter_discovery),
                    ("JS Endpoint Extraction", self.run_js_endpoint_extraction),
                ])
                
                # Subdomain takeover only needs subdomains.txt (already available)
                _run_step("Subdomain Takeover Check", self.run_subdomain_takeover_check)
                
                self.save_session()
            
            # ── PHASE 4: VULNERABILITY ANALYSIS ──────────────────────────
            if not aborted:
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 4/5: VULNERABILITY ANALYSIS ---{Colors.RESET}")
                
                # Nuclei (needs alive.txt)
                _run_step("Vulnerability Scan (Nuclei)", self.run_vulnerability_scan)
                
                # GF Filters (needs urls_final.txt, gates SQLi/XSS/Redirect scans)
                _run_step("GF Filters", self.run_gf_filters)
                
                # Concurrent: fuzzing tasks (both need alive.txt, independent)
                _run_concurrent([
                    ("Directory Fuzzing", self.run_directory_fuzzing),
                    ("API Fuzzing", self.run_api_fuzzing),
                ])
                
                self.save_session()
            
            # ── PHASE 5: TARGETED EXPLOITATION ───────────────────────────
            if not aborted:
                print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- PHASE 5/5: TARGETED EXPLOITATION ---{Colors.RESET}")
                
                # Concurrent: all GF-dependent scans (need gf/*.txt)
                _run_concurrent([
                    ("SQLi Scan", self.run_sqlmap_scan),
                    ("XSS Scan (Dalfox)", self.run_xss_scan),
                    ("Open Redirect Scan", self.run_open_redirect_scan),
                ])
                
                # Concurrent: network-level vuln scans (need alive.txt)
                _run_concurrent([
                    ("CORS Scanner", self.run_cors_scan),
                    ("HTTP Smuggling", self.run_http_smuggling),
                ])
                
                self.save_session()
                
        except KeyboardInterrupt:
            aborted = True
            print(f"\n{Colors.YELLOW}[!] Scan aborted by user (Ctrl+C){Colors.RESET}")
        
        # ── FINAL: REPORTING (always runs, even on abort) ────────────
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
        print(f"  {Colors.GREEN}Completed   : {len(completed_steps)} steps{Colors.RESET}")
        if failed_steps:
            print(f"  {Colors.RED}Failed      : {len(failed_steps)} steps{Colors.RESET}")
            for name, err in failed_steps:
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
                f.write("                        OCULUS v3 SUMMARY REPORT\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Target Domain: {self.domain}\n")
                f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if duration:
                    f.write(f"Total Duration: {duration} seconds\n")
                f.write(f"Output Directory: {self.output_dir}\n\n")
                f.write("-" * 80 + "\n")
                f.write("                           DISCOVERY RESULTS\n")
                f.write("-" * 80 + "\n\n")
                metrics = [
                    ('Subdomains Discovered', 'subdomains', f'{self.output_dir}/subdomains.txt'),
                    ('DNS Records Resolved', 'dns_resolved', f'{self.output_dir}/dns_resolved.txt'),
                    ('Alive Hosts Found', 'alive_hosts', f'{self.output_dir}/alive.txt'),
                    ('Open Ports (Fast)', 'fast_ports', f'{self.output_dir}/ports_fast.txt'),
                    ('Service Details (Full)', 'full_ports', f'{self.output_dir}/ports_full.txt'),
                    ('URLs Collected', 'urls', f'{self.output_dir}/urls.txt'),
                    ('JS Endpoints', 'js_endpoints', f'{self.output_dir}/js_endpoints/endpoints.txt'),
                    ('Parameters Discovered', 'parameters', f'{self.output_dir}/parameters/parameters_final.txt'),
                    ('API Endpoints Fuzzed', 'api_fuzz', f'{self.output_dir}/api_fuzzing/'),
                    ('ASN IP Ranges', 'asn_ranges', f'{self.output_dir}/asn/asn_ranges.txt'),
                    ('XSS Findings', 'xss_findings', f'{self.output_dir}/xss_findings/'),
                    ('CORS Findings', 'cors_findings', f'{self.output_dir}/cors_findings/'),
                    ('Takeover Findings', 'takeover', f'{self.output_dir}/takeover/'),
                    ('SQLMap Scanned', 'sqlmap', f'{self.output_dir}/sqlmap/'),
                    ('Tech Scan Results', 'tech_scan', f'{self.output_dir}/tech_scan/'),
                ]
                for label, key, path in metrics:
                    val = self.results.get(key, 0)
                    f.write(f"{label}: {val}\n")
                    if val:
                        f.write(f"  • {path}\n")
                # WAF
                waf_d = self.results.get('waf_detected', 0)
                waf_t = self.results.get('waf_total', 0)
                f.write(f"WAF Protected: {waf_d}/{waf_t}\n")
                # Vulns
                vulns = self.results.get('vulnerabilities', 0)
                if vulns:
                    f.write(f"Vulnerabilities: {vulns}\n")
                    f.write(f"  • Critical: {self.results.get('critical_vulns', 0)}\n")
                    f.write(f"  • High: {self.results.get('high_vulns', 0)}\n")
                # GF
                gf = self.results.get('gf_filters', {})
                if gf:
                    f.write("GF Findings:\n")
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
                if val:
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
        alive = self.read_file_lines(f"{self.output_dir}/alive.txt")
        ports = self.read_file_lines(f"{self.output_dir}/ports_full.txt")
        if not ports:
            ports = self.read_file_lines(f"{self.output_dir}/ports_fast.txt")
        params = self.read_file_lines(f"{self.output_dir}/parameters/parameters_final.txt")
        urls = self.read_file_lines(f"{self.output_dir}/urls_final.txt")
        
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
        screenshots = []
        if screenshots_dir.exists():
            screenshots = list(screenshots_dir.glob("*.png"))

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oculus Report — {self.domain}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#e0e0e0;font-family:'Courier New',monospace;padding:20px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{color:#00ffcc;font-size:28px;border-bottom:2px solid #00ffcc;padding-bottom:10px;margin-bottom:20px}}
h2{{color:#00aaff;font-size:20px;margin:25px 0 10px}}
.card{{background:#12121a;border:1px solid #1a1a2e;border-radius:8px;padding:15px;margin:10px 0}}
.stat{{display:inline-block;background:#1a1a2e;border-radius:6px;padding:12px 20px;margin:5px;text-align:center;min-width:150px}}
.stat .num{{font-size:24px;font-weight:bold;color:#00ffcc}}
.stat .label{{font-size:11px;color:#888;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th{{background:#1a1a2e;color:#00aaff;padding:8px;text-align:left;font-size:12px;cursor:pointer}}
th:hover{{background:#2a2a3e}}
td{{padding:6px 8px;border-bottom:1px solid #1a1a2e;font-size:12px;word-break:break-all}}
tr:hover{{background:#1a1a2e}}
.critical{{color:#ff4444;font-weight:bold}} .high{{color:#ff8800}} .medium{{color:#ffcc00}} .low{{color:#44cc44}} .info{{color:#4488ff}}
details{{margin:5px 0}} summary{{cursor:pointer;color:#00aaff;padding:5px;font-weight:bold}}
.gallery{{display:flex;flex-wrap:wrap;gap:10px}}
.gallery img{{max-width:250px;border:1px solid #1a1a2e;border-radius:4px;cursor:pointer}}
.gallery img:hover{{border-color:#00ffcc}}
.chart-container{{width:400px;margin:0 auto;padding:20px}}
</style></head><body><div class="container">
<h1>⚡ Oculus v{VERSION} — {self.domain}</h1>
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

            html += """<h2>🔴 Vulnerabilities</h2><div class="card">
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
            html += f'<details><summary>📸 Screenshots ({len(screenshots)})</summary><div class="card gallery">'
            for img in screenshots[:50]:
                rel_path = f"screenshots/{img.name}"
                html += f'<a href="{rel_path}" target="_blank"><img src="{rel_path}" loading="lazy" alt="Screenshot"></a>'
            if len(screenshots) > 50:
                html += f'<p>... and {len(screenshots)-50} more in screenshots/ directory</p>'
            html += '</div></details>'

        sections = [
            ("📡 Subdomains", subs, 200),
            ("🟢 Alive Hosts", alive, 200),
            ("🔌 Open Ports", ports, 200),
            ("🔗 URLs", urls, 200),
            ("📝 Parameters", params, 200)
        ]
        
        for title, data, limit in sections:
            if data:
                html += f'<details><summary>{title} ({len(data)})</summary><div class="card">'
                for item in data[:limit]:
                    html += f'{item}<br>'
                if len(data) > limit:
                    html += f'<br><i>... and {len(data)-limit} more</i>'
                html += '</div></details>'

        html += f'<p style="color:#333;margin-top:40px;text-align:center">Generated by Oculus v{VERSION}</p></div></body></html>'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"{Colors.GREEN}[✔] Enhanced HTML report: {report_path}{Colors.RESET}")

    def generate_json_report(self):
        """Generate machine-readable JSON report"""
        if not self._require_setup():
            return
        report = {
            'domain': self.domain,
            'version': VERSION,
            'scan_date': datetime.now().isoformat(),
            'results': self.results,
            'subdomains': self.read_file_lines(f"{self.output_dir}/subdomains.txt"),
            'alive_hosts': self.read_file_lines(f"{self.output_dir}/alive.txt"),
            'urls': self.read_file_lines(f"{self.output_dir}/urls_final.txt")[:500],
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
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Oculus Report — {self.domain}\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Version:** {VERSION}\n\n---\n\n")
            f.write("## Summary\n\n| Metric | Count |\n|---|---|\n")
            for k, v in self.results.items():
                if isinstance(v, (int, float)):
                    f.write(f"| {k.replace('_', ' ').title()} | {v} |\n")
            f.write("\n---\n\n")
            # Vulns
            vulns_file = f"{self.output_dir}/nuclei_output.txt"
            if os.path.exists(vulns_file):
                lines = self.read_file_lines(vulns_file)
                if lines:
                    f.write("## Vulnerabilities\n\n```\n")
                    for l in lines[:50]:
                        f.write(l + "\n")
                    f.write("```\n\n")
            # Alive
            alive = self.read_file_lines(f"{self.output_dir}/alive.txt")
            if alive:
                f.write(f"## Alive Hosts ({len(alive)})\n\n")
                for a in alive[:30]:
                    f.write(f"- {a}\n")
                f.write("\n")
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
                "[U]", "[bold bright_red]Full Spectrum Scan (All 29)[/]",
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
            print(f"{Colors.YELLOW}[ AUTOMATION & SYSTEM ]{Colors.RESET}")
            print("9. Full Auto   | D. Deep Recon  | U. Full Spectrum| C. Domain     | Q. Quit")
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
                    dispatch[choice]()
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
    parser.add_argument('--full-recon', action='store_true', help='Run full automated recon')
    parser.add_argument('--deep', action='store_true', help='Run deep recon mode')
    parser.add_argument('--module', help='Comma-separated modules: subdomain,dns,alive,ports,urls,waf,vuln,xss,cors,asn')
    parser.add_argument('--no-confirm', action='store_true', help='Skip all confirmation prompts')
    parser.add_argument('--threads', type=int, help='Thread count')
    parser.add_argument('--timeout', type=int, help='Default timeout in seconds')
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
}


def main():
    """Main entry point with CLI support"""
    parser = build_parser()
    args = parser.parse_args()

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
        Path(recon.output_dir).mkdir(exist_ok=True)
        Path(f"{recon.output_dir}/logs").mkdir(exist_ok=True)
        recon._setup_logging_full()
        recon.setup_complete = True
        recon.load_session()

        if args.full_recon:
            recon.run_full_automated_recon()
        elif args.deep:
            recon.run_deep_recon_mode()
        elif args.module:
            modules = [m.strip() for m in args.module.split(',')]
            for mod in modules:
                method = MODULE_MAP.get(mod)
                if method and hasattr(recon, method):
                    print(f"\n{Colors.CYAN}[*] Running module: {mod}{Colors.RESET}")
                    getattr(recon, method)()
                else:
                    print(f"{Colors.RED}[!] Unknown module: {mod}{Colors.RESET}")
                    print(f"    Available: {', '.join(MODULE_MAP.keys())}")
        else:
            recon.run()
    else:
        # Interactive mode
        try:
            recon.run()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}[!] Interrupted. Goodbye!{Colors.RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"\n{Colors.RED}[!] Fatal error: {e}{Colors.RESET}")
            sys.exit(1)


if __name__ == "__main__":
    main()