# Anti-Gravity · Neon Gesture Game 🖐️✨

A polished, neon-arcade-styled gesture game powered by real-time webcam hand
tracking. A glowing orb floats and follows your finger with smooth spring
physics while you collect golden orbs, build combos, and watch particles fly.

---

## Quick Start

```bash
# 1 — Install dependencies
pip install -r requirements.txt

# 2 — Run
python main.py
```

> **Tip:** If you use a virtual environment:
> ```bash
> python -m venv .venv
> .venv\Scripts\activate      # Windows
> source .venv/bin/activate   # macOS / Linux
> pip install -r requirements.txt
> ```

---

## Controls

| Input | Action |
|-------|--------|
| **Point** (index finger) | Move the orb toward your fingertip |
| **Pinch** (thumb + index) | **Boost** — faster pull, magenta particles, screen shake |
| **Fist** | **Pause** — heavy damping, orb freezes |
| **Open hand** | Normal tracking |
| `W` key | Toggle webcam background on / off |
| `R` key | Reset score |
| `ESC` | Quit |

---

## What's New in the Neon Upgrade

| Feature | Details |
|---------|---------|
| 🎨 **Neon visual overhaul** | Cyberpunk grid, scanlines, edge vignette |
| 💥 **Screen shake** | Trauma-based camera shake on boost & collection |
| 🔢 **Score popups** | Floating "+10" / "+20 x2" text that rises and fades |
| ⚡ **Combo system** | Collect orbs within 2.5s for x2–x5 multiplier |
| 🌈 **Speed-reactive colour** | Ball shifts cyan → white at high speed, magenta on boost |
| 🪐 **Orbiting dots** | Collectible orbs have animated satellite dots |
| 🎆 **Enhanced particles** | Gravity, colour interpolation, size decay |
| 📺 **Webcam toggle** | Press `W` to switch between webcam and pure neon grid |
| 🖥️ **Neon HUD** | Bordered panels, glow text, combo indicator |
| 📊 **Build progress** | Console prints step-by-step startup status |

---

## Architecture

```
antigravity-game/
├── main.py            # Game loop, rendering, neon HUD
├── hand_tracker.py    # MediaPipe tracking + EMA + hand speed
├── game_objects.py    # Ball, particles, collectibles, effects
└── requirements.txt   # Python dependencies
```

### Classes in `game_objects.py`

| Class | Purpose |
|-------|---------|
| `ScreenShake` | Trauma-based camera shake |
| `PopupManager` | Floating score text |
| `ComboTracker` | Streak multiplier (x1–x5) |
| `NeonBackground` | Pre-rendered grid, scanlines, vignette |
| `GameObject` | Spring-physics ball with neon trail & glow |
| `ParticleSystem` | Burst particles with gravity & colour lerp |
| `CollectibleManager` | Spawns and manages orbiting gold orbs |

---

## Tuning

| Parameter | File | Default | Notes |
|-----------|------|---------|-------|
| `SCREEN_W / SCREEN_H` | `main.py` | 960×720 | Window size |
| `FPS_TARGET` | `main.py` | 60 | Pygame clock target |
| `CAMERA_INDEX` | `main.py` | 0 | Try 1, 2 if wrong cam |
| `ema_alpha` | `hand_tracker.py` | 0.35 | Lower = smoother |
| `accel_factor` | `game_objects.py` | 3500 | Spring pull strength |
| `damping` | `game_objects.py` | 0.91 | Velocity decay |
| `PINCH_THRESHOLD` | `hand_tracker.py` | 0.06 | Pinch sensitivity |
| `combo.timeout` | `game_objects.py` | 2.5s | Combo window |

---

## Troubleshooting

### Wrong camera
Change `CAMERA_INDEX` at the top of `main.py` (try `1`, `2`).

### Low FPS
- Close other webcam apps.
- Lower screen resolution (e.g. 640×480).
- Press `W` to disable webcam background (pure neon grid is faster).

### MediaPipe not found
```bash
pip install --upgrade mediapipe
```

### Hand not detected
- Good lighting, avoid backlight.
- Keep full hand visible, ~30–50% of frame.
- Move closer to camera.

---

## License

MIT — use however you like.
