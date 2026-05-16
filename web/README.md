# Oculus Web Console

Browser UI for running the existing Oculus CLI locally.

## Run locally

```bash
cd web
python -m pip install -r requirements.txt
npm install
```

Start the API in one terminal:

```bash
npm run api
```

Start the React app in another terminal:

```bash
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## Architecture

- `backend/app.py` validates requests, starts `../oculus.py` as a subprocess, streams logs over SSE, and exposes generated reports.
- `src/main.jsx` is the operator console.
- `shared/modules.json` is the module catalog used by both frontend and backend, so future modules can be added in one obvious place.

The CLI remains unchanged and is still the source of truth for scan behavior.
