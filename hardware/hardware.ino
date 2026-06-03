#include 
#include <SPI.h>
#include <WiFiNINA.h>

// ================= CONFIGURATION =================
const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;
const char* apiKey = SECRET_API_KEY;

// Adresse IP de ton PC Fedora et port du serveur
const char* serverAddress = SERVER_ADDRESS; 
const int serverPort = 8000;

// Broches du matériel (Mises à jour avec ton schéma)
const int PIN_BOUTON = 2;
const int PIN_IR = 3;
const int PIN_SPEAKER = 4;
const int PIN_SON = A1;

// Configuration du seuil de bruit (à ajuster selon la sensibilité de ton capteur DFR0034)
const int SEUIL_BRUIT = 200; // Valeur entre 0 et 1023

// Variables pour le "cooldown" (éviter de spammer le serveur)
unsigned long dernierEnvoiBouton = 0;
unsigned long dernierEnvoiIR = 0;
unsigned long dernierEnvoiSon = 0;
const unsigned long DELAI_COOLDOWN = 1000; // 5 secondes minimum entre deux alertes
unsigned long dernierCheckAlarme = 0;
const unsigned long DELAI_CHECK_ALARME = 4000; // Vérifie toutes les 4 secondes

// Mémoire locale pour le Edge Computing
int sonBouton = 2;
int sonIR = 1;
int sonSon = 0;

WiFiClient client;
int status = WL_IDLE_STATUS;

// ================= INITIALISATION =================
void setup() {
  Serial.begin(9600);
  
  // Configuration des broches
  pinMode(PIN_BOUTON, INPUT);  // DFR0029 est actif HAUT
  pinMode(PIN_IR, INPUT);
  pinMode(PIN_SPEAKER, OUTPUT);
  pinMode(PIN_SON, INPUT);

  // Petit bip de démarrage pour confirmer que le haut-parleur marche
  tone(PIN_SPEAKER, 1000, 200); // 1000 Hz pendant 200 ms

  // Connexion Wi-Fi
  while (status != WL_CONNECTED) {
    Serial.print("Connexion au Wi-Fi: ");
    Serial.println(ssid);
    status = WiFi.begin(ssid, password);
    delay(5000);
  }
  Serial.println("✅ Connecté au Wi-Fi !");
  
  // Double bip pour dire que le Wi-Fi est prêt
  tone(PIN_SPEAKER, 1500, 100);
  delay(150);
  tone(PIN_SPEAKER, 1500, 100);
}

// ================= BOUCLE PRINCIPALE =================
void loop() {
  unsigned long maintenant = millis();

  // 1. Lecture du Bouton (Digital)
  if (digitalRead(PIN_BOUTON) == HIGH && (maintenant - dernierEnvoiBouton > DELAI_COOLDOWN)) {
    Serial.println("🔘 Bouton pressé !");
    jouerSirene(sonBouton);
    envoyerAlerte("bouton");
    dernierEnvoiBouton = maintenant;
  }

  // 2. Lecture de l'Infrarouge (Digital)
  /*if (digitalRead(PIN_IR) == HIGH && (maintenant - dernierEnvoiIR > DELAI_COOLDOWN)) {
    Serial.println("🏃 Mouvement détecté !");
    jouerSirene(sonIR);
    envoyerAlerte("infrarouge");
    dernierEnvoiIR = maintenant;
  }*/

  // 3. Lecture du Capteur de Son (Analogique)
  int niveauSonore = analogRead(PIN_SON);
  if (niveauSonore > SEUIL_BRUIT && (maintenant - dernierEnvoiSon > DELAI_COOLDOWN)) {
    Serial.print("🔊 Bruit fort détecté ! Niveau : ");
    Serial.println(niveauSonore);
    jouerSirene(sonSon);
    envoyerAlerte("son");
    dernierEnvoiSon = maintenant;
  }

  // --- NOUVEAU : Vérification de l'alarme à distance ---
  if (maintenant - dernierCheckAlarme > DELAI_CHECK_ALARME) {
    verifierAlarme();
    dernierCheckAlarme = maintenant;
  } 
}

// ================= FONCTIONS SECONDAIRES =================

// Fonction pour faire sonner le haut-parleur (type "Ding-Dong")
void jouerSonnette() {
  tone(PIN_SPEAKER, 800, 300);  // "Ding"
  delay(350);
  tone(PIN_SPEAKER, 600, 400);  // "Dong"
}

// Fonction d'envoi HTTP modifiée pour la sécurité
void envoyerAlerte(String source) {
  if (client.connect(serverAddress, serverPort)) {
    client.print("POST /alerte?source=");
    client.print(source);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    
    // NOUVEAU : Envoi de la clé API dans les en-têtes
    client.print("X-API-Key: ");
    client.println(apiKey);
    
    client.println("Connection: close");
    client.println(); 
    client.stop(); 
    Serial.println("   -> 🌐 Alerte envoyée (Sécurisée).");
  } else {
    Serial.println("   -> ❌ Échec de la connexion.");
  }
}

// Fonction de vérification modifiée pour la sécurité
void verifierAlarme() {
  if (client.connect(serverAddress, serverPort)) {
    client.println("GET /api/check_alarme HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    
    // NOUVEAU : Envoi de la clé API
    client.print("X-API-Key: ");
    client.println(apiKey);
    
    client.println("Connection: close");
    client.println();
    delay(100); 
    
    String reponse = "";
    while (client.available()) {
      char c = client.read();
      reponse += c;
    }
    client.stop();

    reponse.trim(); // Nettoie le texte reçu
    int len = reponse.length();
    
    // Si on a bien reçu notre code à 4 chiffres (ex: "0210")
    if (len >= 4) {
      char manuel = reponse.charAt(len - 4);
      char sBouton = reponse.charAt(len - 3);
      char sIR = reponse.charAt(len - 2);
      char sSon = reponse.charAt(len - 1);

      // 1. Déclenchement manuel via les boutons du site
      if (manuel == '1') jouerSirene(1);
      else if (manuel == '2') jouerSirene(2);
      else if (manuel == '3') jouerSirene(3);

      // 2. Mise à jour de la mémoire pour le prochain appui
      sonBouton = String(sBouton).toInt();
      sonIR = String(sIR).toInt();
      sonSon = String(sSon).toInt();
    }
  }
}

// Nouvelle fonction avec un paramètre "type"
void jouerSirene(int type) {
  if (type == 1) {
    // Alarme de Police (Rapide Haut/Bas)
    for (int i = 0; i < 5; i++) {
      tone(PIN_SPEAKER, 1200, 200);
      delay(200);
      tone(PIN_SPEAKER, 800, 200);
      delay(200);
    }
  } 
  else if (type == 2) {
    // Carillon Doux (Ding - Dong)
    tone(PIN_SPEAKER, 1000, 400); // Ding (Aigu)
    delay(500);
    tone(PIN_SPEAKER, 700, 600);  // Dong (Grave)
    delay(800);
  } 
  else if (type == 3) {
    // Alarme Incendie (très stridente et rapide)
    for (int i = 0; i < 10; i++) {
      tone(PIN_SPEAKER, 2000, 100);
      delay(100);
      noTone(PIN_SPEAKER);
      delay(50);
    }
  }
}