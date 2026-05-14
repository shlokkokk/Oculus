<p align="center">
  <img src="https://img.shields.io/badge/OCULUS-v3.0-00FFFF?style=for-the-badge&logo=opsgenie&logoColor=white" />
  <img src="https://img.shields.io/badge/PLATFORM-KALI_LINUX-orange?style=for-the-badge&logo=kali-linux&logoColor=white" />
  <img src="https://img.shields.io/badge/LICENSE-MIT-green?style=for-the-badge&logo=git&logoColor=white" />
</p>

<h1 align="center">
  OCULUS
</h1>

<p align="center">
  <b>Advanced Reconnaissance & Attack Surface Mapping Framework</b><br>
  <i>Built for high-performance security auditing and automated enumeration.</i>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-the-29-module-arsenal">The Arsenal</a> •
  <a href="#️-configuration-guide">Configuration</a> •
  <a href="#-executive-reporting">Reporting</a>
</p>

---

## 🔥 Overview

Oculus is an intelligent, high-performance reconnaissance framework engineered for serious bug bounty hunters and penetration testers. Version 3.0 represents a total architectural transformation, delivering true concurrency, streaming terminal analytics, stateful execution, and a massive arsenal of 29 integrated security modules.

It orchestrates the industry's most powerful security tools into a single, cohesive workflow—providing maximum coverage with minimal noise.

### ✨ Key Features

- **🎨 Tactical Interface** - Professional ASCII art, color-coded severity mapping, and live streaming outputs.
- **⚡ High-Octane Concurrency** - Orchestrates multiple independent tools simultaneously via a thread pool executor.
- **💾 Stateful Resumption** - Never lose data. Scan interrupted? Oculus automatically resumes from the exact module using `session.json`.
- **🔄 Diff Engine** - Automatically cross-references rescans of a target to highlight net-new infrastructure and vulnerabilities.
- **🛡️ Strict Scope Enforcement** - Validates endpoints against the target boundary to prevent accidental out-of-scope engagement.
- **📊 Automated Reporting** - Generates rich HTML dashboards, machine-readable JSON artifacts, and HackerOne-ready Markdown reports.

---

## 🚀 Quick Start

### Installation

The included installer is hardened, idempotent, and handles Go version pinning automatically.

```bash
# Clone the repository
git clone https://github.com/shlokkokk/Oculus
cd Oculus

# Install the framework and dependencies
sudo chmod +x install.sh
sudo ./install.sh
```

### Basic Usage

```bash
# Start the interactive console
python3 oculus.py

# Quick workflow:
1. Select option 'C' to set your target domain (e.g., target.com)
2. Select option '9' for Full Automated Recon
3. Review results in output-target.com/
```

### Non-Interactive Automation

Oculus supports a fully headless CLI for CI/CD and cron job integration:

```bash
# Run the core pipeline headlessly
python3 oculus.py -d target.com --full-recon --no-confirm

# Unleash Deep Recon Mode with jitter (stealth) and custom threads
python3 oculus.py -d target.com --deep --threads 100 --jitter

# Update the framework and all 29 tools to latest versions
python3 oculus.py --update

# Run specific modules
python3 oculus.py -d target.com --module subdomain,alive,ports,vuln
```

---

## 📋 The 29-Module Arsenal

### Core Reconnaissance Pipeline
| Option | Module | Description | Engine |
|--------|--------|-------------|------------|
| **1** | Subdomain Enumeration | Discover subdomains using multiple sources | Subfinder, Amass, Assetfinder |
| **2** | DNS Resolution | Resolve DNS records for subdomains | DNSx |
| **3** | Alive Hosts Check | Identify live web servers | HTTPx |
| **4** | Fast Port Scan | Quick port discovery | Naabu |
| **5** | Full Port Scan | Comprehensive service detection | Nmap |
| **6** | URL Collection | Gather endpoints from multiple sources | Katana, Gau, Waybackurls |
| **7** | WAF Detection | Identify Web Application Firewalls | Wafw00f |
| **8** | Vulnerability Scan | Automated vulnerability assessment | Nuclei |
| **9** | **FULL AUTOMATED RECON** | **Executes Core Pipeline (1-8)** | **Oculus Engine** |

### Advanced Reconnaissance Modules (v3)
| Option | Module | Description | Engine |
|--------|--------|-------------|------------|
| **10** | Parameter Discovery | Find hidden GET/POST parameters | ParamSpider, Arjun |
| **11** | JS Endpoint Extraction | Extract JS endpoints & hunt for hardcoded secrets | LinkFinder, Regex |
| **12** | Directory Fuzzing | Recursive fuzzing with smart extensions | FFUF |
| **13** | API Fuzzing | Bruteforce API endpoints | Kiterunner |
| **14** | Subdomain Takeover Check | Detect takeover risks using CNAME analysis | Subzy |
| **15** | Advanced URL Enum | Deep crawling beyond base URL | Hakrawler |
| **16** | Screenshot Capture | Take screenshots of alive hosts | Gowitness |
| **17** | DNS Bruteforce | High-speed subdomain bruteforce | MassDNS |
| **18** | GF Filters | Extract XSS/SQLi/LFI/SSRF patterns | GF |
| **19** | Technology Scan | Fingerprint tech stack details | WhatWeb |
| **20** | SQL Injection Scan | Auto SQLMap exploitation | SQLMap |
| **21** | XSS Automation | Payload delivery against GF parameters | Dalfox |
| **22** | CORS Scanner | Misconfiguration & wildcard detection | Oculus Native |
| **23** | HTTP Smuggling | Request desync vulnerability scanning | Smuggler |
| **24** | ASN Discovery | Maps target IP infrastructure | ASNmap |
| **25** | Cloud Assets | Detects exposed AWS S3, GCP, and Azure buckets | Oculus Native |
| **26** | GitHub Dorking | Hunts for leaked secrets using the GitHub API | Oculus Native |
| **27** | OSINT Harvesting | Gathers emails and data | theHarvester |
| **28** | Shodan Recon | Passive port and service discovery | Shodan API |
| **29** | Open Redirect Scan | Exploit verification using GF payloads | Oculus Native |
| **D** | **DEEP RECON MODE** | **Executes Modules 10-29 automatically** | **Oculus Engine** |

