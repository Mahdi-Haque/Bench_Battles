import Phaser from 'phaser';
import { GAME_DIMENSIONS } from './config';
import type { PhysicsConfig, PlayerSetup } from './config';
import type { PenState } from './types';
import { soundManager } from './audio';
import { calculateImpactPoint } from './physicsUtils';

export class Pen {
  public scene: Phaser.Scene;
  public player: PlayerSetup;
  public body!: MatterJS.BodyType;
  public container!: Phaser.GameObjects.Container;
  public state: PenState = 'ON_TABLE';

  // Visual sub-elements
  private shadowGraphics!: Phaser.GameObjects.Graphics;
  private barrelGraphics!: Phaser.GameObjects.Graphics;
  private highlightGraphics!: Phaser.GameObjects.Graphics;
  private turnIndicatorRing!: Phaser.GameObjects.Arc;
  private impactMarkerGraphics!: Phaser.GameObjects.Graphics;

  private isEliminating: boolean = false;

  constructor(scene: Phaser.Scene, player: PlayerSetup, physicsConfig: PhysicsConfig) {
    this.scene = scene;
    this.player = player;

    this.createPhysicsBody(player.startPos.x, player.startPos.y, player.startPos.angle, physicsConfig);
    this.createVisuals();
  }

  private createPhysicsBody(x: number, y: number, angle: number, cfg: PhysicsConfig): void {
    const { length, width } = GAME_DIMENSIONS.pen;

    // Matter rectangle body with rounded chamfer
    this.body = this.scene.matter.add.rectangle(x, y, length, width, {
      chamfer: { radius: 5 },
      friction: cfg.friction,
      frictionAir: cfg.frictionAir,
      frictionStatic: cfg.frictionStatic,
      restitution: cfg.restitution,
      density: cfg.density,
      label: `pen_${this.player.id}`,
    });

    // Set initial orientation
    this.scene.matter.body.setAngle(this.body, angle);

    // Link back to this instance
    (this.body as unknown as { penInstance: Pen }).penInstance = this;
  }

  private createVisuals(): void {
    const { length, width, tipLength, gripLength, capLength } = GAME_DIMENSIONS.pen;
    const halfL = length / 2;
    const halfW = width / 2;

    this.container = this.scene.add.container(this.body.position.x, this.body.position.y);
    this.container.setDepth(10);

    // 1. Drop Shadow (gives 3D tabletop depth)
    this.shadowGraphics = this.scene.add.graphics();
    this.shadowGraphics.fillStyle(0x000000, 0.35);
    this.shadowGraphics.fillRoundedRect(-halfL + 4, -halfW + 5, length, width, 5);
    this.container.add(this.shadowGraphics);

    // 2. Active Turn Indicator Ring (pulsing aura behind pen)
    this.turnIndicatorRing = this.scene.add.arc(0, 0, halfL + 12, 0, 360, false, this.player.themeColor, 0.25);
    this.turnIndicatorRing.setStrokeStyle(3, this.player.accentColor, 0.8);
    this.turnIndicatorRing.setVisible(false);
    this.container.add(this.turnIndicatorRing);

    // 3. Pen Body & Details
    this.barrelGraphics = this.scene.add.graphics();
    this.drawPenGraphics(this.barrelGraphics, halfL, halfW, tipLength, gripLength, capLength);
    this.container.add(this.barrelGraphics);

    // 4. Subtle top specular highlight
    this.highlightGraphics = this.scene.add.graphics();
    this.highlightGraphics.fillStyle(0xffffff, 0.22);
    this.highlightGraphics.fillRoundedRect(-halfL + capLength + 2, -halfW + 2, length - capLength - tipLength - 4, 3, 1.5);
    this.container.add(this.highlightGraphics);

    // 5. Impact Point Cursor (shows exactly where the flick/shot will hit)
    this.impactMarkerGraphics = this.scene.add.graphics();
    this.container.add(this.impactMarkerGraphics);

    this.updateTransform();
  }

