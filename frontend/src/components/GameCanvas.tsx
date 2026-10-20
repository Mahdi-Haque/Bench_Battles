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

    const callbacksRef = useRef<TableSceneCallbacks>({
      onMatchStateChange,
      onAimUpdate,
    });

    // Keep callbacks updated dynamically
    useEffect(() => {
      callbacksRef.current = {
        onMatchStateChange,
        onAimUpdate,
      };
      sceneRef.current?.setCallbacks(callbacksRef.current);
    }, [onMatchStateChange, onAimUpdate]);

    useEffect(() => {
      const container = containerRef.current;
      if (!container) return;

      // Clean any stale child canvases (e.g. from React 19 StrictMode re-mounts)
      container.innerHTML = '';

      const callbacks: TableSceneCallbacks = {
        onMatchStateChange: (state) => callbacksRef.current.onMatchStateChange?.(state),
        onAimUpdate: (params) => callbacksRef.current.onAimUpdate?.(params),
      };

      const scene = new TableScene();
      sceneRef.current = scene;

      const config: Phaser.Types.Core.GameConfig = {
        type: Phaser.AUTO,
        parent: container,
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
        if (container) {
          container.innerHTML = '';
        }
      };
    }, []);

    return (
      <div className="relative w-full aspect-[1200/750] max-h-[72vh] rounded-xl overflow-hidden shadow-2xl border border-slate-800 bg-[#090b10]">
        <div ref={containerRef} className="w-full h-full" />
      </div>
    );
  }
);

GameCanvas.displayName = 'GameCanvas';
