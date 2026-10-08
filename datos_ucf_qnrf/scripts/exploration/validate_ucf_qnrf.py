import argparse
from pathlib import Path

from scipy.io import loadmat


def validate_ucf_qnrf(dataset_path: Path) -> None:
    """
    Cuenta las anotaciones de UCF-QNRF
    por split y en total.
    """

    total_points = 0

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        if not split_path.exists():
            raise FileNotFoundError(
                f"No se encontró el split: {split_path}"
            )

        split_total = 0

        annotation_paths = sorted(
            split_path.glob("*_ann.mat")
        )

        for annotation_path in annotation_paths:
            mat_data = loadmat(annotation_path)

            if "annPoints" not in mat_data:
                raise KeyError(
                    f"'annPoints' no existe en: "
                    f"{annotation_path}"
                )

            points = mat_data["annPoints"]

            split_total += len(points)
            total_points += len(points)

        print(
            f"{split}: "
            f"{split_total:,} anotaciones"
        )

    print(
        "\nTotal:",
        f"{total_points:,}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cuenta las anotaciones de "
            "UCF-QNRF por split y en total."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Ruta al dataset RAW UCF-QNRF.",
    )

    args = parser.parse_args()

    validate_ucf_qnrf(
        dataset_path=args.dataset
    )


if __name__ == "__main__":
    main()