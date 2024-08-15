from typing import Callable, Any
import wx

from gui.frames.windows.AppWindowDescription import InputSetupFrame

from videorotate_utils import abs_path

TestCallback = Callable[[bool], Any]

class InputSetupFrameView(InputSetupFrame):
    # TODO: move into a shared class
    def toggle_info(self, evt):
        self.infoText.Show(not self.infoText.IsShown())
        self.Layout()

        evt.Skip()
    
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        
        info_btn_id = self.infoTextBtn.GetId()
        self.Bind(wx.EVT_TOOL, self.toggle_info, id=info_btn_id)
        
        # icon = wx.EmptyIcon()
        # icon.CopyFromBitmap(wx.Bitmap(abs_path('logo.ico'), wx.BITMAP_TYPE_ANY))
        # self.SetIcon(icon)
    
    def add_listener_driver(self,
                            display_name: str,
                            test_callback: TestCallback):
        pass