  private drawPenGraphics(
    g: Phaser.GameObjects.Graphics,
    halfL: number,
    halfW: number,
    tipL: number,
    gripL: number,
    capL: number
  ): void {
    g.clear();

    // Longitudinal coordinate layout:
    // [-halfL] = Rear Cap  ----  [+halfL - tipL] = Tip Start  ----  [+halfL] = Nib

    // A. Main Barrel
    const barrelStart = -halfL + capL;
    const barrelLen = 2 * halfL - capL - tipL;
    g.fillStyle(this.player.themeColor, 1.0);
    g.fillRoundedRect(barrelStart, -halfW, barrelLen, halfW * 2, 2);

    // B. Rubber Finger Grip Section
    const gripStart = barrelStart + barrelLen - gripL;
    g.fillStyle(0x1e293b, 1.0); // Dark ergonomic grip
    g.fillRoundedRect(gripStart, -halfW, gripL, halfW * 2, 1);

    // Grip rib lines
    g.lineStyle(1, 0x475569, 0.7);
    for (let x = gripStart + 4; x < gripStart + gripL; x += 4) {
      g.lineBetween(x, -halfW + 1, x, halfW - 1);
    }

    // C. Metallic Front Cone & Nib
    const tipBaseX = halfL - tipL;
    // Metallic cone
    g.fillStyle(0xd1d5db, 1.0); // Silver/Chrome
    g.fillTriangle(tipBaseX, -halfW + 1, tipBaseX, halfW - 1, halfL - 4, 0);

    // Ink ballpoint / nib tip
    g.fillStyle(0x0f172a, 1.0);
    g.fillCircle(halfL - 2, 0, 2.5);

    // D. Rear Cap & Pocket Clip
    g.fillStyle(this.player.tailColor, 1.0);
    g.fillRoundedRect(-halfL, -halfW + 1, capL, (halfW - 1) * 2, 4);

    // Pocket Clip
    g.fillStyle(0x94a3b8, 1.0); // Metal clip
    g.fillRoundedRect(-halfL + 2, -halfW - 3, capL - 6, 3, 1);
    g.fillRoundedRect(-halfL + 2, -halfW - 2, 3, 4, 1);

    // E. Player Emblem / Accent Stripe
    g.fillStyle(this.player.accentColor, 1.0);
    g.fillRect(barrelStart + 4, -halfW + 1, 6, (halfW - 1) * 2);

    // Subtle outline for crisp rendering
    g.lineStyle(1, 0x0f172a, 0.4);
    g.strokeRoundedRect(-halfL, -halfW, halfL * 2, halfW * 2, 4);
  }

  /**
   * Calculate world coordinates for an impact point along the pen's longitudinal axis.
   * normalizedOffset: -1.0 (rear cap) to +1.0 (tip), 0.0 is center of mass.
   */
  public getImpactPointWorld(normalizedOffset: number): { x: number; y: number } {
    const effectiveHalfL = GAME_DIMENSIONS.pen.length / 2 - 8;
    return calculateImpactPoint(
      this.body.position.x,
      this.body.position.y,
      this.body.angle,
      normalizedOffset,
      effectiveHalfL
    );
  }

  /**
   * Updates the impact marker graphics in the pen's local coordinate system.
   */
  public updateImpactMarker(normalizedOffset: number, isAiming: boolean): void {
    this.impactMarkerGraphics.clear();
    if (!isAiming || this.state !== 'ON_TABLE') return;

    const halfL = GAME_DIMENSIONS.pen.length / 2 - 8;
    const clampedOffset = Math.max(-1.0, Math.min(1.0, normalizedOffset));
    const localX = clampedOffset * halfL;

    // Outer pulsating target ring
    this.impactMarkerGraphics.lineStyle(2, 0xfacc15, 0.9); // Bright gold/yellow
    this.impactMarkerGraphics.strokeCircle(localX, 0, 7);

    // Crosshair lines
    this.impactMarkerGraphics.lineBetween(localX - 10, 0, localX + 10, 0);
    this.impactMarkerGraphics.lineBetween(localX, -9, localX, 9);

    // Center focal dot
    this.impactMarkerGraphics.fillStyle(0xffffff, 1.0);
    this.impactMarkerGraphics.fillCircle(localX, 0, 3);
  }

