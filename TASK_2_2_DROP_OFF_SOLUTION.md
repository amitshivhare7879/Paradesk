# Task 2.2: Comprehensive Strategy to Eliminate Registration Drop-Off & Ghost Tables
**Department:** Technicals Department, Paradox'27 — IIT Madras  
**Document Type:** Ground Operations & Capacity Engineering Blueprint  
**Tooling Core:** Paradesk Operations Engine  

---

## 1. Root Cause Diagnosis: Why Participants Drop Off

| # | Root Cause Category | Psychology / Ground Reality | Failure Point |
|---|---|---|---|
| **1** | **Impulse Registration ("G-Form Illusion")** | Free registration links feel like zero-stake forms. Students click to register on a whim without checking course deadlines, quiz schedules, or internal team bandwidth. | Over-inflated initial numbers with 30-40% ghost intent. |
| **2** | **Squad Attrition & Solo Intimidation** | When 1 or 2 teammates drop out due to hostel quizzes or lab viva, the remaining 1-2 students feel intimidated and back out entirely rather than competing shorthanded. Solo registrants feel the scope is unmanageable alone. | Cascade withdrawals: 1 member backing out kills a 4-person table. |
| **3** | **Imposter Syndrome & Fear of Exposure** | As kickoff approaches, fear of failure, technical inadequacy, or getting stuck on environment setups (CUDA, Docker, Node mismatches) causes participants to self-select out. | Sudden silent no-shows right when problem statements drop. |
| **4** | **Logistical Ambiguity** | When participants don't know their exact seating, LAN drop availability, power setup, or schedule, they prioritize informal campus plans over the event. | Lack of priority weighting compared to campus alternatives. |
| **5** | **The "Ghost Table" Ground Bottleneck** | Coordinators on the ground wait 30-45 minutes hoping late teams arrive. Desks, power strips, and LAN drops remain locked while eager walk-ins and waitlisted students in the lobby give up and leave. | 25% venue capacity wasted; frustrated waitlists. |

---

## 2. The End-to-End Recovery Pipeline

```
┌─────────────────┐      ┌──────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ T-14 to T-7 Days│      │      T-5 to T-3 Days     │      │     T-48 to T-12 Hours  │      │   Event Day (0 to +15m) │
│  REGISTRATION   │ ───► │ SQUAD-RESCUE & WARM-UP   │ ───► │ 48-HOUR HARD RSVP GATE  │ ───► │ PARADESK GROUND ENGINE  │
│  & COMMITMENT   │      │ (Skill Match & Docker)   │      │ (Dynamic Slot Release)  │      │ (Sweeper & Standby Fill)│
└─────────────────┘      └──────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

---

## 3. Pillar 1: Squad-Rescue & Frictionless Matchmaking (T-7 to T-3 Days)

### The Mechanism
Instead of passive broadcast reminders, the Technicals Department dispatches an interactive **"Team Health Ping"** at T-5 Days:
1. **The 1-Click Status Query:** A lightweight prompt asks team leads:
   - *Option A:* "Full Squad Intact (All 4 Confirmed)"
   - *Option B:* "Partial Squad (1 or 2 Members Missing / Need Reinforcements)"
   - *Option C:* "Solo Looking to Join / Merge"
2. **Automated Matchmaking Engine:**
   - Shorthanded squads (2-person or 3-person) are pooled with solos and orphaned duos based on complementary skill tags (e.g. *Frontend/Design* + *Backend/ML*).
   - In-app/WhatsApp bridging connects them into a unified 4-person squad before event day.
3. **Psychological Impact:**
   - Eradicates the single biggest reason for team drop-outs: *"My friend backed out, so I won't come either."*

---

## 4. Pillar 2: Pre-Event Warm-Up & Imposter Syndrome Relief (T-5 to T-2 Days)

### The Mechanism
Panic drop-offs happen because hackathons feel like an unpredictable black box. We eliminate uncertainty by publishing a **Pre-Configured Starter Kit**:
1. **One-Command Environment Setup:**
   - Provide a tested `docker-compose.yml` or GitHub template repository containing boilerplates for Fastify/FastAPI, Vite, and SQLite/PostgreSQL.
   - Eliminates the painful 2-hour "environment debugging" phase that causes teams to rage-quit before coding starts.
2. **Mock Problem Statement & Evaluation Rubric:**
   - Release a "Warm-Up Challenge" (structurally identical to the judging rubric, but different domain) 3 days prior.
   - Show transparent scoring dimensions: *Working Prototype (40%)*, *System Resilience (25%)*, *UI/UX Usability (20%)*, *Pitch (15%)*.
3. **Dataset & API Stubs:**
   - Provide sanitized sample datasets and mock endpoints early so teams can practice data loading and schema ingestion.
4. **Psychological Impact:**
   - Converts abstract fear into structured preparation. Students arrive with pre-tested laptops, knowing they won't get stuck on trivial config issues.

---

## 5. Pillar 3: Two-Phase Confirmation Gate (T-48 Hours to T-12 Hours)

### The Mechanism
1. **The 48-Hour Hard RSVP Deadline:**
   - Every registered team must click a unique, 1-click token link (`https://paradesk.paradox.iitm/rsvp/{token}`) at exactly T-48 Hours.
   - Teams that confirm move to `CONFIRMED_RSVP`.
   - Teams that do not confirm by T-24 Hours receive a 6-hour final warning countdown.
