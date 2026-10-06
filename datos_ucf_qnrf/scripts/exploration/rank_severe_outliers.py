import argparse
import csv
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUARANTINE = (
    REPO_ROOT / "configs" / "ucf_qnrf_quarantine.csv"
)


def load_quarantine(
    quarantine_path: Path,
) -> set[tuple[str, str]]:
    """
    Carga las muestras en cuarentena desde el CSV.

    Retorna pares:
    (split, image)

    Ejemplo:
    ("Train", "img_1070.jpg")
    """

    quarantined = set()

    with quarantine_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            quarantined.add(
                (
                    row["split"],
                    row["image"],
                )
            )

    return quarantined


def rank_severe_outliers(
    dataset_path: Path,
    quarantine_path: Path,
) -> None:
    """
    Genera un ranking de imágenes según la cantidad
    de anotaciones OOB severas (> 50 px),
    excluyendo las muestras en cuarentena.
    """

    quarantine = load_quarantine(
        quarantine_path
    )

    ranking = []

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        for image_path in sorted(
            split_path.glob("*.jpg")
        ):

            # Excluir muestras en cuarentena
            if (
                split,
                image_path.name,
            ) in quarantine:
                continue

            annotation_path = (
                split_path
                / f"{image_path.stem}_ann.mat"
            )

            # Obtener dimensiones reales
            # de la imagen
            with Image.open(
                image_path
            ) as image:
                width, height = image.size

            # Cargar anotaciones
            points = loadmat(
                annotation_path
            )["annPoints"]

            severe_count = 0

            for x, y in points:

                # Determinar si el punto está
                # fuera de los límites
                is_oob = (
                    x < 0
                    or x >= width
                    or y < 0
                    or y >= height
                )

                if not is_oob:
                    continue

                # Calcular distancia respecto
                # al límite de la imagen
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

                # Solo contar errores severos
                if distance > 50:
                    severe_count += 1

            if severe_count > 0:
                ranking.append(
                    (
                        f"{split}/{image_path.name}",
                        severe_count,
                    )
                )

    # Ordenar de mayor a menor número
    # de puntos severos
    ranking.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print(
        "\n--- ERRORES SEVEROS > 50 PX ---\n"
    )

    for position, (
        sample_id,
        count,
    ) in enumerate(
        ranking,
        start=1,
    ):
        print(
            f"{position:02d}. "
            f"{sample_id:<30} "
            f"{count:>4} puntos"
        )

    print("\n--- RESUMEN ---")

    print(
        "Imágenes con errores severos:",
        len(ranking),
    )

    print(
        "Total puntos > 50 px:",
        sum(
            count
            for _, count in ranking
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un ranking de imágenes de "
            "UCF-QNRF según la cantidad de "
            "anotaciones OOB severas (> 50 px)."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Ruta al dataset RAW UCF-QNRF.",
    )

    parser.add_argument(
        "--quarantine",
        type=Path,
        default=DEFAULT_QUARANTINE,
        help=(
            "CSV que contiene las muestras "
            "en cuarentena."
        ),
    )

    args = parser.parse_args()

    rank_severe_outliers(
        dataset_path=args.dataset,
        quarantine_path=args.quarantine,
    )


if __name__ == "__main__":
    main()