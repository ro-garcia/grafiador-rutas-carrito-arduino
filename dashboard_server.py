import json
import os
import queue
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

MODO_SIMULADOR = os.getenv("CARRITO_SIMULADOR", "0") == "1"
ROBOT_HOST = os.getenv("CARRITO_HOST", "127.0.0.1" if MODO_SIMULADOR else "192.168.4.1")
ROBOT_PORT = int(os.getenv("CARRITO_PORT", "8080" if MODO_SIMULADOR else "80"))
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8765"))

MOVIMIENTOS_VALIDOS = {"Avanzar", "izquierda", "derecha"}
MENSAJES_COMPLETOS_SIN_SALTO = {
    "Avanzar",
    "izquierda",
    "derecha",
    "instruccion",
    "Modo Secuencia Activado",
    "Modo Independiente Activado",
}
lock = threading.RLock()
subscribers = []
robot_socket = None
robot_listener = None

state = {
    "connected": False,
    "connectionTarget": f"{ROBOT_HOST}:{ROBOT_PORT}",
    "connectionKind": "SIMULADOR" if MODO_SIMULADOR else "ARDUINO REAL",
    "mode": "PARADO",
    "sequenceStatus": "Inactiva",
    "sequenceRunning": False,
    "sequenceIndex": 0,
    "history": [],
    "optimized": [],
    "replay": [],
    "logs": [],
}


def optimizar_ruta_con_salida(instrucciones):
    if not instrucciones:
        return []

    movimientos = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}

    x, y = 0, 0
    orientacion = 0
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

    ultima_vez_visitada = {}
    for indice, coord in enumerate(coordenadas):
        ultima_vez_visitada[coord] = indice

    coordenadas_optimas = []
    i = 0
    while i < len(coordenadas):
        actual = coordenadas[i]
        coordenadas_optimas.append(actual)
        i = ultima_vez_visitada[actual] + 1

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


def snapshot():
    with lock:
        return json.loads(json.dumps(state))


def publish(event_type="state", payload=None):
    data = {
        "type": event_type,
        "payload": snapshot() if payload is None else payload,
        "sentAt": time.time(),
    }

    dead = []
    with lock:
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(data)
            except Exception:
                dead.append(subscriber)

        for subscriber in dead:
            if subscriber in subscribers:
                subscribers.remove(subscriber)


def add_log(message):
    print(message)
    with lock:
        timestamp = time.strftime("%H:%M:%S")
        state["logs"].append({"time": timestamp, "message": message})
        state["logs"] = state["logs"][-120:]
    publish()


def set_connection_status(connected):
    with lock:
        state["connected"] = connected
    publish()


def send_command(command):
    with lock:
        sock = robot_socket

    if sock is None:
        add_log(f"[SIN CONEXION] No se pudo enviar: {command}")
        return False

    try:
        sock.sendall(f"{command}\n".encode("utf-8"))
        add_log(f"[PANEL -> ROBOT] {command}")
        return True
    except Exception as exc:
        add_log(f"[ERROR] No se pudo enviar {command!r}: {exc}")
        set_connection_status(False)
        return False


def listen_robot(sock):
    buffer = ""
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                add_log("[ROBOT] Conexion cerrada.")
                break

            buffer += data.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                message = line.strip()
                if message:
                    handle_robot_message(message)

            # El Arduino real enviado usa AT+CIPSEND con longitud exacta, pero
            # no agrega salto de linea al payload. El simulador si lo agrega.
            # Esta rama permite aceptar ambos formatos.
            compact_message = buffer.strip()
            if compact_message in MENSAJES_COMPLETOS_SIN_SALTO:
                buffer = ""
                handle_robot_message(compact_message)
        except OSError:
            break
        except Exception as exc:
            add_log(f"[ERROR] Lectura del robot: {exc}")
            break

    set_connection_status(False)


def connect_robot():
    global robot_socket, robot_listener

    with lock:
        old_socket = robot_socket

    if old_socket is not None:
        try:
            old_socket.close()
        except OSError:
            pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    add_log(f"[INFO] Conectando con {state['connectionKind']} en {ROBOT_HOST}:{ROBOT_PORT}...")
    sock.connect((ROBOT_HOST, ROBOT_PORT))
    sock.settimeout(None)

    with lock:
        robot_socket = sock
        state["connected"] = True

    robot_listener = threading.Thread(target=listen_robot, args=(sock,), daemon=True)
    robot_listener.start()
    add_log("[INFO] Conexion con robot/simulador lista.")
    publish()


def handle_robot_message(message):
    next_command = None
    finished = False

    add_log(f"[ROBOT -> PANEL] {message}")

    with lock:
        if state["mode"] == "MANUAL" and message in MOVIMIENTOS_VALIDOS:
            state["history"].append(message)

        if state["sequenceRunning"] and "instruccion" in message.lower():
            current_index = state["sequenceIndex"]
            if current_index < len(state["optimized"]):
                state["replay"].append(state["optimized"][current_index])

            state["sequenceIndex"] += 1
            if state["sequenceIndex"] < len(state["optimized"]):
                next_command = state["optimized"][state["sequenceIndex"]]
            else:
                state["sequenceRunning"] = False
                state["sequenceStatus"] = "Finalizada"
                finished = True

    publish()

    if next_command:
        send_command(next_command)
    elif finished:
        add_log("[SECUENCIA] Ruta optimizada finalizada.")


