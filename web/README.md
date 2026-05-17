# 🌐 Oculus Web Interface

<p align="center">
  <img src="https://img.shields.io/badge/STATUS-OPERATIONAL-00ff88?style=flat-square" />
  <img src="https://img.shields.io/badge/FRAMEWORK-FastAPI_&_React-00f0ff?style=flat-square" />
  <img src="https://img.shields.io/badge/ARCHITECTURE-HYBRID-b829dd?style=flat-square" />
</p>

The **Oculus Web Interface** is a sleek, high-performance browser dashboard built to orchestrate the core Oculus framework. It provides a real-time command center for configuring scans, monitoring live output streams, managing persistent sessions, and viewing final reports without ever touching a terminal.

> ⚡ **Hybrid Architecture:** The web interface is a pure companion to the CLI. The native CLI (`oculus.py`) remains 100% untouched. You can run scans from the terminal and view the results in the browser, or vice-versa.

---

## ✨ Key Features

- **Zero-Latency Telemetry Streaming**: Low-latency WebSocket piping routes raw shell feeds directly from the underlying daemon execution processes straight into a reactive virtual terminal viewport in the browser.
- **Interactive Configuration**: Form-based UI to build scan profiles, select modules (Nmap, Nuclei, Subfinder, etc.), and set flags without memorizing CLI syntax.
- **Micro-Animated Cyber Toggles**: Full-width glassmorphic control containers (such as Jitter) featuring hardware-inspired responsive styling, CSS physics transitions (`0.3s`), translucent accents, active cyan glowing borders, and drop-shadow illumination.
- **Out-of-Band Daemon Heartbeat**: Automated asynchronous multi-interval polling targeting `/api/health` that updates a breathing hardware-style LED keyframe indicator (ONLINE/OFFLINE) in the sidebar footer.
- **Multi-Vector Battle Presets**: Injects optimized configurations (`🐉 Kali Linux Native` | `⚡ High Performance` | `🥷 Stealth Operations`) to instantly adapt thread limits, timeout delays, and module distributions based on the engagement landscape.
- **Restorative System Synchronization**: Actionable resets that dynamically read configuration specs from the FastAPI backend to instantly wipe localized adjustments and restore raw system baselines.
- **Interventionist Abort Protection**: A safety overlay warning modal armed with Lucide vector icons (`<ShieldAlert />`) that halts abort triggers to prevent premature process drops across active execution paths.
- **Progress-Snap Integration**: Intelligently overrides mathematical parsing when a scan finishes or is resumed, immediately driving the visual progress indicators to `100%` and showing full step completion.
- **Session Management**: Automatically reads the `session.json` state. Resume past scans, view artifact directories, and browse vulnerabilities cleanly.
- **Stateless PARITY Architecture (Zero Database)**: Zero-database design that queries directly from `output-*/` session files, ensuring absolute synchronicity between CLI commands and browser operations.
- **Operational Pre-flight Checks (Live Tool Status)**: Built-in diagnostics checking 29 system tools, matching exact Go directories, apt binaries, and `/opt/recontools/` Python modules to provide a full dependency status overview.

---

## 🛠️ Architecture Stack

```text
Browser (React SPA)
    │
    ├── [ REST API ] ──── FastAPI Backend ──── Oculus Core (oculus.py)
    │                                              │
    └── [ WebSocket ] ── Live Log Stream           └── 29+ Kali Modules
```

- **Backend (`web/backend/`)**: A fast, asynchronous API built with FastAPI. It imports the `Oculus` Python class directly to execute scans without spawning dangerous subprocesses.
- **Frontend (`web/frontend/`)**: A React 19 Single Page Application built with Vite. Features a custom dark-operator theme and Lucide React icons.

---

## 🚀 Complete Setup Guide (From Scratch)

### Prerequisites
- Python 3.8+ (with `pip`)
- Node.js 18+ (with `npm`)
- Native Linux environment (Kali/Ubuntu/WSL).

### Step 0: Install Core Oculus Binaries (Crucial)
The Web UI is just a frontend. It relies on the native security binaries (`nmap`, `nuclei`, `subfinder`, etc.) to actually perform the scans. You **must** run the main installer first.

From the **project root** (`Oculus/`):
```bash
chmod +x install.sh
./install.sh
```
*(This installs all 29+ required tools into your system path and `/opt/recontools/`)*.

### Step 1: Install Web Dependencies

**Backend:**
```bash
cd web/backend
pip3 install -r requirements.txt --break-system-packages
```

**Frontend:**
```bash
cd ../frontend
npm install
```

### Step 2: Launch in Developer Mode (Standard / Live Reloading)
This is the standard and most productive way to run the interface during active operational usage. The React dev server provides hot-reloading and proxies API/WS requests seamlessly to your backend.

Open **two separate terminals** to start both systems:

**Terminal 1 (Backend Daemon):**
```bash
cd web/backend
pip3 install -r requirements.txt --break-system-packages
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend Interface):**
```bash
cd web/frontend
npm run dev
```
Navigate to **http://localhost:5173** to launch the operational control HUD.

---

## 📦 Alternative: Single-Port Production Mode (Build & Host)
If you want to bundle the React frontend into static assets and let the FastAPI backend serve both the client interface and API on a single port:

```bash
# 1. Compile the React frontend assets
cd web/frontend
npm run build

# 2. Spin up the unified FastAPI server
cd ../backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```
Navigate to **http://localhost:8000** in your browser.

---

## 📡 Core API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/tools` | System check for tool installation status |
| `GET`  | `/api/health` | Lightweight system health check (used by Web UI sidebar polling) |
| `GET`  | `/api/config` | Retrieve current backend default configuration settings |
| `POST` | `/api/scan/start` | Trigger the Oculus scanning engine |
| `POST` | `/api/scan/stop` | Safely abort an active scan |
| `GET`  | `/api/scan/status` | Fetch current execution state |
| `GET`  | `/api/sessions` | List all historical scan sessions |
| `GET`  | `/api/results/{domain}` | Browse artifact files for a target |
| `WS`   | `/ws/scan` | Real-time WebSocket log streaming |

---

> ⚠️ **SECURITY WARNING:** The web interface is designed for **local use only**. It does not currently implement authentication. Do not bind the server to a public IP (`0.0.0.0`) on an untrusted network.
