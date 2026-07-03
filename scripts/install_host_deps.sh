#!/bin/bash
# Install FSEMS host dependencies (Ubuntu 22.04+). No Docker. SQLite built into Python.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y \
  qemu-system-arm qemu-system-mips qemu-system-x86 qemu-utils \
  e2fsprogs \
  bridge-utils uml-utilities libguestfs-tools iptables \
  redis-server \
  python3 python3-venv python3-pip \
  nodejs npm

systemctl enable redis-server
systemctl start redis-server

echo "Host dependencies installed. Create /var/fsems/data and run setup_network.sh next."
