import argparse
import csv
import json
import os
import time
import tkinter as tk
from datetime import datetime

from evaluation.metrics import (
    compute_accuracy,
    compute_confusion_matrix,
    compute_euclidean_error,
    compute_jitter,
    compute_latency,
    compute_rms_s2s,
    compute_validity,
    compute_zone_accuracy,
)
from trackers.base_tracker import BaseTracker
from trackers.eyetrax_tracker import EyeTraxWrapper
from trackers.gaze_follower_tracker import GazeFollowerWrapper

LOGS_DIR = os.path.join(os.path.dirname(__file__), "data", "logs")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "data", "results")
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# GLOBAL canvas for showing dots
EVAL_UI_ROOT = None
EVAL_UI_CANVAS = None


def init_eval_ui(screen_size: tuple[int, int]):
    """
    Initialises a fullscreen black window for evaluation.
    """
    global EVAL_UI_ROOT, EVAL_UI_CANVAS
    screen_w, screen_h = screen_size
    EVAL_UI_ROOT = tk.Tk()
    EVAL_UI_ROOT.attributes("-fullscreen", True)
    EVAL_UI_ROOT.configure(background="black")
    EVAL_UI_CANVAS = tk.Canvas(
        EVAL_UI_ROOT, width=screen_w, height=screen_h, bg="black"
    )
    EVAL_UI_CANVAS.pack(fill="both", expand=True)
    EVAL_UI_ROOT.update()


def show_point(duration: float, x: int, y: int, radius: int = 20):
    """
    Shows a point on the existing fullscreen UI for a short duration.

    Args:
        duration (float): The duration to show the point.
        x (int): The x-coordinate of the point.
        y (int): The y-coordinate of the point.
        radius (int, optional): The radius of the point. Defaults to 20.
    """
    global EVAL_UI_CANVAS
    if not EVAL_UI_CANVAS:
        raise RuntimeError("UI not initialised. Call init_eval_ui first.")

    circle_id = EVAL_UI_CANVAS.create_oval(
        x - radius, y - radius, x + radius, y + radius, fill="white", outline="white"
    )
    EVAL_UI_CANVAS.update()

    EVAL_UI_CANVAS.after(int(duration), lambda: EVAL_UI_CANVAS.delete(circle_id))  # type: ignore


def generate_grid(
    screen_w: int, screen_h: int, rows: int, cols: int
) -> list[tuple[int, int]]:
    """
    Generates a grid of points for evaluation.

    Args:
        screen_w (int): The width of the screen.
        screen_h (int): The height of the screen.
        rows (int): The number of rows in the grid.
        cols (int): The number of columns in the grid.

    Returns:
        list[tuple[int, int]]: A list of (x, y) coordinates for the grid points.
    """
    xs = [int((i + 0.5) * screen_w / cols) for i in range(cols)]
    ys = [int((i + 0.5) * screen_h / rows) for i in range(rows)]
    pts = [(x, y) for y in ys for x in xs]
    return pts


def save_results(outfile: str, metrics: dict[str, float | None], args, timestamp: str):
    """
    Saves the evaluation results to a JSON file.

    Args:
        outfile (str): The path to the CSV output file.
        metrics (dict[str, float | None]): A dictionary of metric names and their values.
        args: The command-line arguments used for the evaluation.
        timestamp (str): The timestamp string for the filename.
    """
    metrics_path = os.path.join(RESULTS_DIR, f"metrics_{str(tracker)}_{timestamp}.json")
    results = {
        "timestamp": datetime.now().isoformat(),
        "log_file": os.path.basename(outfile),
        "args": vars(args),
        "metrics": metrics,
    }

    with open(metrics_path, "w") as f:
        json.dump(results, f, indent=4)

    print(f"Metrics saved to {metrics_path}")


def load_samples(csv_file: str) -> list[dict[str, float | None]]:
    """
    Loads the gaze samples from the evaluation CSV file.

    Args:
        csv_file (str): The path to the CSV file.
    Returns:
        list[dict[str, float | None]]: A list of samples with ground truth and tracker coordinates.
    """
    samples = []

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(
                {
                    "gt_x": float(row["gt_x"]),
                    "gt_y": float(row["gt_y"]),
                    "tracker_x": float(row["tracker_x"]) if row["tracker_x"] else None,
                    "tracker_y": float(row["tracker_y"]) if row["tracker_y"] else None,
                    "timestamp": float(row["timestamp"]),
                    "latency": float(row["latency"]),
                }
            )

    return samples


