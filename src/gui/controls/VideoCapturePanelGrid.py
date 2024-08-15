from typing import Callable, Dict, Tuple, List, Optional
from functools import cached_property
from abc import ABC, abstractmethod

import wx
import cv2
import numpy as np
from operator import xor



from IFrameProcessAdapter import IFrameProcessAdapter

VideoPanelPosition = int

# 4 pos grid at most currently
class VideoCapturePanelGrid(wx.GridSizer):
    
    class SinglePanel(wx.Panel):
        
        @property
        def started(self) -> bool:
            return self._started
        
        @property
        def adapter(self) -> IFrameProcessAdapter:
            return self._adapter
        
        def __init__(self,
                     adapter: IFrameProcessAdapter,
                     trigger,
                     *args,
                     **kw):
            super().__init__(*args, **kw)
            
            assert isinstance(adapter, IFrameProcessAdapter)
            assert isinstance(trigger, IFrameProcessAdapter.TriggerStreaming)
            
            self._adapter = adapter
            self._trigger = trigger
            
            self._trigger.drawing_callback = self._prepare_draw_image
            self._trigger.set_new_owner(self)
            
            self._started = False
            self._bmp = None # None = no EVT_PAINT binding
        
        def set_buffer_size(self, buffer_shape: Tuple):
            self._bmp = wx.Bitmap(*buffer_shape)
        
        def start_streaming(self):
            if self._started:
                return
            self._started = True
            self._trigger.start_streaming()
        
        def stop_streaming(self):
            if not self._started:
                return
            self._started = False
            self._trigger.stop_streaming()
        
        def _on_paint(self, evt: wx.PaintEvent) -> None:
            dc = wx.BufferedPaintDC(self)
            
            dc.DrawBitmap(self._bmp, 0, 0)
        
        def _prepare_draw_image(self, img: np.ndarray):
            bmp_exists = self._bmp is not None
            self.set_buffer_size((self._adapter.height, self._adapter.width))
            
            if not bmp_exists:
                self.Bind(wx.EVT_PAINT, self._on_paint)
            
            self._draw_image(img)
            self._trigger.drawing_callback = self._draw_image
        
        def _draw_image(self, img: np.ndarray):
            self._bmp.CopyFromBuffer(img)
            self.Refresh()
        
        def dispose(self):
            if self._bmp is not None:
                # not guaranteed to exists in a small amount of interval
                # (before setting trigger drawing callback from _prepare_draw_image to _draw_image)
                self._bmp.Destroy()
        
                
    def __init__(self, parent: wx.Window, rows=2, cols=2):
        super().__init__(rows=rows, cols=cols, hgap=5, vgap=5)
        
        self._parent = parent
        self._panel = wx.Panel(parent)
        
        self._rows = rows
        self._cols = cols
        
        # self.Add(self._wait_panel, 1, wx.ALL|wx.EXPAND, 5)
        # self._wait_panel.Start()
        
        self._panels: Dict[wx.Window] = {}
        self._panels_max = 4
        
        self._adapter_list = [None for i in range(self._panels_max)]
        
        self._indicator_list = [None for i in range(self._panels_max)]
        self._adapter_listeners = {}
        
        self._allocate_wait_panels()
        
        
        #self.SetMinClientSize(video_size)
        #self.Layout()
        
        # # self.Bind(wx.EVT_PAINT, self._on_paint)
        # # self.Bind(wx.EVT_TIMER, self._on_next_frame)
        
        # # self._timer = wx.Timer(self)
        
        #self._timer.Start(1000./fps)
    
    def initiate_video_panel(self,
                        adapter: IFrameProcessAdapter,
                        force_pos: Optional[VideoPanelPosition] = None,
                        overwrite_existing_pos: bool = False,
                        show_activity: bool = True) -> VideoPanelPosition:
        assert isinstance(adapter, IFrameProcessAdapter)
        
        if force_pos is not None:
            item_exists = self._adapter_list[force_pos] is not None
            if not overwrite_existing_pos and item_exists:
                raise ValueError(f"Has video panel on position {force_pos} but overwrite is not allowed")
            
            pos = force_pos
        else:
            search_available = (i for i,adapter in enumerate(self._adapter_list) if adapter is None)
            first_available = next(search_available, None)
            
            if first_available is None:
                raise RuntimeError('No empty slot available')
            
            pos = first_available
        
        self._adapter_list[pos] = adapter
        
        if show_activity:
            if isinstance(self._indicator_list[pos], wx.ActivityIndicator):
                self._indicator_list[pos].Start()
        
        return pos
    
    # no IndexError supression
    def activate_video_panel(self,
                          pos: VideoPanelPosition,
                          trigger: IFrameProcessAdapter.TriggerStreaming
                          ) -> SinglePanel:
        assert isinstance(trigger, IFrameProcessAdapter.TriggerStreaming)
        
        adapter = self._adapter_list[pos]
        assert isinstance(adapter, IFrameProcessAdapter)
        
        # One listener per adapter! Have no practical use of multiple listeners
        assert adapter not in self._adapter_listeners
        
        # Store panel
        adapter.panel = VideoCapturePanelGrid.SinglePanel(adapter, trigger, parent=self._parent)
        
        
        # def replace_panel(change: PropertyChanged):
        #     panel = adapter.panel
            
        #     # Check if adapter still the same
        #     if adapter != self._adapter_list[pos]:
        #         # destroy this listener indepentent of property value
        #         trigger.notifier.del_change_listener(
        #             trigger.streaming_notifier_property,
        #             replace_panel
        #         )
            
        #     if change.prop_new_value:
        #         self._set_panel(pos, panel)
        #     else:
        #         self._unset_panel(pos)
            
        #     self._parent.Layout()
        
        # topic = trigger.streaming_notifier_property
        # trigger.notifier.on_change_listener(topic, replace_panel)
        
        # self._adapter_listeners[adapter] = (trigger.notifier, replace_panel, topic)
        
        self._set_panel(pos, adapter.panel)
        return adapter.panel

    
    # does not catch builtin ValueError or IndexError
    def deactivate_video_panel(self, pos: VideoPanelPosition):
        adapter: IFrameProcessAdapter = self._adapter_list[pos]
        adapter.backend__input__cleanup()
        
        assert isinstance(adapter, IFrameProcessAdapter)
        panel: VideoCapturePanelGrid.SinglePanel = adapter.panel
        panel.stop_streaming()
        
        self._adapter_list[pos] = None
        
        self._unset_panel(pos)
        
        # notifier, cb, property_id = self._adapter_listeners[adapter]
        
        # parameters = PropertyChangeNotifier.TriggerParameters(
        #     {
        #         property_id: False
        #     },
        #     None
        # )
        # notifier.trigger_change(parameters)
        # notifier.del_change_listener(property_id, cb)
    
    
    # no restriction on how many times can call this
    def _allocate_wait_panels(self):
        def new_indicator() -> wx.ActivityIndicator:
            indicator = wx.ActivityIndicator(self._parent)
            
            # TODO: proper sizing
            min_width, min_height = indicator.GetMinWidth(), indicator.GetMinHeight()
            
            if min_width < 300:
                min_width = 300
            indicator.SetMinSize((min_width, min_height))
            
            self.Add(indicator, flag=wx.ALL|wx.EXPAND)
            self.Fit(indicator)
            return indicator
        
        self._indicator_list = [new_indicator() for _ in range(self._panels_max)]
        
        self.Layout()
    
    # return old indicator
    def _set_panel(self, index: int, panel: SinglePanel):
        indicator = self._indicator_list[index]
        
        assert isinstance(indicator, wx.ActivityIndicator)
        assert self.Replace(indicator, panel)
        self.Fit(panel)
        self.Layout()
        
        indicator.Stop()
        
        self._indicator_list[index] = panel
        
        return indicator
    
    # return detached panel
    def _unset_panel(self, index: int):
        panel = self._indicator_list[index]
        panel.dispose()
        
        indicator = self._indicator_list[index] = wx.ActivityIndicator(self._parent)
        
        assert self.Replace(panel, indicator)
        panel.Destroy()
        
        self.Fit(indicator)
        self.Layout()
        
        indicator.Start()
        
        return panel
    
    