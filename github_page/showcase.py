#!/usr/bin/env python3
"""
Pragma Smart Parking — The Living City
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scroll-driven observatory into a living parking grid.
"""

import json, math, hashlib, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict

OUT_DIR = Path(__file__).parent


# ── Data Models ──

@dataclass
class RushHourStep:
    step: int; time_label: str
    occupancy_pct: float; predicted_occupancy_pct: float
    price: float; base_price: float
    overflow_warning: bool; is_full: bool
    arrival_rate: float; ml_confidence: float
    story: str

@dataclass
class Block:
    index: int; timestamp: str; previous_hash: str
    hash: str; data: dict; nonce: int; valid: bool = True
    story: str = ""

@dataclass
class BookingStep:
    hour: int; price: float; availability_pct: float
    cumulative_bookings: int; total_demand: int; surge_tier: str
    story: str

@dataclass
class MarlZoneStep:
    step: int; zone_a_occ: float; zone_b_occ: float
    zone_c_occ: float; zone_d_occ: float
    overflow_zone: str | None; reroute_active: bool; total_city_occ: float
    story: str

@dataclass
class CancelStep:
    step: int; time_label: str; occupancy_before_pct: float
    price: float; cancellation_rate_pct: float
    cancellations: int; net_occupancy_pct: float; event: str
    story: str


# ── Simulation Engines ──

def _rh_price(occ, base, lo, hi):
    if occ < 0.5:      p = base * 0.8
    elif occ < 0.7:    p = base * 1.0
    elif occ < 0.85:   p = base * 1.3
    elif occ < 0.95:   p = base * 1.7
    else:              p = base * 2.2
    return round(max(lo, min(hi, p)), 2)

def simulate_rush_hour(n=20):
    random.seed(42)
    occ = 0.30
    steps = []
    stories = [
        "5:47 AM — First cars trickle in. The grid is dark. Twelve spots taken.",
        "6:02 AM — Commuters emerge. Nodes flicker amber across the city.",
        "6:18 AM — 38% full. The algorithm adjusts. A quiet hum begins.",
        "6:35 AM — Density rising. Second tier pricing activates. $12/hr.",
        "6:51 AM — Half full in under an hour. The city is waking up.",
        "7:08 AM — Traffic thickens. Arrival rate steepens. Price at $14.",
        "7:24 AM — Only 18 spots left. Late departures clog the exits.",
        "7:41 AM — Overflow probability 62%. MARL agents stir in the dark.",
        "7:58 AM — 88% predicted by 8:15. ML system engaged. Confidence 94%.",
        "8:14 AM — Price climbs to $19. Late arrivals circle the block.",
        "8:31 AM — 92% full. Overflow warning. The city holds its breath.",
        "8:47 AM — Peak density. Every spot turns over in under 4 minutes.",
        "9:04 AM — Price holds at $22. The system breathes for a moment.",
        "9:21 AM — First departures. The demand curve bends at last.",
        "9:38 AM — Cooldown begins. Price eases. Spots reappear like spring.",
        "9:54 AM — $18/hr. The grid repopulates from the edges inward.",
        "10:11 AM — 68% full. Normal pricing resumes. Morning rush fading.",
        "10:28 AM — 55% and falling. The morning rush in the rearview.",
        "10:44 AM — 42%. A dozen cars in the last hour. City settles.",
        "11:01 AM — Cycle complete. 32% occupancy. The grid breathes easy."
    ]
    for i in range(n):
        t = f"{8 + i * 2 // 60:02d}:{i * 2 % 60:02d}"
        flow = 0.045 * (1 + 0.6 * math.sin(math.pi * i / (n - 1))) + random.uniform(-0.02, 0.02)
        occ = min(1, max(0.1, occ + flow))
        pred = min(1, max(0.1, occ + 0.045 * 1.5 * (1 + 0.6 * math.sin(math.pi * min(i + 3, n - 1) / (n - 1)))))
        conf = max(0.7, 1 - 0.3 * (pred - occ))
        story = stories[i] if i < len(stories) else f"{t} — {round(occ*100):.0f}% at ${_rh_price(pred,10,6,25):.0f}"
        steps.append(RushHourStep(i + 1, t, round(occ * 100, 1), round(pred * 100, 1),
            _rh_price(pred, 10, 6, 25), 10, occ > 0.85, occ > 0.95,
            round(flow * 100, 1), round(conf * 100, 1), story))
    return steps

def simulate_blockchain(n=12):
    random.seed(42)
    blocks, prev = [], "0" * 64
    for i in range(n):
        nonce = random.randint(100000, 999999)
        ts = (datetime.now(timezone.utc) - timedelta(minutes=(n - i) * 3)).isoformat()
        ev = random.choice(["session_start","payment","overflow_reroute","session_end","price_update"])
        data = {"lot_id": f"lot_{['a','b','c','d'][i % 4]}",
            "session_id": f"{['sess_','txn_','pkg_'][i % 3]}{random.randint(1000,9999)}",
            "amount": round(random.uniform(8, 22), 2), "duration_min": random.randint(15, 180),
            "occupancy_at_entry": round(random.uniform(0.3, 0.95), 2), "event": ev}
        h = hashlib.sha256(f"{i}{prev}{json.dumps(data, sort_keys=True)}{nonce}".encode()).hexdigest()
        sm = {
            "session_start": f"Block #{i}: Car enters {data['lot_id']}. ${data['amount']}/hr. Chain extends.",
            "payment": f"Block #{i}: ${data['amount']} verified on {data['lot_id']}. Sealed.",
            "overflow_reroute": f"Block #{i}: MARL divert to {data['lot_id']}. ${data['amount']} on-ledger.",
            "session_end": f"Block #{i}: {data['duration_min']}min at {data['lot_id']}. Finalized.",
            "price_update": f"Block #{i}: ${data['amount']}/hr at {data['lot_id']}. Oracle-published."
        }
        story = sm.get(ev, f"Block {i} sealed.")
        blocks.append(Block(i, ts, prev, h, data, nonce, True, story))
        prev = h
    return blocks