def mode_manual():
    with lock:
        state["mode"] = "MANUAL"
        state["sequenceStatus"] = "Inactiva"
        state["sequenceRunning"] = False
        state["sequenceIndex"] = 0
        state["history"] = []
        state["optimized"] = []
        state["replay"] = []
    publish()
    send_command("s")
    add_log("[MODO] Manual activo. Grabando movimientos.")


def mode_stop():
    with lock:
        if state["mode"] == "MANUAL" and state["history"]:
            state["optimized"] = optimizar_ruta_con_salida(state["history"])
            add_log(f"[OPTIMIZACION] Ruta cruda: {state['history']}")
            add_log(f"[OPTIMIZACION] Ruta optimizada: {state['optimized']}")

        state["mode"] = "PARADO"
        state["sequenceStatus"] = "Inactiva"
        state["sequenceRunning"] = False
        state["sequenceIndex"] = 0

    def burst_stop():
        for _ in range(4):
            send_command("p")
            time.sleep(0.05)

    threading.Thread(target=burst_stop, daemon=True).start()
    add_log("[MODO] Robot detenido.")
    publish()


def mode_auto():
    with lock:
        state["mode"] = "AUTOMATICO"
        state["sequenceStatus"] = "Lista"
        state["sequenceRunning"] = False
        state["sequenceIndex"] = 0
        state["replay"] = []
    publish()
    send_command("e")
    add_log("[MODO] Automatico activo.")


def run_optimized():
    with lock:
        if not state["optimized"]:
            return False, "No hay una ruta optimizada. Mapea una ruta real en modo Manual primero."

        state["mode"] = "AUTOMATICO"
        state["sequenceStatus"] = "En progreso"
        state["sequenceRunning"] = True
        state["sequenceIndex"] = 0
        state["replay"] = []
        first_command = state["optimized"][0]

    publish()
    ok = send_command(first_command)
    if ok:
        add_log("[SECUENCIA] Ejecutando ruta optimizada.")
        return True, "Secuencia iniciada."

    with lock:
        state["sequenceRunning"] = False
        state["sequenceStatus"] = "Error de envio"
    publish()
    return False, "No se pudo enviar la primera instruccion."


def reset_state():
    with lock:
        state["mode"] = "PARADO"
        state["sequenceStatus"] = "Inactiva"
        state["sequenceRunning"] = False
        state["sequenceIndex"] = 0
        state["history"] = []
        state["optimized"] = []
        state["replay"] = []
    add_log("[INFO] Dashboard reiniciado.")
    publish()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CarritoDashboard/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/state":
            self._json(200, snapshot())
            return

        if path == "/api/events":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            subscriber = queue.Queue()
            with lock:
                subscribers.append(subscriber)

            initial = {"type": "state", "payload": snapshot(), "sentAt": time.time()}
            try:
                self.wfile.write(f"data: {json.dumps(initial)}\n\n".encode("utf-8"))
                self.wfile.flush()

                while True:
                    try:
                        event = subscriber.get(timeout=20)
                        payload = f"data: {json.dumps(event)}\n\n".encode("utf-8")
                    except queue.Empty:
                        payload = b": ping\n\n"
                    self.wfile.write(payload)
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with lock:
                    if subscriber in subscribers:
                        subscribers.remove(subscriber)
            return

        self._json(404, {"error": "Ruta no encontrada."})

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            payload = self._read_json()

            if path == "/api/connect":
                connect_robot()
                self._json(200, {"ok": True, "state": snapshot()})
                return

            if path == "/api/mode":
                mode = payload.get("mode")
                if mode == "manual":
                    mode_manual()
                elif mode == "stop":
                    mode_stop()
                elif mode == "auto":
                    mode_auto()
                else:
                    self._json(400, {"ok": False, "error": "Modo invalido."})
                    return
                self._json(200, {"ok": True, "state": snapshot()})
                return

            if path == "/api/run-optimized":
                ok, message = run_optimized()
                self._json(200 if ok else 409, {"ok": ok, "message": message, "state": snapshot()})
                return

            if path == "/api/reset":
                reset_state()
                self._json(200, {"ok": True, "state": snapshot()})
                return

            self._json(404, {"ok": False, "error": "Ruta no encontrada."})
        except Exception as exc:
            add_log(f"[ERROR] API: {exc}")
            self._json(500, {"ok": False, "error": str(exc)})

    def log_message(self, format, *args):
        return


def main():
    try:
        connect_robot()
    except Exception as exc:
        add_log(f"[AVISO] No se pudo conectar al iniciar: {exc}")
        add_log("[AVISO] Puedes abrir el simulador y presionar Reconectar en React.")

    server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler)
    print(f"[API] Dashboard server en http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print("[API] Presiona Ctrl+C para cerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
