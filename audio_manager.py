"""
audio_manager.py - GestureVerse procedural audio system.

Design goals
------------
* No continuous looping SFX during normal gameplay.
* Boost: a single short transient fired at most once per second, not a
  continuous laser.  The particle emitter still fires at 25 Hz for visuals;
  audio fires only on the *leading edge* of the pinch gesture and then
  has a long cooldown.
* Ambient music: a gentle multi-layer pad (two detuned sine waves + a very
  low sub-bass) that loops seamlessly with no click at the join point.
* All gameplay SFX are short, pleasant, and spaced well apart.
* Default SFX volume: 35 %.  Master: 100 %.  Music: 28 %.

Public API (unchanged)
----------------------
  SoundManager()
  .play(name)             – fire a named one-shot SFX
  .set_master_volume(v)
  .set_sfx_volume(v)
  .set_music_volume(v)
  .toggle_mute() -> bool
  .muted  (property)

Sound catalogue
---------------
  collect   – bright chime, orb collected
  combo2    – ascending two-note chime, 2× streak
  combo5    – richer chord, 5× streak (only fires at exactly 5)
  boost     – single soft whoosh on pinch gesture START (long cooldown)
  levelup   – warm ascending arpeggio
  achieve   – triumphant bell tone
  powerup   – rising shimmer, power-up collected
  shield    – soft crystalline ping
  slowmo    – gentle pitch-bend down
  click     – UI confirm click
  reset     – short descending blip
"""

import array
import math
import random
import time
import pygame
from typing import Dict, List, Optional


# ══════════════════════════════════════════════════════════════════════ #
#  Low-level wave builder
# ══════════════════════════════════════════════════════════════════════ #
_SR = 22050   # sample rate used throughout


def _gen_wave(
    freq: float,
    duration: float,
    waveform: str = "sine",
    amplitude: float = 0.5,
    attack: float = 0.01,
    decay: float = 0.08,
    sustain: float = 0.55,
    release: float = 0.12,
    freq_sweep: float = 0.0,
    noise_mix: float = 0.0,
    sample_rate: int = _SR,
) -> pygame.mixer.Sound:
    """
    Synthesise a mono ADSR sound and return a stereo pygame.mixer.Sound.

    Parameters match the old API exactly so call-sites don't change.
    """
    n = int(sample_rate * duration)
    a_end = max(1, int(attack * sample_rate))
    d_end = a_end + max(0, int(decay * sample_rate))
    r_start = max(d_end, n - max(1, int(release * sample_rate)))
    max_s = 32767

    mono: List[int] = []
    for i in range(n):
        t = i / sample_rate
        f = freq + freq_sweep * t
        ph = 2.0 * math.pi * f * t

        if waveform == "sine":
            raw = math.sin(ph)
        elif waveform == "square":
            raw = 1.0 if math.sin(ph) >= 0 else -1.0
        elif waveform == "sawtooth":
            raw = 2.0 * ((f * t) % 1.0) - 1.0
        elif waveform == "triangle":
            raw = 2.0 * abs(2.0 * ((f * t) % 1.0) - 1.0) - 1.0
        else:
            raw = math.sin(ph)

        if noise_mix > 0.0:
            raw = raw * (1.0 - noise_mix) + \
                random.uniform(-1.0, 1.0) * noise_mix

        # ADSR envelope
        if i < a_end:
            env = i / a_end
        elif i < d_end:
            env = 1.0 - (i - a_end) / max(d_end - a_end, 1) * (1.0 - sustain)
        elif i >= r_start:
            env = sustain * (1.0 - (i - r_start) / max(n - r_start, 1))
        else:
            env = sustain

        mono.append(max(-max_s, min(max_s, int(raw * env * amplitude * max_s))))

    # Stereo interleave
    stereo = array.array("h")
    for s in mono:
        stereo.append(s)
        stereo.append(s)
    return pygame.mixer.Sound(buffer=bytes(stereo))


