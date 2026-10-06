import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.io import loadmat


DEFAULT_IMAGES = [
    "img_1074",
    "img_0884",
]


def inspect_top_outliers(
    dataset_path: Path,
    split: str,
    image_ids: list[str],
) -> None:
    """
    Inspecciona visualmente muestras específicas de UCF-QNRF.

    Para cada imagen:
    - carga sus anotaciones;
    - separa puntos válidos y OOB;
    - muestra estadísticas;
    - visualiza ambos tipos de puntos.
    """

    split_path = dataset_path / split

    for image_id in image_ids:
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

        # Abrir imagen y copiarla a memoria
        with Image.open(image_path) as image:
            width, height = image.size
            image_np = np.array(image)

        # Cargar anotaciones
        points = loadmat(
            annotation_path
        )["annPoints"]

        # Máscara de puntos espacialmente válidos
        valid_mask = (
            (points[:, 0] >= 0)
            & (points[:, 0] < width)
            & (points[:, 1] >= 0)
            & (points[:, 1] < height)
        )

        valid_points = points[valid_mask]
        invalid_points = points[~valid_mask]

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
            f"Válidas: {len(valid_points)}"
        )

        print(
            f"Fuera de rango: "
            f"{len(invalid_points)}"
        )

        print(
            "X anotaciones: "
            f"{points[:, 0].min():.2f} "
            f"→ {points[:, 0].max():.2f}"
        )

        print(
            "Y anotaciones: "
            f"{points[:, 1].min():.2f} "
            f"→ {points[:, 1].max():.2f}"
        )

        # Visualización
        plt.figure(
            figsize=(14, 9)
        )

        plt.imshow(image_np)

        if len(valid_points) > 0:
            plt.scatter(
                valid_points[:, 0],
                valid_points[:, 1],
                s=5,
                label="Válidos",
            )

        if len(invalid_points) > 0:
            plt.scatter(
                invalid_points[:, 0],
                invalid_points[:, 1],
                s=10,
                marker="x",
                label="Fuera de rango",
            )

        # Ampliar los límites de la gráfica
        # para poder visualizar puntos OOB.
        x_min = min(
            -50,
            points[:, 0].min() - 50,
        )

        x_max = max(
            width + 50,
            points[:, 0].max() + 50,
        )

        y_min = min(
            -50,
            points[:, 1].min() - 50,
        )

        y_max = max(
            height + 50,
            points[:, 1].max() + 50,
        )

        plt.xlim(
            x_min,
            x_max,
        )

        # Se invierte Y porque las coordenadas
        # de imagen comienzan arriba a la izquierda.
        plt.ylim(
            y_max,
            y_min,
        )

        plt.title(
            f"UCF-QNRF - {split}/{image_id}"
        )

        plt.legend()

        plt.show()
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspecciona visualmente muestras "
            "con anotaciones OOB de UCF-QNRF."
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
            "Split que contiene las imágenes. "
            "Default: Train."
        ),
    )

    parser.add_argument(
        "--images",
        nargs="+",
        default=DEFAULT_IMAGES,
        help=(
            "IDs de imágenes a inspeccionar, "
            "sin extensión."
        ),
    )

    args = parser.parse_args()

    inspect_top_outliers(
        dataset_path=args.dataset,
        split=args.split,
        image_ids=args.images,
    )


if __name__ == "__main__":
    main()