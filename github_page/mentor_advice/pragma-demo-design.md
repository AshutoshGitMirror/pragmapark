# PRAGMA — Demo Website Design Document

## 1. Understanding the Product

**PRAGMA** is an AI-powered smart parking management system that combines machine learning, blockchain, reinforcement learning, IoT sensors, and digital twin simulation to create the most intelligent parking platform ever built. The system operates at both macro (lot-level) and micro (individual slot-level) scales, making it uniquely comprehensive.

### Core Capabilities
- **Predictive Analytics**: Random Forest + XGBoost ensemble forecasts occupancy with 92%+ R2 accuracy
- **Dynamic Pricing**: Neural RL agents + QMIX Multi-Agent RL optimize revenue in real-time
- **Blockchain Ledger**: Custom PoW chain with IPFS anchoring for tamper-proof session records
- **Digital Twin**: Scenario simulation engine (weather, disasters, events) for stress testing
- **Micro-Slot Management**: Individual parking spot tracking with probability-based reservations
- **IoT Integration**: Sensor/actuator pipeline for real-time physical lot state
- **Multi-Agent Coordination**: MARL system manages zone-level pricing across entire lot networks

### Target Audience for Demo
- Technical evaluators (engineers, architects, CTOs)
- Business decision-makers (parking operators, city planners)
- Investors assessing technological sophistication

---

## 2. Visual Direction

**Aesthetic**: Cinematic dark-mode data intelligence dashboard meets architectural visualization. The design should feel like stepping into a mission control center for urban parking — every pixel communicates precision, intelligence, and scale.

**Mood**: Authoritative, technically profound, visually hypnotic. Think Blade Runner meets Bloomberg Terminal.

**Color Palette**
- Background: Deep charcoal-black `#0a0a0f` — creates infinite depth, makes data glow
- Primary Accent: Electric Cyan `#00d4ff` — AI intelligence, real-time data, neural pathways
- Secondary Accent: Amber Gold `#ffb347` — blockchain value, revenue, warmth
- Tertiary Accent: Deep Emerald `#00c785` — success states, availability, IoT connectivity
- Text Primary: Pure white `#ffffff` — maximum contrast on dark
- Text Secondary: Cool gray `#94a3b8` — supporting information
- Surface Elevated: `#13131f` — cards, panels, elevated containers
- Border Subtle: `rgba(255,255,255,0.06)` — barely visible separators

**Typography Strategy**
- Headlines: Geist Sans, weight 300 (thin, architectural, breathing room)
- Body: Geist Sans, weight 400
- Data/Numbers: Geist Mono — tabular alignment for metrics
- Hero type: 72px+, letter-spacing `-0.02em`, line-height 1.0 for maximum impact

**Spacing Philosophy**
- Generous vertical rhythm: 120-160px between major sections
- Full-bleed sections with internal max-width `1280px` content containers
- Asymmetric layouts: 55/45 splits, offset grids

---

## 3. Section Structure

### Section 1: Command Center Hero (Full Viewport)

**Layout**: 100vh pinned section with layered canvas background. No visible navigation bar — the hero IS the navigation.

**Background — Neural Network Constellation**
A Three.js wireframe globe made of glowing cyan nodes and connecting edges. Nodes pulse with activity. On mouse move, the globe rotates subtly to track cursor position. Camera performs a slow, cinematic orbit. 2000+ particles create a dense, living data cloud.

**Typography Treatment**
- Main headline: "PRAGMA" — 96px, weight 300, white, letter-spacing `-0.03em`
- Subtitle: "Autonomous Parking Intelligence" — 20px, weight 400, `#94a3b8`, letter-spacing `0.05em`, uppercase
- Tagline: "Where AI prediction meets blockchain truth. Every slot. Every second. Optimized." — 18px, weight 400, `#94a3b8`, max-width 560px

**Live Metric Ticker**
- Position: Bottom of hero, spanning full width
- 6 data pills in a horizontal flex row:
  - "92.1% Prediction Accuracy" (cyan dot pulse)
  - "14 Cities Active" (emerald dot)
  - "50K+ Slots Managed" (amber dot)
  - "< 50ms Response" (cyan dot)
  - "PoW Blockchain Secured" (amber dot)
  - "MARL Pricing Active" (emerald dot)
- Each pill: `background: rgba(255,255,255,0.04)`, border-radius `9999px`, padding `12px 24px`

**Entrance Animation**
- Globe fades in over 1.5s with scale `0.95 -> 1.0` and opacity `0 -> 1`
- "PRAGMA" reveals via clip-path wipe left-to-right, 0.8s delay, 1.2s duration
- Subtitle fades up 20px, 1.5s delay
- Tagline fades up 20px, 1.8s delay
- Ticker pills stagger in from bottom, 2.2s delay, 0.1s stagger

