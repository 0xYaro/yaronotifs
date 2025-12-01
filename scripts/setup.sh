#!/bin/bash

###############################################################################
# AWS Ubuntu Server Setup Script
#
# This script sets up the Telegram Intelligence Bot on a fresh Ubuntu server.
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# Requirements:
#   - Ubuntu 20.04 or newer
#   - sudo privileges
###############################################################################

set -e  # Exit on error

echo "=========================================="
echo "YARONOTIFS - AWS SERVER SETUP"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root (don't use sudo)"
    exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python 3.10+ if not present
print_status "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_warning "Python 3 not found. Installing..."
    sudo apt install -y python3 python3-pip python3-venv
else
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_status "Python 3 found: $(python3 --version)"
fi

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y \
    git \
    wget \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev

# Create virtual environment
print_status "Creating Python virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p temp
mkdir -p logs

# Check for .env file
if [ ! -f ".env" ]; then
    print_warning ".env file not found!"
    echo ""
    echo "Please create a .env file based on .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    echo ""
    echo "Then fill in your configuration values."
else
    print_status ".env file found"
fi

# Check for session file
SESSION_FILE=$(grep -E '^SESSION_NAME=' .env 2>/dev/null | cut -d'=' -f2 || echo "yaronotifs_session")
SESSION_FILE="${SESSION_FILE}.session"

if [ ! -f "$SESSION_FILE" ]; then
    print_warning "Session file not found: $SESSION_FILE"
    echo ""
    echo "Please upload your session file to this directory:"
    echo "  scp $SESSION_FILE user@server:$(pwd)/"
    echo ""
    echo "If you haven't created a session file yet, run this on your LOCAL machine:"
    echo "  python scripts/create_session.py"
else
    print_status "Session file found: $SESSION_FILE"
fi

# Create systemd service file
print_status "Creating systemd service..."

SERVICE_FILE="/etc/systemd/system/yaronotifs.service"
WORKING_DIR=$(pwd)
USER=$(whoami)

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Yaronotifs Telegram Intelligence Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKING_DIR
Environment="PATH=$WORKING_DIR/venv/bin"
ExecStart=$WORKING_DIR/venv/bin/python $WORKING_DIR/main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:$WORKING_DIR/logs/bot.log
StandardError=append:$WORKING_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

print_status "Systemd service created: $SERVICE_FILE"

# Reload systemd
print_status "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your .env file (if not done already):"
echo "   nano .env"
echo ""
echo "2. Upload your session file (if not done already):"
echo "   scp $SESSION_FILE user@server:$WORKING_DIR/"
echo ""
echo "3. Test the bot manually:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "4. Once working, enable and start the service:"
echo "   sudo systemctl enable yaronotifs"
echo "   sudo systemctl start yaronotifs"
echo ""
echo "5. Check service status:"
echo "   sudo systemctl status yaronotifs"
echo ""
echo "6. View logs:"
echo "   tail -f logs/bot.log"
echo "   sudo journalctl -u yaronotifs -f"
echo ""
echo "7. Manage the service:"
echo "   sudo systemctl stop yaronotifs      # Stop the bot"
echo "   sudo systemctl restart yaronotifs   # Restart the bot"
echo "   sudo systemctl disable yaronotifs   # Disable auto-start"
echo ""
