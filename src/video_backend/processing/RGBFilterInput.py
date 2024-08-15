from enum import Enum
from functools import cache, partial
from typing import Optional
import cv2
import numpy as np

# Current implementation is limited with two ColorSpace types


class RGBFilterInput:
    class ColorSpace(Enum):
        RGB: int = 0
        BGR: int = 1

        @classmethod
        @cache
        def get_conversion_param(self, input_colorspace, output_colorspace):
            # {input: {output: cv2.COLOR_..., ..}, ..}
            conv_lookup_tbl = {
                self.RGB: {
                    self.BGR: cv2.COLOR_RGB2BGR
                },
                self.BGR: {
                    self.RGB: cv2.COLOR_BGR2RGB
                }
            }

            if output_colorspace == input_colorspace:
                raise ValueError('Color-spaces are identical')

            return conv_lookup_tbl[input_colorspace][output_colorspace]

    @property
    def width(self) -> int:
        return self._width
    
    @property
    def height(self) -> int:
        return self._height

    # is_mutable <- has single or more children? cannot return ndarr as a mutable if multiple children is consuming it
    def __init__(self,
                 input: np.ndarray,
                 is_mutable: bool,
                 input_color_space: ColorSpace = None) -> None:
        # No check for perf. reasons
        self._input_color_space = RGBFilterInput.ColorSpace.RGB
        
        self.configure(input, is_mutable, input_color_space)
        
        self._last_operation_immutable = None
        self._width = input.shape[1]
        self._height = input.shape[0]

    @property
    def is_mutable(self) -> bool:
        return self._is_mutable

    @property
    def input_color_space(self) -> ColorSpace:
        return self._input_color_space

    def configure(self,
                    input: np.ndarray = None,
                    is_mutable: bool = None,
                    input_color_space: ColorSpace = None) -> None:
        sget = lambda prop_name: getattr(self, prop_name, None)
        
        if input is not None:
            self._input = input
        else:
            self._input = sget('_input')
        
        self._is_mutable = is_mutable or sget('_is_mutable')
        self._input_color_space = input_color_space or sget('_input_color_space')
        
        self._input_converted = None or sget('_input_converted')
        
        self._input.flags.writeable = not is_mutable

    # Current consumer will modify the content
    def get_as_mutable_input(self, target_color_space: ColorSpace = None):
        out_color_space = target_color_space or self._input_color_space

        self._last_operation_immutable = False

        return self._output_image(out_color_space, not self.is_mutable)

    # Current consumer MUST NOT modify the content
    def get_as_immutable_input(self, target_color_space: ColorSpace = None):
        out_color_space = target_color_space or self._input_color_space

        self._last_operation_immutable = True

        return self._output_image(out_color_space, False)

    def is_same_images(self,
                           input_img: np.ndarray = None,
                           input_img_color_space: ColorSpace = None):
        img_color_space = input_img_color_space or self._input_color_space
        
        if self._input_color_space != img_color_space:
            return self._input_converted is input_img
        
        return self._input is input_img

    ## When to use??
    # None - no operation yet
    # True / False
    def was_last_operation_mutable(self):
        return self._last_operation_immutable

    def _output_image(self, out_color_space: ColorSpace, copy_img: bool):
        if self._input_color_space != out_color_space:
            # input & output color-space is different
            
            if self._input_converted is None:
                self._create_conversion(out_color_space)

            if copy_img:
                return np.copy(self._input_converted)
            return self._input_converted

        # the two color-spaces are identical
        
        if copy_img:
            return np.copy(self._input)

        return self._input

    def _create_conversion(self, out_color_space: ColorSpace):
        conversion = RGBFilterInput.ColorSpace.get_conversion_param(
                self._input_color_space,
                out_color_space
            )

        self._input_converted = cv2.cvtColor(self._input, conversion)

    @classmethod
    def clone(self, filter_input):
        assert isinstance(filter_input, RGBFilterInput)

        return RGBFilterInput(
            filter_input._input,
            filter_input._is_mutable,
            filter_input._input_color_space
        )
