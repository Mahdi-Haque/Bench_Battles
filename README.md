# Bench Battles — Pen Fight

A browser-based multiplayer pen-fighting game built with React, TypeScript, Tailwind CSS, Phaser 3 (Matter.js physics), Django REST Framework, and PostgreSQL.

---

## Milestone Status

- [x] **M0 — Tech Confirmation, Inspection & Implementation Plan**
- [x] **M1 — Local Tabletop Physics Prototype**
- [x] **M2 — Pen Fight Polish, Reliability & Test Suite**
- [x] **M3 — Django Backend Foundation, Guest Identities & Game Rooms**
- [ ] M4 — Online Multiplayer Rooms & Real-Time Turns
- [ ] M5 — Room Text Chat & Reconnect Handling
- [ ] M6 — Managed Voice Chat (LiveKit)
- [ ] M7 — Match Results, Audio Preferences & UI Polish
- [ ] M8 — Deployment & Production Verification

---

## Project Architecture

```
Bench_Battles/
├── frontend/                     # React 19 + TypeScript + Vite + Tailwind CSS + Phaser 3
│   ├── src/
│   │   ├── components/           # UI Controls, GameCanvas, Modals, TopBar
│   │   ├── game/                 # Phaser TableScene, Pen entity, physicsUtils, audio, config
│   │   ├── App.tsx               # Main application orchestration
│   │   └── main.tsx              # React entrypoint
│   ├── package.json
│   └── vite.config.ts
├── backend/                      # Django 6 + Django REST Framework + PostgreSQL
│   ├── config/                   # Root Django configuration, settings, urls, wsgi, asgi
│   ├── apps/
│   │   ├── players/              # Guest identity, cryptographic tokens, authentication
│   │   │   ├── models.py         # GuestPlayer (UUID id, SHA-256 token_hash)
│   │   │   ├── authentication.py # GuestTokenAuthentication (Bearer / X-Guest-Token)
│   │   │   ├── serializers.py    # Guest serializers (tokens strictly unexposed)
│   │   │   ├── views.py          # /api/players/guest/, /api/players/me/
│   │   │   └── tests.py          # Identity & authentication test suite
│   │   └── rooms/                # Game room lifecycle, membership, capacity, concurrency
│   │       ├── models.py         # Room, RoomMembership, constraints, 6-char codes
│   │       ├── serializers.py    # Room serializers (passcodes hashed and excluded)
│   │       ├── views.py          # /api/rooms/, join, leave, details
│   │       └── tests.py          # Room lifecycle, constraints & security test suite
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Environment variables template
│   ├── .gitignore                # Python & Django gitignore
│   └── manage.py                 # Django management utility
└── README.md
```

---

## Prerequisites

- **Frontend**: Node.js `v20+` or `v24+`, npm `10+` or `11+`
- **Backend**: Python `3.14+` with pip
- **Database**: PostgreSQL `15+` or `16+` (for persistent multi-user storage)

---

## Windows PowerShell Setup & Run Instructions

### 1. PostgreSQL Setup (Windows)

If PostgreSQL is not yet installed on your Windows system, install it using `winget` or the official EnterpriseDB installer:

```powershell
# Option A: Install via Windows Package Manager
winget install PostgreSQL.PostgreSQL

# Option B: Download installer directly
# https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
```

After installation, start the PostgreSQL service and create the database:
```powershell
# Start the Windows service (if not set to automatic)
Start-Service postgresql-x64-16

# Create database and user using psql
psql -U postgres -c "CREATE DATABASE bench_battles;"
psql -U postgres -c "CREATE DATABASE test_bench_battles;"
```

---

### 2. Backend Setup & Run

Open a Windows PowerShell terminal in the repository root:

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env from template and configure your PostgreSQL password
Copy-Item .env.example .env
# Edit .env to set DB_PASSWORD=your_actual_password

# 6. Apply database migrations
python manage.py migrate

# 7. Run system integrity checks
python manage.py check

# 8. Run automated backend test suite
python manage.py test

# 9. Start Django development server
python manage.py runserver 127.0.0.1:8000
```

> **Note on Testing**: To run tests in an isolated environment without a live PostgreSQL instance running, you can run:
> ```powershell
> $env:DB_ENGINE="django.db.backends.sqlite3"; python manage.py test
> ```
> *Note: While model logic, serializers, and permissions pass identically, SQLite does not provide equivalent row-locking semantics to PostgreSQL's `select_for_update()`, so PostgreSQL is required for multi-client concurrency validation.*

---

### 3. Frontend Setup & Run

Open a second Windows PowerShell terminal:

```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start local development server
npm run dev

# 4. Run Vitest physics tests
npm test

# 5. Run linter
npm run lint

# 6. Verify production build
npm run build
```

Visit `http://localhost:5173/` in your browser.

---

## REST API Documentation

Base URL: `http://127.0.0.1:8000/api`

### 1. System
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health/` | None | Returns system health status and database connectivity. |

### 2. Guest Identity (`/api/players/`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/players/guest/` | None | Create a new guest player. Returns `{ id, nickname, token, created_at }`. The raw `token` is returned **only once** and must be saved by the client. |
| `GET` | `/api/players/me/` | Bearer / X-Guest-Token | Retrieve the authenticated guest player's profile (`id`, `nickname`, timestamps). Never leaks credentials. |
| `PATCH` | `/api/players/me/` | Bearer / X-Guest-Token | Update the authenticated guest player's display nickname. |

