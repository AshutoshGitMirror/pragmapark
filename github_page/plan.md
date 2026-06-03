# PRAGMA Demo — Implementation Plan

## Overview

Build a cinematic, interactive React SPA that showcases the full Pragma Smart Parking system by calling the **live Render API** (`https://pragma-4szs.onrender.com/api/v1/`) with graceful fallback for cold starts (free tier, up to 10 min wake time).

Design reference: [`pragma-demo-design.md`](./pragma-demo-design.md)

---

## Phase 0: Verify Live API Endpoints

Before writing any component, hit every API endpoint we need, log the exact response shape, and build fallback JSON files.

| Endpoint | Purpose | Fallback Needed |
|----------|---------|-----------------|
| `GET /api/v1/lots` | Lot list for hero ticker + micro-slot | Yes |
| `GET /api/v1/lots/A1/occupancy` | Prediction chart data | Yes |
| `GET /api/v1/driver/lots` | Enriched lots with ML predictions | Yes |
| `GET /api/v1/blockchain/status` | Chain health | Yes |
| `GET /api/v1/blockchain/pool/lot_a` | Pool details | Yes |
| `GET /api/v1/admin/dashboard` | System-wide stats | Yes |
| `GET /api/v1/admin/system-health` | Layer health | Yes |
| `GET /api/v1/pricing/zones` | Pricing zones | Yes |
| `GET /api/v1/digital-twin/scenarios` | Scenario list | Yes |
| `GET /api/v1/micro/lots/A1/slots` | Slot grid data | Yes |
| `GET /api/v1/marl/status` | MARL training status | Yes |
| `POST /api/v1/sessions/start` | Session lifecycle demo | Yes |
| `POST /api/v1/sessions/end` | Session closure | Yes |
| `POST /api/v1/digital-twin/scenarios/run` | Scenario simulation | Yes |
| `POST /api/v1/payments/confirm` | Payment demo | Yes |
| `POST /api/v1/marl/train` | MARL training trigger | Yes |

**Auth strategy**: Use `POST /api/v1/auth/login` with `admin@pragma.io` / `admin123` to get a JWT, inject into all subsequent requests.

### Fallback generation

For each endpoint, run a curl script against the live Render URL and save the response to `demo/app/src/api/fallback/`. If the server is cold, wait up to 10 min with polling every 30s.

---

## Phase 1: Project Scaffolding

```
demo/app/
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  tailwind.config.ts
  postcss.config.js
  index.html
  public/
  src/
    main.tsx
    App.tsx
    api/
      client.ts          ← fetch wrapper with auth + retry + timeout
      fallback/           ← cached JSON responses
      types.ts            ← TypeScript interfaces from API shapes
    components/
      layout/
        AppShell.tsx       ← global layout, scroll container
        Navigation.tsx     ← side nav or pill nav
        Section.tsx        ← shared section wrapper with scroll reveal
        LoadingSkeleton.tsx
        StatusBadge.tsx
      hero/
        Hero.tsx
        ThreeGlobe.tsx     ← Three.js wireframe globe
        MetricTicker.tsx   ← 6 live data pills
      prediction/
        PredictionEngine.tsx
        PredictionChart.tsx
      revenue/
        RevenueIntelligence.tsx
        PricingHeatmap.tsx
      blockchain/
        BlockchainLedger.tsx
        BlockCard.tsx
      digital-twin/
        DigitalTwin.tsx
        ScenarioCard.tsx
      micro-slot/
        MicroSlotArchitecture.tsx
        SlotGrid.tsx
        SlotCell.tsx
      architecture/
        ArchitectureDiagram.tsx
        TechStackGrid.tsx
      terminal/
        LiveTerminal.tsx
        TerminalLine.tsx
      testimonials/
        Testimonials.tsx
      footer/
        Footer.tsx
    hooks/
      useApi.ts           ← generic fetch hook with fallback chain
      useScrollReveal.ts  ← IntersectionObserver entrance
      useWarmup.ts        ← cold-start warm-up sequence
    styles/
      globals.css          ← Tailwind base + custom theme
    utils/
      format.ts            ← number/currency formatting
      cn.ts                ← class name utility
```

### Cold-Start Warm-Up Sequence (`useWarmup`)

1. On mount: `GET /api/v1/health` with 60s timeout, retry every 30s
2. When health responds 200: `POST /api/v1/auth/login` to get JWT
3. Then: `POST /api/v1/sessions/start` to warm ML pipeline (will fail but warms models)
4. Then: `GET /api/v1/lots` to verify DB readiness
5. Emit `{ warm: true, jwt, coldStartMs }` — all downstream hooks proceed

