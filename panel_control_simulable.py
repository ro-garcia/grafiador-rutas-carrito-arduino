import os
import socket
import threading
import tkinter as tk
import time

# ==========================================
# CONFIGURACION
# ==========================================
# Para usar el simulador:
#   set CARRITO_SIMULADOR=1
#   python simulador_carrito/panel_control_simulable.py
#
# Para usar el Arduino real, deja CARRITO_SIMULADOR sin definir.
MODO_SIMULADOR = os.getenv("CARRITO_SIMULADOR", "0") == "1"
IP_CARRITO = "127.0.0.1" if MODO_SIMULADOR else "192.168.4.1"
PUERTO = 8080 if MODO_SIMULADOR else 80

# ==========================================
# VARIABLES GLOBALES
# ==========================================
historial = []
instrucciones_optimizadas = []

estado_robot = "PARADO"
indice_instruccion = 0
ejecutando_secuencia = False
cliente = None
ventana = None


# ==========================================
# ALGORITMO DE OPTIMIZACION DE RUTA
# ==========================================
def optimizar_ruta_con_salida(instrucciones):
    if not instrucciones:
        return []

    movimientos = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}

    # FASE 1: Simular ruta.
    x, y = 0, 0
    orientacion = 0  # 0: Norte, 1: Este, 2: Sur, 3: Oeste
    coordenadas = [(x, y)]

    for cmd in instrucciones:
        if cmd == "Avanzar":
            dx, dy = movimientos[orientacion]
            x += dx
            y += dy
            coordenadas.append((x, y))
        elif cmd == "derecha":
            orientacion = (orientacion + 1) % 4
        elif cmd == "izquierda":
            orientacion = (orientacion - 1) % 4

    orientacion_final_original = orientacion

    # FASE 2: Eliminar bucles.
    ultima_vez_visitada = {}
    for indice, coord in enumerate(coordenadas):
        ultima_vez_visitada[coord] = indice

    coordenadas_optimas = []
    i = 0
    while i < len(coordenadas):
        actual = coordenadas[i]
        coordenadas_optimas.append(actual)
        i = ultima_vez_visitada[actual] + 1

    # FASE 3: Reconstruir ruta.
    instrucciones_finales = []
    orientacion_actual = 0

    for i in range(len(coordenadas_optimas) - 1):
        x1, y1 = coordenadas_optimas[i]
        x2, y2 = coordenadas_optimas[i + 1]

        dx, dy = x2 - x1, y2 - y1
        if (dx, dy) == (0, 1):
            orientacion_objetivo = 0
        elif (dx, dy) == (1, 0):
            orientacion_objetivo = 1
        elif (dx, dy) == (0, -1):
            orientacion_objetivo = 2
        elif (dx, dy) == (-1, 0):
            orientacion_objetivo = 3
        else:
            continue

        giros = (orientacion_objetivo - orientacion_actual) % 4
        if giros == 1:
            instrucciones_finales.append("derecha")
        elif giros == 2:
            instrucciones_finales.extend(["derecha", "derecha"])
        elif giros == 3:
            instrucciones_finales.append("izquierda")

        instrucciones_finales.append("Avanzar")
        orientacion_actual = orientacion_objetivo

    # FASE 4: Ajuste final de orientacion y salida.
    giros_finales = (orientacion_final_original - orientacion_actual) % 4
    if giros_finales == 1:
        instrucciones_finales.append("derecha")
    elif giros_finales == 2:
        instrucciones_finales.extend(["derecha", "derecha"])
    elif giros_finales == 3:
        instrucciones_finales.append("izquierda")

    if instrucciones_finales and instrucciones_finales[-1] in ["izquierda", "derecha"]:
        instrucciones_finales.append("Avanzar")

    return instrucciones_finales


# ==========================================
# COMUNICACION CON EL ROBOT / SIMULADOR
# ==========================================
def manejar_mensaje_arduino(mensaje):
    global ejecutando_secuencia, indice_instruccion

    print(f"[Arduino]: {mensaje}")

    if estado_robot == "MANUAL" and mensaje in ["Avanzar", "izquierda", "derecha"]:
        historial.append(mensaje)
        programar_en_gui(actualizar_textos)

    if ejecutando_secuencia and "instruccion" in mensaje.lower():
        indice_instruccion += 1

        if indice_instruccion < len(instrucciones_optimizadas):
            siguiente_orden = instrucciones_optimizadas[indice_instruccion]
            enviar_comando(siguiente_orden)
            print(f"--> [Secuencia] Enviando paso {indice_instruccion}: {siguiente_orden}")
        else:
            print("\n--> [Secuencia] Ruta optimizada finalizada.")
            ejecutando_secuencia = False
            programar_en_gui(
                lambda: lbl_estado_secuencia.config(text="Secuencia: Finalizada", fg="green")
            )
            programar_en_gui(lambda: btn_enviar_lista.config(state=tk.NORMAL, bg="gold"))


