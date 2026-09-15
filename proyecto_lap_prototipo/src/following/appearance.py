"""Descriptor económico del torso para apoyar asociaciones; no es ReID neuronal."""
import cv2


def torso_histogram(frame, box):
    if box is None:
        return None
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    roi = frame[max(0, int(y1+(y2-y1)*.25)):min(height, int(y1+(y2-y1)*.7)),
                max(0, int(x1)):min(width, int(x2))]
    if not roi.size:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    return cv2.normalize(hist, hist, alpha=1, norm_type=cv2.NORM_L1)
