import math
import statistics


def compute_euclidean_error(samples: list[dict[str, float]]) -> float | None:
    """
    Computes the mean Euclidean error from the evaluation CSV file.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.
    """
    errors = [
        math.sqrt((s["tracker_x"] - s["gt_x"]) ** 2 + (s["tracker_y"] - s["gt_y"]) ** 2)
        for s in samples
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


def compute_confusion_matrix(samples, screen_size, rows, cols):
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
        gt = get_zone(s["gt_x"], s["gt_y"], zones)
        pred = get_zone(s["tracker_x"], s["tracker_y"], zones)
        if gt is not None and pred is not None:
            matrix[gt][pred] += 1

    return matrix


def compute_latency(samples: list[dict[str, float]]) -> dict[str, float]:
    """
    Computes latency from the evaluation samples.

    Args:
        samples (list[dict[str, float]]): A list of samples with ground truth and tracker coordinates, and timestamps.

    Returns:
        dict[str, float]: A dictionary with mean, median, and 95th percentile latency in milliseconds.
    """
    latencies = [s["latency"] for s in samples]

    return {
        "mean_ms": 1000 * sum(latencies) / len(latencies),
        "median_ms": 1000 * sorted(latencies)[len(latencies) // 2],
        "p95_ms": 1000 * sorted(latencies)[int(len(latencies) * 0.95)],
    }


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

    return len(valid) / len(samples)


def compute_jitter(
    samples: list[dict[str, float]],
) -> dict[str, dict[str, float]]:
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
        xs = [g["tracker_x"] for g in group]
        ys = [g["tracker_y"] for g in group]
        jitter[key] = {
            "std_x": statistics.pstdev(xs),
            "std_y": statistics.pstdev(ys),
        }

    jitter_json = {f"{k[0]}_{k[1]}": v for k, v in jitter.items()}
    return jitter_json
