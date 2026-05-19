# Simulador del carrito Arduino

Estos dos scripts permiten probar el panel sin tener el Arduino fisico.

## 1. Ejecutar el Arduino falso

Abre una terminal y entra a la carpeta independiente del simulador:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
```

Luego ejecuta:

```powershell
python .\simulador_arduino.py
```

Debe aparecer algo como:

```text
[SIM] Arduino falso escuchando en 127.0.0.1:8080
```

## 2. Ejecutar el panel en modo simulador

Abre otra terminal y ejecuta:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
$env:CARRITO_SIMULADOR='1'
python .\panel_control_simulable.py
```

## 3. Probar el flujo completo

1. Presiona `MANUAL (s)`.
2. El simulador enviara una ruta falsa al panel.
3. Espera a que suba el contador de `Pasos Mapeados`.
4. Presiona `PARAR (p)`.
5. El panel calculara la ruta optimizada.
6. Presiona `AUTO (e)`.
7. Presiona `Enviar Ruta Optimizada`.
8. El simulador respondera `instruccion completada` despues de cada paso.

## Cambiar la ruta falsa

Edita la lista `RUTA_MANUAL_SIMULADA` en:

```text
C:\Users\rgarcia\simulador_carrito_arduino\simulador_arduino.py
```

Los movimientos validos son:

```text
Avanzar
izquierda
derecha
```

## Usar Arduino real

Ejecuta el panel sin definir `CARRITO_SIMULADOR`:

```powershell
cd C:\Users\rgarcia\simulador_carrito_arduino
python .\panel_control_simulable.py
```

En ese modo se conectara a:

```text
192.168.4.1:80
```
