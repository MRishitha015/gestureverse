# GestureVerse Audio System — Design & Philosophy

## Overview

The audio system for GestureVerse was redesigned for immersion without fatigue. Players can enjoy extended gameplay sessions without audio-induced irritation.

**Design principle:** Audio should reward meaningful actions, not punish sustained interaction.

---

## Problem: The Old Audio

The previous implementation had several issues:

1. **Continuous laser sound** — the boost SFX fired every `0.04 s` (25 Hz) while pinching.
   - A `0.20 s` long sawtooth sweep played 25 times per second.
   - Multiple copies overlapped in the mixer, creating a harsh wall of sound.
   - After a few seconds of continuous pinch, players were mentally exhausted.

2. **Overzealous combo sounds** — `combo5` fired on any combo ≥ 5, so streaks of 5, 6, 7, 8 all triggered the same sound repeatedly.

3. **Loud SFX** — default `_sfx_vol = 0.85` (85 %) drowned out thought and conversation.

4. **Ambient loop clicks** — the ambient drone was generated with a default ADSR release that didn't match the loop join point, causing audible pops when looping.

---

## Solution: The New Audio

### 1. Gesture Tracking: Leading-Edge Detection

**Boost sound** now fires only when the pinch gesture *starts*, not continuously during the hold.

```python
if is_boost:
    if prev_gesture != "PINCH":
        audio.play("boost")  # only plays once per pinch
    # Visual particles still emit at 25 Hz (the visuals are great!)
    particles.emit(...)
```

The `SoundManager` also enforces a `1.2 s` cooldown on boost, so even rapid open-close-open pinches won't spam the sound.

**Result:** One soft whoosh per pinch, instead of 5+ overlapping lasers.

### 2. Combo Milestones

Combo sounds fire at *exact* thresholds only:

- `combo2`: fires when combo reaches exactly 2×
- `combo5`: fires when combo reaches exactly 5×
- Streaks of 6, 7, 8: no audio (rainbow particles celebrate visually)

```python
def on_combo(n):
    if n == 2:
        audio.play("combo2")   # ding!
    elif n == 5:
        audio.play("combo5")   # richer tone
    # n > 5: silent, let visuals carry
```

**Result:** Combos feel rewarding at key milestones, not exhausting at every hit.

### 3. Volume Defaults

| Setting | Old | New | Rationale |
|---|---|---|---|
| Master | 100% | 100% | unchanged |
| SFX | 85% | 35% | polite, non-intrusive |
| Music | 40% | 28% | subtle, atmospheric |

At 35% SFX, effects are clearly audible but don't dominate conversation or thought.

### 4. Seamless Ambient Pad

The new ambient music is a **multi-layer sine wave pad**:

- Three sine-wave layers at 55 Hz, 82.5 Hz, and 56.2 Hz (detuned root + fifth + rootish)
- 4-second clip with 10% fade windows (in and out) to hide the loop join
- Extremely low sustain level (harmonic pad, not melody)
- Loops infinitely without audible clicks or pops

**Why it works:**
- 55 Hz + 82.5 Hz creates a perfect fifth interval (pleasant, musical)
- Slow-attack / slow-release envelope hides the loop join even in the fade zone
- Duration = integer multiple of 55 Hz period → waveform aligns at loop boundary
- Very quiet (0.28 volume) → barely perceptible, purely atmospheric

### 5. Per-Sound Cooldowns

Each sound has a minimum gap between plays to prevent spam:

| Sound | Cooldown | Rationale |
|---|---|---|
| collect | 0.08 s | player can collect multiple orbs quickly |
| combo2 | 0.40 s | lets the chime finish before re-triggering |
| combo5 | 1.00 s | rare milestone, sounds cheap if spammed |
| boost | 1.20 s | prevents rapid pinch flutter from looping |
| powerup | 0.50 s | power-ups spawn every 12 s naturally |
| shield | 0.80 s | rare event, deserves space |
| slowmo | 1.00 s | rare event, deserves space |
| levelup | no cooldown | fires once per level up — rare by design |
| achieve | no cooldown | fires once per achievement — rare by design |

### 6. Channel Allocation

The mixer uses 8 channels:

| Channel | Purpose |
|---|---|
| 0 | Ambient music (exclusive, looping) |
| 1-6 | Normal SFX (round-robin to avoid cut-off) |
| 7 | Priority (levelup, achieve) — interrupts other SFX |

When `levelup` or `achieve` plays, it stops whatever is on channel 7 and gets a slight volume boost (×1.15), ensuring important events always cut through.

Normal SFX use channels 1-6 in round-robin fashion. If a player collects 6 orbs in quick succession (unlikely), channels cycle instead of cutting off previous effects.

---

## Sound Catalogue

### Gameplay

