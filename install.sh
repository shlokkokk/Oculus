#!/bin/bash
# Oculus v4.1 — Professional Installation Engine
# Hardened · Idempotent · Docker & CI Compatible

# Failsafe: Ensure we are running in Bash
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

set -o pipefail

# Color Palette
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
CYAN="\033[1;36m"
MAGENTA="\033[1;35m"
DIM="\033[2m"
BOLD="\033[1m"
RESET="\033[0m"

# Globals
export UPDATE_MODE=false
INTERACTIVE=true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_PATHS=()

# Argument Parsing
for arg in "$@"; do
    case "$arg" in
        --update)          export UPDATE_MODE=true ;;
        --non-interactive) INTERACTIVE=false ;;
        --help|-h)
            echo -e "${CYAN}Oculus v4.1 Installer${RESET}"
            echo ""
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --update            Upgrade existing tools to latest versions"
            echo "  --non-interactive   Skip all prompts (for CI/Docker)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}[!] Unknown option: $arg${RESET}"
            echo "    Run './install.sh --help' for usage."
            exit 1
            ;;
    esac
done

# Auto-detect non-interactive (Docker, CI, piped stdin)
if [ ! -t 0 ]; then
    INTERACTIVE=false
fi

if [ "$UPDATE_MODE" = true ]; then
    echo -e "${YELLOW}[*] Update mode — will upgrade existing tools.${RESET}"
fi

