# RCA Smart Copilot for SAP CPI — Frontend

React + TypeScript + Vite shell, styled with the **QDKEP "Control Room"** theme
(dark navy `#0a1019` / `#111a28` + RealCore lime `#8cc63f`).

## Run

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → http://localhost:8000)
```

## Structure

```text
frontend/
  public/brand/rca-logo-white.png   RealCore Albania logo
  src/
    styles/theme.css   Design tokens (colors, type, geometry) — sampled from QDKEP
    styles/app.css     Layout + components (sidebar, KPI grid, panels, tables)
    nav.ts             Numbered module navigation
    components/Sidebar.tsx
    pages/Monitoring.tsx   Control-room landing (mock data; wires to /api later)
    pages/Placeholder.tsx  Stub for Generate/iFlows/Groovy/Benchmark/Feedback/Packages/Settings
    App.tsx  main.tsx
```

## Theme reference

All colors are CSS variables in `src/styles/theme.css`. KPI accents:
failed `--status-failed` · success `--status-success` · watched `--status-watched` · warn `--status-warn`.
