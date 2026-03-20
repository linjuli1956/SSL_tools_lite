#!/bin/bash

echo "========================================"
echo "    SSL Certificate Manager - Install"
echo "========================================"
echo ""
echo "Installing dependencies..."
echo ""

pip3 install flask cryptography paramiko

echo ""
echo "Installation complete!"
echo ""
echo "Run start.sh to start the service"
echo ""
