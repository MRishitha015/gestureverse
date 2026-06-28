"""
progression.py - XP, levels, achievements, and power-up systems.

Classes:
    XPSystem          – experience points and level progression
    Achievement       – single achievement definition
    AchievementSystem – tracks and unlocks achievements
    PowerUp / PowerUpManager – timed in-game boosts
    ProgressionHUD    – draws XP bar, level badge, achievement toasts
"""

import math
import time
import random
import pygame
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple, Dict


# ══════════════════════════════════════════════════════════════════════ #
#  XP / Level
# ══════════════════════════════════════════════════════════════════════ #
class XPSystem:
    """Simple quadratic XP curve. Level N needs N² × 80 XP total."""

    BASE = 80

    def __init__(self):
        self.xp    = 0
        self.level = 1
        self._on_levelup: List[Callable[[int], None]] = []

    @property
    def xp_for_current(self) -> int:
        return self.BASE * (self.level ** 2)

    @property
    def xp_for_prev(self) -> int:
        return self.BASE * ((self.level - 1) ** 2)

    @property
    def progress(self) -> float:
        """0.0 → 1.0 within current level."""
        span = self.xp_for_current - self.xp_for_prev
        return min((self.xp - self.xp_for_prev) / max(span, 1), 1.0)

    def add(self, amount: int):
        self.xp += amount
        while self.xp >= self.xp_for_current:
            self.level += 1
            for cb in self._on_levelup:
                cb(self.level)

    def on_levelup(self, cb: Callable[[int], None]):
        self._on_levelup.append(cb)


# ══════════════════════════════════════════════════════════════════════ #
#  Achievements
# ══════════════════════════════════════════════════════════════════════ #
@dataclass
class Achievement:
    id: str
    name: str
    desc: str
    icon: str               # single emoji used as icon
    check: Callable         # check(stats) -> bool
    unlocked: bool = False
    unlock_time: float = 0.0


class AchievementSystem:
    DEFINITIONS = [
        Achievement("first_blood",  "First Blood",    "Collect your first orb",
                    "⚡", lambda s: s["total_collected"] >= 1),
        Achievement("combo_5",      "Combo King",     "Reach a 5× combo",
                    "🔥", lambda s: s["max_combo"] >= 5),
        Achievement("score_100",    "Century",        "Score 100 points",
                    "💯", lambda s: s["score"] >= 100),
        Achievement("score_500",    "High Roller",    "Score 500 points",
                    "🏆", lambda s: s["score"] >= 500),
        Achievement("level_5",      "Rising Star",    "Reach level 5",
                    "⭐", lambda s: s["level"] >= 5),
        Achievement("level_10",     "Veteran",        "Reach level 10",
                    "🌟", lambda s: s["level"] >= 10),
        Achievement("speed_demon",  "Speed Demon",    "Use boost 50 times",
                    "🚀", lambda s: s["boosts"] >= 50),
        Achievement("powerup_5",    "Power Hungry",   "Collect 5 power-ups",
                    "⚗️",  lambda s: s["powerups"] >= 5),
        Achievement("no_miss_20",   "Sharpshooter",  "Collect 20 orbs in a row",
                    "🎯", lambda s: s["streak"] >= 20),
    ]

    def __init__(self, on_unlock: Optional[Callable] = None):
        self.achievements: List[Achievement] = list(self.DEFINITIONS)
        self._on_unlock = on_unlock  # callback(achievement)
        self._toast_queue: List[Achievement] = []

    def check_all(self, stats: dict):
        for a in self.achievements:
            if not a.unlocked and a.check(stats):
                a.unlocked = True
                a.unlock_time = time.perf_counter()
                self._toast_queue.append(a)
                if self._on_unlock:
                    self._on_unlock(a)

    def pop_toast(self) -> Optional[Achievement]:
        return self._toast_queue.pop(0) if self._toast_queue else None

    @property
    def unlocked_count(self) -> int:
        return sum(1 for a in self.achievements if a.unlocked)


# ══════════════════════════════════════════════════════════════════════ #
#  Power-Ups
# ══════════════════════════════════════════════════════════════════════ #
POWERUP_TYPES = {
    "magnet":    {"color": (120, 80, 255), "label": "MAGNET",    "duration": 6.0},
    "shield":    {"color": (80, 200, 255), "label": "SHIELD",    "duration": 8.0},
    "slowmo":    {"color": (200, 255, 80), "label": "SLOW MO",   "duration": 5.0},
    "double_pts":{"color": (255, 200, 60), "label": "2× POINTS", "duration": 7.0},
}


