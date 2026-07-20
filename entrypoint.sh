#!/bin/sh
set -eu
mkdir -p /app/.ssh
exec python /app/me5_exporter.py
