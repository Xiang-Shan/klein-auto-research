#!/usr/bin/env bash
exec uv run --locked python "$(dirname "$0")/verify_e2e.py" "$@"
