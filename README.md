# Bench Battles — Pen Fight

A browser-based multiplayer pen-fighting game built with React, TypeScript, Tailwind CSS, Phaser 3 (Matter.js physics), and Django Channels.

## Milestone Status

- [x] **M0 — Tech Confirmation, Inspection & Implementation Plan**
- [x] **M1 — Local Tabletop Physics Prototype**
- [x] **M2 — Pen Fight Polish, Reliability & Test Suite**
- [ ] M3 — Django Backend & Guest Identity
- [ ] M4 — Online Multiplayer Rooms & Real-Time Turns
- [ ] M5 — Room Text Chat & Reconnect Handling
- [ ] M6 — Managed Voice Chat (LiveKit)
- [ ] M7 — Match Results, Audio Preferences & UI Polish
- [ ] M8 — Deployment & Production Verification

---

## Getting Started (Frontend Development)

### Prerequisites
- Node.js `v20+` or `v24+`
- npm `10+` or `11+`

### Setup & Run Local Prototype
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start local development server
npm run dev

# Run automated unit test suite (Vitest)
npm test

# Run linter (Oxlint)
npm run lint

# Verify production build
npm run build
```

Visit `http://localhost:5173/` in your browser.

---

## Gameplay Controls & Features
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
