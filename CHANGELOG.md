# Changelog

All notable changes to the **Oculus** project will be documented in this file.

## [Unreleased]
### Added
- 

## [4.2.0] - 2026-05-31
### Added
- **8 New Reconnaissance Modules:** Expanded the orchestrator to run **37 modules** (up from 29) by adding Cariddi URL crawl secrets finder, Jaeles signature vulnerability scan, Tplmap SSTI scan (safe detection), CRLFuzz CRLF injection checks, InternetDB passive port/vulnerability lookup, Nikto web server scanner, TLSX cert scan with CN/SAN subdomain extraction, and nomore403 bypass scanner.
- **ntfy Push Notifications & Setup Wizard:** Added interactive `ntfy_setup.py` wizard and core push notification engine supporting status-tailored alerts (start, completion, findings, errors, skips) over public or authentication-secured private ntfy instances.
- **Deep WAF Fingerprinting:** Integrated `WhatWaf` into the WAF Detection module (Module 7) for secondary deep inspection and bypass suggestions.
- **Smart DNS Bruteforcing Permutations:** Added `AlterX` smart permutation generation and `PureDNS` wildcard-aware resolution to the DNS Bruteforce pipeline (Module 17).
- **Customizable Scan Limits:** Added a collapsible "Target Scope & Limits" panel in the browser configurator to customize max host/URL limit thresholds for Arjun, FFUF, Nikto, WhatWaf, Tplmap, and Nomore403, defaulting to maximum (`999999` / unlimited) for full-spectrum capabilities.
- **Module Return Status Protocol:** Added strict return status validation (`MODULE_OK`, `MODULE_SKIPPED`, `MODULE_PARTIAL`, `MODULE_FAILED`) across CLI tasks and web daemons.
- **Skipped Step UI Indicators:** Integrated skipped module state telemetry with the frontend progress panel, rendering amber fast-forward (`⏩`) indicators and adjusting progress calculations accordingly.
- **Status-Specific Notifications:** Refactored `ntfy` integrations to dispatch status-tailored event headers (like skipped alerts) with appropriate priority tags.
- **Isolated Cloud Asset Findings:** Differentiated accessible `[OPEN]` cloud storage buckets from inaccessible `[EXISTS/PRIVATE]` ones, logging them separately to preserve output purity.
- **ParamSpider Directory Fallback:** Integrated directory search/move logic to automatically resolve ParamSpider v2+ outputs inside the local results folder relative to the runtime path.
- **Dual Screenshot Capture:** Screenshot module now attempts both `gowitness` and `EyeWitness` for every alive URL/domain/subdomain, storing output under engine-specific screenshot folders.
- **Domain-Grouped Screenshot UI:** Web Reports and Results views now display screenshots grouped by inferred host/domain, with larger previews and a near full-screen lightbox viewer.
- **Dynamic Full-Port Timeout:** Full Nmap scans now scale their outer timeout by alive-target count via `nmap.full_port_timeout_base`, `nmap.full_port_timeout_per_host`, and `nmap.full_port_timeout_max`.

### Fixed
- **Null Config Parse Security:** Wrapped nested dictionary reads in API and engine files with safe get fallbacks (`(config.get("section") or {})`) to prevent server crashes on null/empty YAML headers.
- **Robust Directory Creation:** Standardized all directory creation calls in the core CLI to use `parents=True, exist_ok=True` to guarantee flawless standalone execution.
- **Screenshot Telemetry:** Screenshot capture now logs resolved tool paths, output directories, per-engine counts, total counts, and writes screenshot metrics into `session.json`.
- **Recursive Screenshot Reporting:** HTML and web artifact viewers now include nested screenshot outputs instead of only top-level PNGs.
- **EyeWitness Installation Wiring:** Installer now clones and validates `EyeWitness` instead of the unrelated `aquatone` path.

