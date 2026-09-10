import argparse
import csv
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


# Raíz del repositorio:
# Proyecto_LAP_Captone/
REPO_ROOT = Path(__file__).resolve().parents[2]

# Archivo de cuarentena por defecto
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


def validate_after_quarantine(
    dataset_path: Path,
    quarantine_path: Path,
) -> None:
    """
    Valida los puntos fuera de rango de UCF-QNRF
    después de excluir las muestras en cuarentena.
    """

    quarantine = load_quarantine(
        quarantine_path
    )

    invalid_points = 0
    images_with_errors = 0
    excluded_images = 0

    # Severidad de los puntos OOB
    small = 0       # <= 5 px
    medium = 0      # > 5 y <= 50 px
    large = 0       # > 50 px

    for split in ["Train", "Test"]:
        split_path = dataset_path / split

        for image_path in sorted(
            split_path.glob("*.jpg")
        ):

            # Saltar muestras en cuarentena
            if (
                split,
                image_path.name,
            ) in quarantine:
                excluded_images += 1
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

            # Cargar puntos de anotación
            points = loadmat(
                annotation_path
            )["annPoints"]

            bad_in_image = 0

            for x, y in points:

                # Primero determinamos si
                # el punto está fuera de rango
                is_oob = (
                    x < 0
                    or x >= width
                    or y < 0
                    or y >= height
                )

                if not is_oob:
                    continue

                # Distancia respecto al
                # límite correspondiente
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

                invalid_points += 1
                bad_in_image += 1

                if distance <= 5:
                    small += 1

                elif distance <= 50:
                    medium += 1

                else:
                    large += 1

            if bad_in_image > 0:
                images_with_errors += 1

    print(
        "\n--- QA DESPUÉS DE CUARENTENA ---"
    )

    print(
        "Imágenes excluidas:",
        excluded_images,
    )

    print(
        "Imágenes restantes con errores:",
        images_with_errors,
    )

    print(
        "\nPuntos fuera de rango:",
        invalid_points,
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
            "Valida las anotaciones OOB "
            "de UCF-QNRF después de aplicar "
            "las muestras en cuarentena."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help=(
            "Ruta al dataset RAW "
            "UCF-QNRF."
        ),
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

    validate_after_quarantine(
        dataset_path=args.dataset,
        quarantine_path=args.quarantine,
    )


if __name__ == "__main__":
    main()