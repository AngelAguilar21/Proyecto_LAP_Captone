"""Firma visual ligera para asociaciones entre cámaras; no es ReID biométrico."""
import cv2
import numpy as np


def _histogram(image, space, channels, bins, ranges):
    converted = cv2.cvtColor(image, space)
    histogram = cv2.calcHist([converted], channels, None, bins, ranges)
    return cv2.normalize(histogram, histogram, alpha=1, norm_type=cv2.NORM_L1).reshape(-1)


def torso_histogram(frame, box):
    """Describe ropa superior e inferior con color, sin rostro ni biometría.

    Separar el cuerpo en dos franjas reduce confusiones entre personas con una
    prenda parecida. Se combinan HSV y Lab para tolerar mejor cambios de luz
    entre cámaras, con un costo pequeño frente a la inferencia del detector.
    """
    if box is None:
        return None
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    body_width = x2 - x1
    left = max(0, int(x1 + body_width * .12))
    right = min(width, int(x2 - body_width * .12))
    top = max(0, int(y1 + (y2 - y1) * .24))
    bottom = min(height, int(y1 + (y2 - y1) * .82))
    roi = frame[top:bottom, left:right]
    if roi.size == 0 or roi.shape[0] < 4 or roi.shape[1] < 3:
        return None

    middle = max(2, roi.shape[0] // 2)
    regions = (roi[:middle], roi[middle:])
    descriptors = []
    for region in regions:
        if region.size == 0:
            region = roi
        descriptors.append(_histogram(region, cv2.COLOR_BGR2HSV, [0, 1], [12, 6], [0, 180, 0, 256]))
        descriptors.append(_histogram(region, cv2.COLOR_BGR2LAB, [1, 2], [6, 6], [0, 256, 0, 256]))
    signature = np.concatenate(descriptors).astype(np.float32).reshape(-1, 1)
    return cv2.normalize(signature, signature, alpha=1, norm_type=cv2.NORM_L1)
