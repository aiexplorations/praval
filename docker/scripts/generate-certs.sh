#!/bin/bash

# Generate TLS certificates for secure Praval spore communication
# This script creates a CA and server/client certificates for testing

set -e

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../certs" && pwd)"
DAYS=365

echo "Creating certificate directory: $CERT_DIR"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Generate CA private key
echo "Generating CA private key..."
openssl genrsa -out ca_key.pem 4096

# Generate CA certificate
echo "Generating CA certificate..."
openssl req -new -x509 -key ca_key.pem -out ca_certificate.pem -days $DAYS \
    -subj "/C=US/ST=CA/L=San Francisco/O=Praval/OU=Development/CN=Praval CA"

# Generate server private key
echo "Generating server private key..."
openssl genrsa -out server_key.pem 4096

# Generate server certificate request
echo "Generating server certificate request..."
openssl req -new -key server_key.pem -out server_cert.csr \
    -subj "/C=US/ST=CA/L=San Francisco/O=Praval/OU=Development/CN=praval-rabbitmq"

# Create server certificate extensions file
cat > server_cert_extensions.txt << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = praval-rabbitmq
DNS.2 = praval-mosquitto
DNS.3 = praval-activemq
DNS.4 = localhost
IP.1 = 127.0.0.1
IP.2 = 172.20.0.0/16
EOF

# Generate server certificate signed by CA
echo "Generating server certificate..."
openssl x509 -req -in server_cert.csr -CA ca_certificate.pem -CAkey ca_key.pem \
    -CAcreateserial -out server_certificate.pem -days $DAYS \
    -extensions v3_req -extfile server_cert_extensions.txt

# Generate client private key
echo "Generating client private key..."
openssl genrsa -out client_key.pem 4096

# Generate client certificate request
echo "Generating client certificate request..."
openssl req -new -key client_key.pem -out client_cert.csr \
    -subj "/C=US/ST=CA/L=San Francisco/O=Praval/OU=Development/CN=praval-client"

# Create client certificate extensions file
cat > client_cert_extensions.txt << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = clientAuth
EOF

# Generate client certificate signed by CA
echo "Generating client certificate..."
openssl x509 -req -in client_cert.csr -CA ca_certificate.pem -CAkey ca_key.pem \
    -CAcreateserial -out client_certificate.pem -days $DAYS \
    -extensions v3_req -extfile client_cert_extensions.txt

# Clean up CSR and extension files
rm -f server_cert.csr client_cert.csr server_cert_extensions.txt client_cert_extensions.txt

# Set permissions
chmod 600 *_key.pem
chmod 644 *.pem

# Verify certificates
echo "Verifying certificates..."
openssl verify -CAfile ca_certificate.pem server_certificate.pem
openssl verify -CAfile ca_certificate.pem client_certificate.pem

echo "Certificate generation complete!"
echo
echo "Generated files:"
echo "  CA Certificate: ca_certificate.pem"
echo "  Server Certificate: server_certificate.pem"
echo "  Server Private Key: server_key.pem"
echo "  Client Certificate: client_certificate.pem"
echo "  Client Private Key: client_key.pem"
echo
echo "These certificates are for development and testing only!"
echo "Use proper CA-signed certificates in production."