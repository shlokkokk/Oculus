FROM kalilinux/kali-rolling

# Set non-interactive timezone
ENV DEBIAN_FRONTEND=noninteractive

# Update and install base requirements
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    unzip \
    nmap \
    massdns \
    wafw00f \
    whatweb \
    sqlmap \
    jq \
    ruby-dev \
    libpcap-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Go
ENV GOLANG_VERSION=1.21.3
RUN wget -q https://dl.google.com/go/go${GOLANG_VERSION}.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go${GOLANG_VERSION}.linux-amd64.tar.gz && \
    rm go${GOLANG_VERSION}.linux-amd64.tar.gz

ENV PATH=$PATH:/usr/local/go/bin:/root/go/bin
ENV GOPATH=/root/go

# Setup working directory
WORKDIR /app
COPY . /app

# Install Python requirements
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Make install script executable and run it to get Go tools and custom tools
RUN chmod +x install.sh && ./install.sh --update

ENTRYPOINT ["python3", "oculus.py"]