def simulate_advance_booking():
    random.seed(42)
    steps, cum = [], 0
    stories = [
        "T-7 hours: Eight spots at $9. Early birds claim their perch.",
        "T-6 hours: Twelve now. Price rising to $10. Window closing.",
        "T-5 hours: Seventeen gone. Standard tier, $12.50 average.",
        "T-4 hours: Twenty-one committed. Algorithm upgrades to Peak.",
        "T-3 hours: Twenty-five taken. Only five remain. Critical tier.",
        "T-2 hours: Twenty-eight. $18/hr. Two spots left to fight for.",
        "T-1 hour: Full house at $20. Last reservation booked at dusk."
    ]
    for h in range(6, -1, -1):
        cum += random.randint(2, 6); r = cum / 30
        if r < 0.3: p, s = 9.0, "Off-peak"
        elif r < 0.5: p, s = 10.0, "Standard"
        elif r < 0.7: p, s = 12.5, "Rising"
        elif r < 0.9: p, s = 16.0, "Peak"
        else: p, s = 20.0, "Critical"
        story = stories[6 - h] if (6 - h) < len(stories) else f"T-{h}h: {cum}/30 at ${p:.0f}"
        steps.append(BookingStep(h, round(p, 2), round(max(0, (1 - r) * 100), 1), cum, 30, s, story))
    return steps

def simulate_overflow_marl():
    random.seed(42)
    a, b, c, d, reroute = 0.25, 0.20, 0.15, 0.10, False
    steps = []
    for step in range(15):
        a = min(1, a + 0.06 + random.uniform(-0.02, 0.04))
        b = min(1, b + 0.03 + random.uniform(-0.02, 0.02))
        c = min(1, c + 0.02 + random.uniform(-0.01, 0.02))
        d = min(1, d + 0.01 + random.uniform(-0.01, 0.01))
        oz = None
        if a > 0.90 and not reroute:
            oz, reroute = "Zone A", True
            b, c, d = max(0.05, b + 0.15), max(0.05, c + 0.10), max(0.05, d + 0.05)
            a = 0.75
        if reroute and step < 6:
            story = f"Zone A at {a*100:.1f}% — agents watching the pressure gauge."
        elif reroute and oz:
            story = f"Zone A overflows! MARL redistributes: B({b*100:.0f}%) C({c*100:.0f}%) D({d*100:.0f}%)."
        elif reroute:
            story = f"Post-crisis: A({a*100:.0f}%) B({b*100:.0f}%) C({c*100:.0f}%) D({d*100:.0f}%)."
        else:
            story = f"Quiet: A({a*100:.0f}%) B({b*100:.0f}%) C({c*100:.0f}%) D({d*100:.0f}%)."
        steps.append(MarlZoneStep(step + 1, round(a * 100, 1), round(b * 100, 1),
            round(c * 100, 1), round(d * 100, 1), oz, reroute, round((a+b+c+d)/4*100, 1), story))
    return steps

def simulate_cancellation_chain():
    steps, occ, price = [], 0.50, 10.0
    stories = [
        "Demand building under the surface. Price rising toward $18.",
        "The lot fills. $16/hr. Still below the pain threshold. For now.",
        "82% full. $18. The market is about to test its limits.",
        "PRICE HITS $20 — a cascade tears through the grid. 18% collapse.",
        "Freefall. Occupancy plunges. System scrambles to stabilize.",
        "The wave passes. A new equilibrium forms at 55%. Fragile.",
        "Price resets to $14. Drivers cautiously return.",
        "Recovery steady. 52%. Trust rebuilding one car at a time.",
        "48% at $12. The market remembered how to breathe.",
        "Normal operations. 45%. The spike is now a data point.",
        "43%. $11/hr. Green shoots. System healthy again.",
        "Cycle archived. Elasticity curve recorded. Life resumes."
    ]
    for step in range(12):
        if step < 3:
            occ, price = min(0.95, occ + 0.08), round(14 + step * 2, 2)
            cr, ev = 0.02, "Building demand"
        elif step == 3:
            n = occ * (1 - 0.18)
            steps.append(CancelStep(step, f"T+{step * 4}min", round(occ * 100, 1), 20.0,
                18, int(occ * 100 * 0.18), round(n * 100, 1), "Price spike triggered cancellations",
                stories[step]))
            occ = n; continue
        elif step < 6:
            occ, price = max(0.55, occ * 0.85), round(price * 0.85, 2)
            cr, ev = 0.08, "Cancellation wave cooling"
        else:
            occ, price = max(0.30, occ * 0.95), round(max(8, price * 0.92), 2)
            cr, ev = 0.03, "Market stabilising"
        n = occ * max(0.01, 1 - cr)
        story = stories[step] if step < len(stories) else f"{occ*100:.0f}% at ${price:.0f}"
        steps.append(CancelStep(step, f"T+{step * 4}min", round(occ * 100, 1), price,
            round(cr * 100, 1), int(occ * 100 * cr), round(n * 100, 1), ev, story))
        occ = n
    return steps

def generate_simulation_data():
    return {"rush_hour": [asdict(s) for s in simulate_rush_hour()],
        "blockchain": [asdict(b) for b in simulate_blockchain()],
        "advance_booking": [asdict(b) for b in simulate_advance_booking()],
        "overflow_marl": [asdict(m) for m in simulate_overflow_marl()],
        "cancellation_chain": [asdict(c) for c in simulate_cancellation_chain()],
        "generated_at": datetime.now(timezone.utc).isoformat()}


# ── HTML Template ──

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#080808;--surface:rgba(16,16,20,0.85);--text:#ddd;--text2:#667;--amber:#ffb300;--green:#4caf50;--red:#e53935;--blue:#42a5f5;--purple:#ab47bc;--ease:cubic-bezier(0.25,1,0.5,1)}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;line-height:1.6;overflow:hidden}
body{font-size:14px}
#city-grid{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none}
#scanlines{position:fixed;top:0;left:0;width:100%;height:100%;z-index:1;pointer-events:none;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px)}
#vignette{position:fixed;top:0;left:0;width:100%;height:100%;z-index:1;pointer-events:none;background:radial-gradient(ellipse 70% 60% at 50% 40%,transparent 0%,rgba(0,0,0,0.6) 100%)}

