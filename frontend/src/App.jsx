import {
  Activity,
  CircleStop,
  Focus,
  LocateFixed,
  Map,
  Maximize2,
  Minimize2,
  Play,
  PlugZap,
  RotateCcw,
  Route,
  Square,
  Wand2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8765";

const initialState = {
  connected: false,
  connectionTarget: "192.168.4.1:80",
  connectionKind: "ARDUINO REAL",
  mode: "PARADO",
  sequenceStatus: "Inactiva",
  sequenceRunning: false,
  sequenceIndex: 0,
  history: [],
  optimized: [],
  replay: [],
  logs: [],
};

const moves = {
  0: { x: 0, y: 1 },
  1: { x: 1, y: 0 },
  2: { x: 0, y: -1 },
  3: { x: -1, y: 0 },
};

const CM_PER_ADVANCE = 30;
const SECONDS_PER_ADVANCE = 2.5;
const SECONDS_PER_TURN = 1.2;

const navItems = [
  { id: "map", label: "Mapa", icon: Map },
  { id: "raw", label: "Cruda", icon: Route },
  { id: "optimized", label: "Optima", icon: Wand2 },
  { id: "replay", label: "Replay", icon: Activity },
  { id: "events", label: "Eventos", icon: Square },
];

function buildRoute(commands) {
  let x = 0;
  let y = 0;
  let orientation = 0;
  let advanceCount = 0;
  let turnCount = 0;
  const points = [{ x, y, step: 0 }];

  commands.forEach((command) => {
    if (command === "Avanzar") {
      advanceCount += 1;
      x += moves[orientation].x;
      y += moves[orientation].y;
      points.push({ x, y, step: points.length });
    }

    if (command === "derecha") {
      turnCount += 1;
      orientation = (orientation + 1) % 4;
    }

    if (command === "izquierda") {
      turnCount += 1;
      orientation = (orientation + 3) % 4;
    }
  });

  return { advanceCount, commandCount: commands.length, points, orientation, turnCount };
}

function boundsFor(routes) {
  const all = routes.flatMap((route) => route.points);
  const xs = all.map((point) => point.x);
  const ys = all.map((point) => point.y);
  const padding = 5;

  return {
    minX: Math.min(...xs, -1) - padding,
    maxX: Math.max(...xs, 1) + padding,
    minY: Math.min(...ys, -1) - padding,
    maxY: Math.max(...ys, 1) + padding,
  };
}

function commandLabel(command) {
  if (command === "Avanzar") return "Avanzar";
  if (command === "derecha") return "Derecha";
  if (command === "izquierda") return "Izquierda";
  return command;
}

function apiPost(path, body = {}) {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || data.error || "Error de API");
    return data;
  });
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatArrivalTime(totalSeconds) {
  const arrival = new Date(Date.now() + totalSeconds * 1000);
  return arrival.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function RouteMap({
  expanded,
  mode,
  onResetView,
  onToggleExpanded,
  onZoomIn,
  onZoomOut,
  optimizedRoute,
  rawRoute,
  replayRoute,
  zoom,
}) {
  const bounds = boundsFor([rawRoute, optimizedRoute, replayRoute]);
  const cell = 58;
  const width = (bounds.maxX - bounds.minX + 1) * cell;
  const height = (bounds.maxY - bounds.minY + 1) * cell;

  const toSvg = (point) => ({
    x: (point.x - bounds.minX + 0.5) * cell,
    y: (bounds.maxY - point.y + 0.5) * cell,
  });

  const linePoints = (route) =>
    route.points.map((point) => {
      const svgPoint = toSvg(point);
      return `${svgPoint.x},${svgPoint.y}`;
    });

  const rawEnd = rawRoute.points.at(-1);
  const optimizedEnd = optimizedRoute.points.at(-1);
  const replayEnd = replayRoute.points.at(-1);
  const isReplaying = replayRoute.commandCount > 0;
  const robotPoint = isReplaying ? replayEnd : rawEnd;
  const robotOrientation = isReplaying ? replayRoute.orientation : rawRoute.orientation;
  const robotSvg = toSvg(robotPoint ?? { x: 0, y: 0 });
  const viewWidth = width / zoom;
  const viewHeight = height / zoom;
  const viewX = clamp(robotSvg.x - viewWidth / 2, 0, Math.max(0, width - viewWidth));
  const viewY = clamp(robotSvg.y - viewHeight / 2, 0, Math.max(0, height - viewHeight));
  const viewBox = `${viewX} ${viewY} ${viewWidth} ${viewHeight}`;
  const hasOptimizedRoute = optimizedRoute.commandCount > 0;
  const estimatedDistanceCm = optimizedRoute.advanceCount * CM_PER_ADVANCE;
  const estimatedSeconds =
    optimizedRoute.advanceCount * SECONDS_PER_ADVANCE + optimizedRoute.turnCount * SECONDS_PER_TURN;
  const estimatedMinutes = Math.max(1, Math.ceil(estimatedSeconds / 60));

  const grid = [];
  for (let x = bounds.minX; x <= bounds.maxX; x += 1) {
    for (let y = bounds.minY; y <= bounds.maxY; y += 1) {
      const topLeft = {
        x: (x - bounds.minX) * cell,
        y: (bounds.maxY - y) * cell,
      };
      grid.push(
        <rect
          className="grid-cell"
          height={cell}
          key={`${x}:${y}`}
          width={cell}
          x={topLeft.x}
          y={topLeft.y}
        />,
      );
    }
  }

  return (
    <section className={`map-panel ${expanded ? "is-expanded" : ""}`}>
      <div className="map-stage">
        <div className="route-callout">
          <Route size={18} />
          <div>
            <strong>{optimizedRoute.commandCount || rawRoute.commandCount || 0} pasos</strong>
            <span>{optimizedRoute.commandCount > 0 ? "Ruta optimizada lista" : "Mapeando ruta cruda"}</span>
          </div>
        </div>

        <div className="map-actions">
          <button className="map-icon-button" onClick={onZoomIn} title="Acercar mapa" type="button">
            <ZoomIn size={17} />
          </button>
          <button className="map-icon-button" onClick={onResetView} title="Encuadrar ruta" type="button">
            <Focus size={17} />
          </button>
          <button className="map-icon-button" onClick={onZoomOut} title="Alejar mapa" type="button">
            <ZoomOut size={17} />
          </button>
          <button
            className="map-icon-button"
            onClick={onToggleExpanded}
            title={expanded ? "Salir de vista expandida" : "Expandir mapa"}
            type="button"
          >
            {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>
        </div>

        <span className={`mode-badge mode-${mode.toLowerCase()}`}>{mode}</span>

        <svg className="route-svg" role="img" viewBox={viewBox}>
          <g>{grid}</g>

          {rawRoute.points.length > 1 && (
            <polyline className="route-line route-raw" points={linePoints(rawRoute).join(" ")} />
          )}

          {optimizedRoute.points.length > 1 && (
            <polyline
              className="route-line route-optimized"
              points={linePoints(optimizedRoute).join(" ")}
            />
          )}

          {optimizedRoute.points.length > 1 && (
            <polyline
              className="route-line route-navigation"
              points={linePoints(optimizedRoute).join(" ")}
            />
          )}

          {replayRoute.points.length > 1 && (
            <polyline className="route-line route-replay" points={linePoints(replayRoute).join(" ")} />
          )}

          {rawRoute.points.map((point) => {
            const svgPoint = toSvg(point);
            return (
              <g className="step raw-step" key={`raw-${point.step}-${point.x}-${point.y}`}>
                <circle cx={svgPoint.x} cy={svgPoint.y} r="7" />
                {rawRoute.points.length <= 28 && (
                  <text x={svgPoint.x} y={svgPoint.y + 4}>
                    {point.step}
                  </text>
                )}
              </g>
            );
          })}

          {optimizedRoute.points.map((point) => {
            const svgPoint = toSvg(point);
            return (
              <g className="step optimized-step" key={`opt-${point.step}-${point.x}-${point.y}`}>
                <circle cx={svgPoint.x} cy={svgPoint.y} r="5" />
              </g>
            );
          })}

          <rect
            className="cell-marker start-cell"
            height={cell}
            rx="8"
            width={cell}
            x={toSvg({ x: 0, y: 0 }).x - cell / 2}
            y={toSvg({ x: 0, y: 0 }).y - cell / 2}
          />

          {rawEnd && rawRoute.points.length > 1 && (
            <rect
              className="cell-marker finish-cell"
              height={cell}
              rx="8"
              width={cell}
              x={toSvg(rawEnd).x - cell / 2}
              y={toSvg(rawEnd).y - cell / 2}
            />
          )}

          <g className="start-marker">
            <circle cx={toSvg({ x: 0, y: 0 }).x} cy={toSvg({ x: 0, y: 0 }).y} r="13" />
            <text x={toSvg({ x: 0, y: 0 }).x} y={toSvg({ x: 0, y: 0 }).y + 5}>
              S
            </text>
          </g>

          {rawEnd && rawRoute.points.length > 1 && (
            <g className="end-marker raw-end">
              <circle cx={toSvg(rawEnd).x} cy={toSvg(rawEnd).y} r="12" />
              <text x={toSvg(rawEnd).x} y={toSvg(rawEnd).y + 5}>
                F
              </text>
            </g>
          )}

          {optimizedEnd && optimizedRoute.points.length > 1 && (
            <g className="end-marker optimized-end">
              <rect
                height="22"
                rx="6"
                width="22"
                x={toSvg(optimizedEnd).x - 11}
                y={toSvg(optimizedEnd).y - 11}
              />
            </g>
          )}

          <g
            className="robot-marker"
            transform={`translate(${robotSvg.x} ${robotSvg.y}) rotate(${robotOrientation * 90})`}
          >
            <image
              height="54"
              href="/robot-car.png"
              preserveAspectRatio="xMidYMid meet"
              width="54"
              x="-27"
              y="-27"
            />
          </g>
        </svg>

        <div className="map-dock">
          <div className="dock-card">
            <span>Ruta cruda</span>
            <strong>{rawRoute.commandCount} pasos</strong>
            <i className="dock-line raw" />
          </div>
          <div className="dock-card">
            <span>Ruta optimizada</span>
            <strong>{optimizedRoute.commandCount} pasos</strong>
            <i className="dock-line optimized" />
          </div>
          <div className="dock-card">
            <span>Reproduccion</span>
            <strong>{replayRoute.commandCount} pasos</strong>
            <i className="dock-line replay" />
          </div>
        </div>

        {hasOptimizedRoute && (
          <div className="arrival-bubble">
            <div>
              <strong>{formatArrivalTime(estimatedSeconds)}</strong>
              <span>arribo</span>
            </div>
            <div>
              <strong>{estimatedMinutes}</strong>
              <span>min</span>
            </div>
            <div>
              <strong>{estimatedDistanceCm}</strong>
              <span>cm</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function ControlTile({ disabled, icon: Icon, label, onClick, tone }) {
  return (
    <button className={`control-tile ${tone}`} disabled={disabled} onClick={onClick} type="button">
      <Icon size={18} />
      <span>{label}</span>
    </button>
  );
}

function RobotPanel({ busyAction, canRunOptimized, dashboard, runAction }) {
  const progress =
    dashboard.history.length === 0 || dashboard.optimized.length === 0
      ? 0
      : clamp(
          Math.round(
            ((dashboard.history.length - dashboard.optimized.length) / dashboard.history.length) * 100,
          ),
          0,
          100,
        );
  const gaugeAngle = -120 + progress * 2.4;

  return (
    <aside className="robot-panel">
      <div className="robot-visual">
        <img alt="Carrito Arduino" src="/robot-front.png" />
      </div>

      <div className="robot-metrics">
        <div>
          <span>Modo</span>
          <strong>{dashboard.mode}</strong>
        </div>
        <div>
          <span>Pasos</span>
          <strong>{dashboard.history.length}</strong>
        </div>
      </div>

      <div className="control-grid">
        <ControlTile
          disabled={busyAction === "connect"}
          icon={PlugZap}
          label="Reconectar"
          onClick={() => runAction("connect", () => apiPost("/api/connect"))}
          tone="neutral"
        />
        <ControlTile
          disabled={busyAction === "manual" || dashboard.mode === "MANUAL"}
          icon={LocateFixed}
          label="Manual"
          onClick={() => runAction("manual", () => apiPost("/api/mode", { mode: "manual" }))}
          tone="manual"
        />
        <ControlTile
          disabled={busyAction === "stop"}
          icon={CircleStop}
          label="Parar"
          onClick={() => runAction("stop", () => apiPost("/api/mode", { mode: "stop" }))}
          tone="stop"
        />
        <ControlTile
          disabled={busyAction === "auto" || dashboard.mode === "AUTOMATICO"}
          icon={Route}
          label="Auto"
          onClick={() => runAction("auto", () => apiPost("/api/mode", { mode: "auto" }))}
          tone="auto"
        />
        <ControlTile
          disabled={!canRunOptimized || busyAction === "run"}
          icon={Play}
          label="Ruta rapida"
          onClick={() => runAction("run", () => apiPost("/api/run-optimized"))}
          tone="run"
        />
        <ControlTile
          disabled={busyAction === "reset"}
          icon={RotateCcw}
          label="Reiniciar"
          onClick={() => runAction("reset", () => apiPost("/api/reset"))}
          tone="neutral"
        />
      </div>

      <div className="gauge-block">
        <div className="gauge-copy">
          <span>Optimizacion</span>
          <strong>{progress}%</strong>
        </div>
        <div className="rpm-gauge" style={{ "--needle-angle": `${gaugeAngle}deg` }}>
          <div className="gauge-arc" />
          <div className="gauge-red-zone" />
          <div className="gauge-ticks">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((tick) => (
              <span
                key={tick}
                style={{
                  transform: `rotate(${-120 + tick * 30}deg) translateY(-74px) rotate(${120 - tick * 30}deg)`,
                }}
              >
                {tick}
              </span>
            ))}
          </div>
          <i className="gauge-needle" />
          <b className="gauge-hub" />
          <em>x1000 rpm</em>
        </div>
      </div>
    </aside>
  );
}

function CommandTimeline({ title, commands, emptyText }) {
  return (
    <section className="timeline-card">
      <div className="timeline-heading">
        <h3>{title}</h3>
        <span>{commands.length}</span>
      </div>

      {commands.length === 0 ? (
        <p className="empty-copy">{emptyText}</p>
      ) : (
        <div className="command-list">
          {commands.map((command, index) => (
            <span className={`command-chip command-${command}`} key={`${title}-${index}-${command}`}>
              <b>{index + 1}</b>
              {commandLabel(command)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function RoutePage({ commands, emptyText, icon: Icon, title }) {
  return (
    <section className="page-panel">
      <div className="panel-heading">
        <div>
          <p>Detalle de ruta</p>
          <h2>{title}</h2>
        </div>
        <Icon size={24} />
      </div>
      <CommandTimeline commands={commands} emptyText={emptyText} title={title} />
    </section>
  );
}

function EventsPage({ apiStatus, logs }) {
  return (
    <section className="page-panel">
      <div className="panel-heading">
        <div>
          <p>Registro</p>
          <h2>Eventos</h2>
        </div>
        <span className="api-pill">{apiStatus}</span>
      </div>
      <div className="log-list">
        {logs.length === 0 ? (
          <p className="empty-copy">Sin eventos todavia.</p>
        ) : (
          logs.slice(-18).map((entry, index) => (
            <p key={`${entry.time}-${index}`}>
              <b>{entry.time}</b>
              {entry.message}
            </p>
          ))
        )}
      </div>
    </section>
  );
}

function MainPage({
  activePage,
  apiStatus,
  dashboard,
  mapExpanded,
  mapZoom,
  optimizedRoute,
  rawRoute,
  replayRoute,
  resetView,
  setMapExpanded,
  zoomIn,
  zoomOut,
}) {
  if (activePage === "raw") {
    return (
      <RoutePage
        commands={dashboard.history}
        emptyText="Los movimientos reales apareceran aqui."
        icon={Route}
        title="Ruta cruda"
      />
    );
  }

  if (activePage === "optimized") {
    return (
      <RoutePage
        commands={dashboard.optimized}
        emptyText="Presiona Parar para calcular la ruta optimizada."
        icon={Wand2}
        title="Ruta optimizada"
      />
    );
  }

  if (activePage === "replay") {
    return (
      <RoutePage
        commands={dashboard.replay}
        emptyText="La segunda pasada se marcara aqui."
        icon={Activity}
        title="Reproduccion"
      />
    );
  }

  if (activePage === "events") {
    return <EventsPage apiStatus={apiStatus} logs={dashboard.logs} />;
  }

  return (
    <RouteMap
      expanded={mapExpanded}
      mode={dashboard.mode}
      onResetView={resetView}
      onToggleExpanded={() => setMapExpanded((current) => !current)}
      onZoomIn={zoomIn}
      onZoomOut={zoomOut}
      optimizedRoute={optimizedRoute}
      rawRoute={rawRoute}
      replayRoute={replayRoute}
      zoom={mapZoom}
    />
  );
}

export default function App() {
  const [dashboard, setDashboard] = useState(initialState);
  const [apiStatus, setApiStatus] = useState("Conectando con API...");
  const [busyAction, setBusyAction] = useState("");
  const [activePage, setActivePage] = useState("map");
  const [mapExpanded, setMapExpanded] = useState(false);
  const [mapZoom, setMapZoom] = useState(1);

  useEffect(() => {
    fetch(`${API_BASE}/api/state`)
      .then((response) => response.json())
      .then((data) => {
        setDashboard(data);
        setApiStatus("API conectada");
      })
      .catch(() => setApiStatus("API desconectada"));

    const events = new EventSource(`${API_BASE}/api/events`);
    events.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "state") {
        setDashboard(data.payload);
        setApiStatus("API conectada");
      }
    };
    events.onerror = () => setApiStatus("Reconectando con API...");

    return () => events.close();
  }, []);

  const rawRoute = useMemo(() => buildRoute(dashboard.history), [dashboard.history]);
  const optimizedRoute = useMemo(() => buildRoute(dashboard.optimized), [dashboard.optimized]);
  const replayRoute = useMemo(() => buildRoute(dashboard.replay), [dashboard.replay]);

  async function runAction(name, action) {
    setBusyAction(name);
    try {
      await action();
    } catch (error) {
      setApiStatus(error.message);
    } finally {
      setBusyAction("");
    }
  }

  const canRunOptimized = dashboard.optimized.length > 0 && !dashboard.sequenceRunning;
  const zoomIn = () => setMapZoom((current) => clamp(current + 0.35, 1, 3.8));
  const zoomOut = () => setMapZoom((current) => clamp(current - 0.35, 1, 3.8));
  const resetView = () => setMapZoom(1);

  return (
    <main className="cockpit-shell">
      <nav className="side-nav">
        <div className="nav-brand">
          <span />
        </div>
        {navItems.map((item) => (
          <button
            className={`nav-button ${activePage === item.id ? "is-active" : ""}`}
            key={item.id}
            onClick={() => setActivePage(item.id)}
            title={item.label}
            type="button"
          >
            <item.icon size={21} />
          </button>
        ))}
      </nav>

      <section className="dashboard-frame">
        <header className="cockpit-topbar">
          <div className="signal-cluster">
            <span />
            <span />
            <span />
            <b>{dashboard.connectionKind}</b>
          </div>
          <div className="connection-pill">
            <span className={dashboard.connected ? "live-dot on" : "live-dot"} />
            <div>
              <strong>{dashboard.connected ? "Robot conectado" : "Robot sin conexion"}</strong>
              <p>{dashboard.connectionTarget}</p>
            </div>
          </div>
        </header>

        <div className="cockpit-grid">
          <RobotPanel
            busyAction={busyAction}
            canRunOptimized={canRunOptimized}
            dashboard={dashboard}
            runAction={runAction}
          />

          <MainPage
            activePage={activePage}
            apiStatus={apiStatus}
            dashboard={dashboard}
            mapExpanded={mapExpanded}
            mapZoom={mapZoom}
            optimizedRoute={optimizedRoute}
            rawRoute={rawRoute}
            replayRoute={replayRoute}
            resetView={resetView}
            setMapExpanded={setMapExpanded}
            zoomIn={zoomIn}
            zoomOut={zoomOut}
          />
        </div>
      </section>
    </main>
  );
}
