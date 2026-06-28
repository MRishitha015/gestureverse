# 🚀 GestureVerse: Anti-Gravity Neon Gesture Game (v2)

A real-time computer vision game controlled entirely by hand gestures via webcam.
Built with MediaPipe, OpenCV, and Pygame.

---

## ✨ What's New in v2

| Feature | Details |
|---|---|
| 🔊 Procedural Audio | Full SFX + ambient drone, no asset files needed |
| ⭐ XP & Levels | Quadratic XP curve, on-screen XP bar, level-up effects |
| 🏆 Achievements | 9 unlockable achievements with sliding toast notifications |
| ⚗️ Power-Ups | Magnet, Shield, Slow-Mo, Double Points — spawn every 12 s |
| 🌊 One Euro Filter | Lower jitter, velocity-based 2-frame lookahead prediction |
| ✌️ Peace Gesture | Slow-motion mode (40% time scale) |
| 🌈 Rainbow Combos | Particles and popups cycle hue at 3× combo+ |
| 🛡️ Shield Ring | Animated dashed ring when shield is active |
| 🧲 Magnet Aura | Visual aura + orb pull when magnet is active |
| ⭐ Star Field | 120 animated background stars |
| 🎯 Star Orbs | Rotating 4-point star inside collectibles |

---

## 🎮 Controls

| Gesture / Key | Action |
|---|---|
| ☝️ Index Finger | Move energy orb |
| 🤏 Pinch | Activate boost (magenta trail + shake) |
| ✊ Fist | Pause orb |
| ✌️ Peace Sign | Slow-motion mode |
| 🖐️ Open Hand | Normal tracking |
| **W** | Toggle webcam background |
| **M** | Toggle mute |
| **R** | Reset score |
| **ESC** | Quit |

---

## 📦 Installation

```bash
git clone https://github.com/your-username/gestureverse.git
cd gestureverse
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 🏗️ Architecture

```
gestureverse/
├── main.py              # Game loop, rendering, event handling
├── hand_tracker.py      # MediaPipe + EMA + One Euro Filter + lookahead
├── game_objects.py      # Ball, particles, collectibles, background
├── progression.py       # XP, levels, achievements, power-ups, HUD
├── audio_manager.py     # Procedural SFX + ambient audio (no assets)
├── requirements.txt
└── README.md
```

### New Modules

**`audio_manager.py`**
- Generates all sounds from scratch using ADSR envelopes
- Named events: `collect`, `combo2`, `combo5`, `boost`, `levelup`, `achieve`, `powerup`, `shield`, `slowmo`, `hover`, `click`, `reset`
- Ambient drone on loop; master / SFX / music volume controls

**`progression.py`**
- `XPSystem` — level curve: Lv N needs N²×80 XP
- `AchievementSystem` — 9 predefined achievements, extensible
- `PowerUpManager` — spawns & tracks 4 buff types
- `ToastManager` — slide-in achievement notifications
- `draw_xp_bar()` — gradient XP bar with level badge

**Updated `hand_tracker.py`**
- Stage 1: EMA smoothing (α = 0.30)
- Stage 2: One Euro Filter (adaptive low-pass, removes jitter at rest)
- Velocity estimation + 2-frame lookahead prediction
- New gestures: `PEACE` (✌), `THUMBSUP` (👍)

**Updated `game_objects.py`**
- `NeonBackground` — animated 120-star field
- `GameObject` — shield ring, magnet aura, rainbow boost trail
- `CollectibleManager` — magnet pull, double-points flag, ring-burst mode
- `ComboTracker` — cap raised to 8, combo event callbacks

---

## ⚙️ Configuration

| Parameter | File | Default | Description |
|---|---|---|---|
| `CAMERA_INDEX` | `main.py` | `0` | Webcam index |
| `FPS_TARGET` | `main.py` | `60` | Frame rate cap |
| `ema_alpha` | `hand_tracker.py` | `0.30` | EMA smoothing strength |
| `one_euro_beta` | `hand_tracker.py` | `0.009` | One Euro speed sensitivity |
| `accel_factor` | `game_objects.py` | `3500` | Orb spring acceleration |
| `PINCH_THRESHOLD` | `hand_tracker.py` | `0.06` | Pinch detection distance |
| `MAGNET_RADIUS` | `game_objects.py` | `180 px` | Magnet pull range |
| `_spawn_interval` | `progression.py` | `12 s` | Power-up spawn rate |

---

## 🎓 Skills Demonstrated

Computer Vision · Gesture Recognition · Real-Time Signal Processing ·
Physics Simulation · Game Development · Procedural Audio · Software Architecture ·
Human-Computer Interaction · Performance Optimization (60 FPS)
