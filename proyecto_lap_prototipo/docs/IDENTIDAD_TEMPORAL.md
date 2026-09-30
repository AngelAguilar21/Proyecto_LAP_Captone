# Memoria de identidad temporal

Mantiene la asociación de una persona entre cámaras usando posición, ropa y aspecto físico, sin guardar quién es.

## Qué se guarda

Tabla `identity_observations` en `data/identidad/<proyecto>.sqlite`, una fila por persona como máximo cada segundo:

- ID temporal de la sesión (`P00001`...), que se reinicia en cada sesión.
- Cámara, instante y posición en el plano (x, y), estado de asociación y velocidad.
- Firma de color de ropa (histograma comprimido).
- Ancho y alto del recuadro en píxeles y estatura estimada en metros.

No se guardan rostros, imágenes, nombres ni datos biométricos.

## Estatura estimada

Solo con detectores que entregan recuadro (YOLO), calibración por homografía y altura de cámara definida:
`estatura = H * (1 - d_pies / d_cabeza)`. Se descarta si el recuadro toca el borde de la imagen o el resultado
sale de 0,8 a 2,4 m. En la asociación actúa como una penalización suave, nunca como criterio único.

## Retención y borrado

- Por defecto 24 horas; configurable con `identityRetentionHours` (mínimo 1, máximo 168).
- Se purga al abrir la base y cada 10 minutos durante el monitoreo.
- `IdentityMemory.purge_all()` borra todo de inmediato.
- Si la base falla, el monitoreo continúa sin memoria.

## Límites

- La ventana de reasociación entre cámaras sigue siendo `handoffSeconds`; la base no amplía ese plazo.
- Entre cámaras solo se asocia identidad con relojes verificados por el operador.
- La estatura estimada es ruidosa y no se validó con personas reales.
