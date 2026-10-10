# syntax=docker/dockerfile:1
#
# AeroTrack en contenedor. Una sola imagen sirve para equipos con y sin GPU: al arrancar,
# proyecto_lap_prototipo/src/hardware.py detecta si hay una GPU NVIDIA visible y elige solo el
# modelo, la resolución y la precisión (con GPU: YOLO11 n/s/m según la VRAM y FP16; sin GPU: YOLO11n en CPU).
#
# Imagen con soporte de GPU (por defecto, también corre en equipos sin GPU):
#   docker build -t aerotrack .
# Imagen más pequeña, solo CPU:
#   docker build -t aerotrack:cpu --build-arg VARIANT=cpu --build-arg BASE_IMAGE=ubuntu:24.04 .
#
# Para dar la GPU al contenedor hace falta el NVIDIA Container Toolkit en el servidor y `--gpus all`
# (ver docker-compose.gpu.yml). Sin ese permiso el contenedor no ve la GPU y trabaja en CPU.

ARG BASE_IMAGE=nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04

# ---------- Interfaz web ----------
FROM node:22-slim AS dashboard
WORKDIR /dashboard
COPY proyecto_lap_prototipo/dashboard/package.json proyecto_lap_prototipo/dashboard/package-lock.json ./
RUN npm ci
COPY proyecto_lap_prototipo/dashboard/ ./
RUN npm run build

# ---------- Aplicación ----------
FROM ${BASE_IMAGE}
ARG VARIANT=gpu
ARG TORCH_VERSION=2.14.0
ARG TORCHVISION_VERSION=0.29.0
ARG CUDA_WHEELS=cu126
ARG ORT_GPU_VERSION=1.20.2
ARG ORT_CPU_VERSION=1.20.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    YOLO_CONFIG_DIR=/app/proyecto_lap_prototipo/data/ultralytics \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,video \
    AEROTRACK_HOST=0.0.0.0 \
    AEROTRACK_PORT=8765

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3.12 python3.12-venv libgl1 libglib2.0-0t64 tini ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && python3.12 -m venv "$VIRTUAL_ENV"

# Dependencias fijadas del proyecto, sin torch ni onnxruntime: esos dos dependen de la variante
# (los archivos requirements-*.txt traen la compilación para CPU de Windows).
COPY requirements.txt /tmp/req/requirements.txt
COPY proyecto_lap_prototipo/requirements-vision.txt proyecto_lap_prototipo/requirements-commercial.txt /tmp/req/proyecto_lap_prototipo/
RUN cat /tmp/req/requirements.txt /tmp/req/proyecto_lap_prototipo/requirements-vision.txt /tmp/req/proyecto_lap_prototipo/requirements-commercial.txt \
    | grep -vE '^(-|#|torch|onnxruntime|[[:space:]]*$)' | sort -u > /tmp/req/comun.txt

RUN if [ "$VARIANT" = "gpu" ]; then \
        pip install "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" --index-url "https://download.pytorch.org/whl/${CUDA_WHEELS}" \
     && pip install "onnxruntime-gpu==${ORT_GPU_VERSION}"; \
    else \
        pip install "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
     && pip install "onnxruntime==${ORT_CPU_VERSION}"; \
    fi \
 && pip install -r /tmp/req/comun.txt \
 && pip check

WORKDIR /app
COPY proyecto_lap_prototipo/ proyecto_lap_prototipo/
COPY --from=dashboard /dashboard/dist proyecto_lap_prototipo/dashboard/dist
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Pesos de YOLO: el perfil automático usa n en CPU y GPU baja, s en GPU media y m en GPU alta. Si falta el
# que corresponde, hardware.py usa el mejor disponible, así que la variante CPU solo descarga el n.
WORKDIR /app/proyecto_lap_prototipo
RUN mkdir -p data/ultralytics \
 && python setup_objects.py --download \
 && if [ "$VARIANT" = "gpu" ]; then \
        python -c "from ultralytics.utils.downloads import attempt_download_asset as d; [d('models/' + w) for w in ('yolo11s.pt', 'yolo11m.pt')]"; \
    fi \
 && rm -rf /tmp/Ultralytics \
 && sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh \
 && useradd --uid 10001 --create-home aerotrack \
 && mkdir -p config data \
 && chown -R aerotrack:aerotrack config data models

USER aerotrack
# config: usuarios, proyectos y correo. data: videos subidos, grabaciones del análisis y memoria de apariencia.
VOLUME ["/app/proyecto_lap_prototipo/config", "/app/proyecto_lap_prototipo/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://127.0.0.1:%s/api/state' % os.environ.get('AEROTRACK_PORT', '8765'), timeout=4)"
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
