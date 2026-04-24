import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler, Legend);

const MAX_POINTS = 180;
const DEFAULT_THRESHOLD = 120000;
const MAX_RECONNECT_DELAY_MS = 5000;
const MAX_TIMELINE_ITEMS = 12;

const MILESTONE_RULES = [
  { id: "liftoff", label: "Liftoff", condition: ({ t }) => t >= 1 },
  { id: "max-q", label: "Max Q Reached", condition: ({ t }) => t >= 30 },
  { id: "stage-1-sep", label: "Stage 1 Separation", condition: ({ altitude }) => altitude >= 15000 },
  { id: "fairing-sep", label: "Fairing Separation", condition: ({ t }) => t >= 60 },
  { id: "karman", label: "Karman Line Crossed", condition: ({ altitude }) => altitude >= 100000 },
  { id: "meco", label: "Main Engine Cutoff", condition: ({ fuel }) => fuel <= 5 },
];

function resolveWsUrl() {
  const envUrl = import.meta.env?.VITE_WS_URL;
  if (envUrl) return envUrl;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://127.0.0.1:8000/ws`;
}

const Gauge = React.memo(function Gauge({ label, value, unit, percent, color }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 shadow-lg">
      <div className="mb-2 text-xs uppercase tracking-widest text-slate-400">{label}</div>
      <div className="mb-3 font-mono text-3xl text-slate-100">{value.toFixed(1)} {unit}</div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full ${color} transition-all duration-150`}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
      <div className="mt-2 text-right text-xs text-slate-400">{Math.round(percent)}%</div>
    </div>
  );
});

const AttitudeReadout = React.memo(function AttitudeReadout({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950/60 p-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-1 font-mono text-xl text-cyan-300">{value.toFixed(2)} deg</div>
    </div>
  );
});

export default function Dashboard() {
  const chartRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);
  const firedMilestonesRef = useRef(new Set());

  const [connected, setConnected] = useState(false);
  const [altitude, setAltitude] = useState(0);
  const [velocity, setVelocity] = useState(0);
  const [fuel, setFuel] = useState(100);
  const [pitch, setPitch] = useState(0);
  const [roll, setRoll] = useState(0);
  const [yaw, setYaw] = useState(0);
  const [status, setStatus] = useState("NOMINAL");
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [timeline, setTimeline] = useState([
    {
      id: "init",
      event: "Telemetry Link Initialized",
      timestampLabel: new Date().toLocaleTimeString(),
      missionTimeLabel: "T+0.0s",
    },
  ]);

  const pushMilestone = (eventLabel, missionTime) => {
    setTimeline((prev) => {
      const item = {
        id: `${eventLabel}-${missionTime}`,
        event: eventLabel,
        timestampLabel: new Date().toLocaleTimeString(),
        missionTimeLabel: `T+${missionTime.toFixed(1)}s`,
      };
      return [item, ...prev].slice(0, MAX_TIMELINE_ITEMS);
    });
  };

  const chartData = useMemo(
    () => ({
      labels: [],
      datasets: [
        {
          label: "Altitude (m)",
          data: [],
          borderColor: "#22d3ee",
          backgroundColor: "rgba(34, 211, 238, 0.18)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.25,
          fill: true,
        },
      ],
    }),
    []
  );

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      normalized: true,
      parsing: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          ticks: { color: "#94a3b8", maxTicksLimit: 10 },
          grid: { color: "rgba(148, 163, 184, 0.15)" },
        },
        y: {
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148, 163, 184, 0.15)" },
          title: { display: true, text: "Meters", color: "#94a3b8" },
        },
      },
    }),
    []
  );

  useEffect(() => {
    isMountedRef.current = true;
    const wsUrl = resolveWsUrl();

    const connect = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        if (isMountedRef.current) setConnected(true);
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setConnected(false);

        const attempt = reconnectAttemptsRef.current + 1;
        reconnectAttemptsRef.current = attempt;
        const delay = Math.min(500 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
        reconnectTimeoutRef.current = window.setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        let packet;
        try {
          packet = JSON.parse(event.data);
        } catch {
          return;
        }

        if (isMountedRef.current) {
          setConnected(true);
        }

        setAltitude(packet.altitude ?? 0);
        setVelocity(packet.velocity ?? 0);
        setFuel(packet.fuel ?? 0);
        setPitch(packet.pitch ?? 0);
        setRoll(packet.roll ?? 0);
        setYaw(packet.yaw ?? 0);
        setStatus(packet.status ?? "NOMINAL");
        setThreshold(packet.max_threshold ?? DEFAULT_THRESHOLD);

        const snapshot = {
          t: Number(packet.t ?? 0),
          altitude: Number(packet.altitude ?? 0),
          fuel: Number(packet.fuel ?? 0),
        };

        for (const rule of MILESTONE_RULES) {
          if (firedMilestonesRef.current.has(rule.id)) {
            continue;
          }
          if (rule.condition(snapshot)) {
            firedMilestonesRef.current.add(rule.id);
            pushMilestone(rule.label, snapshot.t);
          }
        }

        if (snapshot.altitude > (packet.max_threshold ?? DEFAULT_THRESHOLD)) {
          const thresholdKey = "threshold-breach";
          if (!firedMilestonesRef.current.has(thresholdKey)) {
            firedMilestonesRef.current.add(thresholdKey);
            pushMilestone("Safety Threshold Breach", snapshot.t);
          }
        }

        const chart = chartRef.current;
        if (!chart?.data?.datasets?.[0]) return;

        const t = Number(packet.t ?? 0);
        const altitudeValue = Number(packet.altitude ?? 0);
        const labels = chart.data.labels;
        const values = chart.data.datasets[0].data;

        labels.push(`${t.toFixed(1)}s`);
        values.push(altitudeValue);

        if (labels.length > MAX_POINTS) {
          labels.shift();
          values.shift();
        }

        chart.update("none");
      };
    };

    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  const velocityPercent = Math.min(100, (Math.max(0, velocity) / 4000) * 100);
  const fuelPercent = Math.min(100, Math.max(0, fuel));
  const alert = altitude > threshold || status === "ALERT";
  const cubeTransform = {
    transform: `rotateX(${pitch}deg) rotateY(${yaw}deg) rotateZ(${roll}deg)`,
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#111827_0%,_#020617_55%,_#000000_100%)] p-4 text-slate-200 md:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="font-mono text-2xl tracking-wide text-cyan-300 md:text-4xl">Mission Control</h1>
            <p className="text-sm text-slate-400">VSSC-Inspired Real-Time Telemetry Dashboard</p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                connected ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
              }`}
            >
              {connected ? "WS CONNECTED" : "WS DISCONNECTED"}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                alert ? "bg-red-500 text-white" : "bg-cyan-500/20 text-cyan-300"
              }`}
            >
              STATUS: {alert ? "RED" : "NOMINAL"}
            </span>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Gauge label="Velocity" value={velocity} unit="m/s" percent={velocityPercent} color="bg-cyan-400" />
              <Gauge label="Fuel" value={fuel} unit="%" percent={fuelPercent} color="bg-amber-400" />
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 shadow-lg">
                <div className="mb-2 text-xs uppercase tracking-widest text-slate-400">Altitude</div>
                <div className="font-mono text-3xl text-slate-100">{altitude.toFixed(1)} m</div>
                <div className="mt-2 text-xs text-slate-400">Max Threshold: {threshold.toLocaleString()} m</div>
              </div>
            </section>

            <section className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl md:p-6">
              <div className="mb-3 text-sm uppercase tracking-widest text-slate-400">Altitude Stream</div>
              <div className="h-[360px]">
                <Line ref={chartRef} data={chartData} options={chartOptions} />
              </div>
            </section>

            <section className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl md:p-6">
              <div className="mb-4 text-sm uppercase tracking-widest text-slate-400">Attitude and Orientation</div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <AttitudeReadout label="Pitch" value={pitch} />
                  <AttitudeReadout label="Yaw" value={yaw} />
                  <AttitudeReadout label="Roll" value={roll} />
                </div>

                <div className="flex items-center justify-center rounded-xl border border-slate-700 bg-slate-950/60 py-5 [perspective:900px]">
                  <div className="relative h-24 w-24 [transform-style:preserve-3d] transition-transform duration-150" style={cubeTransform}>
                    <div className="absolute inset-0 border border-cyan-300/70 bg-cyan-500/15 [transform:translateZ(12px)]" />
                    <div className="absolute inset-0 border border-blue-300/70 bg-blue-500/15 [transform:rotateY(180deg)_translateZ(12px)]" />
                    <div className="absolute inset-0 border border-emerald-300/70 bg-emerald-500/15 [transform:rotateY(90deg)_translateZ(12px)]" />
                    <div className="absolute inset-0 border border-rose-300/70 bg-rose-500/15 [transform:rotateY(-90deg)_translateZ(12px)]" />
                    <div className="absolute inset-0 border border-amber-300/70 bg-amber-500/15 [transform:rotateX(90deg)_translateZ(12px)]" />
                    <div className="absolute inset-0 border border-violet-300/70 bg-violet-500/15 [transform:rotateX(-90deg)_translateZ(12px)]" />
                  </div>
                </div>
              </div>
            </section>
          </div>

          <aside className="xl:col-span-4">
            <section className="h-full rounded-2xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl md:p-6">
              <div className="mb-4 text-sm uppercase tracking-widest text-slate-400">Mission Timeline</div>
              <div className="space-y-3">
                {timeline.map((item) => (
                  <div key={item.id} className="rounded-lg border border-slate-700/80 bg-slate-950/60 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-block h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_14px_rgba(74,222,128,0.95)]" />
                      <span className="font-mono text-xs text-slate-400">{item.missionTimeLabel}</span>
                    </div>
                    <div className="mt-2 text-sm font-semibold text-emerald-300">{item.event}</div>
                    <div className="mt-1 text-xs text-slate-400">{item.timestampLabel}</div>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </section>
      </div>
    </div>
  );
}
