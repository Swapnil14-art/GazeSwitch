import logging
from typing import Any

logger = logging.getLogger(__name__)


class DwellLearner:
    """
    Adaptive dwell-time learner for gaze-based window focusing.

    The learner adjusts the required dwell time based on implicit
    user feedback:

    - Regret events (quick corrections) increase dwell time.
    - Successful focuses (user stays in window) decrease dwell time.

    The goal is to converge to a dwell threshold that matches the
    user's natural gaze behaviour while avoiding accidental focuses.
    """

    MIN_DWELL = 0.2
    MAX_DWELL = 1.2
    LEARNING_RATE = 0.05
    SUCCESS_STREAK = 3

    REGRET_MULTIPLIER = 1.5
    SUCCESS_MULTIPLIER = 1.0

    def __init__(self, base_dwell=0.5, learning_rate=None, debug=False):
        self.debug = debug
        self.dwell = base_dwell
        self.learning_rate = learning_rate or self.LEARNING_RATE
        self.success_counter = 0

    def get(self) -> float:
        return self.dwell

    def _clamp(self) -> bool:
        # Ensure dwell stays within safe bounds and avoid
        # floating point drift after repeated updates.
        new_dwell = max(self.MIN_DWELL, min(self.dwell, self.MAX_DWELL))
        new_dwell = round(new_dwell, 3)

        changed = new_dwell != self.dwell
        self.dwell = new_dwell
        return changed

    def on_focus(self):
        # reset success streak when a new auto-focus occurs
        self.success_counter = 0

    def on_regret(self, strength: float = 1.0) -> bool:
        old = self.dwell

        self.dwell *= 1 + (self.learning_rate * strength * self.REGRET_MULTIPLIER)
        changed = self._clamp()

        if changed and self.debug:
            logger.debug(f"Adaptive dwell increased: {old:.2f} → {self.dwell:.2f}")

        return changed

    def on_success(self, strength: float = 1.0) -> bool:
        self.success_counter += 1

        # Require multiple consecutive successes before reducing dwell.
        # This prevents the system from becoming overly aggressive.
        if self.success_counter < self.SUCCESS_STREAK:
            return False

        old = self.dwell

        self.dwell *= 1 - (self.learning_rate * strength * self.SUCCESS_MULTIPLIER)
        changed = self._clamp()

        self.success_counter = 0

        if changed and self.debug:
            logger.debug(f"Adaptive dwell decreased: {old:.2f} → {self.dwell:.2f}")

        return changed

    def get_state(self) -> dict[str, Any]:
        return {
            "dwell": self.dwell,
            "success_counter": self.success_counter,
        }

    def reset(self, dwell=None):
        if dwell is not None:
            self.dwell = dwell
        self.success_counter = 0
