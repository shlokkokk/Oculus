# Oculus v3 — Installation Guide

Oculus is a Python recon orchestrator for **Kali / Debian-style** Linux. The supported path is **`./install.sh`** from your clone; use **Docker** if you are on macOS or do not want a full native toolchain.

For command-line flags, module list, and YAML reference, see **[README.md](README.md)**.

---

## Requirements

| Item | Notes |
|:---|:---|
| **OS** | **Kali** or **Debian / Ubuntu** (glibc Linux). Not tested on Windows native; use **WSL2** or **Docker**. |
| **Python** | **3.8+** (`install.sh` checks this). |
| **Go** | **1.20+** on `PATH` (`go version`). Used for `go install` binaries. |
| **Privileges** | `sudo` for `apt-get` and `/opt/recontools` setup. |
| **Disk** | Plan for **SecLists**, Go build cache, nuclei templates, and scan output (**10 GB+** comfortable). |
| **Network** | Internet to clone repos and download tools/templates. |

---

## Quick install (recommended)

From your machine:

```bash
git clone https://github.com/shlokkokk/Oculus.git
cd Oculus
chmod +x install.sh
./install.sh
```

Use **`./install.sh --update`** later to refresh Go tools and `/opt/recontools` clones (same as `python3 oculus.py --update` from the repo, which runs `git pull` and this script).

### What `install.sh` does

1. Verifies **Python ≥ 3.8** and **`go`** in `PATH` (offers to install the latest Go version if missing).
2. **`apt-get install`**: `python3-pip`, `git`, `wget`, `curl`, `unzip`, `nmap`, `massdns`, `wafw00f`, `whatweb`, `sqlmap`, `jq`.
3. **`pip3 install -r requirements.txt --break-system-packages`** (needed on newer Debian/Ubuntu PEP 668 environments).
4. **`go install`** (see script for exact modules): subfinder, assetfinder, dnsx, httpx, naabu, katana, gau, waybackurls, nuclei, hakrawler, ffuf, dalfox, asnmap, gowitness, gf, amass, kr, subzy.
5. Creates **`/opt/recontools`** and clones: **ParamSpider**, **Arjun**, **XSStrike**, **smuggler**, **LinkFinder**, **theHarvester** (with `pip install -r requirements.txt` per repo where present).
6. Sets up **`~/.gf`** pattern JSONs (best-effort copy from `gf` examples + **Gf-Patterns**).
7. If **`~/.config/oculus/config.yaml`** does not exist yet, copies **`config.yaml.example`** from the same directory as **`install.sh`** (the repo root).

### After `install.sh`

If no config was created (e.g. you already had `~/.config/oculus/config.yaml`), ensure it exists and paths match your machine:

```bash
# Go binaries live here by default
echo 'export PATH="$PATH:$HOME/go/bin"' >> ~/.bashrc
source ~/.bashrc

mkdir -p ~/.config/oculus
cp /path/to/your/Oculus/config.yaml.example ~/.config/oculus/config.yaml
# Edit paths: wordlists (SecLists), massdns resolvers, optional api_keys
```

If **`install.sh`** just created **`~/.config/oculus/config.yaml`**, only add **`PATH`** and edit YAML as needed:

```bash
echo 'export PATH="$PATH:$HOME/go/bin"' >> ~/.bashrc
source ~/.bashrc
```

**Wordlists:** Defaults in `config.yaml.example` assume **SecLists** and **dirb** paths under `/usr/share/wordlists/`. Install or adjust YAML to match your system:

```bash
sudo apt install -y seclists dirb   # package names may vary by distro
```

**`dig`:** Used for CDN checks and CNAME work. If missing: `sudo apt install -y dnsutils` (Debian/Ubuntu) or equivalent.

---

## Verify installation

```bash
cd /path/to/Oculus
python3 oculus.py --version
python3 oculus.py
# In the menu: I = tool check, C = set domain, then try 1 (subdomain enum)
```

Sanity-check common externals:

```bash
which subfinder httpx naabu nuclei ffuf dalfox dnsx massdns
ls /opt/recontools/ParamSpider/paramspider.py
```

---

## Docker (alternative)

From the repo root:

```bash
docker build -t oculus .
docker run --rm -it -v "$(pwd):/app" oculus -d example.com --module subdomain --no-confirm
```

See **README.md** for bind mounts, API keys, and wordlist paths inside the image.

---

## Manual installation

Use this only if `install.sh` fails or you need a minimal custom layout. Mirror the versions in **`install.sh`** when possible.

### 1. System packages (Debian / Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip git wget curl unzip build-essential \
  nmap massdns wafw00f whatweb sqlmap jq dnsutils libpcap-dev
