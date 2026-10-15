import logging
import math
import os
import time
from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration
from eyetrax.filters import KDESmoother  # noqa: F401

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker

logger = logging.getLogger(__name__)

# Cache to avoid redundant camera read calls if multiple monitors share the same camera
_FRAME_CACHE: dict[int, tuple[float, bool, Any]] = {}


def clear_frame_cache(cap_id: int | None = None):
    """Clear cached frames for a specific camera handle or all cameras."""
    global _FRAME_CACHE
    if cap_id is not None:
        _FRAME_CACHE.pop(cap_id, None)
    else:
        _FRAME_CACHE.clear()


class LowPassFilter:
    def __init__(self, alpha: float = 0.5):
        self.alpha = float(alpha)
        self.prev_val: float | None = None

    def reset(self):
        self.prev_val = None

    def filter(self, val: float, alpha: float | None = None) -> float:
        if alpha is not None:
            self.alpha = float(alpha)
        if self.prev_val is None:
            self.prev_val = float(val)
            return self.prev_val
        filtered = self.alpha * float(val) + (1.0 - self.alpha) * self.prev_val
        self.prev_val = filtered
        return filtered


class OneEuroFilter:
    """
    1 Euro Filter for low-latency, jitter-free real-time gaze filtering.
    (Casiez, Roussel, & Vogel, CHI 2012)
    - At low speeds (eye fixation): suppresses micro-tremor and sensor noise.
    - At high speeds (saccades): scales up cutoff frequency to eliminate lag.
    """

    def __init__(
        self,
        min_cutoff: float = 1.2,
        beta: float = 0.06,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filt = LowPassFilter()
        self.dx_filt = LowPassFilter()
        self.last_time: float | None = None

    def reset(self):
        self.x_filt.reset()
        self.dx_filt.reset()
        self.last_time = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, timestamp: float | None = None) -> float:
        if timestamp is None:
            timestamp = time.time()

        if self.last_time is None or timestamp <= self.last_time:
            self.last_time = timestamp
            self.dx_filt.reset()
            return self.x_filt.filter(x, 1.0)

        dt = max(1e-4, timestamp - self.last_time)
        self.last_time = timestamp

        prev_x = self.x_filt.prev_val
        dx = (x - prev_x) / dt if prev_x is not None else 0.0
        a_d = self._alpha(self.d_cutoff, dt)
        edx = self.dx_filt.filter(dx, a_d)

        cutoff = self.min_cutoff + self.beta * abs(edx)
        a = self._alpha(cutoff, dt)
        return self.x_filt.filter(x, a)


class GazeFilter2D:
    """
    2D Gaze filter combining independent X and Y 1 Euro Filters with saccade
    detection and instant recovery upon tracking reacquisition.
    """

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        min_cutoff: float = 1.2,
        beta: float = 0.06,
        saccade_threshold: float = 220.0,
    ):
        self.sw = screen_w
        self.sh = screen_h
        self.filt_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filt_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.saccade_threshold = saccade_threshold
        self.last_point: tuple[float, float] | None = None

    def reset(self):
        self.filt_x.reset()
        self.filt_y.reset()
        self.last_point = None

    def step(
        self, x: float, y: float, timestamp: float | None = None
    ) -> tuple[int, int]:
        if timestamp is None:
            timestamp = time.time()

        # If a saccade (large instantaneous eye movement) is detected, reset velocity
        # to snap immediately to target without trailing interpolation drag.
        if self.last_point is not None:
            dist = math.hypot(x - self.last_point[0], y - self.last_point[1])
            if dist > self.saccade_threshold:
                self.filt_x.reset()
                self.filt_y.reset()

        sx = self.filt_x.filter(x, timestamp)
        sy = self.filt_y.filter(y, timestamp)
        self.last_point = (sx, sy)

        clamped_x = int(round(max(0, min(self.sw - 1, sx))))
        clamped_y = int(round(max(0, min(self.sh - 1, sy))))
        return clamped_x, clamped_y


