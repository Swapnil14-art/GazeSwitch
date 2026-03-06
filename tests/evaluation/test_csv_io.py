import csv

from evaluation.run_evaluation import load_samples


def test_csv_io(tmp_path):
    samples = [
        {
            "gt_x": 0.0,
            "gt_y": 0.0,
            "tracker_x": 1.0,
            "tracker_y": 2.0,
            "timestamp": 0.0,
            "latency": 0.01,
        },
        {
            "gt_x": 1.0,
            "gt_y": 1.0,
            "tracker_x": 2.0,
            "tracker_y": 3.0,
            "timestamp": 0.1,
            "latency": 0.02,
        },
    ]

    csv_file = tmp_path / "test.csv"

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=samples[0].keys())
        writer.writeheader()
        writer.writerows(samples)

    loaded = load_samples(csv_file)

    assert len(loaded) == len(samples)

    for s_orig, s_loaded in zip(samples, loaded):
        for key in s_orig:
            assert s_orig[key] == s_loaded[key]
