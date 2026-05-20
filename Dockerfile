# ==========================================================
# STAGE 1: Build the React Frontend SPA
# ==========================================================
FROM node:18-alpine AS frontend-builder
WORKDIR /web/frontend

# Copy frontend package manifests for dependency installation caching
COPY web/frontend/package*.json ./
RUN npm ci

# Copy the rest of the React dashboard source code and build it
COPY web/frontend/ ./
RUN npm run build

# ==========================================================
# STAGE 2: Build the Core Oculus Scanner & Backend Server
# ==========================================================
FROM kalilinux/kali-rolling

# Set non-interactive timezone / installation mode
ENV DEBIAN_FRONTEND=noninteractive

# Update and install base requirements (including sudo so install.sh does not fail)
RUN apt-get update && apt-get install -y \
    sudo \
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

# Install Go dynamically matching the CPU architecture (amd64, arm64, etc.)
ENV GOLANG_VERSION=1.21.3
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "armhf" ]; then ARCH="armv6l"; fi && \
    wget -q "https://dl.google.com/go/go${GOLANG_VERSION}.linux-${ARCH}.tar.gz" && \
    tar -C /usr/local -xzf "go${GOLANG_VERSION}.linux-${ARCH}.tar.gz" && \
    rm "go${GOLANG_VERSION}.linux-${ARCH}.tar.gz"

ENV PATH=$PATH:/usr/local/go/bin:/root/go/bin
ENV GOPATH=/root/go

# Setup working directory framework
WORKDIR /app

# CACHE LAYER OPTIMIZATION: Copy requirements manifests first
COPY requirements.txt /app/
COPY web/backend/requirements.txt /app/web/backend/

# Install python packages globally inside the container for both CLI and Web API
RUN pip3 install --no-cache-dir -r requirements.txt -r web/backend/requirements.txt --break-system-packages

# Execute dependencies setup script (will be heavily cached by Docker daemon)
COPY install.sh config.yaml.example /app/
RUN chmod +x install.sh && ./install.sh --update --non-interactive

# Copy the rest of the application files
COPY . /app

# Inject the compiled React frontend static build from Stage 1 into the FastAPI serving path
COPY --from=frontend-builder /web/frontend/dist /app/web/frontend/dist

# Expose the single unified port for the FastAPI server & React Web Dashboard
EXPOSE 8000

# Default behavior: Launch the Oculus Web Control HUD (can be overridden to run CLI)
CMD ["python3", "-m", "uvicorn", "web.backend.server:app", "--host", "0.0.0.0", "--port", "8000"]


