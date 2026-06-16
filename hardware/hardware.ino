#include "arduino_secrets.h"
#include <SPI.h>
#include <WiFiNINA.h>

// ==========================================
// CONFIGURATION & BROCHES
// ==========================================

const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;
const char* apiKey = SECRET_API_KEY;

// Serveur (Défini dans arduino_secrets.h ou en dur ici)
const char* serverAddress = SERVER_ADDRESS; 
const int serverPort = 8000;

// Mapping du matériel
const int PIN_BOUTON = 2;
const int PIN_ULTRASON = A2;
const int PIN_SPEAKER = 4;
const int PIN_SON = A1;

const int SEUIL_BRUIT = 50; // Sensibilité du capteur de son (0-1023)
const int SEUIL_DISTANCE = 80;

// ==========================================
// ÉTAT DU SYSTÈME (TIMERS & MÉMOIRE)
// ==========================================

unsigned long dernierEnvoiBouton = 0;
unsigned long dernierEnvoiIR = 0;
unsigned long dernierEnvoiSon = 0;
const unsigned long DELAI_COOLDOWN = 1000; 

unsigned long dernierCheckAlarme = 0;
const unsigned long DELAI_CHECK_ALARME = 1000; 

// Configuration des alertes sonores (0: Silencieux, 1: Police, 2: Carillon, 3: Incendie)
int sonBouton = 2;
int sonIR = 1;
int sonSon = 0;

WiFiClient client;
int status = WL_IDLE_STATUS;

// ==========================================
// INITIALISATION
// ==========================================

void setup() {
  Serial.begin(9600);
  
  pinMode(PIN_BOUTON, INPUT); 
  pinMode(PIN_ULTRASON, INPUT);
  pinMode(PIN_SPEAKER, OUTPUT);
  pinMode(PIN_SON, INPUT);

  // Bip de test matériel
  tone(PIN_SPEAKER, 1000, 200);

  // Connexion Wi-Fi
  while (status != WL_CONNECTED) {
    Serial.print("Connexion au Wi-Fi: ");
    Serial.println(ssid);
    status = WiFi.begin(ssid, password);
    delay(5000);
  }
  
  Serial.println("✅ Connecté au Wi-Fi !");
  tone(PIN_SPEAKER, 1500, 100);
  delay(150);
  tone(PIN_SPEAKER, 1500, 100);
}

// ==========================================
// BOUCLE PRINCIPALE
// ==========================================

void loop() {
  // --- DÉBUT DU BLOC DE TEST ---
  int distanceBrute = mesurerDistance();
  Serial.print("Test Capteur -> Valeur lue : ");
  Serial.println(distanceBrute);
  delay(500); // On ralentit pour avoir le temps de lire
  return;     // On empêche le reste du code de s'exécuter pour l'instant
  // --- FIN DU BLOC DE TEST ---
  
  unsigned long maintenant = millis();

  // 1. Capteur : Bouton physique
  if (digitalRead(PIN_BOUTON) == HIGH && (maintenant - dernierEnvoiBouton > DELAI_COOLDOWN)) {
    Serial.println("🔘 Bouton pressé !");
    envoyerAlerte("bouton"); // L'envoi réseau se fait AVANT de bloquer avec le son
    jouerSirene(sonBouton);
    dernierEnvoiBouton = maintenant;
  }

  // 2. Capteur : Mouvement Ultrason
  int distance = mesurerDistance();
  
  // Si un objet est détecté sous le seuil (et que la distance est valide)
  if (distance > 0 && distance < SEUIL_DISTANCE && (maintenant - dernierEnvoiIR > DELAI_COOLDOWN)) {
    Serial.print("🏃 Intrusion détectée ! Distance : ");
    Serial.print(distance);
    Serial.println(" cm");
    
    // Tu peux garder "infrarouge" pour ne pas casser ton serveur web actuel, 
    // ou le renommer en "ultrason" (mais il faudra modifier ton code Python/JS en conséquence)
    envoyerAlerte("infrarouge"); 
    jouerSirene(sonIR);
    
    dernierEnvoiIR = maintenant;
  }

  // 3. Capteur : Bruit ambiant
  int niveauSonore = analogRead(PIN_SON);
  if (niveauSonore > SEUIL_BRUIT && (maintenant - dernierEnvoiSon > DELAI_COOLDOWN)) {
    Serial.print("🔊 Bruit fort détecté ! Niveau : ");
    Serial.println(niveauSonore);
    envoyerAlerte("son");
    jouerSirene(sonSon);
    dernierEnvoiSon = maintenant;
  }

  // 4. Synchronisation : Mise à jour de l'état depuis le serveur
  if (maintenant - dernierCheckAlarme > DELAI_CHECK_ALARME) {
    verifierAlarme();
    dernierCheckAlarme = maintenant;
  } 
}

// ==========================================
// COMMUNICATION RÉSEAU
// ==========================================

