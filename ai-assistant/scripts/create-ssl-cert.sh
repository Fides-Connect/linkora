#!/usr/bin/env bash
#
# Script to create a self-signed SSL certificate for localhost
# The certificate and key are stored in the project's secrets folder by default
# You can override the certificate dir via CERT_DIR and SAN config via SAN_CONF environment variables
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# project root is assumed to be the parent of the script directory
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# default to <project_root>/secrets unless CERT_DIR is supplied
CERT_DIR="${CERT_DIR:-$PROJECT_ROOT/secrets}"
# SAN config: allow override by SAN_CONF; default to <project_root>/configs/ssl-cert-san.conf
SAN_CONF="${SAN_CONF:-$PROJECT_ROOT/configs/ssl-cert-san.conf}"

# Create CA key and cert
openssl req -x509 -nodes -days "${DAYS:-825}" -newkey rsa:2048 \
  -keyout "$CERT_DIR/ca-key.pem" -out "$CERT_DIR/ca-cert.pem" \
  -config "$SAN_CONF" -extensions v3_ca

# Create SSL key and CSR (Certificate Signing Request)
openssl req -nodes -days "${DAYS:-825}" -newkey rsa:2048 \
  -keyout "$CERT_DIR/ssl-key.pem" -out "$CERT_DIR/ssl-csr.pem" \
  -config "$SAN_CONF" -reqexts v3_req

# Sign the SSL certificate with the CA
openssl x509 -req -days "${DAYS:-825}" \
  -in "$CERT_DIR/ssl-csr.pem" -CA "$CERT_DIR/ca-cert.pem" -CAkey "$CERT_DIR/ca-key.pem" -CAcreateserial \
  -out "$CERT_DIR/ssl-cert.pem" \
  -extensions v3_req -extfile "$SAN_CONF"

#openssl req -x509 -nodes -days "${DAYS:-825}" -newkey rsa:2048 \
#  -keyout "$KEY" -out "$CRT" -config "$SAN_CONF" -extensions v3_req