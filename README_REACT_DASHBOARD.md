# Dashboard React para el carrito real

Esta version usa los datos enviados por el carrito Arduino:

- `dashboard_server.py` se conecta al carrito por TCP.
- `frontend/` muestra la ruta cruda, la ruta optimizada y la reproduccion.
- `simulador_arduino.py` queda solo como respaldo para pruebas sin carrito.

## 1. Preparar el carrito

1. Carga el sketch principal del carrito en el Arduino.
2. Verifica que el modulo WiFi cree la red `Carrito_LosAltos`.
3. Conecta la PC a esa red WiFi.

El backend espera encontrar el carrito en:

```text
192.168.4.1:80
```

## 2. Iniciar el backend

Terminal 1:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
Remove-Item Env:\CARRITO_SIMULADOR -ErrorAction SilentlyContinue
python .\dashboard_server.py
```

La API queda en:

```text
http://127.0.0.1:8765
```

## 3. Iniciar React

Terminal 2:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino\frontend
npm install
npm run dev
```

Abre la URL que muestre Vite, normalmente:

```text
http://127.0.0.1:5173
```

## Flujo con el carrito real

1. Presiona `Reconectar` si aparece sin conexion.
2. Presiona `Manual`.
3. El carrito entrara en modo independiente y empezara a enviar movimientos reales.
4. El dashboard dibujara la ruta cruda conforme lleguen `Avanzar`, `izquierda` y `derecha`.
5. Presiona `Parar y optimizar`.
6. El dashboard calculara y mostrara la ruta optimizada.
7. Presiona `Automatico`.
8. Presiona `Ejecutar optimizada`.
9. El carrito ejecutara la ruta optimizada y el dashboard marcara la reproduccion paso a paso.

## Simulador opcional

Solo si no tienes el carrito conectado:

Terminal 1:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
python .\simulador_arduino.py
```

Terminal 2:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
$env:CARRITO_SIMULADOR='1'
python .\dashboard_server.py
```

Luego inicia React igual que arriba.

## Cambiar IP o puerto

Si el carrito usa otra IP o puerto:

```powershell
$env:CARRITO_HOST='192.168.4.1'
$env:CARRITO_PORT='80'
python .\dashboard_server.py
```