def escuchar():
    buffer = ""

    while True:
        try:
            datos = cliente.recv(1024)
            if not datos:
                print("Conexion cerrada por el robot/simulador.")
                break

            buffer += datos.decode("utf-8", errors="replace")
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                mensaje = linea.strip()
                if mensaje:
                    manejar_mensaje_arduino(mensaje)
        except OSError:
            break
        except Exception as e:
            print("Conexion cerrada o error:", e)
            break


def conectar():
    global cliente

    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.settimeout(5)
    print(f"Buscando al {'simulador' if MODO_SIMULADOR else 'Arduino'} en {IP_CARRITO}:{PUERTO}...")
    cliente.connect((IP_CARRITO, PUERTO))
    cliente.settimeout(None)
    print("Conectado exitosamente.")

    hilo = threading.Thread(target=escuchar, daemon=True)
    hilo.start()


def enviar_comando(texto):
    if cliente is None:
        print(f"[SIN CONEXION] No se pudo enviar: {texto}")
        return

    try:
        cliente.sendall(f"{texto}\n".encode("utf-8"))
    except Exception as e:
        print(f"Error al enviar {texto!r}: {e}")


def programar_en_gui(funcion):
    if ventana is not None:
        ventana.after(0, funcion)


# ==========================================
# BOTONES Y LOGICA DE ESTADOS
# ==========================================
def modo_parar():
    global estado_robot, ejecutando_secuencia, instrucciones_optimizadas

    if estado_robot == "MANUAL" and len(historial) > 0:
        print("\n[INFO] Procesando ruta del laberinto...")
        instrucciones_optimizadas = optimizar_ruta_con_salida(historial)
        print("-> Ruta cruda:", historial)
        print("-> Ruta optimizada:", instrucciones_optimizadas)
        actualizar_textos()

    estado_robot = "PARADO"
    ejecutando_secuencia = False

    def enviar_rafaga():
        for _ in range(4):
            enviar_comando("p")
            time.sleep(0.05)

    threading.Thread(target=enviar_rafaga, daemon=True).start()

    btn_manual.config(state=tk.NORMAL, bg="lightblue")
    btn_auto.config(state=tk.NORMAL, bg="lightgreen")
    btn_parar.config(state=tk.DISABLED, bg="lightgray")
    btn_enviar_lista.config(state=tk.DISABLED, bg="lightgray")

    lbl_estado_principal.config(text="ESTADO: PARADO", fg="red")
    lbl_estado_secuencia.config(text="Secuencia: Inactiva", fg="gray")
    print("\n--- [ ESTADO: PARADO ] ---")


def modo_manual():
    global estado_robot

    estado_robot = "MANUAL"
    enviar_comando("s")

    historial.clear()
    instrucciones_optimizadas.clear()
    actualizar_textos()

    btn_manual.config(state=tk.DISABLED, bg="lightgray")
    btn_auto.config(state=tk.DISABLED, bg="lightgray")
    btn_parar.config(state=tk.NORMAL, bg="salmon")
    btn_enviar_lista.config(state=tk.DISABLED, bg="lightgray")

    lbl_estado_principal.config(text="ESTADO: MANUAL", fg="blue")
    lbl_estado_secuencia.config(text="Secuencia: Inactiva", fg="gray")
    print("\n--- [ MODO: MANUAL ] --- Historial reseteado. Mapeando...")


def modo_automatico():
    global estado_robot

    estado_robot = "AUTOMATICO"
    enviar_comando("e")

    btn_manual.config(state=tk.DISABLED, bg="lightgray")
    btn_auto.config(state=tk.DISABLED, bg="lightgray")
    btn_parar.config(state=tk.NORMAL, bg="salmon")
    btn_enviar_lista.config(state=tk.NORMAL, bg="gold")

    lbl_estado_principal.config(text="ESTADO: AUTOMATICO", fg="green")
    lbl_estado_secuencia.config(text="Secuencia: Inactiva", fg="gray")
    print("\n--- [ MODO: AUTOMATICO ] --- Listo para ejecutar ruta optimizada.")


