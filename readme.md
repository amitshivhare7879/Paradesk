# Paradesk Core Engine — Multi-Event Ground Execution & Capacity-Recovery Portal
**Engineered for Technical Hackathons & Coding Battles at IIT Madras (Paradox '27)**

---

## 1. Overview & Operational Problem Solved

During technical hackathons and coding competitions at IIT Madras (held across the CRC complex), organizers face two acute bottlenecks:
1. **The Registration Drop-Off & "Frozen Table" Bottleneck:** 20% to 30% of registered teams fail to show up on the day of the event. Organizers hesitate to give away empty desks wondering if teams are running late, keeping desks, LAN drops, and venue capacity "frozen" while motivated waitlisted students wait outside.
2. **Disconnected Tools:** Raw Google Form registrations are disconnected from physical table allocations, problem statements, scoring rubrics, and the live leaderboard.

**Paradesk** acts as the single operational bridge between raw Google Form registrations and live ground execution. It automates First-Come-First-Served (FCFS) desk allocations, runs an immediate Top-10 Standby queue in the lobby, enables 1-click 15-minute table reclamation, delivers digital boarding passes with problem statements and marking rubrics, and runs a live leaderboard with an automated 2-hour freeze window.

---

## 2. Technical Architecture & Clean White UI

- **Backend:** Python 3.10+ with **FastAPI**
- **Database:** **SQLite3** with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), foreign keys enabled, and automatic seed generation.
- **Frontend:** Server-rendered **Jinja2 Templates** styled with **Tailwind CSS** + **Font Awesome**.
- **Design Aesthetic:** Clean, distraction-free **white & slate palette** (`bg-white`, `bg-slate-50`, `border-slate-200`, `text-slate-900`) with emerald, amber, and rose status badges. **Strictly no distracting blue gradients.**
- **Deployment:** Fully self-contained, runnable with `uvicorn app:app --reload`.

---

## 3. Database Schema

### `events`
| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Auto-incrementing identifier |
| `name` | `TEXT` | e.g. "HackParadox 2027", "AlgoStrike Coding Battle" |
| `slug` | `TEXT UNIQUE` | URL-safe slug (e.g. `hackparadox-2027`) |
| `max_teams` | `INTEGER` | Table/team capacity (e.g. 30 or 50) |
| `max_members_per_team` | `INTEGER` | Team size limit (default 4) |
| `venue_name` | `TEXT` | Campus venue (e.g. "CRC Complex Hall 101") |
| `event_start` | `DATETIME` | Scheduled kickoff timestamp |
| `problem_statement_url` | `TEXT` | URL to problem statement PDF |
| `problem_statement_text` | `TEXT` | Problem abstract/description |
| `rubric_json` | `TEXT` | Evaluation criteria, weightage, and max scores in JSON |
| `freeze_hours_before_end` | `INTEGER` | Duration of leaderboard lock window (default 2 hrs) |
| `is_leaderboard_frozen` | `INTEGER` | 1 if public leaderboard is locked, 0 if live |

### `desks`
| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Auto-incrementing table ID |
| `event_id` | `INTEGER` | Foreign key referencing `events(id)` ON DELETE CASCADE |
| `desk_code` | `TEXT` | Physical table label (e.g. `CRC-T01`, `CRC-T02`) |
| `is_occupied` | `INTEGER` | 1 if occupied/allocated, 0 if vacant |
| `assigned_team_id` | `INTEGER` | References `teams(id)` |

