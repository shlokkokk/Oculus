# Changelog

All notable changes to **Oculus** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.2.0] - 2026-06-01

### Added

#### Scan modules (8 new — **36** total scan modules, menu **1–36**)

| Menu | CLI | Module |
|:---:|:---|:---|
| 29 | `cariddi` | URL crawl for secrets, endpoints, extensions |
| 30 | `jaeles` | Signature-based vulnerability scan |
| 31 | `tplmap` | SSTI detection (safe mode) |
| 32 | `crlfuzz` | CRLF injection checks |
| 33 | `internetdb` | Passive port/vuln lookup (no API key) |
| 34 | `nikto` | Web server configuration scan |
| 35 | `tlsx` | TLS cert SAN/CN subdomain discovery |
| 36 | `nomore403` | Automated 403/401 bypass testing |

#### Menu & orchestration

- **`SCAN_MODULES` registry** — single source of truth for TUI numbers, `MODULE_MAP`, and `SCAN_MODULE_COUNT` (no more manual “36 vs 37” drift).
- **Automation keys (letters only):** **A** Full Auto (core 1–8), **D** Deep Recon, **F** Full Spectrum, plus **R** / **C** / **I** / **H** / **Q** for system actions.
- **Module status protocol** — every step returns `MODULE_OK`, `MODULE_SKIPPED`, `MODULE_PARTIAL`, or `MODULE_FAILED` (CLI, web API, and ntfy).
- **Scaled timeouts** — `_get_scaled_timeout()` for large target lists (arjun, kr, nikto, jaeles, sqlmap, nomore403, nmap full ports, etc.).
- **Full Spectrum resume** — resume-skipped steps land in `skipped_modules` (not falsely marked completed).

#### Notifications (ntfy)

- Interactive **`python3 oculus.py --setup-ntfy`** wizard and `ntfy_setup.py`.
- **One consolidated notification per module** — Tools breakdown + Total metrics (no per-finding phone spam when `send_module_complete` is on).
- **`_MODULE_NTFY_PROFILES`** — per-module phases, tags, artifact paths, and live tool stats (`_record_module_tool`).
- Distinct **scan complete** vs **scan aborted** messages on Full Spectrum abort.
- All ntfy toggles default **on** in `DEFAULT_CONFIG` and `config.yaml.example`.

#### Tooling & installer

- **WhatWaf** integrated into WAF detection (module 7).
- **AlterX + PureDNS** in DNS bruteforce (menu 16).
- **Dual screenshots** — gowitness + EyeWitness under `screenshots/gowitness/` and `screenshots/eyewitness/`.
- **Dynamic Nmap full-port timeout** via `nmap.full_port_timeout_*` config keys.
- **Web UI:** target scope limits (Arjun, FFUF, Nikto, WhatWaf, Tplmap, nomore403), skipped-module indicators, `scan_module_count` on `/api/health`.
- **`install.sh`** — downloads `routes-large.kite` for Kiterunner when missing.
- **Dual-engine SQLi Scan** — module **19** / `sqli` runs **SQLMap** and **Ghauri** on a **merged** candidate list (GF `sqli` pattern + ParamSpider/Arjun + parameterized URLs from `urls_final.txt` / `urls.txt`), not `gf/sqli.txt` alone.
- **Ghauri** — installed via `install.sh` (`/opt/recontools/Ghauri`, `pip install -e`, `link_cli_to_system ghauri`); config block `ghauri.*` in `config.yaml.example`.
- **Web UI** — SQLi section: SQLMap + Ghauri toggles (`ghauri_enabled`, level, risk, threads, `max_targets`); API `/api/config` and `/api/scan/start` pass through.

#### Resilience fallbacks

- Auto **`auto_dirs_wordlist.txt`** if SecLists dir wordlist missing.
- Auto **`auto_resolvers.txt`** for massdns.
- **theHarvester** keyless-source bundle + fallback source list on failure.
- **nomore403** — auto-clone payloads; `_nomore403_command()` runs from repo with `-f payloads`.
- **Directory fuzz** — auto-feed 403/401 responses into nomore403 (per-URL merge into `bypass_results.txt`).
- **SQLi candidates** — empty GF `sqli.txt` no longer skips the whole module when params or URL harvest have query strings.

---

### Changed

