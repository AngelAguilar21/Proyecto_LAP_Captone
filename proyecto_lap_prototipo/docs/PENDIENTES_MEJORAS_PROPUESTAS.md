# Pendientes y mejoras propuestas para AeroTrack

Fecha de revisión: 2026-10-06  
Rama revisada: `main`  
Base revisada: código actual después de traer `origin/main` hasta `f0f2a5e`.

Este documento resume las mejoras que conversamos y compara cada una contra lo que ya existe en el código actual. La idea es tener una hoja de ruta clara: qué ya está, qué está parcial y qué falta implementar para que el prototipo sea más sólido para pruebas con cámaras reales, análisis comercial y presentación al profesor/LAP.

## 1. Estado actual verificado en el código

### Ya existe en el proyecto

- Monitoreo con YOLO + ByteTrack para detección y seguimiento por cámara.
- Reidentificación entre cámaras con OSNet (`models/osnet.onnx`, `src/following/reid.py`, `src/identity/`).
- Motor nuevo de identidad multicámara:
  - `src/identity/associator.py`
  - `src/identity/engine.py`
  - `src/identity/memory.py`
  - `src/identity/regroup.py`
  - `src/identity/quality.py`
  - `src/identity/tracklet.py`
- Reagrupación/cierre de identidades al finalizar grabaciones.
- Homografía por puntos de suelo para proyectar personas al plano.
- Validación/documentación técnica de identidad en `docs/EVALUACION_IDENTIDAD.md`.
- Insights espaciales y comerciales en `src/insights/`.
- Paneles nuevos en interfaz:
  - `InsightsPanel.tsx`
  - `PersonPairs.tsx`
  - mejoras en `MapCanvas`, `MonitoringWorkspace`, replay y reportes.
- Negocios y ventas usando SQLite por proyecto, no servidor externo.
- Registro/vinculación de negocios con accesos/líneas de conteo.
- Reportes por sesión y consulta comercial.
- Señal inicial de “objeto nuevo / bolsa” en `src/bag_signal.py`.
- Guías técnicas nuevas:
  - `docs/ARQUITECTURA.md`
  - `docs/EVALUACION_IDENTIDAD.md`
  - `docs/REFERENCIAS_MULTICAMARA.md`
  - `docs/GUIA_DE_USO.md`
- Herramientas de evaluación:
  - `tools/evaluar_identidad.py`
  - `tools/barrido_umbrales.py`
  - `tools/ablaciones.py`
  - `tools/medir_rendimiento.py`
- Pruebas nuevas de identidad, rendimiento, calibración, replay, subida de video e insights.

### Cambios importantes respecto a versiones anteriores

- P2PNet fue retirado del flujo principal. La arquitectura actual declara que las aglomeraciones salen del seguimiento con YOLO/ByteTrack, no de P2PNet.
- El submódulo `external/P2PNet` fue eliminado del Git. La carpeta puede quedar localmente, pero ya no forma parte del `main`.
- Se eliminó bastante código antiguo del dashboard y de conteo separado.
- El proyecto se está orientando a un esquema más claro: seguimiento multicámara + identidad + insights + comercio.

## 2. Parámetros mínimos que deben estar bien configurados para reidentificación

Estos parámetros son críticos. Si uno falla, la misma persona puede aparecer con IDs distintos entre cámaras.

| Parámetro | Estado actual | Para qué sirve | Riesgo si está mal |
|---|---:|---|---|
| `links` entre cámaras | Existe en config | Define qué cámaras se pueden comparar entre sí | Si A no enlaza con B, nunca intenta unir IDs |
| `clocksVerified` / Asociar recorridos | Existe | Permite continuidad entre cámaras | Si está apagado, cada cámara conserva IDs separados |
| `handoffSeconds` | Existe | Tiempo máximo para buscar a una persona en otra cámara | Si es muy bajo, pierde personas que tardan en reaparecer |
| `matchDistance` | Existe | Tolerancia espacial en el mapa | Si es muy bajo, bloquea asociaciones aunque visualmente parezcan correctas |
| `reidAcceptScore` | Existe como config avanzada | Umbral mínimo para aceptar coincidencia | Si es alto, no une; si es bajo, une falsos positivos |
| `reidAmbiguityMargin` | Existe como config avanzada | Diferencia mínima entre mejor y segundo candidato | Si es alto, rechaza casos parecidos; si es bajo, puede confundir |
| Homografía por cámara | Existe | Lleva pies/personas del video al mapa | Si está imprecisa, el algoritmo cree que la persona está lejos |
| Calidad visual OSNet | Existe | Extrae apariencia de la persona | Si la persona está tapada/lejana/cortada, la característica sale débil |

