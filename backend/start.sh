#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Criando venv..."
  python -m venv venv
fi

echo "Instalando dependencias..."
./venv/Scripts/python -m pip install --disable-pip-version-check -q -r requirements.txt

if [ ! -f .env ]; then
  echo ".env nao existe, copiando de .env.example..."
  cp .env.example .env
fi

echo "Subindo servidor em http://localhost:8000 (docs em /docs)"
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
