import numpy as np
import cv2
from typing import Optional

from .register_bgr_transform import bgr_transform

from .RGBFilterInput import RGBFilterInput

@bgr_transform
def preview(input: RGBFilterInput, width: int, height: int, is_recording: Optional[bool] = None):
    w, h = int(width), int(height)
    
    img = input.get_as_immutable_input()
    img = cv2.resize(img, (w,h))
    
    if is_recording is not None:
        frame_color = (255, 0, 0) if is_recording else (0, 255, 0)
        #img = cv2.line(img, (0,1), (w,1), (255,0,0), 3)
        pts = np.array([[1, 1], [w-1, 1], [w-1, h-1], [1, h-1]], np.int32).reshape((-1, 1, 2))
        img = cv2.polylines(img, [pts], True, frame_color, 3)
    
    return img