## 3. Pendientes recomendados por prioridad

## A. Mejorar interfaz para configuración de continuidad entre cámaras

**Estado actual:** parcial.

El sistema soporta `links`, `clocksVerified`, `handoffSeconds`, `matchDistance`, OSNet y umbrales, pero no todo está expuesto de forma clara en la interfaz principal.

**Qué falta implementar:**

- Pantalla o bloque claro llamado, por ejemplo, **Red de cámaras / Continuidad entre cámaras**.
- Selector visual para enlazar cámaras cercanas:
  - Cámara 1 puede comparar con Cámara 2.
  - Cámara 2 puede comparar con Cámara 1.
  - Permitir enlaces por piso/nivel.
- Mostrar si una cámara está “lista para continuidad”:
  - Tiene fuente.
  - Tiene homografía.
  - Está en el mismo piso que la cámara enlazada.
  - Tiene enlace configurado.
  - OSNet está disponible.
- Exponer parámetros avanzados con ayuda clara:
  - ventana de búsqueda (`handoffSeconds`)
  - distancia de asociación (`matchDistance`)
  - umbral de aceptación ReID
  - margen de ambigüedad
- Agregar un diagnóstico: “por qué no se unió esta persona”.

**Para qué sirve:** permite que el usuario configure la reidentificación sin tocar JSON/config interna ni depender de Codex. También ayuda a explicar al profesor por qué una persona sí o no fue emparejada.

## B. Diagnóstico visual de reidentificación

**Estado actual:** parcial.

Existe `PersonPairs` y el motor registra asociaciones, pero falta una vista clara para auditar casos aceptados/rechazados.

**Qué falta implementar:**

- Panel de pares candidatos entre cámaras:
  - miniatura Cámara A
  - miniatura Cámara B
  - score OSNet
  - distancia en mapa
  - diferencia temporal
  - estado: aceptado, rechazado por apariencia, rechazado por distancia, ambiguo.
- Línea de tiempo de handoffs:
  - `P00012: Cámara 1 -> Cámara 2, t=38.4s`
- Botón para filtrar solo IDs compartidos.
- Resaltar en video/mapa cuando un ID aparece en dos cámaras.
- Mostrar explicación por cada caso:
  - “No se unió porque había otro candidato parecido”.
  - “No se unió porque cayó a 5.2 m del punto esperado”.
  - “No se unió porque OSNet vio ropa/apariencia distinta”.

**Para qué sirve:** convierte la reidentificación en algo demostrable y defendible. Sin esto, el usuario ve cajas con IDs pero no entiende por qué no coinciden.

## C. Mejorar calibración/homografía

**Estado actual:** existe, pero puede mejorarse.

El sistema ya proyecta al mapa con puntos de suelo. El problema es que una mala homografía bloquea asociaciones o genera posiciones poco precisas.

**Qué falta implementar:**

- Wizard de calibración más guiado:
  - pedir 6 a 8 puntos, no solo 4;
  - advertir si los puntos están muy juntos;
  - advertir si todos están en una esquina;
  - mostrar error promedio y error por punto;
  - separar puntos de entrenamiento y puntos de validación.
- Modo de revisión:
  - mostrar dónde cae cada punto en el mapa;
  - colorear puntos con error alto;
  - mostrar huella de la cámara sobre el plano.
- Validación entre cámaras:
  - si dos cámaras ven una zona compartida, comparar si proyectan personas al mismo lugar.
- Ajuste asistido:
  - sugerir “mueve este punto” si la proyección está sesgada.
