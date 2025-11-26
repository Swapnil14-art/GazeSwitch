import math
import statistics
from collections import defaultdict


def compute_euclidean_error(samples: list[dict[str, float]]) -> float | None:
    """
    Computes the mean Euclidean error from the evaluation CSV file.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.
    """
    if not samples:
        return None

    errors = [
        math.sqrt((s["tracker_x"] - s["gt_x"]) ** 2 + (s["tracker_y"] - s["gt_y"]) ** 2)
        for s in samples
        if s["tracker_x"] is not None and s["tracker_y"] is not None
    ]

    return sum(errors) / len(errors) if errors else None


def get_zone(x: float, y: float, zones: list[tuple[int, int, int, int]]) -> int | None:
    """
    Maps a point to a zone index.

    Args:
        x (float): The x-coordinate of the point.
        y (float): The y-coordinate of the point.
        zones (list[tuple[int, int, int, int]]): A list of zones defined by (x_min, x_max, y_min, y_max).

    Returns:
        int | None: The index of the zone the point belongs to, or None if it doesn't belong to any zone.
    """
    for i, (x_min, x_max, y_min, y_max) in enumerate(zones):
        if x_min <= x < x_max and y_min <= y < y_max:
            return i
    return None


def compute_zone_accuracy(
    samples: list[dict[str, float]], screen_size: tuple, rows: int, cols: int
) -> float | None:
    """
    Computes the zone accuracy from the evaluation CSV file.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.
        screen_size (tuple): The size of the screen (width, height).
        rows (int): The number of rows in the grid.
        cols (int): The number of columns in the grid.
    """
    if not samples:
        return None

    screen_w, screen_h = screen_size
    zone_width = screen_w // cols
    zone_height = screen_h // rows
    zones = [
        (c * zone_width, (c + 1) * zone_width, r * zone_height, (r + 1) * zone_height)
        for r in range(rows)
        for c in range(cols)
    ]

    correct = 0
    total = 0
    for s in samples:
        gx, gy = float(s["gt_x"]), float(s["gt_y"])
        tx, ty = float(s["tracker_x"]), float(s["tracker_y"])

        gt_zone = get_zone(gx, gy, zones)
        tracker_zone = get_zone(tx, ty, zones)
        if tracker_zone is not None and tracker_zone == gt_zone:
            correct += 1
        total += 1

    return (correct / total * 100) if total > 0 else None


def compute_confusion_matrix(
    samples: list[dict[str, float]], screen_size: tuple[int, int], rows: int, cols: int
) -> list[list[int]]:
    """
    Computes the confusion matrix for zone predictions.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.
        screen_size (tuple[int, int]): The size of the screen.
        rows (int): The number of rows in the grid.
        cols (int): The number of columns in the grid.

    Returns:
        list[list[int]]: The confusion matrix as a 2D list.
    """
    if not samples:
        return []

    screen_w, screen_h = screen_size
    zone_width = screen_w // cols
    zone_height = screen_h // rows
    n = rows * cols

    zones = [
        (c * zone_width, (c + 1) * zone_width, r * zone_height, (r + 1) * zone_height)
        for r in range(rows)
        for c in range(cols)
    ]

    matrix = [[0 for _ in range(n)] for _ in range(n)]

    for s in samples:
        gt = get_zone(float(s["gt_x"]), float(s["gt_y"]), zones)
        pred = get_zone(float(s["tracker_x"]), float(s["tracker_y"]), zones)
        if gt is not None and pred is not None:
            matrix[gt][pred] += 1

    return matrix


def compute_latency(samples: list[dict[str, float]]) -> dict[str, float] | None:
    """
    Computes latency from the evaluation samples.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        dict[str, float]: A dictionary with mean, median, and 95th percentile latency in milliseconds.
    """
    if not samples:
        return None

    latencies = [s["latency"] for s in samples]

    return (
        {
            "mean_ms": 1000 * sum(latencies) / len(latencies),
            "median_ms": 1000 * sorted(latencies)[len(latencies) // 2],
            "p95_ms": 1000 * sorted(latencies)[int(len(latencies) * 0.95)],
        }
        if latencies
        else None
    )


def compute_validity(samples: list[dict[str, float | None]]) -> float:
    """
    Computes the validity percentage of the tracker data.

    Args:
        samples (list[dict[str, float | None]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        float: The percentage of valid tracker data.
    """
    valid = [
        s for s in samples if s["tracker_x"] is not None and s["tracker_y"] is not None
    ]

    return len(valid) / len(samples) if samples else 0.0


def compute_jitter(
    samples: list[dict[str, float]],
) -> dict[str, dict[str, float]] | None:
    """
    Computes the jitter (standard deviation) of tracker points grouped by ground truth points.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        dict[str, dict[str, float]]: A dictionary mapping ground truth points to their jitter statistics.
    """
    jitter = {}

    groups = {}
    for s in samples:
        key = (s["gt_x"], s["gt_y"])
        groups.setdefault(key, []).append(s)

    for key, group in groups.items():
        xs = [g["tracker_x"] for g in group if g["tracker_x"] is not None]
        ys = [g["tracker_y"] for g in group if g["tracker_y"] is not None]

        if xs and ys:
            jitter[key] = {
                "std_x": statistics.pstdev(xs),
                "std_y": statistics.pstdev(ys),
            }

    jitter_json = {f"{k[0]}_{k[1]}": v for k, v in jitter.items()}
    return jitter_json if jitter_json else None


def compute_accuracy(
    samples: list[dict[str, float]],
) -> dict[str, float | list[float]] | None:
    """
    Computes the accuracy (ACC) which quantifies the distance between the mean of recorded
    gaze points and the true target location.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        dict[str, float]: A dictionary with per-point accuracy and mean accuracy.
    """
    if not samples:
        return None

    groups = defaultdict(list)
    for s in samples:
        gx, gy = s.get("gt_x"), s.get("gt_y")
        tx, ty = s.get("tracker_x"), s.get("tracker_y")

        if tx is None or ty is None:
            continue

        groups[(gx, gy)].append((tx, ty))

    acc_values = []

    for (gx, gy), pts in groups.items():
        if not pts:
            continue

        mean_x = sum(p[0] for p in pts) / len(pts)
        mean_y = sum(p[1] for p in pts) / len(pts)

        acc = math.sqrt((mean_x - gx) ** 2 + (mean_y - gy) ** 2)
        acc_values.append(acc)

    if not acc_values:
        return None

    return {"per_point_acc": acc_values, "mean_acc": sum(acc_values) / len(acc_values)}


def compute_rms_s2s(samples: list[dict[str, float]]) -> float | None:
    """
    Computes RMS-S2S (root mean square of sample-to-sample distances).
    Measures precision/noise across the entire sequence.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        float: The RMS-S2S value in pixels.
    """
    if not samples:
        return None

    pts = [
        (s["tracker_x"], s["tracker_y"])
        for s in samples
        if s["tracker_x"] is not None and s["tracker_y"] is not None
    ]

    sq_diffs = []
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        dx = x2 - x1
        dy = y2 - y1
        sq_diffs.append(dx * dx + dy * dy)

    return math.sqrt(sum(sq_diffs) / (len(sq_diffs))) if sq_diffs else None
