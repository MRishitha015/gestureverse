"""
hand_tracker.py - MediaPipe Tasks Vision Hand Landmarker API.

Migrated from the deprecated mp.solutions.hands API to mediapipe.tasks.vision.
Preserves all existing functionality:
  - Fingertip tracking (index tip x/y, normalised 0-1)
  - Gesture recognition: OPEN, PINCH, FIST, POINT, PEACE, THUMBSUP
  - Dual-stage smoothing: EMA → One Euro Filter
  - Velocity-based 2-frame lookahead prediction
  - Pinch distance
  - Hand landmarks list + connections list (tuple pairs) for drawing
  - Confidence / hand_speed fields on HandData

Model setup
-----------
The Tasks API requires a .task model file.  This module downloads
``hand_landmarker.task`` into the same directory as this file on first run
if it is not already present.  Pass ``model_path`` to HandTracker.__init__
to use a different location.

Download URL (CPU float-16, ~2 MB):
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
"""

import math
import os
import time
import urllib.request
import cv2
import mediapipe as mp
import mediapipe.tasks as mt
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ── Tasks API handles ──────────────────────────────────────────────── #
_vision         = mt.vision
_HandLandmarker = _vision.HandLandmarker
_HandLandmarkerOptions = _vision.HandLandmarkerOptions
_RunningMode    = _vision.RunningMode
_BaseOptions    = mt.BaseOptions

# Canonical connection pairs as (start_idx, end_idx) tuples.
# Built once at import time from the Tasks API constant.
_HAND_CONNECTIONS: List[Tuple[int, int]] = [
    (c.start, c.end)
    for c in _vision.HandLandmarksConnections.HAND_CONNECTIONS
]

# Default model download URL and local filename.
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)
_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task"
)


# ══════════════════════════════════════════════════════════════════════ #
#  Model bootstrap
# ══════════════════════════════════════════════════════════════════════ #
def _ensure_model(path: str) -> str:
    """Download the .task model file if it is not already present."""
    if os.path.exists(path):
        return path
    print(f"[HandTracker] Downloading hand landmarker model to {path} …")
    try:
        urllib.request.urlretrieve(_MODEL_URL, path)
        print("[HandTracker] Model downloaded OK.")
    except Exception as exc:
        # Clean up partial file
        if os.path.exists(path):
            os.remove(path)
        raise RuntimeError(
            f"[HandTracker] Could not download model from {_MODEL_URL}\n"
            f"  Error: {exc}\n"
            f"  Please download the file manually and place it at:\n"
            f"    {path}\n"
            f"  or pass model_path= to HandTracker()."
        ) from exc
    return path


