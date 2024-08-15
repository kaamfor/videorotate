import dataclasses
from dataclasses import dataclass
from typing import List, Callable, Optional, Any
import cv2

import os
import wx
import reactivex

from IFrameProcessAdapter import IFrameProcessAdapter, DrawingCallback


from gui.frames.windows.AppWindowDescription import MainWindow

from gui.controls.VideoCapturePanelGrid import VideoCapturePanelGrid

import video_backend.rgb_task as rgb_task
from video_backend.consumer import RGBSharedMemoryAdapter

@dataclass
class PlaybackControl:
    video_canvas: wx.Panel
    file_text_ctrl: wx.StaticText
    play_button: wx.BitmapButton
    slider: wx.Slider
    
    MIN_STEP = 200
    
    def start(self, filepath: str):
        self.destroy()
        self._frame_count = 0
        
        self.file_text_ctrl.SetLabel(' '.join([self._file_status_prefix, filepath]))
        self.play_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_MINUS, wx.ART_BUTTON))
        
        self._playback = cv2.VideoCapture(filepath)
        self._fps = int(self._playback.get(cv2.CAP_PROP_FPS))
        
        video_duration = int(self._playback.get(cv2.CAP_PROP_FRAME_COUNT)) / self._fps
        self._step_per_frame = 1
        
        self.slider.SetValue(0)
        self.slider.SetMax(int(video_duration))
        
        if video_duration < self.MIN_STEP:
            self._step_per_frame = self.MIN_STEP / (video_duration * self._fps)
            self.slider.SetMax(self.MIN_STEP)
        
        
        self._timer.Start(1000 // self._fps)
        
        if self._bmp is not None:
            self._bmp.Destroy()
        self._bmp = wx.Bitmap(*self.video_canvas.GetClientSize())
        
        self._last_filepath = filepath
    
    def destroy(self):
        if self._playback is not None:
            self._playback.release()
            self._playback = None
        
        if self._timer is not None:
            self._timer.Stop()
        
        self.play_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_FORWARD, wx.ART_BUTTON))
    
    def _get_image(self, evt):
        if self._playback.isOpened():
            ret, frame = self._playback.read()
        if not ret:
            self.destroy()
            self.slider.SetValue(self.slider.GetMax())
            return

        img = cv2.resize(frame, self.video_canvas.GetClientSize())
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        self._bmp.CopyFromBuffer(img)
        self.video_canvas.Refresh()
        
        self._frame_count += self._step_per_frame
        
        if self._step_per_frame == 1:
            cursor = self._frame_count // self._fps
        else:
            cursor = int(self._frame_count)
        self.slider.SetValue(cursor)
    
    def _draw_image(self, evt: wx.PaintEvent) -> None:
        dc = wx.BufferedPaintDC(self.video_canvas)

        dc.DrawBitmap(self._bmp, 0, 0)
    
    def _resize_event(self, evt):
        if self._bmp is not None:
            self._bmp.Destroy()
        
        self._bmp = wx.Bitmap(*self.video_canvas.GetClientSize())
    
    def _toggle_button(self, evt):
        if self._last_filepath is None:
            return
        
        if self._playback is None:
            self.start(self._last_filepath)
            return
        
        if self._timer.IsRunning():
            self._timer.Stop()
            self.play_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_FORWARD, wx.ART_BUTTON))
        else:
            self._timer.Start(1000 // self._fps)
            self.play_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_MINUS, wx.ART_BUTTON))
    
    def __post_init__(self):
        self._playback = None
        self._timer = None
        self._bmp = None
        
        self._fps = 0
        self._step_per_frame = 0
        
        self._frame_count = 0
        
        self._file_status_prefix = str(self.file_text_ctrl.GetLabel()).strip()
        
        self._timer = wx.Timer(self.video_canvas)
        self.video_canvas.Bind(wx.EVT_TIMER, self._get_image)
        
        self.video_canvas.Bind(wx.EVT_SIZE, self._resize_event)
        self.play_button.Bind(wx.EVT_BUTTON, self._toggle_button)
        
        self._bmp = wx.Bitmap(1, 1)
        self.video_canvas.Bind(wx.EVT_PAINT, self._draw_image)
        
        self._last_filepath = None
    
    def __del__(self):
        self._timer.Unbind(wx.EVT_TIMER, handler=self._get_image)
        self.video_canvas.Unbind(wx.EVT_SIZE, handler=self._resize_event)
        
        self.video_canvas.Unbind(wx.EVT_PAINT, handler=self._draw_image)

