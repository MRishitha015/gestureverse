"""
game_objects.py - Neon Anti-Gravity game objects, effects, and physics.

Classes:
    ScreenShake        – trauma-based camera shake
    ScorePopup / PopupManager – floating "+10" text
    ComboTracker       – streak multiplier
    NeonBackground     – pre-rendered grid, scanlines, vignette
    GameObject         – physics ball with neon trail & glow
    ParticleSystem     – burst particles with gravity
    Collectible / CollectibleManager – glowing pick-up orbs
"""

import math
import random
import pygame
from collections import deque
from typing import Optional, Tuple, List


# ══════════════════════════════════════════════════════════════════════ #
#  Helpers
# ══════════════════════════════════════════════════════════════════════ #
def lerp_color(a: Tuple, b: Tuple, t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


# ══════════════════════════════════════════════════════════════════════ #
#  Screen Shake
# ══════════════════════════════════════════════════════════════════════ #
class ScreenShake:
    """Trauma-based screen shake (Vlambeer style)."""

    def __init__(self, decay: float = 4.0, max_px: int = 14):
        self.trauma = 0.0
        self.decay = decay
        self.max_px = max_px

    def add(self, amount: float):
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float):
        self.trauma = max(0.0, self.trauma - self.decay * dt)

    def offset(self) -> Tuple[int, int]:
        if self.trauma < 0.01:
            return (0, 0)
        s = self.trauma ** 2
        return (
            int(random.uniform(-1, 1) * self.max_px * s),
            int(random.uniform(-1, 1) * self.max_px * s),
        )


# ══════════════════════════════════════════════════════════════════════ #
#  Score Popups
# ══════════════════════════════════════════════════════════════════════ #
class _Popup:
    __slots__ = ("x", "y", "text", "color", "life", "max_life", "vy", "alive")

    def __init__(self, x, y, text, color):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.life = 1.3
        self.max_life = 1.3
        self.vy = -75.0
        self.alive = True

    def tick(self, dt):
        self.y += self.vy * dt
        self.vy *= 0.96
        self.life -= dt
        if self.life <= 0:
            self.alive = False


class PopupManager:
    """Manages floating score text."""

    def __init__(self):
        self.items: List[_Popup] = []

    def spawn(self, x: float, y: float, text: str,
              color: Tuple[int, int, int] = (255, 230, 50)):
        self.items.append(_Popup(x, y, text, color))

    def update(self, dt: float):
        for p in self.items:
            p.tick(dt)
        self.items = [p for p in self.items if p.alive]

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        for p in self.items:
            alpha = int(255 * (p.life / p.max_life))
            txt = font.render(p.text, True, p.color)
            txt.set_alpha(alpha)
            r = txt.get_rect(center=(int(p.x), int(p.y)))
            surf.blit(txt, r)


# ══════════════════════════════════════════════════════════════════════ #
#  Combo Tracker
# ══════════════════════════════════════════════════════════════════════ #
class ComboTracker:
    """Tracks rapid-collection streaks for a score multiplier."""

    def __init__(self, timeout: float = 2.5, cap: int = 5):
        self.combo = 0
        self.timer = 0.0
        self.timeout = timeout
        self.cap = cap
        self.flash = 0.0          # visual flash timer

    def hit(self):
        """Call when an orb is collected."""
        self.combo = min(self.combo + 1, self.cap) if self.timer > 0 else 1
        self.timer = self.timeout
        self.flash = 0.6

    @property
    def multiplier(self) -> int:
        return max(1, self.combo)

    def update(self, dt: float):
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0:
                self.combo = 0
        self.flash = max(0.0, self.flash - dt)


