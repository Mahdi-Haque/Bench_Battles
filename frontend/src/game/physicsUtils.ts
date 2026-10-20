/**
 * Pure physics and geometry utility functions.
 * Easily unit-testable and decoupled from Phaser scene rendering.
 */

export interface TableBounds {
  left: number;
  right: number;
  top: number;
  bottom: number;
  width: number;
  height: number;
  cornerRadius: number;
}

/**
 * Checks whether a 2D point (x, y) is inside a rectangle with rounded corners.
 */
export function isPointInsideRoundedRect(
  x: number,
  y: number,
  left: number,
  top: number,
  width: number,
  height: number,
  radius: number
): boolean {
  const right = left + width;
  const bottom = top + height;

  // Basic bounding box check
  if (x < left || x > right || y < top || y > bottom) {
    return false;
  }

  // Top-left corner
  if (x < left + radius && y < top + radius) {
    return Math.hypot(x - (left + radius), y - (top + radius)) <= radius;
  }
  // Top-right corner
  if (x > right - radius && y < top + radius) {
    return Math.hypot(x - (right - radius), y - (top + radius)) <= radius;
  }
  // Bottom-left corner
  if (x < left + radius && y > bottom - radius) {
    return Math.hypot(x - (left + radius), y - (bottom - radius)) <= radius;
  }
  // Bottom-right corner
  if (x > right - radius && y > bottom - radius) {
    return Math.hypot(x - (right - radius), y - (bottom - radius)) <= radius;
  }

  return true;
}

/**
 * Checks whether the center of a pen is inside the table boundaries.
 */
export function isPenCenterInsideTable(x: number, y: number, table: TableBounds): boolean {
  return isPointInsideRoundedRect(
    x,
    y,
    table.left,
    table.top,
    table.width,
    table.height,
    table.cornerRadius
  );
}

/**
 * Computes world coordinates for an impact point along a pen's longitudinal axis.
 * @param bodyX Center X
 * @param bodyY Center Y
 * @param bodyAngle Orientation in radians
 * @param normalizedOffset -1.0 (rear cap) to +1.0 (front tip), 0 is center
 * @param effectiveHalfLength Distance from center to usable tip/cap impact margin
 */
export function calculateImpactPoint(
  bodyX: number,
  bodyY: number,
  bodyAngle: number,
  normalizedOffset: number,
  effectiveHalfLength: number
): { x: number; y: number } {
  const clampedOffset = Math.max(-1.0, Math.min(1.0, normalizedOffset));
  const localX = clampedOffset * effectiveHalfLength;
  const localY = 0;

  const cos = Math.cos(bodyAngle);
  const sin = Math.sin(bodyAngle);

  return {
    x: bodyX + (localX * cos - localY * sin),
    y: bodyY + (localX * sin + localY * cos),
  };
}

/**
 * Calculates torque spin direction based on normalized impact offset.
 */
export function calculateTorqueDirection(offset: number): 'CLOCKWISE' | 'COUNTER_CLOCKWISE' | 'NEUTRAL' {
  if (offset > 0.15) return 'CLOCKWISE';
  if (offset < -0.15) return 'COUNTER_CLOCKWISE';
  return 'NEUTRAL';
}

/**
 * Calculates impulse force magnitude from normalized power.
 */
export function calculateImpulseForce(
  powerNormalized: number,
  minForce: number,
  maxForce: number
): number {
  const clamped = Math.max(0, Math.min(1, powerNormalized));
  return minForce + clamped * (maxForce - minForce);
}

export interface TrajectoryPoint {
  x: number;
  y: number;
  alpha: number;
  isInsideTable: boolean;
}

/**
 * Generates subtle predicted trajectory points for the pen's initial slide path.
 * Decoupled from collisions — represents the initial impulse vector under table drag.
 */
export function calculatePredictedTrajectory(
  startX: number,
  startY: number,
  angleRad: number,
  powerNormalized: number,
  table: TableBounds,
  maxPoints: number = 7
): TrajectoryPoint[] {
  const points: TrajectoryPoint[] = [];
  const maxDistance = 40 + (powerNormalized / 100) * 160;
  const stepDistance = maxDistance / maxPoints;

  const cos = Math.cos(angleRad);
  const sin = Math.sin(angleRad);

  for (let i = 1; i <= maxPoints; i++) {
    const dist = i * stepDistance;
    const px = startX + cos * dist;
    const py = startY + sin * dist;

    const inside = isPenCenterInsideTable(px, py, table);
    const alpha = Math.max(0.1, 0.75 - (i / maxPoints) * 0.65);

    points.push({
      x: px,
      y: py,
      alpha,
      isInsideTable: inside,
    });
  }

  return points;
}
