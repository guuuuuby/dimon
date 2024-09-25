import mss
from PIL import Image
import io


def capture_screen(monitor_number=1):
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_number]
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        return img
    

def encode_frame(image, quality=50):
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=quality)
    return buffer.getvalue()
