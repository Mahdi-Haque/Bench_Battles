import { useState, useRef, useCallback } from 'react';
import { GameCanvas } from './components/GameCanvas';
import type { GameCanvasHandle } from './components/GameCanvas';
import { TopBar } from './components/TopBar';
import { AimingControls } from './components/AimingControls';
import { WinnerModal } from './components/WinnerModal';
import { PhysicsSettingsModal } from './components/PhysicsSettingsModal';
import { DEFAULT_PHYSICS_CONFIG, PLAYERS_SETUP } from './game/config';
import type { PhysicsConfig } from './game/config';
import type { MatchState, ShotParameters } from './game/types';
import { soundManager } from './game/audio';
import { Info, HelpCircle } from 'lucide-react';

export function App() {
  const canvasRef = useRef<GameCanvasHandle>(null);

  // Match & Turn State
  const [matchState, setMatchState] = useState<MatchState>({
    phase: 'WAITING_FOR_AIM',
    activePlayerId: PLAYERS_SETUP[0].id,
    turnNumber: 1,
    players: PLAYERS_SETUP,
    eliminatedIds: [],
    winner: null,
    isDraw: false,
  });

  // Shot Parameters
  const [shotParams, setShotParams] = useState<ShotParameters>({
    power: 55,
    angle: 0,
    impactOffset: 0.0,
  });

  // Physics Config & Modals
  const [physicsConfig, setPhysicsConfig] = useState<PhysicsConfig>({ ...DEFAULT_PHYSICS_CONFIG });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isInspectMode, setIsInspectMode] = useState(false);
  const [showHowToPlay, setShowHowToPlay] = useState(false);

  // Active Player Reference
  const activePlayer =
    PLAYERS_SETUP.find((p) => p.id === matchState.activePlayerId) ?? PLAYERS_SETUP[0];

  // Callbacks from Game Canvas
  const handleMatchStateChange = useCallback((newState: MatchState) => {
    setMatchState(newState);
    if (newState.phase === 'WAITING_FOR_AIM') {
      setIsInspectMode(false);
    }
  }, []);

  const handleAimUpdate = useCallback((newParams: ShotParameters) => {
    setShotParams(newParams);
  }, []);

  // Update shot parameters from UI controls
  const handleUpdateShotParams = (params: Partial<ShotParameters>) => {
    const updated = { ...shotParams, ...params };
    setShotParams(updated);
    canvasRef.current?.setShotParameters(updated);
  };

  const handleFireShot = () => {
    canvasRef.current?.fireShot();
  };

  const handleResetMatch = () => {
    setIsInspectMode(false);
    canvasRef.current?.resetMatch();
  };

  const handleApplyPhysics = (newConfig: PhysicsConfig) => {
    setPhysicsConfig(newConfig);
    canvasRef.current?.updatePhysicsConfig(newConfig);
  };

  return (
    <div className="min-h-screen w-full bg-[#080a0f] text-slate-100 flex flex-col items-center justify-between selection:bg-cyan-500 selection:text-black">
      {/* 1. Header Navigation */}
      <TopBar
        activePlayer={activePlayer}
        phase={matchState.phase}
        turnNumber={matchState.turnNumber}
        winner={matchState.winner}
        isDraw={matchState.isDraw}
        onReset={handleResetMatch}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* 2. Main Arena & Game Table */}
      <main className="w-full max-w-6xl px-4 py-3 flex flex-col items-center gap-3 flex-1 justify-center">
        {/* Table Canvas */}
        <div className="w-full flex justify-center">
          <GameCanvas
            ref={canvasRef}
            onMatchStateChange={handleMatchStateChange}
            onAimUpdate={handleAimUpdate}
          />
        </div>

        {/* Aiming & Power Control Bar */}
        <AimingControls
          shotParams={shotParams}
          onUpdateParams={handleUpdateShotParams}
          onFire={handleFireShot}
          phase={matchState.phase}
          activePlayerColor={activePlayer.textColor}
          activePlayerName={activePlayer.name}
        />

        {/* Quick Rules & Architecture Notice */}
        <div className="w-full max-w-4xl flex items-center justify-between text-xs text-slate-400 px-2 py-1">
          <button
            onClick={() => {
              soundManager.playButtonClick();
              setShowHowToPlay(!showHowToPlay);
            }}
            className="flex items-center gap-1.5 text-slate-300 hover:text-cyan-400 transition cursor-pointer"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span>{showHowToPlay ? 'Hide How to Play' : 'How to Play & Physics Guide'}</span>
          </button>

          <span className="flex items-center gap-1.5 text-slate-400">
            <Info className="w-3.5 h-3.5 text-slate-400" />
            <span>M1 Local Turn Prototype • React + Phaser Matter.js</span>
          </span>
        </div>

        {/* Expandable How To Play Drawer */}
        {showHowToPlay && (
          <div className="w-full max-w-4xl bg-slate-900/90 border border-slate-800 rounded-xl p-4 text-xs text-slate-300 grid grid-cols-1 md:grid-cols-3 gap-4 shadow-xl animate-in fade-in">
            <div className="flex flex-col gap-1.5">
              <h3 className="font-bold text-amber-400 uppercase tracking-wider">1. The Objective</h3>
              <p className="text-slate-400 leading-relaxed">
                Knock the opponent's pen completely off the tabletop while keeping your own pen safely on the desk surface!
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <h3 className="font-bold text-cyan-400 uppercase tracking-wider">2. Rotational Torque</h3>
              <p className="text-slate-400 leading-relaxed">
                Hitting off-center (Rear Cap or Front Tip) creates torque. Strike the tail to whip your pen's tip forward into the opponent!
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <h3 className="font-bold text-emerald-400 uppercase tracking-wider">3. Boundary Rules</h3>
              <p className="text-slate-400 leading-relaxed">
                Touching the outer amber border line is safe. A pen is only eliminated when its center of mass falls off into the void.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* 3. Victory / Draw Modal */}
      {!isInspectMode && (
        <WinnerModal
          winner={matchState.winner}
          isDraw={matchState.isDraw}
          turnNumber={matchState.turnNumber}
          onRestart={handleResetMatch}
          onClose={() => setIsInspectMode(true)}
        />
      )}

      {/* 4. Physics Parameters Tuning Drawer */}
      <PhysicsSettingsModal
        isOpen={isSettingsOpen}
        currentConfig={physicsConfig}
        onApply={handleApplyPhysics}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
}

export default App;
