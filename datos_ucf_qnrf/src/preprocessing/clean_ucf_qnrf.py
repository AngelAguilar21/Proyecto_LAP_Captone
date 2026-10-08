import argparse
import csv
from pathlib import Path

from PIL import Image
from scipy.io import loadmat, savemat


def load_quarantine(path):
    quarantine = set()

    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            sample_id = f"{row['split']}/{row['image']}"
            quarantine.add(sample_id)

    return quarantine


def clean_dataset(dataset_path, output_path, quarantine):
    manifest = []

    total_original_points = 0
    total_removed_points = 0
    total_clean_points = 0
    total_quarantined = 0

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        output_annotations = (
            output_path /
            split /
            "annotations"
        )

        output_annotations.mkdir(
            parents=True,
            exist_ok=True
        )

        for image_path in sorted(split_path.glob("*.jpg")):

            sample_id = f"{split}/{image_path.name}"

            annotation_path = (
                split_path /
                f"{image_path.stem}_ann.mat"
            )

            # -------------------------
            # Cuarentena
            # -------------------------

            if sample_id in quarantine:
                total_quarantined += 1

                manifest.append({
                    "split": split,
                    "image": image_path.name,
                    "original_points": "",
                    "removed_points": "",
                    "clean_points": "",
                    "status": "quarantined",
                })

                continue

            # -------------------------
            # Leer dimensiones
            # -------------------------

            with Image.open(image_path) as image:
                width, height = image.size

            # -------------------------
            # Leer anotaciones
            # -------------------------

            data = loadmat(annotation_path)
            points = data["annPoints"]

            original_count = len(points)

            # -------------------------
            # Filtrar puntos inválidos
            # -------------------------

            valid_mask = (
                (points[:, 0] >= 0)
                & (points[:, 0] < width)
                & (points[:, 1] >= 0)
                & (points[:, 1] < height)
            )

            clean_points = points[valid_mask]

            clean_count = len(clean_points)
            removed_count = original_count - clean_count

            # -------------------------
            # Guardar nueva anotación
            # -------------------------

            clean_annotation_path = (
                output_annotations /
                f"{image_path.stem}_ann.mat"
            )

            savemat(
                clean_annotation_path,
                {
                    "annPoints": clean_points
                }
            )

            # -------------------------
            # Estadísticas
            # -------------------------

            total_original_points += original_count
            total_removed_points += removed_count
            total_clean_points += clean_count

            status = (
                "cleaned"
                if removed_count > 0
                else "valid"
            )

            manifest.append({
                "split": split,
                "image": image_path.name,
                "original_points": original_count,
                "removed_points": removed_count,
                "clean_points": clean_count,
                "status": status,
            })

    # -------------------------
    # Guardar manifest
    # -------------------------

    manifest_path = output_path / "manifest.csv"

    with open(
        manifest_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "split",
                "image",
                "original_points",
                "removed_points",
                "clean_points",
                "status",
            ]
        )

        writer.writeheader()
        writer.writerows(manifest)

    # -------------------------
    # Resumen
    # -------------------------

    print("\n--- PREPROCESSING REPORT ---")
    print("Muestras en cuarentena:", total_quarantined)
    print("Puntos originales procesados:", total_original_points)
    print("Puntos eliminados:", total_removed_points)
    print("Puntos finales:", total_clean_points)

    print("\nManifest:")
    print(manifest_path)


def main():
    parser = argparse.ArgumentParser(
        description="Clean UCF-QNRF annotations"
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to RAW UCF-QNRF"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path for processed annotations"
    )

    parser.add_argument(
        "--quarantine",
        required=True,
        help="CSV containing quarantined samples"
    )

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    quarantine_path = Path(args.quarantine)

    quarantine = load_quarantine(
        quarantine_path
    )

    clean_dataset(
        dataset_path,
        output_path,
        quarantine
    )


if __name__ == "__main__":
    main()