/**
 * Envoie une notification d'alerte au backend FastAPI.
 */
void envoyerAlerte(String source) {
  if (client.connect(serverAddress, serverPort)) {
    client.print("POST /alerte?source=");
    client.print(source);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    client.print("X-API-Key: ");
    client.println(apiKey);
    client.println("Connection: close");
    client.println(); 
    client.stop(); 
    Serial.println("   -> 🌐 Alerte envoyée.");
  } else {
    Serial.println("   -> ❌ Échec de la connexion.");
  }
}

/**
 * Interroge le serveur pour récupérer la configuration (type de sonneries)
 * et exécuter les déclenchements d'alarme manuels.
 */
void verifierAlarme() {
  if (client.connect(serverAddress, serverPort)) {
    client.println("GET /api/check_alarme HTTP/1.1");
    client.print("Host: ");
    client.println(serverAddress);
    client.print("X-API-Key: ");
    client.println(apiKey);
    client.println("Connection: close");
    client.println();
    
    // On attend que le serveur réponde
    unsigned long timeout = millis();
    while (client.available() == 0) {
      if (millis() - timeout > 5000) {
        client.stop();
        return; // Timeout
      }
    }

    // 1. Ignorer les en-têtes HTTP (ils se terminent par une ligne vide "\r")
    while (client.connected()) {
      String ligne = client.readStringUntil('\n');
      if (ligne == "\r") {
        break; 
      }
    }

    // 2. Lire uniquement le corps de la réponse (tes 4 chiffres)
    String reponse = client.readString();
    reponse.trim(); 
    int len = reponse.length();
    
    // 3. Traitement
    if (len >= 4) {
      char manuel = reponse.charAt(len - 4);
      sonBouton = String(reponse.charAt(len - 3)).toInt();
      sonIR = String(reponse.charAt(len - 2)).toInt();
      sonSon = String(reponse.charAt(len - 1)).toInt();

      // Déclenchement forcé
      if (manuel == '1') jouerSirene(1);
      else if (manuel == '2') jouerSirene(2);
      else if (manuel == '3') jouerSirene(3);
      else if (manuel == '4') jouerSirene(4);
      else if (manuel == '5') jouerSirene(5);
      else if (manuel == '6') jouerSirene(6);
    }
    client.stop();
  }
}

// ==========================================
// ACTIONS MATÉRIELLES
// ==========================================

/**
 * Active le haut-parleur selon le profil sonore sélectionné.
 */
void jouerSirene(int type) {
  if (type == 1) { 
    // Profil 1 : Alarme de Police (Modulation rapide)
    for (int i = 0; i < 5; i++) {
      tone(PIN_SPEAKER, 1200, 200);
      delay(200);
      tone(PIN_SPEAKER, 800, 200);
      delay(200);
    }
  } 
  else if (type == 2) { 
    // Profil 2 : Carillon Classique (Ding-Dong)
    tone(PIN_SPEAKER, 1000, 400); 
    delay(500);
    tone(PIN_SPEAKER, 700, 600);  
    delay(800);
  } 
  else if (type == 3) { 
    // Profil 3 : Alarme Incendie (Stridente)
    for (int i = 0; i < 10; i++) {
      tone(PIN_SPEAKER, 2000, 100);
      delay(100);
      noTone(PIN_SPEAKER);
      delay(50);
    }
  }
  else if (type == 4) {
    // Profil 4 : Pièce Super Mario (Bref et positif)
    tone(PIN_SPEAKER, 988, 100);  // Note Si5
    delay(100);
    tone(PIN_SPEAKER, 1319, 400); // Note Mi6
    delay(400);
  }
  else if (type == 5) {
    // Profil 5 : Jingle Secret Zelda (Mystérieux)
    int notes[] = {784, 740, 622, 440, 415, 659, 831, 1047};
    for(int i = 0; i < 8; i++) {
      tone(PIN_SPEAKER, notes[i], 100);
      delay(120); // Léger espacement pour détacher les notes
    }
  }
  else if (type == 6) {
    // Profil 6 : Démarrage Robotique / Sci-Fi
    for (int freq = 200; freq <= 2000; freq += 100) {
      tone(PIN_SPEAKER, freq, 20);
      delay(20);
    }
    tone(PIN_SPEAKER, 2000, 200);
    delay(200);
  }
}

/**
 * Mesure la distance en cm pour un capteur ultrason DFRobot Gravity V1.0 (1 seul pin)
int mesurerDistance() {
  // Lecture de la tension envoyée par le capteur (entre 0 et 1023)
  int valeurBrute = analogRead(PIN_ULTRASON);
  
  // Pour le capteur DFRobot URM09 Analogique, la conversion standard est :
  // Distance max = 500 cm. La valeur 1023 correspond à 500 cm.
  int distance = (valeurBrute * 500.0) / 1023.0; 
  
  return distance;
}