# ══════════════════════════════════════════════════════════════════════ #
#  Neon Background  (pre-rendered once at startup)
# ══════════════════════════════════════════════════════════════════════ #
class NeonBackground:
    """Cyberpunk grid, scanlines, and edge vignette."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self._grid = self._make_grid(w, h)
        self._scan = self._make_scanlines(w, h)
        self._vig  = self._make_vignette(w, h)

    # ── builders (called once) ──
    @staticmethod
    def _make_grid(w, h):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        sp = 48
        c = (0, 190, 170, 16)
        for x in range(0, w + sp, sp):
            pygame.draw.line(s, c, (x, 0), (x, h))
        for y in range(0, h + sp, sp):
            pygame.draw.line(s, c, (0, y), (w, y))
        # Brighter centre cross
        cx, cy = w // 2, h // 2
        pygame.draw.line(s, (0, 190, 170, 8), (cx, 0), (cx, h))
        pygame.draw.line(s, (0, 190, 170, 8), (0, cy), (w, cy))
        return s

    @staticmethod
    def _make_scanlines(w, h):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 3):
            pygame.draw.line(s, (0, 0, 0, 20), (0, y), (w, y))
        return s

    @staticmethod
    def _make_vignette(w, h):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        ew, eh = w // 3, h // 3
        for i in range(ew):
            f = 1 - i / ew
            a = int(f * f * 110)
            pygame.draw.line(s, (0, 0, 0, a), (i, 0), (i, h))
            pygame.draw.line(s, (0, 0, 0, a), (w - 1 - i, 0), (w - 1 - i, h))
        for j in range(eh):
            f = 1 - j / eh
            a = int(f * f * 110)
            pygame.draw.line(s, (0, 0, 0, a), (0, j), (w, j))
            pygame.draw.line(s, (0, 0, 0, a), (0, h - 1 - j), (w, h - 1 - j))
        return s

    def draw(self, surf: pygame.Surface):
        surf.blit(self._grid, (0, 0))
        surf.blit(self._scan, (0, 0))
        surf.blit(self._vig,  (0, 0))


# ══════════════════════════════════════════════════════════════════════ #
#  Game Ball
# ══════════════════════════════════════════════════════════════════════ #
class GameObject:
    """Floating ball with spring tracking, damping, and neon effects."""

    # Colour palette
    COL_NORMAL = (0, 255, 209)      # cyan
    COL_FAST   = (180, 255, 255)    # white-cyan
    COL_BOOST  = (255, 0, 170)      # hot magenta

    def __init__(self, x: float, y: float, sw: int, sh: int):
        self.x, self.y = float(x), float(y)
        self.sw, self.sh = sw, sh

        # Physics
        self.vx = 0.0
        self.vy = 0.0
        self.radius        = 22
        self.accel_factor   = 3500.0
        self.damping        = 0.91
        self.max_speed      = 1800.0
        self.bounce_factor  = 0.55

        # Boost
        self.boost_active    = False
        self.boost_multiplier = 2.8

        # Visual
        self.trail: deque = deque(maxlen=45)
        self.glow_phase = 0.0
        self.speed      = 0.0

        # Idle bob
        self._idle_t  = 0.0
        self._bob_amp = 4.0

    # ------------------------------------------------------------------ #
    @property
    def color(self) -> Tuple[int, int, int]:
        if self.boost_active:
            return self.COL_BOOST
        speed_frac = min(self.speed / 800.0, 1.0)
        return lerp_color(self.COL_NORMAL, self.COL_FAST, speed_frac)

    # ------------------------------------------------------------------ #
    def update(self, tx: Optional[float], ty: Optional[float],
               dt: float, boost: bool = False, paused: bool = False):
        dt = max(min(dt, 0.1), 1e-4)
        self.glow_phase += dt * 3.5
        self.boost_active = boost

        if paused:
            self.vx *= 0.85 ** (dt * 60)
            self.vy *= 0.85 ** (dt * 60)
            self._idle_t += dt
        elif tx is not None and ty is not None:
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            if dist > 1.0:
                nx, ny = dx / dist, dy / dist
                a = self.accel_factor * (self.boost_multiplier if boost else 1.0)
                strength = min(dist / 100.0, 3.0)
                self.vx += nx * a * strength * dt
                self.vy += ny * a * strength * dt
            self._idle_t = 0.0
        else:
            self._idle_t += dt

        # Frame-rate-independent damping
        d = self.damping ** (dt * 60)
        self.vx *= d
        self.vy *= d

        self.speed = math.hypot(self.vx, self.vy)
        if self.speed > self.max_speed:
            s = self.max_speed / self.speed
            self.vx *= s;  self.vy *= s
            self.speed = self.max_speed

        self.x += self.vx * dt
        self.y += self.vy * dt

        if self._idle_t > 0.5:
            self.y += math.sin(self._idle_t * 2.0 * math.tau) * self._bob_amp * dt * 5

        self._bounce()
        self.trail.append((self.x, self.y, self.speed, self.boost_active))

    # ------------------------------------------------------------------ #
    def _bounce(self):
        m = self.radius
        if self.x < m:
            self.x = m;  self.vx =  abs(self.vx) * self.bounce_factor
        elif self.x > self.sw - m:
            self.x = self.sw - m;  self.vx = -abs(self.vx) * self.bounce_factor
        if self.y < m:
            self.y = m;  self.vy =  abs(self.vy) * self.bounce_factor
        elif self.y > self.sh - m:
            self.y = self.sh - m;  self.vy = -abs(self.vy) * self.bounce_factor

    # ------------------------------------------------------------------ #
    def draw(self, surf: pygame.Surface):
        col = self.color
        trail = list(self.trail)
        n = max(len(trail), 1)

        # ── Trail (solid colour, darker = older → no SRCALPHA needed) ──
        for i, (tx, ty, spd, was_boost) in enumerate(trail):
            frac = i / n
            tc = self.COL_BOOST if was_boost else lerp_color(
                self.COL_NORMAL, self.COL_FAST, min(spd / 800, 1))
            fade = (int(tc[0] * frac * 0.45),
                    int(tc[1] * frac * 0.45),
                    int(tc[2] * frac * 0.45))
            r = int(self.radius * (0.25 + 0.55 * frac))
            pygame.draw.circle(surf, fade, (int(tx), int(ty)), r)

        # ── Glow rings ──
        pulse = 0.8 + 0.2 * math.sin(self.glow_phase)
        for ring in range(5, 0, -1):
            gr = int(self.radius + ring * 9 * pulse)
            ga = int(28 / ring)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*col, ga), (gr, gr), gr)
            surf.blit(gs, (int(self.x) - gr, int(self.y) - gr))

        # ── Core ──
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), self.radius)

        # ── Inner highlight ──
        hr = int(self.radius * 0.45)
        hc = tuple(min(c + 90, 255) for c in col)
        pygame.draw.circle(surf, hc, (int(self.x) - 3, int(self.y) - 3), hr)


# ══════════════════════════════════════════════════════════════════════ #
#  Particle System
# ══════════════════════════════════════════════════════════════════════ #
class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "end_color",
                 "life", "max_life", "radius", "alive", "gravity")

    def __init__(self, x, y, vx, vy, color, end_color, life, radius, gravity):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.end_color = end_color
        self.life = life
        self.max_life = life
        self.radius = radius
        self.alive = True
        self.gravity = gravity

    def tick(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= 0.97
        self.vy *= 0.97
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf):
        if not self.alive:
            return
        frac = self.life / self.max_life
        alpha = int(255 * frac)
        r = max(1, int(self.radius * frac))
        col = lerp_color(self.end_color, self.color, frac)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col, alpha), (r, r), r)
        surf.blit(s, (int(self.x) - r, int(self.y) - r))


class ParticleSystem:
    """Burst-particle manager with gravity and colour interpolation."""

    MAX_PARTICLES = 250

    def __init__(self):
        self.particles: List[_Particle] = []

    def emit(
        self, x: float, y: float, count: int = 8,
        color: Tuple[int, int, int] = (255, 160, 0),
        end_color: Optional[Tuple[int, int, int]] = None,
        speed_range: Tuple[float, float] = (80, 250),
        lifetime_range: Tuple[float, float] = (0.3, 0.8),
        radius_range: Tuple[int, int] = (2, 6),
        gravity: float = 120.0,
    ):
        if end_color is None:
            end_color = color
        budget = self.MAX_PARTICLES - len(self.particles)
        for _ in range(min(count, budget)):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(*speed_range)
            self.particles.append(_Particle(
                x, y,
                math.cos(ang) * spd, math.sin(ang) * spd,
                color, end_color,
                random.uniform(*lifetime_range),
                random.randint(*radius_range),
                gravity,
            ))

    def update(self, dt: float):
        for p in self.particles:
            p.tick(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, surf: pygame.Surface):
        for p in self.particles:
            p.draw(surf)


# ══════════════════════════════════════════════════════════════════════ #
#  Collectibles
# ══════════════════════════════════════════════════════════════════════ #
class Collectible:
    """Glowing pick-up orb with orbiting dots."""

    def __init__(self, x: float, y: float):
        self.x, self.y = x, y
        self.radius = 12
        self.color  = (255, 230, 50)
        self.alive  = True
        self._phase = random.uniform(0, math.tau)
        self._speed = random.uniform(2.5, 4.0)
        self._orbit_phase = random.uniform(0, math.tau)

    def update(self, dt: float):
        self._phase += dt * self._speed
        self._orbit_phase += dt * 3.0

    def draw(self, surf: pygame.Surface):
        if not self.alive:
            return
        p = 0.7 + 0.3 * math.sin(self._phase)

        # Glow rings
        for ring in range(3, 0, -1):
            gr = int(self.radius + ring * 6 * p)
            ga = int(25 / ring)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*self.color, ga), (gr, gr), gr)
            surf.blit(gs, (int(self.x) - gr, int(self.y) - gr))

        # Main orb
        pygame.draw.circle(surf, self.color,
                           (int(self.x), int(self.y)), int(self.radius * p))
        # Bright centre
        ir = max(2, int(self.radius * 0.4 * p))
        pygame.draw.circle(surf, (255, 255, 220),
                           (int(self.x), int(self.y)), ir)

        # Orbiting dots (2 dots 180° apart)
        orbit_r = int(self.radius * 1.8)
        for k in range(2):
            a = self._orbit_phase + k * math.pi
            dx = int(math.cos(a) * orbit_r)
            dy = int(math.sin(a) * orbit_r)
            pygame.draw.circle(surf, (255, 255, 180),
                               (int(self.x) + dx, int(self.y) + dy), 2)

    def collides(self, ox: float, oy: float, orad: float) -> bool:
        return math.hypot(self.x - ox, self.y - oy) < (self.radius + orad)


class CollectibleManager:
    """Spawns, updates, and collects orbs."""

    def __init__(self, sw: int, sh: int, max_orbs: int = 5):
        self.sw, self.sh = sw, sh
        self.max_orbs = max_orbs
        self.orbs: List[Collectible] = []
        self._timer = 0.0
        self._interval = 2.0
        for _ in range(3):
            self._spawn()

    def _spawn(self):
        m = 70
        self.orbs.append(Collectible(
            random.randint(m, self.sw - m),
            random.randint(m, self.sh - m)))

    def update(self, dt: float, ball: GameObject,
               particles: ParticleSystem,
               combo: ComboTracker,
               popups: PopupManager,
               shake: ScreenShake) -> int:
        """Returns total score earned this frame."""
        earned = 0
        for o in self.orbs:
            o.update(dt)
            if o.alive and o.collides(ball.x, ball.y, ball.radius):
                o.alive = False
                combo.hit()
                pts = 10 * combo.multiplier
                earned += pts
                # Effects
                particles.emit(o.x, o.y, count=18,
                               color=(255, 230, 50), end_color=(255, 120, 0),
                               speed_range=(100, 320),
                               lifetime_range=(0.4, 1.0),
                               gravity=80)
                popups.spawn(o.x, o.y - 20,
                             f"+{pts}" if combo.multiplier == 1
                             else f"+{pts} x{combo.multiplier}",
                             (255, 230, 50))
                shake.add(0.25)
        self.orbs = [o for o in self.orbs if o.alive]

        self._timer += dt
        if self._timer >= self._interval and len(self.orbs) < self.max_orbs:
            self._timer = 0.0
            self._spawn()
        return earned

    def draw(self, surf: pygame.Surface):
        for o in self.orbs:
            o.draw(surf)