### `teams`
| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Auto-incrementing team ID |
| `event_id` | `INTEGER` | Foreign key referencing `events(id)` ON DELETE CASCADE |
| `team_name` | `TEXT` | Unique team name |
| `lead_name` | `TEXT` | Team leader's full name |
| `lead_email` | `TEXT` | Leader's email address |
| `lead_phone` | `TEXT` | Contact phone number |
| `member_count` | `INTEGER` | Active member count (e.g. 1-4) |
| `registration_timestamp`| `DATETIME`| Registration timestamp used for FCFS sequencing |
| `queue_position` | `INTEGER` | Overall registration queue rank |
| `status` | `TEXT` | `ALLOCATED`, `STANDBY_TOP10`, `WAITLISTED`, `CHECKED_IN`, `NO_SHOW` |
| `unique_checkin_token` | `TEXT UNIQUE` | 6-char alphanumeric code (e.g. `PX-A7K92B`) |
| `assigned_desk_id` | `INTEGER` | References `desks(id)` |
| `checkin_timestamp` | `DATETIME` | Recorded on physical check-in |
| `score_innovation` | `REAL` | Score (0-40) |
| `score_technical` | `REAL` | Score (0-35) |
| `score_presentation` | `REAL` | Score (0-25) |
| `total_score` | `REAL` | Sum of all evaluation categories (0-100) |

### `audit_logs`
Chronological operational stream capturing event creations, CSV imports, check-ins, no-show table reclamations, standby promotions, and judge scoring actions.

---

## 4. Key Workflows & Features

```
[Raw G-Form CSV] 
       │
       ▼ (Sort by Timestamp: FCFS)
 ┌───────────────────────────────────────────────────────────────┐
 │ Ranks 1 to max_teams         ──► ALLOCATED (Assigned Desk)    │
 │ Ranks max_teams+1 to +10     ──► STANDBY_TOP10 (Lobby Call)   │
 │ Ranks > max_teams+10         ──► WAITLISTED (Remote Standby)  │
 └───────────────────────────────────────────────────────────────┘
       │
       ▼
 [Participant Lead Portal: /portal/{token}]
 ├── Unique Check-In Token & Mock Barcode
 ├── Assigned Desk / Priority Standby Callout
 ├── Problem Statement Abstract & Official PDF Link
 └── Marking Rubric Criteria (Innovation, Tech, Presentation)
       │
       ▼ (Kickoff + 15 Minutes)
 [15-Minute No-Show Protocol: /admin/{event_id}/sweep-noshows]
 ├── Unverified ALLOCATED teams ──► Marked NO_SHOW (Desks Reclaimed)
 └── STANDBY_TOP10 Candidates   ──► Immediately PROMOTED to Desks
       │
       ▼
 [Judging & 2-Hour Leaderboard Freeze]
 ├── Judges record scores per criteria (Max 100 pts)
 ├── 2 Hours Before End: Admin hits "Freeze 2-Hour Window"
 ├── Public View (/leaderboard/{event_id}): Padlock banner, scores locked
 └── Admin View (?admin=1): Backstage live telemetry for judges & organizers
```

---

## 5. Demo Credentials

