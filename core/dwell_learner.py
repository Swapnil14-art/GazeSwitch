import logging

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

    def __init__(self, base_dwell=0.5):
        self.dwell = base_dwell
        self.success_counter = 0

    def get(self):
        return self.dwell

    def _clamp(self):
        # Ensure dwell stays within safe bounds and avoid
        # floating point drift after repeated updates.
        self.dwell = max(self.MIN_DWELL, min(self.dwell, self.MAX_DWELL))
        self.dwell = round(self.dwell, 3)

    def on_focus(self):
        # reset success streak when a new auto-focus occurs
        self.success_counter = 0

    def on_regret(self):
        old = self.dwell

        self.dwell *= 1 + self.LEARNING_RATE
        self._clamp()

        changed = self.dwell != old

        if changed:
            logger.debug(f"Adaptive dwell increased: {old:.2f} → {self.dwell:.2f}")

        return changed

    def on_success(self):
        self.success_counter += 1

        # Require multiple consecutive successes before reducing dwell.
        # This prevents the system from becoming overly aggressive.
        if self.success_counter < self.SUCCESS_STREAK:
            return False

        old = self.dwell

        self.dwell *= 1 - self.LEARNING_RATE
        self._clamp()

        self.success_counter = 0

        changed = self.dwell != old

        if changed:
            logger.debug(f"Adaptive dwell decreased: {old:.2f} → {self.dwell:.2f}")

        return changed
