import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.io import loadmat


def inspect_outlier(
    dataset_path: Path,
    split: str,
    image_id: str,
    margin: int,
) -> None:
    """
    Inspecciona visualmente una muestra específica de UCF-QNRF.

    Separa las anotaciones en:
    - puntos válidos;
    - puntos fuera de rango (OOB).

    También muestra las coordenadas OOB y genera
    una visualización ampliada alrededor de la imagen.
    """

    split_path = dataset_path / split

    image_path = (
        split_path / f"{image_id}.jpg"
    )

    annotation_path = (
        split_path / f"{image_id}_ann.mat"
    )

    if not image_path.exists():
        raise FileNotFoundError(
            f"No se encontró la imagen: "
            f"{image_path}"
        )

    if not annotation_path.exists():
        raise FileNotFoundError(
            f"No se encontró la anotación: "
            f"{annotation_path}"
        )

    # 1. Cargar imagen
    with Image.open(image_path) as image:
        width, height = image.size
        image_np = np.array(image)

    # 2. Cargar anotaciones
    data = loadmat(annotation_path)

    if "annPoints" not in data:
        raise KeyError(
            f"'annPoints' no existe en: "
            f"{annotation_path}"
        )

    points = data["annPoints"]

    # 3. Separar puntos válidos e inválidos
    valid_mask = (
        (points[:, 0] >= 0)
        & (points[:, 0] < width)
        & (points[:, 1] >= 0)
        & (points[:, 1] < height)
    )

    valid_points = points[valid_mask]
    invalid_points = points[~valid_mask]

    # 4. Mostrar información
    print(
        f"\n--- {split}/{image_id} ---"
    )

    print(
        f"Resolución: {width} x {height}"
    )

    print(
        f"Anotaciones totales: {len(points)}"
    )

    print(
        f"Puntos válidos: {len(valid_points)}"
    )

    print(
        f"Puntos fuera de rango: "
        f"{len(invalid_points)}"
    )

    print("\nPuntos fuera de rango:")

    if len(invalid_points) == 0:
        print("Ninguno")
    else:
        for point in invalid_points:
            print(point)

    # 5. Visualizar
    plt.figure(
        figsize=(14, 10)
    )

    plt.imshow(image_np)

    if len(valid_points) > 0:
        plt.scatter(
            valid_points[:, 0],
            valid_points[:, 1],
            s=10,
            label="Dentro de rango",
        )

    if len(invalid_points) > 0:
        plt.scatter(
            invalid_points[:, 0],
            invalid_points[:, 1],
            s=40,
            marker="x",
            label="Fuera de rango",
        )

    # Extender la vista para poder observar
    # anotaciones ubicadas fuera de la imagen.
    plt.xlim(
        -margin,
        width + margin,
    )

    plt.ylim(
        height + margin,
        -margin,
    )

    plt.title(
        f"UCF-QNRF - {split}/{image_id} "
        "- revisión de anotaciones"
    )

    plt.legend()

    plt.show()
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspecciona visualmente una muestra "
            "de UCF-QNRF y sus anotaciones OOB."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Ruta al dataset RAW UCF-QNRF.",
    )

    parser.add_argument(
        "--split",
        default="Train",
        choices=["Train", "Test"],
        help=(
            "Split de la muestra. "
            "Default: Train."
        ),
    )

    parser.add_argument(
        "--image",
        default="img_0017",
        help=(
            "ID de la imagen sin extensión. "
            "Default: img_0017."
        ),
    )

    parser.add_argument(
        "--margin",
        type=int,
        default=700,
        help=(
            "Margen adicional de visualización "
            "en píxeles. Default: 700."
        ),
    )

    args = parser.parse_args()

    inspect_outlier(
        dataset_path=args.dataset,
        split=args.split,
        image_id=args.image,
        margin=args.margin,
    )


if __name__ == "__main__":
    main()