During warm-up, show a "SYSTEM INITIALIZING" overlay with:
- Animated pulse ring
- Elapsed time counter
- Status messages: "Waking database..." → "Loading ML models..." → "Initializing blockchain..." → "System ready"

---

## Phase 2: Component Implementation

### Section 1 — Hero Command Center

**Components**: `Hero.tsx`, `ThreeGlobe.tsx`, `MetricTicker.tsx`

**Implementation**:
- `ThreeGlobe.tsx`: Three.js wireframe globe with 2000 nodes, cyan edges, mouse-tracking rotation, slow orbit
- Globe is a `<canvas>` inside a full-viewport section
- Title "PRAGMA" in Geist Sans weight 300, 96px, staggered clip-path reveal
- Subtitle + tagline fade up with delay
- `MetricTicker.tsx`: Horizontal pill row at bottom with live data from `/api/v1/admin/dashboard` and `/api/v1/lots`
- While warming up: globe renders but ticker shows "CONNECTING..." pills

**API**: `GET /api/v1/admin/dashboard`, `GET /api/v1/lots`

**Fallback**: Hardcoded stat pills with actual seed data values.

---

### Section 2 — Prediction Engine

**Components**: `PredictionEngine.tsx`, `PredictionChart.tsx`

**Implementation**:
- Two-column layout (55/45)
- Left: ML description + R² = 0.921 stat
- Right: `recharts` LineChart with predicted (cyan solid) vs actual (white dashed) occupancy
- 24-hour window, animated draw-on via framer-motion or manual SVG
- Hover tooltip with percentage

**API**: `GET /api/v1/lots/A1/occupancy?hours=24`

**Fallback**: Pre-generated 24h prediction data from seed data patterns.

---

### Section 3 — Revenue Intelligence

**Components**: `RevenueIntelligence.tsx`, `PricingHeatmap.tsx`

**Implementation**:
- Full-width dark panel
- RL description text
- 24h × 7d heatmap grid (168 cells), color-coded by price multiplier
- Cells pulse gently (CSS animation)
- Hover tooltip: exact multiplier + predicted occupancy
- Stats row: Peak multiplier, Avg revenue lift, Agent latency

**API**: `GET /api/v1/pricing/zones`

**Fallback**: Generated heatmap data from RL pricing formula.

---

### Section 4 — Blockchain Ledger

**Components**: `BlockchainLedger.tsx`, `BlockCard.tsx`

**Implementation**:
- Two-column reversed (45/55)
- Left: 5 block cards in vertical stack with amber glow, connecting lines, traveling light dots
- Each block: index, timestamp, TX count, truncated hash
- Top block: "PENDING" pulse
- Right: Description + feature list with amber check icons
- Blocks stagger-reveal on scroll

**API**: `GET /api/v1/blockchain/status`, `GET /api/v1/blockchain/pool/lot_a`

**Fallback**: Hardcoded block data matching the actual genesis block.

---

### Section 5 — Digital Twin

**Components**: `DigitalTwin.tsx`, `ScenarioCard.tsx`

**Implementation**:
- Full-width section with horizontal scroll row of 6 scenario cards
- Each card: icon, name, occupancy shift, price adjustment
- "Run Simulation" button → loading spinner → results
- Cards from `GET /api/v1/digital-twin/scenarios`
- Simulation results from `POST /api/v1/digital-twin/scenarios/run`

**API**: `GET /api/v1/digital-twin/scenarios`, `POST /api/v1/digital-twin/scenarios/run`

**Fallback**: 6 hardcoded scenario cards with placeholder results.

---

### Section 6 — Micro-Slot Architecture

**Components**: `MicroSlotArchitecture.tsx`, `SlotGrid.tsx`, `SlotCell.tsx`

**Implementation**:
- 50/50 split
- Left: 8×5 grid of 40 slots, color-coded: Available (emerald), Occupied (gray), Reserved (cyan), Premium (amber), Handicap (blue), EV (green)
- Hover: slot ID + probability + price tooltip
- Click: "Reserve" flow with confirmation
- Right: description + state machine diagram

**API**: `GET /api/v1/micro/lots/A1/slots`

**Fallback**: 40 generated slots with realistic distribution.

---

### Section 7 — Architecture Diagram

**Components**: `ArchitectureDiagram.tsx`, `TechStackGrid.tsx`

**Implementation**:
- Pure SVG pipeline: IoT → Ingestion → Feature Engine → ML Pipeline → RL Pricing → Blockchain → API Gateway
- Animated cyan traveling dots on arrows
- Hover: expand stage + tech details
- Below: 4×2 tech stack cards grid

