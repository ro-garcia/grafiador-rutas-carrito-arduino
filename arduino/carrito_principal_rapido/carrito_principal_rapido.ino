#include <Servo.h>
#include <SoftwareSerial.h>

// ===== PINES WIFI =====
SoftwareSerial wifiSerial(4, 5);

// ===== PINES DE MOTORES =====
#define speedPinR 3
#define RightDirectPin1 12
#define RightDirectPin2 11

#define speedPinL 6
#define LeftDirectPin1 7
#define LeftDirectPin2 8

// ===== PINES DE SENSORES Y SERVO =====
#define SERVO_PIN 9
#define Echo_PIN 2
#define Trig_PIN 13

// ===== CONSTANTES DE NAVEGACION =====
// Manual: mas estable para descubrir/mapear.
const int DISTANCIA_MINIMA_MAPEO = 15;
const int VELOCIDAD_MAPEO_AVANCE_IZQ = 150;
const int VELOCIDAD_MAPEO_AVANCE_DER = 168;
const int VELOCIDAD_MAPEO_GIRO = 250;
const int TIEMPO_MAPEO_GIRO_90 = 360;

// Automatico: segunda pasada con ruta optimizada, un poco mas rapida.
// Si se pasa de largo o golpea, baja estas velocidades o sube DISTANCIA_MINIMA_AUTO.
const int DISTANCIA_MINIMA_AUTO = 20;
const int VELOCIDAD_AUTO_AVANCE_IZQ = 185;
const int VELOCIDAD_AUTO_AVANCE_DER = 205;
const int VELOCIDAD_AUTO_GIRO = 250;
const int TIEMPO_AUTO_GIRO_90 = 360;

// ===== ANGULOS DEL SERVO =====
const int ANGULO_FRENTE = 90;
const int ANGULO_IZQUIERDA = 165;
const int ANGULO_DERECHA = 15;

Servo head;

// ===== VARIABLES DE CONTROL DE ESTADOS =====
unsigned long tiempoAnterior = 0;

enum EstadoRobot {
  AVANZANDO,
  EVALUANDO_OBSTACULO,
  ESPERANDO_SERVO_IZQ,
  ESPERANDO_SERVO_DER,
  EJECUTANDO_GIRO,
  ESPERANDO_SERVO_CENTRO
};

EstadoRobot estadoActual = AVANZANDO;

int distanciaIzq = 0;
int distanciaDer = 0;
bool girarAIzquierda = false;

// Variables de comunicacion
String mensaje = "";
String automatico = "";
String orden = "esperando";

