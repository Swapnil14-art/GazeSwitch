import csv
import math


def compute_euclidean_error(csv_file: str):
    """
    Computes the mean Euclidean error from the evaluation CSV file.

    Args:
        csv_file (str): The path to the CSV file.
    """
    errors = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gx, gy = float(row["gt_x"]), float(row["gt_y"])
            tx, ty = float(row["tracker_x"]), float(row["tracker_y"])
            errors.append(math.sqrt((tx - gx) ** 2 + (ty - gy) ** 2))
    if errors:
        mean_error = sum(errors) / len(errors)
        return mean_error
    else:
        return None


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


def compute_zone_accuracy(csv_file: str, screen_size: tuple, rows: int, cols: int):
    """
    Computes the zone accuracy from the evaluation CSV file.

    Args:
        csv_file (str): The path to the CSV file.
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
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gx, gy = float(row["gt_x"]), float(row["gt_y"])
            tx, ty = float(row["tracker_x"]), float(row["tracker_y"])
            gt_zone = get_zone(gx, gy, zones)
            tracker_zone = get_zone(tx, ty, zones)
            if tracker_zone is not None and tracker_zone == gt_zone:
                correct += 1
            total += 1
    if total > 0:
        accuracy = correct / total * 100
        return accuracy
    else:
        return None
