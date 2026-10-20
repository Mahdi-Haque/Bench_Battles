import Phaser from 'phaser';
import {
  GAME_DIMENSIONS,
  DEFAULT_PHYSICS_CONFIG,
  PLAYERS_SETUP,
} from './config';
import type { PhysicsConfig, PlayerSetup } from './config';
import type { MatchState, ShotParameters, GamePhase } from './types';
import { Pen } from './Pen';
import { soundManager } from './audio';
import { isPenCenterInsideTable, calculatePredictedTrajectory } from './physicsUtils';

export interface TableSceneCallbacks {
  onMatchStateChange?: (state: MatchState) => void;
  onAimUpdate?: (params: ShotParameters) => void;
}

export class TableScene extends Phaser.Scene {
  private physicsConfig: PhysicsConfig = { ...DEFAULT_PHYSICS_CONFIG };
  private pens: Map<string, Pen> = new Map();
  private callbacks: TableSceneCallbacks = {};

  // Gameplay state
  private activePlayerIndex: number = 0;
  private phase: GamePhase = 'WAITING_FOR_AIM';
  private turnNumber: number = 1;
  private eliminatedPlayerIds: string[] = [];
  private winner: PlayerSetup | null = null;
  private isDraw: boolean = false;

  // Aiming parameters
  private shotParams: ShotParameters = {
    power: 55,
    angle: 0,
    impactOffset: 0.0, // center
  };

  // Drag interaction state
  private isDraggingAim: boolean = false;

  // Settling tracking
  private settleTimer: number = 0;
  private simulateTimer: number = 0;
  private roundResolveTimer: Phaser.Time.TimerEvent | null = null;

  // Visual layers
  private aimGraphics!: Phaser.GameObjects.Graphics;
  private tableEdgeGlow!: Phaser.GameObjects.Graphics;

  constructor() {
    super({ key: 'TableScene' });
  }

  public init(data: { callbacks?: TableSceneCallbacks; config?: Partial<PhysicsConfig> }): void {
    if (data.callbacks) {
      this.callbacks = data.callbacks;
    }
    if (data.config) {
      this.physicsConfig = { ...this.physicsConfig, ...data.config };
    }
  }

  public setCallbacks(callbacks: TableSceneCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  public create(): void {
    this.cameras.main.setBackgroundColor('#090b10');

    this.drawEnvironment();
    this.createPens();
    this.setupCollisions();
    this.setupInputHandlers();

    this.aimGraphics = this.add.graphics().setDepth(20);

    // Register lifecycle cleanup
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, this.shutdown, this);
    this.events.once(Phaser.Scenes.Events.DESTROY, this.shutdown, this);

    // Initial turn setup
    this.setTurn(0);
  }

  /**
   * Draw the classroom desk / wooden table surface and surroundings
   */
  private drawEnvironment(): void {
    const { width, height, table } = GAME_DIMENSIONS;

    // 1. Surrounding floor tiles / ambient vignette
    const floor = this.add.graphics();
    floor.fillStyle(0x0e111a, 1.0);
    floor.fillRect(0, 0, width, height);

    // Grid lines for floor texture
    floor.lineStyle(1, 0x161c2e, 0.4);
    for (let x = 0; x < width; x += 60) {
      floor.lineBetween(x, 0, x, height);
    }
    for (let y = 0; y < height; y += 60) {
      floor.lineBetween(0, y, width, y);
    }

    // 2. Table Drop Shadow
    const shadow = this.add.graphics();
    shadow.fillStyle(0x000000, 0.55);
    shadow.fillRoundedRect(
      table.left - 10,
      table.top + 14,
      table.width + 20,
      table.height + 20,
      table.cornerRadius + 4
    );

    // 3. Desk Outer Wooden Bevel Border
    const tableBorder = this.add.graphics();
    tableBorder.fillStyle(0x382216, 1.0); // Rich dark mahogany wood
    tableBorder.fillRoundedRect(
      table.left - table.borderWidth,
      table.top - table.borderWidth,
      table.width + table.borderWidth * 2,
      table.height + table.borderWidth * 2,
      table.cornerRadius + 6
    );

    // Border bevel highlight
    tableBorder.lineStyle(2, 0x5c3824, 0.9);
    tableBorder.strokeRoundedRect(
      table.left - table.borderWidth + 1,
      table.top - table.borderWidth + 1,
      table.width + table.borderWidth * 2 - 2,
      table.height + table.borderWidth * 2 - 2,
      table.cornerRadius + 5
    );

    // 4. Main Desk Surface
    const surface = this.add.graphics();
    // Warm school desk oak/cherry finish
    surface.fillStyle(0x4a2c1b, 1.0);
    surface.fillRoundedRect(table.left, table.top, table.width, table.height, table.cornerRadius);

    // Subtle wood grain planks
    surface.lineStyle(1, 0x3d2315, 0.35);
    const plankHeight = 56;
    for (let y = table.top + plankHeight; y < table.bottom; y += plankHeight) {
      surface.lineBetween(table.left + 8, y, table.right - 8, y);
    }

    // Classroom desk nostalgic scribbles / ruler marks
    surface.lineStyle(1, 0x331c10, 0.25);
    surface.lineBetween(table.left + 60, table.top + 40, table.left + 140, table.top + 40);
    surface.lineBetween(table.right - 180, table.bottom - 45, table.right - 80, table.bottom - 45);

    // 5. Table Perimeter Warning Edge
    this.tableEdgeGlow = this.add.graphics();
    this.tableEdgeGlow.lineStyle(2, 0xf59e0b, 0.3); // Soft amber perimeter warning
    this.tableEdgeGlow.strokeRoundedRect(table.left + 2, table.top + 2, table.width - 4, table.height - 4, table.cornerRadius - 2);

    // 6. Center Table Court Line (classic playground bench line)
    const centerLine = this.add.graphics();
    centerLine.lineStyle(2, 0xffffff, 0.08);
    centerLine.lineBetween(table.centerX, table.top + 16, table.centerX, table.bottom - 16);
    centerLine.strokeCircle(table.centerX, table.centerY, 70);
  }

