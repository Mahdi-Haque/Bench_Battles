import React from 'react';
import type { PlayerSetup } from '../game/config';
import { soundManager } from '../game/audio';
import { Trophy, RotateCcw, Eye, ShieldAlert } from 'lucide-react';

interface WinnerModalProps {
  winner: PlayerSetup | null;
  isDraw: boolean;
  turnNumber: number;
  onRestart: () => void;
  onClose: () => void;
}

export const WinnerModal: React.FC<WinnerModalProps> = ({
  winner,
  isDraw,
  turnNumber,
  onRestart,
  onClose,
}) => {
  if (!winner && !isDraw) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl p-6 shadow-2xl text-center relative overflow-hidden">
        {/* Glow backdrop */}
        <div
          className="absolute -top-24 left-1/2 -translate-x-1/2 w-48 h-48 rounded-full blur-3xl opacity-30"
          style={{ backgroundColor: winner?.textColor ?? '#ef4444' }}
        />

        {winner ? (
          <>
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-tr from-amber-500 to-yellow-300 flex items-center justify-center shadow-lg shadow-amber-500/30">
              <Trophy className="w-9 h-9 text-slate-950 stroke-[2.2]" />
            </div>

            <span className="text-xs font-bold uppercase tracking-widest text-amber-400">
              Victorious Pen!
            </span>
            <h2
              className="text-2xl font-black mt-1 tracking-tight"
              style={{ color: winner.textColor }}
            >
              {winner.name} Wins!
            </h2>
            <p className="text-sm text-slate-400 mt-2">
              Knocked the opponent off the tabletop in <span className="text-slate-200 font-bold">{turnNumber} turns</span>.
            </p>
          </>
        ) : (
          <>
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-9 h-9" />
            </div>
            <h2 className="text-2xl font-black text-rose-400 tracking-tight">Mutual Elimination!</h2>
            <p className="text-sm text-slate-400 mt-2">
              Both pens plunged off the table in the same collision round! It is a Draw.
            </p>
          </>
        )}

        {/* Action Buttons */}
        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => {
              soundManager.playButtonClick();
              onRestart();
            }}
            className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 font-bold uppercase tracking-wider text-xs flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 active:scale-95 transition cursor-pointer"
          >
            <RotateCcw className="w-4 h-4 stroke-[2.5]" />
            Play Again
          </button>

          <button
            onClick={() => {
              soundManager.playButtonClick();
              onClose();
            }}
            className="py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs flex items-center justify-center gap-2 border border-slate-700 active:scale-95 transition cursor-pointer"
          >
            <Eye className="w-4 h-4" />
            Inspect Table
          </button>
        </div>
      </div>
    </div>
  );
};
