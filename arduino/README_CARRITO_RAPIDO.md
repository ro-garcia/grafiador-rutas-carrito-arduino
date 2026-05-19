# Segunda pasada mas rapida

El sketch `carrito_principal_rapido/carrito_principal_rapido.ino` separa las velocidades en dos grupos:

- Modo `Manual`: velocidad mas estable para mapear el laberinto.
- Modo `Automatico`: velocidad mas alta para ejecutar la ruta optimizada.

## Valores importantes

```cpp
const int VELOCIDAD_MAPEO_AVANCE_IZQ = 150;
const int VELOCIDAD_MAPEO_AVANCE_DER = 168;

const int VELOCIDAD_AUTO_AVANCE_IZQ = 185;
const int VELOCIDAD_AUTO_AVANCE_DER = 205;
```

Tambien se aumento la distancia minima en automatico:

```cpp
const int DISTANCIA_MINIMA_AUTO = 20;
```

Eso ayuda a que, al ir mas rapido, el carrito frene antes.

## Flujo esperado

1. En el dashboard, presiona `Manual`.
2. El carrito mapea a velocidad normal.
3. Presiona `Parar y optimizar`.
4. Coloca el carrito otra vez en el inicio, mirando en la misma direccion inicial.
5. Presiona `Automatico`.
6. Presiona `Ejecutar optimizada`.
7. El carrito ejecuta la ruta optimizada con las velocidades `AUTO`.

## Calibracion

Si el carrito se pasa o choca:

- Baja `VELOCIDAD_AUTO_AVANCE_IZQ`.
- Baja `VELOCIDAD_AUTO_AVANCE_DER`.
- Sube `DISTANCIA_MINIMA_AUTO`.

Si gira demasiado o muy poco:

- Ajusta `TIEMPO_AUTO_GIRO_90`.

Empieza con cambios pequenos, por ejemplo de 5 a 10 unidades.