class MainWindowView(MainWindow):
    class StreamTrigger(IFrameProcessAdapter.TriggerStreaming):
        
        @property
        def started(self) -> bool:
            return self._started
        
        @property
        def drawing_callback(self) -> DrawingCallback:
            return self._drawing_cb
        
        @drawing_callback.setter
        def drawing_callback(self, callback: DrawingCallback):
            #assert isinstance(callback, DrawingCallback)
            assert isinstance(callable, Callable)
            
            self._drawing_cb = callback
        
        def __init__(self,
                     parent_window: wx.Window,
                     adapter: IFrameProcessAdapter,
                     frame_interval_ms: int,
                     tick_threshold: int) -> None:
            super().__init__()
            
            self._adapter = adapter
            self._parent_window = parent_window
            self._frame_interval_ms = frame_interval_ms
            self._drawing_cb = None
            self._started = False
            
            self._tick = 0
            self._tick_threshold = tick_threshold
            
            # self.notifier.on_change_listener(
            #     self.streaming_notifier_property,
            #     self._handle_streaming_property
            #     )
            
            self._new_stream_dialog = reactivex.empty()
            #self.AddRTSPCameraBtn
        
        def on_new_stream_dialog(self) -> reactivex.Observable:
            return self._new_stream_dialog
        
        def start_streaming(self):
            if not self._started:
                self._timer = wx.Timer(self.timer_owner)
                self.timer_owner.Bind(wx.EVT_TIMER, self._timer_run_cycle)
                self._timer.Start(self._frame_interval_ms)
                self._started = True
            
        
        def stop_streaming(self):
            if self._started:
                self._started = False
                self._timer.Stop()
                self.timer_owner.Unbind(wx.EVT_TIMER, handler=self._timer_run_cycle)
                
                self.set_new_owner(self.pending_owner)
        
        # return boolean: - did threshold reached?
        def _timer_run_cycle(self, evt: wx.TimerEvent) -> bool:
            ready, img, _ = self._adapter.backend__input__grab_frame()
            
            if ready:
                self._drawing_cb(img)
                self._tick_threshold = 0
                
                self._parent_window.Refresh()
                return True
            
            return self._tick < self._tick_threshold
        
        def _handle_streaming_property(self, change):
            if change.prop_new_value:
                self.start_streaming()
            else:
                self.stop_streaming()
    
    # TODO: move into a shared class
    def toggle_info(self, evt):
        self.infoText.Show(not self.infoText.IsShown())
        self.Layout()
        
        evt.Skip()
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self._timer = wx.Timer(self)
        self._timer_interval = None
        self._timer_old_callback = None
        
        # self.Bind(wx.EVT_TIMER, self.run_timer_cycle)
        
        self._streams = {}
        self._prepare_streams = {}
        
        self._video_slots = {}
        self._video_slots_size = {}
        
        self._panel_pos = {}
        
        info_btn_id = self.infoTextBtn.GetId()
        self.Bind(wx.EVT_TOOL, self.toggle_info, id=info_btn_id)
        self.infoText.Show(False)
        self.Layout()
        
        #self.videoCapturePanelGrid.SetSizeHints(self)
        self.set_activity(None)
        
        self.playback_control = PlaybackControl(
            self.playbackVideoCanvas,
            self.playbackVideoCurrentFile,
            self.playbackVideoPlayBtn,
            self.playbackVideoSlider
        )
        self.RecordsListBox.Bind(wx.EVT_LISTBOX_DCLICK, self._on_start_playback)

    def _on_start_playback(self, evt):
        # TODO: set according to panel, not index
        self.mainNotebook.SetSelection(1)
        
        selected_i = self.RecordsListBox.GetSelection()
        if selected_i != wx.NOT_FOUND:
            self.playback_control.start(self.RecordsListBox.GetClientData(selected_i))
    
    def add_streaming_video(self,
                            shmem_img: rgb_task.RGBSharedMemoryImage
                            ) -> VideoCapturePanelGrid.SinglePanel:
        adapter = RGBSharedMemoryAdapter(shmem_img)
        adapter.backend__input__setup()
        
        real_pos = self.videoCapturePanelGrid.initiate_video_panel(adapter)
        # self._video_adapters[real_pos] = adapter
        
        trigger = self.StreamTrigger(self, adapter, 1000 // 15, 15)
        panel = self.videoCapturePanelGrid.activate_video_panel(real_pos, trigger)
        panel.start_streaming()
        
        self._panel_pos[panel] = real_pos
        
        return panel
    
    # def free_video_panel(self, adapter: IFrameProcessAdapter) -> VideoCapturePanelGrid:
    #     # Exception not caught
    #     return self._streams.pop(adapter)
    
    def free_video_panel(self, panel: VideoCapturePanelGrid.SinglePanel):
        self.videoCapturePanelGrid.deactivate_video_panel(self._panel_pos[panel])

    
    # def run_timer_cycle(self, timer_evt: wx.TimerEvent):
    #     for adapter, panel in dict(self._streams).items():
            
    
    def run_extended_timer_cycle(self, a):
        # - Preparing new streams happen after updating existing
        #  so image update not happen twice
        # - Clone dict so we can manipulate freely
        for adapter, panel in dict(self._prepare_streams).items():
            if self._prepare_stream(adapter, panel):
                
                del self._prepare_stream[adapter]
                self._streams[adapter] = panel
    
    def _prepare_stream(self, adapter: IFrameProcessAdapter):
        
        ok, img, _ = adapter.backend__input__grab_frame()
        
        self.start_timer()
        
        if ok:
            panel_pos = self.videoCapturePanelGrid.initiate_video_panel(adapter)
            self.Layout()
            self.videoCapturePanelGrid.activate_video_panel(panel_pos)
            panel_pos.set_buffer_size((self._adapter.height, self._adapter.width))
            self.videoCapturePanelGrid.draw_image(img)
            self.Refresh()
            
            # setup done, bind runtime function
            self.Unbind(wx.EVT_TIMER)
            self.Bind(wx.EVT_TIMER, self.stream_video)
            self._timer.Start(1000//15)
        else:
            # repeat setup process (this function)
            self._timer.StartOnce(1000//15)
    
    # interval is the last known value if not given, raise ValueError when such value not exists
    def start_timer(self, interval: Optional[int] = None):
        assert (interval or self._timer_interval) is not None
        self._timer_interval = int(interval or self._timer_interval)
        
        self._timer.Start(self._timer_interval)
    
    def stop_timer(self):
        self._timer.Stop()
    
    def _change_timer_callback(self, callback: Callable, start_after: bool = True):
        self.stop_timer()
        
        self.Unbind(wx.TimerEvent, self._timer_old_callback)
        self.Bind()
        ## splitterWindow?
        if start_after:
            self.start_timer()
    
    # max 4 streams this time
    # TODO: extend
    def _allocate_video_panel(self) -> VideoCapturePanelGrid:
        pass
    
    def on_stream_select(self, fn: Callable[[str], Any]):
        def selected(evt):
            selected_i = self.InputStreamsListBox.GetSelection()
            if selected_i != wx.NOT_FOUND:
                fn(self.InputStreamsListBox.GetString(selected_i))
        self.selectInputStream.Bind(wx.EVT_BUTTON, selected)
    
    def set_activity(self, msg: Optional[str]):
        if msg is None:
            self.globalLoadingActivity.Stop()
            self.globalLoadingActivityText.SetLabelText('')
        else:
            assert isinstance(msg, str)
            self.globalLoadingActivity.Start()
            self.globalLoadingActivityText.SetLabelText(msg)
    
    # call
    #def on_livepanel_resize(self, cb: Callable)
    
    #     self.imagesWildcard = "Image Files(*.BMP;*.JPG;*.GIF)|*.BMP;*.JPG;*.GIF|All files (*.*)|*.*"
        
    #     # Create Collection Tree rootnode
    #     colTree = self.projectCollectionTree
    #     colTreeRoot = self.projectCollectionTreeRoot = colTree.AddRoot("Projektek")
    #     colTree.SetItemData(colTreeRoot, None)
    
    def loadProjectDialog(self) -> Optional[List[str]]:
        with wx.FileDialog(
            #self, message="Betölteni kívánt projekt kiválasztása..",
            self,
            message="Select project file to open..",
            #defaultDir=os.getcwd(),
            defaultFile="",
            #wildcard=self.imagesWildcard,
            style=wx.FD_OPEN | #wx.FD_MULTIPLE |
                wx.FD_CHANGE_DIR | wx.FD_FILE_MUST_EXIST |
                wx.FD_PREVIEW
            ) as dlg:
            if dlg.ShowModal() == wx.ID_OK: # vs. wx.ID_CANCEL
                return dlg.GetPaths()
        return None
    
    def saveProjectDialog(self) -> Optional[List[str]]:
        with wx.FileDialog(
                self,
                message="Select project file to save..",
                # defaultDir=os.getcwd(),
                defaultFile="",
                #wildcard=self.imagesWildcard,
                style=wx.FD_SAVE | wx.FD_CHANGE_DIR | wx.FD_PREVIEW
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:  # vs. wx.ID_CANCEL
                return dlg.GetPaths()
        return None
    
    # def addSourceDirectoryDialog(self):
    #     with wx.DirDialog(
    #         self, message="Egy vagy több forrásmappa kiválasztása..",
    #         #defaultPath=os.getcwd()
    #         ) as dlg:
    #         if dlg.ShowModal() == wx.ID_OK: # vs. wx.ID_CANCEL
    #             return dlg.GetPath()
    #     return None

