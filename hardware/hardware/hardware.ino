#include <SPI.h>
#include <WiFiNINA.h>

// ================= CONFIGURATION =================
const char* ssid = "BELL782";          // Ton réseau Wi-Fi
const char* password = "logetudes";    // Ton mot de passe Wi-Fi

// Adresse IP de ton PC Fedora et port du serveur
const char* serverAddress = "192.168.2.91"; 
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
    jouerSonnette();
    envoyerAlerte("bouton");
    dernierEnvoiBouton = maintenant;
  }

  // 2. Lecture de l'Infrarouge (Digital)
  /*if (digitalRead(PIN_IR) == HIGH && (maintenant - dernierEnvoiIR > DELAI_COOLDOWN)) {
    Serial.println("🏃 Mouvement détecté !");
    jouerSonnette();
    envoyerAlerte("infrarouge");
    dernierEnvoiIR = maintenant;
  }*/

  // 3. Lecture du Capteur de Son (Analogique)
  int niveauSonore = analogRead(PIN_SON);
  if (niveauSonore > SEUIL_BRUIT && (maintenant - dernierEnvoiSon > DELAI_COOLDOWN)) {
    Serial.print("🔊 Bruit fort détecté ! Niveau : ");
    Serial.println(niveauSonore);
    jouerSonnette();
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

// Fonction d'envoi HTTP
void envoyerAlerte(String source) {
  if (client.connect(serverAddress, serverPort)) {
    client.print("POST /alerte?source=");
    client.print(source);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    client.println("Connection: close");
    client.println(); 
    client.stop(); 
    Serial.println("   -> 🌐 Alerte envoyée au serveur Fedora.");
  } else {
    Serial.println("   -> ❌ Échec de la connexion au serveur.");
  }
}

// Fonction qui interroge le serveur pour savoir s'il faut sonner
void verifierAlarme() {
  if (client.connect(serverAddress, serverPort)) {
    client.println("GET /api/check_alarme HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    client.println("Connection: close");
    client.println();

    // On attend un peu que le serveur réponde
    delay(100); 
    
    String reponse = "";
    while (client.available()) {
      char c = client.read();
      reponse += c;
    }
    client.stop();

    // Si la réponse contient un "1" à la toute fin du message HTTP
    if (reponse.endsWith("1")) {
      Serial.println("🚨 ORDRE REÇU : DÉCLENCHEMENT DE L'ALARME !");
      jouerSirene();
    }
  }
}

// Fonction pour faire un son d'alarme agressif
void jouerSirene() {
  for (int i = 0; i < 3; i++) {
    tone(PIN_SPEAKER, 1200, 300);
    delay(300);
    tone(PIN_SPEAKER, 800, 300);
    delay(300);
  }
}