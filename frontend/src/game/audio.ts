/**
 * Web Audio API Procedural Sound Engine
 * Generates all gameplay sounds dynamically with zero external asset dependencies,
 * zero licensing risks, realistic physical variation, and rate-limiting.
 */

class SoundEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private sfxGain: GainNode | null = null;
  private isMuted: boolean = false;
  private masterVolume: number = 0.8;
  private sfxVolume: number = 0.9;
  private lastCollisionTime: number = 0;
  private lastSlideTime: number = 0;

  constructor() {
    // AudioContext will be initialized on first user interaction
  }

  public init(): void {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') {
        this.ctx.resume().catch(() => {});
      }
      return;
    }

    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.sfxGain = this.ctx.createGain();

      this.masterGain.gain.setValueAtTime(this.isMuted ? 0 : this.masterVolume, this.ctx.currentTime);
      this.sfxGain.gain.setValueAtTime(this.sfxVolume, this.ctx.currentTime);

      this.sfxGain.connect(this.masterGain);
      this.masterGain.connect(this.ctx.destination);
    } catch (e) {
      console.warn('Web Audio API not supported in this browser.', e);
    }
  }

  public setMasterVolume(val: number): void {
    this.masterVolume = Math.max(0, Math.min(1, val));
    if (this.masterGain && this.ctx && !this.isMuted) {
      this.masterGain.gain.setTargetAtTime(this.masterVolume, this.ctx.currentTime, 0.05);
    }
  }

  public setSfxVolume(val: number): void {
    this.sfxVolume = Math.max(0, Math.min(1, val));
    if (this.sfxGain && this.ctx) {
      this.sfxGain.gain.setTargetAtTime(this.sfxVolume, this.ctx.currentTime, 0.05);
    }
  }

  public setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(this.isMuted ? 0 : this.masterVolume, this.ctx.currentTime, 0.03);
    }
  }

  public getMasterVolume(): number {
    return this.masterVolume;
  }

  public getSfxVolume(): number {
    return this.sfxVolume;
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  /**
   * Helper to ensure context is ready
   */
  private ensureReady(): boolean {
    this.init();
    if (!this.ctx || !this.sfxGain) return false;
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return true;
  }

  /**
   * UI Button Click
   */
  public playButtonClick(): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(1400, now);
    osc.frequency.exponentialRampToValueAtTime(700, now + 0.04);

    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

    osc.connect(gain);
    gain.connect(this.sfxGain!);

    osc.start(now);
    osc.stop(now + 0.04);
  }

  /**
   * Flick sound when a shot is released (finger/cue flick on pen body)
   */
  public playFlick(powerNormalized: number): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    const clampedPower = Math.max(0.1, Math.min(1.0, powerNormalized));

    // Transient snap (casing impact)
    const osc = ctx.createOscillator();
    const oscGain = ctx.createGain();

    osc.type = 'sine';
    const baseFreq = 450 + clampedPower * 400;
    osc.frequency.setValueAtTime(baseFreq, now);
    osc.frequency.exponentialRampToValueAtTime(120, now + 0.06);

    const volume = 0.2 + clampedPower * 0.45;
    oscGain.gain.setValueAtTime(volume, now);
    oscGain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);

    // Filtered noise click for crisp finger skin-on-plastic snap
    const bufferSize = Math.floor(ctx.sampleRate * 0.04);
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const output = noiseBuffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      output[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.25));
    }

    const whiteNoise = ctx.createBufferSource();
    whiteNoise.buffer = noiseBuffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(1800 + clampedPower * 1200, now);
    filter.Q.setValueAtTime(2.5, now);

    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(volume * 0.6, now);
    noiseGain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

    osc.connect(oscGain);
    oscGain.connect(this.sfxGain!);

    whiteNoise.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(this.sfxGain!);

    osc.start(now);
    osc.stop(now + 0.08);
    whiteNoise.start(now);
  }

  /**
   * Pen-to-Pen or Pen-to-Surface Collision
   * Intensity: 0.1 (gentle nudge) to 10+ (high speed smash)
   */
  public playCollision(intensity: number): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    // Throttle collisions to avoid machine-gun clicking during continuous contacts
    if (now - this.lastCollisionTime < 0.08) return;
    this.lastCollisionTime = now;

    const normalizedIntensity = Math.min(1.0, Math.max(0.05, intensity / 8));
    const isHardClack = intensity > 2.5;

    // Resonant plastic body tone
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();

    osc1.type = 'triangle';
    osc2.type = 'sine';

    // Plastic clack frequencies
    const freq1 = isHardClack ? 2100 + Math.random() * 300 : 1400 + Math.random() * 200;
    const freq2 = isHardClack ? 3300 + Math.random() * 400 : 2200 + Math.random() * 300;

    osc1.frequency.setValueAtTime(freq1, now);
    osc1.frequency.exponentialRampToValueAtTime(freq1 * 0.4, now + 0.04);

    osc2.frequency.setValueAtTime(freq2, now);
    osc2.frequency.exponentialRampToValueAtTime(freq2 * 0.35, now + 0.03);

    const vol = Math.min(0.8, 0.15 + normalizedIntensity * 0.6);
    const duration = isHardClack ? 0.055 : 0.035;

    gain.gain.setValueAtTime(vol, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(this.sfxGain!);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + duration);
    osc2.stop(now + duration);
  }

  /**
   * Subtle pen glide / slide across the tabletop
   */
  public playSlide(speed: number): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    if (now - this.lastSlideTime < 0.18) return;
    this.lastSlideTime = now;

    if (speed < 1.0) return;

    const duration = 0.12;
    const bufferSize = Math.floor(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);

    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * 0.3;
    }

    const noise = ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(800 + Math.min(speed * 120, 1500), now);
    filter.Q.setValueAtTime(1.8, now);

    const gain = ctx.createGain();
    const vol = Math.min(0.2, (speed / 15) * 0.2);
    gain.gain.setValueAtTime(vol, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.sfxGain!);

    noise.start(now);
  }

  /**
   * Pen drops off table edge
   */
  public playTableFall(): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    // Edge clatter
    const edgeOsc = ctx.createOscillator();
    const edgeGain = ctx.createGain();
    edgeOsc.type = 'sawtooth';
    edgeOsc.frequency.setValueAtTime(520, now);
    edgeOsc.frequency.exponentialRampToValueAtTime(140, now + 0.1);
    edgeGain.gain.setValueAtTime(0.35, now);
    edgeGain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

    edgeOsc.connect(edgeGain);
    edgeGain.connect(this.sfxGain!);
    edgeOsc.start(now);
    edgeOsc.stop(now + 0.12);

    // Deep drop / whoosh as it falls through air
    const dropOsc = ctx.createOscillator();
    const dropGain = ctx.createGain();
    dropOsc.type = 'sine';
    dropOsc.frequency.setValueAtTime(280, now + 0.05);
    dropOsc.frequency.exponentialRampToValueAtTime(50, now + 0.55);

    dropGain.gain.setValueAtTime(0.001, now);
    dropGain.gain.setValueAtTime(0.4, now + 0.06);
    dropGain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

    dropOsc.connect(dropGain);
    dropGain.connect(this.sfxGain!);
    dropOsc.start(now + 0.05);
    dropOsc.stop(now + 0.55);
  }

  /**
   * Turn switch chime (pleasant 2-tone alert)
   */
  public playTurnChime(): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    const playTone = (freq: number, start: number, duration: number, vol: number) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.001, start);
      gain.gain.linearRampToValueAtTime(vol, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);

      osc.connect(gain);
      gain.connect(this.sfxGain!);

      osc.start(start);
      osc.stop(start + duration);
    };

    // E5 (659Hz) -> B5 (987Hz)
    playTone(659.25, now, 0.22, 0.22);
    playTone(987.77, now + 0.1, 0.35, 0.25);
  }

  /**
   * Player eliminated cue (descending dramatic motif)
   */
  public playElimination(): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    const notes = [440, 370, 311]; // A4 -> F#4 -> Eb4
    notes.forEach((freq, idx) => {
      const start = now + idx * 0.12;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.28, start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.3);

      osc.connect(gain);
      gain.connect(this.sfxGain!);

      osc.start(start);
      osc.stop(start + 0.3);
    });
  }

  /**
   * Match victory fanfare (ascending triumphant arpeggio)
   */
  public playVictory(): void {
    if (!this.ensureReady() || this.isMuted) return;
    const ctx = this.ctx!;
    const now = ctx.currentTime;

    // C5, E5, G5, C6 triumphant chord arpeggio
    const chord = [523.25, 659.25, 783.99, 1046.5];
    chord.forEach((freq, idx) => {
      const start = now + idx * 0.14;
      const duration = idx === chord.length - 1 ? 0.9 : 0.35;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.001, start);
      gain.gain.linearRampToValueAtTime(0.3, start + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);

      osc.connect(gain);
      gain.connect(this.sfxGain!);

      osc.start(start);
      osc.stop(start + duration);
    });
  }
}

export const soundManager = new SoundEngine();
