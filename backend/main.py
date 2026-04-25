import asyncio
import math
import os
import random
import statistics
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

# Add your GitHub Pages URL here
'''origins = [
   "http://localhost:5173",
    "https://lalepragati.github.io", 
]'''

''' app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''
def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _origins_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [origin.strip() for origin in value.split(",") if origin.strip()]


TICK_SECONDS = _float_env("TELEMETRY_TICK_SECONDS", 0.1)  # 10 Hz
GRAVITY = 9.81
MAX_ALTITUDE_THRESHOLD = _float_env("MAX_ALTITUDE_THRESHOLD", 120_000.0)  # meters
ALLOWED_ORIGINS = _origins_env("ALLOWED_ORIGINS", "*")


@dataclass
class Telemetry:
    timestamp: float
    t: float
    altitude: float
    velocity: float
    fuel: float
    pitch: float
    roll: float
    yaw: float
    status: str
    max_threshold: float
    anomaly_score: float
    anomaly_flag: bool
    predicted_apogee: Optional[float]


class AnomalyDetector:
    """Rolling Z-score anomaly detector for the telemetry stream.

    Maintains a sliding window of recent altitude and velocity readings and
    computes a normalised anomaly score in [0, 1] using the Z-score of the
    current observation relative to the window statistics.  A score above
    *ANOMALY_THRESHOLD* sets the anomaly_flag field.
    """

    WINDOW: int = 60           # number of ticks kept (~6 s at 10 Hz)
    ANOMALY_THRESHOLD: float = 0.70  # normalised score that triggers the flag

    def __init__(self) -> None:
        self._alt_buf: list[float] = []
        self._vel_buf: list[float] = []

    def update(self, altitude: float, velocity: float) -> dict:
        """Push new readings and return a dict with AI-derived fields."""
        self._alt_buf.append(altitude)
        self._vel_buf.append(velocity)

        if len(self._alt_buf) > self.WINDOW:
            self._alt_buf.pop(0)
            self._vel_buf.pop(0)

        anomaly_score = 0.0
        if len(self._alt_buf) >= 10:
            try:
                alt_mean = statistics.mean(self._alt_buf)
                alt_std = statistics.stdev(self._alt_buf)
                if alt_std > 0.0:
                    z = abs((altitude - alt_mean) / alt_std)
                    anomaly_score = min(1.0, z / 3.0)
            except statistics.StatisticsError:
                pass

        predicted_apogee: Optional[float] = None
        if velocity > 0.0:
            predicted_apogee = round(altitude + (velocity ** 2) / (2.0 * GRAVITY), 1)

        return {
            "anomaly_score": round(anomaly_score, 4),
            "anomaly_flag": anomaly_score >= self.ANOMALY_THRESHOLD,
            "predicted_apogee": predicted_apogee,
        }


class RocketSimulator:
    """Simple staged flight model with thrust, drag, coast, and descent."""

    def __init__(self) -> None:
        self.t = 0.0
        self.altitude = 0.0
        self.velocity = 0.0
        self.fuel = 100.0
        self._ai = AnomalyDetector()

    def step(self, dt: float) -> Telemetry:
        powered = self.fuel > 0.0

        if powered:
            thrust_accel = 35.0 * (0.55 + 0.45 * (self.fuel / 100.0))
            burn_rate = 1.1  # % per second
            self.fuel = max(0.0, self.fuel - burn_rate * dt)
        else:
            thrust_accel = 0.0

        drag_accel = 0.00006 * self.velocity * abs(self.velocity)
        acceleration = thrust_accel - GRAVITY - drag_accel
        self.velocity += acceleration * dt
        self.altitude += self.velocity * dt

        if self.altitude < 0.0:
            self.altitude = 0.0
            self.velocity = 0.0

        self.t += dt

        wobble = math.exp(-self.t / 180.0)
        pitch = 90.0 - min(75.0, self.t * 0.22) + 1.8 * wobble * math.sin(self.t * 0.9)
        roll = 3.2 * wobble * math.sin(self.t * 1.25) + random.uniform(-0.2, 0.2)
        yaw = 2.4 * wobble * math.cos(self.t * 1.05) + random.uniform(-0.2, 0.2)

        status = "ALERT" if self.altitude > MAX_ALTITUDE_THRESHOLD else "NOMINAL"

        ai = self._ai.update(self.altitude, self.velocity)

        return Telemetry(
            timestamp=time.time(),
            t=round(self.t, 2),
            altitude=round(self.altitude, 2),
            velocity=round(self.velocity, 2),
            fuel=round(self.fuel, 2),
            pitch=round(pitch, 2),
            roll=round(roll, 2),
            yaw=round(yaw, 2),
            status=status,
            max_threshold=MAX_ALTITUDE_THRESHOLD,
            anomaly_score=ai["anomaly_score"],
            anomaly_flag=ai["anomaly_flag"],
            predicted_apogee=ai["predicted_apogee"],
        )


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def active_count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def broadcast(self, payload: dict) -> None:
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        stale_clients: list[WebSocket] = []

        async def send_one(client: WebSocket) -> None:
            try:
                await client.send_json(payload)
            except Exception:
                stale_clients.append(client)

        await asyncio.gather(*(send_one(client) for client in clients), return_exceptions=False)

        for client in stale_clients:
            await self.disconnect(client)


simulator = RocketSimulator()
manager = ConnectionManager()


async def telemetry_loop() -> None:
    next_tick = time.monotonic()
    while True:
        telemetry = simulator.step(TICK_SECONDS)
        await manager.broadcast(asdict(telemetry))
        next_tick += TICK_SECONDS
        sleep_for = max(0.0, next_tick - time.monotonic())
        await asyncio.sleep(sleep_for)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(telemetry_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="VSSC-Inspired Telemetry API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict:
    return {
        "connected_clients": await manager.active_count(),
        "tick_seconds": TICK_SECONDS,
        "max_altitude_threshold": MAX_ALTITUDE_THRESHOLD,
    }


@app.get("/ai/insights")
async def ai_insights() -> dict:
    """Return the latest AI-derived telemetry analytics snapshot."""
    last = simulator.step(0.0)
    return {
        "anomaly_score": last.anomaly_score,
        "anomaly_flag": last.anomaly_flag,
        "predicted_apogee_m": last.predicted_apogee,
        "current_altitude_m": last.altitude,
        "current_velocity_ms": last.velocity,
        "description": (
            "anomaly_score is a normalised Z-score [0–1] computed from a "
            "rolling window of altitude readings; values ≥ 0.70 set "
            "anomaly_flag=true. predicted_apogee uses kinematic projection "
            "(v²/2g + h) while the rocket is ascending."
        ),
    }


async def telemetry_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "message": "VSSC Telemetry API is operational",
        "endpoints": ["/health", "/metrics", "/ai/insights", "/ws"],
        "docs": "/docs"
    }

# 2. Start the server LAST
if __name__ == "__main__":
    import uvicorn
    import os
    # Get the port from Render's environment, default to 8000 for local dev
    port = int(os.environ.get("PORT", 8000))
    # host must be 0.0.0.0 to be accessible externally
    uvicorn.run(app, host="0.0.0.0", port=port)