---

## ⚙️ Architecture & Data Structure

### Output Directory Mapping

Oculus maintains a pristine, highly organized data structure for every target:

```text
output-target.com/
├── subdomains.txt
├── dns_resolved.txt
├── alive.txt
├── ports_fast.txt
├── ports_full.txt
├── urls_final.txt
├── js_endpoints/        # Linkfinder outputs & regex secret hits
├── parameters/          # Merged Arjun and Paramspider outputs
├── fuzzing/             # FFUF JSON artifacts
├── takeover/            # Subzy reports
├── screenshots/         # Gowitness PNGs
├── gf/                  # Categorized injection vectors (xss.txt, sqli.txt)
├── cloud/               # Exposed S3 buckets
├── github/              # Leaked API keys and tokens
├── osint/               # Harvester data
├── shodan/              # Passive port data
├── session.json         # State persistence core
└── report.html          # Interactive executive dashboard
```

## ⚙️ Configuration Guide

Oculus uses a centralized YAML configuration system. By default, it looks for settings in `~/.config/oculus/config.yaml`, but will fallback to `config.yaml` in the current directory.

### Full Configuration Reference (`config.yaml`)

| Setting | Type | Description |
|---------|------|-------------|
| `threads` | Int | Global thread count for concurrent modules (e.g., 50). |
| `timeout` | Int | Default timeout in seconds for any tool execution. |
| `jitter` | Bool | If `true`, adds random sub-second delays between tool calls for stealth. |
| `parallel` | Bool | If `true`, runs independent tools (like Subfinder & Amass) simultaneously. |
| `auto_confirm` | Bool | Skips all "Continue?" prompts for headless automation. |

#### Example `config.yaml` Structure:
```yaml
# API Integration (Critical for Passive Recon)
api_keys:
  shodan: "YOUR_SHODAN_KEY"    # Enables Module 28
  github: "YOUR_GITHUB_TOKEN"  # Enables Module 26
  chaos: "YOUR_CHAOS_KEY"

# Wordlist Management
wordlists:
  dns: "/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt"
  dirs: "/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt"
  resolvers: "/opt/recontools/massdns/resolvers.txt"

# Tool Tuning
nuclei:
  severity: "low,medium,high,critical"
  rate_limit: 150
  concurrency: 25
  templates: ""                # Leave empty for default templates
```

### Quick Setup
1. **Initialize Config**:
   ```bash
   mkdir -p ~/.config/oculus
   cp config.yaml.example ~/.config/oculus/config.yaml
   ```
2. **Add Tokens**: Edit `~/.config/oculus/config.yaml` and add your Shodan and GitHub API tokens to unlock passive scanning.

---

## 📊 Executive Reporting

Upon completion of any scanning pipeline, Oculus generates three types of reports in the target directory:
1. **`report.html`**: A visually stunning, dark-themed dashboard featuring interactive screenshots, a sortable vulnerability table, and severity statistics.
2. **`findings.json`**: A highly structured machine-readable artifact perfect for ingesting into Jira, ElasticSearch, or SIEMs.
3. **`report.md`**: A clean, organized Markdown summary built specifically for copy-pasting into Bugcrowd/HackerOne submissions.

---

## 🔧 Workflow Examples & Integration

### Exporting for Continuous Monitoring
```bash
# Pipe active infrastructure directly into JSON for tracking
cat output-target.com/alive.txt | httpx -silent -json > active_infrastructure.json
```

### Burp Suite Handoff
```bash
# Send all discovered parameters straight to Burp Suite for manual testing
cat output-target.com/parameters/parameters_final.txt | while read url; do
    curl -x http://127.0.0.1:8080 "$url"
done
```

### Troubleshooting Tools

**KR (Kiterunner) fails or exits instantly**
Ensure `kr` is symlinked correctly:
```bash
ls /usr/local/bin/kr
# If missing, reinstall:
go install github.com/assetnote/kiterunner/cmd/kr@latest
```

**Missing tools after installation**
```bash
# Re-run the tool initialization directly from the menu
python3 oculus.py
# Select option 'I' to instantly check and install missing tools
```

---

## ⚠️ Security & Legal Considerations

Oculus performs **high-intensity active recon modules** such as directory fuzzing, SQLMap exploitation, MassDNS bruteforcing, and API payload delivery. 

**Responsible Usage:** Only scan targets you own or have explicit, legal permission to test (e.g., active Bug Bounty programs). The authors are not responsible for any misuse, downtime, or damage caused by this program.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
