import React, { useState } from 'react';
import type { PlayerSetup } from '../game/config';
import type { GamePhase } from '../game/types';
import { soundManager } from '../game/audio';
import { Volume2, VolumeX, Sliders, RotateCcw, ShieldAlert, Swords } from 'lucide-react';

interface TopBarProps {
  activePlayer: PlayerSetup;
  phase: GamePhase;
  turnNumber: number;
  winner: PlayerSetup | null;
  isDraw: boolean;
  onReset: () => void;
  onOpenSettings: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activePlayer,
  phase,
  turnNumber,
  winner,
  isDraw,
  onReset,
  onOpenSettings,
}) => {
  const [isMuted, setIsMuted] = useState(soundManager.getIsMuted());

  const toggleMute = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    soundManager.setMuted(nextMuted);
    if (!nextMuted) {
      soundManager.playButtonClick();
    }
  };

  return (
    <header className="w-full bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-4 py-3 flex items-center justify-between shadow-md">
      {/* Title & Branding */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 via-orange-600 to-red-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
          <Swords className="w-5 h-5 text-slate-950 stroke-[2.5]" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-black tracking-wider text-slate-100 uppercase">
              Bench Battles
            </h1>
            <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30">
              M1 Prototype
            </span>
          </div>
          <p className="text-xs text-slate-400 font-medium">Tabletop Pen-Fighting Physics</p>
        </div>
      </div>

      {/* Match Status / Turn Badge */}
      <div className="flex items-center gap-3">
        {winner ? (
          <div className="px-4 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-bold text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/10">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
            <span>Winner: {winner.name}!</span>
          </div>
        ) : isDraw ? (
          <div className="px-4 py-1.5 rounded-full bg-rose-500/20 border border-rose-500/40 text-rose-300 font-bold text-sm flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <span>Mutual Elimination (Draw)!</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-slate-800/90 border border-slate-700/80 px-4 py-1.5 rounded-full shadow-inner">
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full animate-pulse"
                style={{ backgroundColor: activePlayer.textColor }}
              />
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Turn {turnNumber}:
              </span>
              <span
                className="text-sm font-bold tracking-wide"
                style={{ color: activePlayer.textColor }}
              >
                {activePlayer.name}
              </span>
            </div>

            <div className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700">
              {phase === 'SIMULATING'
                ? 'Simulating...'
                : phase === 'ROUND_RESOLVING'
                ? 'Checking Edges'
                : 'Aiming'}
            </div>
          </div>
        )}
      </div>

      {/* Utilities: Audio, Settings, Reset */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleMute}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 border border-slate-700 transition"
          title={isMuted ? 'Unmute Sound' : 'Mute Sound'}
        >
          {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4 text-emerald-400" />}
        </button>

        <button
          onClick={() => {
            soundManager.playButtonClick();
            onOpenSettings();
          }}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 border border-slate-700 transition flex items-center gap-1.5 text-xs font-medium"
          title="Tune Physics Parameters"
        >
          <Sliders className="w-4 h-4 text-cyan-400" />
          <span className="hidden sm:inline">Physics</span>
        </button>

        <button
          onClick={() => {
            soundManager.playButtonClick();
            onReset();
          }}
          className="p-2 px-3 rounded-lg bg-slate-800 hover:bg-rose-950/40 hover:border-rose-700 active:bg-slate-600 text-slate-300 border border-slate-700 transition flex items-center gap-1.5 text-xs font-semibold"
          title="Reset Match to Starting Positions"
        >
          <RotateCcw className="w-4 h-4 text-amber-400" />
          <span className="hidden sm:inline">Reset</span>
        </button>
      </div>
    </header>
  );
};
