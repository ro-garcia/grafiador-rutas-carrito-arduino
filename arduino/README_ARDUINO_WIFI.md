# Configuracion WiFi del carrito

El sketch `wifi_setup_esp8266.ino` sirve solo para configurar y probar el modulo WiFi ESP con comandos AT.

## Que hace

- Pone el ESP en modo Access Point.
- Crea la red `Carrito_LosAltos`.
- Usa la contrasena `12345678`.
- Activa multiples conexiones.
- Abre un servidor TCP en el puerto `80`.
- Muestra la IP del modulo con `AT+CIFSR`.

La IP esperada normalmente es:

```text
192.168.4.1
```

## Como usarlo

1. Abre Arduino IDE.
2. Carga `arduino/wifi_setup_esp8266/wifi_setup_esp8266.ino`.
3. Abre el Monitor Serie a `9600`.
4. Espera respuestas `OK`.
5. Revisa que en la computadora aparezca la red WiFi `Carrito_LosAltos`.
6. Conectate con la clave `12345678`.

## Importante

Este sketch no controla motores, sensores ni rutas. Solo configura y prueba WiFi.

Despues de confirmar que la red aparece, vuelve a cargar el sketch principal del carrito para recuperar el control del robot.

## Conexion con el dashboard

Con el WiFi configurado, el dashboard Python/React puede conectarse al carrito real con:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
Remove-Item Env:\CARRITO_SIMULADOR -ErrorAction SilentlyContinue
python .\dashboard_server.py
```

El backend intentara conectarse a:

```text
192.168.4.1:80
```

## Si no responde

- Verifica que el Monitor Serie este a `9600`.
- Verifica que el ESP tambien este configurado a `9600`.
- Si ves caracteres raros, prueba otro baud rate.
- Usa fuente estable de `3.3V`; el ESP puede consumir picos altos.
- Une GND de Arduino y ESP.
- No conectes el RX del ESP directo a 5V; usa divisor de voltaje o level shifter.