**API**: None (static)

---

### Section 8 — Live Terminal

**Components**: `LiveTerminal.tsx`, `TerminalLine.tsx`

**Implementation**:
- macOS-style terminal mockup
- Types out 4 API calls sequentially:
  1. `GET /api/v1/driver/lots` → enriched lot JSON
  2. `POST /api/v1/sessions/start` → 6-layer activation response
  3. `GET /api/v1/lots/A1/occupancy` → prediction result
  4. `POST /api/v1/digital-twin/scenarios/run` → simulation results
- 50ms/char typing speed
- Syntax highlighting
- Cold start handling: show "SERVICE WARMING UP..." state with retry
- "Replay" button

**API**: Four sequential API calls with real auth

**Fallback**: Pre-recorded JSON responses for each command.

---

### Section 9 — Testimonials

**Components**: `Testimonials.tsx`

**Implementation**:
- Two large quote cards side by side
- Left border accent (cyan / amber)
- Actual test suite numbers hardcoded

**API**: None (static)

---

### Section 10 — Footer

**Components**: `Footer.tsx`

**Implementation**:
- PRAGMA logotype 64px
- Tagline, divider, GitHub link, copyright, version badge
- Actual version from API health response

**API**: `GET /api/v1/health` (version field)

---

## Phase 3: Integration & Polish

### Entrance Animations
- GSAP ScrollTrigger for each section
- Fade in + translateY(30px → 0) when section top reaches 80% viewport
- Stagger child elements

### Custom Scrollbar
- 6px wide, transparent track, `rgba(255,255,255,0.15)` thumb
- CSS only (no library)

### Responsive
- Desktop (1280px+): Full layout
- Tablet (768-1279px): Stacked columns, reduced particles
- Mobile (<768px): Single column, hero 48px, terminal hidden, globe simplified

### Performance
- Three.js `devicePixelRatio` capped at 2
- 2000 particles desktop, 1000 mobile
- Dynamic import for Three.js
- Bundle size budget: <300KB JS gzipped (excl Three.js)

### Loading States
- Per-section skeleton loaders while API fetches
- Cold start: full-screen "SYSTEM INITIALIZING" overlay with progress messages
- Error: inline "Live data unavailable — showing simulation" banner + cached data

---

## Phase 4: Build & Deploy

1. `cd demo/app && npm run build`
2. Serve from FastAPI: mount `demo/app/dist` as static files
3. Update `render.yaml` health check path
4. Deploy to Render
5. The demo is available at `https://pragma-4szs.onrender.com/`

---

## File Manifest

```
demo/
  plan.md                               ← THIS FILE
  pragma-demo-design.md                 ← Design reference
  showcase.py                           ← Keep for Python data gen
  boilerplate.html                      ← Keep for reference
  app/
    package.json
    vite.config.ts
    tsconfig.json
    tsconfig.node.json
    tailwind.config.ts
    postcss.config.js
    index.html
    public/
    src/
      main.tsx
      App.tsx
      vite-env.d.ts
      api/
        client.ts
        types.ts
        fallback/
          lots.json
          occupancy.json
          blockchain-status.json
          dashboard.json
          pricing-zones.json
          scenarios.json
          micro-slots.json
          marl-status.json
          session-start.json
          session-end.json
          scenario-run.json
          payment-confirm.json
          health.json
      components/
        layout/
          AppShell.tsx
          Navigation.tsx
          Section.tsx
          LoadingSkeleton.tsx
          StatusBadge.tsx
        hero/
          Hero.tsx
          ThreeGlobe.tsx
          MetricTicker.tsx
        prediction/
          PredictionEngine.tsx
          PredictionChart.tsx
        revenue/
          RevenueIntelligence.tsx
          PricingHeatmap.tsx
        blockchain/
          BlockchainLedger.tsx
          BlockCard.tsx
        digital-twin/
          DigitalTwin.tsx
          ScenarioCard.tsx
        micro-slot/
          MicroSlotArchitecture.tsx
          SlotGrid.tsx
          SlotCell.tsx
        architecture/
          ArchitectureDiagram.tsx
          TechStackGrid.tsx
        terminal/
          LiveTerminal.tsx
          TerminalLine.tsx
        testimonials/
          Testimonials.tsx
        footer/
          Footer.tsx
      hooks/
        useApi.ts
        useScrollReveal.ts
        useWarmup.ts
      styles/
        globals.css
      utils/
        format.ts
        cn.ts
```
