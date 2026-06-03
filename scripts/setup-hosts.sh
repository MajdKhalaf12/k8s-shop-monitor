#!/usr/bin/env bash
# Adds operating-systems.com to /etc/hosts (requires sudo).
set -euo pipefail
LINE="127.0.0.1 operating-systems.com www.operating-systems.com"
if grep -q "operating-systems.com" /etc/hosts 2>/dev/null; then
  echo "Already in /etc/hosts:"
  grep operating-systems.com /etc/hosts
  exit 0
fi
echo "Adding: $LINE"
echo "$LINE" | sudo tee -a /etc/hosts
echo "Done. Open: https://operating-systems.com/balancer-manager"