  /**
   * Applies shot force at the specified normalized impact offset.
   * Produces authentic torque and rotational deflection via Matter.js.
   */
  public shoot(powerNormalized: number, angleRad: number, impactOffset: number, physicsConfig: PhysicsConfig): void {
    if (this.state !== 'ON_TABLE') return;

    // Convert power (0 to 1) to impulse magnitude
    const forceMag = physicsConfig.minForce + powerNormalized * (physicsConfig.maxForce - physicsConfig.minForce);

    // Force vector
    const forceX = Math.cos(angleRad) * forceMag;
    const forceY = Math.sin(angleRad) * forceMag;

    // World impact point
    const impactPoint = this.getImpactPointWorld(impactOffset);

    // Matter.js applies force at the world coordinate point,
    // which automatically calculates torque = r x F and updates angular velocity!
    this.scene.matter.body.applyForce(this.body, impactPoint, { x: forceX, y: forceY });

    // Play flick sound
    soundManager.playFlick(powerNormalized);
  }

  /**
   * Synchronizes visual container with Matter.js physics body.
   */
  public updateTransform(): void {
    if (!this.container || !this.body) return;

    this.container.setPosition(this.body.position.x, this.body.position.y);
    this.container.setRotation(this.body.angle);
  }

  public setActiveTurn(isActive: boolean): void {
    if (!this.turnIndicatorRing) return;
    this.turnIndicatorRing.setVisible(isActive);
  }

  public getSpeed(): number {
    if (!this.body) return 0;
    return Math.hypot(this.body.velocity.x, this.body.velocity.y);
  }

  public getAngularSpeed(): number {
    if (!this.body) return 0;
    return Math.abs(this.body.angularVelocity);
  }

  public stopMovement(): void {
    if (!this.body) return;
    this.scene.matter.body.setVelocity(this.body, { x: 0, y: 0 });
    this.scene.matter.body.setAngularVelocity(this.body, 0);
  }

  /**
   * Trigger falling off the table animation and elimination.
   */
  public eliminate(): void {
    if (this.isEliminating || this.state === 'ELIMINATED') return;
    this.isEliminating = true;
    this.state = 'FALLING';

    // Cancel any active tweens on the container before starting fall animation
    this.scene.tweens.killTweensOf(this.container);

    soundManager.playTableFall();
    this.setActiveTurn(false);
    this.updateImpactMarker(0, false);

    // Remove physics body so it doesn't collide with remaining pens while falling
    this.scene.matter.world.remove(this.body);

    // Tween scale, alpha, and spin to simulate plunging downward to the floor
    this.scene.tweens.add({
      targets: this.container,
      scaleX: 0.1,
      scaleY: 0.1,
      alpha: 0,
      rotation: this.container.rotation + Math.PI * 1.5,
      y: this.container.y + 120,
      duration: 650,
      ease: 'Cubic.easeIn',
      onComplete: () => {
        this.state = 'ELIMINATED';
        this.container.setVisible(false);
      },
    });
  }

  /**
   * Reset pen to start position
   */
  public reset(physicsConfig: PhysicsConfig): void {
    // Kill any active elimination or transition tweens
    this.scene.tweens.killTweensOf(this.container);

    this.isEliminating = false;
    this.state = 'ON_TABLE';

    // If body was removed from world during elimination, re-add it
    if (!this.scene.matter.world.has(this.body)) {
      this.scene.matter.world.add(this.body);
    }

    this.scene.matter.body.setPosition(this.body, { x: this.player.startPos.x, y: this.player.startPos.y });
    this.scene.matter.body.setAngle(this.body, this.player.startPos.angle);
    this.stopMovement();

    // Reset physics properties in case config changed
    this.body.friction = physicsConfig.friction;
    this.body.frictionAir = physicsConfig.frictionAir;
    this.body.restitution = physicsConfig.restitution;

    this.container.setScale(1.0);
    this.container.setAlpha(1.0);
    this.container.setVisible(true);
    this.updateTransform();
    this.setActiveTurn(false);
    this.updateImpactMarker(0, false);
  }

  public destroy(): void {
    this.scene.tweens.killTweensOf(this.container);
    if (this.body && this.scene.matter.world.has(this.body)) {
      this.scene.matter.world.remove(this.body);
    }
    if (this.container) {
      this.container.destroy();
    }
  }
}