- Soporte futuro para coordenadas reales:
  - si se consigue CAD/BIM/LAP oficial;
  - si se extraen coordenadas desde mapas externos;
  - si se registran mediciones de campo.

**Para qué sirve:** mejora mapa, flujo, zonas de calor y reidentificación. La reidentificación multicámara depende mucho de que el punto proyectado tenga sentido físico.

## D. Migrar datos importantes a PostgreSQL + PostGIS

**Estado actual:** no implementado. Actualmente se usan archivos locales y SQLite por proyecto.

**Qué falta implementar:**

- Definir una base PostgreSQL con extensión PostGIS.
- Migrar o sincronizar:
  - proyectos;
  - usuarios y roles;
  - cámaras;
  - homografías;
  - pisos/planos;
  - zonas/negocios;
  - líneas de conteo;
  - sesiones de monitoreo;
  - eventos de cruces;
  - incidentes de aglomeración;
  - ventas importadas;
  - métricas por hora;
  - resultados de ReID y tracklets;
  - geometrías de mapa.
- Mantener SQLite/local como modo demo/offline, si conviene.
- Diseñar migraciones.
- Agregar backups/exportación.

**Para qué sirve:** permite trabajo multiusuario, persistencia real, consultas históricas, reportes robustos y análisis espacial con geometrías. PostGIS es especialmente útil para zonas, cámaras, tiendas, líneas y trayectorias.

## E. Estructura de grafo para red de cámaras y rutas posibles

**Estado actual:** parcial en configuración por `links`, pero no hay una capa de grafo formal.

**Qué falta implementar:**

- Crear grafo de cámaras por piso:
  - nodos: cámaras, accesos, zonas, negocios, intersecciones;
  - aristas: continuidad posible, distancia, tiempo esperado, confiabilidad.
- Usar el grafo para limitar comparaciones:
  - una cámara solo busca candidatos en cámaras cercanas o alcanzables;
  - priorizar caminos probables;
  - evitar comparar contra todas las cámaras cuando haya muchas.
- Guardar estadísticas por arista:
  - cuántas asociaciones reales tuvo A→B;
  - tiempo promedio de traslado;
  - tasa de falsos positivos/rechazos.
- Integrar con PostGIS a futuro.

**Para qué sirve:** mejora rendimiento y precisión cuando el sistema tenga muchas cámaras. Evita buscar coincidencias imposibles y ayuda a explicar la lógica de “por dónde pudo caminar la persona”.

## F. Mejorar ReID para casos difíciles

**Estado actual:** OSNet implementado; evaluación y herramientas existen.

**Qué falta implementar:**

- Mejorar extracción de características:
  - seleccionar mejores crops del track, no solo muestras puntuales;
  - evitar crops con oclusión;
  - descartar cajas demasiado pequeñas;
  - guardar una galería por track con varias vistas.
- Probar comparación por partes del cuerpo:
  - cuerpo completo;
  - torso;
  - piernas;
  - cabeza solo si la resolución lo permite.
- Medir si “part-based ReID” mejora con cámaras cenitales/inclinadas.
- Mejorar manejo de oclusión:
  - juntar fragmentos cortos de la misma cámara;
  - reintentar cierre al final de la sesión.
- Exponer métricas de confianza al usuario.

**Para qué sirve:** algunas personas no se unen porque aparecen pequeñas, cortadas, de espaldas o con ropa similar a otras. Esta mejora reduce fragmentación y falsos negativos.

## G. Pruebas con videos adecuados para ReID

**Estado actual:** hay herramientas de evaluación y demos, pero falta un set propio claro para sustentación.

**Qué falta implementar/preparar:**

- Carpeta de pruebas con 2 o 3 escenarios claros:
  - persona entra por Cámara 1 y aparece en Cámara 2;
  - varias personas parecidas para probar ambigüedad;
  - una persona con oclusión;
  - entrada/salida de tienda.
- Anotaciones simples:
  - “persona A aparece en cámara 1 de 00:10 a 00:18 y en cámara 2 de 00:25 a 00:35”.
