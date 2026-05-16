# ⚙️ Oculus Web Backend

<p align="center">
  <img src="https://img.shields.io/badge/FRAMEWORK-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PYTHON-3.8+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/SERVER-Uvicorn-FF6B6B?style=flat-square" />
</p>

This directory contains the **FastAPI Backend** that powers the Oculus Web Cockpit. It acts as the critical bridge between the sleek React frontend and the heavy-duty Python reconnaissance engine.

---

## ⚡ Core Responsibilities

- **Engine Orchestration:** Directly imports the native `Oculus` Python class from the parent directory. It does not spawn messy subprocesses; it interacts with the framework at the object level.
- **WebSocket Streaming:** Upgrades connections to `ws://` to stream high-frequency terminal logs and scan status directly to the browser with zero latency.
- **Static Asset Serving:** Automatically detects if the React frontend has been compiled (in `../frontend/dist`) and serves the UI, allowing for a seamless single-port production deployment.
- **Artifact Retrieval:** Reads directly from the `output-*/` directories on disk, allowing you to fetch HTML reports, JSON findings, and raw text logs via the API.

---

## 🏗️ Directory Structure

```text
backend/
├── requirements.txt    # Minimal backend dependencies
├── server.py           # FastAPI application & route definitions
├── engine.py           # Wrapper that imports the Oculus class safely
└── models.py           # Pydantic schemas for strict API validation
```

---

## 🛠️ Development Workflow

Ensure you are using Python 3.8 or higher.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Development Server
```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```
> **Note:** The `--reload` flag enables Hot-Reloading. Any changes you make to `server.py` or the core Oculus framework will automatically restart the backend API.

---

## 📡 API Documentation

FastAPI automatically generates interactive Swagger documentation based on our Pydantic models. 

When the server is running, navigate to:
**[http://localhost:8000/docs](http://localhost:8000/docs)** 

Here, you can manually trigger scans, test the endpoints, and view the strict type definitions for all requests and responses.

---

## ⚠️ Security Context

Because Oculus is an offensive security tool that executes system-level binaries (like `nmap` and `nuclei`), **this backend must never be exposed to the public internet** (`0.0.0.0`) without adding a robust authentication layer. By default, it is intended to bind only to `127.0.0.1` for local dashboard viewing.