# ══════════════════════════════════════════════════════════════════════ #
#  One Euro Filter
# ══════════════════════════════════════════════════════════════════════ #
class _OneEuro:
    """Adaptive low-pass filter. Removes jitter, keeps fast movements."""

    def __init__(self, freq: float = 30.0, min_cutoff: float = 1.0,
                 beta: float = 0.007, d_cutoff: float = 1.0):
        self.freq       = freq
        self.min_cutoff = min_cutoff
        self.beta       = beta
        self.d_cutoff   = d_cutoff
        self._x:  Optional[float] = None
        self._dx: float = 0.0

    def _alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te  = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, freq: Optional[float] = None) -> float:
        if freq is not None:
            self.freq = freq
        if self._x is None:
            self._x = x
        dx = (x - self._x) * self.freq
        a_d = self._alpha(self.d_cutoff)
        self._dx = a_d * dx + (1.0 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = self._alpha(cutoff)
        self._x = a * x + (1.0 - a) * self._x
        return self._x


# ══════════════════════════════════════════════════════════════════════ #
#  HandData  (public interface – unchanged from v1)
# ══════════════════════════════════════════════════════════════════════ #
@dataclass
class HandData:
    """Container for one frame of hand-tracking results."""
    detected:       bool  = False
    x:              float = 0.0   # smoothed + predicted index tip x (0-1)
    y:              float = 0.0   # smoothed + predicted index tip y (0-1)
    raw_x:          float = 0.0
    raw_y:          float = 0.0
    gesture:        str   = "NONE"   # OPEN | PINCH | FIST | POINT | PEACE | THUMBSUP
    pinch_distance: float = 1.0
    landmarks:      list  = field(default_factory=list)   # [(x,y), …] 21 points
    connections:    list  = field(default_factory=list)   # [(a,b), …] index pairs
    hand_speed:     float = 0.0
    confidence:     float = 0.0


# ══════════════════════════════════════════════════════════════════════ #
#  HandTracker
# ══════════════════════════════════════════════════════════════════════ #
class HandTracker:
    """
    Tracks one hand via the MediaPipe Tasks Vision Hand Landmarker.

    Parameters
    ----------
    model_path : str, optional
        Path to ``hand_landmarker.task``.  If the file does not exist it will
        be downloaded automatically on first instantiation.
    ema_alpha : float
        EMA smoothing coefficient (0 = no smoothing, 1 = raw).
    max_hands : int
        Maximum number of hands to detect (only the first is used).
    detection_confidence : float
        Minimum confidence for initial detection.
    tracking_confidence : float
        Minimum confidence to retain tracking between frames.
    one_euro_beta : float
        One Euro filter speed coefficient (higher → less lag on fast motion).
    """

    # Landmark indices (identical to solutions API)
    THUMB_TIP  = 4
    INDEX_PIP  = 6
    INDEX_TIP  = 8
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_PIP   = 14
    RING_TIP   = 16
    PINKY_PIP  = 18
    PINKY_TIP  = 20
    WRIST      = 0
    MCP_INDEX  = 5

    PINCH_THRESHOLD = 0.06

    def __init__(
        self,
        model_path: Optional[str] = None,
        ema_alpha: float = 0.35,
        max_hands: int = 1,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.6,
        one_euro_beta: float = 0.009,
    ):
        self.ema_alpha = ema_alpha

        # Resolve and (if needed) download the model
        path = _ensure_model(model_path or _DEFAULT_MODEL_PATH)

        options = _HandLandmarkerOptions(
            base_options=_BaseOptions(model_asset_path=path),
            running_mode=_RunningMode.VIDEO,   # VIDEO gives best frame-to-frame tracking
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._landmarker = _HandLandmarker.create_from_options(options)

        # Dual-stage smoothing: EMA → One Euro
        self._sx: Optional[float] = None
        self._sy: Optional[float] = None
        self._oex = _OneEuro(freq=30.0, min_cutoff=0.8, beta=one_euro_beta)
        self._oey = _OneEuro(freq=30.0, min_cutoff=0.8, beta=one_euro_beta)

        # Velocity state (for lookahead prediction)
        self._prev_x: Optional[float] = None
        self._prev_y: Optional[float] = None
        self._prev_t: Optional[float] = None
        self._vx: float = 0.0
        self._vy: float = 0.0

        # Frame-rate estimation
        self._frame_count = 0
        self._t0 = time.perf_counter()

        # Wallclock start for VIDEO-mode timestamps (must be monotonically
        # increasing integers in milliseconds)
        self._ts_start = time.perf_counter()

    # ------------------------------------------------------------------ #
    def process(self, frame) -> HandData:
        """
        Run detection on a BGR, *already-mirrored* OpenCV frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 frame from cv2.VideoCapture after cv2.flip.

        Returns
        -------
        HandData
        """
        # Convert BGR → RGB and wrap in mp.Image (Tasks API format)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Monotonically increasing timestamp in ms (required by VIDEO mode)
        timestamp_ms = int((time.perf_counter() - self._ts_start) * 1000)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        data = HandData()
        now  = time.perf_counter()

        # Update frame-rate estimate
        self._frame_count += 1
        elapsed = now - self._t0
        freq = min(max(self._frame_count / max(elapsed, 1e-3), 15.0), 90.0)

        if result.hand_landmarks:
            # result.hand_landmarks is List[List[NormalizedLandmark]]
            lm = result.hand_landmarks[0]   # first detected hand

            raw_x = lm[self.INDEX_TIP].x
            raw_y = lm[self.INDEX_TIP].y
            data.raw_x, data.raw_y = raw_x, raw_y

            # Stage 1 – EMA
            if self._sx is None:
                self._sx, self._sy = raw_x, raw_y
                self._oex.filter(raw_x, freq)
                self._oey.filter(raw_y, freq)
            else:
                a = self.ema_alpha
                self._sx = a * raw_x + (1.0 - a) * self._sx
                self._sy = a * raw_y + (1.0 - a) * self._sy

            # Stage 2 – One Euro
            fx = self._oex.filter(self._sx, freq)
            fy = self._oey.filter(self._sy, freq)

            # Velocity for lookahead prediction
            if self._prev_x is not None and self._prev_t is not None:
                dt = now - self._prev_t
                if dt > 0:
                    self._vx = (fx - self._prev_x) / dt
                    self._vy = (fy - self._prev_y) / dt
                    data.hand_speed = math.hypot(self._vx, self._vy)

            # 2-frame lookahead (reduces perceived latency)
            lookahead = 2.0 / freq
            data.x = max(0.0, min(1.0, fx + self._vx * lookahead * 0.4))
            data.y = max(0.0, min(1.0, fy + self._vy * lookahead * 0.4))

            self._prev_x, self._prev_y, self._prev_t = fx, fy, now

            data.detected = True
            data.gesture, data.pinch_distance = self._detect_gesture(lm)

            # Confidence from handedness if available
            if result.handedness and result.handedness[0]:
                data.confidence = result.handedness[0][0].score

            # Landmark list as (x, y) tuples — same format as before
            data.landmarks   = [(p.x, p.y) for p in lm]
            # Connection pairs as (int, int) — used by draw_hand_landmarks
            data.connections = _HAND_CONNECTIONS

        else:
            data.detected = False
            # Hold last known position so the ball doesn't snap to origin
            data.x = self._sx if self._sx is not None else 0.5
            data.y = self._sy if self._sy is not None else 0.5

        return data

    # ------------------------------------------------------------------ #
    def release(self):
        """Close the landmarker and free resources."""
        self._landmarker.close()

    # ------------------------------------------------------------------ #
    def _detect_gesture(self, lm) -> Tuple[str, float]:
        """
        Classify hand pose into a named gesture.

        Uses normalised landmark coordinates directly — no dependency on
        any mediapipe gesture recogniser, so it works identically to v1.
        """
        thumb = lm[self.THUMB_TIP]
        index = lm[self.INDEX_TIP]
        pinch_d = math.hypot(thumb.x - index.x, thumb.y - index.y)

        if pinch_d < self.PINCH_THRESHOLD:
            return "PINCH", pinch_d

        # Which fingers are extended (tip.y < pip.y in image coords)
        ext = [
            self._ext(lm, self.INDEX_TIP,  self.INDEX_PIP),
            self._ext(lm, self.MIDDLE_TIP, self.MIDDLE_PIP),
            self._ext(lm, self.RING_TIP,   self.RING_PIP),
            self._ext(lm, self.PINKY_TIP,  self.PINKY_PIP),
        ]
        n = sum(ext)

        if n == 0:
            # Thumb-up special case: thumb tip above MCP-index knuckle
            if lm[self.THUMB_TIP].y < lm[self.MCP_INDEX].y:
                return "THUMBSUP", pinch_d
            return "FIST", pinch_d
        if ext[0] and n == 1:
            return "POINT", pinch_d
        if ext[0] and ext[1] and n == 2:
            return "PEACE", pinch_d   # ✌ slow-motion trigger
        return "OPEN", pinch_d

    @staticmethod
    def _ext(lm, tip: int, pip: int) -> bool:
        """Return True if the finger tip is above (smaller y) the PIP joint."""
        return lm[tip].y < lm[pip].y
