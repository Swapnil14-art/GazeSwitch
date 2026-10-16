import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import numpy as np

from core.tracker import GazeTracker
from tests.fixtures.dummy_window_manager import DummyWindowManager
from trackers.eyetrax_tracker import (
    EyeTraxWrapper,
    GazeFilter2D,
    SharedCameraCapture,
)


class CustomDummyWindowManager(DummyWindowManager):
    def __init__(self):
        super().__init__()
        self.windows_list = [
            {"title": "Window 1", "rect": (0, 0, 800, 600), "handle": 1},
            {"title": "Window 2", "rect": (2000, 0, 2800, 600), "handle": 2},
        ]
        self._cached_windows = None
        self._cache_time = 0.0
        self._cache_ttl = 0.25

    def get_windows(self, force_refresh: bool = False):
        now = time.time()
        if (
            not force_refresh
            and self._cached_windows is not None
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cached_windows
        self._cached_windows = list(self.windows_list)
        self._cache_time = now
        return self._cached_windows

    def invalidate_window_cache(self):
        self._cached_windows = None
        self._cache_time = 0.0


class DummyMonitor:
    def __init__(self, x, y, width, height, name):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.name = name


def test_multi_monitor_arbitration_selects_secondary_monitor():
    """
    Test that gaze on Monitor 1 is correctly selected instead of Monitor 0.
    Previously, the loop terminated on Monitor 0 prematurely.
    """
    monitors = [
        DummyMonitor(x=0, y=0, width=1920, height=1080, name="Mon0"),
        DummyMonitor(x=1920, y=0, width=1920, height=1080, name="Mon1"),
    ]

    with (
        patch("core.tracker.get_monitors", return_value=monitors),
        patch("core.tracker.cv2.VideoCapture"),
        patch("core.tracker.keyboard.Listener"),
        patch("core.tracker.keyboard.GlobalHotKeys"),
    ):
        wm = CustomDummyWindowManager()
        tracker = GazeTracker(window_manager=wm)

        # Mock estimators for both monitors
        est0 = MagicMock()
        est0.is_camera_ready.return_value = True
        # Estimator 0 reports gaze far off to the right (outside monitor 0)
        est0.get_data.return_value = {
            "gaze": {"x": 2200, "y": 300},
            "raw_gaze": {"x": 2200, "y": 300},
            "is_inside": False,
            "confidence": 0.5,
            "head_pose": {"yaw": 0.2, "pitch": 0.0, "roll": 0.0},
        }

        est1 = MagicMock()
        est1.is_camera_ready.return_value = True
        # Estimator 1 reports gaze squarely inside monitor 1
        est1.get_data.return_value = {
            "gaze": {"x": 300, "y": 300},
            "raw_gaze": {"x": 300, "y": 300},
            "is_inside": True,
            "confidence": 0.95,
            "head_pose": {"yaw": 0.2, "pitch": 0.0, "roll": 0.0},
        }

        tracker.estimators = {0: est0, 1: est1}
        tracker.monitor_camera_mapping = {
            0: {"enabled": True, "camera_index": 0},
            1: {"enabled": True, "camera_index": 0},
        }

        # Run tracker step
        tracker._run_tracker_step()

        # Candidate on Monitor 1 must be chosen: virtual coords = 300 + 1920 = 2220, 300
        # Target window at point (2220, 300) is Window 2 (x=2000..2800)
        assert tracker._tracker_last_target is not None
        assert tracker._tracker_last_target["title"] == "Window 2"


def test_negative_monitor_coordinates_support():
    """
    Test monitor positioned to the left of the primary display
    (negative virtual coordinates).
    """
    monitors = [
        DummyMonitor(x=-1920, y=0, width=1920, height=1080, name="LeftMon"),
        DummyMonitor(x=0, y=0, width=1920, height=1080, name="PrimaryMon"),
    ]

    with (
        patch("core.tracker.get_monitors", return_value=monitors),
        patch("core.tracker.cv2.VideoCapture"),
        patch("core.tracker.keyboard.Listener"),
        patch("core.tracker.keyboard.GlobalHotKeys"),
    ):
        wm = CustomDummyWindowManager()
        tracker = GazeTracker(window_manager=wm)
        assert tracker.virtual_left == -1920
        assert tracker.virtual_right == 1920


def test_calibration_cancellation_preserves_existing_model():
    """
    Test that aborting or cancelling calibration never overwrites or destroys
    an existing valid model file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "gaze_model_0.pkl")
        # Create an existing valid model
        with open(model_path, "wb") as f:
            f.write(b"EXISTING_VALID_MODEL_DATA_DO_NOT_CORRUPT")

        wrapper = EyeTraxWrapper(
            cap=MagicMock(),
            screen_width=1920,
            screen_height=1080,
            monitor_index=0,
            model_dir=tmpdir,
        )

        # Mock run_enhanced_calibration to simulate user pressing ESC (returns False)
        with patch(
            "trackers.eyetrax_tracker.run_enhanced_calibration", return_value=False
        ):
            res = wrapper.calibrate(device_index=0)
            assert res is False

        # Verify existing model data was preserved intact
        with open(model_path, "rb") as f:
            content = f.read()
        assert content == b"EXISTING_VALID_MODEL_DATA_DO_NOT_CORRUPT"


def test_shared_camera_handle_updated_for_all_estimators_after_calibration():
    """
    Test that when calibration reacquires a shared camera handle, all estimators
    using that camera index receive the updated handle.
    """
    monitors = [
        DummyMonitor(x=0, y=0, width=1920, height=1080, name="Mon0"),
        DummyMonitor(x=1920, y=0, width=1920, height=1080, name="Mon1"),
    ]

    with (
        patch("core.tracker.get_monitors", return_value=monitors),
        patch("core.tracker.cv2.VideoCapture"),
        patch("core.tracker.keyboard.Listener"),
        patch("core.tracker.keyboard.GlobalHotKeys"),
    ):
        wm = CustomDummyWindowManager()
        tracker = GazeTracker(window_manager=wm)

        # Both monitors share camera 0
        tracker.monitor_camera_mapping = {
            0: {"enabled": True, "camera_index": 0},
            1: {"enabled": True, "camera_index": 0},
        }

        est0 = MagicMock()
        est0.calibrate.return_value = True
        est1 = MagicMock()

        tracker.estimators = {0: est0, 1: est1}

        with patch("core.tracker.SharedCameraCapture") as MockCapture:
            mock_new_cap = MagicMock()
            MockCapture.return_value = mock_new_cap

            tracker.calibrate(monitor_id=0)

            # Both estimators must now reference the new capture handle
            assert est0.cap == mock_new_cap
            assert est1.cap == mock_new_cap


def test_shared_camera_capture_buffer_and_preview():
    """
    Test that SharedCameraCapture buffers frames, preventing concurrent cv2
    read() calls, and supplies frames to preview safely.
    """
    mock_cv2_cap = MagicMock()
    mock_cv2_cap.isOpened.return_value = True
    test_frame = np.full((100, 100, 3), 200, dtype=np.uint8)
    mock_cv2_cap.read.return_value = (True, test_frame)

    with patch("trackers.eyetrax_tracker.cv2.VideoCapture", return_value=mock_cv2_cap):
        shared_cap = SharedCameraCapture(0)

        # First read
        ret, frame = shared_cap.read()
        assert ret is True
        assert mock_cv2_cap.read.call_count == 1

        # Read immediately after (< 15 ms) should return buffered frame
        # without calling cv2.read() again
        ret2, frame2 = shared_cap.read()
        assert ret2 is True
        assert mock_cv2_cap.read.call_count == 1

        # Preview frame request during active tracking should return copy of
        # latest frame
        ret_prev, prev_frame = shared_cap.get_preview_frame(tracking_active=True)
        assert ret_prev is True
        assert prev_frame is not None
        assert mock_cv2_cap.read.call_count == 1


def test_camera_warmup_logic_fixed():
    """
    Test that preload_camera warms up when is_camera_ready() is True.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, np.zeros((10, 10, 3), dtype=np.uint8))

    wrapper = EyeTraxWrapper(cap=mock_cap)
    wrapper.preload_camera()

    # Cap.read() should have been called 3 times during warmup
    assert mock_cap.read.call_count == 3


