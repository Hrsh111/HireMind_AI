#!/usr/bin/env bash
set -euo pipefail
# Run from the directory this script lives in, so it works from anywhere.
cd "$(dirname "$0")"
exec ./node_modules/.bin/next dev -p 3001
