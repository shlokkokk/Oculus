# Oculus Web Frontend

This directory contains the React SPA (Single Page Application) frontend for the Oculus web interface.

It is built with:
- **Vite** (Build tool)
- **React 19** (UI library)
- **Lucide React** (Icons)
- **Vanilla CSS** (Custom dark operator theme)

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies API requests to FastAPI on port 8000)
npm run dev
```

## Production Build

```bash
# Build the production assets into dist/
npm run build
```

Once built, the FastAPI backend will serve the static files from the `dist/` directory automatically.

For complete web interface instructions, see the main [web README](../README.md).