### 3. Game Rooms (`/api/rooms/`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/rooms/` | None | List eligible public rooms (status: `WAITING`, `is_private: false`, non-full). |
| `POST` | `/api/rooms/` | Bearer / X-Guest-Token | Create a new room. Generates a unique 6-character room code. Creator is automatically joined as `HOST`. Supports private passcode (hashed with PBKDF2/argon2). |
| `GET` | `/api/rooms/{code}/` | None / Auth | Retrieve room details and active player rosters. Private rooms require active membership, `X-Room-Passcode` header, or `POST` with passcode body. |
| `POST` | `/api/rooms/{code}/join/` | Bearer / X-Guest-Token | Join an eligible room. Enforces row-level atomic locks, capacity limits (2–10 players), duplicate-membership rejection, and private room passcode verification. |
| `POST` | `/api/rooms/{code}/leave/` | Bearer / X-Guest-Token | Leave a room. If the host leaves and other active members remain, ownership transfers to the oldest member; if no players remain, the room closes (`CLOSED`). |

---

## Authentication Mechanism

- **Public Player ID**: A UUIDv4 string (e.g. `c7b2a65a-8b93-4e38-9582-72179815d482`). Safe for opponent UI and public room rosters.
- **Authentication Token**: A high-entropy cryptographic token (`secrets.token_urlsafe(32)`).
  - Stored in PostgreSQL as a SHA-256 hash (`token_hash`) with a database index.
  - The client provides the token in either header:
    - `Authorization: Bearer <token>`
    - `X-Guest-Token: <token>`
  - Passwords and social logins are not required for guest access.

---

## Gameplay Controls & Features (Local Tabletop Prototype)

1. **Interactive Slingshot Aiming**: Click & drag backward on the active pen on the table canvas to aim and pull power, then release to shoot.
2. **Predicted Trajectory Preview**: Fading trajectory guide dots show the initial slide path; dots tint red if the predicted impulse approaches or exceeds the table boundary.
3. **Impulse Power Slider**: Adjust flick power from 10% to 100% or use quick presets (*Nudge 30%*, *Flick 65%*, *Smash 95%*).
4. **Impact Point Selector**: Move the target crosshair along the pen body from **Rear Cap (-1.0)** to **Center (0.0)** to **Front Tip (+1.0)**.
   - *Tail Strike*: Induces strong rotational torque (spins the tip outward).
   - *Center Strike*: Direct linear impulse with minimal spin.
   - *Tip Strike*: Sweeps the rear cap in a sweeping arc.
5. **Angle Fine-Tuning**: Stepper buttons (`-5°` / `+5°`) to dial in precise angles with automatic angle synchronization between Phaser and React.
6. **Table Edge Rules**: Pens stay active while resting on the table; touching the border is legal. The instant a pen's center of mass crosses the perimeter into the drop zone, it is eliminated with a drop animation and fall sound.
7. **Tactile Collision Feedback**: Dynamic collision sparks scaled to impact intensity, with subtle camera micro-shake on heavy hits ($> 7\text{ px/ms}$).
8. **Physics Tuner**: Click the **Physics** button in the header to tune table friction, air drag, collision elasticity (restitution = 0.75 default), and max impulse in real time.

---

## Real-Time WebSockets & Multiplayer (Milestone 4)

Endpoint: `ws://127.0.0.1:8000/ws/rooms/{room_code}/?token={guest_token}`

- **Transport**: Django Channels 4.x with Daphne ASGI server.
- **WebSocket Authentication**: `GuestTokenAuthMiddleware` authenticates incoming connections using the raw guest token from query parameters (`?token=...`), hashing it via SHA-256 before database lookup.
- **Match Lifecycle & Turns (Authoritative)**:
  - `start_match`: Initiated by room host; requires $\ge 2$ players; creates authoritative `Match` in PostgreSQL.
  - `flick`: Validates active player turn ownership and animation state.
  - `end_turn`: Authoritatively rotates turn in round-robin order; increments `turn_number` monotonically.
  - `turn_timeout`: Safe 30s timeout handling; protected against duplicate or stale timer callbacks via PostgreSQL row locking (`select_for_update()`).
  - `concede`: Forfeits active match, awards victory to opponent, and transitions room status to `FINISHED`.
  - Reconnecting players immediately receive the current authoritative `active_match` state snapshot.

---

## Current Status & Next Steps

- **Completed**:
  - M1 & M2: Local Pen Fight tabletop prototype, tactile physics tuning (`restitution = 0.75`), slingshot aiming, drop-zone eliminations.
  - M3: Django REST backend, PostgreSQL database, guest player identities, game room management, atomic concurrency safeguards.
  - M4 Stage 1 & 2: Real-Time WebSockets with Django Channels, presence sync, server-authoritative match lifecycle, turn order, timeouts, and concurrency protections.
- **Next Stage (M4 Stage 3)**:
  - Synchronized pen flick impulses, deterministic client Matter.js physics playback, turn settlement (`settle_turn`), and server-validated drop-off eliminations.
