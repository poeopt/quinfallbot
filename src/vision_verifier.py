import cv2
import pytesseract
import numpy as np

class VisionVerifier:
    def __init__(self, tesseract_cmd=None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def verify_resource_on_screen(self, frame, resource_name="Ore"):
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Simple thresholding
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # OCR
        text = pytesseract.image_to_string(thresh)

        return resource_name.lower() in text.lower()

    def find_minimap_marker(self, minimap_frame, marker_color_hsv_range):
        # Find specific color on minimap (e.g., yellow for resources)
        hsv = cv2.cvtColor(minimap_frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, marker_color_hsv_range[0], marker_color_hsv_range[1])

        coords = cv2.findNonZero(mask)
        if coords is not None:
            # Return average position
            avg = np.mean(coords, axis=0)
            return (int(avg[0][0]), int(avg[0][1]))
        return None
