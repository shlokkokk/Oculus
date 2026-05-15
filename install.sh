#!/bin/bash

# Oculus v3 Professional Install Script
# Hardened, idempotent, with version pinning and update support

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
CYAN="\033[1;36m"
RESET="\033[0m"

UPDATE_MODE=false
if [ "$1" == "--update" ]; then
    UPDATE_MODE=true
    echo -e "${YELLOW}[*] Update mode enabled. Will upgrade existing tools.${RESET}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}[*] Starting Oculus Environment Setup...${RESET}"

# 1. System Requirements Check
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}[!] Note: This script requires 'sudo' for system packages and /opt/recontools.${RESET}"
  echo -e "${YELLOW}[*] Please ensure you have sudo privileges.${RESET}"
fi

# Check Python >= 3.8
PY_VER=$(python3 -c 'import sys; print("1") if sys.version_info >= (3, 8) else print("0")')
if [ "$PY_VER" == "0" ]; then
    echo -e "${RED}[!] Python 3.8+ is required! Please upgrade.${RESET}"
    exit 1
fi

# 2. APT Packages (Bootstrap)
echo -e "${CYAN}[*] Installing baseline dependencies...${RESET}"
sudo apt-get update
sudo apt-get install -y git wget curl unzip

# Check Go
if ! command -v go &> /dev/null; then
    echo -e "${YELLOW}[!] Go is not installed.${RESET}"
    read -p "    Do you want to install the latest Go version now? (y/n): " INSTALL_GO
    if [[ "$INSTALL_GO" =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}[*] Fetching latest Go version...${RESET}"
        LATEST_GO=$(curl -s https://go.dev/VERSION?m=text | head -n 1)
        echo -e "${CYAN}[*] Installing $LATEST_GO...${RESET}"
        wget -q https://dl.google.com/go/${LATEST_GO}.linux-amd64.tar.gz
        sudo tar -C /usr/local -xzf ${LATEST_GO}.linux-amd64.tar.gz
        rm ${LATEST_GO}.linux-amd64.tar.gz
        export PATH=$PATH:/usr/local/go/bin:~/go/bin
        echo -e "${GREEN}[✔] $LATEST_GO installed. PATH will be updated below.${RESET}"
    else
        echo -e "${RED}[!] Go >= 1.20 is required for Oculus! Please install it manually.${RESET}"
        exit 1
    fi
fi

# 3. APT Packages (Rest)
echo -e "${CYAN}[*] Installing remaining system dependencies...${RESET}"
sudo apt-get install -y python3-pip nmap massdns wafw00f whatweb sqlmap jq

# 3. Python Packages
echo -e "${CYAN}[*] Installing Python requirements...${RESET}"
pip3 install -r requirements.txt --break-system-packages

# 4. ProjectDiscovery & Go Tools (with version pinning)
echo -e "${CYAN}[*] Installing/Updating Go tools...${RESET}"

# Ensure Go binaries are in PATH for this session
export PATH=$PATH:/usr/local/go/bin:~/go/bin:$GOPATH/bin

# Function to add to shell config if not present
add_to_path() {
    local shell_config=$1
    if [ -f "$shell_config" ]; then
        if ! grep -q "go/bin" "$shell_config"; then
            echo 'export PATH=$PATH:/usr/local/go/bin:~/go/bin' >> "$shell_config"
            echo -e "${GREEN}[✔] Added Go to PATH in $shell_config${RESET}"
        fi
    fi
}

add_to_path "$HOME/.bashrc"
add_to_path "$HOME/.zshrc"

install_go_tool() {
    TOOL_NAME=$1
    REPO=$2
    if ! command -v $TOOL_NAME &> /dev/null || [ "$UPDATE_MODE" = true ]; then
        echo -e "${YELLOW} -> Installing $TOOL_NAME...${RESET}"
        go install $REPO
    else
        echo -e "${GREEN} -> $TOOL_NAME already installed. Skipping.${RESET}"
    fi
}

install_go_tool "subfinder" "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
install_go_tool "assetfinder" "github.com/tomnomnom/assetfinder@latest"
install_go_tool "dnsx" "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
install_go_tool "httpx" "github.com/projectdiscovery/httpx/cmd/httpx@latest"
install_go_tool "naabu" "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
install_go_tool "katana" "github.com/projectdiscovery/katana/cmd/katana@latest"
install_go_tool "gau" "github.com/lc/gau/v2/cmd/gau@latest"
install_go_tool "waybackurls" "github.com/tomnomnom/waybackurls@latest"
install_go_tool "nuclei" "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
install_go_tool "hakrawler" "github.com/hakluke/hakrawler@latest"
install_go_tool "ffuf" "github.com/ffuf/ffuf/v2@latest"
install_go_tool "dalfox" "github.com/hahwul/dalfox/v2@latest"
install_go_tool "asnmap" "github.com/projectdiscovery/asnmap/cmd/asnmap@latest"
install_go_tool "gowitness" "github.com/sensepost/gowitness@latest"
install_go_tool "gf" "github.com/tomnomnom/gf@latest"
install_go_tool "amass" "github.com/owasp-amass/amass/v4/...@master"
install_go_tool "kr" "github.com/assetnote/kiterunner/cmd/kr@latest"
install_go_tool "subzy" "github.com/LukaSikic/subzy@latest"

# 5. Custom /opt/recontools installations
echo -e "${CYAN}[*] Installing custom Python/GitHub tools to /opt/recontools...${RESET}"
sudo mkdir -p /opt/recontools
sudo chown -R $USER:$USER /opt/recontools
cd /opt/recontools

clone_or_update() {
    REPO_URL=$1
    DIR_NAME=$2
    if [ ! -d "$DIR_NAME" ]; then
        echo -e "${YELLOW} -> Cloning $DIR_NAME...${RESET}"
        git clone $REPO_URL $DIR_NAME
        cd $DIR_NAME && pip3 install -r requirements.txt --break-system-packages || true
        cd ..
    elif [ "$UPDATE_MODE" = true ]; then
        echo -e "${YELLOW} -> Updating $DIR_NAME...${RESET}"
        cd $DIR_NAME && git pull && pip3 install -r requirements.txt --break-system-packages || true
        cd ..
    else
        echo -e "${GREEN} -> $DIR_NAME already exists. Skipping.${RESET}"
    fi
}

clone_or_update "https://github.com/devanshbatham/ParamSpider" "ParamSpider"
clone_or_update "https://github.com/s0md3v/Arjun" "Arjun"
clone_or_update "https://github.com/s0md3v/XSStrike" "XSStrike"
clone_or_update "https://github.com/defparam/smuggler" "smuggler"
clone_or_update "https://github.com/GerbenJavado/LinkFinder" "LinkFinder"
clone_or_update "https://github.com/laramies/theHarvester" "theHarvester"

# Setup GF patterns
mkdir -p ~/.gf
cp -r /root/go/pkg/mod/github.com/tomnomnom/gf*/examples/*.json ~/.gf/ 2>/dev/null || true
git clone https://github.com/1ndianl33t/Gf-Patterns 2>/dev/null || true
cp Gf-Patterns/*.json ~/.gf/ 2>/dev/null || true

# Default config (only if user has none — do not overwrite existing)
if [ ! -f "$HOME/.config/oculus/config.yaml" ] && [ -f "$SCRIPT_DIR/config.yaml.example" ]; then
    mkdir -p "$HOME/.config/oculus"
    cp "$SCRIPT_DIR/config.yaml.example" "$HOME/.config/oculus/config.yaml"
    echo -e "${GREEN}[✔] Installed default config to ~/.config/oculus/config.yaml${RESET}"
fi

echo -e "${GREEN}[✔] Oculus professional installation complete!${RESET}"
echo -e "${YELLOW}[!] Make sure ~/go/bin is in your PATH.${RESET}"