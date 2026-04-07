import pytest

from trackers.base_tracker import BaseTracker


class BadTracker(BaseTracker):
    """
    Tracker that does not implement abstract methods.
    """

    pass


def test_abstract_methods_enforced():
    """
    Subclasses must implement required abstract methods.
    """
    with pytest.raises(TypeError):
        BadTracker()  # type: ignore
