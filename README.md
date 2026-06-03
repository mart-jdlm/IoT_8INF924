# 🔔 8INF924 — Internet des Objets (IoT) | UQAC
## Projet de Session : Sujet 2 — Sonnette (pas si) intelligente

Ce dépôt contient l'ensemble des livrables (code source, schémas, et documentation) pour la réalisation de notre prototype de sonnette connectée dans le cadre du cours **8INF924 — Internet des Objets** à l'Université du Québec à Chicoutimi (UQAC).

---

## 📌 Liens Utiles et Ressources

* **📂 Dossier Google Drive :** [Lien vers notre Google Drive](https://drive.google.com/drive/folders/1QAB8TGwj6tMms-aaFJpvWMOTLZgNMYCz?usp=sharing)
* **📐 Projet EasyEDA :** [Lien vers notre projet EasyEDA](https://u.easyeda.com/join?type=project&key=fac310169bb212075f3a17a619c96056&inviter=c13f891e938d48d1b52ad1fcd24347ec)
* **🎓 Moodle du cours :** [Accès au cours 8INF924](https://moodle.uqac.ca/course/view.php?id=19530)
* **📧 Enseignant :** Florentin Thullier (fthullie@uqac.ca) — Bureau : P3-5040

---

## 👥 Membres de l'Équipe
* **Martin** — Firmware & Intégration
* **Julian** — Hardware, Schématique & PCB
* **Nolan** — Backend, Base de données & Notifications

---

## 🎯 Objectif du Projet

L'objectif est de concevoir et réaliser une sonnette connectée autonome capable de :
1. **Détecter une présence** et des bruits anormaux devant la porte.
2. **Interagir avec le visiteur** localement via un haut-parleur avec des sonneries personnalisées (Carillon, Alarmes).
3. **Informer l'utilisateur à distance** en temps réel via un système de notifications Discord et un tableau de bord web.

---

## 🛠️ Architecture et Matériel

### 1. Contrôleur Central et Capteurs
* **Arduino MKR1010** : Microcontrôleur avec connectivité Wi-Fi native pour l'IoT.
* **Bouton Poussoir (DFR0029)** ➔ Broche Digitale `D2`
* **Capteur Infrarouge (SEN0018)** ➔ Broche Digitale `D3`
* **Capteur de Son (DFR0034)** ➔ Broche Analogique `A1` (Seuil ajustable)
* **Haut-parleur (FIT0449)** ➔ Broche Digitale `D4` (Sortie PWM pour jouer les mélodies)

### 2. Architecture Logicielle
* **Firmware (C++)** : Programme Arduino gérant les capteurs, les alertes sonores et la communication HTTP vers l'API. Intègre une logique "Edge Computing" pour éviter le spam réseau.
* **Backend (Python / FastAPI)** : Serveur léger gérant les requêtes de la sonnette et distribuant l'interface web (rendue via **Jinja2**).
* **Base de données (SQLite)** : Persistance des données et de l'historique des événements.
* **Déploiement (Docker)** : Conteneurisation de l'API via `Dockerfile` et `docker-compose.yml`.

---

## 🏗️ Structure du Dépôt

L'arborescence complète du projet est structurée comme suit :

```text
IOT_8INF924/
├── backend/        
│   ├── database/            
│   │   └── sonnette.db
│   ├── templates/         
│   │   ├── dashboard.html
│   │   ├── historique.html
│   │   ├── layout.html
│   │   └── parametres.html
│   ├── .dockerignore
│   ├── docker-compose.yml   
│   ├── Dockerfile         
│   ├── requirements.txt 
│   └── server.py    
├── hardware/            
│   └── hardware.ino     
├── images/           
├── .gitignore            
├── README.md   
```
---

## ✨ Fonctionnalités Avancées Implémentées

* **Dashboard Web & Historique** : Consultation des déclenchements et des statistiques (KPIs) en temps réel via l'interface web.
* **Notifications Discord** : Envoi d'alertes personnalisées avec un système anti-spam paramétrable.
* **Heures Silencieuses & Mode Vacances** : Désactivation intelligente des notifications sonores la nuit, avec possibilité de forcer la surveillance (Mode Vacances).
* **Gestion des Sonneries Dynamique** : Affectation de différentes alarmes sonores (Carillon Doux, Alarme Police, Alarme Incendie) selon le type de détection (Bouton, Mouvement, Son).

---

## 🚀 Installation et Démarrage

### 1. Déploiement du Backend (Serveur & Interface Web)
1. Placez-vous dans le dossier `backend/`.
2. Dupliquez le fichier `.env.example` et renommez-le en `.env`.
3. Éditez le fichier `.env` avec vos identifiants, votre clé API secrète et votre Webhook Discord.
4. Lancez l'environnement de production avec Docker Compose : `docker-compose up -d --build`.
5. Accédez à l'interface de gestion via votre navigateur à l'adresse : `http://localhost:8000`.

### 2. Configuration du Firmware (Arduino)

1. Placez-vous dans le dossier `hardware/`.
2. Dupliquez le fichier `arduino_secrets.example.h` et renommez-le en `arduino_secrets.h`.

3. Ouvrez `arduino_secrets.h` et renseignez votre réseau Wi-Fi, l'IP de votre serveur local et la clé API (qui doit être identique à celle du backend).

4. Ouvrez `hardware.ino` dans l'IDE Arduino.

5. Assurez-vous d'avoir installé la bibliothèque WiFiNINA.

6. Compilez et téléversez le code sur votre microcontrôleur Arduino MKR1010.

---

## 📐 Conception Matérielle (PCB)

Pour la conception physique du prototype, nous avons utilisé le logiciel **EasyEDA** afin de réaliser le schéma logique et le circuit imprimé. Tous les modules et capteurs sont alimentés en **3.3V** pour respecter la tension logique maximale de l'Arduino MKR1010].

### Attribution des Broches (Pinout)
Le câblage a été pensé pour être robuste et utilise la configuration suivante:
* **Bouton Poussoir (DFR0029)** ➔ Broche Digitale **D2** 
* **Capteur Infrarouge (SEN0018)** ➔ Broche Digitale **D3** 
* **Haut-parleur (FIT0449)** ➔ Broche Digitale **D4** (Sortie PWM) 
* **Capteur de Son (DFR0034)** ➔ Broche Analogique **A1** 

### Aperçus des Schémas
* **Schéma Électronique :**
  ![Schéma Électronique](./images/Schematic.webp)

* **Circuit Imprimé (Routage PCB double face) :**
  ![Circuit Imprimé (Vue 2D)](./images/PCB.webp).