#tower{position:fixed;top:0;left:0;right:0;z-index:20;height:48px;background:rgba(8,8,8,0.92);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,179,0,0.08);display:flex;align-items:center;padding:0 14px;gap:6px;font-family:'JetBrains Mono',monospace;font-size:10px}
#tower .logo{font-family:'Oswald',sans-serif;font-size:14px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:var(--amber);margin-right:2px}
#tower .logo::after{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--amber);margin-left:6px;vertical-align:middle;filter:blur(3px);opacity:.6;animation:tp 1.8s ease-in-out infinite}
@keyframes tp{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:1;transform:scale(1.8)}}
#tower .sep{color:var(--text2);opacity:0.25;font-size:12px;user-select:none}
#tower .metric{display:flex;align-items:center;gap:3px;color:var(--text2)}
#tower .metric .v{color:var(--text);font-weight:700}
#tower .metric .v.a{color:var(--amber)}
#tower .sd{width:5px;height:5px;border-radius:50%;background:var(--green);animation:td 1.4s ease infinite}
@keyframes td{50%{opacity:.2}}
#tower .nav{display:flex;gap:1px;margin-left:auto}
#tower .nav a{font-family:'Oswald',sans-serif;font-size:8px;letter-spacing:1.5px;text-transform:uppercase;text-decoration:none;color:var(--text2);padding:2px 5px;border:1px solid transparent;transition:.2s var(--ease)}
#tower .nav a:hover{color:var(--amber);border-color:rgba(255,179,0,0.15)}

#scroll-world{position:relative;z-index:10;height:100vh;overflow-y:scroll;overflow-x:hidden;scrollbar-width:none}
#scroll-world::-webkit-scrollbar{display:none}

.hero{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 20px 60px;text-align:center;position:relative;z-index:2}
.hero h1{font-family:'Oswald',sans-serif;font-size:clamp(2em,5.5vw,3.6em);font-weight:700;text-transform:uppercase;letter-spacing:6px;line-height:1.15;z-index:2}
.hero h1 .hl{color:var(--amber);display:block}
.hero .tag{z-index:2;font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--text2);letter-spacing:3px;margin-top:6px;text-transform:uppercase}

.chapter{min-height:100vh;display:flex;flex-direction:column;justify-content:center;padding:72px 16px;position:relative;will-change:opacity,filter}
.chapter-inner{max-width:480px;margin:0 auto;width:100%;position:relative;z-index:5}
.chapter-panel{background:var(--surface);border:1px solid rgba(255,179,0,0.06);backdrop-filter:blur(10px);padding:18px;position:relative}
.chapter-panel::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--amber),transparent)}
.ch-panel-head{font-family:'Oswald',sans-serif;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:2.5px;color:var(--amber);margin-bottom:10px;display:flex;align-items:center;gap:6px}
.ch-panel-head::after{content:'';flex:1;height:1px;background:rgba(255,179,0,0.06)}
.ch-icon{font-size:13px;line-height:1;filter:drop-shadow(0 0 3px currentColor)}
.ch-data{position:relative}

