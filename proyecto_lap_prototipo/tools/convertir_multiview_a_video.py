import cv2
import os

# Carpeta principal donde están las 6 carpetas de cámaras
carpeta_principal = r"C:\Users\Angel\Downloads\MultiviewX\MultiviewX\Image_subsets"

# Carpeta donde se guardarán los videos
carpeta_salida = r"C:\Users\Angel\Downloads\Multiview\Videos"

# Crear carpeta de salida si no existe
os.makedirs(carpeta_salida, exist_ok=True)

# FPS del video
fps = 5   # aumenta o disminuye la velocidad aquí

# Obtener las carpetas (C1, C2, C3...)
carpetas = sorted(os.listdir(carpeta_principal))


for carpeta in carpetas:

    ruta_carpeta = os.path.join(carpeta_principal, carpeta)

    # Verificar que sea una carpeta
    if not os.path.isdir(ruta_carpeta):
        continue

    print("Procesando:", carpeta)

    # Obtener imágenes
    imagenes = sorted([
        img for img in os.listdir(ruta_carpeta)
        if img.lower().endswith(('.jpg', '.png', '.jpeg'))
    ])

    if len(imagenes) == 0:
        print("No hay imágenes en", carpeta)
        continue


    # Leer primera imagen para tamaño
    primera = cv2.imread(os.path.join(ruta_carpeta, imagenes[0]))

    if primera is None:
        print("Error leyendo", imagenes[0])
        continue

    alto, ancho, _ = primera.shape


    # Nombre del video
    salida_video = os.path.join(
        carpeta_salida,
        carpeta + ".mp4"
    )


    # Crear video
    video = cv2.VideoWriter(
        salida_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (ancho, alto)
    )


    # Agregar frames
    for imagen in imagenes:

        ruta_imagen = os.path.join(ruta_carpeta, imagen)

        frame = cv2.imread(ruta_imagen)

        if frame is not None:
            video.write(frame)


    video.release()

    print("Video creado:", salida_video)


print("==== TODOS LOS VIDEOS TERMINADOS ====")