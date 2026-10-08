# Prompt para crear planos con perspectiva coherente

Este prompt está pensado para entregarle varias imágenes de cámaras etiquetadas (`Cámara 1`, `Cámara 2`, `Cámara 3`...). La imagen resultante ayuda a preparar el proyecto, pero no reemplaza la calibración con puntos reales.

## Prompt para reconstruir un plano a partir de varias cámaras

```text
Actúa como especialista en fotogrametría, cartografía arquitectónica, visión por computador y reconstrucción de planos.

Recibirás varias imágenes de cámaras del mismo espacio. Cada imagen viene etiquetada con un identificador, por ejemplo Cámara 1, Cámara 2, Cámara 3 y Cámara 4. Construye un único plano operativo coherente usando todas las imágenes.

Objetivo:

- reconstruir la distribución común del suelo;
- ubicar pasillos, paredes, columnas, puertas, escaleras, entradas y negocios visibles;
- conectar las imágenes mediante elementos físicos compartidos;
- producir un plano completo donde se pueda colocar la posición proyectada de cada cámara y de cada persona.

Procedimiento obligatorio:

1. Analiza cada cámara por separado antes de unirlas.
2. Para cada imagen identifica líneas del suelo, esquinas, columnas, puertas, juntas de baldosas y otros elementos fijos.
3. Busca correspondencias entre cámaras: el mismo pilar, esquina, puerta, intersección de baldosas, borde de pared o acceso debe recibir el mismo nombre en todas las imágenes.
4. Construye una tabla de correspondencias con: elemento, cámaras donde aparece, coordenadas aproximadas en cada imagen, nivel de confianza y motivo de la coincidencia.
5. Usa esas correspondencias para formar un sistema de coordenadas común. Si las cámaras observan el mismo suelo, proyecta sus referencias a un plano compartido.
6. Conserva la perspectiva de cada cámara. No conviertas una vista oblicua en una fotografía frontal y no endereces automáticamente rectángulos o fachadas deformadas.
7. Si dos cámaras no tienen elementos compartidos, no inventes una unión. Mantén sus zonas separadas y marca “sin conexión geométrica comprobable”.
8. Si una zona no aparece en ninguna cámara, no la dibujes como si fuera conocida. Marca el espacio como “no observado”.
9. Si una cámara solo muestra una parte del suelo, conserva el recorte y su orientación; no extiendas artificialmente la imagen.
10. No inventes negocios, paredes, puertas, medidas, niveles, escaleras ni pasillos que no aparezcan en alguna imagen o que no hayan sido proporcionados.

Reglas para la geometría:

- Las homografías se calculan únicamente con puntos del mismo plano físico del suelo.
- No uses cabezas, torsos, personas, sombras, reflejos, vehículos ni objetos móviles como referencias geométricas.
- Las personas marcadas en dos cámaras sirven para validar tiempo y asociación, no para sustituir los puntos físicos del suelo.
- No fuerces cuatro puntos a formar un rectángulo. Si la imagen muestra un trapecio por perspectiva, conserva el trapecio.
- Distribuye las referencias por toda la zona visible y evita puntos casi alineados.
- Si no existe escala real, usa coordenadas relativas y escribe “escala no calibrada”.

Entregables:

1. Plano operativo unificado en vista superior, con la orientación indicada.
2. Versión del plano con cuadrícula y sistema de coordenadas.
3. Vista con el contorno de cobertura de cada cámara y el identificador de la cámara.
4. Tabla de correspondencias entre cámaras.
5. Lista de puntos recomendados para calibrar cada cámara, indicando si son:
   - referencia física del suelo;
   - referencia compartida con otra cámara;
   - referencia dudosa que debe revisar el operador.
6. Zonas no observadas o ambiguas.
7. Advertencias sobre perspectiva, oclusiones, deformaciones y uniones que no se pudieron comprobar.

Formato de salida de cada cámara:

- Cámara: [identificador]
- Orientación aproximada: [ángulo o dirección]
- Región visible del suelo: [descripción]
- Referencias válidas: [lista]
- Referencias compartidas: [lista]
- Referencias dudosas: [lista]
- Conexiones geométricas confiables: [lista de cámaras]
- Conexiones no comprobables: [lista de cámaras]

No generes un diseño conceptual ni completes huecos con imaginación. Cuando falte evidencia, dibuja el vacío y decláralo explícitamente.
```