// ===== FUNCIONES DEL SENSOR =====
int medirDistancia() {
  digitalWrite(Trig_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(Trig_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(Trig_PIN, LOW);

  noInterrupts();
  long duracion = pulseIn(Echo_PIN, HIGH, 25000);
  interrupts();

  if (duracion == 0) return 200;

  int distancia = duracion / 58;
  if (distancia < 4) return 200;

  return distancia;
}

// ===== FUNCIONES DE MOVIMIENTO =====
void setVelocidad(int speed_L, int speed_R) {
  analogWrite(speedPinL, speed_L);
  analogWrite(speedPinR, speed_R);
}

void detener() {
  digitalWrite(RightDirectPin1, HIGH); digitalWrite(RightDirectPin2, HIGH);
  digitalWrite(LeftDirectPin1, HIGH);  digitalWrite(LeftDirectPin2, HIGH);

  analogWrite(speedPinL, 255);
  analogWrite(speedPinR, 255);
}

void avanzar() {
  digitalWrite(RightDirectPin1, HIGH); digitalWrite(RightDirectPin2, LOW);
  digitalWrite(LeftDirectPin1, HIGH);  digitalWrite(LeftDirectPin2, LOW);
}

void girarIzquierda() {
  digitalWrite(RightDirectPin1, HIGH); digitalWrite(RightDirectPin2, LOW);
  digitalWrite(LeftDirectPin1, LOW);   digitalWrite(LeftDirectPin2, HIGH);
}

void girarDerecha() {
  digitalWrite(RightDirectPin1, LOW);  digitalWrite(RightDirectPin2, HIGH);
  digitalWrite(LeftDirectPin1, HIGH);  digitalWrite(LeftDirectPin2, LOW);
}

// ===== SETUP =====
void setup() {
  Serial.begin(9600);

  wifiSerial.begin(9600);
  delay(2000);
  wifiSerial.println("AT+CIPMUX=1");
  delay(500);
  wifiSerial.println("AT+CIPSERVER=1,80");
  delay(500);

  pinMode(RightDirectPin1, OUTPUT); pinMode(RightDirectPin2, OUTPUT); pinMode(speedPinR, OUTPUT);
  pinMode(LeftDirectPin1, OUTPUT);  pinMode(LeftDirectPin2, OUTPUT);  pinMode(speedPinL, OUTPUT);
  pinMode(Trig_PIN, OUTPUT);        pinMode(Echo_PIN, INPUT);

  head.attach(SERVO_PIN);
  head.write(ANGULO_FRENTE);
  delay(1000);

  while (wifiSerial.available()) {
    wifiSerial.read();
  }

  automatico = "p";
}

// ===== BUCLE PRINCIPAL =====
void loop() {
  unsigned long tiempoActual = millis();

  recibirMensaje();

  if (automatico == "e") {
    // MODO AUTOMATICO: ejecuta la ruta optimizada enviada por Python.
    // Usa velocidades mas altas que el modo manual.
    if (orden == "Avanzar") {
      head.write(ANGULO_FRENTE);
      delay(20);

      if (medirDistancia() > DISTANCIA_MINIMA_AUTO) {
        setVelocidad(VELOCIDAD_AUTO_AVANCE_IZQ, VELOCIDAD_AUTO_AVANCE_DER);
        avanzar();
      } else {
        detener();
        orden = "esperando";
        enviarMensaje("instruccion");
      }
    } else if (orden == "izquierda") {
      setVelocidad(VELOCIDAD_AUTO_GIRO, VELOCIDAD_AUTO_GIRO);
      girarIzquierda();
      delay(TIEMPO_AUTO_GIRO_90);
      detener();
      delay(600);
      orden = "esperando";
      enviarMensaje("instruccion");
    } else if (orden == "derecha") {
      setVelocidad(VELOCIDAD_AUTO_GIRO, VELOCIDAD_AUTO_GIRO);
      girarDerecha();
      delay(TIEMPO_AUTO_GIRO_90);
      detener();
      delay(600);
      orden = "esperando";
      enviarMensaje("instruccion");
    } else if (orden == "esperando") {
      detener();
    }
  } else if (automatico == "s") {
    // MODO MANUAL/INDEPENDIENTE: descubre el laberinto y avisa movimientos.
    switch (estadoActual) {
      case AVANZANDO:
        head.write(ANGULO_FRENTE);
        delay(20);

        if (medirDistancia() > DISTANCIA_MINIMA_MAPEO) {
          setVelocidad(VELOCIDAD_MAPEO_AVANCE_IZQ, VELOCIDAD_MAPEO_AVANCE_DER);
          avanzar();
        } else {
          detener();
          enviarMensaje("Avanzar");
          delay(1000);
          tiempoAnterior = tiempoActual;
          estadoActual = EVALUANDO_OBSTACULO;
        }
        break;

      case EVALUANDO_OBSTACULO:
        if (tiempoActual - tiempoAnterior >= 200) {
          head.write(ANGULO_IZQUIERDA);
          tiempoAnterior = tiempoActual;
          estadoActual = ESPERANDO_SERVO_IZQ;
        }
        break;

      case ESPERANDO_SERVO_IZQ:
        if (tiempoActual - tiempoAnterior >= 1000) {
          distanciaIzq = medirDistancia();
          head.write(ANGULO_DERECHA);
          tiempoAnterior = tiempoActual;
          estadoActual = ESPERANDO_SERVO_DER;
        }
        break;

      case ESPERANDO_SERVO_DER:
        if (tiempoActual - tiempoAnterior >= 1000) {
          distanciaDer = medirDistancia();
          girarAIzquierda = (distanciaIzq > distanciaDer);

          setVelocidad(VELOCIDAD_MAPEO_GIRO, VELOCIDAD_MAPEO_GIRO);
          if (girarAIzquierda) {
            girarIzquierda();
            mensaje = "izquierda";
          } else {
            girarDerecha();
            mensaje = "derecha";
          }

          tiempoAnterior = millis();
          estadoActual = EJECUTANDO_GIRO;
        }
        break;

      case EJECUTANDO_GIRO:
        if (tiempoActual - tiempoAnterior >= TIEMPO_MAPEO_GIRO_90) {
          detener();
          head.write(ANGULO_FRENTE);

          tiempoAnterior = millis();

          enviarMensaje(mensaje);
          estadoActual = ESPERANDO_SERVO_CENTRO;
        }
        break;

      case ESPERANDO_SERVO_CENTRO:
        if (tiempoActual - tiempoAnterior >= 400) {
          estadoActual = AVANZANDO;
        }
        break;
    }
  } else if (automatico == "p") {
    detener();
  }
}

// ===== FUNCIONES DE COMUNICACION WI-FI =====
void recibirMensaje() {
  if (wifiSerial.available()) {
    String peticion = wifiSerial.readStringUntil('\n');

    if (peticion.indexOf("+IPD,") != -1) {
      int separador = peticion.indexOf(':');
      if (separador != -1) {
        String mensajePython = peticion.substring(separador + 1);
        mensajePython.trim();

        if (mensajePython == "e") {
          automatico = mensajePython;
          orden = "esperando";
          enviarMensaje("Modo Secuencia Activado");
        } else if (mensajePython == "s") {
          automatico = mensajePython;
          estadoActual = AVANZANDO;
          enviarMensaje("Modo Independiente Activado");
        } else if (mensajePython == "p") {
          automatico = mensajePython;
        } else {
          orden = mensajePython;
        }
      }
    }
  }
}

void enviarMensaje(String texto) {
  wifiSerial.print("AT+CIPSEND=0,");
  wifiSerial.println(texto.length());
  delay(20);
  wifiSerial.print(texto);
}
