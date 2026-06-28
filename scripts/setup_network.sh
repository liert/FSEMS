#!/bin/bash
# FSEMS global bridge — aligned with /home/kali/openwrt/armv8/start.sh (br0 @ 192.168.1.10/24).
set -euo pipefail

BRIDGE_NAME="${FSEMS_BRIDGE:-br_fsems}"
BRIDGE_CIDR="${FSEMS_BRIDGE_CIDR:-192.168.1.10/24}"
BRIDGE_NET="${FSEMS_BRIDGE_NET:-192.168.1.0/24}"
PHY_NIC="${FSEMS_PHY_NIC:-eth0}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

if ! command -v brctl >/dev/null 2>&1; then
  echo "Install bridge-utils first." >&2
  exit 1
fi

if ! ip link show "$BRIDGE_NAME" >/dev/null 2>&1; then
  brctl addbr "$BRIDGE_NAME"
fi

ip link set dev "$BRIDGE_NAME" up
ip addr flush dev "$BRIDGE_NAME" 2>/dev/null || true
ip addr add "$BRIDGE_CIDR" dev "$BRIDGE_NAME"

# NAT (optional outbound); skip if no upstream NIC
if ip link show "$PHY_NIC" >/dev/null 2>&1; then
  sysctl -w net.ipv4.ip_forward=1
  iptables -t nat -C POSTROUTING -s "$BRIDGE_NET" -o "$PHY_NIC" -j MASQUERADE 2>/dev/null \
    || iptables -t nat -A POSTROUTING -s "$BRIDGE_NET" -o "$PHY_NIC" -j MASQUERADE
  iptables -C FORWARD -i "$BRIDGE_NAME" -o "$PHY_NIC" -j ACCEPT 2>/dev/null \
    || iptables -A FORWARD -i "$BRIDGE_NAME" -o "$PHY_NIC" -j ACCEPT
  iptables -C FORWARD -i "$PHY_NIC" -o "$BRIDGE_NAME" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
    || iptables -A FORWARD -i "$PHY_NIC" -o "$BRIDGE_NAME" -m state --state RELATED,ESTABLISHED -j ACCEPT
  echo "Bridge $BRIDGE_NAME up ($BRIDGE_CIDR), NAT via $PHY_NIC."
else
  echo "Bridge $BRIDGE_NAME up ($BRIDGE_CIDR). No NAT (NIC '$PHY_NIC' not found)."
fi
