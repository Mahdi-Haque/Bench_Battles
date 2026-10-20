import React from 'react';
import type { ShotParameters, GamePhase } from '../game/types';
import { soundManager } from '../game/audio';
import { Crosshair, Zap, RotateCcw, Compass, ArrowUpRight } from 'lucide-react';

interface AimingControlsProps {
  shotParams: ShotParameters;
  onUpdateParams: (params: Partial<ShotParameters>) => void;
  onFire: () => void;
  phase: GamePhase;
  activePlayerColor: string;
  activePlayerName: string;
}

export const AimingControls: React.FC<AimingControlsProps> = ({
  shotParams,
  onUpdateParams,
  onFire,
  phase,
  activePlayerColor,
  activePlayerName,
}) => {
  const isInputEnabled = phase === 'WAITING_FOR_AIM' || phase === 'AIMING';
  const angleDeg = Math.round((shotParams.angle * 180) / Math.PI) % 360;
  const normalizedDeg = angleDeg < 0 ? angleDeg + 360 : angleDeg;

  const handlePowerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const power = parseInt(e.target.value, 10);
    onUpdateParams({ power });
  };

  const handleImpactChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const impactOffset = parseFloat(e.target.value);
    onUpdateParams({ impactOffset });
  };

  const adjustAngle = (deltaDeg: number) => {
    soundManager.playButtonClick();
    const currentDeg = (shotParams.angle * 180) / Math.PI;
    const newRad = ((currentDeg + deltaDeg) * Math.PI) / 180;
    onUpdateParams({ angle: newRad });
  };

  // Torque explanation based on impact point offset
  let torqueDescription = 'Center of Mass: Direct linear impulse';
  let torqueColor = 'text-slate-400';
  if (shotParams.impactOffset < -0.15) {
    torqueDescription = 'Tail Impact: Generates high torque (spins tip outward)';
    torqueColor = 'text-cyan-400';
  } else if (shotParams.impactOffset > 0.15) {
    torqueDescription = 'Tip Impact: Spins rear cap clockwise in sweeping arc';
    torqueColor = 'text-amber-400';
  }

  return (
    <div className="w-full max-w-4xl mx-auto bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-xl p-4 shadow-xl">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-center">
        {/* 1. Shot Power Control */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-300">
            <span className="flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-400" />
              Impulse Power
            </span>
            <span
              className={`font-mono px-2 py-0.5 rounded text-sm font-bold ${
                shotParams.power > 75
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                  : shotParams.power > 45
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              }`}
            >
              {shotParams.power}%
            </span>
          </div>

          <input
            type="range"
            min="10"
            max="100"
            step="1"
            disabled={!isInputEnabled}
            value={shotParams.power}
            onChange={handlePowerChange}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500 disabled:opacity-40"
          />

          <div className="flex justify-between items-center text-[11px] text-slate-400">
            <button
              onClick={() => onUpdateParams({ power: 30 })}
              disabled={!isInputEnabled}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 transition"
            >
              Nudge (30%)
            </button>
            <button
              onClick={() => onUpdateParams({ power: 65 })}
              disabled={!isInputEnabled}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 transition"
            >
              Flick (65%)
            </button>
            <button
              onClick={() => onUpdateParams({ power: 95 })}
              disabled={!isInputEnabled}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 transition"
            >
              Smash (95%)
            </button>
          </div>
        </div>

        {/* 2. Impact Point Selector (along the pen body) */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-300">
            <span className="flex items-center gap-1.5">
              <Crosshair className="w-4 h-4 text-cyan-400" />
              Impact Point
            </span>
            <span className="font-mono text-xs px-1.5 py-0.5 bg-slate-800 rounded text-slate-300">
              {shotParams.impactOffset < -0.1
                ? 'Rear Tail'
                : shotParams.impactOffset > 0.1
                ? 'Front Tip'
                : 'Center'}
            </span>
          </div>

          {/* Pen schematic with slider */}
          <div className="relative py-1">
            <input
              type="range"
              min="-1.0"
              max="1.0"
              step="0.05"
              disabled={!isInputEnabled}
              value={shotParams.impactOffset}
              onChange={handleImpactChange}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400 disabled:opacity-40"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono mt-1">
              <span>Cap (-1.0)</span>
              <span>Center (0.0)</span>
              <span>Tip (+1.0)</span>
            </div>
          </div>

          <p className={`text-[11px] leading-tight font-medium ${torqueColor}`}>
            {torqueDescription}
          </p>
        </div>

        {/* 3. Aim Angle Fine Tuning & Shoot Action */}
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold uppercase">
              <Compass className="w-4 h-4 text-purple-400" />
              <span>Angle:</span>
              <span className="font-mono text-amber-400 font-bold">{normalizedDeg}°</span>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => adjustAngle(-5)}
                disabled={!isInputEnabled}
                className="px-2 py-0.5 text-xs font-mono font-bold bg-slate-800 hover:bg-slate-700 active:bg-slate-600 rounded text-slate-300 disabled:opacity-30 border border-slate-700"
                title="Rotate 5° Counter-Clockwise"
              >
                -5°
              </button>
              <button
                onClick={() => adjustAngle(5)}
                disabled={!isInputEnabled}
                className="px-2 py-0.5 text-xs font-mono font-bold bg-slate-800 hover:bg-slate-700 active:bg-slate-600 rounded text-slate-300 disabled:opacity-30 border border-slate-700"
                title="Rotate 5° Clockwise"
              >
                +5°
              </button>
            </div>
          </div>

          <button
            onClick={() => {
              soundManager.playButtonClick();
              onFire();
            }}
            disabled={!isInputEnabled}
            className={`w-full py-2.5 px-4 rounded-lg font-bold text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all duration-150 shadow-lg ${
              isInputEnabled
                ? 'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 shadow-amber-500/25 active:scale-[0.98] cursor-pointer'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            }`}
          >
            {phase === 'SIMULATING' ? (
              <span className="flex items-center gap-2">
                <RotateCcw className="w-4 h-4 animate-spin text-amber-400" />
                Pen In Motion...
              </span>
            ) : phase === 'ROUND_RESOLVING' ? (
              <span className="flex items-center gap-2">
                <RotateCcw className="w-4 h-4 animate-spin text-red-400" />
                Checking Table Edge...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <ArrowUpRight className="w-4 h-4 stroke-[3]" />
                Flick Pen! ({activePlayerName})
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: activePlayerColor }} />
          <span>Interactive tabletop: Drag backwards directly on the active pen to aim and release!</span>
        </span>
        <span className="hidden sm:inline text-slate-400">Matter.js Rigid-Body Rotational Physics</span>
      </div>
    </div>
  );
};
