import type { PlayerSetup } from './config';

export type GamePhase =
  | 'WAITING_FOR_AIM'
  | 'AIMING'
  | 'SIMULATING'
  | 'ROUND_RESOLVING'
  | 'MATCH_OVER';

export interface ShotParameters {
  power: number; // 0 to 100
  angle: number; // In radians (direction the pen will be pushed toward)
  impactOffset: number; // -1.0 (rear cap) to +1.0 (front tip), 0 is center of mass
}

export type PenState = 'ON_TABLE' | 'FALLING' | 'ELIMINATED';

export interface PenData {
  playerId: string;
  state: PenState;
  position: { x: number; y: number };
  angle: number;
  velocity: { x: number; y: number };
  angularVelocity: number;
}

export interface MatchState {
  phase: GamePhase;
  activePlayerId: string;
  turnNumber: number;
  players: PlayerSetup[];
  eliminatedIds: string[];
  winner: PlayerSetup | null;
  isDraw: boolean;
  lastShot?: {
    playerId: string;
    power: number;
    angle: number;
    impactOffset: number;
  };
}

export interface SoundConfig {
  masterVolume: number; // 0.0 to 1.0
  sfxVolume: number; // 0.0 to 1.0
  muted: boolean;
}
