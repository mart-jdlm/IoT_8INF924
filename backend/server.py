from fastapi import FastAPI
import sqlite3
from datetime import datetime
import os

app = FastAPI(title="API Sonnette Intelligente")

os.makedirs("database", exist_ok=True)
DB_PATH = "database/sonnette.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def accueil():
    return {"message": "Le serveur de la sonnette intelligente est en ligne !"}

@app.post("/alerte")
def recevoir_alerte(source: str):
    maintenant = datetime.now()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO evenements (source, timestamp) VALUES (?, ?)", 
                   (source, maintenant))
    conn.commit()
    conn.close()

    heure_formatee = maintenant.strftime('%H:%M:%S')
    print(f"🔔 NOTIFICATION : Détection via '{source}' à {heure_formatee} !")

    return {"statut": "succès", "source": source, "heure": heure_formatee}