2. **Dynamic Slot Release Pipeline:**
   - At T-18 Hours, unconfirmed slots are **automatically revoked** and transferred to the top of the Waitlist pool.
   - Newly promoted waitlisted teams are sent an automated 6-hour acceptance window.
3. **Psychological Impact:**
   - Forces uncommitted impulse registrants to release their spots without social friction.
   - Eliminates the "Day-of-Event Surprise" where organizers expect 40 teams and only 25 show up.

---

## 6. Pillar 4: Zero-Wait Ground Recovery & Proximity Architecture (Kickoff to T+15 Min)

Leveraging the unique physical layout of IIT Madras where the vast majority of hackathon participants reside inside campus hostels:

```
                                  PARADESK CAPACITY ALLOCATION
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
       TIER 1: VENUE LOBBY STANDBY                                   TIER 2: HOSTEL BROADCAST
       • Sitting physically in CRC lobby                             • Resting in campus hostels (10m away)
       • Instant 1-click admittance                                  • 1-minute automated broadcast trigger
       • 0-minute latency to desk                                    • 8-10 minute cycling transit window
```

### 1. Tier-1: Venue Lobby Standby Queue
- Top 5-10 waitlisted squads are invited with a guaranteed perk: *"Be physically present in the CRC venue lobby at kickoff. You are guaranteed priority admittance into any vacated desk."*
- Organizers provide power stations and Wi-Fi in the lobby so waitlisted teams can warm up.

### 2. Tier-2: Campus Hostel Flash Broadcast
- IIT Madras campus hostels (Tapti, Pampa, Mandak, Ganga, Sharav, etc.) are an 8–10 minute bicycle ride or walk from the Central Research Complex (CRC).
- When desks remain open after Tier-1 admittance, Paradesk dispatches a high-priority flash broadcast to `HOSTEL_BROADCAST` candidates with a 12-minute reporting deadline.

### 3. The 15-Minute Automated No-Show Sweep
- **Protocol:** Exactly 15 minutes post-kickoff, the Senior Core hits **"Sweep No-Shows (15-Min Cutoff)"** in Paradesk (`POST /sweep-noshows`).
- All silent non-checked-in teams are revoked instantly to `NO_SHOW`.
- Desks are freed atomically and transferred to the ready Lobby Standby students.
- **Result:** Zero idle "frozen" tables, 100% capacity utilization.

