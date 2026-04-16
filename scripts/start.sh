#!/usr/bin/env sh
set -eu

python /app/scripts/wait_for_dependencies.py
exec uvicorn app.main:create_app --factory --host "${APP__HOST:-0.0.0.0}" --port "${APP__PORT:-8000}"
