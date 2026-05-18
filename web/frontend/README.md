# 🎨 Oculus Web Frontend

<p align="center">
  <img src="https://img.shields.io/badge/FRAMEWORK-React_19-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/BUILDER-Vite-646CFF?style=flat-square&logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/STYLING-Vanilla_CSS-1572B6?style=flat-square&logo=css3&logoColor=white" />
</p>

This directory houses the **React Single Page Application (SPA)** that powers the Oculus Web Cockpit. It provides a sleek, hacker-themed, dark-operator interface for commanding the underlying Python reconnaissance engine.

---

## ⚡ Tech Stack

- **React 19:** Core UI library leveraging modern hooks for state management.
- **Vite:** Next-generation frontend tooling for instantaneous Hot Module Replacement (HMR).
- **Lucide React:** Clean, lightweight SVG iconography.
- **Vanilla CSS:** Custom-built styling system (no Tailwind) to ensure maximum control over the cyberpunk aesthetic, glowing borders, and terminal animations.

---

## 🖼️ Screenshot Review UI

- **Reports tab:** Includes a Screenshots view that groups captures by inferred host/domain and opens each capture in a near full-screen lightbox with previous/next controls.
- **Results tab:** Includes a Screenshots workspace alongside Explorer and Global Search, grouping captured artifacts domain-wise and previewing image files directly.
- **Artifact source:** The UI reads recursively from `output-<domain>/screenshots/`, including `gowitness/` and `eyewitness/` subfolders when both engines run.

---

## 🏗️ Directory Structure

```text
frontend/
├── index.html          # Main HTML entry point
├── package.json        # Node dependencies & scripts
├── vite.config.js      # Vite bundler & proxy configuration
├── src/
│   ├── main.jsx        # React DOM mounting
│   ├── App.jsx         # Root application component
│   ├── index.css       # Global design tokens and utilities
│   └── components/     # Modular React components
│       ├── ScanConfigurator.jsx  # Scan setup, presets, module selection
│       ├── ScanProgress.jsx      # Live progress and terminal output surface
│       ├── ResultsViewer.jsx     # Artifact explorer, search, screenshot workspace
│       ├── ReportViewer.jsx      # HTML/JSON/Markdown reports and screenshot lightbox
│       └── ToolStatus.jsx        # Dependency validation and refresh
```

---

## 🛠️ Development Workflow

To work on the frontend independently, you must have Node.js 18+ installed.

### 1. Install Dependencies
```bash
npm install
```

### 2. Start the Development Server
```bash
npm run dev
```
> **Note:** The Vite development server runs on `http://localhost:5173`. It is configured via `vite.config.js` to automatically proxy all API (`/api/*`) and WebSocket (`/ws/*`) requests to the FastAPI backend running on port `8000`. You **must** have the backend running simultaneously to test real data.

---

## 📦 Production Build

When the UI is ready for release, it must be compiled into static HTML/CSS/JS files.

```bash
npm run build
```
This command generates an optimized bundle in the `dist/` directory. Once built, the FastAPI backend will automatically detect this folder and serve the application statically, meaning you only need to run the Python server in production.

---

## 🎨 Design Philosophy

The interface is built around a **"Terminal-First" aesthetic**:
- **Colors:** Deep blacks (`#0a0a0f`), vibrant cyan (`#00f0ff`), and alert reds (`#ff3366`).
- **Typography:** JetBrains Mono for logs and technical data, Inter for standard UI elements.
- **Animations:** Subtle fade-ins and typing effects that mimic real CLI output without feeling slow or bloated.

For complete backend integration instructions, see the main [Web README](../README.md).