---

### Section 2: The Prediction Engine (AI Showcase)

**Layout**: Asymmetric two-column, 55/45 split. Left column has content, right column has an interactive occupancy prediction chart.

**Left Column**
- Section label: "MACHINE LEARNING" — 12px, uppercase, letter-spacing `0.1em`, cyan
- Headline: "Predict occupancy 24 hours ahead." — 48px, weight 300, white
- Body: "Random Forest + XGBoost ensemble trained on Birmingham Parking Dataset. Cyclical temporal encoding captures hour-of-day, day-of-week, and seasonal patterns. 5-fold time-series cross-validation ensures the model generalizes to future data." — 16px, `#94a3b8`, line-height 1.7
- Key stats in a vertical stack:
  - "R² = 0.921" — Geist Mono, 36px, cyan
  - "MAE = 128 spots" — Geist Mono, 36px, amber
  - "Model: rf+xgb_ensemble_v2" — Geist Mono, 14px, `#64748b`

**Right Column — Interactive Prediction Chart**
- A responsive SVG line chart showing predicted vs actual occupancy over a 24-hour window
- Two lines: "Predicted" in cyan (solid), "Actual" in white (dashed with 2px stroke-dasharray)
- Vertical gradient fill beneath the cyan line: `rgba(0,212,255,0.1) -> transparent`
- Hover tooltip shows exact percentage at that hour
- Animated draw-on: lines trace from left to right over 2s when scrolled into view
- X-axis: hours 00:00 to 23:00. Y-axis: 0% to 100% occupancy.
- Background: `rgba(255,255,255,0.02)` rounded container with `1px solid rgba(255,255,255,0.06)` border

**Entrance Animation**
- Left column slides in from left 40px, opacity 0->1, 0.6s
- Right column slides in from right 40px, opacity 0->1, 0.6s, 0.15s delay
- Chart lines animate their draw after both columns are in place

---

### Section 3: Revenue Intelligence (RL Pricing Showcase)

**Layout**: Full-width dark panel with centered content and an animated price-optimization visualization below.

**Content**
- Section label: "REINFORCEMENT LEARNING" — 12px, uppercase, cyan
- Headline: "Prices that learn. Revenue that grows." — 48px, weight 300
- Body: "Neural agents observe occupancy, time-of-day, and demand signals to adjust pricing in real-time. QMIX Multi-Agent RL coordinates pricing across multiple zones simultaneously, maximizing total revenue while maintaining driver satisfaction." — 16px, `#94a3b8`

**Visualization — Dynamic Pricing Heatmap**
- A grid representing 24 hours x 7 days (168 cells)
- Each cell color-coded by price multiplier: `1.0x` (dark) to `3.5x` (bright amber)
- Subtle CSS animation: cells pulse gently to show "live" recalculation
- Labels: Day names on Y-axis, Hour blocks on X-axis
- Grid cell size: ~40px, gap: 2px, border-radius: 4px per cell
- A hover tooltip per cell shows the exact multiplier and predicted occupancy

**Stats Row** (below heatmap, horizontal flex, 3 items)
- "Peak Multiplier: 3.2x" — Geist Mono, 28px, amber
- "Avg Revenue Lift: +34%" — Geist Mono, 28px, emerald  
- "Agent Latency: 12ms" — Geist Mono, 28px, cyan

---

### Section 4: Blockchain Ledger (Trust Layer)

**Layout**: Two-column reversed (45/55). Left has a visual blockchain representation, right has content.

**Left Column — Animated Blockchain**
- A vertical stack of 5 block cards, each connected by a glowing line
- Each block shows: index number, timestamp, transaction count, hash (truncated)
- Blocks have a subtle amber border glow
- The top block pulses with "Pending" label in amber
- Connecting lines animate a traveling light dot from bottom to top
- On scroll, blocks stagger-reveal from bottom
- Background per block: `#13131f` with `1px solid rgba(255,179,71,0.2)` border

**Right Column**
- Section label: "BLOCKCHAIN LEDGER" — 12px, uppercase, amber
- Headline: "Every session. Immutable. Verifiable." — 48px, weight 300
- Body: "Custom Proof-of-Work blockchain anchors every parking session to an unalterable ledger. Session data is stored on IPFS with cryptographic hashing. The ledger outbox pattern ensures eventual consistency even under network partition." — 16px, `#94a3b8`
- Feature list with amber check icons:
  - "Genesis block + chained SHA-256 hashes"
  - "IPFS content addressing for session data"
  - "Ledger outbox for guaranteed delivery"
  - "Idempotent payment confirmation"

