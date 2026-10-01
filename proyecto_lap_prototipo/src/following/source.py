"""Adaptador de recepción reciente para cámaras IP, compartido con conteo."""
import cv2
from counting.source import VideoSource


class NetworkCapture:
    def __init__(self, source, root):
        self.source = VideoSource(source, root)

    def isOpened(self):
        return True

    def get(self, property_id):
        return self.source.fps if property_id == cv2.CAP_PROP_FPS else 0

    def set(self, *_):
        return False

    def read(self):
        frame, _ = self.source.read()
        return frame is not None, frame

    def release(self):
        return self.source.close()

    def request_stop(self):
        self.source.request_stop()

    def is_alive(self):
        return self.source.is_alive()