- Script de prueba reproducible:
  - corre solo esas cámaras;
  - genera reporte de IDs correctos/incorrectos;
  - exporta capturas para presentación.
- Panel de “validación de prueba” en UI.

**Para qué sirve:** permite demostrar al profesor que el sistema funciona en un caso controlado y explicar cuándo falla.

## H. Dashboard ejecutivo comercial

**Estado actual:** parcial. Hay negocios, ventas, insights y reportes, pero falta una vista ejecutiva final más clara.

**Qué falta implementar:**

- Dashboard por negocio/local:
  - entradas;
  - salidas;
  - permanencia estimada;
  - horas pico;
  - tasa entrada/salida;
  - aglomeraciones cercanas;
  - venta importada;
  - venta estimada;
  - conversión estimada.
- Ranking:
  - locales con más flujo;
  - locales con mayor conversión;
  - zonas con más aglomeración;
  - oportunidades comerciales.
- Comparación temporal:
  - por hora;
  - por día;
  - por sesión;
  - por cámara;
  - por negocio.
- Explicar claramente si es dato real, estimado o simulado.

**Para qué sirve:** traduce el tracking técnico a valor comercial. Es lo que más entiende un gerente: flujo, venta, conversión, oportunidades.

## I. CSV de ventas y pronóstico comercial

**Estado actual:** parcial. Hay módulo comercial y ventas, pero se debe consolidar el flujo de importación, validación y explicación.

**Qué falta implementar o reforzar:**

- Plantilla CSV oficial para ventas.
- Validador de columnas:
  - negocio;
  - fecha;
  - hora;
  - ventas;
  - tickets;
  - moneda.
- Importación con errores claros.
- Cruce por negocio y hora.
- Pronóstico en vivo:
  - entradas actuales × ticket promedio histórico por hora/día.
- Estados claros:
  - “sin historial suficiente”;
  - “estimación, no venta real”;
  - “venta confirmada por CSV”.

**Para qué sirve:** completa las fases comerciales: tráfico → ventas → conversión → proyección.

## J. Correlación aglomeración-ventas

**Estado actual:** parcial por insights/reportes; falta vista específica y validación estadística clara.

**Qué falta implementar:**

- Para cada incidente de aglomeración:
  - ventana horaria;
  - negocio cercano;
  - ventas durante esa ventana;
  - ventas promedio históricas de esa franja.
- Indicadores:
  - subió/bajó contra lo normal;
  - tamaño de muestra;
  - confiabilidad.
- Mensajes responsables:
  - “correlación, no causalidad”;
  - “muestra insuficiente”.

**Para qué sirve:** responde si una aglomeración ayuda o perjudica ventas, pero sin vender conclusiones falsas.

## K. Señal “salió con bolsa / objeto nuevo”

**Estado actual:** existe `src/bag_signal.py`, pero requiere validación y una UI más clara.

**Qué falta implementar/mejorar:**

- Activar por negocio/acceso desde la interfaz.
- Mostrar resultados como señal estimada, no compra confirmada.
- Diferenciar objetos COCO:
  - handbag puede confundirse con cartera;
  - mochila/maleta no debe contarse como compra;
  - bolsa real de tienda puede no detectarse bien.
- Vincular con identidad:
  - entró sin objeto;
  - salió con objeto nuevo;
  - misma persona emparejada con confianza.
- Reportar porcentaje no emparejado.

**Para qué sirve:** da una señal alternativa a ventas, pero debe presentarse con cautela. Sirve como “evidencia posible de compra”, no como censo.

## L. ROI y zonas de interés sugeridas automáticamente

**Estado actual:** parcial. Hay zonas, negocios y oportunidades/insights, pero falta un flujo completo de ROI sugerida → edición → guardado.

**Qué falta implementar:**

- Sugerir zonas por ocupación observada:
  - zonas calientes;
  - zonas de permanencia;
  - puntos de cruce;
  - oportunidades fuera de negocios existentes.
- Permitir editar polígonos sugeridos.
- Convertir sugerencia en zona guardada.
- Clasificar zonas:
  - negocio existente;
  - oportunidad comercial;
  - aglomeración operativa;
  - tránsito/pasillo;
  - acceso.
