#!/bin/bash
set -eu

dnf update -y
dnf install -y docker awscli2
systemctl enable --now docker
mkdir -p /opt/agriculture-rag
docker volume create agriculture-rag-memory
touch /opt/agriculture-rag/.env
chmod 600 /opt/agriculture-rag/.env
