# Imagen base ligera con Python 3.11
FROM python:3.11-slim

# Dependencias de sistema que OpenCV necesita para leer/mostrar imágenes y video
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python primero (aprovecha el cache de Docker:
# solo se reinstala si requirements.txt cambia, no cada vez que editas código)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El código real se monta como volumen (ver docker-compose.yml),
# así que no lo copiamos aquí para no tener que reconstruir la imagen
# cada vez que alguien edita un archivo.
CMD ["bash"]