def run_evaluation(
    tracker: BaseTracker,
    screen_size: tuple[int, int],
    fixation_delay: float,
    hold_seconds: float,
    sampling_rate: float,
    grid_rows: int,
    grid_cols: int,
    args,
):
    """
    Runs the specified evaluation on the given tracker.

    Args:
        tracker (BaseTracker): The gaze tracker to evaluate.
        screen_size (tuple): The size of the screen.
        fixation_delay (float): The delay before sampling after showing each point.
        hold_seconds (float): The duration to hold each point.
        sampling_rate (float): The rate at which to sample gaze data.
        grid_rows (int): The number of rows in the grid.
        grid_cols (int): The number of columns in the grid.
        args: The command-line arguments.

    Returns:
        str: The path to the output file.
    """
    screen_w, screen_h = screen_size
    pts = generate_grid(screen_w, screen_h, rows=grid_rows, cols=grid_cols)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = os.path.join(LOGS_DIR, f"eval_{str(tracker)}_{timestamp}.csv")

    csv_header = [
        "gt_x",
        "gt_y",
        "tracker_x",
        "tracker_y",
        "timestamp",
        "latency",
    ]
    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)

        for gx, gy in pts:
            # Show fixation point
            show_point(hold_seconds, gx, gy, 20)

            # Short delay before sampling to allow user to fixate
            time.sleep(fixation_delay)

            end_time = time.time() + (hold_seconds - fixation_delay)

            while time.time() < end_time:
                ts_before = time.time()
                data = tracker.get_data()

                if data:
                    gaze = data.get("gaze", None)
                    tx = gaze["x"] if gaze else None
                    ty = gaze["y"] if gaze else None

                    gaze_timestamp = data.get("timestamp", None)
                    latency = gaze_timestamp - ts_before if gaze_timestamp else None

                    writer.writerow([gx, gy, tx, ty, gaze_timestamp, latency])

                time.sleep(1.0 / sampling_rate)

    EVAL_UI_ROOT.destroy()  # type: ignore
    print(f"Evaluation data saved to {outfile}")

    # Compute evaluation metrics
    samples = load_samples(outfile)
    valid_samples: list[dict[str, float]] = [
        s for s in samples if s["tracker_x"] is not None and s["tracker_y"] is not None
    ]  # type: ignore

    accuracy = compute_accuracy(valid_samples)
    rms_s2s = compute_rms_s2s(valid_samples)
    mean_error = compute_euclidean_error(valid_samples)
    zone_accuracy = compute_zone_accuracy(
        valid_samples, screen_size, grid_rows, grid_cols
    )
    confusion_matrix = compute_confusion_matrix(
        valid_samples, screen_size, grid_rows, grid_cols
    )
    latency = compute_latency(valid_samples)
    jitter = compute_jitter(valid_samples)
    validity = compute_validity(samples)

    metrics = {
        "accuracy": accuracy,
        "rms_s2s": rms_s2s,
        "mean_euclidean_error_pixels": mean_error,
        "zone_accuracy_percentage": zone_accuracy,
        "confusion_matrix": confusion_matrix,
        "latency": latency,
        "jitter": jitter,
        "validity": validity,
    }
    save_results(outfile, metrics, args, timestamp)


if __name__ == "__main__":
    # Get the screen dimensions
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tracker", choices=["eyetrax", "gazefollower"], default="eyetrax"
    )
    parser.add_argument("--calibrate", type=bool, default=False)
    parser.add_argument("--calibration-mode", type=str, default="with_glasses")
    parser.add_argument("--screen-w", type=int, default=screen_width)
    parser.add_argument("--screen-h", type=int, default=screen_height)
    parser.add_argument("--fixation-delay", type=float, default=1.0)
    parser.add_argument("--hold-seconds", type=float, default=4.0)
    parser.add_argument("--sampling-rate", type=float, default=17.0)
    parser.add_argument("--grid-rows", type=int, default=3)
    parser.add_argument("--grid-cols", type=int, default=3)
    args = parser.parse_args()

    if args.tracker == "eyetrax":
        tracker = EyeTraxWrapper(
            calibrate=args.calibrate,
            calibration_mode=args.calibration_mode,
            model_dir="models/eyetrax",
        )
    else:
        tracker = GazeFollowerWrapper(
            calibrate=args.calibrate,
            calibration_mode=args.calibration_mode,
            model_dir="models/gazefollower",
        )

    try:
        init_eval_ui((args.screen_w, args.screen_h))
        run_evaluation(
            tracker,
            screen_size=(args.screen_w, args.screen_h),
            fixation_delay=args.fixation_delay,
            hold_seconds=args.hold_seconds,
            sampling_rate=args.sampling_rate,
            grid_rows=args.grid_rows,
            grid_cols=args.grid_cols,
            args=args,
        )
    finally:
        tracker.stop()
