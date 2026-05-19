import socket
import threading
import time

HOST = "127.0.0.1"
PORT = 8080

# Ruta falsa que el simulador enviara cuando el panel entre a modo manual.
# Esta ruta dibuja un cuadrado, vuelve al inicio y luego sale avanzando.
RUTA_MANUAL_SIMULADA = [
    "Avanzar",
    "derecha",
    "Avanzar",
    "derecha",
    "Avanzar",
    "derecha",
    "Avanzar",
    "derecha",
    "Avanzar",
]

MOVIMIENTOS_VALIDOS = {"Avanzar", "izquierda", "derecha"}
detener_ruta_manual = threading.Event()


def enviar_linea(conexion, texto):
    conexion.sendall(f"{texto}\n".encode("utf-8"))


def enviar_ruta_manual(conexion):
    detener_ruta_manual.clear()
    print("[SIM] Enviando ruta manual falsa...")
    for paso in RUTA_MANUAL_SIMULADA:
        if detener_ruta_manual.is_set():
            print("[SIM] Ruta manual falsa detenida por PARAR.")
            return
        time.sleep(0.7)
        if detener_ruta_manual.is_set():
            print("[SIM] Ruta manual falsa detenida por PARAR.")
            return
        print(f"[SIM -> PANEL] {paso}")
        enviar_linea(conexion, paso)
    print("[SIM] Ruta manual falsa terminada. Presiona PARAR en el panel.")


def atender_cliente(conexion, direccion):
    print(f"[SIM] Panel conectado desde {direccion}")
    buffer = ""

    with conexion:
        while True:
            datos = conexion.recv(1024)
            if not datos:
                print("[SIM] Panel desconectado.")
                break

            buffer += datos.decode("utf-8", errors="replace")
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                comando = linea.strip()
                if not comando:
                    continue

                print(f"[PANEL -> SIM] {comando}")

                if comando == "s":
                    threading.Thread(target=enviar_ruta_manual, args=(conexion,), daemon=True).start()
                elif comando == "e":
                    print("[SIM] Modo automatico activado.")
                elif comando == "p":
                    detener_ruta_manual.set()
                    print("[SIM] Robot detenido.")
                elif comando in MOVIMIENTOS_VALIDOS:
                    time.sleep(0.8)
                    print("[SIM -> PANEL] instruccion completada")
                    enviar_linea(conexion, "instruccion completada")
                else:
                    print(f"[SIM] Comando no reconocido: {comando}")


def main():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen(1)

    print(f"[SIM] Arduino falso escuchando en {HOST}:{PORT}")
    print("[SIM] Abre otra terminal y ejecuta el panel en modo simulador.")

    while True:
        conexion, direccion = servidor.accept()
        atender_cliente(conexion, direccion)


if __name__ == "__main__":
    main()