# Cleanup Trap
cleanup() {
    for path in "${CLEANUP_PATHS[@]}"; do
        rm -rf "$path" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

# Helper Functions
log_info()    { echo -e "${CYAN}[*]${RESET} $1"; }
log_success() { echo -e "${GREEN}[✔]${RESET} $1"; }
log_warn()    { echo -e "${YELLOW}[!]${RESET} $1"; }
log_error()   { echo -e "${RED}[✘]${RESET} $1"; }
log_step()    { echo -e "\n${MAGENTA}${BOLD}━━━ $1 ━━━${RESET}"; }

cmd_exists() { command -v "$1" &>/dev/null; }

safe_pip_install() {
    pip3 install "$@" --break-system-packages 2>/dev/null \
        || pip3 install "$@" 2>/dev/null \
        || { log_warn "pip install failed for: $*"; return 1; }
}

check_sudo() {
    if [ "$EUID" -eq 0 ]; then return 0; fi
    if ! cmd_exists sudo; then
        log_error "'sudo' is not installed. Run as root or install sudo."
        exit 1
    fi
    if ! sudo -n true 2>/dev/null; then
        if [ "$INTERACTIVE" = false ]; then
            log_error "Cannot prompt for sudo in non-interactive mode."
            exit 1
        fi
        log_warn "Sudo privileges required. You may be prompted for your password."
        sudo true || { log_error "Failed to obtain sudo."; exit 1; }
    fi
}

# PHASE 1: Pre-flight Checks
log_step "Phase 1 · Pre-flight Checks"

check_sudo

if ! cmd_exists python3; then
    log_error "Python 3 is not installed! Please install Python 3.8+."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print("1") if sys.version_info >= (3, 8) else print("0")' 2>/dev/null || echo "0")
if [ "$PY_VER" = "0" ]; then
    log_error "Python 3.8+ required! Current: $(python3 --version 2>/dev/null || echo 'unknown')"
    exit 1
fi
log_success "Python $(python3 --version 2>&1 | cut -d' ' -f2) detected"

# PHASE 2: System Packages
log_step "Phase 2 · System Packages"

log_info "Updating package lists..."
sudo apt-get update -qq 2>/dev/null || log_warn "apt-get update had warnings"

APT_PACKAGES=(
    git wget curl unzip jq
    python3-pip python3-venv
    build-essential libpcap-dev
    nmap massdns wafw00f whatweb sqlmap
    dnsutils chromium
)

log_info "Installing ${#APT_PACKAGES[@]} packages..."
sudo apt-get install -y "${APT_PACKAGES[@]}" -qq 2>/dev/null \
    || log_warn "Some apt packages may have failed (continuing)"
log_success "System packages ready"

# PHASE 3: Go Toolchain
log_step "Phase 3 · Go Toolchain"

export GOPATH="${GOPATH:-$HOME/go}"
export PATH="$PATH:/usr/local/go/bin:$GOPATH/bin"

if ! cmd_exists go; then
    log_warn "Go is not installed."
    INSTALL_GO=false

    if [ "$INTERACTIVE" = true ]; then
        read -rp "    Install the latest Go version now? (y/n): " REPLY
        [[ "$REPLY" =~ ^[Yy]$ ]] && INSTALL_GO=true
    else
        INSTALL_GO=true
        log_info "Non-interactive mode — auto-installing Go."
    fi

    if [ "$INSTALL_GO" = true ]; then
        log_info "Fetching latest Go version..."
        LATEST_GO=$(curl -fsSL 'https://go.dev/VERSION?m=text' 2>/dev/null | head -n 1)

        if [ -z "$LATEST_GO" ]; then
            log_error "Failed to fetch Go version. Check internet connection."
            exit 1
        fi

        GO_TARBALL="${LATEST_GO}.linux-amd64.tar.gz"
        log_info "Downloading ${LATEST_GO}..."

        if wget -q "https://dl.google.com/go/${GO_TARBALL}" -O "/tmp/${GO_TARBALL}"; then
            CLEANUP_PATHS+=("/tmp/${GO_TARBALL}")
            sudo rm -rf /usr/local/go
            if sudo tar -C /usr/local -xzf "/tmp/${GO_TARBALL}"; then
                export PATH="$PATH:/usr/local/go/bin"
                log_success "${LATEST_GO} installed"
            else
                log_error "Failed to extract Go tarball. Installation is incomplete."
                exit 1
            fi
        else
            log_error "Failed to download Go."
            exit 1
        fi
    else
        log_error "Go >= 1.20 is required. Install from https://go.dev/dl/"
        exit 1
    fi
else
    log_success "Go $(go version | awk '{print $3}' | sed 's/go//') detected"
fi

# PHASE 4: Python Dependencies
log_step "Phase 4 · Python Dependencies"

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log_info "Installing Oculus Python requirements..."
    if safe_pip_install -r "$SCRIPT_DIR/requirements.txt" -q; then
        log_success "Python requirements installed"
    else
        log_warn "Some Python requirements failed — Oculus may have limited functionality"
    fi
else
    log_warn "requirements.txt not found — installing rich only"
    safe_pip_install rich -q || log_warn "Could not install rich"
fi

# PHASE 5: Tool Installation Dashboard
log_step "Phase 5.1 · Tool Installation Dashboard"

# Prepare /opt/recontools
if [ ! -d "/opt/recontools" ]; then
    log_info "Creating /opt/recontools..."
    sudo mkdir -p /opt/recontools
    sudo chown -R "$(id -u):$(id -g)" /opt/recontools
elif [ ! -w "/opt/recontools" ]; then
    log_info "Fixing /opt/recontools permissions..."
    sudo chown -R "$(id -u):$(id -g)" /opt/recontools
fi

export GOPATH PATH SCRIPT_DIR

log_info "Launching Installation Dashboard..."

python3 << 'INSTALLER_EOF'
import os, sys, shutil, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from rich.console import Console
    from rich.progress import (Progress, SpinnerColumn, TextColumn,
                               BarColumn, TaskProgressColumn, TimeElapsedColumn)
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Fallback if rich is missing
if not HAS_RICH:
    print("[!] 'rich' not available — using plain output")

    class FallbackConsole:
        def print(self, *a, **k):
            text = str(a[0]) if a else ""
            import re
            print(re.sub(r'\[.*?\]', '', text))

    console = FallbackConsole()
else:
    console = Console()

UPDATE_MODE = os.environ.get("UPDATE_MODE", "false").lower() == "true"
INSTALL_LOG = os.path.join(os.environ.get("SCRIPT_DIR", "."), "install.log")

# Initialize log
with open(INSTALL_LOG, "w") as f:
    f.write(f"Oculus Install Log — {datetime.datetime.now().isoformat()}\n")
    f.write(f"Update mode: {UPDATE_MODE}\n")
    f.write("=" * 60 + "\n\n")

def log_failure(name, text):
    with open(INSTALL_LOG, "a") as f:
        f.write(f"\n--- {name} [{datetime.datetime.now().strftime('%H:%M:%S')}] ---\n{text}\n")

def augment_path_env():
    home = os.path.expanduser("~")
    gopath = os.environ.get("GOPATH", os.path.join(home, "go"))
    extra = [
        os.path.join(home, ".local", "bin"),
        "/usr/local/bin",
        os.path.join(gopath, "bin"),
        "/usr/local/go/bin",
    ]
    parts = [p for p in os.environ.get("PATH", "").split(":") if p]
    for p in extra:
        if os.path.isdir(p) and p not in parts:
            parts.insert(0, p)
    os.environ["PATH"] = ":".join(parts)

def cli_available(name):
    augment_path_env()
    return shutil.which(name) is not None

def py_log(msg):
    with open(INSTALL_LOG, "a") as f:
        f.write(msg + "\n")

def ensure_cli_on_path(cli_name):
    """Symlink CLI into /usr/local/bin so it is visible without reloading shell."""
    augment_path_env()
    src = shutil.which(cli_name)
    if not src:
        local = os.path.join(os.path.expanduser("~"), ".local", "bin", cli_name)
        if os.path.isfile(local):
            src = local
    if not src:
        return False
    dst = f"/usr/local/bin/{cli_name}"
    if os.path.isfile(dst):
        return True
    subprocess.run(["sudo", "ln", "-sf", src, dst], capture_output=True, timeout=30)
    return os.path.isfile(dst)

def pip_install_package_dir(opt):
    if shutil.which("pipx"):
        r = subprocess.run(["pipx", "install", "--force", opt],
                           capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            return True
        py_log(f"pipx install failed: {r.stderr or r.stdout}")
    for flags in (["--break-system-packages"], []):
        cmd = [sys.executable, "-m", "pip", "install", "--user", opt] + flags
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            return True
        py_log(f"pip install failed: {r.stderr or r.stdout}")
    return False

# Tools invoked as python3 /opt/recontools/<repo>/<script>.py — not PATH CLIs
SCRIPT_BASED_TOOLS = frozenset({"xsstrike", "smuggler", "linkfinder", "eyewitness"})

def recon_script_exists(name_lower, opt):
    """Return True when the cloned repo contains its main Python entry script."""
    candidates = [
        os.path.join(opt, f"{name_lower}.py"),
        os.path.join(opt, name_lower, f"{name_lower}.py"),
    ]
    if name_lower == "xsstrike":
        candidates.append(os.path.join(opt, "xsstrike.py"))
    elif name_lower == "linkfinder":
        candidates.append(os.path.join(opt, "linkfinder.py"))
    elif name_lower == "smuggler":
        candidates.append(os.path.join(opt, "smuggler.py"))
    elif name_lower == "eyewitness":
        candidates.extend([
            os.path.join(opt, "Python", "EyeWitness.py"),
            os.path.join(opt, "Python", "eyewitness.py"),
        ])
    return any(os.path.isfile(p) for p in candidates)

def install_kiterunner(opt, progress, tid):
    dist_bin = os.path.join(opt, "dist", "kr")
    has_makefile = any(
        os.path.exists(os.path.join(opt, mf)) for mf in ("makefile", "Makefile")
    )
    if has_makefile:
        progress.update(tid, description="[bold cyan]⚒ kiterunner[/] (Building...)")
        r = subprocess.run(["make", "build"], cwd=opt, capture_output=True, text=True, timeout=300)
        if not os.path.isfile(dist_bin):
            py_log(f"kiterunner make build failed: {r.stderr or r.stdout}")
    if not os.path.isfile(dist_bin):
        progress.update(tid, description="[bold cyan]➤ kiterunner[/] (Downloading release...)")
        arch = "amd64"
        url = f"https://github.com/assetnote/kiterunner/releases/download/v1.0.2/kiterunner_1.0.2_linux_{arch}.tar.gz"
        tmp = os.path.join("/tmp", "kiterunner_release.tar.gz")
        try:
            extract_dir = os.path.join("/tmp", "kiterunner_extract")
            shutil.rmtree(extract_dir, ignore_errors=True)
            os.makedirs(extract_dir, exist_ok=True)
            subprocess.run(["wget", "-q", url, "-O", tmp], check=True, timeout=120)
            subprocess.run(["tar", "-xzf", tmp, "-C", extract_dir], check=True, timeout=60)
            for root, _, files in os.walk(extract_dir):
                if "kr" in files:
                    os.makedirs(os.path.dirname(dist_bin), exist_ok=True)
                    shutil.copy2(os.path.join(root, "kr"), dist_bin)
                    os.chmod(dist_bin, 0o755)
                    break
        except Exception as e:
            py_log(f"kiterunner release download failed: {e}")
    if os.path.isfile(dist_bin):
        subprocess.run(["sudo", "cp", dist_bin, "/usr/local/bin/kr"], timeout=30)
        subprocess.run(["sudo", "chmod", "+x", "/usr/local/bin/kr"], timeout=30)
        return cli_available("kr")
    return False

GO_TOOLS = [
    ("subfinder",   "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
    ("assetfinder", "github.com/tomnomnom/assetfinder@latest"),
    ("dnsx",        "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"),
    ("httpx",       "github.com/projectdiscovery/httpx/cmd/httpx@latest"),
    ("httprobe",    "github.com/tomnomnom/httprobe@latest"),
    ("naabu",       "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"),
    ("katana",      "github.com/projectdiscovery/katana/cmd/katana@latest"),
    ("gau",         "github.com/lc/gau/v2/cmd/gau@latest"),
    ("waybackurls", "github.com/tomnomnom/waybackurls@latest"),
    ("nuclei",      "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
    ("hakrawler",   "github.com/hakluke/hakrawler@latest"),
    ("ffuf",        "github.com/ffuf/ffuf/v2@latest"),
    ("dalfox",      "github.com/hahwul/dalfox/v2@latest"),
    ("asnmap",      "github.com/projectdiscovery/asnmap/cmd/asnmap@latest"),
    ("gowitness",   "github.com/sensepost/gowitness@latest"),
    ("gf",          "github.com/tomnomnom/gf@latest"),
    ("amass",       "github.com/owasp-amass/amass/v4/...@master"),
    ("subzy",       "github.com/PentestPad/subzy@latest"),
]

RECON_TOOLS = [
    ("ParamSpider",  "https://github.com/devanshbatham/ParamSpider"),
    ("Arjun",        "https://github.com/s0md3v/Arjun"),
    ("XSStrike",     "https://github.com/s0md3v/XSStrike"),
    ("smuggler",     "https://github.com/defparam/smuggler"),
    ("LinkFinder",   "https://github.com/GerbenJavado/LinkFinder"),
    ("theHarvester", "https://github.com/laramies/theHarvester"),
    ("kiterunner",   "https://github.com/assetnote/kiterunner"),
    ("EyeWitness",   "https://github.com/RedSiege/EyeWitness"),
]

results = {}  # name -> (status, detail)
GO_TIMEOUT = 600  # 10 min per Go tool

def is_installed(name):
    return shutil.which(name) is not None

def pip_install_req(req_file):
    r = subprocess.run(["pip3", "install", "-r", req_file, "--break-system-packages", "-q"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        r = subprocess.run(["pip3", "install", "-r", req_file, "-q"],
                           capture_output=True, text=True)
    return r.returncode == 0

def install_go_tool(name, repo, progress, tid):
    try:
        if not UPDATE_MODE and is_installed(name):
            progress.update(tid, description=f"[bold green]✔ {name}[/] (Present)", completed=100)
            results[name] = ("skipped", "Already installed")
            return

        action = "Upgrading" if UPDATE_MODE else "Installing"
        progress.update(tid, description=f"[bold yellow]➤ {name}[/] ({action}...)")

        res = subprocess.run(["go", "install", repo],
                             capture_output=True, text=True, timeout=GO_TIMEOUT)
        if res.returncode == 0:
            progress.update(tid, description=f"[bold green]✔ {name}[/] (Done)", completed=100)
            results[name] = ("success", "Installed")
        else:
            progress.update(tid, description=f"[bold red]✘ {name}[/] (Failed)", completed=100)
            log_failure(name, res.stderr)
            err = res.stderr.strip().split('\n')[-1][:80] if res.stderr.strip() else "Unknown"
            results[name] = ("failed", err)

    except subprocess.TimeoutExpired:
        progress.update(tid, description=f"[bold red]✘ {name}[/] (Timeout)", completed=100)
        log_failure(name, f"Timed out after {GO_TIMEOUT}s")
        results[name] = ("failed", "Build timeout")

    except Exception as e:
        progress.update(tid, description=f"[bold red]✘ {name}[/] (Error)", completed=100)
        log_failure(name, str(e))
        results[name] = ("failed", str(e)[:80])

def install_recon_tool(name, repo, progress, tid):
    try:
        opt = f"/opt/recontools/{name}"
        name_lower = name.lower()
        cli_name = "kr" if name_lower == "kiterunner" else name_lower

        augment_path_env()
        if os.path.exists(opt) and not UPDATE_MODE:
            if cli_available(cli_name):
                progress.update(tid, description=f"[bold green]✔ {name}[/] (Present)", completed=100)
                results[name] = ("skipped", "CLI already on PATH")
                return
            if name_lower in SCRIPT_BASED_TOOLS and recon_script_exists(name_lower, opt):
                progress.update(tid, description=f"[bold green]✔ {name}[/] (Script ready)", completed=100)
                results[name] = ("skipped", "Script in /opt/recontools")
                return

        if os.path.exists(opt):
            if UPDATE_MODE:
                progress.update(tid, description=f"[bold blue]⟳ {name}[/] (Pulling...)")
                r = subprocess.run(["git", "-C", opt, "pull", "-q"],
                                   capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    progress.update(tid, description=f"[bold red]✘ {name}[/] (Pull failed)", completed=100)
                    log_failure(name, r.stderr)
                    results[name] = ("failed", "git pull failed")
                    return
        else:
            progress.update(tid, description=f"[bold yellow]➤ {name}[/] (Cloning...)")
            r = subprocess.run(["git", "clone", "-q", "--depth=1", repo, opt],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                progress.update(tid, description=f"[bold red]✘ {name}[/] (Clone failed)", completed=100)
                log_failure(name, r.stderr)
                results[name] = ("failed", "git clone failed")
                return

        if name_lower == "arjun" and not cli_available("arjun"):
            progress.update(tid, description=f"[bold cyan]➤ {name}[/] (PyPI install...)")
            if shutil.which("pipx"):
                pip_cmd = ["pipx", "install", "arjun"]
            else:
                pip_cmd = [sys.executable, "-m", "pip", "install", "--user", "arjun", "--break-system-packages"]
            r = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                subprocess.run([sys.executable, "-m", "pip", "install", "--user", "arjun"],
                                 capture_output=True, text=True, timeout=300)
            ensure_cli_on_path("arjun")

        if name_lower == "kiterunner":
            if install_kiterunner(opt, progress, tid):
                progress.update(tid, description=f"[bold green]✔ {name}[/] (kr installed)", completed=100)
                results[name] = ("success", "kr on PATH")
            else:
                progress.update(tid, description=f"[bold red]✘ {name}[/] (Build failed)", completed=100)
                results[name] = ("failed", "kr binary not found")
            return

        req = os.path.join(opt, "requirements.txt")
        if name_lower == "eyewitness":
            py_req = os.path.join(opt, "Python", "requirements.txt")
            if os.path.exists(py_req):
                req = py_req
        if os.path.exists(req):
            if not pip_install_req(req):
                log_failure(name, "pip requirements had errors (tool may still work)")
                if name_lower == "eyewitness":
                    progress.update(tid, description=f"[bold red]✘ {name}[/] (Python deps failed)", completed=100)
                    results[name] = ("failed", "EyeWitness Python requirements failed")
                    return

        setup_py = os.path.join(opt, "setup.py")
        pyproject = os.path.join(opt, "pyproject.toml")
        if (os.path.exists(setup_py) or os.path.exists(pyproject)) and not cli_available(cli_name):
            progress.update(tid, description=f"[bold cyan]➤ {name}[/] (pip install from source...)")
            if pip_install_package_dir(opt):
                ensure_cli_on_path(cli_name)
                py_log(f"Installed {name} from {opt}")
            else:
                log_failure(name, "pip install from clone failed")

        if cli_available(cli_name):
            if name_lower == "massdns":
                # Ensure the resolvers list is present
                res_dir = "/usr/share/massdns"
                res_file = os.path.join(res_dir, "resolvers.txt")
                if not os.path.exists(res_file):
                    progress.update(tid, description=f"[bold cyan]➤ {name}[/] (Downloading resolvers...)")
                    try:
                        subprocess.run(["sudo", "mkdir", "-p", res_dir], capture_output=True, timeout=30)
                        subprocess.run(["sudo", "wget", "-q", "https://raw.githubusercontent.com/trickest/resolvers/main/resolvers-trusted.txt", "-O", res_file], capture_output=True, timeout=60)
                        subprocess.run(["sudo", "chmod", "644", res_file], capture_output=True, timeout=30)
                        py_log(f"Successfully downloaded massdns resolvers to {res_file}")
                    except Exception as e:
                        py_log(f"Failed to download massdns resolvers: {e}")
            progress.update(tid, description=f"[bold green]✔ {name}[/] (Ready)", completed=100)
            results[name] = ("success", f"{cli_name} on PATH")
        elif name_lower in SCRIPT_BASED_TOOLS and recon_script_exists(name_lower, opt):
            progress.update(tid, description=f"[bold green]✔ {name}[/] (Script ready)", completed=100)
            results[name] = ("success", "Script in /opt/recontools")
        else:
            progress.update(tid, description=f"[bold red]✘ {name}[/] (CLI missing)", completed=100)
            results[name] = ("failed", f"{cli_name} not on PATH after install")

    except subprocess.TimeoutExpired:
        progress.update(tid, description=f"[bold red]✘ {name}[/] (Timeout)", completed=100)
        log_failure(name, "Git operation timed out")
        results[name] = ("failed", "Timeout")

    except Exception as e:
        progress.update(tid, description=f"[bold red]✘ {name}[/] (Error)", completed=100)
        log_failure(name, str(e))
        results[name] = ("failed", str(e)[:80])

# Run Installation
if HAS_RICH:
    console.print(Panel(
        "[bold cyan]Oculus v4.1 — Tool Installation Engine[/]\n"
        f"[dim]Go tools: {len(GO_TOOLS)} · Recon tools: {len(RECON_TOOLS)} · "
        f"Mode: {'[yellow]Update[/]' if UPDATE_MODE else '[green]Fresh Install[/]'}[/dim]",
        border_style="cyan", padding=(1, 2)
    ))

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, style="dim", complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        total = len(GO_TOOLS) + len(RECON_TOOLS)
        main_task = progress.add_task("[bold cyan]Overall Progress", total=total)

        task_entries = []
        for name, repo in GO_TOOLS:
            tid = progress.add_task(f"[dim]Queued: {name}", total=100)
            task_entries.append(("go", name, repo, tid))
        for name, repo in RECON_TOOLS:
            tid = progress.add_task(f"[dim]Queued: {name}", total=100)
            task_entries.append(("recon", name, repo, tid))

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {}
            for ttype, name, repo, tid in task_entries:
                fn = install_go_tool if ttype == "go" else install_recon_tool
                future_map[executor.submit(fn, name, repo, progress, tid)] = name

            for future in as_completed(future_map):
                future.result()
                progress.advance(main_task)

    # Summary Table
    console.print()
    table = Table(title="[bold]Installation Summary[/]", box=box.ROUNDED,
                  border_style="cyan", header_style="bold cyan", padding=(0, 1))
    table.add_column("Tool", style="white", min_width=16)
    table.add_column("Status", justify="center", min_width=10)
    table.add_column("Detail", style="dim", max_width=50)

    ok = skip = fail = 0
    for name in [t[0] for t in GO_TOOLS] + [t[0] for t in RECON_TOOLS]:
        status, detail = results.get(name, ("failed", "Unknown"))
        if status in ("success", "installed"):
            table.add_row(name, "[bold green]✔ OK[/]", detail); ok += 1
        elif status == "skipped":
            table.add_row(name, "[bold blue]● Skip[/]", detail); skip += 1
        else:
            table.add_row(name, "[bold red]✘ FAIL[/]", detail); fail += 1

    console.print(table)
    parts = [f"[green]{ok} installed[/]"]
    if skip: parts.append(f"[blue]{skip} skipped[/]")
    if fail: parts.append(f"[red]{fail} failed[/]")
    console.print(f"\n  {' · '.join(parts)}")
    if fail:
        console.print(f"  [dim]Details in {INSTALL_LOG}[/dim]")

else:
    # Plain fallback (no rich)
    print(f"\nInstalling {len(GO_TOOLS)} Go tools + {len(RECON_TOOLS)} recon tools...")
    for name, repo in GO_TOOLS:
        if not UPDATE_MODE and is_installed(name):
            print(f"  [skip] {name}"); results[name] = ("skipped",""); continue
        print(f"  [install] {name}...", end=" ", flush=True)
        try:
            r = subprocess.run(["go","install",repo], capture_output=True, text=True, timeout=GO_TIMEOUT)
            if r.returncode == 0:
                print("OK"); results[name] = ("success","")
            else:
                print("FAIL"); log_failure(name, r.stderr); results[name] = ("failed","")
        except Exception as e:
            print(f"ERROR: {e}"); results[name] = ("failed","")
    for name, repo in RECON_TOOLS:
        opt = f"/opt/recontools/{name}"
        if os.path.exists(opt) and not UPDATE_MODE:
            print(f"  [skip] {name}"); results[name] = ("skipped",""); continue
        print(f"  [install] {name}...", end=" ", flush=True)
        try:
            r = subprocess.run(["git","clone","-q","--depth=1",repo,opt], capture_output=True, text=True, timeout=120)
            print("OK" if r.returncode == 0 else "FAIL")
            results[name] = ("success","") if r.returncode == 0 else ("failed","")
        except Exception as e:
            print("ERROR"); results[name] = ("failed","")

# Exit code for critical failures
CRITICAL = {"subfinder", "httpx", "nuclei", "naabu", "dnsx", "ffuf"}
crit_fail = [t for t in CRITICAL if results.get(t, ("failed",))[0] == "failed"]
if crit_fail:
    if HAS_RICH:
        console.print(f"\n  [bold red]⚠ Critical failures: {', '.join(crit_fail)}[/]")
    else:
        print(f"\n  ⚠ Critical failures: {', '.join(crit_fail)}")
    sys.exit(1)
INSTALLER_EOF

PYTHON_EXIT=$?
if [ $PYTHON_EXIT -ne 0 ]; then
    log_error "Dashboard exited with errors (critical tools failed — see install.log)"
    log_warn "Continuing post-install phases, but Oculus may not work correctly."
fi
INSTALL_FAILED=$PYTHON_EXIT

# PHASE 5b: Python CLIs (paramspider, arjun, kr) — pip install + system symlinks
log_step "Phase 5.2 · Python CLI Tools"

export PATH="$HOME/.local/bin:/usr/local/bin:$GOPATH/bin:$PATH"

link_cli_to_system() {
    local tool="$1"
    local src=""
    src="$(command -v "$tool" 2>/dev/null || true)"
    if [ -z "$src" ] && [ -x "$HOME/.local/bin/$tool" ]; then
        src="$HOME/.local/bin/$tool"
    fi
    if [ -n "$src" ]; then
        sudo ln -sf "$src" "/usr/local/bin/$tool" 2>/dev/null || true
        log_success "$tool → /usr/local/bin/$tool"
        return 0
    fi
    log_warn "$tool not found after install attempt"
    return 1
}

# Arjun — PyPI package
if ! command -v arjun &>/dev/null; then
    log_info "Installing arjun via pip..."
    pip3 install --user arjun --break-system-packages -q 2>/dev/null \
        || pip3 install --user arjun -q 2>/dev/null \
        || log_warn "pip install arjun failed"
fi
link_cli_to_system arjun || true

# ParamSpider — NOT on PyPI; install from cloned repo
PS_DIR="/opt/recontools/ParamSpider"
if [ -d "$PS_DIR" ] && ! command -v paramspider &>/dev/null; then
    log_info "Installing paramspider from $PS_DIR..."
    pip3 install --user "$PS_DIR" --break-system-packages -q 2>/dev/null \
        || pip3 install --user "$PS_DIR" -q 2>/dev/null \
        || log_warn "pip install ParamSpider failed"
fi
link_cli_to_system paramspider || true

# Kiterunner — ensure kr binary exists
if ! command -v kr &>/dev/null; then
    KR_DIR="/opt/recontools/kiterunner"
    if [ -d "$KR_DIR" ]; then
        if [ -f "$KR_DIR/makefile" ] || [ -f "$KR_DIR/Makefile" ]; then
            log_info "Building kiterunner (kr)..."
            (cd "$KR_DIR" && make build) 2>/dev/null || log_warn "make build failed"
        fi
        if [ -f "$KR_DIR/dist/kr" ]; then
            sudo cp "$KR_DIR/dist/kr" /usr/local/bin/kr 2>/dev/null
            sudo chmod +x /usr/local/bin/kr 2>/dev/null
        fi
    fi
    if ! command -v kr &>/dev/null; then
        log_info "Downloading kiterunner release binary..."
        KR_TMP="/tmp/kiterunner_linux_amd64.tar.gz"
        if wget -q "https://github.com/assetnote/kiterunner/releases/download/v1.0.2/kiterunner_1.0.2_linux_amd64.tar.gz" \
            -O "$KR_TMP" 2>/dev/null; then
            mkdir -p /tmp/kiterunner_extract
            tar -xzf "$KR_TMP" -C /tmp/kiterunner_extract 2>/dev/null
            KR_BIN="$(find /tmp/kiterunner_extract -name kr -type f 2>/dev/null | head -1)"
            if [ -n "$KR_BIN" ]; then
                sudo cp "$KR_BIN" /usr/local/bin/kr
                sudo chmod +x /usr/local/bin/kr
            fi
        fi
    fi
fi
link_cli_to_system kr || true

log_info "CLI verification:"
for t in arjun paramspider kr; do
    if command -v "$t" &>/dev/null; then
        log_success "  $t → $(command -v "$t")"
    else
        log_warn "  $t — not on PATH (run: export PATH=\"\$HOME/.local/bin:\$PATH\")"
    fi
done

# PHASE 6: GF Patterns
log_step "Phase 6 · GF Patterns"

mkdir -p "$HOME/.gf"

# Copy built-in gf examples
GF_MOD=$(find "$GOPATH/pkg/mod/github.com/tomnomnom" -maxdepth 1 -name "gf*" -type d 2>/dev/null | sort | tail -1)
if [ -n "$GF_MOD" ] && [ -d "$GF_MOD/examples" ]; then
    cp "$GF_MOD/examples/"*.json "$HOME/.gf/" 2>/dev/null || true
    log_success "Copied built-in gf patterns"
fi

# Clone community patterns to temp dir (NOT cwd)
GF_TEMP=$(mktemp -d)
CLEANUP_PATHS+=("$GF_TEMP")
GF_ERR_LOG="${GF_TEMP}/gf-clone.err"

if git clone --depth=1 https://github.com/1ndianl33t/Gf-Patterns "$GF_TEMP/Gf-Patterns" 2>"$GF_ERR_LOG"; then
    cp "$GF_TEMP/Gf-Patterns/"*.json "$HOME/.gf/" 2>/dev/null || true
    log_success "Installed community GF patterns"
else
    log_warn "Could not clone Gf-Patterns (non-critical — built-in patterns still installed)"
    if [ -s "$GF_ERR_LOG" ]; then
        GF_REASON=$(tail -n 1 "$GF_ERR_LOG" | sed 's/^[[:space:]]*//')
        [ -n "$GF_REASON" ] && log_warn "  Reason: ${GF_REASON}"
    fi
    log_warn "  Retry manually: git clone https://github.com/1ndianl33t/Gf-Patterns /tmp/Gf-Patterns && cp /tmp/Gf-Patterns/*.json ~/.gf/"
fi

# PHASE 7: Nuclei Templates
log_step "Phase 7 · Nuclei Templates"

if cmd_exists nuclei; then
    log_info "Updating Nuclei templates..."
    if nuclei -ut -silent 2>/dev/null; then
        log_success "Nuclei templates updated"
    else
        log_warn "Template update had issues (run 'nuclei -ut' manually)"
    fi
else
    log_warn "Nuclei not on PATH — skipping template update"
fi

# PHASE 8: Configuration
log_step "Phase 8 · Configuration"

if [ ! -f "$HOME/.config/oculus/config.yaml" ] && [ -f "$SCRIPT_DIR/config.yaml.example" ]; then
    mkdir -p "$HOME/.config/oculus"
    cp "$SCRIPT_DIR/config.yaml.example" "$HOME/.config/oculus/config.yaml"
    log_success "Default config → ~/.config/oculus/config.yaml"
else
    log_info "Config already exists or no example found (skipping)"
fi

# Persist Go PATH in shell rc files
if ! grep -q 'GOPATH' "$HOME/.bashrc" 2>/dev/null || [ ! -f "$HOME/.bashrc" ]; then
    {
        echo ''
        echo '# Oculus — Go binaries'
        echo 'export GOPATH="${GOPATH:-$HOME/go}"'
        echo 'export PATH="$PATH:/usr/local/go/bin:$GOPATH/bin"'
    } >> "$HOME/.bashrc"
    log_success "Added Go PATH to ~/.bashrc"
fi

if [ -f "$HOME/.zshrc" ] && ! grep -q 'GOPATH' "$HOME/.zshrc" 2>/dev/null; then
    {
        echo ''
        echo '# Oculus — Go binaries'
        echo 'export GOPATH="${GOPATH:-$HOME/go}"'
        echo 'export PATH="$PATH:/usr/local/go/bin:$GOPATH/bin"'
    } >> "$HOME/.zshrc"
    log_success "Added Go PATH to ~/.zshrc"
fi

# Ensure user-local bin is on PATH for pip --user installs
if ! grep -q 'LOCAL_BIN' "$HOME/.bashrc" 2>/dev/null; then
    {
        echo ''
        echo '# Oculus — user local bin'
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$HOME/.bashrc"
    log_success "Added ~/.local/bin to ~/.bashrc"
fi

if [ -f "$HOME/.zshrc" ] && ! grep -q 'LOCAL_BIN' "$HOME/.zshrc" 2>/dev/null; then
    {
        echo ''
        echo '# Oculus — user local bin'
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$HOME/.zshrc"
    log_success "Added ~/.local/bin to ~/.zshrc"
fi

# ══════════════════════════════════════════════════════════════
# Done!
# ══════════════════════════════════════════════════════════════
echo ""
if [ "${INSTALL_FAILED:-0}" -ne 0 ]; then
    echo -e "${YELLOW}${BOLD}╔═══════════════════════════════════════════════════════╗${RESET}"
    echo -e "${YELLOW}${BOLD}║ Oculus v4.1 — Installed (with critical failures)      ║${RESET}"
    echo -e "${YELLOW}${BOLD}╚═══════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  ${RED}Some critical tools failed to install.${RESET}"
    echo -e "  ${DIM}Review install.log and re-run with:  ${YELLOW}./install.sh --update${RESET}"
else
    echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}║       Oculus v4.1 — Installation Complete! ✔          ║${RESET}"
    echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════════════╝${RESET}"
fi
echo ""

# Detect login shell so users source the correct rc file (bash vs zsh)
case "${SHELL:-}" in
    */zsh|zsh)
        SHELL_RC="$HOME/.zshrc"
        SHELL_NAME="zsh"
        ;;
    */bash|bash)
        SHELL_RC="$HOME/.bashrc"
        SHELL_NAME="bash"
        ;;
    *)
        SHELL_RC="$HOME/.bashrc"
        SHELL_NAME="bash"
        ;;
esac

echo -e "  ${YELLOW}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${YELLOW}${BOLD}  REQUIRED — Run this command before using Oculus${RESET}"
echo -e "  ${YELLOW}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${YELLOW}  Installation updated your PATH. Run the line below in this${RESET}"
echo -e "  ${YELLOW}  terminal (type it and press Enter):${RESET}"
echo ""
echo -e "  ${CYAN}${USER}@${HOSTNAME}${RESET}:${BLUE}~${RESET}\$ source ${SHELL_RC}${RESET}"
echo ""
echo -e "  ${DIM}  Or close this terminal and open a new one.${RESET}"
if [ "$SHELL_NAME" = "zsh" ]; then
    echo -e "  ${DIM}  (${SHELL_NAME}: run the command above to apply the new PATH changes)${RESET}"
fi
echo -e "  ${YELLOW}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${CYAN}Optional — only if you want to:${RESET}"
echo -e "    ${DIM}·${RESET} Check the version:  ${YELLOW}python3 oculus.py --version${RESET}"
echo -e "    ${DIM}·${RESET} List all tools:     ${YELLOW}python3 oculus.py${RESET}  then press ${CYAN}I${RESET}"
echo -e "    ${DIM}·${RESET} Edit settings:      ${YELLOW}nano ~/.config/oculus/config.yaml${RESET}"
echo ""

# Propagate failure exit code so CI/Docker can detect broken installs
exit "${INSTALL_FAILED:-0}"
