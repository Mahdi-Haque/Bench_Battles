import { describe, it, expect } from 'vitest';
import {
  isPointInsideRoundedRect,
  isPenCenterInsideTable,
  calculateImpactPoint,
  calculateTorqueDirection,
  calculateImpulseForce,
  calculatePredictedTrajectory,
} from './physicsUtils';
import { DEFAULT_PHYSICS_CONFIG, GAME_DIMENSIONS } from './config';

describe('Physics Configuration Integrity', () => {
  it('preserves tuned collision restitution of 0.75', () => {
    expect(DEFAULT_PHYSICS_CONFIG.restitution).toBe(0.75);
  });

  it('has stable positive friction and drag coefficients', () => {
    expect(DEFAULT_PHYSICS_CONFIG.friction).toBeGreaterThan(0);
    expect(DEFAULT_PHYSICS_CONFIG.frictionAir).toBeGreaterThan(0);
    expect(DEFAULT_PHYSICS_CONFIG.minForce).toBeLessThan(DEFAULT_PHYSICS_CONFIG.maxForce);
  });

  it('defines valid table boundary dimensions', () => {
    const { table } = GAME_DIMENSIONS;
    expect(table.left).toBeLessThan(table.right);
    expect(table.top).toBeLessThan(table.bottom);
    expect(table.width).toBe(980);
    expect(table.height).toBe(560);
    expect(table.cornerRadius).toBe(24);
  });
});

describe('Table Boundary & Rounded Corner Detection', () => {
  const table = {
    left: 100,
    right: 500,
    top: 100,
    bottom: 400,
    width: 400,
    height: 300,
    cornerRadius: 20,
  };

  it('detects center of table as inside', () => {
    expect(isPenCenterInsideTable(300, 250, table)).toBe(true);
  });

  it('detects points well outside boundaries as outside', () => {
    expect(isPenCenterInsideTable(50, 250, table)).toBe(false); // Far left
    expect(isPenCenterInsideTable(550, 250, table)).toBe(false); // Far right
    expect(isPenCenterInsideTable(300, 50, table)).toBe(false); // Far top
    expect(isPenCenterInsideTable(300, 450, table)).toBe(false); // Far bottom
  });

  it('differentiates rounded corners from rectangular bounding box', () => {
    // Extreme top-left corner point (101, 101) is inside the bounding box [100, 500] x [100, 400],
    // but outside the circular rounded corner arc with radius 20 from corner center (120, 120):
    // Distance from (120, 120) is sqrt(19^2 + 19^2) = ~26.87 > 20
    expect(isPointInsideRoundedRect(101, 101, table.left, table.top, table.width, table.height, table.cornerRadius)).toBe(false);

    // Point slightly inside the rounded arc: (115, 115) -> dist from (120, 120) = sqrt(5^2 + 5^2) = ~7.07 < 20
    expect(isPointInsideRoundedRect(115, 115, table.left, table.top, table.width, table.height, table.cornerRadius)).toBe(true);
  });
});

describe('Impact Point Calculation along Pen Axis', () => {
  it('maps center offset 0 to the pen body center regardless of angle', () => {
    const center0 = calculateImpactPoint(300, 200, 0, 0, 50);
    expect(center0.x).toBeCloseTo(300);
    expect(center0.y).toBeCloseTo(200);

    const centerRotated = calculateImpactPoint(300, 200, Math.PI / 4, 0, 50);
    expect(centerRotated.x).toBeCloseTo(300);
    expect(centerRotated.y).toBeCloseTo(200);
  });

  it('correctly projects front tip (+1.0) and rear cap (-1.0) at angle 0', () => {
    const tip = calculateImpactPoint(300, 200, 0, 1.0, 52);
    expect(tip.x).toBeCloseTo(352);
    expect(tip.y).toBeCloseTo(200);

    const cap = calculateImpactPoint(300, 200, 0, -1.0, 52);
    expect(cap.x).toBeCloseTo(248);
    expect(cap.y).toBeCloseTo(200);
  });

  it('correctly projects along rotated pen axis (angle = 90 deg / PI/2)', () => {
    const tip = calculateImpactPoint(300, 200, Math.PI / 2, 1.0, 50);
    expect(tip.x).toBeCloseTo(300);
    expect(tip.y).toBeCloseTo(250);

    const cap = calculateImpactPoint(300, 200, Math.PI / 2, -1.0, 50);
    expect(cap.x).toBeCloseTo(300);
    expect(cap.y).toBeCloseTo(150);
  });
});

describe('Torque & Impulse Calculations', () => {
  it('identifies clockwise spin for positive offsets (front tip strikes)', () => {
    expect(calculateTorqueDirection(0.5)).toBe('CLOCKWISE');
    expect(calculateTorqueDirection(1.0)).toBe('CLOCKWISE');
  });

  it('identifies counter-clockwise spin for negative offsets (rear tail strikes)', () => {
    expect(calculateTorqueDirection(-0.5)).toBe('COUNTER_CLOCKWISE');
    expect(calculateTorqueDirection(-1.0)).toBe('COUNTER_CLOCKWISE');
  });

  it('identifies neutral spin for near-center strikes', () => {
    expect(calculateTorqueDirection(0.0)).toBe('NEUTRAL');
    expect(calculateTorqueDirection(0.1)).toBe('NEUTRAL');
    expect(calculateTorqueDirection(-0.1)).toBe('NEUTRAL');
  });

  it('interpolates impulse force between minForce and maxForce', () => {
    const minF = 0.01;
    const maxF = 0.10;
    expect(calculateImpulseForce(0, minF, maxF)).toBeCloseTo(0.01);
    expect(calculateImpulseForce(1.0, minF, maxF)).toBeCloseTo(0.10);
    expect(calculateImpulseForce(0.5, minF, maxF)).toBeCloseTo(0.055);
  });
});

describe('Predicted Trajectory Preview', () => {
  const table = {
    left: 100,
    right: 500,
    top: 100,
    bottom: 400,
    width: 400,
    height: 300,
    cornerRadius: 20,
  };

  it('generates points with descending opacity', () => {
    const points = calculatePredictedTrajectory(300, 250, 0, 50, table, 5);
    expect(points.length).toBe(5);
    for (let i = 1; i < points.length; i++) {
      expect(points[i].alpha).toBeLessThan(points[i - 1].alpha);
    }
  });

  it('flags points that cross table boundary', () => {
    // Shot heading right towards edge at x=500
    const points = calculatePredictedTrajectory(480, 250, 0, 100, table, 5);
    const outsidePoints = points.filter((p) => !p.isInsideTable);
    expect(outsidePoints.length).toBeGreaterThan(0);
  });
});
