#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color
YELLOW='\033[1;33m'
RED='\033[0;31m'

echo -e "${GREEN}===[ PC Fan Controller Setup ]===${NC}"

# 1. Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
fi
python3 --version

# 2. Try to create Virtual Environment
echo -e "\n${GREEN}Setting up virtual environment...${NC}"
USE_VENV=true
if python3 -m venv venv 2>/dev/null; then
    echo "Virtual environment created in ./venv"
else
    echo -e "${YELLOW}Warning: Could not create virtual environment (python3-venv might be missing).${NC}"
    echo -e "Falling back to system-wide/user packages with --break-system-packages..."
    USE_VENV=false
fi

# 3. Install requirements
echo -e "\n${GREEN}Installing dependencies...${NC}"
if [ "$USE_VENV" = true ]; then
    venv/bin/pip install --upgrade pip
    venv/bin/pip install -r requirements.txt
    PYTHON_EXEC="$(pwd)/venv/bin/python"
else
    python3 -m pip install --user --break-system-packages -r requirements.txt
    PYTHON_EXEC="/usr/bin/python3"
fi

# 4. Check Motherboard sensors (nct6775)
echo -e "\n${GREEN}Checking motherboard hardware monitoring driver...${NC}"
if lsmod | grep -q "nct6775"; then
    echo -e "${GREEN}nct6775 kernel module is loaded!${NC}"
else
    echo -e "${YELLOW}Warning: nct6775 kernel module (motherboard sensors) is NOT loaded.${NC}"
    echo -e "To control chassis fans, you will need to load it by running:"
    echo -e "  ${GREEN}sudo modprobe nct6775${NC}"
    echo -e "If this fails due to resource busy errors, edit ${YELLOW}/etc/default/grub${NC} and append"
    echo -e "  ${YELLOW}acpi_enforce_resources=lax${NC} to ${YELLOW}GRUB_CMDLINE_LINUX_DEFAULT${NC}"
    echo -e "Then run ${GREEN}sudo update-grub${NC} and reboot."
fi

# 5. Create a systemd service file template
echo -e "\n${GREEN}Generating systemd service template...${NC}"
cat << EOF > air-controller.service
[Unit]
Description=PC PWM Fan Controller Daemon
After=network.target lm-sensors.service

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$PYTHON_EXEC $(pwd)/src/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Systemd service file created: ${YELLOW}air-controller.service${NC}"
echo -e "To run the controller on boot, install the service:"
echo -e "  ${GREEN}sudo cp air-controller.service /etc/systemd/system/${NC}"
echo -e "  ${GREEN}sudo systemctl daemon-reload${NC}"
echo -e "  ${GREEN}sudo systemctl enable --now air-controller.service${NC}"

echo -e "\n${GREEN}Setup completed successfully!${NC}"
echo -e "To start the application manually, run:"
echo -e "  ${GREEN}sudo $PYTHON_EXEC src/main.py${NC}"
echo -e "(Running as root/sudo is necessary to control motherboard chassis fan sysfs files)"
