from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime
import os
import requests 
import time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API Sonnette Intelligente")

# On connecte le dossier "templates"
templates = Jinja2Templates(directory="templates")

os.makedirs("database", exist_ok=True)
DB_PATH = "database/sonnette.db"

# --- MÉMOIRE GLOBALE ENRICHIE ---
etat_systeme = {
    "dernier_contact": time.time(),
    "dernier_envoi_discord": 0,
    "alarme_code": "0", 
    "config": {
        "notif_bouton": True,
        "notif_infrarouge": True,
        "notif_son": False,
        "heures_silencieuses_debut": "22:00",
        "heures_silencieuses_fin": "07:00",
        "silence_actif": False,
        "mode_vacances": False,
        "delai_anti_spam": 30,
        "webhook_discord": os.getenv("URL_DISCORD", ""),
        
        # --- NOUVEAUX PARAMÈTRES COOL ---
        "sonnerie_bouton": "2",      # 2 = Carillon par défaut
        "sonnerie_infrarouge": "1",  # 1 = Police par défaut
        "sonnerie_son": "0",         # 0 = Silencieux
        "msg_bouton": "Quelqu'un a sonné à la porte !",
        "msg_infrarouge": "Mouvement suspect détecté !",
        "msg_son": "Bruit anormal entendu !"
    }
}

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

def est_heure_silencieuse():
    # Le Mode Vacances annule le mode silencieux !
    if etat_systeme["config"]["mode_vacances"]: return False
    if not etat_systeme["config"]["silence_actif"]: return False
    
    try:
        maintenant = datetime.now().time()
        debut = datetime.strptime(etat_systeme["config"]["heures_silencieuses_debut"], "%H:%M").time()
        fin = datetime.strptime(etat_systeme["config"]["heures_silencieuses_fin"], "%H:%M").time()
        
        if debut <= fin: return debut <= maintenant <= fin
        else: return maintenant >= debut or maintenant <= fin
    except:
        return False

# ==========================================
# ROUTES DES PAGES WEB (JINJA2)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/historique", response_class=HTMLResponse)
async def page_historique(request: Request):
    return templates.TemplateResponse(request=request, name="historique.html")

@app.get("/parametres", response_class=HTMLResponse)
async def page_parametres(request: Request):
    return templates.TemplateResponse(request=request, name="parametres.html")

# ==========================================
# ROUTES DE L'API (DONNÉES)
# ==========================================

@app.post("/api/sauvegarder_config")
def sauvegarder_config(config: dict):
    etat_systeme["config"].update(config)
    return {"statut": "Sauvegardé"}

@app.post("/api/activer_alarme/{code}")
def activer_alarme(code: str):
    etat_systeme["alarme_code"] = code
    return {"statut": "Alarme armée"}

@app.get("/api/check_alarme", response_class=PlainTextResponse)
def check_alarme(x_api_key: str = Header(None)):
    # VÉRIFICATION DE SÉCURITÉ
    if x_api_key != os.getenv("API_KEY", ""):
        raise HTTPException(status_code=401, detail="Non autorisé. Mauvaise clé API.")
    
    etat_systeme["dernier_contact"] = time.time()
    code_manuel = etat_systeme["alarme_code"]
    
    # On remet à zéro l'alarme manuelle après l'avoir lue
    if code_manuel != "0":
        etat_systeme["alarme_code"] = "0"
        
    c = etat_systeme["config"]
    
    # Si c'est l'heure silencieuse, on force tous les capteurs à "0" (silencieux)
    if est_heure_silencieuse():
        return f"{code_manuel}000"
        
    # Sinon, on envoie la configuration actuelle : ex "0210"
    return f"{code_manuel}{c.get('sonnerie_bouton', '2')}{c.get('sonnerie_infrarouge', '1')}{c.get('sonnerie_son', '0')}"

@app.get("/api/etat")
def lire_etat():
    return {
        "en_ligne": (time.time() - etat_systeme["dernier_contact"]) < 12,
        "config": etat_systeme["config"],
        "en_silence": est_heure_silencieuse()
    }

@app.get("/api/historique_data")
def lire_historique_data(limite: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Si la limite est supérieure à 0, on limite. Sinon (limite = 0), on prend TOUT.
    if limite > 0:
        cursor.execute("SELECT source, timestamp FROM evenements ORDER BY id DESC LIMIT ?", (limite,))
    else:
        cursor.execute("SELECT source, timestamp FROM evenements ORDER BY id DESC")
        
    lignes = cursor.fetchall()
    conn.close()
    return [{"source": l[0], "heure": l[1]} for l in lignes]

@app.get("/api/stats")
def lire_statistiques():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT source, COUNT(*) FROM evenements GROUP BY source")
    lignes = cursor.fetchall()
    conn.close()
    return {l[0]: l[1] for l in lignes}

@app.post("/alerte")
def recevoir_alerte(source: str, x_api_key: str = Header(None)):
    # VÉRIFICATION DE SÉCURITÉ
    if x_api_key != os.getenv("API_KEY", ""):
        raise HTTPException(status_code=401, detail="Non autorisé. Mauvaise clé API.")
    
    temps_actuel = time.time()
    etat_systeme["dernier_contact"] = temps_actuel
    maintenant = datetime.now()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO evenements (source, timestamp) VALUES (?, ?)", (source, maintenant))
    conn.commit()
    conn.close()

    en_silence = est_heure_silencieuse()

    # --- 2. LOGIQUE DISCORD ---
    delai_ecoule = temps_actuel - etat_systeme["dernier_envoi_discord"]
    anti_spam_ok = delai_ecoule >= etat_systeme["config"]["delai_anti_spam"]
    
    autorise_capteur = False
    if source == "bouton" and etat_systeme["config"]["notif_bouton"]: autorise_capteur = True
    elif source == "infrarouge" and etat_systeme["config"]["notif_infrarouge"]: autorise_capteur = True
    elif source == "son" and etat_systeme["config"]["notif_son"]: autorise_capteur = True

    webhook = etat_systeme["config"]["webhook_discord"]

    if not en_silence and autorise_capteur and anti_spam_ok and webhook:
        heure_formatee = maintenant.strftime('%H:%M:%S')
        # On utilise le message personnalisé !
        msg_custom = etat_systeme["config"].get(f"msg_{source}", f"Détection {source}")
        
        message = {"content": f"🔔 **Alerte IoT** : {msg_custom} *(à {heure_formatee})*"}
        try:
            requests.post(webhook, json=message)
            etat_systeme["dernier_envoi_discord"] = temps_actuel
        except:
            pass

    return {"statut": "succès"}

@app.get("/api/kpi")
def lire_kpi():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Nombre de détections aujourd'hui
    aujourd_hui = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM evenements WHERE timestamp LIKE ?", (f"{aujourd_hui}%",))
    total_jour = cursor.fetchone()[0]
    
    # 2. Le dernier événement enregistré
    cursor.execute("SELECT source, timestamp FROM evenements ORDER BY id DESC LIMIT 1")
    dernier = cursor.fetchone()
    
    # 3. Le capteur le plus sollicité au total
    cursor.execute("SELECT source FROM evenements GROUP BY source ORDER BY COUNT(*) DESC LIMIT 1")
    top_capteur = cursor.fetchone()
    
    conn.close()
    
    return {
        "total_jour": total_jour,
        "dernier_event": dernier[1] if dernier else "Aucun",
        "derniere_source": dernier[0] if dernier else "-",
        "top_capteur": top_capteur[0] if top_capteur else "Aucun"
    }