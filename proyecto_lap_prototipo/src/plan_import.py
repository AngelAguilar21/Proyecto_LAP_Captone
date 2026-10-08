"""Import floor plans as relative geometry; never infer a room's purpose as fact."""
import base64
import io
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from pdf_runtime import serialized_pdfium


# Lado mayor al que se guarda el plano rasterizado. Manda cuanto zoom aguanta antes
# de pixelarse, y el plano viaja dentro del JSON del proyecto, asi que el peso importa.
# Medido con un plano de linea de 4000x2800: en JPEG q88 a 1600 px ocupaba 311 KB en
# base64; en WebP a 3200 px ocupa 70 KB. Cuatro veces mas detalle y cuatro veces menos
# peso, porque JPEG es mal formato para dibujo de linea.
LADO_MAXIMO = 3200


@serialized_pdfium
def _pdf_png(data, page):
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(data)
    try:
        if not 0 <= page < len(document):
            raise ValueError(f"El PDF contiene {len(document)} páginas.")
        pdf_page = document[page]
        try:
            width, height = pdf_page.get_size()
            # Un PDF es vectorial: el detalle esta ahi y solo se pierde al rasterizar.
            # Se rasteriza al lado mayor de LADO_MAXIMO para que el plano aguante zoom;
            # el tope de escala evita agrandar de mas una pagina chica.
            bitmap = pdf_page.render(scale=min(4.,LADO_MAXIMO/max(width,height)))
            try:
                image = bitmap.to_pil()
                buffer = io.BytesIO()
                image.save(buffer,format="PNG")
                return buffer.getvalue()
            finally:
                bitmap.close()
        finally:
            pdf_page.close()
    finally:
        document.close()


