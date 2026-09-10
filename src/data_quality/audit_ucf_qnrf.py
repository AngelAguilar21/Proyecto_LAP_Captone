import argparse
import csv
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from scipy.io import loadmat


def load_quarantine(path):
    quarantine = set()

    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            sample_id = f"{row['split']}/{row['image']}"
            quarantine.add(sample_id)

    return quarantine


def calculate_out_of_bounds_distance(x, y, width, height):
    dx = 0
    dy = 0

    if x < 0:
        dx = abs(x)
    elif x >= width:
        dx = x - width

    if y < 0:
        dy = abs(y)
    elif y >= height:
        dy = y - height

    return max(dx, dy)


def audit_dataset(dataset_path, quarantine):
    summary = {
        "images": 0,
        "annotations_files": 0,
        "total_points": 0,
        "quarantined_images": 0,
        "corrupted_images": 0,
        "missing_annotations": 0,
        "invalid_annotation_format": 0,
        "images_with_oob_points": 0,
        "oob_points": 0,
        "oob_le_5px": 0,
        "oob_5_to_50px": 0,
        "oob_gt_50px": 0,
    }

    issues = []

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        for image_path in sorted(split_path.glob("*.jpg")):
            summary["images"] += 1

            sample_id = f"{split}/{image_path.name}"

            annotation_path = (
                split_path /
                f"{image_path.stem}_ann.mat"
            )

            # -------------------------
            # Quarantine
            # -------------------------

            if sample_id in quarantine:
                summary["quarantined_images"] += 1

                issues.append({
                    "sample": sample_id,
                    "issue": "quarantined",
                    "count": 1,
                })

                continue

            # -------------------------
            # Image validation
            # -------------------------

            try:
                with Image.open(image_path) as image:
                    image.verify()

                with Image.open(image_path) as image:
                    width, height = image.size

            except (
                UnidentifiedImageError,
                OSError
            ):
                summary["corrupted_images"] += 1

                issues.append({
                    "sample": sample_id,
                    "issue": "corrupted_image",
                    "count": 1,
                })

                continue

            # -------------------------
            # Annotation existence
            # -------------------------

            if not annotation_path.exists():
                summary["missing_annotations"] += 1

                issues.append({
                    "sample": sample_id,
                    "issue": "missing_annotation",
                    "count": 1,
                })

                continue

            summary["annotations_files"] += 1

            # -------------------------
            # Annotation validation
            # -------------------------

            try:
                annotation_data = loadmat(annotation_path)

                if "annPoints" not in annotation_data:
                    raise ValueError(
                        "annPoints not found"
                    )

                points = annotation_data["annPoints"]

                if (
                    len(points.shape) != 2
                    or points.shape[1] != 2
                ):
                    raise ValueError(
                        "annPoints must have shape Nx2"
                    )

            except Exception:
                summary["invalid_annotation_format"] += 1

                issues.append({
                    "sample": sample_id,
                    "issue": "invalid_annotation_format",
                    "count": 1,
                })

                continue

            summary["total_points"] += len(points)

            # -------------------------
            # Bounds validation
            # -------------------------

            oob_count = 0

            for x, y in points:
                distance = calculate_out_of_bounds_distance(
                    x,
                    y,
                    width,
                    height
                )

                if distance <= 0:
                    continue

                oob_count += 1
                summary["oob_points"] += 1

                if distance <= 5:
                    summary["oob_le_5px"] += 1

                elif distance <= 50:
                    summary["oob_5_to_50px"] += 1

                else:
                    summary["oob_gt_50px"] += 1

            if oob_count > 0:
                summary["images_with_oob_points"] += 1

                issues.append({
                    "sample": sample_id,
                    "issue": "out_of_bounds_points",
                    "count": oob_count,
                })

    return summary, issues


def save_reports(summary, issues, report_dir):
    report_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    summary_path = (
        report_dir /
        "ucf_qnrf_summary.json"
    )

    issues_path = (
        report_dir /
        "ucf_qnrf_issues.csv"
    )

    with open(
        summary_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            summary,
            file,
            indent=4
        )

    with open(
        issues_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "sample",
                "issue",
                "count"
            ]
        )

        writer.writeheader()
        writer.writerows(issues)

    print("\n--- DATA QUALITY REPORT ---")

    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\nReportes generados:")
    print(summary_path)
    print(issues_path)


def main():
    parser = argparse.ArgumentParser(
        description="Audit UCF-QNRF dataset"
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to UCF-QNRF_ECCV18"
    )

    parser.add_argument(
        "--quarantine",
        required=True,
        help="CSV with quarantined samples"
    )

    parser.add_argument(
        "--report-dir",
        default="reports/data_quality",
        help="Output directory"
    )

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    quarantine_path = Path(args.quarantine)
    report_dir = Path(args.report_dir)

    quarantine = load_quarantine(
        quarantine_path
    )

    summary, issues = audit_dataset(
        dataset_path,
        quarantine
    )

    save_reports(
        summary,
        issues,
        report_dir
    )


if __name__ == "__main__":
    main()