#!/bin/sh
set -eu
mkdir -p /app/.ssh
chmod 700 /app/.ssh
exec python /app/me5_exporter.py