def raster_pdf(data, page):
    try:
        import pypdfium2  # noqa: F401
        return _pdf_png(data,page)
    except ImportError:
        runtime = os.environ.get("AEROTRACK_DOCUMENT_PYTHON")
        if not runtime or not Path(runtime).is_file():
            raise ValueError("Para importar PDF se necesita pypdfium2 o AEROTRACK_DOCUMENT_PYTHON con esa dependencia.")
        result = subprocess.run([runtime,str(Path(__file__).resolve()),"pdf",str(page)],input=data,capture_output=True,timeout=40,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if result.returncode:
            raise ValueError("No se pudo abrir esa página del PDF. Comprueba que el archivo no esté protegido y que la página exista.")
        return result.stdout


def dxf_geometry(data, target_width):
    """Read ASCII DXF LINE/LWPOLYLINE/CIRCLE entities and their layer names."""
    text = data.decode("utf-8",errors="replace").splitlines()
    if len(text)>500000:
        raise ValueError("El DXF es demasiado complejo para este prototipo.")
    pairs=[]
    for i in range(0,len(text)-1,2):
        try:
            pairs.append((int(text[i].strip()),text[i+1].strip()))
        except ValueError:
            raise ValueError("Usa un DXF ASCII válido; los DXF binarios requieren conversión.")
    entities=[]
    current=[]
    kind=""
    for code,value in pairs+[(0,"EOF")]:
        if code==0:
            if kind in ("LINE","LWPOLYLINE","CIRCLE"):
                entities.append((kind,current))
            kind=value
            current=[]
        else:
            current.append((code,value))
    shapes=[]
    for kind, values in entities:
        bycode={code:value for code,value in values}
        layer=bycode.get(8,"")
        try:
            if kind=="LINE":
                vertices=[(float(bycode[10]),float(bycode[20])),(float(bycode[11]),float(bycode[21]))]
                closed=False
            elif kind=="CIRCLE":
                x,y,r=float(bycode[10]),float(bycode[20]),float(bycode[40])
                if r<=0:
                    continue
                vertices=[(x+math.cos(i*math.pi/18)*r,y+math.sin(i*math.pi/18)*r) for i in range(36)]
                closed=True
            else:
                vertices=[]
                x=None
                for code,value in values:
                    if code==10:
                        x=float(value)
                    elif code==20 and x is not None:
                        vertices.append((x,float(value)))
                        x=None
                closed=bool(int(bycode.get(70,"0"))&1)
            if len(vertices)>=2 and all(math.isfinite(v) for p in vertices for v in p):
                shapes.append((vertices,closed,layer))
        except (ValueError,KeyError):
            continue
    if not shapes:
        raise ValueError("No se encontraron LINE, LWPOLYLINE o CIRCLE. Exporta el CAD como DXF ASCII o PDF.")
    xs=[p[0] for vertices,_,_ in shapes for p in vertices]
    ys=[p[1] for vertices,_,_ in shapes for p in vertices]
    dx,dy=max(xs)-min(xs),max(ys)-min(ys)
    if dx<=0 or dy<=0:
        raise ValueError("La geometría CAD debe tener ancho y alto.")
    scale=target_width/dx
    height=dy*scale
    if not 1<=height<=10000:
        raise ValueError("La proporción del plano CAD excede el tamaño permitido.")
    from PIL import Image,ImageDraw
    image=Image.new("RGB",(1600,max(1,round(1600*dy/dx))),"#000000")
    if image.height>5000:
        raise ValueError("El plano CAD es demasiado alto; exporta una región del dibujo.")
    draw=ImageDraw.Draw(image)
    zones=[]
    for vertices,closed,layer in shapes:
        points=[[(x-min(xs))*scale,(max(ys)-y)*scale] for x,y in vertices]
        pixels=[(x/target_width*image.width,y/height*image.height) for x,y in points]
        draw.line(pixels+([pixels[0]] if closed else []),fill="#ffffff",width=2)
        if closed and len(points)>=3 and len(zones)<80:
            label=layer.lower()
            category=next((value for words,value in [(('wall','muro'),'wall'),(('door','puerta'),'door'),(('restricted','restring'),'restricted'),(('commercial','comerc'),'commercial'),(('corridor','pasillo'),'corridor')] if any(word in label for word in words)),"room")
            zones.append({"id":f"cad-{len(zones)+1}","name":layer if layer and layer!="0" else f"Área CAD {len(zones)+1}","kind":category,"shape":"polygon","points":points})
    output=io.BytesIO()
    image.save(output,format="JPEG",quality=88)
    return {"background":"data:image/jpeg;base64,"+base64.b64encode(output.getvalue()).decode(),"width":target_width,"height":round(height,5),"zones":zones,
            "warnings":["Geometría en unidades relativas. Confirma usos de áreas y capas; sus nombres no se infieren de personas ni trayectorias."]}


def import_plan(data, name, width=12., page=0):
    suffix=Path(name).suffix.lower()
    if suffix==".dwg":
        converter=shutil.which("dwg2dxf")
        if not converter:
            raise ValueError("DWG requiere el conversor dwg2dxf (LibreDWG). Exporta el plano como DXF ASCII, PDF o PNG para continuar; no se interpretó el DWG.")
        with tempfile.TemporaryDirectory(prefix="aerotrack-cad-") as directory:
            source=Path(directory)/"plan.dwg"
            target=Path(directory)/"plan.dxf"
            source.write_bytes(data)
            subprocess.run([converter,"-o",str(target),str(source)],check=True,capture_output=True,timeout=40,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            return dxf_geometry(target.read_bytes(),width)
    if suffix==".dxf":
        return dxf_geometry(data,width)
    if suffix==".pdf":
        data=raster_pdf(data,page)
    elif suffix not in (".png",".jpg",".jpeg",".webp"):
        raise ValueError("Formatos: PNG, JPG, WebP, PDF, DXF ASCII o DWG con conversor.")
    from PIL import Image,ImageOps
    try:
        image=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        image.thumbnail((LADO_MAXIMO,LADO_MAXIMO),Image.LANCZOS)
        output,mime=io.BytesIO(),"image/webp"
        try:
            image.save(output,format="WEBP",quality=82,method=4)
        except Exception:
            # Sin soporte de WebP en esta instalacion de Pillow: no se impide importar.
            output,mime=io.BytesIO(),"image/jpeg"
            image.save(output,format="JPEG",quality=88)
    except Exception as exc:
        raise ValueError("La imagen del plano no se pudo interpretar.") from exc
    return {"background":f"data:{mime};base64,"+base64.b64encode(output.getvalue()).decode(),"width":width,"height":max(1,min(10000,width*image.height/image.width)),"zones":[],"warnings":["Plano importado como imagen sin procesar. Recorta la zona util y genera las lineas del plano antes de calibrar."]}


def solo_estructuras(rgb, area_min=.0004, suavizado=.006):
    """Contorno de lo construido, descartando lo que no es estructura fija.

    En un plano de conjunto a color lo edificado se dibuja como volumen relleno,
    mas oscuro que el fondo y de tono frio, mientras que la vegetacion es verde y
    las vias y estacionamientos son casi blancos. Medido sobre un plano de campus
    real: fondo luminancia 246, vias 240-252, cesped y arboles 213 con verde
    dominante, y los edificios entre 159 y 209 con azul >= verde. Con esas dos
    condiciones se separa el volumen construido, y de ahi sale su contorno.

    Es preferible a detectar bordes porque devuelve la huella del edificio, que
    es una estructura fija, en vez de cualquier borde de la imagen: arboles,
    lineas de estacionamiento, rotulos o sombras. Sobre un plano CAD en blanco y
    negro no hay volumenes rellenos y no encuentra nada; por eso quien llama
    vuelve al metodo de bordes en ese caso.
    """
    import cv2
    import numpy as np
    alto, ancho = rgb.shape[:2]
    r, g, b = (rgb[:, :, i].astype(np.int16) for i in range(3))
    lum = (.299 * r + .587 * g + .114 * b).astype(np.int16)
    # mas oscuro que el fondo, mas claro que un rotulo negro, y de tono frio
    mask = (((lum < 230) & (lum > 55) & (b >= g)).astype(np.uint8)) * 255
    # abrir quita textos y trazos finos; cerrar consolida el interior del volumen
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    hallados, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total = float(alto * ancho)
    segmentos = []
    for contorno in hallados:
        if cv2.contourArea(contorno) / total < area_min:
            continue
        poly = cv2.approxPolyDP(contorno, suavizado * cv2.arcLength(contorno, True), True).reshape(-1, 2)
        if len(poly) < 3:
            continue
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            segmentos.append([int(x1), int(y1), int(x2), int(y2)])
    return segmentos


def raster_to_lines(image, target_width, modo="estructuras"):
    """Reduce a raster floor-plan photo/scan to a schematic line drawing via
    edge detection, instead of embedding the original photo (which carries
    titleblocks, tables and scanning noise that don't belong on a live
    tracking map). This approximates walls/borders as line segments; it is
    not semantic vectorization and will also pick up text or hatching --
    crop to the useful area first to keep it clean."""
    import cv2
    import numpy as np
    from PIL import Image as PILImage, ImageDraw
    rgb = np.array(image)
    long_side = max(image.width, image.height)
    estructural = modo == "estructuras"
    segments = None
    aviso_modo = None
    if estructural:
        recortes = solo_estructuras(rgb)
        if recortes:
            segments = [[s] for s in recortes]
            aviso_modo = ("Se trazo solo el volumen construido: se dejaron fuera vegetacion, vias, "
                          "estacionamientos y rotulos. Comprueba que no falte ninguna estructura.")
        else:
            # Un plano CAD en blanco y negro no tiene volumenes rellenos que separar.
            aviso_modo = ("No se distinguieron volumenes construidos por color, asi que se trazaron "
                          "los bordes de la imagen. Revisa y borra lo que no sea estructura.")
    if segments is None:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        gray = cv2.bilateralFilter(gray, 5, 40, 40)
        edges = cv2.Canny(gray, 40, 130)
        edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        segments = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=35,
                                    minLineLength=max(6, long_side * .015), maxLineGap=long_side * .006)
    height = max(1, min(10000, target_width * image.height / image.width))
    canvas_w = 1600
    canvas_h = max(1, round(canvas_w * image.height / image.width))
    if canvas_h > 5000:
        raise ValueError("La proporción del plano excede el tamaño permitido.")
    canvas = PILImage.new("RGB", (canvas_w, canvas_h), "#000000")
    draw = ImageDraw.Draw(canvas)
    scale_x, scale_y = canvas_w / image.width, canvas_h / image.height
    found = 0
    vectors = []
    if segments is not None:
        for line in segments[:6000]:
            x1, y1, x2, y2 = line[0]
            draw.line([(x1 * scale_x, y1 * scale_y), (x2 * scale_x, y2 * scale_y)], fill="#ffffff", width=2)
            vectors.append([float(x1)/image.width,float(y1)/image.height,float(x2)/image.width,float(y2)/image.height])
            found += 1
    output = io.BytesIO()
    canvas.save(output, format="JPEG", quality=88)
    warnings = ["Plano generado a partir de la imagen importada: aproxima muros y limites visibles, no reemplaza un plano CAD real. Revisa y ajusta contra el espacio antes de calibrar camaras."]
    if aviso_modo:
        warnings.append(aviso_modo)
    if not found:
        warnings.append("No se detectaron bordes claros en la imagen; el plano quedo en blanco. Prueba con mas contraste o recorta una zona con lineas mas definidas.")
    return {"background": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode(),
            "width": target_width, "height": round(height, 5), "zones": [], "planLines": vectors, "warnings": warnings}


def plan_lines_from_bytes(data, target_width, modo="estructuras"):
    from PIL import Image, ImageOps
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as exc:
        raise ValueError("La imagen recortada no se pudo interpretar.") from exc
    return raster_to_lines(image, target_width, modo)


if __name__=="__main__" and len(sys.argv)>2 and sys.argv[1]=="pdf":
    sys.stdout.buffer.write(_pdf_png(sys.stdin.buffer.read(),int(sys.argv[2])))
