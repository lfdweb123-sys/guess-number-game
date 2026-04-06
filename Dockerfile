# Utiliser une image Python légère
FROM python:3.11-slim

# Variables d'environnement pour éviter les warnings pip
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Créer le dossier de travail
WORKDIR /app

# Copier backend et installer dépendances
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le backend
COPY backend/ ./backend

# Exposer le port pour Railway
EXPOSE 8000

# Commande pour démarrer FastAPI
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]