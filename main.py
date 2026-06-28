#!/usr/bin/env python3
"""
main.py (v2) - GestureVerse: Anti-Gravity Neon Gesture Game

New in v2:
  - Audio system (procedural sound effects + ambient drone)
  - XP / level progression
  - Achievement system with toast notifications
  - Power-ups (magnet, shield, slowmo, double points)
  - Improved gesture tracking (One Euro Filter + lookahead prediction)
  - PEACE gesture → slow motion
  - THUMBSUP gesture → reserved for future ability
  - Animated star field background
  - Rainbow particles at high combos
  - Shield ring on ball
  - Magnet aura + pull mechanic
  - Power-up HUD with countdown bars
  - XP bar HUD
  - Stats tracking (streak, boosts used, power-ups collected)

Controls:
  Point   → move orb
  Pinch   → boost (magenta particles + shake)
  Fist    → pause
  ✌ Peace → slow-motion
  Open    → normal
  W       → toggle webcam background
  R       → reset score
  M       → toggle mute
  ESC     → quit
"""

import sys
import numpy as np
import cv2
import pygame

from hand_tracker import HandTracker
from game_objects import (
    GameObject, ParticleSystem, CollectibleManager,
    ScreenShake, PopupManager, ComboTracker, NeonBackground,
)
from progression import (
    XPSystem, AchievementSystem, PowerUpManager,
    ToastManager, draw_xp_bar,
)
from audio_manager import SoundManager

# ═══════════════════════════════════════════════════════════════════ #
#  Configuration
# ═══════════════════════════════════════════════════════════════════ #
SCREEN_W = 960
SCREEN_H = 720
FPS_TARGET = 60
CAMERA_INDEX = 0
TITLE = "GestureVerse · Anti-Gravity Neon v2"

C_BG = (8, 8, 18)
C_TEXT = (220, 220, 235)
C_DIM = (90, 90, 110)
C_ACCENT = (0, 255, 209)
C_MAGENTA = (255, 0, 170)
C_WARN = (255, 70, 70)
C_GOLD = (255, 230, 50)
C_OVERLAY = (6, 6, 14, 150)
C_LM_DOT = (0, 220, 175)
C_LM_LINE = (40, 55, 70)


# ═══════════════════════════════════════════════════════════════════ #
#  Drawing helpers
# ═══════════════════════════════════════════════════════════════════ #
def neon_text(surf, text, font, pos, color, glow=True):
    if glow:
        g = font.render(text, True, color)
        g.set_alpha(45)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            surf.blit(g, (pos[0]+dx, pos[1]+dy))
    surf.blit(font.render(text, True, color), pos)


def neon_panel(surf, rect, border_color, bg_alpha=35):
    p = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    p.fill((0, 0, 0, bg_alpha))
    pygame.draw.rect(p, (*border_color, 70), (0, 0, rect.w, rect.h), 1,
                     border_radius=5)
    surf.blit(p, rect.topleft)


def draw_hand_landmarks(surf, landmarks, connections, w, h):
    pts = [(int(lx * w), int(ly * h)) for lx, ly in landmarks]
    for a, b in connections:
        if a < len(pts) and b < len(pts):
            pygame.draw.line(surf, C_LM_LINE, pts[a], pts[b], 2)
    tips = {4, 8, 12, 16, 20}
    for i, p in enumerate(pts):
        r = 5 if i in tips else 3
        c = C_ACCENT if i == 8 else C_LM_DOT
        pygame.draw.circle(surf, c, p, r)


def draw_crosshair(surf, x, y):
    ix, iy = int(x), int(y)
    sz, gap = 16, 6
    cs = pygame.Surface((sz*2+2, sz*2+2), pygame.SRCALPHA)
    cx, cy = sz+1, sz+1
    col = (*C_ACCENT, 90)
    pygame.draw.line(cs, col, (cx-sz, cy), (cx-gap, cy), 1)
    pygame.draw.line(cs, col, (cx+gap, cy), (cx+sz, cy), 1)
    pygame.draw.line(cs, col, (cx, cy-sz), (cx, cy-gap), 1)
    pygame.draw.line(cs, col, (cx, cy+gap), (cx, cy+sz), 1)
    pygame.draw.circle(cs, (*C_ACCENT, 50), (cx, cy), 2)
    surf.blit(cs, (ix-sz-1, iy-sz-1))