def test_monitor_disconnection_preserves_configuration():
    """
    Test that disconnecting a monitor does not delete its settings from config.
    """
    monitors_2 = [
        DummyMonitor(x=0, y=0, width=1920, height=1080, name="Mon0"),
        DummyMonitor(x=1920, y=0, width=1920, height=1080, name="Mon1"),
    ]

    with (
        patch("core.tracker.get_monitors", return_value=monitors_2),
        patch("core.tracker.cv2.VideoCapture"),
        patch("core.tracker.keyboard.Listener"),
        patch("core.tracker.keyboard.GlobalHotKeys"),
        patch("core.tracker.save_config"),
    ):
        wm = CustomDummyWindowManager()
        tracker = GazeTracker(window_manager=wm)
        tracker.config["monitor_camera_mapping"] = {
            0: {"enabled": True, "camera_index": 0},
            1: {"enabled": True, "camera_index": 1},
        }

        # Simulate monitor 1 being disconnected (only monitor 0 remains)
        tracker.monitor_rects = [
            {
                "id": 0,
                "name": "Mon0",
                "left": 0,
                "top": 0,
                "right": 1920,
                "bottom": 1080,
                "width": 1920,
                "height": 1080,
            }
        ]
        normalised = tracker._normalise_monitor_camera_mapping()

        # Monitor 1 must still be in normalised mapping!
        assert 1 in normalised
        assert normalised[1]["camera_index"] == 1