def _mix_waves(waves: List[array.array], amplitude: float = 0.5) -> pygame.mixer.Sound:
    """
    Sum several equal-length mono int arrays into one normalised stereo Sound.
    Each wave is a plain list/array of int samples [-32767, 32767].
    """
    n = len(waves[0])
    k = len(waves)
    max_s = 32767
    stereo = array.array("h")
    for i in range(n):
        mix = sum(w[i] for w in waves) / k
        s = max(-max_s, min(max_s, int(mix * amplitude)))
        stereo.append(s)
        stereo.append(s)
    return pygame.mixer.Sound(buffer=bytes(stereo))


def _raw_mono(
    freq: float,
    duration: float,
    waveform: str = "sine",
    amplitude: float = 1.0,
    freq_sweep: float = 0.0,
    sample_rate: int = _SR,
) -> List[int]:
    """Return a raw list of int16 samples (no envelope) for mixing."""
    n = int(sample_rate * duration)
    max_s = 32767
    out = []
    for i in range(n):
        t = i / sample_rate
        f = freq + freq_sweep * t
        ph = 2.0 * math.pi * f * t
        if waveform == "sine":
            raw = math.sin(ph)
        elif waveform == "triangle":
            raw = 2.0 * abs(2.0 * ((f * t) % 1.0) - 1.0) - 1.0
        else:
            raw = math.sin(ph)
        out.append(int(raw * amplitude * max_s))
    return out


# ══════════════════════════════════════════════════════════════════════ #
#  Ambient pad builder
# ══════════════════════════════════════════════════════════════════════ #
def _build_ambient_pad(music_vol: float, master_vol: float) -> pygame.mixer.Sound:
    """
    Seamlessly looping ambient pad: two detuned sine layers + sub bass.

    Strategy for click-free looping:
    - Choose a duration that is an exact integer multiple of the period
      of the lowest frequency used, so the waveform returns to exactly
      zero at the loop boundary.
    - Use a very long slow-attack/slow-release envelope that stays near
      the sustain level across the whole clip — the join is inaudible.

    The pad is 4 seconds long.  55 Hz period = 1/55 s ≈ 0.0182 s.
    4 s / 0.0182 s ≈ 220 complete cycles → exact loop.
    """
    duration = 4.0          # seconds
    n = int(_SR * duration)
    max_s = 32767

    # Three layers: root (55 Hz), fifth above (82.5 Hz), subtle detuned (56.2 Hz)
    freqs = [55.0, 82.5, 56.2]
    layer_amp = [0.45, 0.20, 0.15]

    # Fade-in / fade-out over 10 % of the clip to hide any residual click
    fade_samp = int(n * 0.10)

    mono: List[int] = [0] * n
    for freq, amp in zip(freqs, layer_amp):
        for i in range(n):
            t = i / _SR
            raw = math.sin(2.0 * math.pi * freq * t) * amp
            mono[i] += int(raw * max_s)

    # Apply fade window
    for i in range(fade_samp):
        frac = i / fade_samp
        mono[i] = int(mono[i] * frac)
        mono[n-1-i] = int(mono[n-1-i] * frac)

    # Clip and build stereo
    stereo = array.array("h")
    for s in mono:
        stereo.append(max(-max_s, min(max_s, s)))
        stereo.append(max(-max_s, min(max_s, s)))

    snd = pygame.mixer.Sound(buffer=bytes(stereo))
    snd.set_volume(music_vol * master_vol)
    return snd