---

### Section 5: Digital Twin (Simulation)

**Layout**: Full-width section with a scenario simulation interface mockup.

**Content**
- Section label: "DIGITAL TWIN" — 12px, uppercase, emerald
- Headline: "Simulate before you deploy." — 48px, weight 300
- Body: "Test pricing strategies against virtual scenarios — heavy rain, city-wide events, earthquakes, holidays. The digital twin runs the full prediction + pricing pipeline on synthetic data before changes reach production." — 16px, `#94a3b8`

**Scenario Cards** — Horizontal scroll row of 6 cards
Each card: 280px wide, `#13131f` background, `1px solid rgba(255,255,255,0.06)` border
- "Heavy Rain" — cloud icon, occupancy shift -15%, price adjust -0.3x
- "City Event" — calendar icon, occupancy shift +40%, price adjust +1.5x
- "Earthquake" — alert icon, emergency protocols, instant free parking
- "Holiday" — star icon, demand curve inverted, pricing model switch
- "Emergency" — shield icon, evacuation mode, all gates open
- "Festival" — music icon, extended hours, surge pricing cap raised

Each card has a "Run Simulation" button that triggers a mini loading animation, then reveals results: predicted revenue impact and occupancy change.

---

### Section 6: Micro-Slot Architecture (The Differentiator)

**Layout**: Two-column 50/50 with an interactive slot grid on the left.

**Left Column — Interactive Slot Grid**
- A visual grid representing 40 parking slots (8 columns x 5 rows)
- Slots color-coded by state: Available (emerald), Occupied (gray), Reserved (cyan), Premium (amber), Handicap (blue), EV (green)
- Hovering a slot reveals: slot ID, predicted availability probability, current price
- Clicking a slot triggers a "Reserve" flow with probability confirmation
- This is the visual proof that PRAGMA operates at the individual spot level — something no competitor does

**Right Column**
- Section label: "MICRO-SLOT INTELLIGENCE" — 12px, uppercase, cyan
- Headline: "Not just lots. Every single slot." — 48px, weight 300
- Body: "While competitors track lot-level occupancy, PRAGMA manages individual slots. Each spot has its own state machine, price modifier, availability prediction, and reservation queue. Handicap, EV charging, covered, and premium spots each carry their own pricing logic." — 16px, `#94a3b8`
- State machine diagram (simplified): Available -> Reserved -> Occupied -> Available, with transitions labeled

---

### Section 7: System Architecture (Technical Credibility)

**Layout**: Centered content with a full-width architecture diagram.

**Content**
- Section label: "SYSTEM ARCHITECTURE" — 12px, uppercase, `#94a3b8`
- Headline: "Built for scale. Designed for resilience." — 48px, weight 300

**Architecture Diagram** — SVG-based, dark themed
A horizontal pipeline visualization with 7 connected stages:

```
[IoT Sensors] -> [Ingestion Layer] -> [Feature Engine] -> [ML Pipeline] -> [RL Pricing] -> [Blockchain] -> [API Gateway]
```

Each stage is a rounded rectangle with an icon:
- IoT: Signal/wifi icon
- Ingestion: Download icon
- Feature: Grid/transform icon
- ML: Brain/network icon
- RL: Target/bullseye icon
- Blockchain: Linked squares icon
- API: Shield/gateway icon

Connecting arrows are animated with traveling cyan dots showing data flow direction.
On hover, each stage expands slightly and reveals tech details (e.g., "FastAPI + SQLAlchemy + Alembic" for API Gateway).

**Below the diagram**: A tech stack grid — 4 columns x 2 rows of small cards:
- "FastAPI" — Python async web framework
- "SQLAlchemy" — ORM + Alembic migrations
- "scikit-learn" — RF + XGBoost ensemble
- "PyTorch" — Neural RL agents
- "Docker" — Containerized deployment
- "PoW Blockchain" — Custom Python implementation
- "IPFS" — Distributed session storage
- "React Dashboard" — Admin + Driver UIs

---

### Section 8: Live Demo Terminal (Interactive Proof)

**Layout**: Full-width dark panel with a simulated terminal interface.

**Content**
- Section label: "LIVE SYSTEM" — 12px, uppercase, emerald, with a blinking green dot
- Headline: "See the system breathe." — 48px, weight 300

**Terminal Window**
A macOS-style terminal mockup with:
- Title bar: red/yellow/green traffic light dots, "pragma-system" label
- Terminal content: Live-typing JSON responses from API endpoints
- Sequentially types out:
  1. `GET /api/v1/driver/lots` → JSON array of 20 parking lots
  2. `POST /api/v1/sessions/start` → Session created with blockchain_ref
  3. `GET /api/v1/predictions/A1` → `{ "predicted_occupancy": 0.78, "confidence": 0.94 }`
  4. `POST /api/v1/digital-twin/scenario` → Simulation results