- **TUI menu renumbering:** advanced modules are **9–36** (was 10–37); automation is **not** a number slot anymore.
- **Full Spectrum** returns explicit status (`completed` / `aborted` / `setup_failed` / `cancelled`); web engine maps orchestrator lists into API progress.
- **Web engine** uses `SCAN_MODULE_COUNT`, `QUICK_RECON_STEP_COUNT`, and `DEEP_RECON_STEP_COUNT` instead of hardcoded totals.
- **API fuzzing** builds `host:port` target file, resolves/downloads `routes-large.kite`, treats non-zero kr exit with output as partial success.
- **Amass** subdomain pass uses longer scaled timeout (up to 30 min) to reduce false timeouts on passive enum.
- **theHarvester** primary source list is keyless-only (no bufferoverun/dnsdumpster noise without API keys).
- **Jaeles** uses `config init` + per-host output dirs; removed deprecated `--no-output-url` flag (Jaeles v0.17+).
- **Nikto** uses `-h host` + `-ssl` for HTTPS URLs; removed `-nolookup` that caused “given name” errors on URL targets.
- **Cariddi** runs under `/tmp` (tool rejects dots in `output-<domain>/` paths) then copies artifacts back.
- **SQLi module** — `run_sqli_scan()` is canonical; `run_sqlmap_scan()` remains a backward-compatible alias. Ghauri defaults to **parallel** with SQLMap; set `ghauri.parallel: false` for sequential (lower RAM).
- **Cloud / Shodan** modules return proper `MODULE_*` constants instead of bare `return` / implicit `None`.

---

### Fixed

- **`out_file` NameError** in directory fuzz → nomore403 auto-feed.
- **nomore403** `payloads/` path — run from correct working directory.
- **Kiterunner** `-A apiroutes-210228` (space, not `=`) and **MODULE_FAILED** when kr dies (was wrongly `SKIPPED`).
- **Full Spectrum web UI** marking scan “completed” on setup cancel; **`_end_time`** preserved after abort.
- **Duplicate ntfy** finding pings when module-complete notifications enabled.
- **Resume skips** counted as completed in Full Spectrum.
- **Web:** `None` module return treated as failure; overlapping scans blocked while thread alive.
- **Null-safe config** in web API (`(config.get("section") or {})`).
- **Report generation** errors logged instead of silent `pass` on abort path.
- **ParamSpider** v2+ output path discovery under `results/`.
- **EyeWitness** install path (was incorrectly tied to aquatone).
- **Shodan module** missing return status on success/failure (silent pipeline gap).

---

### Documentation

- **README.md** — ntfy section, module status table, menu **A/D/F**, modules **1–36**, SQLi/Ghauri/GF merge, RAM guidance, troubleshooting (kr, nomore403, web overlap).
- **INSTALLATION.md** — Ghauri install/verify notes.
- **web/README.md**, **web/backend/README.md**, **web/frontend/README.md** — SQLi dual-engine and config API fields.
- **`_internal_docs/INTERNAL.md`** — SQLi pipeline (§15), module 19 catalog, Ghauri tool check, web parity.

---

### Notes for operators

| Item | Action |
|:---|:---|
| Shodan / GitHub modules | Add keys under `api_keys` in `~/.config/oculus/config.yaml` |
| Shodan / GitHub skipped | Expected without keys — not a bug |
| Nuclei timeouts on dead hosts | Tool behavior on slow/unresponsive hosts |
| ParamSpider archive errors | External web.archive.org rate limits |
| Full Spectrum runtime | ~2–6 h depending on target size; use **F** + resume |
| SQLi RAM (both engines, parallel) | Often ~400 MB–1.5 GB peak; use `ghauri.parallel: false` or `ghauri.enabled: false` on small VMs |

---

## [4.1.0] - 2026-05-17

### Added

- **Dual-engine probing** — `httprobe` runs alongside `httpx` for alive checks.
- **Background Nmap** — full port scan decoupled from Phase 2 pool to avoid UI stalls.
- **Smart web resume** — Resume vs Start Fresh in configurator and abort flows.
- **Force tool refresh** — bypass cache in Tool Status UI.

### Fixed

- **Arjun/SQLMap targeting** — suffix-matching instead of strict filter drops.
- **Report generation on abort** — try/except wrappers so partial HTML/JSON/MD still write.

---

## [4.0.0] - 2026-05-17

### Added

- **Web cockpit** — FastAPI + React: live logs, scan config, artifacts, reports.
- **Zero-modification CLI** — web wraps the same `Oculus` class as the terminal.

---

## [3.1.0] - 2026-05-15

### Added

- **Full Spectrum Scan** — five-phase pipeline with concurrency and dependency gating.
- **Smart resume** — skip completed steps from `session.json` and marker files.
- **Graceful abort** — Ctrl+C / web Stop saves progress and still generates reports.
- **Data protection** — overwrite warnings for Full Auto and Deep Recon.
- **Suggested next steps** in TUI dashboard.

### Improved

- **Rich TUI** — aligned columns, live stats, color-coded progress.
- **Branding** — “Full-Spectrum Attack Surface Intelligence” tagline.

### Fixed

- **Suggestion engine** — advanced results no longer override core-phase hints incorrectly.

---

## [3.0.0] - 2026-05-14

### Added

- Initial **Oculus** release (rebrand from ReconMaster).
- **Concurrency** via `ThreadPoolExecutor`, streaming command output, `session.json` resume.
- **Reporting** — HTML dashboard, JSON, Markdown.
- Modules: subdomain through exploitation baseline, GF, CORS, smuggling, ASN, cloud, OSINT, and more.

### Changed

- Unified **command runner** with timeouts, retries, and exit-code handling.

---

*Maintained with the Oculus codebase — `VERSION` in `oculus.py`.*
