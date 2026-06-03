#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="${ROOT}/apache/ssl"
mkdir -p "$SSL_DIR"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "${SSL_DIR}/tls.key" \
  -out "${SSL_DIR}/tls.crt" \
  -subj "/CN=operating-systems.com/O=OS2-HW2/C=SY"
echo "Certificates written to ${SSL_DIR}"