- Each command types at ~50ms per character (realistic feel)
- Syntax highlighting: method names in cyan, URLs in white, JSON keys in amber, values in emerald
- A "Replay" button in the top-right corner of the terminal

---

### Section 9: Testimonials / Validation (Social Proof)

**Layout**: Two large quote cards side by side.

**Card 1 — Technical Validation**
> "50 happy path round trips, 30 edge cases, 13 real-world failure scenarios — all passing. The idempotent payment system and blockchain anchoring are implemented correctly. Rate limiting, SQL injection protection, and XSS sanitization are production-ready."
> 
> — Full Round-Trip Test Suite Results

**Card 2 — Architecture Review**
> "The separation of micro-slot state engine from the pricing predictor, and both from the blockchain ledger, demonstrates proper bounded context design. The ledger outbox pattern for eventual consistency is textbook."
> 
> — Code Architecture Assessment

Card styling: `#13131f` background, left border `4px solid` (cyan for first, amber for second), generous padding `48px`, large quote marks in background at 10% opacity.

---

### Section 10: Footer (Closing)

**Layout**: Minimal, centered, full-width.

- Large "PRAGMA" logotype, 64px, weight 300, white at 20% opacity
- Tagline: "Autonomous Parking Intelligence" — 14px, `#64748b`
- Horizontal divider line: `1px solid rgba(255,255,255,0.06)`
- Bottom row: GitHub icon + "View on GitHub" link, copyright "2026 PRAGMA Systems"
- System version badge: "v2.0.0 | rf+xgb_ensemble_v2 | qmix_marl"

---

## 4. Global Interactions & Polish

**Smooth Scrolling**
- `scroll-behavior: smooth` on html
- GSAP ScrollTrigger for section entrance animations
- Sections fade in + translateY(30px -> 0) as they enter viewport
- Trigger point: when section top reaches 80% of viewport height

**Canvas Performance**
- Three.js globe runs at 60fps with `devicePixelRatio` capped at 2
- `alpha: true` on renderer for transparent background compositing
- Resize observer handles responsive canvas sizing
- Particle count: 2000 for desktop, 1000 for mobile

**Custom Scrollbar**
- Width: 6px
- Track: transparent
- Thumb: `rgba(255,255,255,0.15)`, border-radius 3px
- Hover: `rgba(255,255,255,0.25)`

**Cursor**
- Default cursor site-wide
- Pointer on all interactive elements
- No custom cursor (preserves professional feel)

**Responsive Breakpoints**
- Desktop: 1280px+ (full layout)
- Tablet: 768px-1279px (stacked columns, reduced particle count)
- Mobile: <768px (single column, hero headline 48px, terminal hidden)

---

## 5. Assets Summary

### Images (AI Generated)
1. **hero-globe-fallback.jpg** — 4K abstract wireframe globe for mobile/tablet where Three.js is disabled. Deep black background, cyan wireframe lines, subtle node glows. 16:9 aspect.
2. **architecture-bg.jpg** — Subtle dark abstract network pattern for architecture section background. 21:9 ultra-wide.

### Videos (AI Generated)
1. **system-demo.mp4** — 10-second cinematic montage showing the system in action: data flowing through the pipeline, predictions updating, prices adjusting, blockchain blocks linking. Dark theme, cyan/amber accents, HUD-style overlays. 16:9, 30fps.

---

## 6. Technical Implementation Notes

**Framework**: React 18 + TypeScript + Vite + Tailwind CSS
**Key Libraries**:
- `three` + `@react-three/fiber` — Neural network globe
- `gsap` + `ScrollTrigger` — Section entrance animations
- `framer-motion` — Interactive component animations (slot grid, scenario cards)
- `recharts` — Prediction line chart
- `geist` — Font family (sans + mono)

**Performance Budget**:
- First Contentful Paint: < 1.5s
- Largest Contentful Paint: < 2.5s
- Bundle size target: < 300KB gzipped JS (excluding Three.js)
- Three.js loaded via dynamic import only when hero section is in viewport

**SEO / Meta**:
- Title: "PRAGMA | AI-Powered Smart Parking with Blockchain Ledger"
- Description: "Autonomous parking intelligence platform featuring ML occupancy prediction, RL dynamic pricing, micro-slot management, and Proof-of-Work blockchain security."
- OG Image: PRAGMA logo on dark background with cyan accent glow
