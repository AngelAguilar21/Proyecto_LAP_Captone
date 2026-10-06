import argparse
from collections import defaultdict
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


def rank_invalid_points(dataset_path: Path) -> None:
    """
    Genera un ranking de imágenes de UCF-QNRF
    según la cantidad de anotaciones fuera de rango (OOB).

    Este análisis se realiza sobre el dataset RAW
    y no aplica la cuarentena.
    """

    invalid_per_image = defaultdict(int)

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        if not split_path.exists():
            raise FileNotFoundError(
                f"No se encontró el split: {split_path}"
            )

        for image_path in sorted(
            split_path.glob("*.jpg")
        ):
            annotation_path = (
                split_path
                / f"{image_path.stem}_ann.mat"
            )

            if not annotation_path.exists():
                raise FileNotFoundError(
                    f"No se encontró la anotación: "
                    f"{annotation_path}"
                )

            # Obtener dimensiones reales de la imagen
            with Image.open(image_path) as image:
                width, height = image.size

            # Cargar anotaciones
            data = loadmat(annotation_path)

            if "annPoints" not in data:
                raise KeyError(
                    f"'annPoints' no existe en: "
                    f"{annotation_path}"
                )

            points = data["annPoints"]

            invalid_count = 0

            for x, y in points:
                is_oob = (
                    x < 0
                    or x >= width
                    or y < 0
                    or y >= height
                )

                if is_oob:
                    invalid_count += 1

            if invalid_count > 0:
                sample_id = (
                    f"{split}/{image_path.name}"
                )

                invalid_per_image[
                    sample_id
                ] = invalid_count

    # Ordenar de mayor a menor cantidad
    # de puntos fuera de rango
    ranking = sorted(
        invalid_per_image.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    print(
        "\n--- TOP 20 IMÁGENES CON MÁS "
        "PUNTOS FUERA DE RANGO ---\n"
    )

    for position, (
        image_name,
        count,
    ) in enumerate(
        ranking[:20],
        start=1,
    ):
        print(
            f"{position:02d}. "
            f"{image_name:<30} "
            f"{count:>5} puntos"
        )

    print("\n--- RESUMEN ---")

    print(
        "Imágenes afectadas:",
        len(ranking),
    )

    print(
        "Total de puntos fuera de rango:",
        sum(
            invalid_per_image.values()
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un ranking de imágenes de "
            "UCF-QNRF según la cantidad de "
            "anotaciones Out-of-Bounds."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Ruta al dataset RAW UCF-QNRF.",
    )

    args = parser.parse_args()

    rank_invalid_points(
        dataset_path=args.dataset
    )


if __name__ == "__main__":
    main()