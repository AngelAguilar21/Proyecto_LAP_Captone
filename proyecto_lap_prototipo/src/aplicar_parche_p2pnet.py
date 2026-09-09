"""
P2PNet (external/P2PNet) es codigo de 2021 y no corre tal cual con
torch/torchvision modernos. Como es un submodulo git que apunta al repo real
de Tencent, no podemos depender de un commit local dentro de el (no seria
reproducible para otra persona que clone el proyecto) -- este script aplica
los mismos 2 parches minimos de compatibilidad de forma idempotente.

Corre una vez despues de `git submodule update --init`:
    python aplicar_parche_p2pnet.py

Parches:
  1. util/misc.py: el chequeo de version "float(torchvision.__version__[:3])
     < 0.7" corta mal versiones de dos digitos (0.29.0 -> 0.2 -> True) y
     activa por error un import legado que ya no existe en torchvision
     moderno. Se reemplaza por un parseo correcto de major.minor.
  2. models/backbone.py: Backbone_VGG llama a vgg16_bn(pretrained=True), que
     intenta descargar pesos ImageNet desde una ruta interna de Tencent
     (/apdcephfs/...) que no existe fuera de su servidor. No hace falta: el
     checkpoint fine-tuneado que carga detection.py justo despues (via
     load_state_dict) reemplaza todo el peso del backbone de todas formas.
"""
from pathlib import Path

RAIZ_P2PNET = Path(__file__).resolve().parent.parent / "external" / "P2PNet"

PARCHES = [
    {
        "archivo": RAIZ_P2PNET / "util" / "misc.py",
        "buscar": "if float(torchvision.__version__[:3]) < 0.7:",
        "reemplazo": (
            "_tv_major, _tv_minor = (int(x) for x in torchvision.__version__.split(\".\")[:2])\n"
            "if (_tv_major, _tv_minor) < (0, 7):"
        ),
    },
    {
        "archivo": RAIZ_P2PNET / "models" / "backbone.py",
        "buscar": (
            "        if name == 'vgg16_bn':\n"
            "            backbone = models.vgg16_bn(pretrained=True)\n"
            "        elif name == 'vgg16':\n"
            "            backbone = models.vgg16(pretrained=True)"
        ),
        "reemplazo": (
            "        if name == 'vgg16_bn':\n"
            "            backbone = models.vgg16_bn(pretrained=False)\n"
            "        elif name == 'vgg16':\n"
            "            backbone = models.vgg16(pretrained=False)"
        ),
    },
]


def aplicar():
    if not RAIZ_P2PNET.exists():
        raise RuntimeError(
            "No se encontro external/P2PNet. Corre primero:\n"
            "  git submodule update --init proyecto_lap_prototipo/external/P2PNet"
        )

    for parche in PARCHES:
        archivo = parche["archivo"]
        contenido = archivo.read_text(encoding="utf-8")
        if parche["reemplazo"] in contenido:
            print(f"[=] {archivo.relative_to(RAIZ_P2PNET)} ya tiene el parche aplicado.")
            continue
        if parche["buscar"] not in contenido:
            print(f"[!] {archivo.relative_to(RAIZ_P2PNET)}: no se encontro el texto esperado "
                  "(¿cambio el submodulo de version? revisar manualmente).")
            continue
        archivo.write_text(contenido.replace(parche["buscar"], parche["reemplazo"]), encoding="utf-8")
        print(f"[OK] Parche aplicado en {archivo.relative_to(RAIZ_P2PNET)}")


if __name__ == "__main__":
    aplicar()
