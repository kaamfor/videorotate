import numpy as np
import cv2

from .register_bgr_transform import bgr_transform

from .RGBFilterInput import RGBFilterInput

@bgr_transform
def bgr_stream_preview(input: RGBFilterInput):
    cv2.imshow('Test', input.get_as_immutable_input())
    cv2.waitKey(1)