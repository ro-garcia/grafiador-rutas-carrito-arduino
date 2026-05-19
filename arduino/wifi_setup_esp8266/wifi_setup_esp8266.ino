#include <SoftwareSerial.h>

// Arduino RX=4 recibe desde TX del ESP.
// Arduino TX=5 envia hacia RX del ESP. Usa divisor de voltaje o level shifter.
SoftwareSerial wifiSerial(4, 5);

void setup() {
  Serial.begin(9600);
  wifiSerial.begin(9600);

  Serial.println("Iniciando configuracion del modulo Wi-Fi...");
  delay(3000);

  // Modo Access Point: el carrito crea su propia red WiFi.
  enviarComando("AT+CWMODE=2");

  // SSID, password, canal 1, seguridad WPA2.
  enviarComando("AT+CWSAP=\"Carrito_LosAltos\",\"12345678\",1,3");

  // Multiples conexiones, necesario para servidor TCP.
  enviarComando("AT+CIPMUX=1");

  // Servidor TCP en puerto 80.
  enviarComando("AT+CIPSERVER=1,80");

  // Muestra IP del modulo. Normalmente sera 192.168.4.1 en modo AP.
  enviarComando("AT+CIFSR");

  Serial.println("=========================================");
  Serial.println("Configuracion terminada.");
  Serial.println("Busca la red WiFi: Carrito_LosAltos");
  Serial.println("Password: 12345678");
  Serial.println("=========================================");
}

void loop() {
  // Puente transparente: todo lo que responde el ESP se ve en Monitor Serie.
  if (wifiSerial.available()) {
    Serial.write(wifiSerial.read());
  }

  // Permite escribir comandos AT manuales desde el Monitor Serie.
  if (Serial.available()) {
    wifiSerial.write(Serial.read());
  }
}

void enviarComando(String comando) {
  Serial.println("--> " + comando);
  wifiSerial.println(comando);
  delay(2000);
}