class PowerUp:
    """A floating power-up orb on the field."""

    def __init__(self, x: float, y: float, kind: str):
        self.x, self.y = x, y
        self.kind  = kind
        self.info  = POWERUP_TYPES[kind]
        self.color = self.info["color"]
        self.label = self.info["label"]
        self.radius = 16
        self.alive  = True
        self._phase = random.uniform(0, math.tau)
        self._bob_speed = random.uniform(1.8, 2.4)

    def update(self, dt: float):
        self._phase += dt * self._bob_speed

    def draw(self, surf: pygame.Surface):
        if not self.alive:
            return
        bob = math.sin(self._phase) * 4
        x, y = int(self.x), int(self.y + bob)
        p = 0.75 + 0.25 * abs(math.sin(self._phase * 0.7))

        # Outer glow
        for ring in range(4, 0, -1):
            gr = int(self.radius + ring * 7 * p)
            ga = int(22 / ring)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*self.color, ga), (gr, gr), gr)
            surf.blit(gs, (x - gr, y - gr))

        # Hex body (drawn as octagon via polygon)
        pts = []
        for k in range(6):
            ang = k * math.pi / 3 + self._phase * 0.5
            pts.append((x + int(math.cos(ang) * self.radius * p),
                        y + int(math.sin(ang) * self.radius * p)))
        pygame.draw.polygon(surf, self.color, pts)
        pygame.draw.polygon(surf, (255, 255, 255), pts, 1)

    def collides(self, bx: float, by: float, brad: float) -> bool:
        return math.hypot(self.x - bx, self.y - by) < (self.radius + brad)


class PowerUpManager:
    """Spawns power-ups, tracks active buffs."""

    def __init__(self, sw: int, sh: int):
        self.sw, self.sh = sw, sh
        self.orbs: List[PowerUp] = []
        self._spawn_timer = 0.0
        self._spawn_interval = 12.0   # seconds between spawns

        # Active effects: kind → expiry timestamp
        self._active: Dict[str, float] = {}

    # ── Queries ──
    def is_active(self, kind: str) -> bool:
        return time.perf_counter() < self._active.get(kind, 0)

    def remaining(self, kind: str) -> float:
        return max(0.0, self._active.get(kind, 0) - time.perf_counter())

    @property
    def any_active(self) -> bool:
        now = time.perf_counter()
        return any(v > now for v in self._active.values())

    # ── Update ──
    def update(self, dt: float, bx: float, by: float,
               brad: float) -> Optional[str]:
        """Returns kind string if a power-up was just collected."""
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_interval and len(self.orbs) < 2:
            self._spawn_timer = 0.0
            self._do_spawn()

        collected = None
        for o in self.orbs:
            o.update(dt)
            if o.alive and o.collides(bx, by, brad):
                o.alive = False
                dur = POWERUP_TYPES[o.kind]["duration"]
                self._active[o.kind] = time.perf_counter() + dur
                collected = o.kind
        self.orbs = [o for o in self.orbs if o.alive]
        return collected

    def _do_spawn(self):
        m = 90
        kind = random.choice(list(POWERUP_TYPES.keys()))
        self.orbs.append(PowerUp(
            random.randint(m, self.sw - m),
            random.randint(m, self.sh - m),
            kind,
        ))

    def draw(self, surf: pygame.Surface):
        for o in self.orbs:
            o.draw(surf)

    def draw_active_hud(self, surf: pygame.Surface, font: pygame.font.Font,
                        x: int, y: int):
        """Draw active buff indicators below the score panel."""
        now = time.perf_counter()
        row = 0
        for kind, expiry in self._active.items():
            rem = expiry - now
            if rem <= 0:
                continue
            info = POWERUP_TYPES[kind]
            col  = info["color"]
            # Bar bg
            bw = 130
            bh = 14
            bx = x
            by = y + row * 22
            pygame.draw.rect(surf, (30, 30, 50), (bx, by, bw, bh), border_radius=3)
            fill = int(bw * (rem / info["duration"]))
            pygame.draw.rect(surf, col, (bx, by, fill, bh), border_radius=3)
            # Label
            lbl = font.render(info["label"], True, (220, 220, 235))
            surf.blit(lbl, (bx + 4, by))
            row += 1


