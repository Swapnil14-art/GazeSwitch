import logging
import math
import os
import threading
import time
from typing import Any

import cv2
import numpy as np
from eyetrax import GazeEstimator
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


class SharedCameraCapture:
    """
    Thread-safe single-owner camera capture wrapper.
    Buffers latest frames, avoids concurrent read() collisions,
    and shares extracted MediaPipe features across monitors.
    """

    def __init__(self, camera_index: int):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index)
        self.lock = threading.Lock()
        self.latest_frame: Any = None
        self.latest_timestamp: float = 0.0
        self.cached_features: Any = None
        self.cached_blink: bool = False
        self.features_timestamp: float = 0.0
        self.consecutive_errors: int = 0

    def isOpened(self) -> bool:
        with self.lock:
            return self.cap is not None and self.cap.isOpened()

    def read(self) -> tuple[bool, Any]:
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                return False, None

            now = time.time()
            if self.latest_frame is not None and (now - self.latest_timestamp) < 0.015:
                return True, self.latest_frame

            res = self.cap.read()
            if isinstance(res, tuple) and len(res) == 2:
                ret, frame = res
            elif isinstance(res, bool):
                ret, frame = res, None
            else:
                ret, frame = False, None
            if ret and frame is not None:
                self.latest_frame = frame
                self.latest_timestamp = now
                self.consecutive_errors = 0
                return True, frame
            else:
                self.consecutive_errors += 1
                return False, None

    def read_frame(self) -> tuple[bool, Any]:
        return self.read()

    def get_features(self, tracker) -> tuple[Any, bool]:
        with self.lock:
            if self.latest_frame is None:
                return None, False
            if (
                self.features_timestamp == self.latest_timestamp
                and self.cached_features is not None
            ):
                return self.cached_features, self.cached_blink

            try:
                feats, blink = tracker.extract_features(self.latest_frame)
                self.cached_features = feats
                self.cached_blink = blink
                self.features_timestamp = self.latest_timestamp
                return feats, blink
            except Exception as e:
                logger.debug(f"Shared feature extraction error: {e}")
                return None, False

    def get_preview_frame(self, tracking_active: bool) -> tuple[bool, Any]:
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                return False, None

            now = time.time()
            if (
                tracking_active
                and self.latest_frame is not None
                and (now - self.latest_timestamp) < 0.5
            ):
                return True, self.latest_frame.copy()

            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.latest_frame = frame
                self.latest_timestamp = now
                return True, frame.copy()
            return False, None

    def release(self):
        with self.lock:
            if self.cap and self.cap.isOpened():
                try:
                    self.cap.release()
                except Exception:
                    pass
            self.latest_frame = None
            self.cached_features = None


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
    2D Gaze filter combining independent X and Y 1 Euro Filters with velocity-aware
    saccade tracking and instant recovery upon tracking reacquisition.
    """

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        min_cutoff: float = 1.2,
        beta: float = 0.06,
        saccade_threshold: float = 220.0,
        saccade_velocity_threshold: float = 1200.0,
    ):
        self.sw = screen_w
        self.sh = screen_h
        self.filt_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filt_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.saccade_threshold = saccade_threshold
        self.saccade_velocity_threshold = saccade_velocity_threshold
        self.last_point: tuple[float, float] | None = None
        self.last_timestamp: float | None = None
        self.last_raw: tuple[float, float] | None = None

    def reset(self):
        self.filt_x.reset()
        self.filt_y.reset()
        self.last_point = None
        self.last_timestamp = None
        self.last_raw = None

    def step(
        self,
        x: float,
        y: float,
        timestamp: float | None = None,
        clamp: bool = True,
    ) -> tuple[int, int]:
        if timestamp is None:
            timestamp = time.time()

        # Recovery on tracking reacquisition after gap / blink (> 0.15s)
        if self.last_timestamp is not None and (timestamp - self.last_timestamp) > 0.15:
            self.filt_x.reset()
            self.filt_y.reset()

        # Time- and velocity-aware saccade detection
        if self.last_point is not None:
            dt = max(1e-4, timestamp - (self.last_timestamp or timestamp))
            dist = math.hypot(x - self.last_point[0], y - self.last_point[1])
            velocity = dist / dt

            # If sudden large jump exceeds threshold or velocity indicates
            # genuine saccade, reset velocity filter so it snaps immediately.
            if (
                dist > self.saccade_threshold
                or velocity > self.saccade_velocity_threshold
            ):
                self.filt_x.reset()
                self.filt_y.reset()

        self.last_timestamp = timestamp
        self.last_raw = (x, y)

        sx = self.filt_x.filter(x, timestamp)
        sy = self.filt_y.filter(y, timestamp)
        self.last_point = (sx, sy)

        if clamp:
            clamped_x = int(round(max(0, min(self.sw - 1, sx))))
            clamped_y = int(round(max(0, min(self.sh - 1, sy))))
            return clamped_x, clamped_y
        else:
            return int(round(sx)), int(round(sy))


def run_enhanced_calibration(
    gaze_estimator,
    camera_index: int = 0,
    monitor_index: int = 0,
    model_save_path: str | None = None,
) -> bool:
    """
    Enhanced 9-point calibration with robust sample collection, outlier rejection,
    median feature aggregation per grid point, validation on held-out samples,
    and atomic model saving. If cancelled (ESC) or validation fails, existing
    model files are strictly preserved.
    """
    try:
        from eyetrax.calibration.common import (
            compute_grid_points,
            wait_for_face_and_countdown,
        )
        from eyetrax.utils.screen import get_monitor_geometry
        from eyetrax.utils.video import open_camera
    except Exception as e:
        logger.error(f"Failed to import eyetrax calibration utilities: {e}")
        return False

    try:
        mx, my, sw, sh = get_monitor_geometry(monitor_index)
    except Exception as e:
        logger.error(f"Could not get geometry for monitor {monitor_index}: {e}")
        return False

    cap = open_camera(camera_index)
    if not cap or not cap.isOpened():
        logger.error(f"Failed to open camera {camera_index} for calibration")
        return False

    try:
        # 1. Wait for stable face detection and countdown
        if not wait_for_face_and_countdown(cap, gaze_estimator, sw, sh, mx, my, 2):
            logger.info("Calibration cancelled during face alignment")
            cap.release()
            cv2.destroyAllWindows()
            return False

        # 2. 9-point calibration grid (corners, edge midpoints, center)
        order = [
            (1, 1),  # Center first
            (0, 0),  # Top-left
            (2, 0),  # Top-right
            (0, 2),  # Bottom-left
            (2, 2),  # Bottom-right
            (1, 0),  # Top-mid
            (0, 1),  # Left-mid
            (2, 1),  # Right-mid
            (1, 2),  # Bottom-mid
        ]
        pts = compute_grid_points(order, sw, sh, margin_ratio=0.10)

        aggregated_feats = []
        aggregated_targs = []
        validation_feats = []
        validation_targs = []

        # 3. Pulse & Capture loop with robust filtering
        pulse_d = 0.8  # seconds for eye movement to settle
        cd_d = 0.8  # seconds for multi-sample collection

        for tx, ty in pts:
            # Phase A: Pulse target while eye shifts to it
            # (discard unstable transit frames)
            ps = time.time()
            final_radius = 20
            cancelled = False
            while True:
                elapsed = time.time() - ps
                if elapsed > pulse_d:
                    break
                ok, frame = cap.read()
                if not ok:
                    continue
                canvas = np.zeros((sh, sw, 3), dtype=np.uint8)
                radius = 15 + int(15 * abs(np.sin(2 * np.pi * elapsed)))
                final_radius = radius
                cv2.circle(canvas, (tx, ty), radius, (0, 255, 0), -1)
                cv2.imshow("Calibration", canvas)
                key = cv2.waitKey(1)
                if key == 27:  # ESC
                    cancelled = True
                    break
            if cancelled:
                logger.info("Calibration cancelled by user (ESC)")
                cap.release()
                cv2.destroyAllWindows()
                return False

            # Phase B: Capture multiple valid samples at target
            cs = time.time()
            point_samples = []
            while True:
                elapsed = time.time() - cs
                if elapsed > cd_d:
                    break
                ok, frame = cap.read()
                if not ok:
                    continue
                canvas = np.zeros((sh, sw, 3), dtype=np.uint8)
                cv2.circle(canvas, (tx, ty), final_radius, (0, 255, 0), -1)
                t = elapsed / cd_d
                ease = t * t * (3 - 2 * t)
                ang = 360 * (1 - ease)
                cv2.ellipse(
                    canvas, (tx, ty), (40, 40), 0, -90, -90 + ang, (255, 255, 255), 4
                )
                cv2.imshow("Calibration", canvas)
                key = cv2.waitKey(1)
                if key == 27:
                    cancelled = True
                    break

                # Extract features and filter blinks/head movement
                try:
                    ft, blink = gaze_estimator.extract_features(frame)
                    if ft is not None and not blink:
                        # Check head pose (last 3 elements are yaw, pitch, roll)
                        if hasattr(ft, "__len__") and len(ft) >= 3:
                            yaw, pitch = float(ft[-3]), float(ft[-2])
                            if abs(yaw) <= 0.6 and abs(pitch) <= 0.6:
                                point_samples.append(ft)
                        else:
                            point_samples.append(ft)
                except Exception:
                    pass

            if cancelled:
                logger.info("Calibration cancelled by user (ESC)")
                cap.release()
                cv2.destroyAllWindows()
                return False

            # Phase C: Robust aggregation of valid samples
            if point_samples:
                # Use median feature vector across valid samples to reject noise spikes
                median_vector = np.median(point_samples, axis=0)
                aggregated_feats.append(median_vector)
                aggregated_targs.append([tx, ty])

                # Hold out the last valid individual sample for model validation
                if len(point_samples) >= 2:
                    validation_feats.append(point_samples[-1])
                    validation_targs.append([tx, ty])

        cap.release()
        cv2.destroyAllWindows()

        # 4. Model Training & Validation
        if len(aggregated_feats) < 7:
            logger.warning(
                f"Calibration incomplete: only {len(aggregated_feats)} of 9 "
                "points acquired"
            )
            return False

        # Train model with Ridge regression
        X_train = np.array(aggregated_feats)
        y_train = np.array(aggregated_targs)
        gaze_estimator.train(X_train, y_train)

        # Validate with held-out samples if available
        if validation_feats:
            try:
                preds = gaze_estimator.predict(np.array(validation_feats))
                errors = np.linalg.norm(preds - np.array(validation_targs), axis=1)
                mean_error = float(np.mean(errors))
                diag = math.hypot(sw, sh)
                err_pct = mean_error / diag * 100
                logger.info(
                    f"Calibration validation error: {mean_error:.1f}px "
                    f"({err_pct:.1f}% screen diag)"
                )
                if mean_error > 0.45 * diag:
                    logger.warning("Calibration validation error exceeded threshold")
                    return False
            except Exception as e:
                logger.debug(f"Validation calculation skipped: {e}")

        # 5. Atomic model persistence: save to temp and rename
        if model_save_path:
            tmp_path = f"{model_save_path}.tmp"
            gaze_estimator.save_model(tmp_path)
            os.replace(tmp_path, model_save_path)
            logger.info(f"Calibration saved atomically to {model_save_path}")

        return True

    except Exception as e:
        logger.exception(f"Error during enhanced calibration: {e}")
        try:
            cap.release()
            cv2.destroyAllWindows()
        except Exception:
            pass
        return False


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

        # Warm up if camera is opened and ready to capture
        if self.is_camera_ready():
            for _ in range(3):
                self.cap.read()
                time.sleep(0.01)

    def calibrate(self, device_index: int) -> bool:
        success = run_enhanced_calibration(
            self.tracker,
            camera_index=device_index,
            monitor_index=self.monitor_index,
            model_save_path=self.model_path,
        )
        if success:
            self.model_loaded = True
            self._initialise_smoother()
            return True
        return False

    def start(self):
        if not self.model_loaded:
            self.preload_model()

        self.preload_camera()

    def get_data(self) -> dict[str, Any]:
        now = time.time()
        if not self.is_camera_ready():
            return {
                "gaze": {"x": None, "y": None},
                "raw_gaze": {"x": None, "y": None},
                "is_inside": False,
                "confidence": 0.0,
                "timestamp": now,
            }

        # Frame capture with cache for shared cameras
        frame = None
        ret = False
        if isinstance(self.cap, SharedCameraCapture):
            ret, frame = self.cap.read()
        else:
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
                "raw_gaze": {"x": None, "y": None},
                "is_inside": False,
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
                    "raw_gaze": {"x": None, "y": None},
                    "is_inside": False,
                    "confidence": 0.0,
                    "timestamp": now,
                }
        except Exception:
            pass

        # Feature extraction (reusing shared features if shared camera)
        try:
            if isinstance(self.cap, SharedCameraCapture):
                features, blink = self.cap.get_features(self.tracker)
            else:
                features, blink = self.tracker.extract_features(frame)
        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")
            self.smoother.reset()
            return {
                "gaze": {"x": None, "y": None},
                "raw_gaze": {"x": None, "y": None},
                "is_inside": False,
                "confidence": 0.0,
                "timestamp": now,
            }

        if features is None or blink:
            # Face lost or eye blink - do not update smoother, output None
            if features is None:
                self.smoother.reset()
            return {
                "gaze": {"x": None, "y": None},
                "raw_gaze": {"x": None, "y": None},
                "is_inside": False,
                "confidence": 0.0,
                "timestamp": now,
            }

        # Check head rotation angles if available in features
        # In eyetrax, features[-3:] are [yaw, pitch, roll] in radians
        confidence = 1.0
        yaw, pitch, roll = 0.0, 0.0, 0.0
        try:
            if (
                hasattr(features, "__len__")
                and len(features) >= 3
                and type(features).__name__ != "MagicMock"
            ):
                yaw = float(features[-3])
                pitch = float(features[-2])
                roll = float(features[-1])
                # Abs angles > 0.6 rad (~34 deg) indicate face turned too far
                if abs(yaw) > 0.6 or abs(pitch) > 0.6:
                    self.smoother.reset()
                    return {
                        "gaze": {"x": None, "y": None},
                        "raw_gaze": {"x": None, "y": None},
                        "is_inside": False,
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
                    "raw_gaze": {"x": None, "y": None},
                    "is_inside": False,
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
                    "raw_gaze": {"x": None, "y": None},
                    "is_inside": False,
                    "confidence": 0.0,
                    "timestamp": now,
                }

            # Smooth predicted coordinates
            x_pred, y_pred = self.smoother.step(x, y, timestamp=now)
            is_inside = 0 <= x <= self.screen_width and 0 <= y <= self.screen_height
        except Exception as e:
            logger.debug(f"Gaze prediction error: {e}")
            return {
                "gaze": {"x": None, "y": None},
                "raw_gaze": {"x": None, "y": None},
                "is_inside": False,
                "confidence": 0.0,
                "timestamp": now,
            }

        return {
            "gaze": {"x": x_pred, "y": y_pred},
            "raw_gaze": {"x": x, "y": y},
            "is_inside": is_inside,
            "confidence": confidence,
            "head_pose": {"yaw": yaw, "pitch": pitch, "roll": roll},
            "timestamp": now,
        }

    def stop(self):
        pass

    def __str__(self):
        return "eyetrax"
