from fastapi import FastAPI, Request, Header, HTTPException, Depends, Form, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from enum import Enum
import sqlite3
from datetime import datetime
import os
import requests 
import time
import secrets
from dotenv import load_dotenv

# Charge les variables du fichier .env
load_dotenv()

# ==========================================
# CONFIGURATION & SÉCURITÉ
# ==========================================

def verifier_admin(request: Request):
    """Vérifie la présence et la validité du cookie de session."""
    session = request.cookies.get("session_iot")
    if session != "admin_auth_valide":
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return True

class SourceCapteur(str, Enum):
    """Liste stricte des capteurs autorisés pour la validation des requêtes."""
    bouton = "bouton"
    infrarouge = "infrarouge"
    son = "son"

app = FastAPI(title="API Sonnette Intelligente")
templates = Jinja2Templates(directory="templates")

# Initialisation des dossiers et chemins
os.makedirs("database", exist_ok=True)
DB_PATH = "database/sonnette.db"

# ==========================================
# ÉTAT GLOBAL DU SYSTÈME (MÉMOIRE)
# ==========================================

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
        
        # --- MISE À JOUR DES PROFILS SONORES ---
        # 0 = Silencieux | 1 = Police | 2 = Carillon | 3 = Incendie 
        # 4 = Mario      | 5 = Zelda  | 6 = Sci-Fi Robotique
        "sonnerie_bouton": "4",      # 4 = Pièce Mario par défaut
        "sonnerie_infrarouge": "6",  # 6 = Robotique par défaut
        "sonnerie_son": "0",         # 0 = Silencieux par défaut
        
        "msg_bouton": "Quelqu'un a sonné à la porte !",
        "msg_infrarouge": "Mouvement suspect détecté !",
        "msg_son": "Bruit anormal entendu !"
    }
}

# ==========================================
# BASE DE DONNÉES & UTILITAIRES
# ==========================================

def init_db():
    """Crée la table des événements si elle n'existe pas."""
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
    """Détermine si le système doit désactiver les notifications sonores/alertes."""
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
# ROUTES : AUTHENTIFICATION
# ==========================================

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request, erreur: str = None):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"request": request, "erreur": erreur}
    )

@app.post("/login")
async def traiter_login(username: str = Form(...), password: str = Form(...)):
    """Valide les identifiants et génère le cookie de session."""
    correct_username = secrets.compare_digest(username, os.getenv("LOGIN", ""))
    correct_password = secrets.compare_digest(password, os.getenv("PASSWORD", ""))

    if correct_username and correct_password:
        reponse = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        reponse.set_cookie(
            key="session_iot", 
            value="admin_auth_valide", 
            httponly=True,
            max_age=86400 # Expire dans 24h
        )
        return reponse
    else:
        return RedirectResponse(url="/login?erreur=Identifiants incorrects", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
async def deconnexion():
    """Détruit le cookie de session et redirige vers le login."""
    reponse = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    reponse.delete_cookie("session_iot")
    return reponse

# ==========================================
# ROUTES : INTERFACE WEB (PROTÉGÉES)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request, user: str = Depends(verifier_admin)):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/historique", response_class=HTMLResponse)
async def page_historique(request: Request, user: str = Depends(verifier_admin)):
    return templates.TemplateResponse(request=request, name="historique.html")

@app.get("/parametres", response_class=HTMLResponse)
async def page_parametres(request: Request, user: str = Depends(verifier_admin)):
    return templates.TemplateResponse(request=request, name="parametres.html")

# ==========================================
# ROUTES : API & COMMUNICATION MATÉRIELLE
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
    """Permet à l'Arduino de récupérer l'état actuel et les consignes."""
    if x_api_key != os.getenv("SECRET_API_KEY", ""):
        raise HTTPException(status_code=401, detail="Non autorisé. Mauvaise clé API.")
    
    etat_systeme["dernier_contact"] = time.time()
    code_manuel = etat_systeme["alarme_code"]
    
    # Réinitialisation de l'alarme manuelle après lecture
    if code_manuel != "0":
        etat_systeme["alarme_code"] = "0"
        
    c = etat_systeme["config"]
    
    if est_heure_silencieuse():
        return f"{code_manuel}000"
        
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
def recevoir_alerte(source: SourceCapteur, x_api_key: str = Header(None)):
    """Gère une alerte envoyée par l'Arduino : log en BDD et notification Discord."""
    if x_api_key != os.getenv("SECRET_API_KEY", ""):
        raise HTTPException(status_code=401, detail="Non autorisé. Mauvaise clé API.")

    source_str = source.value 
    temps_actuel = time.time()
    maintenant = datetime.now()
    
    # Mise à jour de l'état et log en base de données
    etat_systeme["dernier_contact"] = temps_actuel
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO evenements (source, timestamp) VALUES (?, ?)", (source_str, maintenant))
    conn.commit()
    conn.close()

    # Logique d'envoi Discord (anti-spam et heures silencieuses)
    en_silence = est_heure_silencieuse()
    delai_ecoule = temps_actuel - etat_systeme["dernier_envoi_discord"]
    anti_spam_ok = delai_ecoule >= etat_systeme["config"]["delai_anti_spam"]
    
    autorise_capteur = False
    if source_str == "bouton" and etat_systeme["config"]["notif_bouton"]: autorise_capteur = True
    elif source_str == "infrarouge" and etat_systeme["config"]["notif_infrarouge"]: autorise_capteur = True
    elif source_str == "son" and etat_systeme["config"]["notif_son"]: autorise_capteur = True

    webhook = etat_systeme["config"]["webhook_discord"]

    if not en_silence and autorise_capteur and anti_spam_ok and webhook:
        heure_formatee = maintenant.strftime('%H:%M:%S')
        msg_custom = etat_systeme["config"].get(f"msg_{source_str}", f"Détection {source_str}")
        
        message = {"content": f"🔔 **Alerte IoT** : {msg_custom} *(à {heure_formatee})*"}
        try:
            requests.post(webhook, json=message)
            etat_systeme["dernier_envoi_discord"] = temps_actuel
        except:
            pass

    return {"statut": "succès"}

@app.get("/api/kpi")
def lire_kpi():
    """Génère les indicateurs clés (KPI) pour le tableau de bord."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Détections du jour
    aujourd_hui = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM evenements WHERE timestamp LIKE ?", (f"{aujourd_hui}%",))
    total_jour = cursor.fetchone()[0]
    
    # Dernier événement
    cursor.execute("SELECT source, timestamp FROM evenements ORDER BY id DESC LIMIT 1")
    dernier = cursor.fetchone()
    
    # Capteur le plus sollicité
    cursor.execute("SELECT source FROM evenements GROUP BY source ORDER BY COUNT(*) DESC LIMIT 1")
    top_capteur = cursor.fetchone()
    
    conn.close()
    
    return {
        "total_jour": total_jour,
        "dernier_event": dernier[1] if dernier else "Aucun",
        "derniere_source": dernier[0] if dernier else "-",
        "top_capteur": top_capteur[0] if top_capteur else "Aucun"
    }