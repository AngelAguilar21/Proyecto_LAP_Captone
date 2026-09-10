import argparse
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


def audit_processed(raw_path, processed_path):
    total_files = 0
    total_points = 0
    oob_points = 0
    images_with_errors = 0

    for split in ["Train", "Test"]:

        raw_split = raw_path / split

        processed_annotations = (
            processed_path /
            split /
            "annotations"
        )

        for annotation_path in sorted(
            processed_annotations.glob("*_ann.mat")
        ):
            total_files += 1

            image_name = annotation_path.name.replace(
                "_ann.mat",
                ".jpg"
            )

            image_path = raw_split / image_name

            with Image.open(image_path) as image:
                width, height = image.size

            points = loadmat(
                annotation_path
            )["annPoints"]

            total_points += len(points)

            invalid = (
                (points[:, 0] < 0)
                | (points[:, 0] >= width)
                | (points[:, 1] < 0)
                | (points[:, 1] >= height)
            )

            invalid_count = invalid.sum()

            if invalid_count > 0:
                images_with_errors += 1
                oob_points += invalid_count

                print(
                    f"{split}/{image_name}: "
                    f"{invalid_count} puntos inválidos"
                )

    print("\n--- PROCESSED DATA QUALITY REPORT ---")
    print("Annotation files:", total_files)
    print("Total points:", total_points)
    print(
        "Images with out-of-bounds points:",
        images_with_errors
    )
    print(
        "Out-of-bounds points:",
        oob_points
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--raw",
        required=True
    )

    parser.add_argument(
        "--processed",
        required=True
    )

    args = parser.parse_args()

    audit_processed(
        Path(args.raw),
        Path(args.processed)
    )


if __name__ == "__main__":
    main()