## Cómo entregar las imágenes

Sube las imágenes con nombres claros, por ejemplo:

```text
Cámara_1.jpg
Cámara_2.jpg
Cámara_3.jpg
Cámara_4.jpg
```

Si conoces alguno de estos datos, inclúyelo junto a las imágenes:

- altura aproximada de la cámara;
- dirección hacia la que apunta;
- posición aproximada de la cámara en el edificio;
- ancho o largo real de un pasillo;
- plano arquitectónico o imagen aérea de referencia;
- si dos cámaras se superponen o solo son consecutivas.

Con una sola imagen el modelo solo puede describir una región. Para armar un plano completo necesita imágenes que se superpongan físicamente o una referencia externa que conecte las cámaras. Si no hay solapamiento, la salida correcta es mantener zonas separadas y pedir una referencia adicional.

```text
Actúa como especialista en cartografía arquitectónica, fotogrametría y reconstrucción de planos a partir de imágenes.

Usa la imagen adjunta como única fuente de geometría visible. Crea una representación limpia del mismo espacio para usarla como plano operativo de un sistema de visión artificial.

Reglas geométricas obligatorias:

1. Conserva la orientación original de la imagen. Si la escena está en horizontal, mantén horizontal; si está en vertical, mantén vertical.
2. Conserva los ángulos, líneas de fuga, perspectiva y deformación proyectiva que aparecen en la referencia. No conviertas automáticamente una vista oblicua en una vista perfectamente frontal.
3. Las líneas paralelas en el espacio solo deben permanecer paralelas si también lo son en la imagen de referencia. Mantén los puntos de fuga cuando existan.
4. No endereces rectángulos, fachadas, pasillos ni negocios. Si un rectángulo aparece como trapecio por perspectiva, conserva ese trapecio.
5. No cambies la posición relativa, el tamaño aparente ni la proporción de calles, paredes, entradas, columnas, escaleras, negocios u obstáculos.
6. No inventes edificios, puertas, negocios, pasillos, marcas, texto ni medidas que no sean visibles o que no hayan sido proporcionados.
7. Elimina personas, vehículos, anuncios temporales, reflejos y elementos móviles solo cuando eso no cambie la geometría del suelo.
8. Mantén una textura de suelo neutra y un contraste suficiente para que se puedan marcar puntos de referencia.
9. Añade una cuadrícula ligera y una flecha de norte únicamente si la orientación se conoce. Si no se conoce, no la inventes.
10. Si se proporciona una escala real, respétala. Si no se proporciona, escribe claramente “escala no calibrada” y no calcules distancias métricas.

Entrega:

- una imagen PNG limpia en alta resolución;
- la misma imagen con una cuadrícula discreta;
- una lista de 8 a 12 puntos de referencia visibles y estables, en orden horario, describiendo cada punto sin inventar coordenadas;
- una lista de zonas cuya geometría no es suficientemente visible para calibrar;
- una advertencia explícita sobre cualquier parte ocluida, recortada o deformada.

No generes una vista nueva ni un diseño conceptual. Corrige y limpia la referencia conservando su geometría proyectiva.
```

## Prompt para una vista de cámara y un plano existente

Cuando se tenga una imagen del plano y una imagen de la cámara, usar este complemento:

```text
Compara la imagen del plano con la imagen de cámara. No dibujes puntos automáticamente si no puedes identificar el mismo elemento físico en ambas imágenes.

Propón solamente referencias que cumplan estas condiciones:

- son fijas y visibles en las dos imágenes;
- tienen una esquina o centro claramente localizable;
- están distribuidas por toda la zona donde caminarán las personas;
- no pertenecen a personas, sombras, vehículos, pantallas o elementos móviles;
- no son cuatro puntos casi alineados.

Para cada referencia devuelve: nombre del elemento, ubicación aproximada en la imagen de cámara, ubicación correspondiente en el plano, nivel de confianza y motivo de la correspondencia.

Si una correspondencia es dudosa, márcala como “revisar” y no la uses para calcular la homografía.
```

La homografía final debe calcularse con puntos revisados por el operador. El plano generado por IA no debe considerarse una fuente métrica confiable por sí solo.