GESTURE_COLS = {
    "OPEN":     (0, 200, 160),
    "PINCH":    (255, 0, 170),
    "FIST":     (200, 55, 55),
    "POINT":    (100, 180, 255),
    "PEACE":    (100, 255, 150),
    "THUMBSUP": (255, 200, 50),
    "NONE":     C_DIM,
}


def draw_hud(surf, fps, gesture, score, hand_ok, combo,
             font, font_sm, show_cam, xp_sys, powerup_mgr):
    # ── Left panel ──
    neon_panel(surf, pygame.Rect(8, 8, 210, 120), C_ACCENT)
    fc = C_TEXT if fps >= 25 else C_WARN
    neon_text(surf, f"FPS  {fps:.0f}", font_sm, (18, 14), fc, glow=False)
    gc = GESTURE_COLS.get(gesture, C_DIM)
    neon_text(surf, f"GESTURE  {gesture}", font_sm, (18, 38), gc)
    status = "TRACKING" if hand_ok else "NO HAND"
    sc = C_ACCENT if hand_ok else C_WARN
    neon_text(surf, status, font_sm, (18, 62), sc, glow=False)
    cam_lbl = "CAM  ON" if show_cam else "CAM  OFF"
    neon_text(surf, cam_lbl, font_sm, (18, 86), C_DIM, glow=False)

    # ── Score panel ──
    neon_panel(surf, pygame.Rect(surf.get_width()-178, 8, 170, 70), C_GOLD)
    st = font.render(f"{score}", True, C_GOLD)
    surf.blit(st, st.get_rect(topright=(surf.get_width()-22, 12)))
    lt = font_sm.render("SCORE", True, C_DIM)
    surf.blit(lt, lt.get_rect(topright=(surf.get_width()-22, 48)))

    # ── Combo ──
    if combo.combo > 1:
        ct = font.render(f"×{combo.multiplier}", True, C_MAGENTA)
        alpha = int(min(1.0, combo.flash * 3) *
                    255) if combo.flash > 0 else 180
        ct.set_alpha(alpha)
        surf.blit(ct, ct.get_rect(midtop=(surf.get_width()//2, 14)))

    # ── XP bar ──
    draw_xp_bar(surf, xp_sys, font, font_sm,
                x=surf.get_width()-178, y=90, width=170)

    # ── Power-up bars ──
    powerup_mgr.draw_active_hud(surf, font_sm,
                                x=8, y=surf.get_height()-80)

    # ── Bottom hints ──
    hints = ("Point=Move · Pinch=Boost · Fist=Pause · "
             "✌=SlowMo · W=Cam · M=Mute · R=Reset · ESC=Quit")
    ht = font_sm.render(hints, True, C_DIM)
    surf.blit(ht, ht.get_rect(midbottom=(surf.get_width()//2,
                                         surf.get_height()-10)))


def report(step, detail=""):
    print(f"  [BUILD] {step}  {detail}")


# ═══════════════════════════════════════════════════════════════════ #
#  MAIN
# ═══════════════════════════════════════════════════════════════════ #
def main():
    report("1/8  Initialising Pygame ...")
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("Consolas", 30, bold=True)
        font_sm = pygame.font.SysFont("Consolas", 16)
        font_pop = pygame.font.SysFont("Consolas", 20, bold=True)
    except Exception:
        font = font_sm = font_pop = pygame.font.Font(None, 20)
    report("1/8  Pygame ready", "✓")

    report("2/8  Opening webcam ...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {CAMERA_INDEX}.")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ch = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    report("2/8  Camera ready", f"{cw}×{ch} ✓")

    report("3/8  Initialising MediaPipe hand tracker ...")
    tracker = HandTracker(ema_alpha=0.30, one_euro_beta=0.009)
    report("3/8  Tracker ready", "✓")

    report("4/8  Creating game objects ...")
    ball = GameObject(SCREEN_W//2, SCREEN_H//2, SCREEN_W, SCREEN_H)
    particles = ParticleSystem()
    collectibles = CollectibleManager(SCREEN_W, SCREEN_H, max_orbs=5)
    shake = ScreenShake()
    popups = PopupManager()
    combo = ComboTracker()
    report("4/8  Objects ready", "✓")

    report("5/8  Setting up progression systems ...")
    xp_sys = XPSystem()
    toasts = ToastManager(SCREEN_H)
    achieve = AchievementSystem(on_unlock=lambda a: toasts.add(a))
    powerups = PowerUpManager(SCREEN_W, SCREEN_H)

    # Wire up callbacks
    def on_levelup(level):
        audio.play("levelup")
        shake.add(0.4)
        popups.spawn(SCREEN_W//2, SCREEN_H//2 - 60,
                     f"LEVEL {level}!", (160, 100, 255), scale=1.4)

    xp_sys.on_levelup(on_levelup)

    def on_combo(n):
        # Fire combo2 only at exactly 2× streak; combo5 only at exactly 5×.
        # Higher streaks (6-8) are already celebrated by the visual rainbow
        # effects and don't need extra audio to avoid spam.
        if n == 2:
            audio.play("combo2")
        elif n == 5:
            audio.play("combo5")

    combo.on_combo(on_combo)
    report("5/8  Progression ready", "✓")

    report("6/8  Pre-rendering neon background ...")
    neon_bg = NeonBackground(SCREEN_W, SCREEN_H)
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill(C_OVERLAY)
    bg_surf = pygame.Surface((SCREEN_W, SCREEN_H))
    bg_surf.fill(C_BG)
    report("6/8  Background ready", "✓")

    report("7/8  Initialising audio ...")
    try:
        audio = SoundManager()
        audio_ok = True
    except Exception as e:
        print(f"        (audio disabled: {e})")
        audio_ok = False

        class _NullAudio:
            def play(self, *a, **k): pass
            def toggle_mute(self): return True
            muted = True
        audio = _NullAudio()
    report("7/8  Audio ready", "✓" if audio_ok else "(disabled)")

    report("8/8  Final setup ...")
    score = 0
    fps = 0.0
    boost_cd = 0.0
    show_cam = True
    slowmo = False
    prev_gesture = "NONE"   # used to detect leading edge of gestures
    stats = {
        "total_collected": 0,
        "max_combo":       0,
        "score":           0,
        "level":           1,
        "boosts":          0,
        "powerups":        0,
        "streak":          0,
    }
    report("8/8  Setup complete", "✓")
    print()
    print("  ┌──────────────────────────────────────────────┐")
    print("  │  GestureVerse  v2  –  READY                  │")
    print("  │  Point=Move  Pinch=Boost  Fist=Pause         │")
    print("  │  ✌=SlowMo  W=Cam  M=Mute  R=Reset  ESC=Quit │")
    print("  └──────────────────────────────────────────────┘")
    print()

    running = True
    while running:
        dt = clock.tick(FPS_TARGET) / 1000.0
        fps = clock.get_fps()

        # Slow-motion time dilation
        if slowmo:
            dt *= 0.4

        # ── Events ──
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    score = 0
                    combo.combo = 0
                    audio.play("reset")
                elif ev.key == pygame.K_w:
                    show_cam = not show_cam
                    audio.play("click")
                elif ev.key == pygame.K_m:
                    muted = audio.toggle_mute()
                    popups.spawn(SCREEN_W//2, 80,
                                 "MUTED" if muted else "SOUND ON",
                                 C_DIM)

        # ── Webcam ──
        ret, frame = cap.read()
        hand = None
        if ret:
            frame = cv2.flip(frame, 1)
            hand = tracker.process(frame)
            if show_cam:
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    s = pygame.surfarray.make_surface(
                        np.transpose(rgb, (1, 0, 2)))
                    bg_surf = pygame.transform.scale(s, (SCREEN_W, SCREEN_H))
                except Exception:
                    bg_surf.fill(C_BG)
            else:
                bg_surf.fill(C_BG)

        # ── Update logic ──
        gesture = "NONE"
        hand_ok = False
        tx = ty = None

        if hand and hand.detected:
            hand_ok = True
            gesture = hand.gesture
            tx = hand.x * SCREEN_W
            ty = hand.y * SCREEN_H

            is_boost = gesture == "PINCH"
            is_paused = gesture == "FIST"
            slowmo = (gesture == "PEACE" or
                      powerups.is_active("slowmo"))

            ball.update(tx, ty, dt, boost=is_boost, paused=is_paused)
            ball.has_shield = powerups.is_active("shield")
            ball.magnet_active = powerups.is_active("magnet")

            if is_boost:
                stats["boosts"] += 1
                # Fire the boost SOUND only on the leading edge of the pinch
                # gesture (transition from non-PINCH → PINCH). The sound
                # manager's own 1.2 s cooldown also prevents spam if the
                # player rapidly opens and closes their hand.
                if prev_gesture != "PINCH":
                    audio.play("boost")
                # Visual particles + shake still emit at 25 Hz — looks great,
                # but audio is now a single whoosh per pinch activation.
                boost_cd += dt
                if boost_cd >= 0.04:
                    boost_cd = 0.0
                    particles.emit(ball.x, ball.y, count=5,
                                   color=(255, 0, 170), end_color=(80, 0, 120),
                                   speed_range=(60, 200),
                                   lifetime_range=(0.25, 0.6),
                                   radius_range=(2, 6), gravity=60)
                    shake.add(0.06)
            else:
                boost_cd = 0.0
        else:
            slowmo = powerups.is_active("slowmo")
            ball.update(None, None, dt)
            ball.has_shield = powerups.is_active("shield")
            ball.magnet_active = powerups.is_active("magnet")

        # Track previous gesture for leading-edge detection
        prev_gesture = gesture

        # Power-up collection
        collected_pu = powerups.update(
            dt, ball.x, ball.y, ball.radius)
        if collected_pu:
            stats["powerups"] += 1
            audio.play("powerup")
            shake.add(0.3)
            popups.spawn(ball.x, ball.y - 40,
                         powerups.orbs[0].label if powerups.orbs else "POWER UP!",
                         (160, 100, 255))

        # Collectibles
        earned = collectibles.update(
            dt, ball, particles, combo, popups, shake,
            magnet_active=powerups.is_active("magnet"),
            double_pts=powerups.is_active("double_pts"),
        )
        if earned:
            stats["total_collected"] += earned // 10
            stats["streak"] += 1
            audio.play("collect")
            score += earned
            xp_gain = earned // 2
            xp_sys.add(xp_gain)

        stats["max_combo"] = max(stats["max_combo"], combo.combo)
        stats["score"] = score
        stats["level"] = xp_sys.level

        particles.update(dt)
        shake.update(dt)
        combo.update(dt)
        popups.update(dt)
        neon_bg.update(dt)
        toasts.update(dt)
        achieve.check_all(stats)

        # ── Render ──
        sx, sy = shake.offset()

        screen.fill(C_BG)
        screen.blit(bg_surf, (sx, sy))
        screen.blit(overlay, (sx, sy))
        neon_bg.draw(screen)

        # Slow-mo tint
        if slowmo:
            tint = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            tint.fill((100, 255, 80, 18))
            screen.blit(tint, (0, 0))

        if hand and hand.detected and hand.landmarks:
            draw_hand_landmarks(screen, hand.landmarks,
                                hand.connections, SCREEN_W, SCREEN_H)
        if tx is not None:
            draw_crosshair(screen, tx + sx, ty + sy)

        powerups.draw(screen)
        collectibles.draw(screen)
        particles.draw(screen)
        ball.draw(screen)
        popups.draw(screen, font_pop)

        draw_hud(screen, fps, gesture, score, hand_ok, combo,
                 font, font_sm, show_cam, xp_sys, powerups)
        toasts.draw(screen, font_sm, font_sm)

        pygame.display.flip()

    # ── Cleanup ──
    print("[INFO] Shutting down ...")
    tracker.release()
    cap.release()
    pygame.quit()
    cv2.destroyAllWindows()
    print("[INFO] Done.")


if __name__ == "__main__":
    main()
