import asyncio
import math
import os
import random
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


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


class RocketSimulator:
    """Simple staged flight model with thrust, drag, coast, and descent."""

    def __init__(self) -> None:
        self.t = 0.0
        self.altitude = 0.0
        self.velocity = 0.0
        self.fuel = 100.0

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


@app.websocket("/ws")
async def telemetry_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