| Sound | When | Duration | Waveform | Character |
|---|---|---|---|---|
| **collect** | Orb collected | 0.16 s | sine | Bright ascending chime — "got it!" |
| **combo2** | 2× streak | 0.20 s | triangle | Two-note ping — "nice!" |
| **combo5** | 5× streak | 0.28 s | sine | Rich ascending tone — "impressive!" |
| **boost** | Pinch START | 0.22 s | triangle | Soft aerodynamic whoosh |
| **powerup** | Power-up collected | 0.30 s | triangle | Shimmering rise |
| **shield** | Shield activated | 0.22 s | sine | Crystalline ping |
| **slowmo** | Slow-mo START | 0.35 s | sine | Gentle downward slide |

### Progression

| Sound | When | Duration | Waveform | Character |
|---|---|---|---|---|
| **levelup** | Level up | 0.50 s | triangle | Warm ascending arpeggio — celebration |
| **achieve** | Achievement unlock | 0.55 s | sine | Clear bell tone — triumph |

### UI

| Sound | When | Duration | Waveform | Character |
|---|---|---|---|---|
| **click** | Confirm (W, M, R keys) | 0.07 s | triangle | Soft confirm click |
| **reset** | Score reset (R key) | 0.22 s | sine | Descending blip — undo |

---

## Implementation Details

### Procedural Generation

All sounds are generated from scratch using ADSR envelopes and waveform synthesis. No external audio assets required.

Each sound is built once at startup into a `pygame.mixer.Sound` object and cached. Re-playing reuses the cached sound.

Example: boost sound generation
```python
"boost": dict(
    freq=320,           # root frequency (Hz)
    duration=0.22,      # total duration (seconds)
    waveform="triangle",
    attack=0.008,       # fade in (seconds)
    decay=0.06,         # pitch decay
    sustain=0.30,       # hold level
    release=0.14,       # fade out
    freq_sweep=-160,    # freq drift (Hz/sec)
    amplitude=0.38,     # peak loudness
),
```

### Seamless Loop Strategy

The ambient pad stays audible indefinitely without clicking:

1. **Exact period alignment**: 4-second duration = 220 complete cycles of 55 Hz
   - At the 4 s boundary, the sine wave is exactly at zero crossing
   - No discontinuity at the loop join

2. **Fade windows**: 10% in, 10% out (0.4 s each)
   - Even if alignment is slightly off, fades hide the join
   - Fades are slow enough to stay inaudible

3. **Detuned layers**: three slightly-different sine waves beat together
   - Creates a "living" texture, not robotic
   - Beating masks any tiny loop artifacts

**Result**: Players forget the music is looping.

---

## Tuning Knobs

Users can adjust audio at runtime:

```python
# Python API
audio.set_master_volume(0.8)   # reduce to 80 %
audio.set_sfx_volume(0.5)      # reduce effects to 50 %
audio.set_music_volume(0.15)   # make music even quieter
audio.toggle_mute()            # instant mute (M key)
```

**Recommended for different contexts:**

- **Silent play** (library, office): `M` key → mute
- **Late night** (no volume for others): `music 0.1`, `sfx 0.2`
- **Solo gaming**: defaults (35 % SFX, 28 % music)
- **Party mode**: `sfx 0.6`, `music 0.4` (louder, celebratory)

---

## Future Improvements

1. **Adaptive volume** — reduce SFX volume automatically during long streaks
2. **Fatigue detection** — if player plays >30 min, subtly reduce all audio
3. **Gesture-specific tones** — PEACE gesture → unique sound when activated
4. **Dynamic music** — ambient pad layers activate based on combo level (subtle)
5. **Haptic feedback** — rumble instead of (or alongside) sound for accessibility
6. **A/B testing** — compare different waveforms and amplitudes with real players

---

## Testing Checklist

- [ ] Boost sound fires exactly once per pinch gesture (not continuous)
- [ ] Combo2 fires at 2× only; combo5 fires at 5× only
- [ ] No audio stuttering or overlapping harshly (cooldowns prevent this)
- [ ] Ambient music loops for >5 minutes without clicking
- [ ] Achievement/levelup sounds interrupt lower-priority SFX
- [ ] Mute toggle (M key) silences all sound including music
- [ ] Volume sliders work smoothly in 1% increments
- [ ] No audio devices cause crashes (graceful fallback to silent mode)

---

## References

**ADSR Envelope Theory**
- Attack-Decay-Sustain-Release shapes every physical instrument's sound
- Chosen values here are empirically tuned for a game context (short, punchy, pleasant)

**Hertz & Frequency**
- 55 Hz = very deep, sub-bass
- 220 Hz = A2, bass register
- 330 Hz = E3, low-mid
- 660 Hz = E4, mid
- 880 Hz = A4, mid-high
- 1100 Hz = C#5, high

**Waveform Character**
- Sine: smooth, mellow, musical
- Triangle: bright, clear, slightly hollow
- Square: buzzy, electronic, harsh (avoided here)
- Sawtooth: harsh, laser-like (used sparingly)