## [4.1.0] - 2026-05-17
### 🚀 Added
- **Dual-Engine Probing:** Configured `httprobe` as a secondary, concurrent alive-checking engine alongside `httpx` to guarantee zero dropped targets.
- **Zero-Block Background Nmap:** Decoupled slow Full Port Scans from the Phase 2 execution pool to run in a background daemon thread, eliminating UI lag.
- **Smart Web Resume Selector:** Integrated session endpoints to detect previous scans and offer dynamic "Resume" vs "Start Fresh" toggle options directly in the configuration and abort screens.
- **Force Dependency Refresh:** Added a cache-bypassing Refresh button to the Tool Status UI to force re-evaluation of installed systems.

### 🐛 Fixed
- **Active Targeting Suffix-Matching:** Fixed the strict filtering bug in Arjun/SQLMap where valid endpoints were dropped; replaced with dynamic suffix-matching.
- **Resilient Report Generation:** Wrapped HTML report blocks in try/except boundaries to ensure aborted scans still write complete, clean partial reports.

## [4.0.0] - 2026-05-17
### 🚀 Added
- **Web Cockpit:** A complete, real-time web interface built with FastAPI and React.
- **Operator Dashboard:** Configure scans, select modules, and monitor live streaming output directly from the browser.
- **Results Viewer:** Browse artifacts, view HTML/JSON/Markdown reports, and inspect tool health status visually.
- **Zero-Modification CLI:** The web interface wraps the existing `Oculus` engine without modifying the trusted CLI source of truth.

## [3.1.0] - 2026-05-15
### 🚀 Added
- **Full Spectrum Scan (`[U]`):** A new 5-phase orchestration pipeline running all modules concurrently with intelligent dependency gating.
- **Smart Resume Logic:** Deep session integration allowing Full Spectrum Scan to instantly skip previously completed tasks on resume.
- **Graceful Abort Handling:** Safe `Ctrl+C` interrupt handling that halts pipelines, saves progress, and generates partial reports without losing data.
- **Data Protection:** Added pre-scan warnings to Full Auto (`[9]`) and Deep Recon (`[D]`) to prevent accidental overwrites of existing session data.
- **Suggested Next Steps:** Intelligent dashboard prompts that analyze the current scan state and recommend the optimal next action.

### ✨ Improved
- **Premium TUI Experience:** Redesigned the main menu using `rich` with aligned columns, dynamic real-time scan statistics, and color-coded progress indicators.
- **Visual Branding:** Updated the ASCII banner tagline to accurately reflect the tool's capabilities ("Full-Spectrum Attack Surface Intelligence").
- **Graceful Fallbacks:** Enhanced the standard plain-text menu to ensure 100% feature parity for terminals lacking `rich` support.

### 🐛 Fixed
- **Suggestion Engine Bug:** Fixed an issue where advanced module results would incorrectly override core phase suggestions in the dashboard logic.

## [3.0.0] - 2026-05-14
### 🚀 Added
- **Initial Release:** Complete rewrite of the framework architecture.
- **Concurrency Engine:** Integrated `ThreadPoolExecutor` for high-performance scanning.
- **Streaming Output:** Real-time terminal feedback for all major scanning modules.
- **State Management:** Added `session.json` for persistent scan state and auto-resume.
- **Enhanced Modules:**
    - Deep CNAME takeover analysis.
    - Multi-vector CORS misconfiguration scanner.
    - SSL-resilient JS secret extraction.
    - Automated WAF detection and bypass hinting.
- **Reporting:** 
    - Interactive dark-themed HTML dashboards.
    - Machine-readable JSON output.
    - HackerOne-ready Markdown reports.

### 🛠️ Changed
- **Branding:** Transitioned project identity from ReconMaster to Oculus.
- **Command Runner:** Refactored execution core to support granular exit codes and robust timeouts.
- **I/O Logic:** Standardized file redirection to prevent shell injection and race conditions.

---
*Generated by the Oculus Development Team.*
