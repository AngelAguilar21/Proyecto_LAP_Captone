"""Insights espaciales ligados al negocio, portados de AeroVision (Insights Modelo/historico).

    from insights import analizar_replay
    resultado, eventos, meta = analizar_replay(raiz, sesion, config, negocios)

Eventos (EXPOSURE, ENTER, DWELL, EXIT, RETURN, QUEUE), mapa de calor KDE, rutas frecuentes (PrefixSpan), grafo
origen-destino, permanencia, captación, densidad y congestión sobre las zonas y los negocios de AeroTrack, y su relación
con las ventas por hora (insights.ventas).
"""
from .analisis import PARAMETROS, analizar, analizar_replay, parametros_escalados
from .eventos import Estancia, estancias, generar_eventos
from .espacial import kde_grilla, origen_destino, prefixspan, secuencias_semanticas
from .metricas import episodios_congestion, metricas_locales, metricas_zonas, ocupacion_por_segundo, paso_serie, series_temporales
from .piso import PisoTransitable, piso_desde_config
from .trayectorias import Consolidado, consolidar, desde_replay
from .zonas import Zona, asignar_zonas, dentro_poligono, desde_config
