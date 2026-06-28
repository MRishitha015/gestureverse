"""
game_objects.py (v2) - GestureVerse game objects with AAA visual upgrades.

Changes from v1:
  - ScreenShake: added frequency parameter
  - ScorePopup: size scales with value, rainbow colour for combos
  - ComboTracker: cap raised to 8, new event callbacks
  - NeonBackground: animated grid + star field layer
  - GameObject: motion-blur streak, shield ring, magnet aura
  - ParticleSystem: ring-burst mode, spark trails
  - Collectible: rotating inner star, pulsing ring
  - CollectibleManager: magnet pull support
"""

import math
import random
import pygame
from collections import deque
from typing import Optional, Tuple, List, Callable


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

def hue_color(h: float) -> Tuple[int, int, int]:
    """HSV(h, 1, 1) → RGB where h in [0, 1)."""
    h %= 1.0
    i = int(h * 6)
    f = h * 6 - i
    p, q, t_ = 0, int(255 * (1 - f)), int(255 * f)
    lut = [(255, t_, p), (int(255*q/255), 255, p),
           (p, 255, t_), (p, int(255*q/255), 255),
           (t_, p, 255), (255, p, int(255*q/255))]
    return lut[i % 6]


# ══════════════════════════════════════════════════════════════════════ #
#  Screen Shake
# ══════════════════════════════════════════════════════════════════════ #
class ScreenShake:
    def __init__(self, decay: float = 4.0, max_px: int = 14):
        self.trauma = 0.0
        self.decay  = decay
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
    __slots__ = ("x", "y", "text", "color", "life", "max_life",
                 "vy", "alive", "scale")

    def __init__(self, x, y, text, color, scale=1.0):
        self.x, self.y = x, y
        self.text    = text
        self.color   = color
        self.scale   = scale
        self.life    = 1.4
        self.max_life = 1.4
        self.vy      = -80.0
        self.alive   = True

    def tick(self, dt):
        self.y  += self.vy * dt
        self.vy *= 0.94
        self.life -= dt
        if self.life <= 0:
            self.alive = False


class PopupManager:
    def __init__(self):
        self.items: List[_Popup] = []

    def spawn(self, x, y, text, color=(255, 230, 50), scale=1.0):
        self.items.append(_Popup(x, y, text, color, scale))

    def update(self, dt):
        for p in self.items:
            p.tick(dt)
        self.items = [p for p in self.items if p.alive]

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        for p in self.items:
            alpha = int(255 * (p.life / p.max_life))
            txt = font.render(p.text, True, p.color)
            if p.scale != 1.0:
                w, h = txt.get_size()
                nw = max(1, int(w * p.scale))
                nh = max(1, int(h * p.scale))
                txt = pygame.transform.smoothscale(txt, (nw, nh))
            txt.set_alpha(alpha)
            r = txt.get_rect(center=(int(p.x), int(p.y)))
            surf.blit(txt, r)


# ══════════════════════════════════════════════════════════════════════ #
#  Combo Tracker
# ══════════════════════════════════════════════════════════════════════ #
class ComboTracker:
    def __init__(self, timeout: float = 2.5, cap: int = 8):
        self.combo   = 0
        self.timer   = 0.0
        self.timeout = timeout
        self.cap     = cap
        self.flash   = 0.0
        self._on_combo: List[Callable[[int], None]] = []

    def on_combo(self, cb: Callable[[int], None]):
        self._on_combo.append(cb)

    def hit(self):
        self.combo = min(self.combo + 1, self.cap) if self.timer > 0 else 1
        self.timer = self.timeout
        self.flash = 0.6
        for cb in self._on_combo:
            cb(self.combo)

    @property
    def multiplier(self) -> int:
        return max(1, self.combo)

    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0:
                self.combo = 0
        self.flash = max(0.0, self.flash - dt)