### 4. In-Hall "Squad-Rescue" at the Incident Desk
- If an arriving team reports: *"Only 2 of us could make it, our other 2 dropped out,"* the ground coordinator uses Paradesk's **Squad-Rescue Merger** (`POST /merge-squads`).
- Another partial team of 2 is paired with them at a single table (`DESK-01`), immediately liberating `DESK-02` back to the standby queue.

---

## 7. Metrics & Telemetry: How We Track and Measure Success

The Technicals Department tracks the following telemetry stream inside Paradesk:

```
[Impulse Funnel] ──► [Rescue Conversion] ──► [RSVP Retention] ──► [Capacity Recovery Index]
```

### Core Metrics Dashboard

| Metric | Definition | Benchmark / Target |
|---|---|---|
| **Registration Attrition Rate (RAR)** | `(Total Registered - Confirmed RSVPs) / Total Registered` | Baseline: 35% ➔ **Target: < 12%** |
| **Squad-Rescue Recovery Rate (SRRR)** | `(Consolidated Partial Teams) / (Total Partial Incomplete Reports)` | Target: **> 75%** of broken teams salvaged |
| **Venue Desk Utilization %** | `(Occupied Desks at Kickoff + 30m) / Total Venue Capacity` | Baseline: 68% ➔ **Target: > 96%** |
| **Frozen Table Latency (FTL)** | Time elapsed between kickoff and desk reallocation to standby | Baseline: 45+ mins ➔ **Target: ≤ 15 mins** |
| **Waitlist Admittance Velocity (WAV)** | Average minutes to seat a lobby standby team once a desk is swept | Target: **< 90 seconds** |
| **Capacity Recovery Index (CRI)** | Total desks reclaimed via No-Show Sweeper + Squad Mergers | Target: **100% of ghost desks reassigned** |

### Data Points Tracked in DB
1. **Response Time to RSVP Ping (hours):** Identifies low-confidence teams early.
2. **Squad Incompleteness Ratio:** Percentage of teams arriving with `< original_team_size`.
3. **Hostel Proximity Transit Latency:** Real measured time between hostel notification and venue check-in.
4. **Audit Trail Logs:** Every single desk transition, merge, and sweep timestamped to the second.

---

## 8. Operational Cadence & RACI Matrix

| Timeline | Action Item | Department Owner | Engine / Tool |
|---|---|---|---|
| **T-7 Days** | Registration Closes & Commitment Token Dispatch | Registrations Lead | Automated Mailer / DB |
| **T-5 Days** | Dispatch "Team Health & Squad-Rescue" Form | Operations Lead | Matchmaking Script |
| **T-3 Days** | Release Starter Kit (Docker, Mock PS, Schema) | Technicals Lead | GitHub / Discord |
| **T-48 Hours** | 48h Hard RSVP Window Opens | Ground Coordinator | Paradesk Token Gate |
| **T-18 Hours** | Sweep Unconfirmed RSVPs & Promote Waitlist | Operations Lead | Paradesk Dynamic Release |
| **T-1 Hour** | Prime CRC-North/South LAN Drops & Power Banks | Facilities Lead | Paradesk Hall Grid Map |
| **Kickoff (T=0)** | Ground Check-in Starts (1-click atomic desk bind) | Desk Volunteers | `POST /checkin/{team_id}` |
| **T+15 Mins** | Trigger 15-Minute Hard Sweep Protocol | Senior Core / Lead | `POST /sweep-noshows` |
| **T+16 Mins** | Admit Lobby Standby & Dispatch Hostel Broadcast | Standby Desk Lead | `POST /admit-standby/{id}` |
| **T+30 Mins** | Lock Live Evaluator Roster for Contest Judges | Senior Core | `/judges-roster` |

---

## 9. Conclusion: The Paradesk Advantage

By combining **psychological de-risking** (warm-up kits, squad matchmaking) before the event with **automated algorithmic desk reclamation** (Paradesk) on ground, the Technicals Department replaces uncertainty and wishful waiting with deterministic capacity recovery. 

No desk is left frozen, no solo student is left behind, and campus enthusiasm is maximized.

