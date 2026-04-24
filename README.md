# VSSC-Inspired Real-Time Telemetry Dashboard

Low-latency mission-control style telemetry system built with FastAPI (backend) and React + Tailwind + Chart.js (frontend).

## What This Project Implements

- Real-time telemetry simulation at 10Hz (every 100ms)
- WebSocket broadcast from backend to frontend
- Altitude streaming line chart
- Digital gauges for velocity and fuel
- Threshold-based status indicator (turns RED on alert)
- Mission Timeline sidebar with automatic milestone insertion
- Vehicle Attitude module with live pitch, yaw, roll
- CSS 3D cube rotating in real-time based on attitude telemetry
- WebSocket reconnect with exponential backoff

## Project Structure

```text
.
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── Dashboard.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.js
│   └── .env.example
├── scripts/
│   ├── start-backend.ps1
│   └── start-frontend.ps1
└── README.md
```

## Backend (FastAPI)

Telemetry packet fields sent over `/ws`:

- `timestamp`
- `t`
- `altitude`
- `velocity`
- `fuel`
- `pitch`
- `roll`
- `yaw`
- `status`
- `max_threshold`

Simulation behavior:

- Powered ascent with thrust tapering
- Drag term (`v * |v|`)
- Coast/descent behavior after fuel depletion
- Attitude wobble model for pitch/roll/yaw

API endpoints:

- `GET /health`
- `GET /metrics`
- `WS /ws`

## Frontend (React + Tailwind)

Dashboard modules:

- Mission status header and connection badge
- Real-time altitude chart (Chart.js)
- Velocity/Fuel gauges
- Altitude/threshold panel
- Attitude & Orientation panel
- Mission Timeline panel with glowing milestone indicators

Performance notes:

- Chart is updated via direct chart instance mutation (`chart.update("none")`) to keep 10Hz updates smooth.
- Reconnect logic uses exponential backoff for network resilience.

## Prerequisites

- Python 3.10+
- Node.js 20+
- PowerShell (Windows)

## Package Manager Note

In this environment, `npm` can fail with `ERR_INVALID_ARG_TYPE` during install.
Use `corepack pnpm` for frontend commands.

## Setup and Run (End-to-End)

### 1. Clone and open

```powershell
git clone https://github.com/Lalepragati/VSSC-Inspired-Real-Time-Telemetry-Dashboard.git
cd VSSC-Inspired-Real-Time-Telemetry-Dashboard
```

### 2. Run backend

```powershell
Set-Location D:\projects\python\isro
.\scripts\start-backend.ps1
```

Optional (development autoreload):

```powershell
$env:DEV_RELOAD="1"
.\scripts\start-backend.ps1
```

Backend checks:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/metrics

### 3. Run frontend (second terminal)

```powershell
Set-Location D:\projects\python\isro
.\scripts\start-frontend.ps1
```

Open:

- http://localhost:5173

## Manual Commands (Without Scripts)

### Backend manual

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
$env:ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Frontend manual

```powershell
corepack pnpm install --dir .\frontend
Copy-Item .\frontend\.env.example .\frontend\.env -Force
corepack pnpm --dir .\frontend dev
```

## Environment Variables

Backend (`backend/.env.example`):

- `TELEMETRY_TICK_SECONDS=0.1`
- `MAX_ALTITUDE_THRESHOLD=120000`
- `ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`

Frontend (`frontend/.env.example`):

- `VITE_WS_URL=ws://127.0.0.1:8000/ws`

## Build for Production (Frontend)

```powershell
corepack pnpm --dir .\frontend build
corepack pnpm --dir .\frontend preview
```

## Troubleshooting

- `WS DISCONNECTED` in UI:
  - Confirm backend is running on port `8000`
  - Confirm `frontend/.env` has `VITE_WS_URL=ws://127.0.0.1:8000/ws`
  - Restart backend and frontend terminals
- `npm install` fails with `ERR_INVALID_ARG_TYPE`:
  - Use `corepack pnpm install --dir .\frontend`
- Backend immediately exits when launched in automation shells:
  - Run from a normal terminal using `./scripts/start-backend.ps1`

## Author

Pragati Lale