  private createPens(): void {
    this.pens.clear();
    for (const player of PLAYERS_SETUP) {
      const pen = new Pen(this, player, this.physicsConfig);
      this.pens.set(player.id, pen);
    }
  }

  private setupCollisions(): void {
    this.matter.world.on('collisionstart', (event: Phaser.Physics.Matter.Events.CollisionStartEvent) => {
      event.pairs.forEach((pair) => {
        const bodyA = pair.bodyA as unknown as { penInstance?: Pen };
        const bodyB = pair.bodyB as unknown as { penInstance?: Pen };

        if (bodyA.penInstance && bodyB.penInstance) {
          // Pen-to-Pen collision
          const vA = bodyA.penInstance.body.velocity;
          const vB = bodyB.penInstance.body.velocity;
          const relSpeed = Math.hypot(vA.x - vB.x, vA.y - vB.y);

          soundManager.playCollision(relSpeed);

          // Support point with fallback to midpoint between pen bodies
          const contactX =
            pair.collision.supports[0]?.x ??
            (bodyA.penInstance.body.position.x + bodyB.penInstance.body.position.x) / 2;
          const contactY =
            pair.collision.supports[0]?.y ??
            (bodyA.penInstance.body.position.y + bodyB.penInstance.body.position.y) / 2;

          this.spawnCollisionSparks(contactX, contactY, relSpeed);

          // Subtle tactile camera micro-shake on heavy hits
          if (relSpeed > 7.0) {
            this.cameras.main.shake(80, 0.0025);
          }
        }
      });
    });
  }

  private spawnCollisionSparks(x: number, y: number, intensity: number = 2): void {
    if (!x || !y) return;
    const radius = Math.min(7, 3 + intensity * 0.35);
    const spark = this.add.graphics().setDepth(25);
    spark.fillStyle(0xfffbeb, 0.95);
    spark.fillCircle(x, y, radius);
    spark.lineStyle(1.5, 0xf59e0b, 0.85);
    spark.strokeCircle(x, y, radius * 2);

    this.tweens.add({
      targets: spark,
      alpha: 0,
      scaleX: 1.8,
      scaleY: 1.8,
      duration: 180,
      onComplete: () => spark.destroy(),
    });
  }

