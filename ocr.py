import easyocr
import numpy as np
import cv2
from PIL import Image
import io
reader = easyocr.Reader(['es', 'en'])

def read_image(image_bytes: bytes):
    # Convertir bytes a imagen de OpenCV
    image = Image.open(io.BytesIO(image_bytes))
    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # Leer texto con easyocr
    result = reader.readtext(image)
    parsed_result = []
    for box, text, conf in result:
        parsed_box = [[int(x), int(y)] for x, y in box]
        parsed_result.append({
            "text": text,
            "confidence": float(conf),
            "box": parsed_box
        })
    return parsed_result
