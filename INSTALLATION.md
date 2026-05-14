# ReconMaster Installation Guide

## 🚀 Quick Installation

### Automated Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/reconmaster.git
cd reconmaster

# Make installation script executable
sudo chmod +x install.sh

# Run installation
sudo ./install.sh
```

### Manual Installation

If you prefer manual installation or encounter issues with the automated script:

#### 1. System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git wget curl build-essential python3 python3-pip \
    python3-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev \
    libjpeg62-turbo-dev zlib1g-dev libpcap-dev nmap masscan wafw00f \
    amass jq ruby ruby-dev golang-go snapd
```

#### 2. Install Go Tools

```bash
# Set Go environment
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin
mkdir -p $GOPATH/bin

# Install security tools
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/tomnomnom/assetfinder@latest
go install github.com/tomnomnom/waybackurls@latest
go install github.com/lc/gau@latest

# Make Go tools available system-wide
sudo cp ~/go/bin/* /usr/local/bin/
```

#### 3. Python Environment

```bash
# Install Python packages
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

#### 4. Install ReconMaster

```bash
# Copy to system location
sudo cp reconmaster.py /usr/local/bin/reconmaster
sudo chmod +x /usr/local/bin/reconmaster

# Create wordlists directory
sudo mkdir -p /usr/share/wordlists/reconmaster
```

#### 5. Verify Installation

```bash
# Test ReconMaster
reconmaster

# Check tool availability
which subfinder httpx naabu nuclei
```

---

## 📋 System Requirements

### Minimum Requirements

- **Operating System**: Kali Linux 2020.1 or later
- **Python**: 3.6 or higher
- **RAM**: 4GB minimum
- **Storage**: 2GB free space
- **Network**: Internet connection for tool downloads

### Recommended Requirements

- **Operating System**: Kali Linux 2023.3 or later
- **Python**: 3.9 or higher
- **RAM**: 8GB or more
- **Storage**: 10GB free space
- **Network**: High-speed internet connection

---

## 🛠️ Platform-Specific Instructions

### Kali Linux (Primary)

ReconMaster is optimized for Kali Linux. The automated installation script handles all dependencies.

```bash
# Standard installation
sudo ./install.sh
```

### Ubuntu/Debian

```bash
# Install dependencies manually
sudo apt update
sudo apt install -y git golang-go python3-pip

# Follow manual installation steps
# Note: Some tools may not be available in default repositories
```

### Arch Linux

```bash
# Install dependencies
sudo pacman -S git go python-pip

# Install tools from AUR (use yay or similar)
yay -S subfinder httpx naabu nuclei

# Follow manual installation steps
```

### macOS

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install git go python3

# Install tools
brew install projectdiscovery/tap/subfinder
brew install projectdiscovery/tap/httpx
brew install projectdiscovery/tap/naabu
brew install projectdiscovery/tap/nuclei

# Follow manual installation steps
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Command not found" errors

```bash
# Check if reconmaster is in PATH
which reconmaster

# If not found, create symlink
sudo ln -s /path/to/reconmaster.py /usr/local/bin/reconmaster

# Or run directly
python3 /path/to/reconmaster.py
```

#### 2. Missing Go tools

```bash
# Check GOPATH
echo $GOPATH

# Set GOPATH if empty
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Reinstall tools
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
# ... repeat for other tools
```

#### 3. Permission errors

```bash
# Fix file permissions
sudo chmod +x /usr/local/bin/reconmaster
sudo chmod 755 /usr/local/bin/reconmaster

# Fix directory permissions
sudo chmod 755 /usr/local/bin/
```

#### 4. Python module errors

```bash
# Install missing Python packages
pip3 install colorama termcolor pyfiglet requests

# Or install all requirements
pip3 install -r requirements.txt
```

#### 5. Network connectivity issues

```bash
# Test internet connectivity
ping 8.8.8.8
nslookup github.com

# Check proxy settings
env | grep -i proxy
```

---

## 🐛 Advanced Troubleshooting

### Debug Mode

```bash
# Run with debug output
python3 -u /usr/local/bin/reconmaster 2>&1 | tee debug.log

# Check for specific errors
grep -i error debug.log
grep -i "failed\|error\|exception" debug.log
```

### Tool Verification

```bash
# Verify each tool is working
subfinder --version
httpx --version
naabu --version
nuclei --version

# Test basic functionality
subfinder -d example.com -silent | head -5
httpx -l <(echo "example.com") -silent
```

### Environment Issues

```bash
# Check environment variables
env | grep -E "(PATH|GOPATH|PYTHON)"

# Reset environment if needed
unset GOPATH
export GOPATH=$HOME/go
export PATH=/usr/local/bin:/usr/bin:/bin:$GOPATH/bin
```

---

## 🔄 Updating ReconMaster

### Update to Latest Version

```bash
# Pull latest changes
git pull origin main

# Re-run installation
sudo ./install.sh

# Or manually update
sudo cp reconmaster.py /usr/local/bin/reconmaster
```

### Update Tools

```bash
# Update Go tools
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
# ... repeat for other tools

# Update Nuclei templates
nuclei -ut
```

---

## 🧪 Testing Installation

### Basic Test

```bash
# Start ReconMaster
reconmaster

# Should show main menu with ASCII banner
```

### Comprehensive Test

```bash
# Create test directory
mkdir -p /tmp/reconmaster-test
cd /tmp/reconmaster-test

# Test with example domain
reconmaster
# Select 'C' and enter: example.com
# Select '1' for subdomain enumeration
# Check if results are generated

# Verify output
ls -la output-example.com/
cat output-example.com/summary.txt
```

---

## 🛡️ Security Considerations

### Legal Usage

- **Only scan targets you own or have explicit permission to test**
- **Respect rate limits and robots.txt files**
- **Follow responsible disclosure practices**
- **Comply with all applicable laws and regulations**

### Best Practices

- **Target Validation**: Verify domain ownership before scanning
- **Rate Control**: Use appropriate timeouts for target infrastructure
- **Data Protection**: Secure storage of scan results
- **Privacy**: No data transmitted to external services

---

## 📞 Getting Help

### Self-Help Resources

1. **Check logs**: Review execution logs in `logs/` directory
2. **Read documentation**: Comprehensive README and help system
3. **Test tools individually**: Verify each tool works standalone
4. **Check permissions**: Ensure proper file and directory permissions

### Community Support

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Wiki and usage guides
- **Community**: Security and bug bounty forums

### Professional Support

For enterprise deployments or custom integrations, consider professional support options.

---

## 📋 Post-Installation Checklist

- [ ] ReconMaster starts without errors
- [ ] All tools are detected as installed
- [ ] Can set target domain successfully
- [ ] Subdomain enumeration works
- [ ] Results are saved to output directory
- [ ] Summary report is generated
- [ ] Can access help system
- [ ] Can exit cleanly

---

**Congratulations!** 🎉 You now have ReconMaster installed and ready for professional reconnaissance operations.

Happy hunting! 🎯