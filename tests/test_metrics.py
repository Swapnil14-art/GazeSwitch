import math

from evaluation.metrics import (
    compute_accuracy,
    compute_confusion_matrix,
    compute_euclidean_error,
    compute_jitter,
    compute_latency,
    compute_rms_s2s,
    compute_validity,
    compute_zone_accuracy,
    get_zone,
)


# ------------------------------
# Euclidean error
# ------------------------------
def test_compute_euclidean_error():
    samples = [
        {
            "gt_x": 0.0,
            "gt_y": 0.0,
            "tracker_x": 3.0,
            "tracker_y": 4.0,
            "timestamp": 0,
            "latency": 0,
        },
        {
            "gt_x": 1.0,
            "gt_y": 1.0,
            "tracker_x": 4.0,
            "tracker_y": 5.0,
            "timestamp": 1,
            "latency": 0,
        },
    ]
    result = compute_euclidean_error(samples)
    assert result == 5.0


# ------------------------------
# get_zone
# ------------------------------
def test_get_zone_inside():
    zones = [(0, 10, 0, 10), (10, 20, 0, 10)]
    assert get_zone(5, 5, zones) == 0
    assert get_zone(15, 5, zones) == 1


def test_get_zone_outside():
    zones = [(0, 10, 0, 10)]
    assert get_zone(11, 5, zones) is None


# ------------------------------
# Zone accuracy
# ------------------------------
def test_compute_zone_accuracy_perfect():
    samples = [
        {"gt_x": 5.0, "gt_y": 5.0, "tracker_x": 5.0, "tracker_y": 5.0},
        {"gt_x": 15.0, "gt_y": 5.0, "tracker_x": 15.0, "tracker_y": 5.0},
    ]
    screen_size = (20, 10)
    result = compute_zone_accuracy(samples, screen_size, 1, 2)
    assert result == 100.0


def test_compute_zone_accuracy_partial():
    samples = [
        {"gt_x": 5.0, "gt_y": 5.0, "tracker_x": 15.0, "tracker_y": 5.0},  # wrong
        {"gt_x": 15.0, "gt_y": 5.0, "tracker_x": 15.0, "tracker_y": 5.0},  # correct
    ]
    screen_size = (20, 10)
    result = compute_zone_accuracy(samples, screen_size, 1, 2)
    assert result == 50.0


# ------------------------------
# Confusion matrix
# ------------------------------
def test_compute_confusion_matrix():
    samples = [
        {"gt_x": 5.0, "gt_y": 5.0, "tracker_x": 5.0, "tracker_y": 5.0},
        {"gt_x": 15.0, "gt_y": 5.0, "tracker_x": 15.0, "tracker_y": 5.0},
    ]
    screen_size = (20, 10)
    matrix = compute_confusion_matrix(samples, screen_size, 1, 2)
    assert matrix == [[1, 0], [0, 1]]


# ------------------------------
# Latency
# ------------------------------
def test_compute_latency():
    samples = [{"latency": 0.01}, {"latency": 0.02}, {"latency": 0.03}]
    result = compute_latency(samples)
    assert result is not None
    assert math.isclose(result["mean_ms"], 20.0)
    assert math.isclose(result["median_ms"], 20.0)
    assert math.isclose(result["p95_ms"], 30.0)


# ------------------------------
# Validity
# ------------------------------
def test_compute_validity():
    samples = [
        {"tracker_x": 1, "tracker_y": 1},
        {"tracker_x": None, "tracker_y": None},
        {"tracker_x": 2, "tracker_y": 2},
    ]
    result = compute_validity(samples)
    assert math.isclose(result, 2 / 3)


# ------------------------------
# Jitter
# ------------------------------
def test_compute_jitter():
    samples = [
        {"gt_x": 0.0, "gt_y": 0.0, "tracker_x": 1.0, "tracker_y": 2.0},
        {"gt_x": 0.0, "gt_y": 0.0, "tracker_x": 3.0, "tracker_y": 4.0},
    ]
    result = compute_jitter(samples)
    key = "0.0_0.0"
    assert result is not None
    assert key in result
    assert "std_x" in result[key]
    assert "std_y" in result[key]


def test_jitter_groups_correctly():
    samples = [
        {"gt_x": 100.0, "gt_y": 100.0, "tracker_x": 10.0, "tracker_y": 10.0},
        {"gt_x": 100.0, "gt_y": 100.0, "tracker_x": 12.0, "tracker_y": 9.0},
        {"gt_x": 200.0, "gt_y": 200.0, "tracker_x": 30.0, "tracker_y": 30.0},
    ]

    jitter = compute_jitter(samples)
    assert jitter is not None
    assert len(jitter) == 2

    assert any("100" in key for key in jitter.keys())
    assert any("200" in key for key in jitter.keys())


# ------------------------------
# Accuracy
# ------------------------------
def test_compute_accuracy():
    samples = [
        {"gt_x": 0.0, "gt_y": 0.0, "tracker_x": 1.0, "tracker_y": 1.0},
        {"gt_x": 0.0, "gt_y": 0.0, "tracker_x": 2.0, "tracker_y": 2.0},
    ]
    result = compute_accuracy(samples)
    assert result is not None
    mean_acc = result["mean_acc"]
    expected = math.sqrt(((1.5 - 0) ** 2 + (1.5 - 0) ** 2))
    assert mean_acc == expected


# ------------------------------
# RMS S2S
# ------------------------------
def test_compute_rms_s2s():
    samples = [
        {"tracker_x": 0.0, "tracker_y": 0.0},
        {"tracker_x": 3.0, "tracker_y": 4.0},
    ]
    result = compute_rms_s2s(samples)
    assert result is not None
    assert math.isclose(result, 5.0)


# ------------------------------
# Edge Cases
# ------------------------------
def test_empty_samples():
    samples = []

    assert compute_accuracy(samples) is None
    assert compute_euclidean_error(samples) is None
    assert compute_rms_s2s(samples) is None
    assert compute_latency(samples) is None
    assert compute_zone_accuracy(samples, (1000, 1000), 3, 3) is None
    assert compute_jitter(samples) == None
    assert compute_validity(samples) == 0.0


def test_all_missing_tracker_data():
    samples = [
        {
            "gt_x": 100,
            "gt_y": 100,
            "tracker_x": None,
            "tracker_y": None,
            "timestamp": 1.0,
            "latency": 0.1,
        },
        {
            "gt_x": 200,
            "gt_y": 200,
            "tracker_x": None,
            "tracker_y": None,
            "timestamp": 2.0,
            "latency": 0.1,
        },
    ]

    assert compute_validity(samples) == 0.0
    assert compute_accuracy(samples) is None
    assert compute_euclidean_error(samples) is None
    assert compute_rms_s2s(samples) is None
    assert compute_jitter(samples) is None


def test_weird_values_negative_and_out_of_bounds():
    samples = [
        {
            "gt_x": 100,
            "gt_y": 100,
            "tracker_x": -50.0,
            "tracker_y": 2000.0,
            "timestamp": 1.0,
            "latency": 0.2,
        },
        {
            "gt_x": 100,
            "gt_y": 100,
            "tracker_x": -60.0,
            "tracker_y": 2100.0,
            "timestamp": 2.0,
            "latency": 0.3,
        },
    ]

    err = compute_euclidean_error(samples)
    assert err is not None
    assert err > 0

    jitter = compute_jitter(samples)
    assert jitter is not None
    assert len(jitter) == 1
    key = list(jitter.keys())[0]
    assert "100" in key
