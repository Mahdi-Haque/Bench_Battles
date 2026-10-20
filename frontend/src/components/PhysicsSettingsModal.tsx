import React, { useState } from 'react';
import { DEFAULT_PHYSICS_CONFIG } from '../game/config';
import type { PhysicsConfig } from '../game/config';
import { soundManager } from '../game/audio';
import { X, RotateCcw, Sliders, Check } from 'lucide-react';

interface PhysicsSettingsModalProps {
  isOpen: boolean;
  currentConfig: PhysicsConfig;
  onApply: (newConfig: PhysicsConfig) => void;
  onClose: () => void;
}

export const PhysicsSettingsModal: React.FC<PhysicsSettingsModalProps> = ({
  isOpen,
  currentConfig,
  onApply,
  onClose,
}) => {
  const [config, setConfig] = useState<PhysicsConfig>({ ...currentConfig });

  if (!isOpen) return null;

  const handleChange = (key: keyof PhysicsConfig, val: number) => {
    const updated = { ...config, [key]: val };
    setConfig(updated);
    onApply(updated);
  };

  const resetDefaults = () => {
    soundManager.playButtonClick();
    setConfig({ ...DEFAULT_PHYSICS_CONFIG });
    onApply({ ...DEFAULT_PHYSICS_CONFIG });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-bold text-slate-100">Physics & Tabletop Tuner</h2>
          </div>
          <button
            onClick={() => {
              soundManager.playButtonClick();
              onClose();
            }}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">
          Tuning takes effect immediately on the live Matter.js tabletop simulation. Use this to test
          different table surfaces (e.g. slick glossy desk vs rough wooden bench).
        </p>

        <div className="flex flex-col gap-4 text-xs">
          {/* Surface Friction */}
          <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 flex flex-col gap-2">
            <div className="flex justify-between font-semibold text-slate-200">
              <span>Table Surface Friction</span>
              <span className="font-mono text-cyan-400 font-bold">{config.friction.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.02"
              max="0.30"
              step="0.01"
              value={config.friction}
              onChange={(e) => handleChange('friction', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
            <span className="text-[11px] text-slate-400">
              Controls sliding drag against the table surface. Lower = slicker ice-like glide.
            </span>
          </div>

          {/* Friction Air / Slide Drag */}
          <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 flex flex-col gap-2">
            <div className="flex justify-between font-semibold text-slate-200">
              <span>Linear & Angular Resistance (Air Drag)</span>
              <span className="font-mono text-cyan-400 font-bold">{config.frictionAir.toFixed(3)}</span>
            </div>
            <input
              type="range"
              min="0.005"
              max="0.060"
              step="0.002"
              value={config.frictionAir}
              onChange={(e) => handleChange('frictionAir', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
            <span className="text-[11px] text-slate-400">
              Gradually decelerates spinning and translation to achieve a realistic settle.
            </span>
          </div>

          {/* Restitution (Bounciness) */}
          <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 flex flex-col gap-2">
            <div className="flex justify-between font-semibold text-slate-200">
              <span>Collision Elasticity (Restitution)</span>
              <span className="font-mono text-amber-400 font-bold">{config.restitution.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.20"
              max="0.95"
              step="0.02"
              value={config.restitution}
              onChange={(e) => handleChange('restitution', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <span className="text-[11px] text-slate-400">
              0.2 = dull plastic thud; 0.95 = hyper-elastic snappy billiard-ball clack.
            </span>
          </div>

          {/* Max Impulse Strength */}
          <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 flex flex-col gap-2">
            <div className="flex justify-between font-semibold text-slate-200">
              <span>Max Flick Impulse Force</span>
              <span className="font-mono text-red-400 font-bold">{config.maxForce.toFixed(3)}</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.22"
              step="0.005"
              value={config.maxForce}
              onChange={(e) => handleChange('maxForce', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-red-400"
            />
            <span className="text-[11px] text-slate-400">
              Upper bound for 100% power shots.
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-slate-800">
          <button
            onClick={resetDefaults}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs flex items-center gap-1.5 border border-slate-700 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Defaults
          </button>

          <button
            onClick={() => {
              soundManager.playButtonClick();
              onClose();
            }}
            className="px-5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition"
          >
            <Check className="w-4 h-4" />
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
