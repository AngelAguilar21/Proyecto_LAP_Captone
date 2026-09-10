import argparse
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


def inspect_ucf_qnrf(dataset_path: Path) -> None:
    """
    Analiza la severidad de las anotaciones fuera de rango
    (Out-of-Bounds / OOB) del dataset RAW UCF-QNRF.
    """

    total_invalid = 0

    # Severidad de los puntos OOB
    small = 0       # <= 5 px
    medium = 0      # > 5 y <= 50 px
    large = 0       # > 50 px

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        for image_path in sorted(
            split_path.glob("*.jpg")
        ):
            annotation_path = (
                split_path
                / f"{image_path.stem}_ann.mat"
            )

            # Obtener dimensiones reales de la imagen
            with Image.open(image_path) as image:
                width, height = image.size

            # Cargar anotaciones
            points = loadmat(
                annotation_path
            )["annPoints"]

            for x, y in points:

                # Determinar primero si el punto
                # está fuera de los límites
                is_oob = (
                    x < 0
                    or x >= width
                    or y < 0
                    or y >= height
                )

                if not is_oob:
                    continue

                # Calcular qué tan lejos está
                # del límite correspondiente
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

                distance = max(dx, dy)

                total_invalid += 1

                if distance <= 5:
                    small += 1

                elif distance <= 50:
                    medium += 1

                else:
                    large += 1

    print(
        "\n--- SEVERIDAD DE PUNTOS FUERA DE RANGO ---"
    )

    print(
        "Total:",
        total_invalid,
    )

    print(
        "<= 5 px:",
        small,
    )

    print(
        "> 5 y <= 50 px:",
        medium,
    )

    print(
        "> 50 px:",
        large,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analiza la severidad de las anotaciones "
            "Out-of-Bounds del dataset RAW UCF-QNRF."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Ruta al dataset RAW UCF-QNRF.",
    )

    args = parser.parse_args()

    inspect_ucf_qnrf(
        dataset_path=args.dataset
    )


if __name__ == "__main__":
    main()