.chapter[data-ch="rush"] .chapter-panel::before{background:linear-gradient(90deg,transparent,#ffb300,transparent)}
.chapter[data-ch="book"] .chapter-panel::before{background:linear-gradient(90deg,transparent,#42a5f5,transparent)}
.chapter[data-ch="marl"] .chapter-panel::before{background:linear-gradient(90deg,transparent,#ab47bc,transparent)}
.chapter[data-ch="cancel"] .chapter-panel::before{background:linear-gradient(90deg,transparent,#e53935,transparent)}
.chapter[data-ch="chain"] .chapter-panel::before{background:linear-gradient(90deg,transparent,#4caf50,transparent)}
.chapter[data-ch="rush"] .ch-panel-head{color:#ffb300}
.chapter[data-ch="book"] .ch-panel-head{color:#42a5f5}
.chapter[data-ch="marl"] .ch-panel-head{color:#ab47bc}
.chapter[data-ch="cancel"] .ch-panel-head{color:#e53935}
.chapter[data-ch="chain"] .ch-panel-head{color:#4caf50}
.chapter[data-ch="rush"] .chapter-panel{border-color:rgba(255,179,0,0.1)}
.chapter[data-ch="book"] .chapter-panel{border-color:rgba(66,165,245,0.1)}
.chapter[data-ch="marl"] .chapter-panel{border-color:rgba(171,71,188,0.1)}
.chapter[data-ch="cancel"] .chapter-panel{border-color:rgba(229,57,53,0.1)}
.chapter[data-ch="chain"] .chapter-panel{border-color:rgba(76,175,80,0.1)}

.rh-price{font-family:'Oswald',sans-serif;font-size:1.6em;font-weight:700;color:var(--amber);line-height:1;margin-bottom:3px}
.rh-price .cents{font-size:.4em;color:rgba(255,179,0,0.5);vertical-align:super}
.rh-bar{height:44px;background:rgba(255,255,255,0.02);overflow:hidden;border:1px solid rgba(255,255,255,0.03)}
.rh-fill{height:100%;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.7);background:linear-gradient(90deg,#2e7d32,#558b2f,#f9a825,#ef6c00,#c62828);background-size:200% 100%}
.rh-fill.hz{animation:hz .5s linear infinite}
@keyframes hz{to{background-position:200% 0}}
.rh-step{font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--text2);margin-top:2px;text-align:right}

.bk-price{font-family:'Oswald',sans-serif;font-size:1.4em;font-weight:700;color:var(--amber);margin-bottom:3px}
.bk-price .cents{font-size:.4em;color:rgba(255,179,0,0.5);vertical-align:super}
.bk-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:2px}
.bk-spot{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:9px;min-height:20px}
.bk-spot.free{background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.03)}
.bk-spot.booked.t1{background:rgba(46,125,80,0.3)}
.bk-spot.booked.t2{background:rgba(88,143,47,0.25)}
.bk-spot.booked.t3{background:rgba(249,168,37,0.2)}
.bk-spot.booked.t4{background:rgba(198,40,40,0.25)}

.ml-zone{margin-bottom:3px}
.ml-zone:last-child{margin-bottom:0}
.ml-label{font-family:'Outfit',sans-serif;font-size:8px;font-weight:500;text-transform:uppercase;letter-spacing:1px;color:var(--text2);margin-bottom:2px}
.ml-track{height:24px;background:rgba(255,255,255,0.015);overflow:hidden;border:1px solid rgba(255,255,255,0.03)}
.ml-fill{height:100%;display:flex;align-items:center;justify-content:flex-end;padding-right:4px;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5)}
.ml-fill.over{animation:mp .5s ease 3}
@keyframes mp{50%{opacity:.2}}

.cc-box{display:flex;gap:3px;height:120px;align-items:flex-end}
.cc-col{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}
.cc-col::before{content:attr(data-l);font-family:'Oswald',sans-serif;font-size:9px;color:var(--text2);letter-spacing:1.5px;margin-bottom:2px}
.cc-bar{width:55%;display:flex;align-items:flex-start;justify-content:center;padding-top:3px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.4)}
.cc-col.pk .cc-bar{background:linear-gradient(to top,rgba(255,179,0,0.65),rgba(255,179,0,0.06))}
.cc-col.lost .cc-bar{background:linear-gradient(to top,rgba(229,57,53,0.6),rgba(229,57,53,0.05))}
.cc-col.net .cc-bar{background:linear-gradient(to top,rgba(67,160,71,0.65),rgba(67,160,71,0.06))}
@keyframes sh{0%,100%{translate:0}20%{translate:-3px}40%{translate:3px}60%{translate:-2px}80%{translate:2px}}

.bc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:3px}
.bc-card{background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.03);padding:4px;transition:.2s var(--ease)}
.bc-card.hl{border-color:var(--amber);background:rgba(255,179,0,0.04)}
.bc-card .bc-num{font-family:'Oswald',sans-serif;font-weight:700;font-size:9px;margin-bottom:1px;display:flex;align-items:center;gap:3px}
.bc-card .bc-dot{display:inline-block;width:4px;height:4px;border-radius:50%}
.bc-card .bc-detail{font-size:7px;color:var(--text2);line-height:1.3}
.bc-card .bc-hash{font-family:'JetBrains Mono',monospace;font-size:6px;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.bc-card.genesis{border-color:rgba(67,160,71,0.15);background:rgba(67,160,71,0.03)}
.bc-card .chain-link{font-family:'JetBrains Mono',monospace;font-size:6px;color:rgba(255,179,0,0.25);margin-top:1px;display:block}
.hl-tag{display:inline;float:right;font-size:6px;color:var(--amber)}

.badge{font-family:'Outfit',sans-serif;font-size:7px;font-weight:600;letter-spacing:1px;text-transform:uppercase;padding:2px 5px;border:1px solid rgba(255,255,255,0.03);color:var(--text2);white-space:nowrap;display:inline-block}

.telemetry{position:absolute;bottom:20px;left:50%;translate:-50% 0;z-index:15;max-width:500px;width:calc(100% - 28px);pointer-events:none}
.telemetry-inner{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--text2);background:rgba(0,0,0,0.65);border:1px solid rgba(255,179,0,0.06);padding:7px 10px;backdrop-filter:blur(4px);line-height:1.5;text-align:center}
.telemetry .ts{color:var(--amber);opacity:.45}
.telemetry .msg{color:#999}
.telemetry .cr{color:var(--amber);animation:bl 1s step-end infinite;margin-left:2px}
@keyframes bl{50%{opacity:0}}

.footer{z-index:10;position:relative;text-align:center;padding:20px 12px;font-size:8px;font-family:'JetBrains Mono',monospace;letter-spacing:1px;color:#333}

@media(max-width:640px){
  #tower .nav{display:none}#tower .hm{display:none}
  .chapter{padding:56px 10px}.chapter-panel{padding:12px}
  .rh-bar{height:36px}.rh-fill{font-size:10px}.rh-price{font-size:1.3em}
  .bk-price{font-size:1.2em}.bk-spot{min-height:16px;font-size:7px}
  .cc-box{height:90px}.cc-bar{font-size:8px}
  .bc-grid{grid-template-columns:repeat(2,1fr)}
  .telemetry{width:calc(100% - 16px)}.telemetry-inner{font-size:9px;padding:5px 8px}
}
"""

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pragma — Smart Parking</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Oswald:wght@400;700&family=Outfit:wght@300;500;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lenis@1.1.20/dist/lenis.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<style>__STYLES__</style>
</head>
<body>

<canvas id="c"></canvas>
<div id="scanlines"></div>
<div id="vignette"></div>

<div id="twr">
  <span class="logo">Pragma</span>
  <span class="sep">|</span>
  <span class="metric hm"><span class="v" id="twTm">06:00</span></span>
  <span class="sep hm">|</span>
  <span class="metric"><span class="v a" id="twOc">30%</span><span class="hm"> occ</span></span>
  <span class="sep">|</span>
  <span class="metric hm"><span class="v a">$</span><span class="v a" id="twPr">8</span></span>
  <span class="sep hm">|</span>
  <span class="metric"><span class="v" id="twBk">0x0000</span></span>
  <span class="sep">|</span>
  <span class="metric"><span class="sd"></span><span id="twSt" class="hm">SYSTEM NOMINAL</span></span>
  <span class="nav">
    <a href="#ch-rush">Rush</a>
    <a href="#ch-book">Book</a>
    <a href="#ch-marl">MARL</a>
    <a href="#ch-cancel">Cancel</a>
    <a href="#ch-chain">Chain</a>
  </span>
</div>

<div id="sw">

<div class="hero">
  <h1><span class="hl">Pragma</span><span class="hl">Smart Parking</span></h1>
  <div class="tag">AI · MARL · Blockchain · City-Scale</div>
</div>

<div class="chapter" id="ch-rush" data-ch="rush">
  <div class="chapter-inner">
    <div class="chapter-panel">
      <div class="ch-panel-head"><span class="ch-icon">⏱</span> Rush Hour <span class="badge">sim · 20 frames</span></div>
      <div class="ch-data">
        <div class="rh-price" id="rhPr">$10.00</div>
        <div class="rh-bar"><div class="rh-fill" id="rhFl" style="width:30%"></div></div>
        <div class="rh-step" id="rhSp">Frame 1 / 20</div>
      </div>
    </div>
  </div>
  <div class="telemetry"><div class="telemetry-inner"><span class="ts" id="rhTs">[06:00]</span> <span class="msg" id="rhMg">System boot. Twelve spots taken. Grid online.</span><span class="cr">_</span></div></div>
</div>

<div class="chapter" id="ch-book" data-ch="book">
  <div class="chapter-inner">
    <div class="chapter-panel">
      <div class="ch-panel-head"><span class="ch-icon">📋</span> Advance Booking <span class="badge">sim · 7 hours</span></div>
      <div class="ch-data">
        <div class="bk-price" id="bkPr">$9.00</div>
        <div class="bk-grid" id="bkGr"></div>
      </div>
    </div>
  </div>
  <div class="telemetry"><div class="telemetry-inner"><span class="ts">[T-7]</span> <span class="msg" id="bkMg">Early birds claim their perch. Eight spots at $9.</span><span class="cr">_</span></div></div>
</div>

<div class="chapter" id="ch-marl" data-ch="marl">
  <div class="chapter-inner">
    <div class="chapter-panel">
      <div class="ch-panel-head"><span class="ch-icon">🧠</span> MARL Overflow <span class="badge">sim · 4 zones</span></div>
      <div class="ch-data" id="mz"></div>
    </div>
  </div>
  <div class="telemetry"><div class="telemetry-inner"><span class="ts">[NET]</span> <span class="msg" id="mzMg">Four autonomous agents monitoring the grid.</span><span class="cr">_</span></div></div>
</div>

<div class="chapter" id="ch-cancel" data-ch="cancel">
  <div class="chapter-inner">
    <div class="chapter-panel">
      <div class="ch-panel-head"><span class="ch-icon">⚡</span> Cancellation <span class="badge">sim · 12 frames</span></div>
      <div class="ch-data">
        <div class="cc-box" id="ccBx">
          <div class="cc-col pk" data-l="PEAK"><div class="cc-bar" id="ccPk"></div></div>
          <div class="cc-col lost" data-l="LOST"><div class="cc-bar" id="ccLs"></div></div>
          <div class="cc-col net" data-l="NET"><div class="cc-bar" id="ccNt"></div></div>
        </div>
      </div>
    </div>
  </div>
  <div class="telemetry"><div class="telemetry-inner"><span class="ts">[EVENT]</span> <span class="msg" id="ccMg">Demand building. Price rising.</span><span class="cr">_</span></div></div>
</div>

<div class="chapter" id="ch-chain" data-ch="chain">
  <div class="chapter-inner">
    <div class="chapter-panel">
      <div class="ch-panel-head"><span class="ch-icon">⛓</span> Blockchain <span class="badge">SHA-256 · 12 blocks</span></div>
      <div class="ch-data">
        <div class="bc-grid" id="bcGr"></div>
      </div>
    </div>
  </div>
  <div class="telemetry"><div class="telemetry-inner"><span class="ts">[CHAIN]</span> <span class="msg" id="bcMg">Genesis block sealed. Chain growing.</span><span class="cr">_</span></div></div>
</div>

<div class="footer">Pragma · smart parking · v0.3</div>
</div><!-- /sw -->

<script>
(function() {
  var D = __DATA__;

  // ── Canvas ──
  var cv = document.getElementById('c'), cx = cv.getContext('2d');
  var W, H, nodes = [], parts = [], raf, mode = 'idle', frameOcc = 0.3, sVel = 1, woke = false;

  var COLS = {
    rush: { r: 'rgba(255,179,0,0.035)', g: 'rgba(255,179,0,0.12)', b: [8,8,8], p: '#ffb300' },
    book: { r: 'rgba(66,165,245,0.035)', g: 'rgba(66,165,245,0.1)', b: [8,8,12], p: '#42a5f5' },
    marl: { r: 'rgba(171,71,188,0.035)', g: 'rgba(171,71,188,0.1)', b: [10,8,12], p: '#ab47bc' },
    cancel: { r: 'rgba(229,57,53,0.04)', g: 'rgba(229,57,53,0.12)', b: [12,8,8], p: '#e53935' },
    chain: { r: 'rgba(76,175,80,0.035)', g: 'rgba(76,175,80,0.1)', b: [8,12,8], p: '#4caf50' },
    idle: { r: 'rgba(255,179,0,0.02)', g: 'rgba(255,179,0,0.06)', b: [8,8,8], p: '#ffb300' },
  };

  function rs() { W = cv.width = innerWidth; H = cv.height = innerHeight; mkNodes(); }
  function mkNodes() {
    nodes = [];
    for (var r = 0; r < 4; r++)
      for (var c = 0; c < 6; c++)
        nodes.push({ x: (c + 0.5) / 6 * W, y: (r + 0.5) / 4 * H, occ: 0.3, tOcc: 0.3, glow: 0, tGlow: 0 });
  }
  function mkParts() {
    parts = [];
    for (var i = 0; i < 60; i++)
      parts.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5, s: Math.random() * 1.5 + 0.5, a: Math.random() * 0.4 + 0.15, ph: Math.random() * 6.28 });
  }

  var NCFG = {
    rush: { gl: 1.0 }, book: { gl: 0.7 }, marl: { gl: 0.8 }, cancel: { gl: 1.2 }, chain: { gl: 0.5 }, idle: { gl: 0.3 }
  };

  function setNS(m, oc) {
    var cfg = NCFG[m] || NCFG.idle;
    var th = Math.round(oc * nodes.length);
    for (var i = 0; i < nodes.length; i++) {
      var io = i < th ? oc : oc * 0.4 + 0.1;
      nodes[i].tOcc = Math.min(1, Math.max(0.1, io));
      nodes[i].tGlow = cfg.gl * (0.3 + nodes[i].tOcc * 0.7);
      if (m === 'rush' && oc > 0.85) nodes[i].tGlow *= 1.5;
      if (m === 'cancel' && oc > 0.8) nodes[i].tGlow *= 2;
    }
  }

  function nCol(occ) {
    return occ > 0.85 ? '#ff5722' : occ > 0.6 ? '#ffb300' : occ > 0.35 ? '#4caf50' : '#42a5f5';
  }
  function streamColor(m) {
    return m === 'rush' ? '255,179,0' : m === 'book' ? '66,165,245' : m === 'marl' ? '171,71,188' : m === 'cancel' ? '229,57,53' : m === 'chain' ? '76,175,80' : '255,179,0';
  }

  function dr(t) {
    var c = COLS[mode] || COLS.idle;

    cx.fillStyle = 'rgb(' + c.b.join(',') + ')';
    cx.fillRect(0, 0, W, H);

    cx.strokeStyle = c.r;
    cx.lineWidth = 0.5;
    for (var ri = 0; ri < 5; ri++) { var y = (ri + 0.5) / 5 * H; cx.beginPath(); cx.moveTo(0, y); cx.lineTo(W, y); cx.stroke(); }
    for (var ci = 0; ci < 7; ci++) { var x = (ci + 0.5) / 7 * W; cx.beginPath(); cx.moveTo(x, 0); cx.lineTo(x, H); cx.stroke(); }

    // Data streams between occupied nodes (clean O(n²) but n=24, typically <10 active)
    var sc = streamColor(mode);
    for (var si = 0; si < nodes.length; si++) {
      for (var sj = si + 1; sj < nodes.length; sj++) {
        var na = nodes[si], nb = nodes[sj];
        if (na.occ < 0.35 || nb.occ < 0.35) continue;
        var dx = nb.x - na.x, dy = nb.y - na.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > Math.max(W, H) * 0.3) continue;
        var sa = 0.07 * (na.occ + nb.occ) * (0.5 + 0.5 * Math.sin(t * 0.0015 + si * 0.7 + sj));
        cx.strokeStyle = 'rgba(' + sc + ',' + sa + ')';
        cx.lineWidth = 0.4 + na.occ * 0.6;
        cx.beginPath(); cx.moveTo(na.x, na.y); cx.lineTo(nb.x, nb.y); cx.stroke();
        var pulse = (t * 0.0007 + si * 0.31 + sj * 0.17) % 1;
        var px = na.x + dx * pulse, py = na.y + dy * pulse;
        cx.fillStyle = 'rgba(255,255,255,0.6)';
        cx.shadowColor = 'rgba(255,255,255,0.25)'; cx.shadowBlur = 5;
        cx.beginPath(); cx.arc(px, py, 1.8, 0, 6.28); cx.fill();
        cx.shadowBlur = 0;
      }
    }

    // Nodes
    for (var ni = 0; ni < nodes.length; ni++) {
      var n = nodes[ni];
      n.occ += (n.tOcc - n.occ) * 0.06;
      n.glow += (n.tGlow - n.glow) * 0.06;
      var nc = nCol(n.occ);
      var r2 = 3 + n.glow * 8;
      var gd = cx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r2);
      gd.addColorStop(0, 'rgba(255,255,255,0.35)');
      gd.addColorStop(0.3, nc);
      gd.addColorStop(1, 'transparent');
      cx.fillStyle = gd;
      cx.beginPath(); cx.arc(n.x, n.y, r2, 0, 6.28); cx.fill();
      cx.fillStyle = nc;
      cx.beginPath(); cx.arc(n.x, n.y, 2, 0, 6.28); cx.fill();
    }

    // Pulse rings for rush
    if (mode === 'rush' && frameOcc > 0.8) {
      cx.strokeStyle = 'rgba(255,179,0,0.06)';
      cx.lineWidth = 0.5;
      var pr = 50 + 30 * Math.sin(t * 0.0025);
      for (var pi = 0; pi < nodes.length; pi++) {
        if (nodes[pi].occ > 0.85) { cx.beginPath(); cx.arc(nodes[pi].x, nodes[pi].y, pr, 0, 6.28); cx.stroke(); }
      }
    }

    // Particles with node attraction
    var spd = (mode === 'rush' ? 0.9 : mode === 'marl' ? 0.7 : mode === 'cancel' ? 1.0 : 0.35) * sVel;
    for (var pi = 0; pi < parts.length; pi++) {
      var p = parts[pi];
      // Find nearest occupied node for attraction
      var nn = -1, nd = Infinity;
      for (var pj = 0; pj < nodes.length; pj++) {
        if (nodes[pj].occ < 0.25) continue;
        var dx = nodes[pj].x - p.x, dy = nodes[pj].y - p.y;
        var d = dx * dx + dy * dy;
        if (d < nd) { nd = d; nn = pj; }
      }
      if (nn >= 0 && nd < (W * 0.3) * (W * 0.3)) {
        var dx = nodes[nn].x - p.x, dy = nodes[nn].y - p.y;
        var pull = 0.00015 * nodes[nn].occ;
        p.vx += dx * pull; p.vy += dy * pull;
      }
      p.vx *= 0.997; p.vy *= 0.997;
      var mv = 1.0 * spd;
      var sp = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
      if (sp > mv) { p.vx = (p.vx / sp) * mv; p.vy = (p.vy / sp) * mv; }
      p.x += p.vx + Math.sin(t * 0.001 + p.ph) * 0.1;
      p.y += p.vy + Math.cos(t * 0.001 + p.ph) * 0.1;
      if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
      if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
      cx.fillStyle = c.p;
      cx.globalAlpha = p.a * (0.5 + 0.5 * Math.sin(t * 0.002 + p.ph));
      cx.beginPath(); cx.arc(p.x, p.y, p.s, 0, 6.28); cx.fill();
      cx.globalAlpha = 1;
    }

    raf = requestAnimationFrame(dr);
  }

  rs(); mkParts(); raf = requestAnimationFrame(dr);
  addEventListener('resize', rs);

  // ── Helpers ──
  function fmtP(p) {
    var d = Math.floor(p), c = Math.round((p - d) * 100);
    return '$<span class="curr">' + d + '</span><span class="cents">.' + (c < 10 ? '0' : '') + c + '</span>';
  }

  var _twTL = null, _twTO = null;
  function tw(el, msg) {
    if (_twTO) { clearTimeout(_twTO); _twTO = null; }
    el.textContent = '';
    var i = 0, len = msg.length;
    (function go() {
      if (i >= len) return;
      el.textContent += msg[i++];
      _twTO = setTimeout(go, 16 + Math.random() * 12);
    })();
  }
  function setTel(id, ts, msg) {
    var el = document.getElementById(id);
    if (el._last === msg) return;
    el._last = msg;
    if (id === 'rhMg') document.getElementById('rhTs').textContent = '[' + ts + ']';
    if (_twTO) { clearTimeout(_twTO); _twTO = null; }
    if (_twTL) _twTL.kill();
    _twTL = gsap.timeline();
    _twTL.to(el, { opacity: 0, y: -3, duration: 0.06, ease: 'power2.in' })
      .call(function() { tw(el, msg); })
      .to(el, { opacity: 1, y: 0, duration: 0.12, ease: 'power2.out' }, 0.04);
  }

  // ── Dashboard auto-player ──
  (function() {
    var rh = D.rush_hour, bc = D.blockchain, st = 0;
    function tk() {
      var s = rh[st]; if (!s) return;
      document.getElementById('twTm').textContent = s.time_label;
      document.getElementById('twOc').textContent = s.occupancy_pct + '%';
      document.getElementById('twPr').textContent = '$' + Math.floor(s.price);
      document.getElementById('twBk').textContent = bc[st % bc.length].hash.substring(0, 8) + '…';
      document.getElementById('twSt').textContent = s.overflow_warning ? 'OVERFLOW' : s.is_full ? 'FULL' : 'NOMINAL';
      document.getElementById('twSt').style.color = s.overflow_warning ? 'var(--red)' : s.is_full ? 'var(--amber)' : '';
      st = (st + 1) % rh.length;
    }
    tk(); setInterval(tk, 1400);
  })();

  // ── Rush Hour ──
  var _rRd = false, _rLP = 0;
  function rRush(idx) {
    var s = D.rush_hour[idx];
    var pEl = document.getElementById('rhPr'), fEl = document.getElementById('rhFl');
    if (!_rRd) {
      pEl.innerHTML = fmtP(s.price);
      fEl.style.width = s.occupancy_pct + '%'; fEl.textContent = s.occupancy_pct + '%';
      _rRd = true; _rLP = s.price;
    } else {
      if (Math.floor(s.price) !== Math.floor(_rLP)) {
        var o = { v: _rLP };
        gsap.to(o, {
          v: Math.floor(s.price), duration: 0.5, ease: 'power2.out',
          onUpdate: function() { pEl.innerHTML = fmtP(o.v); },
          onComplete: function() { pEl.innerHTML = fmtP(s.price); },
        });
      }
      _rLP = s.price;
      gsap.to(fEl, {
        width: s.occupancy_pct + '%', duration: 0.6, ease: 'power4.out',
        onUpdate: function() { fEl.textContent = Math.round(gsap.getProperty(fEl, 'width')) + '%'; },
        onComplete: function() {
          fEl.textContent = s.occupancy_pct + '%';
          fEl.className = 'rh-fill' + (s.occupancy_pct > 92 ? ' hz' : '');
          var bg = s.occupancy_pct > 92 ? 'linear-gradient(90deg,#ff9800,#e91e63,#d50000)' : s.occupancy_pct > 80 ? 'linear-gradient(90deg,#4caf50,#8bc34a,#ffeb3b,#ff9800)' : 'linear-gradient(90deg,#2e7d32,#558b2f,#f9a825)';
          fEl.style.background = bg; fEl.style.backgroundSize = '200% 100%';
        },
      });
    }
    document.getElementById('rhSp').textContent = 'Frame ' + (idx + 1) + ' / ' + D.rush_hour.length;
    setTel('rhMg', s.time_label, s.story);
    mode = 'rush'; frameOcc = s.occupancy_pct / 100; setNS('rush', frameOcc);
  }

  // ── Booking ──
  var _bRd = false, _bLP = 0;
  function rBook(idx) {
    var s = D.advance_booking[idx], pEl = document.getElementById('bkPr');
    if (!_bRd) { pEl.innerHTML = fmtP(s.price); _bRd = true; _bLP = s.price; }
    else {
      if (Math.floor(s.price) !== Math.floor(_bLP)) {
        var o = { v: _bLP };
        gsap.to(o, {
          v: Math.floor(s.price), duration: 0.5, ease: 'power2.out',
          onUpdate: function() { pEl.innerHTML = fmtP(o.v); },
          onComplete: function() { pEl.innerHTML = fmtP(s.price); },
        });
      }
      _bLP = s.price;
    }
    var grid = document.getElementById('bkGr'), h = '';
    for (var i = 0; i < 30; i++) {
      var bk = i < s.cumulative_bookings;
      var t = s.price < 10 ? 't1' : s.price < 13 ? 't2' : s.price < 17 ? 't3' : 't4';
      h += '<div class="bk-spot ' + (bk ? 'booked ' + t : 'free') + '">' + (bk ? '🚗' : '') + '</div>';
    }
    grid.innerHTML = h;
    gsap.fromTo(grid.querySelectorAll('.bk-spot.booked'), { scale: 0 }, { scale: 1, duration: 0.2, stagger: 0.01, ease: 'back.out(2)' });
    setTel('bkMg', 'T-' + s.hour, s.story);
    mode = 'book'; frameOcc = s.cumulative_bookings / 30; setNS('book', frameOcc);
  }

  // ── MARL ──
  var _mRd = false, _mLO = null;
  function rMarl(idx) {
    var s = D.overflow_marl[idx], oz = s.overflow_zone;
    var z = [
      { l: 'Zone A', p: s.zone_a_occ, c: '#667eea' },
      { l: 'Zone B', p: s.zone_b_occ, c: '#4caf50' },
      { l: 'Zone C', p: s.zone_c_occ, c: '#ff9800' },
      { l: 'Zone D', p: s.zone_d_occ, c: '#e91e63' }
    ];
    var h = '';
    z.forEach(function(v) {
      var ov = oz && v.l === oz;
      h += '<div class="ml-zone"><div class="ml-label">' + v.l + '</div><div class="ml-track"><div class="ml-fill' + (ov ? ' over' : '') + '" style="width:' + v.p + '%;background:' + v.c + '"></div></div></div>';
    });
    document.getElementById('mz').innerHTML = h;
    if (!_mRd) { _mRd = true; _mLO = oz; }
    else if (oz && oz !== _mLO) {
      var panel = document.querySelector('#ch-marl .chapter-panel');
      gsap.fromTo(panel, { borderColor: 'var(--red)', boxShadow: '0 0 24px rgba(229,57,53,0.25)' },
        { borderColor: '', boxShadow: '', duration: 1, ease: 'power2.out' });
    }
    _mLO = oz;
    setTel('mzMg', 'NET', s.story);
    mode = 'marl'; frameOcc = (s.zone_a_occ + s.zone_b_occ + s.zone_c_occ + s.zone_d_occ) / 400;
    setNS('marl', frameOcc);
  }

  // ── Cancel ──
  var _cRd = false;
  function rCancel(idx) {
    var s = D.cancellation_chain[idx], mH = 90;
    var pH = s.occupancy_before_pct / 100 * mH;
    var cH = Math.max(0, (s.occupancy_before_pct - s.net_occupancy_pct) / 100 * mH);
    var nH = s.net_occupancy_pct / 100 * mH;
    var spike = s.occupancy_before_pct - s.net_occupancy_pct;
    var eP = document.getElementById('ccPk'), eL = document.getElementById('ccLs'), eN = document.getElementById('ccNt');
    if (!_cRd) { eP.style.height = pH + 'px'; eL.style.height = cH + 'px'; eN.style.height = nH + 'px'; _cRd = true; }
    else {
      gsap.to(eP, { height: pH + 'px', duration: 0.5, ease: 'power3.out' });
      gsap.to(eL, { height: cH + 'px', duration: 0.5, ease: 'power3.out', delay: 0.06 });
      gsap.to(eN, { height: nH + 'px', duration: 0.5, ease: 'power3.out', delay: 0.12 });
    }
    if (spike > 15 && idx > 2) {
      var box = document.getElementById('ccBx');
      box.style.animation = 'none'; void box.offsetHeight; box.style.animation = 'sh .35s ease';
    }
    setTel('ccMg', 'EVENT', s.story);
    mode = 'cancel'; frameOcc = s.net_occupancy_pct / 100; setNS('cancel', frameOcc);
  }

  // ── Blockchain ──
  var _chRd = false;
  function rChain(idx) {
    var blocks = D.blockchain, grid = document.getElementById('bcGr'), h = '';
    for (var i = 0; i < blocks.length; i++) {
      var b = blocks[i];
      var cl = (i === 0 ? 'bc-card genesis' : 'bc-card') + (i === idx ? ' hl' : '');
      var dot = i === 0 ? '#4caf50' : '#ab47bc';
      var pl = i === 0 ? '<span class="chain-link">◆ Genesis block</span>' : '<span class="chain-link">↑ ' + blocks[i - 1].hash.substring(0, 6) + '…</span>';
      var ei = b.data.event === 'session_start' ? '🚗' : b.data.event === 'payment' ? '💰' : b.data.event === 'session_end' ? '✅' : b.data.event === 'overflow_reroute' ? '🔄' : '📊';
      var ht = i === idx ? '<span class="hl-tag">▶</span>' : '';
      h += '<div class="' + cl + '"><div class="bc-num"><span class="bc-dot" style="background:' + dot + '"></span>#' + b.index + ht + ' <span style="color:#556;font-weight:400;font-size:8px;margin-left:auto">' + b.data.duration_min + 'm</span></div><div class="bc-detail">' + ei + ' ' + b.data.event.replace(/_/g, ' ') + ' · <strong>$' + b.data.amount + '</strong></div><div class="bc-hash">' + b.hash.substring(0, 12) + '…</div>' + pl + '</div>';
    }
    grid.innerHTML = h;
    if (!_chRd) _chRd = true;
    setTel('bcMg', 'CHAIN', blocks[idx].story);
    mode = 'chain'; frameOcc = 0.5 + (idx / blocks.length) * 0.4; setNS('chain', frameOcc);
  }

  // ── Chapters ──
  var chapters = [
    { el: document.getElementById('ch-rush'), data: D.rush_hour, fn: rRush, cur: -1 },
    { el: document.getElementById('ch-book'), data: D.advance_booking, fn: rBook, cur: -1 },
    { el: document.getElementById('ch-marl'), data: D.overflow_marl, fn: rMarl, cur: -1 },
    { el: document.getElementById('ch-cancel'), data: D.cancellation_chain, fn: rCancel, cur: -1 },
    { el: document.getElementById('ch-chain'), data: D.blockchain, fn: rChain, cur: -1 }
  ];

  function upd() {
    var vh = innerHeight;
    chapters.forEach(function(ch) {
      var r = ch.el.getBoundingClientRect();
      // progress: 0 when chapter bottom enters viewport, 1 when chapter top exits
      var entry = vh - r.top - ch.el.offsetHeight;
      var total = vh + ch.el.offsetHeight;
      var p = Math.max(0, Math.min(1, entry / total));

      var op = p < 0.1 ? p / 0.1 : p > 0.85 ? Math.max(0, (1 - p) / 0.15) : 1;
      ch.el.style.opacity = op;
      ch.el.style.filter = 'blur(' + (3 * (1 - op)).toFixed(1) + 'px)';

      var frame = Math.min(ch.data.length - 1, Math.max(0, Math.floor(p * ch.data.length)));
      if (frame !== ch.cur) { ch.cur = frame; ch.fn(frame); }
    });
  }

  // ── Lenis ──
  var lenis = new Lenis({ lerp: 0.085, duration: 1.4, easing: function(t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); } });
  lenis.on('scroll', function(e) {
    sVel = Math.min(3, Math.abs(e.velocity) * 0.04 + 0.3);
    if (!woke && e.velocity > 0.5) {
      woke = true;
      for (var wi = 0; wi < nodes.length; wi++) (function(i) { setTimeout(function() { nodes[i].tGlow = 0.3; }, i * 50); })(wi);
    }
    upd();
  });
  gsap.ticker.add(function(t) { lenis.raf(t * 1000); });
  gsap.ticker.lagSmoothing(0);

  // ── Entrance ──
  gsap.timeline({ defaults: { ease: 'power3.out' } })
    .from('.hero h1 .hl', { opacity: 0, y: 20, duration: 0.5, stagger: 0.1 }, 0)
    .from('.hero .tag', { opacity: 0, y: 8, duration: 0.35 }, 0.4)
    .from('#twr', { opacity: 0, y: -16, duration: 0.35 }, 0.25)
    .from('.chapter', { opacity: 0, duration: 0.01 }, 0.7);

  upd();
})();
</script>
</body>
</html>"""


def main():
    print("=" * 60)
    print("  Pragma Smart Parking — The Living City")
    print("=" * 60)
    print()

    data = generate_simulation_data()
    for k, v in data.items():
        if isinstance(v, list): print(f"  {k}: {len(v)} frames")

    html = (_HTML.replace("__STYLES__", _CSS.strip()).replace("__DATA__", json.dumps(data)))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"showcase_{ts}.html"
    path.write_text(html, encoding="utf-8")

    print(f"\n  => {path} ({len(html) // 1024} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
