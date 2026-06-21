#!/usr/bin/env python3
"""
main.py - Anti-Gravity Neon Gesture Game

Controls
--------
  Point finger   → move the orb
  Pinch          → boost + screen shake + magenta particles
  Fist           → pause orb motion
  Open hand      → normal tracking
  W              → toggle webcam background
  R              → reset score
  ESC / close    → quit

Run:  python main.py
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

# ═══════════════════════════════════════════════════════════════════ #
#  Configuration
# ═══════════════════════════════════════════════════════════════════ #
SCREEN_W     = 960
SCREEN_H     = 720
FPS_TARGET   = 60
CAMERA_INDEX = 0            # change if your webcam is on another index
TITLE        = "Anti-Gravity · Neon Gesture Game"

# Neon palette
C_BG         = (8, 8, 18)
C_TEXT       = (220, 220, 235)
C_DIM        = (90, 90, 110)
C_ACCENT     = (0, 255, 209)
C_MAGENTA    = (255, 0, 170)
C_WARN       = (255, 70, 70)
C_GOLD       = (255, 230, 50)
C_LM_DOT    = (0, 220, 175)
C_LM_LINE   = (40, 55, 70)
C_OVERLAY    = (6, 6, 14, 150)


# ═══════════════════════════════════════════════════════════════════ #
#  Neon drawing helpers
# ═══════════════════════════════════════════════════════════════════ #
def neon_text(surf, text, font, pos, color, glow=True):
    """Render text with an optional glow halo."""
    if glow:
        g = font.render(text, True, color)
        g.set_alpha(45)
        surf.blit(g, (pos[0] - 1, pos[1]))
        surf.blit(g, (pos[0] + 1, pos[1]))
        surf.blit(g, (pos[0], pos[1] - 1))
        surf.blit(g, (pos[0], pos[1] + 1))
    surf.blit(font.render(text, True, color), pos)


def neon_panel(surf, rect, border_color, bg_alpha=35):
    """Semi-transparent panel with 1-px neon border."""
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
    cs = pygame.Surface((sz * 2 + 2, sz * 2 + 2), pygame.SRCALPHA)
    cx, cy = sz + 1, sz + 1
    col = (*C_ACCENT, 90)
    pygame.draw.line(cs, col, (cx - sz, cy), (cx - gap, cy), 1)
    pygame.draw.line(cs, col, (cx + gap, cy), (cx + sz, cy), 1)
    pygame.draw.line(cs, col, (cx, cy - sz), (cx, cy - gap), 1)
    pygame.draw.line(cs, col, (cx, cy + gap), (cx, cy + sz), 1)
    # Small centre dot
    pygame.draw.circle(cs, (*C_ACCENT, 50), (cx, cy), 2)
    surf.blit(cs, (ix - sz - 1, iy - sz - 1))


# ═══════════════════════════════════════════════════════════════════ #
#  HUD
# ═══════════════════════════════════════════════════════════════════ #
GESTURE_COLS = {
    "OPEN":  (0, 200, 160),
    "PINCH": (255, 0, 170),
    "FIST":  (200, 55, 55),
    "POINT": (100, 180, 255),
    "NONE":  C_DIM,
}

def draw_hud(surf, fps, gesture, score, hand_ok, combo,
             font, font_sm, show_cam):
    # ── Left panel ──
    neon_panel(surf, pygame.Rect(8, 8, 200, 100), C_ACCENT)
    fc = C_TEXT if fps >= 25 else C_WARN
    neon_text(surf, f"FPS  {fps:.0f}", font_sm, (18, 14), fc, glow=False)

    gc = GESTURE_COLS.get(gesture, C_DIM)
    neon_text(surf, f"GESTURE  {gesture}", font_sm, (18, 38), gc)

    status = "TRACKING" if hand_ok else "NO HAND"
    sc = C_ACCENT if hand_ok else C_WARN
    neon_text(surf, status, font_sm, (18, 62), sc, glow=False)

    cam_label = "CAM  ON" if show_cam else "CAM  OFF"
    neon_text(surf, cam_label, font_sm, (18, 86), C_DIM, glow=False)

    # ── Right panel (score) ──
    neon_panel(surf, pygame.Rect(surf.get_width() - 178, 8, 170, 70), C_GOLD)
    st = font.render(f"{score}", True, C_GOLD)
    surf.blit(st, st.get_rect(topright=(surf.get_width() - 22, 12)))
    lt = font_sm.render("SCORE", True, C_DIM)
    surf.blit(lt, lt.get_rect(topright=(surf.get_width() - 22, 48)))

    # ── Combo indicator ──
    if combo.combo > 1:
        ct = font.render(f"x{combo.multiplier}", True, C_MAGENTA)
        alpha = int(min(1.0, combo.flash * 3) * 255) if combo.flash > 0 else 180
        ct.set_alpha(alpha)
        surf.blit(ct, ct.get_rect(midtop=(surf.get_width() // 2, 14)))

    # ── Bottom hints ──
    hints = "Point=Move · Pinch=Boost · Fist=Pause · W=Cam · R=Reset · ESC=Quit"
    ht = font_sm.render(hints, True, C_DIM)
    surf.blit(ht, ht.get_rect(midbottom=(surf.get_width() // 2,
                                          surf.get_height() - 10)))


# ═══════════════════════════════════════════════════════════════════ #
#  Progress reporter (prints to console)
# ═══════════════════════════════════════════════════════════════════ #
def report_progress(step: str, detail: str = ""):
    print(f"  [BUILD] {step}  {detail}")


# ═══════════════════════════════════════════════════════════════════ #
#  MAIN
# ═══════════════════════════════════════════════════════════════════ #
def main():
    # ── Init Pygame ──
    report_progress("1/7  Initialising Pygame ...")
    pygame.init()
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    try:
        font    = pygame.font.SysFont("Consolas", 30, bold=True)
        font_sm = pygame.font.SysFont("Consolas", 16)
        font_pop = pygame.font.SysFont("Consolas", 20, bold=True)
    except Exception:
        font    = pygame.font.Font(None, 30)
        font_sm = pygame.font.Font(None, 16)
        font_pop = pygame.font.Font(None, 20)
    report_progress("1/7  Pygame ready", "✓")

    # ── Camera ──
    report_progress("2/7  Opening webcam ...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {CAMERA_INDEX}.")
        print("        Change CAMERA_INDEX at the top of main.py.")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ch = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    report_progress("2/7  Camera ready", f"{cw}x{ch} ✓")

    # ── Tracker ──
    report_progress("3/7  Initialising MediaPipe hand tracker ...")
    tracker = HandTracker(ema_alpha=0.35)
    report_progress("3/7  Tracker ready", "✓")

    # ── Game objects ──
    report_progress("4/7  Creating game objects ...")
    ball         = GameObject(SCREEN_W // 2, SCREEN_H // 2, SCREEN_W, SCREEN_H)
    particles    = ParticleSystem()
    collectibles = CollectibleManager(SCREEN_W, SCREEN_H, max_orbs=5)
    shake        = ScreenShake()
    popups       = PopupManager()
    combo        = ComboTracker()
    report_progress("4/7  Objects ready", "✓")

    # ── Background ──
    report_progress("5/7  Pre-rendering neon background ...")
    neon_bg = NeonBackground(SCREEN_W, SCREEN_H)
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill(C_OVERLAY)
    bg_surf = pygame.Surface((SCREEN_W, SCREEN_H))
    bg_surf.fill(C_BG)
    report_progress("5/7  Background ready", "✓")

    # ── State ──
    report_progress("6/7  Final setup ...")
    score = 0
    fps   = 0.0
    boost_cd = 0.0
    show_cam = True        # toggle with W
    report_progress("6/7  Setup complete", "✓")

    report_progress("7/7  Entering game loop",
                    "— show your hand to the camera!")
    print()
    print("  ┌──────────────────────────────────────────┐")
    print("  │  Anti-Gravity Neon Gesture Game  READY   │")
    print("  │  Point=Move  Pinch=Boost  Fist=Pause     │")
    print("  │  W=Toggle cam  R=Reset  ESC=Quit         │")
    print("  └──────────────────────────────────────────┘")
    print()

    # ═════════════════════════════════════════════════════════════ #
    #  MAIN LOOP
    # ═════════════════════════════════════════════════════════════ #
    running = True
    while running:
        dt  = clock.tick(FPS_TARGET) / 1000.0
        fps = clock.get_fps()

        # ── Events ──
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    score = 0
                elif ev.key == pygame.K_w:
                    show_cam = not show_cam

        # ── Webcam + tracking ──
        ret, frame = cap.read()
        hand = None
        if ret:
            frame = cv2.flip(frame, 1)
            hand  = tracker.process(frame)
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

            is_boost  = gesture == "PINCH"
            is_paused = gesture == "FIST"
            ball.update(tx, ty, dt, boost=is_boost, paused=is_paused)

            # Boost particles
            if is_boost:
                boost_cd += dt
                if boost_cd >= 0.04:
                    boost_cd = 0.0
                    particles.emit(ball.x, ball.y, count=5,
                                   color=(255, 0, 170),
                                   end_color=(80, 0, 120),
                                   speed_range=(60, 200),
                                   lifetime_range=(0.25, 0.6),
                                   radius_range=(2, 6),
                                   gravity=60)
                    shake.add(0.06)
            else:
                boost_cd = 0.0
        else:
            ball.update(None, None, dt)

        particles.update(dt)
        shake.update(dt)
        combo.update(dt)
        popups.update(dt)
        score += collectibles.update(dt, ball, particles, combo, popups, shake)

        # ── Render ──
        # Game surface (everything draws here, then offset by shake)
        game_surf = screen  # draw directly for speed; apply shake to blit pos

        sx, sy = shake.offset()

        game_surf.fill(C_BG)
        game_surf.blit(bg_surf, (sx, sy))
        game_surf.blit(overlay, (sx, sy))
        neon_bg.draw(game_surf)   # grid + scanlines + vignette on top

        # Hand skeleton
        if hand and hand.detected and hand.landmarks:
            draw_hand_landmarks(game_surf, hand.landmarks,
                                hand.connections, SCREEN_W, SCREEN_H)
        if tx is not None:
            draw_crosshair(game_surf, tx + sx, ty + sy)

        collectibles.draw(game_surf)
        particles.draw(game_surf)
        ball.draw(game_surf)
        popups.draw(game_surf, font_pop)

        # HUD (always drawn at fixed position, not shaken)
        draw_hud(game_surf, fps, gesture, score, hand_ok, combo,
                 font, font_sm, show_cam)

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