# ══════════════════════════════════════════════════════════════════════ #
#  SoundManager
# ══════════════════════════════════════════════════════════════════════ #
class SoundManager:
    """
    Central audio hub.

    Cooldown policy
    ---------------
    Every sound has a minimum gap between plays.  High-frequency triggers
    (boost, collect) have long cooldowns so they cannot spam the mixer.
    One-shot celebratory sounds (levelup, achieve) have no cooldown because
    they fire rarely by nature.

    Channel policy
    --------------
    SFX are played on a dedicated channel pool (channels 1-7).
    The ambient pad occupies channel 0 exclusively.
    Celebratory sounds (levelup, achieve) use channel 7 and stop whatever
    was there — they are important enough to cut through.
    """

    # ── Sound definitions ────────────────────────────────────────────── #
    # Only sounds that are actually called from main.py are defined here.
    # Removed: bounce, gesture, hover (defined but never called).
    # Removed: the continuous "boost" laser loop — replaced with a single
    #          soft whoosh that fires only on pinch gesture START.
    SOUNDS: Dict[str, dict] = {

        # ── Orb collected: bright ascending chime ──────────────────────
        # Short, pleasant, clearly signals a reward.
        "collect": dict(
            freq=660, duration=0.16, waveform="sine",
            attack=0.004, decay=0.04, sustain=0.45, release=0.10,
            freq_sweep=180, amplitude=0.52,
        ),

        # ── Combo × 2: two-note ascending ping ────────────────────────
        # Noticeably different from collect so the player feels the streak.
        "combo2": dict(
            freq=784, duration=0.20, waveform="triangle",
            attack=0.004, decay=0.05, sustain=0.50, release=0.12,
            freq_sweep=196, amplitude=0.48,
        ),

        # ── Combo × 5+: richer reward tone ────────────────────────────
        # Only fires at exactly the 5× milestone (controlled in main.py).
        "combo5": dict(
            freq=1047, duration=0.28, waveform="sine",
            attack=0.005, decay=0.07, sustain=0.60, release=0.16,
            freq_sweep=262, amplitude=0.52,
        ),

        # ── Boost: single soft whoosh on pinch START ───────────────────
        # Triangle waveform with downward sweep = aerodynamic, not laser.
        # Cooldown of 1.2 s means it plays at most once per second even if
        # the player holds the pinch for a long time.
        "boost": dict(
            freq=320, duration=0.22, waveform="triangle",
            attack=0.008, decay=0.06, sustain=0.30, release=0.14,
            freq_sweep=-160, amplitude=0.38,
        ),

        # ── Level up: warm ascending arpeggio ─────────────────────────
        "levelup": dict(
            freq=440, duration=0.50, waveform="triangle",
            attack=0.01, decay=0.09, sustain=0.75, release=0.22,
            freq_sweep=440, amplitude=0.52,
        ),

        # ── Achievement: clear bell tone ───────────────────────────────
        "achieve": dict(
            freq=523, duration=0.55, waveform="sine",
            attack=0.008, decay=0.09, sustain=0.70, release=0.28,
            freq_sweep=523, amplitude=0.50,
        ),

        # ── Power-up collected: rising shimmer ─────────────────────────
        "powerup": dict(
            freq=330, duration=0.30, waveform="triangle",
            attack=0.005, decay=0.07, sustain=0.60, release=0.18,
            freq_sweep=440, amplitude=0.46,
        ),

        # ── Shield activated: crystalline ping ─────────────────────────
        "shield": dict(
            freq=880, duration=0.22, waveform="sine",
            attack=0.006, decay=0.05, sustain=0.40, release=0.16,
            freq_sweep=220, amplitude=0.36,
        ),

        # ── Slow-mo: gentle pitch-bend downward ────────────────────────
        "slowmo": dict(
            freq=280, duration=0.35, waveform="sine",
            attack=0.015, decay=0.12, sustain=0.45, release=0.18,
            freq_sweep=-140, amplitude=0.34,
        ),

        # ── UI: confirm click ──────────────────────────────────────────
        "click": dict(
            freq=660, duration=0.07, waveform="triangle",
            attack=0.001, decay=0.02, sustain=0.20, release=0.04,
            amplitude=0.28,
        ),

        # ── UI: score/game reset ───────────────────────────────────────
        "reset": dict(
            freq=220, duration=0.22, waveform="sine",
            attack=0.004, decay=0.07, sustain=0.35, release=0.14,
            freq_sweep=-110, amplitude=0.32,
        ),
    }

    # Minimum seconds between successive plays of the same sound.
    # Absent entry = no cooldown (safe because those fire rarely by design).
    _COOLDOWNS: Dict[str, float] = {
        "collect":  0.08,   # fast player can collect multiple orbs quickly
        "combo2":   0.40,   # let the chime finish before re-triggering
        "combo5":   1.00,   # rare milestone — sounds cheap if it spams
        "boost":    1.20,   # fires only on pinch START; long gap prevents loop
        "powerup":  0.50,
        "shield":   0.80,
        "slowmo":   1.00,
        "click":    0.15,
        "reset":    0.50,
    }

    # pygame channel assignments
    _CH_AMBIENT = 0
    _CH_SFX_START = 1
    _CH_SFX_END = 6   # channels 1-6 for normal SFX (round-robin)
    _CH_PRIORITY = 7   # levelup / achieve interrupt whatever's there

    def __init__(self) -> None:
        self._cache: Dict[str, pygame.mixer.Sound] = {}
        self._master_vol: float = 1.0
        self._sfx_vol:    float = 0.35   # 35 % — polite, non-intrusive
        self._music_vol:  float = 0.28   # 28 % — subtle background texture
        self._muted:      bool = False
        self._last_played: Dict[str, float] = {}
        self._sfx_rr:     int = self._CH_SFX_START   # round-robin channel

        # Reserve enough channels
        pygame.mixer.set_num_channels(max(pygame.mixer.get_num_channels(), 8))

        self._build_all()
        self._start_ambient()

    # ── Construction ──────────────────────────────────────────────────── #
    def _build_all(self) -> None:
        for name, kw in self.SOUNDS.items():
            try:
                self._cache[name] = _gen_wave(**kw)
            except Exception:
                pass

    def _start_ambient(self) -> None:
        try:
            snd = _build_ambient_pad(self._music_vol, self._master_vol)
            ch = pygame.mixer.Channel(self._CH_AMBIENT)
            ch.set_volume(self._music_vol * self._master_vol)
            ch.play(snd, loops=-1)
            self._ambient_snd = snd
            self._ambient_ch = ch
        except Exception:
            self._ambient_snd = None
            self._ambient_ch = None

    # ── Public API ────────────────────────────────────────────────────── #
    def play(self, name: str) -> None:
        """
        Fire a named one-shot SFX.

        Silently ignored if:
        - audio is muted
        - the sound name is unknown
        - the per-sound cooldown has not elapsed
        """
        if self._muted:
            return
        if name not in self._cache:
            return

        now = time.perf_counter()
        cd = self._COOLDOWNS.get(name, 0.0)
        if now - self._last_played.get(name, 0.0) < cd:
            return
        self._last_played[name] = now

        snd = self._cache[name]
        vol = self._sfx_vol * self._master_vol

        # Priority sounds get a dedicated channel so they always play
        if name in ("levelup", "achieve"):
            ch = pygame.mixer.Channel(self._CH_PRIORITY)
            ch.stop()
            ch.set_volume(min(1.0, vol * 1.15))   # slightly louder — important
            ch.play(snd)
        else:
            # Round-robin across SFX channels to avoid cut-off on rapid fire
            ch = pygame.mixer.Channel(self._sfx_rr)
            ch.set_volume(vol)
            ch.play(snd)
            self._sfx_rr += 1
            if self._sfx_rr > self._CH_SFX_END:
                self._sfx_rr = self._CH_SFX_START

    def set_master_volume(self, v: float) -> None:
        self._master_vol = max(0.0, min(1.0, v))
        self._refresh_ambient()

    def set_sfx_volume(self, v: float) -> None:
        self._sfx_vol = max(0.0, min(1.0, v))

    def set_music_volume(self, v: float) -> None:
        self._music_vol = max(0.0, min(1.0, v))
        self._refresh_ambient()

    def toggle_mute(self) -> bool:
        self._muted = not self._muted
        self._refresh_ambient()
        return self._muted

    @property
    def muted(self) -> bool:
        return self._muted

    # ── Internal ──────────────────────────────────────────────────────── #
    def _refresh_ambient(self) -> None:
        if self._ambient_ch is not None:
            vol = 0.0 if self._muted else self._music_vol * self._master_vol
            self._ambient_ch.set_volume(vol)
