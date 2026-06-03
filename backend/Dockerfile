# On part d'une version légère de Python
FROM python:3.11-slim

# On se place dans le dossier de travail du conteneur
WORKDIR /app

# Étape 1 : On copie juste les dépendances et on les installe
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Étape 2 : On copie tout le reste (server.py et le dossier templates/)
COPY . .

# On indique le port utilisé
EXPOSE 8000

# La commande pour démarrer le serveur
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]