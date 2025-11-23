#!/usr/bin/env bash
set -e

if [ ! -f ".env" ]; then
  echo "Please copy .env.example -> .env and configure variables"
  exit 1
fi

python -m app.main
