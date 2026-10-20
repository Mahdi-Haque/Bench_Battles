/**
 * Centralized Game & Physics Configuration
 * All physics constants, table dimensions, and gameplay tuning in one documented location.
 */

export interface PhysicsConfig {
  friction: number;
  frictionAir: number;
  frictionStatic: number;
  restitution: number;
  density: number;
  penMass: number;
  maxForce: number;
  minForce: number;
  settleSpeedThreshold: number;
  settleAngularThreshold: number;
  settleDurationMs: number;
  maxSimulateTimeoutMs: number;
}

export const GAME_DIMENSIONS = {
  width: 1200,
  height: 750,
  table: {
    width: 980,
    height: 560,
    centerX: 600,
    centerY: 375,
    borderWidth: 16,
    cornerRadius: 24,
    // Calculated bounds
    get left() {
      return this.centerX - this.width / 2;
    },
    get right() {
      return this.centerX + this.width / 2;
    },
    get top() {
      return this.centerY - this.height / 2;
    },
    get bottom() {
      return this.centerY + this.height / 2;
    },
  },
  pen: {
    length: 120,
    width: 18,
    tipLength: 22,
    gripLength: 26,
    capLength: 28,
  },
};

export const DEFAULT_PHYSICS_CONFIG: PhysicsConfig = {
  friction: 0.12,
  frictionAir: 0.025,
  frictionStatic: 0.25,
  restitution: 0.75,
  density: 0.002,
  penMass: 2.2,
  minForce: 0.006,
  maxForce: 0.11,
  settleSpeedThreshold: 0.06,
  settleAngularThreshold: 0.006,
  settleDurationMs: 250,
  maxSimulateTimeoutMs: 7000,
};

export interface PlayerSetup {
  id: string;
  name: string;
  colorName: string;
  themeColor: number;
  accentColor: number;
  tailColor: number;
  textColor: string;
  startPos: { x: number; y: number; angle: number };
}

export const PLAYERS_SETUP: PlayerSetup[] = [
  {
    id: 'p1',
    name: 'Player 1 (Blue)',
    colorName: 'Cyan Blue',
    themeColor: 0x0ea5e9, // Sky 500
    accentColor: 0x38bdf8,
    tailColor: 0x0284c7,
    textColor: '#38bdf8',
    startPos: { x: 380, y: 375, angle: 0 }, // Horizontal pointing right
  },
  {
    id: 'p2',
    name: 'Player 2 (Red)',
    colorName: 'Crimson Red',
    themeColor: 0xef4444, // Red 500
    accentColor: 0xf87171,
    tailColor: 0xb91c1c,
    textColor: '#f87171',
    startPos: { x: 820, y: 375, angle: Math.PI }, // Horizontal pointing left
  },
];
