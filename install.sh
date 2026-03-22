#!/bin/bash
set -e

REPO_URL="https://github.com/GurKalra/prescient-linux.git"
INSTALL_DIR="$HOME/.prescient"

echo "Deploying prescient....."

# Upfront sudo check
echo "Checking sudo privileges for global installation..."
if ! sudo -v &> /dev/null; then
    echo "Error: sudo privileges are required for system-wide installation."
    exit 1
fi

# Check prerequisites
if ! command -v git &> /dev/null || ! command -v python3 &> /dev/null || ! command -v make &> /dev/null; then
    echo "Error: git, python3, and make are required but not installed."
    exit 1
fi

# Check for python 3.11+
PY_VERSION=$(python3 -c "import sys; print(sys.version_info >= (3, 11))")
if [ "$PY_VERSION" != "True" ]; then
    echo "Error: Python 3.11 or higher is required."
    exit 1
fi

# Clone or update the repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin main --quiet
else
    echo "Cloning Prescient repository..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create the isolated virtual enviroment
echo "Setting up isolated Python environment..."
python3 -m venv .venv

# Install the package in editable mode (-e) so it auto-updates with git pulls
echo "Installing dependencies (Developer Mode)..."
.venv/bin/pip install -q -e .

# Calling the Makefile to create the global symlink
echo "Handing off to Makefile for system integration..."
make install

echo ""
echo "[+] Prescient core installed successfully!"
echo "[+] Booting Vanguard Engine (TUI)...."

sleep 1.2

prescient tui