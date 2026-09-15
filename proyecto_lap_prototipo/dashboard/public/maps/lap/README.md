# Cartografía local LAP

Fuente: https://map.lima-airport.com/ (Living Map / Lima Airport Partners).

Los archivos `1.json` a `4.json` contienen geometría vectorial publicada por el visor oficial, extraída de su capa `indoor`, no una imagen dibujada ni una geometría levantada por el equipo. Conservan atribución. El nivel 3 es el principal de la interfaz.

Configuración pública consultada: `https://map-api.prod.livingmap.com/v1/maps?host=map.lima-airport.com`.
Estilo público: `https://map-api.prod.livingmap.com/v1/maps/lima_airport_two/styles/styles.json`.
Teselas: `https://prod.cdn.livingmap.com/tiles/lima_airport_two/{z}/{x}/{y}.pbf?lang=es-PE`.

El importador `tools/import_lap_map.py` une las geometrías fragmentadas entre teselas y conserva categorías, nombres y nivel. No requiere guardar tokens de Mapbox ni claves privadas. Cada archivo incluye fecha de captura, fuente y transformación de coordenadas. La escala es Web Mercator local corregida a la latitud del aeropuerto; no certifica precisión topográfica. Las coordenadas de los cuatro niveles usan el mismo origen.

La disponibilidad pública no concede por sí sola licencia de redistribución comercial. Esta copia sirve como referencia local del prototipo académico. Para distribución del producto o despliegue en LAP, obtener de LAP/Living Map autorización de uso y planos vigentes; no presentar estos vectores como propiedad del equipo. La copia no se actualiza automáticamente con cambios del aeropuerto.

Dependencias de regeneración (no necesarias para ejecutar el dashboard): `pip install -r requirements-cartography.txt` desde la raíz del prototipo, y `python tools/import_lap_map.py`.