  private setupInputHandlers(): void {
    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      soundManager.init(); // Resume audio context on user gesture
      if (this.phase !== 'WAITING_FOR_AIM' && this.phase !== 'AIMING') return;

      const activePen = this.getActivePen();
      if (!activePen || activePen.state !== 'ON_TABLE') return;

      // Check if clicking near the active pen
      const penPos = activePen.body.position;
      const dist = Phaser.Math.Distance.Between(pointer.worldX, pointer.worldY, penPos.x, penPos.y);

      // If clicked near pen or anywhere during aiming
      if (dist < 100) {
        this.isDraggingAim = true;
        this.phase = 'AIMING';
        this.updateAimFromPointer(pointer);
        this.emitState();
      }
    });

    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (!this.isDraggingAim) return;
      this.updateAimFromPointer(pointer);
    });

    const handlePointerRelease = () => {
      if (!this.isDraggingAim) return;
      this.isDraggingAim = false;

      // If power is sufficient, fire the shot!
      if (this.shotParams.power >= 8) {
        this.fireShot();
      } else {
        // Return to waiting
        this.phase = 'WAITING_FOR_AIM';
        this.emitState();
      }
    };

    this.input.on('pointerup', handlePointerRelease);
    this.input.on('pointerupoutside', handlePointerRelease);
  }

  /**
   * Translates mouse/touch drag into power and angle (slingshot feel)
   */
  private updateAimFromPointer(pointer: Phaser.Input.Pointer): void {
    const activePen = this.getActivePen();
    if (!activePen) return;

    // Pull back from the impact point to aim forward
    const impactPoint = activePen.getImpactPointWorld(this.shotParams.impactOffset);
    const dx = impactPoint.x - pointer.worldX;
    const dy = impactPoint.y - pointer.worldY;
    const dragDistance = Math.hypot(dx, dy);

    // Aim angle points in direction of release
    const angle = Math.atan2(dy, dx);

    // Map drag distance (0 to 180px) to power (0 to 100%)
    const maxDrag = 180;
    const power = Math.min(100, Math.max(5, Math.round((dragDistance / maxDrag) * 100)));

    this.shotParams.angle = angle;
    this.shotParams.power = power;

    activePen.updateImpactMarker(this.shotParams.impactOffset, true);
    this.callbacks.onAimUpdate?.(this.shotParams);
  }

  public update(_time: number, delta: number): void {
    // 1. Update transforms of all pens
    for (const pen of this.pens.values()) {
      pen.updateTransform();

      // Play slide sound if moving fast
      if (this.phase === 'SIMULATING') {
        const speed = pen.getSpeed();
        if (speed > 1.8) {
          soundManager.playSlide(speed);
        }
      }
    }

    // 2. Render aiming vector on canvas
    this.renderAimVisuals();

    // 3. Monitor simulation settling and real-time edge crossing
    if (this.phase === 'SIMULATING') {
      this.simulateTimer += delta;

      // Real-time boundary check: eliminate pen the instant its center of mass leaves the table
      for (const [id, pen] of this.pens.entries()) {
        if (pen.state === 'ON_TABLE') {
          const { x, y } = pen.body.position;
          if (!isPenCenterInsideTable(x, y, GAME_DIMENSIONS.table)) {
            pen.eliminate();
            if (!this.eliminatedPlayerIds.includes(id)) {
              this.eliminatedPlayerIds.push(id);
            }
          }
        }
      }

      let allSettled = true;
      for (const pen of this.pens.values()) {
        if (pen.state === 'ON_TABLE') {
          const speed = pen.getSpeed();
          const angSpeed = pen.getAngularSpeed();
          if (speed > this.physicsConfig.settleSpeedThreshold || angSpeed > this.physicsConfig.settleAngularThreshold) {
            allSettled = false;
            break;
          }
        }
      }

      if (allSettled) {
        this.settleTimer += delta;
      } else {
        this.settleTimer = 0;
      }

      const settledSufficiently = this.settleTimer >= this.physicsConfig.settleDurationMs;
      const timedOut = this.simulateTimer >= this.physicsConfig.maxSimulateTimeoutMs;

      if (settledSufficiently || timedOut) {
        this.handleSimulationFinished();
      }
    }
  }

  /**
   * Draws the aim trajectory line, power gauge arrow, predicted trajectory dots, and torque indicator
   */
  private renderAimVisuals(): void {
    this.aimGraphics.clear();

    if (this.phase !== 'WAITING_FOR_AIM' && this.phase !== 'AIMING') return;

    const activePen = this.getActivePen();
    if (!activePen || activePen.state !== 'ON_TABLE') return;

    const impactPoint = activePen.getImpactPointWorld(this.shotParams.impactOffset);
    const { angle, power, impactOffset } = this.shotParams;

    // Arrow length proportional to power
    const arrowLength = 30 + (power / 100) * 120;
    const endX = impactPoint.x + Math.cos(angle) * arrowLength;
    const endY = impactPoint.y + Math.sin(angle) * arrowLength;

    // Color gradient based on power: Cyan/Green -> Amber -> Red
    let arrowColor = 0x10b981; // Emerald
    if (power > 45 && power <= 75) {
      arrowColor = 0xf59e0b; // Amber
    } else if (power > 75) {
      arrowColor = 0xef4444; // Red
    }

    // Main impulse vector line
    this.aimGraphics.lineStyle(3.5, arrowColor, 0.9);
    this.aimGraphics.lineBetween(impactPoint.x, impactPoint.y, endX, endY);

    // Arrowhead
    const headLen = 12;
    const headAngle1 = angle + Math.PI * 0.85;
    const headAngle2 = angle - Math.PI * 0.85;
    this.aimGraphics.fillStyle(arrowColor, 1.0);
    this.aimGraphics.fillTriangle(
      endX,
      endY,
      endX + Math.cos(headAngle1) * headLen,
      endY + Math.sin(headAngle1) * headLen,
      endX + Math.cos(headAngle2) * headLen,
      endY + Math.sin(headAngle2) * headLen
    );

    // Predicted trajectory dots along the slide vector
    const trajectoryPoints = calculatePredictedTrajectory(
      activePen.body.position.x,
      activePen.body.position.y,
      angle,
      power,
      GAME_DIMENSIONS.table,
      6
    );

    for (const pt of trajectoryPoints) {
      const dotColor = pt.isInsideTable ? arrowColor : 0xef4444; // Warning red if predicted past table boundary
      this.aimGraphics.fillStyle(dotColor, pt.alpha);
      this.aimGraphics.fillCircle(pt.x, pt.y, 3);
    }

    // Off-center torque spin indicator
    if (Math.abs(impactOffset) > 0.15) {
      const isClockwise = impactOffset > 0;
      this.drawTorqueIndicator(activePen.body.position.x, activePen.body.position.y, isClockwise);
    }
  }

  private drawTorqueIndicator(centerX: number, centerY: number, isClockwise: boolean): void {
    const radius = 34;
    this.aimGraphics.lineStyle(2, 0x38bdf8, 0.7);
    const startAngle = isClockwise ? 0 : Math.PI;
    const endAngle = isClockwise ? Math.PI * 0.8 : Math.PI * 1.8;

    this.aimGraphics.beginPath();
    this.aimGraphics.arc(centerX, centerY, radius, startAngle, endAngle, !isClockwise);
    this.aimGraphics.strokePath();
  }

  /**
   * Executes the shot with current parameters
   */
  public fireShot(): void {
    if (this.phase !== 'WAITING_FOR_AIM' && this.phase !== 'AIMING') return;

    const activePen = this.getActivePen();
    if (!activePen || activePen.state !== 'ON_TABLE') return;

    this.phase = 'SIMULATING';
    this.simulateTimer = 0;
    this.settleTimer = 0;
    this.isDraggingAim = false;

    // Clear aiming graphics and marker
    this.aimGraphics.clear();
    activePen.updateImpactMarker(0, false);
    activePen.setActiveTurn(false);

    // Apply physics impulse
    activePen.shoot(
      this.shotParams.power / 100,
      this.shotParams.angle,
      this.shotParams.impactOffset,
      this.physicsConfig
    );

    this.emitState();
  }

  /**
   * Called when all moving pens have completely settled
   */
  private handleSimulationFinished(): void {
    // 1. Halt micro-drifting
    for (const pen of this.pens.values()) {
      pen.stopMovement();
    }

    this.phase = 'ROUND_RESOLVING';
    this.emitState();

    // 2. Final boundary check for any remaining pens
    for (const [id, pen] of this.pens.entries()) {
      if (pen.state === 'ON_TABLE') {
        const { x, y } = pen.body.position;
        if (!isPenCenterInsideTable(x, y, GAME_DIMENSIONS.table)) {
          pen.eliminate();
          if (!this.eliminatedPlayerIds.includes(id)) {
            this.eliminatedPlayerIds.push(id);
          }
        }
      }
    }

    // Cancel any existing round resolve timer before starting a new one
    if (this.roundResolveTimer) {
      this.roundResolveTimer.destroy();
      this.roundResolveTimer = null;
    }

    // Allow 650ms for drop animation and sound before advancing state
    this.roundResolveTimer = this.time.delayedCall(650, () => {
      this.roundResolveTimer = null;
      this.evaluateRoundOutcome();
    });
  }

  /**
   * Evaluates if match has ended or who plays next
   */
  private evaluateRoundOutcome(): void {
    const survivingPens = Array.from(this.pens.values()).filter((p) => p.state === 'ON_TABLE');

    if (survivingPens.length === 1) {
      // 1 Winner!
      this.winner = survivingPens[0].player;
      this.phase = 'MATCH_OVER';
      soundManager.playVictory();
      this.emitState();
      return;
    }

    if (survivingPens.length === 0) {
      // Mutual elimination / Draw
      this.isDraw = true;
      this.phase = 'MATCH_OVER';
      soundManager.playElimination();
      this.emitState();
      return;
    }

    // More than 1 player alive -> proceed to next turn
    this.advanceTurn();
  }

  private advanceTurn(): void {
    this.turnNumber++;

    // Find next alive player
    let nextIndex = (this.activePlayerIndex + 1) % PLAYERS_SETUP.length;
    let attempts = 0;
    while (attempts < PLAYERS_SETUP.length) {
      const candidatePlayer = PLAYERS_SETUP[nextIndex];
      const pen = this.pens.get(candidatePlayer.id);
      if (pen && pen.state === 'ON_TABLE') {
        break;
      }
      nextIndex = (nextIndex + 1) % PLAYERS_SETUP.length;
      attempts++;
    }

    this.setTurn(nextIndex);
    soundManager.playTurnChime();
  }

  private setTurn(playerIndex: number): void {
    this.activePlayerIndex = playerIndex;
    this.phase = 'WAITING_FOR_AIM';

    for (const [id, pen] of this.pens.entries()) {
      const isTurn = id === PLAYERS_SETUP[playerIndex].id;
      pen.setActiveTurn(isTurn);
      pen.updateImpactMarker(this.shotParams.impactOffset, isTurn);
    }

    // Default aim pointing towards opponent
    const activePen = this.getActivePen();
    const opponent = this.getOpponentPen();
    if (activePen && opponent && activePen.state === 'ON_TABLE' && opponent.state === 'ON_TABLE') {
      const angle = Phaser.Math.Angle.Between(
        activePen.body.position.x,
        activePen.body.position.y,
        opponent.body.position.x,
        opponent.body.position.y
      );
      this.shotParams.angle = angle;
    }

    // Synchronize React's aiming controls with the newly auto-calculated aim angle
    this.callbacks.onAimUpdate?.(this.shotParams);

    this.emitState();
  }

  public resetMatch(): void {
    // Cancel any pending round resolution timer
    if (this.roundResolveTimer) {
      this.roundResolveTimer.destroy();
      this.roundResolveTimer = null;
    }

    this.winner = null;
    this.isDraw = false;
    this.eliminatedPlayerIds = [];
    this.turnNumber = 1;
    this.isDraggingAim = false;
    this.settleTimer = 0;
    this.simulateTimer = 0;

    for (const pen of this.pens.values()) {
      pen.reset(this.physicsConfig);
    }

    this.setTurn(0);
  }

  public updatePhysicsConfig(newConfig: Partial<PhysicsConfig>): void {
    this.physicsConfig = { ...this.physicsConfig, ...newConfig };
    for (const pen of this.pens.values()) {
      if (pen.body) {
        pen.body.friction = this.physicsConfig.friction;
        pen.body.frictionAir = this.physicsConfig.frictionAir;
        pen.body.restitution = this.physicsConfig.restitution;
      }
    }
  }

  public setShotParameters(params: Partial<ShotParameters>): void {
    this.shotParams = { ...this.shotParams, ...params };
    const activePen = this.getActivePen();
    if (activePen && (this.phase === 'WAITING_FOR_AIM' || this.phase === 'AIMING')) {
      activePen.updateImpactMarker(this.shotParams.impactOffset, true);
    }
  }

  public getShotParameters(): ShotParameters {
    return { ...this.shotParams };
  }

  private getActivePen(): Pen | undefined {
    return this.pens.get(PLAYERS_SETUP[this.activePlayerIndex].id);
  }

  private getOpponentPen(): Pen | undefined {
    const oppIndex = (this.activePlayerIndex + 1) % PLAYERS_SETUP.length;
    return this.pens.get(PLAYERS_SETUP[oppIndex].id);
  }

  public shutdown(): void {
    if (this.roundResolveTimer) {
      this.roundResolveTimer.destroy();
      this.roundResolveTimer = null;
    }
    this.matter.world.off('collisionstart');
    this.input.off('pointerdown');
    this.input.off('pointermove');
    this.input.off('pointerup');
    this.input.off('pointerupoutside');
    for (const pen of this.pens.values()) {
      pen.destroy();
    }
    this.pens.clear();
  }

  private emitState(): void {
    const state: MatchState = {
      phase: this.phase,
      activePlayerId: PLAYERS_SETUP[this.activePlayerIndex].id,
      turnNumber: this.turnNumber,
      players: PLAYERS_SETUP,
      eliminatedIds: [...this.eliminatedPlayerIds],
      winner: this.winner,
      isDraw: this.isDraw,
      lastShot: {
        playerId: PLAYERS_SETUP[this.activePlayerIndex].id,
        power: this.shotParams.power,
        angle: this.shotParams.angle,
        impactOffset: this.shotParams.impactOffset,
      },
    };

    this.callbacks.onMatchStateChange?.(state);
  }
}
