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

- **Real-Time Log Streaming:** WebSocket integration streams terminal output directly to your browser with zero latency.
- **Interactive Configuration:** Form-based UI to build scan profiles, select modules (Nmap, Nuclei, Subfinder, etc.), and set flags without memorizing CLI syntax.
- **Session Management:** Automatically reads the `session.json` state. Resume past scans, view artifact directories, and browse vulnerabilities cleanly.
- **Live Tool Status:** Built-in system check that instantly validates which of the 29+ required tools are installed on your Linux host.
- **Zero Database:** Fully stateless backend. It reads directly from the existing `output-*/` directories to ensure perfect parity with the CLI.

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
pip install -r requirements.txt
```

**Frontend:**
```bash
cd ../frontend
npm install
```

### Step 2: Build & Launch (Single-Port Production Mode)
This is the recommended, most robust way to run the Web Interface. You compile the React frontend into static assets, and the FastAPI backend serves both the API and the UI on a single port.

```bash
# 1. Build the React frontend
cd web/frontend
npm run build

# 2. Start the FastAPI backend
cd ../backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```
Navigate to **http://localhost:8000** in your browser. The FastAPI server is now handling everything!

---

## 🛠️ Alternative: Developer Mode (Live Reloading)

If you are modifying the React code and want instant hot-reloading in the browser, you must run two separate terminals:

**Terminal 1 (Backend):**
```bash
cd web/backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
cd web/frontend
npm run dev
```

Navigate to **http://localhost:5173**. The Vite dev server will automatically proxy `/api/*` and `/ws/*` requests to your FastAPI backend.

---

## 📡 Core API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/tools` | System check for tool installation status |
| `POST` | `/api/scan/start` | Trigger the Oculus scanning engine |
| `POST` | `/api/scan/stop` | Safely abort an active scan |
| `GET`  | `/api/scan/status` | Fetch current execution state |
| `GET`  | `/api/sessions` | List all historical scan sessions |
| `GET`  | `/api/results/{domain}` | Browse artifact files for a target |
| `WS`   | `/ws/scan` | Real-time WebSocket log streaming |

---

> ⚠️ **SECURITY WARNING:** The web interface is designed for **local use only**. It does not currently implement authentication. Do not bind the server to a public IP (`0.0.0.0`) on an untrusted network.
