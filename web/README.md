# Oculus Web Interface

A full operational web cockpit for the Oculus reconnaissance framework. Configure scans, monitor live output, browse results, and view reports — all from your browser.

> **This is a companion to the CLI.** The CLI (`oculus.py`) remains untouched and continues to work exactly as before. The web interface wraps the same `Oculus` class.

---

## Quick Start

### Prerequisites

- Python 3.8+ with `pip`
- Node.js 18+ with `npm`
- Oculus CLI dependencies installed (see main [README](../README.md))

### 1. Install backend dependencies

```bash
cd web/backend
pip install -r requirements.txt
```

### 2. Install frontend dependencies

```bash
cd web/frontend
npm install
```

### 3. Start the backend (FastAPI)

From the **project root** (`Oculus/`):

```bash
cd web/backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Start the frontend (Vite dev server)

In a separate terminal:

```bash
cd web/frontend
npm run dev
```

### 5. Open in browser

Navigate to **http://localhost:5173**

The Vite dev server proxies `/api/*` and `/ws/*` requests to the FastAPI backend on port 8000.

---

## Production Build

To serve everything from the FastAPI server (single port):

```bash
# Build the frontend
cd web/frontend
npm run build

# Start the backend — it will serve the built frontend automatically
cd ../backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** — the FastAPI server serves both the API and the built React app.

---

## Architecture

```
Browser (React SPA)
    │
    ├── REST API ──── FastAPI Backend ──── Oculus Class (oculus.py)
    │                                          │
    └── WebSocket ── Live Log Stream           └── CLI Tools (subfinder, nuclei, etc.)
```

- **Backend** (`web/backend/`): FastAPI app that imports and wraps the `Oculus` class directly
- **Frontend** (`web/frontend/`): React + Vite SPA with Lucide icons
- **No database**: Reads existing `session.json` and file artifacts from `output-*/` directories
- **Single scan at a time**: Safety constraint to prevent resource conflicts

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Backend health + version |
| GET | `/api/tools` | Tool installation status |
| GET | `/api/config` | Current config (keys redacted) |
| POST | `/api/scan/start` | Start a scan |
| POST | `/api/scan/stop` | Abort running scan |
| GET | `/api/scan/status` | Current scan state |
| GET | `/api/scan/logs` | Fetch log lines |
| GET | `/api/sessions` | List all scan sessions |
| GET | `/api/sessions/{domain}` | Session details |
| GET | `/api/results/{domain}` | List artifact files |
| GET | `/api/results/{domain}/file/{path}` | Get file content |
| GET | `/api/reports/{domain}/{format}` | Get report (html/json/md/summary) |
| WS | `/ws/scan` | Real-time log + status streaming |

## Important Notes

- **Authorization**: No authentication — designed for **localhost use only**. Do not expose to the internet without adding auth.
- **Platform**: The web UI runs on any OS, but actual scans require Linux with the recon tools installed.
- **CLI unchanged**: `oculus.py` is never modified. Run `python oculus.py --version` to verify.
