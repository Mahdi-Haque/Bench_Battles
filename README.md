# Bench Battles — Pen Fight

A browser-based multiplayer pen-fighting game built with React, TypeScript, Tailwind CSS, Phaser 3 (Matter.js physics), and Django Channels.

## Milestone Status

- [x] **M0 — Tech Confirmation, Inspection & Implementation Plan**
- [x] **M1 — Local Tabletop Physics Prototype**
- [ ] M2 — Physics Polish, Audio Refinement & Edge Cases
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
```

Visit `http://localhost:5173/` in your browser.

---

## Gameplay Controls (M1 Prototype)
1. **Interactive Slingshot Aiming**: Click & drag backward on the active pen on the table canvas to aim and pull power, then release to shoot.
2. **Impulse Power Slider**: Adjust flick power from 10% to 100% or use quick presets (Nudge, Flick, Smash).
3. **Impact Point Selector**: Move the target crosshair along the pen body from **Rear Cap (-1.0)** to **Center (0.0)** to **Front Tip (+1.0)**.
   - *Tail Strike*: Induces strong rotational torque (spins the tip outward).
   - *Center Strike*: Direct linear impulse with minimal spin.
   - *Tip Strike*: Sweeps the rear cap in a sweeping arc.
4. **Angle Fine-Tuning**: Stepper buttons (`-5°` / `+5°`) to dial in precise angles.
5. **Table Edge Rules**: Pens stay active while resting on the table; when a pen's center of mass crosses the perimeter into the drop zone, it is eliminated with a drop animation and fall sound.
6. **Physics Tuner**: Click the **Physics** button in the header to tune table friction, air drag, collision elasticity (restitution), and max impulse in real time.
