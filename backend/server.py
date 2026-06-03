from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv
import requests 
import time # !!! NOUVEAU !!! Pour gérer le battement de coeur

app = FastAPI(title="API Sonnette Intelligente")

os.makedirs("database", exist_ok=True)
DB_PATH = "database/sonnette.db"
load_dotenv()
WEBHOOK_URL = os.getenv("URL_DISCORD")

etat_systeme = {
    "notifications_actives": True,
    "declencher_alarme": False,
    "dernier_contact": time.time() # !!! NOUVEAU !!! L'heure de la dernière communication
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

@app.post("/api/toggle_silence")
def basculer_silence():
    etat_systeme["notifications_actives"] = not etat_systeme["notifications_actives"]
    return {"notifications_actives": etat_systeme["notifications_actives"]}

@app.post("/api/activer_alarme")
def activer_alarme():
    etat_systeme["declencher_alarme"] = True
    return {"statut": "Alarme armée"}

@app.get("/api/check_alarme", response_class=PlainTextResponse)
def check_alarme():
    # !!! NOUVEAU !!! À chaque fois que l'Arduino vérifie l'alarme, on met à jour son heure de vie
    etat_systeme["dernier_contact"] = time.time()
    
    if etat_systeme["declencher_alarme"]:
        etat_systeme["declencher_alarme"] = False 
        return "1"
    return "0"

@app.get("/api/etat")
def lire_etat():
    # !!! NOUVEAU !!! Si l'Arduino n'a pas donné de nouvelles depuis plus de 12 secondes, il est hors ligne
    temps_ecoule = time.time() - etat_systeme["dernier_contact"]
    en_ligne = temps_ecoule < 12 
    
    return {
        "notifications_actives": etat_systeme["notifications_actives"],
        "en_ligne": en_ligne
    }

@app.get("/api/historique")
def lire_historique():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT source, timestamp FROM evenements ORDER BY id DESC LIMIT 20")
    lignes = cursor.fetchall()
    conn.close()
    return [{"source": ligne[0], "heure": ligne[1]} for ligne in lignes]

@app.get("/api/stats")
def lire_statistiques():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT source, COUNT(*) FROM evenements GROUP BY source")
    lignes = cursor.fetchall()
    conn.close()
    return {ligne[0]: ligne[1] for ligne in lignes}

@app.get("/", response_class=HTMLResponse)
def accueil():
    page_html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tableau de Bord - Sonnette</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; color: #333; margin: 0; padding: 20px; }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 5px; }
            
            /* !!! NOUVEAU !!! Style pour le statut en ligne/hors ligne */
            .status-box { text-align: center; margin-bottom: 20px; font-weight: bold; font-size: 18px; transition: 0.3s; }
            .online { color: #27ae60; }
            .offline { color: #c0392b; animation: clignoter 1.5s infinite; }
            
            @keyframes clignoter { 50% { opacity: 0.5; } }
            
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .panneau-controle { text-align: center; margin-bottom: 20px; padding: 15px; background: #ecf0f1; border-radius: 8px;}
            button { padding: 10px 20px; font-size: 16px; font-weight: bold; border: none; border-radius: 5px; cursor: pointer; transition: 0.3s; margin: 5px; }
            .btn-on { background-color: #2ecc71; color: white; }
            .btn-off { background-color: #e74c3c; color: white; }
            .btn-alarme { background-color: #c0392b; color: white; border: 2px solid #900; }
            .btn-alarme:hover { background-color: #e74c3c; }
            
            .contenu-principal { display: flex; gap: 20px; flex-wrap: wrap; }
            .section-graphique { flex: 1; min-width: 300px; text-align: center; }
            .section-historique { flex: 2; min-width: 300px; }
            
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #3498db; color: white; }
            .source-bouton { color: #e74c3c; font-weight: bold; }
            .source-infrarouge { color: #f39c12; font-weight: bold; }
            .source-son { color: #9b59b6; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔔 Ma Sonnette Intelligente</h1>
            <div id="status-indicateur" class="status-box offline">⏳ Recherche de l'Arduino...</div>
            
            <div class="panneau-controle">
                <h3>⚙️ Contrôle du système</h3>
                <button id="btn-notif" class="btn-on" onclick="basculerNotif()">🔊 Notifications</button>
                <button class="btn-alarme" onclick="declencherAlarme()">🚨 DÉCLENCHER L'ALARME</button>
            </div>

            <div class="contenu-principal">
                <div class="section-graphique">
                    <h3>📊 Statistiques</h3>
                    <canvas id="monGraphique"></canvas>
                </div>
                
                <div class="section-historique">
                    <h3 style="text-align: center;">Dernières détections</h3>
                    <table id="table-historique">
                        <thead>
                            <tr>
                                <th>Déclencheur</th>
                                <th>Date et Heure</th>
                            </tr>
                        </thead>
                        <tbody id="donnees">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
            let graphiqueStats = null;

            async function basculerNotif() {
                const reponse = await fetch('/api/toggle_silence', { method: 'POST' });
                const data = await reponse.json();
                mettreAJourBouton(data.notifications_actives);
            }

            async function declencherAlarme() {
                await fetch('/api/activer_alarme', { method: 'POST' });
                alert("Ordre envoyé ! L'Arduino va sonner.");
            }

            function mettreAJourBouton(actives) {
                const btn = document.getElementById('btn-notif');
                if (actives) {
                    btn.className = 'btn-on'; btn.innerHTML = '🔊 Notifications';
                } else {
                    btn.className = 'btn-off'; btn.innerHTML = '🔕 Mode Silencieux';
                }
            }

            // !!! NOUVEAU !!! Cette fonction met à jour le texte En ligne/Hors ligne
            async function chargerEtat() {
                try {
                    const reponse = await fetch('/api/etat');
                    const data = await reponse.json();
                    
                    mettreAJourBouton(data.notifications_actives);
                    
                    const indicateur = document.getElementById('status-indicateur');
                    if (data.en_ligne) {
                        indicateur.className = 'status-box online';
                        indicateur.innerHTML = '🟢 Appareil connecté et actif';
                    } else {
                        indicateur.className = 'status-box offline';
                        indicateur.innerHTML = '🔴 Appareil hors ligne (Connexion perdue)';
                    }
                } catch (e) {
                    // Si le serveur Python plante, ça affichera hors ligne aussi
                    document.getElementById('status-indicateur').className = 'status-box offline';
                    document.getElementById('status-indicateur').innerHTML = '🔴 Serveur injoignable';
                }
            }

            async function chargerHistorique() {
                const reponse = await fetch('/api/historique');
                const donnees = await reponse.json();
                
                let html = '';
                donnees.forEach(event => {
                    let sourceClasse = 'source-' + event.source;
                    let emoji = event.source === 'bouton' ? '🔘' : (event.source === 'infrarouge' ? '🏃' : '🔊');
                    html += `<tr>
                                <td class="${sourceClasse}">${emoji} ${event.source.toUpperCase()}</td>
                                <td>${event.heure.substring(0, 19)}</td>
                             </tr>`;
                });
                document.getElementById('donnees').innerHTML = html;
            }

            async function chargerStatistiques() {
                const reponse = await fetch('/api/stats');
                const stats = await reponse.json();
                const labels = Object.keys(stats);
                const valeurs = Object.values(stats);
                const couleurs = labels.map(label => {
                    if(label === 'bouton') return '#e74c3c';
                    if(label === 'infrarouge') return '#f39c12';
                    if(label === 'son') return '#9b59b6';
                    return '#bdc3c7';
                });
                const ctx = document.getElementById('monGraphique').getContext('2d');
                
                if (graphiqueStats != null) {
                    graphiqueStats.data.labels = labels;
                    graphiqueStats.data.datasets[0].data = valeurs;
                    graphiqueStats.data.datasets[0].backgroundColor = couleurs;
                    graphiqueStats.update();
                } else {
                    graphiqueStats = new Chart(ctx, {
                        type: 'pie',
                        data: { labels: labels, datasets: [{ data: valeurs, backgroundColor: couleurs, borderWidth: 1 }] },
                        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
                    });
                }
            }

            function rafraichirTout() {
                chargerEtat();
                chargerHistorique();
                chargerStatistiques();
            }

            rafraichirTout();
            setInterval(rafraichirTout, 3000); // Recharge tout (y compris le statut) toutes les 3s
        </script>
    </body>
    </html>
    """
    return page_html

@app.post("/alerte")
def recevoir_alerte(source: str):
    # !!! NOUVEAU !!! Quand on reçoit une alerte, ça prouve aussi que l'Arduino est en vie !
    etat_systeme["dernier_contact"] = time.time()
    
    maintenant = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO evenements (source, timestamp) VALUES (?, ?)", (source, maintenant))
    conn.commit()
    conn.close()

    heure_formatee = maintenant.strftime('%H:%M:%S')
    
    if etat_systeme["notifications_actives"]:
        message_discord = {"content": f"🔔 **Alerte Sonnette** : Détection via '{source}' à {heure_formatee} !"}
        try:
            requests.post(WEBHOOK_URL, json=message_discord)
        except:
            pass

    return {"statut": "succès", "source": source, "heure": heure_formatee}