# ══════════════════════════════════════════════════════════════════════ #
#  Achievement Toast
# ══════════════════════════════════════════════════════════════════════ #
class AchievementToast:
    """Single sliding toast notification."""

    DISPLAY_TIME = 3.2
    SLIDE_TIME   = 0.35

    def __init__(self, achievement: Achievement, y_pos: int):
        self.a      = achievement
        self.y_pos  = y_pos
        self.timer  = self.DISPLAY_TIME
        self.alive  = True

    def update(self, dt: float):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surf: pygame.Surface, font: pygame.font.Font,
             font_sm: pygame.font.Font):
        w = surf.get_width()
        # Slide in from right
        if self.timer > self.DISPLAY_TIME - self.SLIDE_TIME:
            progress = 1 - (self.timer - (self.DISPLAY_TIME - self.SLIDE_TIME)) / self.SLIDE_TIME
        elif self.timer < self.SLIDE_TIME:
            progress = self.timer / self.SLIDE_TIME
        else:
            progress = 1.0

        panel_w, panel_h = 260, 56
        # ease out cubic
        eased = 1 - (1 - progress) ** 3
        px = int(w - panel_w - 12 + (1 - eased) * (panel_w + 12))
        py = self.y_pos

        # Panel
        p = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        p.fill((8, 8, 30, 210))
        pygame.draw.rect(p, (255, 210, 50, 180), (0, 0, panel_w, panel_h), 1,
                         border_radius=6)
        surf.blit(p, (px, py))

        # Icon
        icon_t = font.render(self.a.icon, True, (255, 210, 50))
        surf.blit(icon_t, (px + 8, py + 8))

        # Text
        title = font.render(self.a.name, True, (255, 210, 50))
        surf.blit(title, (px + 38, py + 6))
        desc  = font_sm.render(self.a.desc, True, (180, 180, 200))
        surf.blit(desc, (px + 38, py + 30))


class ToastManager:
    """Queues and renders achievement toasts."""

    def __init__(self, surf_h: int):
        self._toasts: List[AchievementToast] = []
        self._base_y = surf_h - 80

    def add(self, a: Achievement):
        y = self._base_y - len(self._toasts) * 68
        self._toasts.append(AchievementToast(a, y))

    def update(self, dt: float):
        for t in self._toasts:
            t.update(dt)
        self._toasts = [t for t in self._toasts if t.alive]

    def draw(self, surf: pygame.Surface, font: pygame.font.Font,
             font_sm: pygame.font.Font):
        for t in self._toasts:
            t.draw(surf, font, font_sm)


# ══════════════════════════════════════════════════════════════════════ #
#  XP Bar HUD
# ══════════════════════════════════════════════════════════════════════ #
def draw_xp_bar(surf: pygame.Surface, xp_sys: XPSystem,
                font: pygame.font.Font, font_sm: pygame.font.Font,
                x: int, y: int, width: int = 180):
    """Compact XP bar with level badge."""
    bar_h = 10
    # Background
    pygame.draw.rect(surf, (20, 20, 40), (x, y, width, bar_h), border_radius=4)

    # Fill (animated by caller – just use progress)
    fill = int(width * xp_sys.progress)
    c1, c2 = (0, 200, 255), (160, 0, 255)
    # Simple gradient via two rects
    half = fill // 2
    if fill > 0:
        pygame.draw.rect(surf, c1, (x, y, half, bar_h), border_radius=4)
        if fill > half:
            pygame.draw.rect(surf, c2, (x + half, y, fill - half, bar_h),
                             border_radius=4)
    pygame.draw.rect(surf, (60, 60, 120), (x, y, width, bar_h), 1, border_radius=4)

    # Level badge
    lv_txt = font_sm.render(f"Lv {xp_sys.level}", True, (200, 200, 255))
    surf.blit(lv_txt, (x, y - 16))

    # XP text
    xp_txt = font_sm.render(
        f"{xp_sys.xp - xp_sys.xp_for_prev} / "
        f"{xp_sys.xp_for_current - xp_sys.xp_for_prev} XP",
        True, (100, 100, 160))
    surf.blit(xp_txt, (x, y + bar_h + 3))
