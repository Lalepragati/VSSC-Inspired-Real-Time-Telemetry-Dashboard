# VSSC-Inspired Real-Time Telemetry Dashboard

Mission-control style telemetry dashboard with a FastAPI backend and React frontend.

## What Was Updated

- Fixed frequent WS DISCONNECTED issues for local clones.
- Frontend now tries multiple WebSocket targets and auto-recovers:
  - localhost backend first when running locally
  - env-configured backend
  - same-origin fallback
- Updated default frontend env example for localhost development.
- Rewrote setup and troubleshooting steps with clone-to-localhost guidance.

## Features

- Real-time telemetry simulation at 10Hz
- WebSocket broadcast from backend to frontend
- Altitude line chart
- Velocity and fuel gauges
- Alert state when altitude crosses threshold
- Mission timeline milestone events
- Live pitch, yaw, roll attitude panel with 3D orientation cube

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
│   ├── vite.config.js
│   └── .env.example
├── scripts/
│   ├── start-backend.ps1
│   └── start-frontend.ps1
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 20+
- corepack enabled (for pnpm)
- PowerShell 7+ (only if using provided .ps1 scripts)

Enable corepack once if needed:

```bash
corepack enable
```

## Clone and Localhost Setup

```bash
git clone https://github.com/Lalepragati/VSSC-Inspired-Real-Time-Telemetry-Dashboard.git
cd VSSC-Inspired-Real-Time-Telemetry-Dashboard
```

### Required Local Changes After Clone

1. Frontend websocket URL should point to local backend:

```env
frontend/.env
VITE_WS_URL=ws://127.0.0.1:8000/ws
```

2. Backend CORS should allow local frontend origin:

```env
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

If you copy from examples, these defaults are already set for localhost.

## Run Locally (Recommended)

Open two terminals from project root.

### Terminal 1: Backend

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
$env:ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Terminal 2: Frontend

Linux/macOS:

```bash
cp frontend/.env.example frontend/.env
corepack pnpm install --dir frontend
corepack pnpm --dir frontend dev
```

Windows PowerShell:

```powershell
Copy-Item .\frontend\.env.example .\frontend\.env -Force
corepack pnpm install --dir .\frontend
corepack pnpm --dir .\frontend dev
```

Open:

- http://localhost:5173

Backend health checks:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/metrics

## Run Using Existing PowerShell Scripts

From repository root (Windows):

```powershell
.\scripts\start-backend.ps1
```

In second terminal:

```powershell
.\scripts\start-frontend.ps1
```

## Deploy/Hosted Backend Mode

If you want frontend to connect to hosted backend instead of localhost:

```env
frontend/.env
VITE_WS_URL=wss://your-hosted-backend-domain/ws
```

Then restart frontend dev server.

## Troubleshooting

### WS DISCONNECTED

1. Confirm backend is running at port 8000.
2. Check frontend env value:
   - frontend/.env -> VITE_WS_URL=ws://127.0.0.1:8000/ws (for local mode)
3. Ensure backend CORS includes localhost origins.
4. Restart both backend and frontend terminals.
5. Open browser DevTools Network tab and verify /ws handshake status.

### CORS errors in browser

- Set backend env:
  - ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

### Frontend install issues

- Use corepack pnpm commands instead of npm in this project.

## API Endpoints

- GET /health
- GET /metrics
- WS /ws