def iniciar_envio_lista():
    global ejecutando_secuencia, indice_instruccion

    if len(instrucciones_optimizadas) == 0:
        print("[AVISO] No hay una ruta procesada para enviar. Mapea en manual primero.")
        return

    print(f"\nIniciando secuencia ({len(instrucciones_optimizadas)} instrucciones)...")
    ejecutando_secuencia = True
    indice_instruccion = 0

    btn_enviar_lista.config(state=tk.DISABLED, bg="lightgray")
    lbl_estado_secuencia.config(text="Secuencia: En progreso...", fg="blue")

    primer_orden = instrucciones_optimizadas[0]
    enviar_comando(primer_orden)
    print(f"--> [Secuencia] Enviando paso 0: {primer_orden}")


def actualizar_textos():
    lbl_historial.config(text=f"Pasos Mapeados (Crudo): {len(historial)}")
    lbl_procesar.config(text=f"Pasos Optimizados: {len(instrucciones_optimizadas)}")


def al_cerrar():
    if estado_robot != "PARADO":
        enviar_comando("p")

    try:
        if cliente is not None:
            cliente.close()
    finally:
        ventana.destroy()


# ==========================================
# INTERFAZ
# ==========================================
def crear_interfaz():
    global ventana
    global lbl_estado_principal, lbl_historial, lbl_procesar, lbl_estado_secuencia
    global btn_manual, btn_parar, btn_auto, btn_enviar_lista

    ventana = tk.Tk()
    ventana.title("Panel de Control Los Altos")
    ventana.geometry("400x380")
    ventana.configure(padx=20, pady=10)

    modo_texto = "SIMULADOR" if MODO_SIMULADOR else "ARDUINO REAL"
    lbl_modo = tk.Label(ventana, text=f"Conexion: {modo_texto} ({IP_CARRITO}:{PUERTO})", fg="gray")
    lbl_modo.pack()

    lbl_estado_principal = tk.Label(
        ventana, text="ESTADO: PARADO", font=("Arial", 14, "bold"), fg="red"
    )
    lbl_estado_principal.pack(pady=10)

    frame_estados = tk.Frame(ventana)
    frame_estados.pack(fill=tk.X, pady=10)

    btn_manual = tk.Button(
        frame_estados, text="MANUAL (s)", command=modo_manual, width=12, bg="lightblue"
    )
    btn_manual.grid(row=0, column=0, padx=5)

    btn_parar = tk.Button(
        frame_estados,
        text="PARAR (p)",
        command=modo_parar,
        width=12,
        bg="lightgray",
        state=tk.DISABLED,
    )
    btn_parar.grid(row=0, column=1, padx=5)

    btn_auto = tk.Button(
        frame_estados, text="AUTO (e)", command=modo_automatico, width=12, bg="lightgreen"
    )
    btn_auto.grid(row=0, column=2, padx=5)

    tk.Frame(ventana, height=2, bg="gray").pack(fill=tk.X, pady=10)

    lbl_historial = tk.Label(ventana, text="Pasos Mapeados (Crudo): 0", font=("Arial", 11))
    lbl_historial.pack()

    lbl_procesar = tk.Label(ventana, text="Pasos Optimizados: 0", font=("Arial", 11))
    lbl_procesar.pack()

    tk.Frame(ventana, height=2, bg="gray").pack(fill=tk.X, pady=10)

    btn_enviar_lista = tk.Button(
        ventana,
        text="Enviar Ruta Optimizada",
        command=iniciar_envio_lista,
        state=tk.DISABLED,
        bg="lightgray",
        font=("Arial", 10, "bold"),
    )
    btn_enviar_lista.pack(fill=tk.X, pady=5)

    lbl_estado_secuencia = tk.Label(ventana, text="Secuencia: Inactiva", fg="gray")
    lbl_estado_secuencia.pack()

    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)


if __name__ == "__main__":
    try:
        conectar()
    except Exception as e:
        print(f"No se pudo conectar: {e}")
        print("Tip: ejecuta primero simulador_carrito/simulador_arduino.py o revisa la IP del Arduino.")
        raise SystemExit(1)

    crear_interfaz()
    ventana.mainloop()
