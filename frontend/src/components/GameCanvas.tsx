import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import Phaser from 'phaser';
import { GAME_DIMENSIONS } from '../game/config';
import type { PhysicsConfig } from '../game/config';
import { TableScene } from '../game/TableScene';
import type { TableSceneCallbacks } from '../game/TableScene';
import type { MatchState, ShotParameters } from '../game/types';


export interface GameCanvasHandle {
  fireShot: () => void;
  resetMatch: () => void;
  setShotParameters: (params: Partial<ShotParameters>) => void;
  updatePhysicsConfig: (config: Partial<PhysicsConfig>) => void;
}

interface GameCanvasProps {
  onMatchStateChange: (state: MatchState) => void;
  onAimUpdate: (params: ShotParameters) => void;
}

export const GameCanvas = forwardRef<GameCanvasHandle, GameCanvasProps>(
  ({ onMatchStateChange, onAimUpdate }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const gameRef = useRef<Phaser.Game | null>(null);
    const sceneRef = useRef<TableScene | null>(null);

    useImperativeHandle(ref, () => ({
      fireShot: () => {
        sceneRef.current?.fireShot();
      },
      resetMatch: () => {
        sceneRef.current?.resetMatch();
      },
      setShotParameters: (params: Partial<ShotParameters>) => {
        sceneRef.current?.setShotParameters(params);
      },
      updatePhysicsConfig: (config: Partial<PhysicsConfig>) => {
        sceneRef.current?.updatePhysicsConfig(config);
      },
    }));

    useEffect(() => {
      if (!containerRef.current) return;

      const callbacks: TableSceneCallbacks = {
        onMatchStateChange,
        onAimUpdate,
      };

      const scene = new TableScene();
      sceneRef.current = scene;

      const config: Phaser.Types.Core.GameConfig = {
        type: Phaser.AUTO,
        parent: containerRef.current,
        width: GAME_DIMENSIONS.width,
        height: GAME_DIMENSIONS.height,
        backgroundColor: '#090b10',
        scale: {
          mode: Phaser.Scale.FIT,
          autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        physics: {
          default: 'matter',
          matter: {
            gravity: { x: 0, y: 0 }, // Top-down table has zero gravity
            debug: false,
          },
        },
        scene: [scene],
      };

      const game = new Phaser.Game(config);
      gameRef.current = game;

      // Pass initial callbacks to scene when ready
      game.events.once('ready', () => {
        scene.init({ callbacks });
      });

      return () => {
        game.destroy(true);
        gameRef.current = null;
        sceneRef.current = null;
      };
    }, []);

    return (
      <div className="relative w-full aspect-[1200/750] max-h-[72vh] flex items-center justify-center rounded-xl overflow-hidden shadow-2xl border border-slate-800 bg-[#090b10]">
        <div ref={containerRef} className="w-full h-full flex items-center justify-center" />
      </div>
    );
  }
);

GameCanvas.displayName = 'GameCanvas';