```

Install **Go** from [go.dev](https://go.dev/dl/) if your distro ships an old version; Oculus expects **Go ≥ 1.20**.

### 2. Python dependencies

```bash
cd /path/to/Oculus
pip3 install -r requirements.txt --break-system-packages
```

Packages: `requests`, `urllib3`, `dnspython`, `tldextract`, `rich` (recommended), `pyyaml` (recommended).

### 3. Go tools

```bash
export PATH="$PATH:$HOME/go/bin"
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/tomnomnom/assetfinder@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/lc/gau/v2/cmd/gau@latest
go install github.com/tomnomnom/waybackurls@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/hakluke/hakrawler@latest
go install github.com/ffuf/ffuf/v2@latest
go install github.com/hahwul/dalfox/v2@latest
go install github.com/projectdiscovery/asnmap/cmd/asnmap@latest
go install github.com/sensepost/gowitness@latest
go install github.com/tomnomnom/gf@latest
go install github.com/owasp-amass/amass/v4/...@master
go install github.com/assetnote/kiterunner/cmd/kr@latest
go install github.com/LukaSikic/subzy@latest
```

### 4. `/opt/recontools` Python tools

```bash
sudo mkdir -p /opt/recontools
sudo chown -R "$USER:$USER" /opt/recontools
cd /opt/recontools
git clone https://github.com/devanshbatham/ParamSpider.git
git clone https://github.com/s0md3v/Arjun.git
git clone https://github.com/s0md3v/XSStrike.git
git clone https://github.com/defparam/smuggler.git
git clone https://github.com/GerbenJavado/LinkFinder.git
git clone https://github.com/laramies/theHarvester.git
for d in ParamSpider Arjun XSStrike smuggler LinkFinder theHarvester; do
  [ -f "$d/requirements.txt" ] && pip3 install -r "$d/requirements.txt" --break-system-packages || true
done
```

### 5. GF patterns

```bash
mkdir -p ~/.gf
git clone https://github.com/1ndianl33t/Gf-Patterns.git /tmp/Gf-Patterns 2>/dev/null || true
cp /tmp/Gf-Patterns/*.json ~/.gf/ 2>/dev/null || true
```

### 6. Optional: `oculus` on PATH

```bash
sudo ln -sf /path/to/Oculus/oculus.py /usr/local/bin/oculus
sudo chmod +x /usr/local/bin/oculus
# shebang already invokes python3
```

---

## Other platforms

### Kali Linux

Primary target. **`./install.sh`** matches typical Kali package names. Enable **`~/go/bin`** on `PATH` after install.

### Ubuntu / Debian

Same as Kali; ensure **Go** is recent enough. Some optional packages differ; adjust `apt` names if a package is missing.

### Arch Linux

Install `go`, `python`, `nmap`, `massdns`, etc. from Arch/AUR; run the **Manual installation** Go and pip sections. There is no Arch-specific script in this repo.

### macOS

Oculus expects Linux-style paths and tools (`/opt/recontools`, GNU assumptions in places). Prefer **Docker** or a **Linux VM** rather than native macOS for full parity.

---

## Troubleshooting

### `command not found` for Go tools

```bash
export GOPATH="${GOPATH:-$HOME/go}"
export PATH="$PATH:$GOPATH/bin"
hash -r
```

### `pip` refuses system install (externally-managed-environment)

Use the same flag as `install.sh`:

```bash
pip3 install -r requirements.txt --break-system-packages
```

Or use a **venv** and run `oculus.py` with that interpreter (you must install CLI tools into `PATH` separately; venv does not replace `subfinder`, `nuclei`, etc.).

### Missing wordlists or resolvers

Edit **`~/.config/oculus/config.yaml`** (`wordlists.*`, `resolvers`). Defaults point at SecLists and `/opt/recontools/massdns/resolvers.txt`. 

> [!TIP]
> **Auto-Healing DNS Resolvers (v4.0.0+)**: If your installer didn't run with root privileges or hit transient network errors (leaving `/usr/share/massdns/resolvers.txt` missing), **Oculus now dynamically heals itself**. It will automatically print a warning and generate a comprehensive `auto_resolvers.txt` in your session folder, containing **over 120+ un-nerfed premium public recursive DNS resolvers** (Google, Cloudflare, OpenDNS, Level3/CenturyLink, OpenNIC, etc.) to ensure concurrent bruteforcing runs at extreme speeds without any rate-limits.

### `massdns` / `dig` not found

```bash
sudo apt-get install -y massdns dnsutils
```

### Nuclei templates empty or old

```bash
nuclei -ut
```

### Permission errors under `/opt/recontools`

```bash
sudo chown -R "$USER:$USER" /opt/recontools
```

### Oculus says a tool is missing

Run **menu `I`** (initialize tools) or compare with **`install.sh`** list. Install the suggested `go install …` or apt package.

---

## Updating Oculus

```bash
cd /path/to/Oculus
git pull
./install.sh --update
```

Refresh Nuclei templates periodically: `nuclei -ut`.

---

## Testing a minimal flow

```bash
cd /path/to/Oculus
python3 oculus.py
# C → enter a domain you are allowed to test (e.g. your own)
# 1 → subdomain enumeration
ls -la "output-<domain>/"
```

CLI smoke test:

```bash
python3 oculus.py -d example.com --module subdomain --no-confirm
```

Only use domains you are authorized to assess.

---

## Security and legal use

- Run Oculus **only** against assets you **own** or have **written permission** to test.
- Respect rate limits, scope rules, and local laws.
- API keys (GitHub, Shodan) send queries to third parties; handle keys as secrets.

---

## Post-install checklist

- [ ] `python3 oculus.py --version` prints **3.0**
- [ ] `which subfinder httpx naabu nuclei` succeeds (after `PATH` includes `~/go/bin`)
- [ ] `/opt/recontools/ParamSpider/paramspider.py` exists
- [ ] `~/.config/oculus/config.yaml` exists and paths match your machine
- [ ] SecLists (or custom) wordlists exist where YAML points
- [ ] Menu **I** shows critical tools installed
- [ ] Menu **C** + **1** produces `output-<domain>/subdomains.txt` for a permitted target

---

When this checklist passes, the native toolchain is ready. Use **[README.md](README.md)** for workflows, **Deep** vs **Full** recon, and reporting.
