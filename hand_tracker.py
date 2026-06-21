"""
hand_tracker.py - MediaPipe hand tracking with EMA smoothing, gesture detection,
                  and hand-speed estimation.
"""

import math
import time
import cv2
import mediapipe as mp
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class HandData:
    """Container for a single frame of hand-tracking results."""
    detected: bool = False
    x: float = 0.0            # Smoothed index fingertip x (normalised 0-1)
    y: float = 0.0            # Smoothed index fingertip y (normalised 0-1)
    raw_x: float = 0.0
    raw_y: float = 0.0
    gesture: str = "NONE"     # OPEN | PINCH | FIST | POINT
    pinch_distance: float = 1.0
    landmarks: list = field(default_factory=list)
    connections: list = field(default_factory=list)
    hand_speed: float = 0.0   # Normalised units / second


class HandTracker:
    """Tracks one hand via MediaPipe Hands with EMA smoothing."""

    # Landmark indices
    THUMB_TIP  = 4
    INDEX_PIP  = 6
    INDEX_TIP  = 8
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_PIP   = 14
    RING_TIP   = 16
    PINKY_PIP  = 18
    PINKY_TIP  = 20

    PINCH_THRESHOLD = 0.06

    def __init__(
        self,
        ema_alpha: float = 0.35,
        max_hands: int = 1,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.6,
    ):
        self.ema_alpha = ema_alpha

        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self.mp_connections = mp.solutions.hands.HAND_CONNECTIONS

        # EMA state
        self._sx: Optional[float] = None
        self._sy: Optional[float] = None

        # Speed tracking
        self._prev_x: Optional[float] = None
        self._prev_y: Optional[float] = None
        self._prev_t: Optional[float] = None

    # ------------------------------------------------------------------ #
    def process(self, frame) -> HandData:
        """Run detection on a BGR, *already-mirrored* frame."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.mp_hands.process(rgb)

        data = HandData()
        now = time.perf_counter()

        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0].landmark
            raw_x, raw_y = lm[self.INDEX_TIP].x, lm[self.INDEX_TIP].y
            data.raw_x, data.raw_y = raw_x, raw_y

            # ── EMA filter ──
            if self._sx is None:
                self._sx, self._sy = raw_x, raw_y
            else:
                a = self.ema_alpha
                self._sx = a * raw_x + (1 - a) * self._sx
                self._sy = a * raw_y + (1 - a) * self._sy

            data.detected = True
            data.x, data.y = self._sx, self._sy

            # ── Hand speed ──
            if self._prev_x is not None and self._prev_t is not None:
                dt = now - self._prev_t
                if dt > 0:
                    data.hand_speed = math.hypot(
                        self._sx - self._prev_x,
                        self._sy - self._prev_y,
                    ) / dt
            self._prev_x, self._prev_y, self._prev_t = self._sx, self._sy, now

            data.gesture, data.pinch_distance = self._detect_gesture(lm)
            data.landmarks  = [(l.x, l.y) for l in lm]
            data.connections = list(self.mp_connections)
        else:
            data.detected = False
            data.x = self._sx if self._sx is not None else 0.5
            data.y = self._sy if self._sy is not None else 0.5

        return data

    def release(self):
        self.mp_hands.close()

    # ------------------------------------------------------------------ #
    def _detect_gesture(self, lm) -> Tuple[str, float]:
        thumb, index = lm[self.THUMB_TIP], lm[self.INDEX_TIP]
        pinch_d = math.hypot(thumb.x - index.x, thumb.y - index.y)

        if pinch_d < self.PINCH_THRESHOLD:
            return "PINCH", pinch_d

        ext = [
            self._ext(lm, self.INDEX_TIP,  self.INDEX_PIP),
            self._ext(lm, self.MIDDLE_TIP, self.MIDDLE_PIP),
            self._ext(lm, self.RING_TIP,   self.RING_PIP),
            self._ext(lm, self.PINKY_TIP,  self.PINKY_PIP),
        ]
        n = sum(ext)
        if n == 0:
            return "FIST", pinch_d
        if ext[0] and n == 1:
            return "POINT", pinch_d
        return "OPEN", pinch_d

    @staticmethod
    def _ext(lm, tip: int, pip: int) -> bool:
        return lm[tip].y < lm[pip].y