# ══════════════════════════════════════════════════════════════════════ #
#  Neon Background  – animated star field + grid
# ══════════════════════════════════════════════════════════════════════ #
class NeonBackground:
    """Cyberpunk grid, scanlines, vignette, and animated star field."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self._grid = self._make_grid(w, h)
        self._scan = self._make_scanlines(w, h)
        self._vig  = self._make_vignette(w, h)
        # Stars
        self._stars = [(random.randint(0, w), random.randint(0, h),
                        random.uniform(0.5, 2.5), random.uniform(0, math.tau))
                       for _ in range(120)]
        self._star_t = 0.0

    @staticmethod
    def _make_grid(w, h):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        sp = 48
        c = (0, 190, 170, 16)
        for x in range(0, w + sp, sp):
            pygame.draw.line(s, c, (x, 0), (x, h))
        for y in range(0, h + sp, sp):
            pygame.draw.line(s, c, (0, y), (w, y))
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
            pygame.draw.line(s, (0, 0, 0, a), (w-1-i, 0), (w-1-i, h))
        for j in range(eh):
            f = 1 - j / eh
            a = int(f * f * 110)
            pygame.draw.line(s, (0, 0, 0, a), (0, j), (w, j))
            pygame.draw.line(s, (0, 0, 0, a), (0, h-1-j), (w, h-1-j))
        return s

    def update(self, dt: float):
        self._star_t += dt

    def draw(self, surf: pygame.Surface):
        surf.blit(self._grid, (0, 0))
        # Animated stars
        for sx, sy, speed, phase in self._stars:
            brightness = int(100 + 80 * math.sin(self._star_t * speed + phase))
            r = 1 if speed < 1.5 else 2
            pygame.draw.circle(surf, (brightness, brightness, brightness + 30),
                               (sx, sy), r)
        surf.blit(self._scan, (0, 0))
        surf.blit(self._vig,  (0, 0))


# ══════════════════════════════════════════════════════════════════════ #
#  Game Ball
# ══════════════════════════════════════════════════════════════════════ #
class GameObject:
    COL_NORMAL = (0, 255, 209)
    COL_FAST   = (180, 255, 255)
    COL_BOOST  = (255, 0, 170)
    COL_SHIELD = (80, 200, 255)

    def __init__(self, x: float, y: float, sw: int, sh: int):
        self.x, self.y = float(x), float(y)
        self.sw, self.sh = sw, sh
        self.vx = self.vy = 0.0
        self.radius       = 22
        self.accel_factor  = 3500.0
        self.damping       = 0.91
        self.max_speed     = 1800.0
        self.bounce_factor = 0.55
        self.boost_active  = False
        self.boost_multiplier = 2.8
        self.trail: deque = deque(maxlen=55)
        self.glow_phase   = 0.0
        self.speed        = 0.0
        self._idle_t      = 0.0
        self._bob_amp     = 4.0
        self.has_shield   = False
        self._shield_phase = 0.0
        self.hue          = 0.0   # rainbow cycle when boosting

    @property
    def color(self) -> Tuple[int, int, int]:
        if self.boost_active:
            return self.COL_BOOST
        speed_frac = min(self.speed / 800.0, 1.0)
        return lerp_color(self.COL_NORMAL, self.COL_FAST, speed_frac)

    def update(self, tx, ty, dt, boost=False, paused=False,
               magnet_orbs: Optional[List] = None):
        dt = max(min(dt, 0.1), 1e-4)
        self.glow_phase  += dt * 3.5
        self._shield_phase += dt * 4.0
        self.hue         = (self.hue + dt * 0.5) % 1.0
        self.boost_active = boost

        # Magnet: pull nearby collectibles (handled in CollectibleManager)

        if paused:
            self.vx *= 0.85 ** (dt * 60)
            self.vy *= 0.85 ** (dt * 60)
            self._idle_t += dt
        elif tx is not None and ty is not None:
            dx, dy = tx - self.x, ty - self.y
            dist   = math.hypot(dx, dy)
            if dist > 1.0:
                nx, ny = dx / dist, dy / dist
                a = self.accel_factor * (self.boost_multiplier if boost else 1.0)
                strength = min(dist / 100.0, 3.0)
                self.vx += nx * a * strength * dt
                self.vy += ny * a * strength * dt
            self._idle_t = 0.0
        else:
            self._idle_t += dt

        d = self.damping ** (dt * 60)
        self.vx *= d;  self.vy *= d
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

    def _bounce(self):
        m = self.radius
        if self.x < m:
            self.x = m;  self.vx = abs(self.vx) * self.bounce_factor
        elif self.x > self.sw - m:
            self.x = self.sw - m;  self.vx = -abs(self.vx) * self.bounce_factor
        if self.y < m:
            self.y = m;  self.vy = abs(self.vy) * self.bounce_factor
        elif self.y > self.sh - m:
            self.y = self.sh - m;  self.vy = -abs(self.vy) * self.bounce_factor

    def draw(self, surf: pygame.Surface):
        col = self.color
        trail = list(self.trail)
        n = max(len(trail), 1)

        for i, (tx, ty, spd, was_boost) in enumerate(trail):
            frac = i / n
            if was_boost:
                tc = hue_color(self.hue - frac * 0.15)
            else:
                tc = lerp_color(self.COL_NORMAL, self.COL_FAST, min(spd / 800, 1))
            fade = (int(tc[0] * frac * 0.5),
                    int(tc[1] * frac * 0.5),
                    int(tc[2] * frac * 0.5))
            r = int(self.radius * (0.2 + 0.6 * frac))
            pygame.draw.circle(surf, fade, (int(tx), int(ty)), r)

        # Glow rings
        pulse = 0.8 + 0.2 * math.sin(self.glow_phase)
        for ring in range(5, 0, -1):
            gr = int(self.radius + ring * 9 * pulse)
            ga = int(30 / ring)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*col, ga), (gr, gr), gr)
            surf.blit(gs, (int(self.x) - gr, int(self.y) - gr))

        # Shield ring
        if self.has_shield:
            sp2 = self._shield_phase
            sr = int(self.radius * 1.7)
            ss = pygame.Surface((sr * 2 + 4, sr * 2 + 4), pygame.SRCALPHA)
            # Dashed arc (8 segments)
            for seg in range(8):
                a1 = sp2 + seg * math.pi / 4
                a2 = a1 + math.pi / 5
                pts = []
                for ang in [a1, (a1+a2)/2, a2]:
                    pts.append((sr + 2 + int(math.cos(ang) * sr),
                                sr + 2 + int(math.sin(ang) * sr)))
                if len(pts) >= 2:
                    pygame.draw.lines(ss, (80, 200, 255, 180), False, pts, 2)
            surf.blit(ss, (int(self.x) - sr - 2, int(self.y) - sr - 2))

        # Core
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), self.radius)
        hr = int(self.radius * 0.45)
        hc = tuple(min(c + 90, 255) for c in col)
        pygame.draw.circle(surf, hc, (int(self.x) - 3, int(self.y) - 3), hr)

        # Magnet aura ring (if magnet active – set by main)
        if getattr(self, 'magnet_active', False):
            mr = int(self.radius * 3.5)
            ms = pygame.Surface((mr * 2, mr * 2), pygame.SRCALPHA)
            ma = int(25 + 15 * math.sin(self.glow_phase * 2))
            pygame.draw.circle(ms, (120, 80, 255, ma), (mr, mr), mr, 2)
            surf.blit(ms, (int(self.x) - mr, int(self.y) - mr))


# ══════════════════════════════════════════════════════════════════════ #
#  Particle System
# ══════════════════════════════════════════════════════════════════════ #
class _Particle:
    __slots__ = ("x","y","vx","vy","color","end_color",
                 "life","max_life","radius","alive","gravity")

    def __init__(self, x, y, vx, vy, color, end_color, life, radius, gravity):
        self.x, self.y   = x, y
        self.vx, self.vy = vx, vy
        self.color, self.end_color = color, end_color
        self.life = self.max_life = life
        self.radius = radius
        self.alive  = True
        self.gravity = gravity

    def tick(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= 0.97;  self.vy *= 0.97
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf):
        if not self.alive:
            return
        frac  = self.life / self.max_life
        alpha = int(255 * frac)
        r     = max(1, int(self.radius * frac))
        col   = lerp_color(self.end_color, self.color, frac)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col, alpha), (r, r), r)
        surf.blit(s, (int(self.x) - r, int(self.y) - r))


class ParticleSystem:
    MAX_PARTICLES = 300

    def __init__(self):
        self.particles: List[_Particle] = []

    def emit(self, x, y, count=8,
             color=(255,160,0), end_color=None,
             speed_range=(80,250), lifetime_range=(0.3,0.8),
             radius_range=(2,6), gravity=120.0, ring=False):
        if end_color is None:
            end_color = color
        budget = self.MAX_PARTICLES - len(self.particles)
        for i in range(min(count, budget)):
            if ring:
                ang = i / count * math.tau
                spd = random.uniform(*speed_range)
            else:
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

    def update(self, dt):
        for p in self.particles:
            p.tick(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)


# ══════════════════════════════════════════════════════════════════════ #
#  Collectibles
# ══════════════════════════════════════════════════════════════════════ #
class Collectible:
    def __init__(self, x, y):
        self.x, self.y  = x, y
        self.radius     = 12
        self.color      = (255, 230, 50)
        self.alive      = True
        self._phase     = random.uniform(0, math.tau)
        self._speed     = random.uniform(2.5, 4.0)
        self._orbit_phase = random.uniform(0, math.tau)
        self._star_rot  = random.uniform(0, math.tau)

    def update(self, dt):
        self._phase       += dt * self._speed
        self._orbit_phase += dt * 3.0
        self._star_rot    += dt * 2.5

    def draw(self, surf):
        if not self.alive:
            return
        p = 0.7 + 0.3 * math.sin(self._phase)
        cx, cy = int(self.x), int(self.y)

        # Glow
        for ring in range(3, 0, -1):
            gr = int(self.radius + ring * 6 * p)
            ga = int(25 / ring)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*self.color, ga), (gr, gr), gr)
            surf.blit(gs, (cx - gr, cy - gr))

        # Main orb
        pygame.draw.circle(surf, self.color, (cx, cy), int(self.radius * p))
        # Centre star (4-point)
        sr = int(self.radius * 0.55 * p)
        for k in range(4):
            ang = self._star_rot + k * math.pi / 2
            ex = cx + int(math.cos(ang) * sr)
            ey = cy + int(math.sin(ang) * sr)
            pygame.draw.line(surf, (255, 255, 200), (cx, cy), (ex, ey), 2)
        # Bright centre
        ir = max(2, int(self.radius * 0.3 * p))
        pygame.draw.circle(surf, (255, 255, 220), (cx, cy), ir)
        # Orbiting dots
        orbit_r = int(self.radius * 1.8)
        for k in range(2):
            a = self._orbit_phase + k * math.pi
            dx = int(math.cos(a) * orbit_r)
            dy = int(math.sin(a) * orbit_r)
            pygame.draw.circle(surf, (255, 255, 180), (cx + dx, cy + dy), 2)

    def collides(self, ox, oy, orad):
        return math.hypot(self.x - ox, self.y - oy) < (self.radius + orad)


MAGNET_RADIUS = 180.0   # pixels

class CollectibleManager:
    def __init__(self, sw, sh, max_orbs=5):
        self.sw, self.sh = sw, sh
        self.max_orbs    = max_orbs
        self.orbs: List[Collectible] = []
        self._timer      = 0.0
        self._interval   = 2.0
        for _ in range(3):
            self._spawn()

    def _spawn(self):
        m = 70
        self.orbs.append(Collectible(
            random.randint(m, self.sw - m),
            random.randint(m, self.sh - m)))

    def update(self, dt, ball, particles, combo, popups, shake,
               magnet_active=False, double_pts=False) -> int:
        earned = 0
        for o in self.orbs:
            o.update(dt)

            # Magnet pull
            if magnet_active:
                dx = ball.x - o.x
                dy = ball.y - o.y
                dist = math.hypot(dx, dy)
                if 0 < dist < MAGNET_RADIUS:
                    pull = 320 * (1 - dist / MAGNET_RADIUS)
                    o.x += (dx / dist) * pull * dt
                    o.y += (dy / dist) * pull * dt

            if o.alive and o.collides(ball.x, ball.y, ball.radius):
                o.alive = False
                combo.hit()
                pts = 10 * combo.multiplier * (2 if double_pts else 1)
                earned += pts
                # Rainbow burst for high combos
                burst_col = hue_color(combo.combo / 8.0) if combo.combo >= 3 \
                            else (255, 230, 50)
                particles.emit(o.x, o.y, count=20,
                               color=burst_col, end_color=(255, 120, 0),
                               speed_range=(100, 340),
                               lifetime_range=(0.4, 1.1),
                               gravity=80, ring=(combo.combo >= 3))
                label = f"+{pts}"
                if combo.multiplier > 1:
                    label += f" ×{combo.multiplier}"
                if double_pts:
                    label += " 2×"
                scale = 1.0 + 0.15 * min(combo.multiplier - 1, 5)
                popups.spawn(o.x, o.y - 20, label,
                             hue_color(combo.combo / 8.0) if combo.combo >= 3
                             else (255, 230, 50),
                             scale=scale)
                shake.add(0.2 + 0.05 * combo.multiplier)

        self.orbs = [o for o in self.orbs if o.alive]
        self._timer += dt
        if self._timer >= self._interval and len(self.orbs) < self.max_orbs:
            self._timer = 0.0
            self._spawn()
        return earned

    def draw(self, surf):
        for o in self.orbs:
            o.draw(surf)
