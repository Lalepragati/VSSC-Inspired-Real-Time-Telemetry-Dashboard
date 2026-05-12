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
- **AI Insights panel**: rolling Z-score anomaly detector + kinematic apogee predictor

## AI Analytics

This project includes lightweight AI-driven analytics computed entirely in the backend (no external ML libraries required — only Python's standard `statistics` module):

| Feature | How it works |
|---|---|
| **Anomaly Score** | Rolling Z-score of the last 60 altitude readings (≈ 6 s at 10 Hz), normalised to [0, 1]. |
| **Anomaly Flag** | Set to `true` when the anomaly score ≥ 0.70 (2.1 σ above the window mean). |
| **Predicted Apogee** | Kinematic projection: `h + v² / (2g)` — the maximum altitude the rocket would reach if thrust cut off right now. |

All three values are broadcast with every WebSocket tick and are also available via the REST endpoint `GET /ai/insights`.

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

## Deploy Frontend on Render

Backend is already deployed at:

- https://vssc-inspired-real-time-telemetry.onrender.com

Frontend is now configured to use this backend in production.

### Option 1: Deploy with render.yaml (recommended)

This repository now includes [render.yaml](render.yaml).

Steps:

1. Push latest code to GitHub.
2. In Render dashboard, click New + and select Blueprint.
3. Connect this repository.
4. Render will detect [render.yaml](render.yaml) and create static site service automatically.
5. After deploy, open your frontend URL and verify WS status is CONNECTED.

### Option 2: Manual Static Site setup on Render

Create a Static Site in Render with:

- Root Directory: frontend
- Build Command: corepack pnpm install && corepack pnpm build
- Publish Directory: dist
- Environment Variable:
  - VITE_WS_URL=wss://vssc-inspired-real-time-telemetry.onrender.com/ws

## Deploy Frontend on Vercel

> **Note:** The Python/WebSocket backend cannot run on Vercel (Vercel serverless does not support persistent WebSocket connections). The backend stays on Render; only the React frontend is deployed to Vercel.

This repository includes [vercel.json](vercel.json) which configures the build automatically.

### Steps

1. Push this branch to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import this repository.
3. Vercel auto-detects the `vercel.json` — no framework preset changes needed.
4. Add the following **Environment Variable** in the Vercel project settings:

   | Name | Value |
   |---|---|
   | `VITE_WS_URL` | `wss://vssc-inspired-real-time-telemetry.onrender.com/ws` |

5. Click **Deploy**. Vercel will run:
   ```
   cd frontend && npm install -g pnpm && pnpm install && pnpm build
   ```
   and serve `frontend/dist/` as a static site.
6. After deploy, open your Vercel URL and verify **WS CONNECTED** appears in the header.

### Why WS disconnect was happening in production

- Production frontend sometimes attempted wrong WS targets (localhost/same-origin without WS server).
- Now frontend prioritizes:
  - VITE_WS_URL
  - Render backend fallback URL
  - same-origin WS fallback
- Also added ws to wss normalization on HTTPS pages to avoid mixed-content WS blocking.

## Troubleshooting

### WS DISCONNECTED

1. Confirm backend is running at port 8000.
2. Check frontend env value:
   - frontend/.env -> VITE_WS_URL=ws://127.0.0.1:8000/ws (for local mode)
  - frontend/.env.production -> VITE_WS_URL=wss://vssc-inspired-real-time-telemetry.onrender.com/ws (for Render production build)
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
- GET /ai/insights
- WS /ws