| Role | Email | Password | Access / Scope |
|---|---|---|---|
| **Admin** | `admin@iitm.ac.in` | `admin123` | Full Ground Admin Console: All tables, check-in verifier, 15-min sweep, mail dispatch, venue/timing editor |
| **Participant (Allocated)** | `aarav@smail.iitm.ac.in` | `participant123` | Team: **NeuralForge** (Queue #1, Desk `CRC-T01` in Today's Event). Check-in code is **ACTIVE** (< 24h) |
| **Participant (Standby)** | `vikram@smail.iitm.ac.in` | `participant123` | Team: **CodeVanguard** (Queue #31, Standby Priority #1 in Today's Event). Lobby standby pass |

---

## 6. Mock Events & Seed State

1. **Event 1: "HackParadox 2027" (Today's Event)**
   - **Timing:** Starts today in 2 hours (`< 24h` $\rightarrow$ Check-in codes are **unlocked & active** for ground scanning).
   - **Capacity:** Exactly **30 desks** (`CRC-T01` to `CRC-T30`).
   - **Registrations:** Exactly **30 allocated teams** (Desks 1 to 30) + **5 teams in the standby queue** (Queue #31 to #35).
   - Demonstrates the live ground check-in desk, floorplan matrix, 15-minute no-show reclamation, and standby promotions.
2. **Event 2: "AlgoStrike Coding Battle" (Next Week's Event)**
   - **Timing:** Scheduled next week in 7 days (`> 24h`).
   - **24-Hour Rule:** Check-in codes are **LOCKED** ("Unlocks 24 hours prior to event").
   - Visible on the participant dashboard under **"Upcoming Events Open for Registration"**, where users can sign up their squads. If capacity is filled, new registrations are automatically queued without cluttering the registration form with internal desk codes.

---

## 7. Production Deployment Guide

Paradesk is fully hardened and deployment-ready across multiple deployment targets:

### Option A: Docker / Container Deployment (Recommended)
Build and run with a persistent SQLite database volume:
```bash
# Build and launch in background
docker compose up -d --build

# Inspect logs
docker compose logs -f

# Verify container health
curl http://localhost:8000/health
```

Or run standalone:
```bash
docker build -t paradesk:latest .
docker run -d -p 8000:8000 -v paradesk_data:/app/data --name paradesk-prod paradesk:latest
```

### Option B: 1-Click Cloud Deployment (Render / Railway / Fly.io / Heroku)
The repo contains pre-configured deployment manifests:
- **`Procfile`**: Automatically used by Render, Railway, and Heroku.
- **`render.yaml`**: Pre-configured Blueprint for Render with auto-deploy and health checks.
- Environment variables:
  - `PORT`: Automatically set by the hosting provider.
  - `SECRET_KEY`: Set to a strong random secret.
  - `SECURE_COOKIES`: Set to `true` when HTTPS is enabled.

### Option C: Traditional Linux VM / Server (Nginx + Systemd)
Run as a systemd service with Gunicorn or Uvicorn:
```bash
pip install -r requirements.txt
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000
```

### Option D: Quickstart & Running Locally
```powershell
pip install -r requirements.txt
uvicorn app:app --reload
```
Open **http://127.0.0.1:8000** in your browser. Use the demo account buttons or enter the credentials above to explore!

### Step 3: Run the Automated Verification Suite
```powershell
python direct_test.py
```

---

## 8. Endpoints Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/dashboard` | Multi-event ground operations command center |
| `POST` | `/admin/events` | Provision a new competition / event with desk capacity |
| `POST` | `/admin/events/{event_id}/update-resources` | Update Problem Statement and Rubric JSON |
| `POST` | `/admin/events/{event_id}/toggle-freeze` | Toggle 2-hour leaderboard freeze window |
| `POST` | `/events/{event_id}/import-csv` | Upload G-Form CSV for automated FCFS allocation |
| `GET` | `/events/{event_id}/sample-csv` | Download sample Google Form CSV template |
| `GET` | `/portal/{unique_checkin_token}` | Lead participant digital pass & resources |
| `POST` | `/admin/{event_id}/checkin` | Fast ground check-in by token or team name |
| `POST` | `/admin/{event_id}/sweep-noshows` | 15-minute protocol: sweep no-shows, promote standby |
| `POST` | `/admin/{event_id}/score` | Record judge scores across rubric dimensions |
| `GET` | `/leaderboard/{event_id}` | Public leaderboard with freeze banner |
| `GET` | `/leaderboard/{event_id}?admin=1` | Admin unmasked live leaderboard |
| `POST` | `/admin/reset` | Reseed system to initial Paradox'27 state |

---

## 7. Companion Documentation

- **`TASK_2_2_DROP_OFF_SOLUTION.md`:** Detailed strategic blueprint analyzing root causes of drop-off (impulse registration, solo fear, team attrition, lack of schedule visibility, ghost tables) and the full technical operations plan for the Technicals Department.
- **`google_sheets_apps_script.js`:** Google Apps Script connecting directly to Google Sheets for automated confirmation emails, 48-hour hard RSVP, and standby notifications.
