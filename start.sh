#!/bin/bash

# Installer les dépendances
pip install -r backend/requirements.txt

# Lancer le serveur FastAPI
uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}