- Ranking de zonas por tráfico y permanencia.

**Para qué sirve:** transforma el mapa en herramienta de análisis, no solo visualización.

## M. Alertas en UI

**Estado actual:** existe módulo de alertas e incidentes, pero puede mejorar diseño y comportamiento.

**Qué falta implementar/mejorar:**

- Alertas tipo toast o panel temporal:
  - aparece al superar umbral;
  - se puede cerrar;
  - se autocierra si ya no está activa;
  - queda en bitácora.
- Colores consistentes:
  - rojo: crítico;
  - ámbar: advertencia;
  - verde: resuelto;
  - gris: revisado/falsa alarma.
- Agrupar alertas repetidas.
- Mostrar cámara/zona/personas/duración.
- Botón “ver cámara” y “ver en mapa”.

**Para qué sirve:** mejora operación en vivo y evita que el usuario dependa de revisar tablas.

## N. Mejorar UI/UX general

**Estado actual:** parcial. Hay mejoras y tema oscuro/claro, pero aún conviene una revisión visual completa.

**Qué falta revisar:**

- Sidebar colapsado:
  - logo;
  - iconos;
  - botón de salir;
  - usuario centrado.
- Botones principales y secundarios:
  - guardar no debe confundirse con iniciar monitoreo;
  - cancelar/deshacer visibles;
  - estados hover/selected legibles.
- Formularios de cámara:
  - menos menús escondidos;
  - pasos claros;
  - guardar visible.
- Mapas:
  - controles consistentes;
  - zoom/pan en todas las vistas;
  - capas claras;
  - leyendas menos invasivas.
- Video y resultados:
  - reproducción general e individual por cámara;
  - mapa sincronizado abierto por defecto;
  - IDs compartidos resaltados.
- Reportes:
  - explicar si es por sesión, por día o por rango;
  - separar datos reales/simulados;
  - exportar CSV/PDF.

**Para qué sirve:** reduce confusión del usuario final y hace que el sistema parezca producto terminado, no solo prototipo técnico.

## O. Rendimiento para cámaras en vivo

**Estado actual:** hay perfil de hardware, mediciones y optimizaciones parciales.

**Qué falta implementar/mejorar:**

- Perfil automático:
  - bajo, equilibrado, preciso.
- Control de FPS de inferencia por cámara.
- Procesar embeddings OSNet solo cuando el track lo necesite.
- Decodificación eficiente de streams.
- Cola por cámara para evitar bloquear todo si una fuente se cae.
- Modo “sin P2PNet / sin densidad” permanente para laptops.
- Monitoreo de rendimiento en UI:
  - ms por ciclo;
  - FPS efectivo;
  - cámaras atrasadas;
  - fuente desconectada.

**Para qué sirve:** permite correr con cámaras reales o IP Webcam sin que el sistema se congele.

## P. Cámaras en vivo y fuentes externas

**Estado actual:** soporta archivos, USB, RTSP/streams y URLs, pero falta guía/validación para usuario final.

**Qué falta implementar:**

- Validador de fuente:
  - archivo local;
  - webcam USB;
  - RTSP;
  - HTTP/HLS;
  - YouTube si se resuelve con `yt-dlp`.
- Diagnóstico:
  - no abre;
  - abre pero no hay frames;
  - baja resolución;
  - latencia alta;
  - stream bloqueado.
- Guía para IP Webcam/celular.
- Configuración de reconexión.
- Prueba rápida antes de guardar cámara.

**Para qué sirve:** facilita pruebas reales con celulares, cámaras IP y streams públicos.

## Q. Persistencia, roles y seguridad

**Estado actual:** hay autenticación local y roles operador/administrador; datos mayormente locales/SQLite.

**Qué falta implementar/mejorar:**

- Revisar roles definitivos:
  - operador;
  - administrador;
  - analista;
  - solo lectura.
- Pasar usuarios a BD cuando exista PostgreSQL.
- Auditoría:
  - quién cambió cámara;
  - quién borró zona;
  - quién importó ventas;
  - quién inició/detuvo monitoreo.