def test_window_caching_and_invalidation():
    """
    Test that get_windows caches within TTL and invalidate_window_cache clears it.
    """
    wm = CustomDummyWindowManager()
    wins1 = wm.get_windows()
    assert len(wins1) == 2

    # Change underlying windows without invalidating
    wm.windows_list.append(
        {"title": "Window 3", "rect": (500, 500, 900, 800), "handle": 3}
    )
    wins2 = wm.get_windows()
    # Should still return cached 2 windows
    assert len(wins2) == 2

    # Invalidate cache
    wm.invalidate_window_cache()
    wins3 = wm.get_windows()
    # Now returns fresh 3 windows
    assert len(wins3) == 3


def test_transient_tracking_error_resilience():
    """
    Test that _run_tracker does not shut down on transient errors.
    """
    wm = CustomDummyWindowManager()
    with (
        patch(
            "core.tracker.get_monitors",
            return_value=[DummyMonitor(0, 0, 1920, 1080, "Mon0")],
        ),
        patch("core.tracker.cv2.VideoCapture"),
        patch("core.tracker.keyboard.Listener"),
        patch("core.tracker.keyboard.GlobalHotKeys"),
    ):
        tracker = GazeTracker(window_manager=wm)
        tracker.running = True

        call_count = [0]

        def mock_step():
            call_count[0] += 1
            if call_count[0] < 5:
                raise RuntimeError("Transient frame capture error")
            tracker.running = False  # Exit loop safely after testing resilience

        tracker._run_tracker_step = mock_step

        with patch("core.tracker.time.sleep"):
            tracker._run_tracker()

        # Tracker handled 4 transient errors and continued running until
        # explicitly stopped
        assert call_count[0] == 5


def test_filter_velocity_aware_saccades():
    """
    Test that GazeFilter2D handles high-velocity saccades (> 1200 px/s)
    by catching up rapidly.
    """
    gf = GazeFilter2D(1920, 1080)
    # Fixation at (100, 100)
    gf.step(100, 100, timestamp=1.0)
    gf.step(100, 100, timestamp=1.03)

    # Large sudden jump to (1200, 800) after 30 ms (velocity ~ 40,000 px/s)
    x, y = gf.step(1200, 800, timestamp=1.06)
    # Must catch up fast without locking to the old position
    assert x > 900
    assert y > 600
