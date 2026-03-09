#!/bin/bash
# Deployment script for Digital Ocean

set -e  # Exit on error

echo "Winter Weather Agent - Deployment Script"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Installation directory
INSTALL_DIR="/opt/winter-weather-agent"

echo "Installing to: $INSTALL_DIR"
echo ""

# Install system dependencies
echo "Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv sqlite3

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp -r ./* "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup configuration
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: You need to edit .env with your email settings!"
    echo "   Run: nano $INSTALL_DIR/.env"
    echo ""
else
    echo ".env file already exists, skipping..."
fi

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/winter-weather-agent.service << EOF
[Unit]
Description=Winter Weather Agent for Harrisburg International Airport
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/weather_agent.py
Restart=always
RestartSec=60
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your email settings:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Test the agent (single run):"
echo "   cd $INSTALL_DIR"
echo "   source venv/bin/activate"
echo "   python3 weather_agent.py --once"
echo ""
echo "3. Start the service:"
echo "   systemctl start winter-weather-agent"
echo ""
echo "4. Enable auto-start on boot:"
echo "   systemctl enable winter-weather-agent"
echo ""
echo "5. Check status:"
echo "   systemctl status winter-weather-agent"
echo ""
echo "6. View logs:"
echo "   journalctl -u winter-weather-agent -f"
echo ""