- Separar datos demo de datos reales.
- Política de retención:
  - videos;
  - embeddings;
  - sesiones;
  - ventas;
  - logs.

**Para qué sirve:** necesario si el prototipo se presenta como sistema real para aeropuerto o tiendas.

## R. Datos y datasets externos

**Estado actual:** se revisó SCOUT como referencia; no está integrado al sistema.

**Qué falta hacer:**

- Mantener `SCOUT` o papers como referencia local, pero no subir datasets grandes a Git.
- Usar SCOUT para aprender estructura:
  - cámaras sincronizadas;
  - calibraciones;
  - mallas 3D;
  - anotaciones.
- No depender de SCOUT para el prototipo LAP, salvo pruebas técnicas.
- Preparar dataset pequeño propio para demo.

**Para qué sirve:** SCOUT ayuda como referencia de arquitectura multicámara, pero no reemplaza pruebas con videos del entorno LAP/prototipo.

## S. Documentación para presentación

**Estado actual:** hay docs técnicas, pero falta una guía narrativa para sustentar.

**Qué falta preparar:**

- Explicación simple del pipeline:
  1. Video entra.
  2. YOLO detecta personas.
  3. ByteTrack mantiene IDs por cámara.
  4. OSNet extrae apariencia.
  5. Homografía proyecta al mapa.
  6. Motor de identidad une tracklets entre cámaras.
  7. Insights calculan flujo, ocupación, negocio, ventas.
- Qué datos se guardan y dónde.
- Qué es dato real vs estimado.
- Qué limitaciones existen.
- Qué falta para producción.

**Para qué sirve:** ayuda a responder preguntas del profesor y presentar el avance sin improvisar.

## 4. Recomendación de orden de implementación

### Fase 1: dejar demostrable ReID multicámara

- UI para enlaces entre cámaras.
- Diagnóstico de pares candidatos.
- Resaltar IDs compartidos en video/mapa.
- Mejorar calibración y validación de homografía.
- Preparar dos videos demo claros con anotación.

### Fase 2: consolidar comercial

- Dashboard ejecutivo comercial.
- Plantilla/importación CSV robusta.
- Pronóstico de ventas con historial.
- Correlación aglomeración-ventas.
- Exportación clara de reportes.

### Fase 3: robustez de operación

- Mejor UI/UX completa.
- Alertas tipo toast + bitácora.
- Fuentes en vivo con diagnóstico.
- Perfil de rendimiento.
- Guía de uso final.

### Fase 4: arquitectura de datos

- PostgreSQL + PostGIS.
- Migraciones.
- Auditoría y roles.
- Grafo de cámaras/rutas.
- Persistencia histórica para análisis real.

### Fase 5: investigación avanzada

- Part-based ReID.
- Mejor manejo de oclusión.
- Señal de bolsa más robusta.
- Uso de datasets externos como referencia.
- Comparación con técnicas/papers recientes.

## 5. Riesgos principales si se deja como está

- La reidentificación puede funcionar internamente, pero el usuario no ve claramente por qué se unió o no se unió una persona.
- La calibración manual puede hacer que personas correctas no se unan por distancia en mapa.
- Si se bajan mucho los umbrales de ReID, aparecerán falsos positivos.
- Sin PostgreSQL/PostGIS, el sistema sirve como prototipo local, pero no como plataforma multiusuario robusta.
- Sin videos demo bien anotados, es difícil demostrar precisión frente al profesor.
- La parte comercial existe parcialmente, pero necesita una narrativa y dashboard más ejecutivo.

## 6. Próximo paso recomendado

El siguiente cambio más valioso es implementar una pantalla de **Diagnóstico de Reidentificación**. Debe mostrar pares A↔B aceptados/rechazados con score, distancia y razón. Eso permitiría saber inmediatamente si el problema es video, homografía, apariencia, umbral o ambigüedad.

Después de eso, conviene mejorar la calibración y preparar un video demo controlado donde una persona pase claramente de Cámara 1 a Cámara 2.