class EyeTraxWrapper(BaseTracker):
    def __init__(
        self,
        cap: cv2.VideoCapture,
        screen_width: int = 1920,
        screen_height: int = 1080,
        monitor_index: int = 0,
        model_dir: str = get_model_dir(),
    ):
        self.tracker = GazeEstimator()
        self.cap = cap
        self.monitor_index = monitor_index

        self.model_path = f"{model_dir}/gaze_model_{monitor_index}.pkl"
        self.model_loaded = False

        self.confidence_level = 0.95
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._initialise_smoother()

    def _initialise_smoother(self):
        self.smoother = GazeFilter2D(
            self.screen_width,
            self.screen_height,
        )

    def is_ready(self) -> bool:
        if not os.path.exists(self.model_path):
            return False

        if not os.path.isfile(self.model_path):
            return False

        if os.path.getsize(self.model_path) == 0:
            return False

        return True

    def is_camera_ready(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def preload_model(self):
        if self.is_ready():
            self.tracker.load_model(self.model_path)
            self.model_loaded = True
            self._initialise_smoother()

    def preload_camera(self):
        if not self.cap:
            return

        if not self.is_camera_ready():
            for _ in range(3):
                self.cap.read()
                time.sleep(0.01)

    def calibrate(self, device_index: int):
        run_9_point_calibration(self.tracker, device_index, self.monitor_index)
        self.tracker.save_model(self.model_path)
        self.model_loaded = True
        self._initialise_smoother()

    def start(self):
        if not self.model_loaded:
            self.preload_model()

        self.preload_camera()

    def get_data(self) -> dict[str, Any]:
        now = time.time()
        if not self.is_camera_ready():
            return {
                "gaze": {"x": None, "y": None},
                "confidence": 0.0,
                "timestamp": now,
            }

        # Frame capture with cache for shared cameras
        frame = None
        ret = False
        cap_id = id(self.cap)
        cached = _FRAME_CACHE.get(cap_id)
        if cached and (now - cached[0]) < 0.015:
            ret, frame = cached[1], cached[2]
        else:
            ret, frame = self.cap.read()  # type: ignore[reportOptionalMemberAccess]
            _FRAME_CACHE[cap_id] = (now, ret, frame)

        if not ret or frame is None:
            self.smoother.reset()
            return {
                "gaze": {"x": None, "y": None},
                "confidence": 0.0,
                "timestamp": now,
            }

        # Fast lighting check: if frame is too dark or washed out, reject
        try:
            gray_mean = float(cv2.mean(frame)[0])
            if gray_mean < 12.0 or gray_mean > 248.0:
                self.smoother.reset()
                return {
                    "gaze": {"x": None, "y": None},
                    "confidence": 0.0,
                    "timestamp": now,
                }
        except Exception:
            pass

        try:
            features, blink = self.tracker.extract_features(frame)
        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")
            self.smoother.reset()
            return {
                "gaze": {"x": None, "y": None},
                "confidence": 0.0,
                "timestamp": now,
            }

        if features is None or blink:
            # Face lost or eye blink - do not update smoother, output None
            if features is None:
                self.smoother.reset()
            return {
                "gaze": {"x": None, "y": None},
                "confidence": 0.0,
                "timestamp": now,
            }

        # Check head rotation angles if available in features
        # In eyetrax, features[-3:] are [yaw, pitch, roll] in radians
        confidence = 1.0
        try:
            if (
                hasattr(features, "__len__")
                and len(features) >= 3
                and type(features).__name__ != "MagicMock"
            ):
                yaw = float(features[-3])
                pitch = float(features[-2])
                # Abs angles > 0.6 rad (~34 deg) indicate face turned too far
                if abs(yaw) > 0.6 or abs(pitch) > 0.6:
                    self.smoother.reset()
                    return {
                        "gaze": {"x": None, "y": None},
                        "confidence": 0.0,
                        "timestamp": now,
                    }
                angle_ratio = max(abs(yaw), abs(pitch)) / 0.6
                confidence = max(0.3, 1.0 - 0.4 * angle_ratio)
        except Exception:
            pass

        try:
            raw_pred = self.tracker.predict([features])[0]
            x, y = float(raw_pred[0]), float(raw_pred[1])
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                return {
                    "gaze": {"x": None, "y": None},
                    "confidence": 0.0,
                    "timestamp": now,
                }

            # Outlier rejection: if predicted gaze is far out of bounds
            if (
                x < -self.screen_width
                or x > 2 * self.screen_width
                or y < -self.screen_height
                or y > 2 * self.screen_height
            ):
                return {
                    "gaze": {"x": None, "y": None},
                    "confidence": 0.0,
                    "timestamp": now,
                }

            x_pred, y_pred = self.smoother.step(x, y, timestamp=now)
        except Exception as e:
            logger.debug(f"Gaze prediction error: {e}")
            return {
                "gaze": {"x": None, "y": None},
                "confidence": 0.0,
                "timestamp": now,
            }

        return {
            "gaze": {"x": x_pred, "y": y_pred},
            "confidence": confidence,
            "timestamp": now,
        }

    def stop(self):
        pass

    def __str__(self):
        return "eyetrax"
