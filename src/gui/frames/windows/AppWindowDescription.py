# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 3.10.1-0-g8feb16b)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
from gui.controls.VideoCapturePanelGrid import VideoCapturePanelGrid
from gui.controls.wx_form import FormHolder

###########################################################################
## Class MainWindow
###########################################################################

class MainWindow ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"Videorotate", pos = wx.DefaultPosition, size = wx.Size( 820,576 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.Size( -1,-1 ), wx.DefaultSize )

		FrameVSizer = wx.BoxSizer( wx.VERTICAL )

		MainHeaderHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.tasksToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.loadProjectBtn = self.tasksToolbar.AddTool( wx.ID_ANY, u"Open Project", wx.ArtProvider.GetBitmap( wx.ART_FILE_OPEN, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, u"Save as startup project", u"Save as startup project", None )

		self.saveProjectBtn = self.tasksToolbar.AddTool( wx.ID_ANY, u"Save Project", wx.ArtProvider.GetBitmap( wx.ART_FILE_SAVE, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, u"Save as startup project", u"Save as startup project", None )

		self.AddRTSPCameraBtn = self.tasksToolbar.AddTool( wx.ID_ANY, u"tool", wx.ArtProvider.GetBitmap( wx.ART_PLUS, wx.ART_BUTTON ), wx.NullBitmap, wx.ITEM_NORMAL, u"Add RTSP Stream...", u"Add RTSP Stream...", None )

		self.tasksToolbar.Realize()

		MainHeaderHSizer.Add( self.tasksToolbar, 1, wx.EXPAND, 5 )

		self.infoToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.infoToolbar.AddSeparator()

		self.infoTextBtn = self.infoToolbar.AddTool( wx.ID_ANY, u"tool", wx.ArtProvider.GetBitmap( wx.ART_HELP_BOOK, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, wx.EmptyString, wx.EmptyString, None )

		self.infoToolbar.Realize()

		MainHeaderHSizer.Add( self.infoToolbar, 0, wx.EXPAND, 5 )


		FrameVSizer.Add( MainHeaderHSizer, 0, wx.EXPAND, 5 )

		MainContentHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.mainNotebook = wx.Notebook( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.mainLivePanel = wx.Panel( self.mainNotebook, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		mainLivePanelVSizer = wx.BoxSizer( wx.VERTICAL )

		self.videoCapturePanelGrid = VideoCapturePanelGrid(self.mainLivePanel)
		mainLivePanelVSizer.Add( self.videoCapturePanelGrid, 4, wx.ALL|wx.EXPAND, 5 )

		LivePanelStatusSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.globalLoadingActivity = wx.ActivityIndicator(self.mainLivePanel)
		LivePanelStatusSizer.Add( self.globalLoadingActivity, 0, wx.ALL, 5 )

		self.globalLoadingActivityText = wx.StaticText( self.mainLivePanel, wx.ID_ANY, u"..", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.globalLoadingActivityText.Wrap( -1 )

		LivePanelStatusSizer.Add( self.globalLoadingActivityText, 0, wx.ALIGN_CENTER_VERTICAL, 5 )


		mainLivePanelVSizer.Add( LivePanelStatusSizer, 0, wx.EXPAND, 5 )


		self.mainLivePanel.SetSizer( mainLivePanelVSizer )
		self.mainLivePanel.Layout()
		mainLivePanelVSizer.Fit( self.mainLivePanel )
		self.mainNotebook.AddPage( self.mainLivePanel, u"Live", True )
		self.mainPlaybackPanel = wx.Panel( self.mainNotebook, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		PlaybackPanelVSizer = wx.BoxSizer( wx.VERTICAL )

		self.playbackVideoCanvas = wx.Panel( self.mainPlaybackPanel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		PlaybackPanelVSizer.Add( self.playbackVideoCanvas, 1, wx.EXPAND |wx.ALL, 5 )

		self.playbackVideoCurrentFile = wx.StaticText( self.mainPlaybackPanel, wx.ID_ANY, u"Filename:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.playbackVideoCurrentFile.Wrap( -1 )

		PlaybackPanelVSizer.Add( self.playbackVideoCurrentFile, 0, wx.ALL|wx.EXPAND, 5 )

		PlaybackControlHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.playbackVideoPlayBtn = wx.BitmapButton( self.mainPlaybackPanel, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.DefaultSize, wx.BU_AUTODRAW|0 )

		self.playbackVideoPlayBtn.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_GO_FORWARD, wx.ART_BUTTON ) )
		PlaybackControlHSizer.Add( self.playbackVideoPlayBtn, 0, wx.ALL, 5 )

		self.playbackVideoSlider = wx.Slider( self.mainPlaybackPanel, wx.ID_ANY, 0, 0, 100, wx.DefaultPosition, wx.DefaultSize, wx.SL_HORIZONTAL )
		PlaybackControlHSizer.Add( self.playbackVideoSlider, 1, wx.ALL|wx.EXPAND, 5 )


		PlaybackPanelVSizer.Add( PlaybackControlHSizer, 0, wx.EXPAND, 5 )


		self.mainPlaybackPanel.SetSizer( PlaybackPanelVSizer )
		self.mainPlaybackPanel.Layout()
		PlaybackPanelVSizer.Fit( self.mainPlaybackPanel )
		self.mainNotebook.AddPage( self.mainPlaybackPanel, u"Playback", False )

		MainContentHSizer.Add( self.mainNotebook, 3, wx.EXPAND |wx.ALL, 5 )

		SidePanelVSizer = wx.BoxSizer( wx.VERTICAL )

		self.StreamPanelTitleText = wx.StaticText( self, wx.ID_ANY, u"Stream sources", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.StreamPanelTitleText.Wrap( -1 )

		SidePanelVSizer.Add( self.StreamPanelTitleText, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5 )

		InputStreamsListBoxChoices = []
		self.InputStreamsListBox = wx.ListBox( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, InputStreamsListBoxChoices, 0 )
		SidePanelVSizer.Add( self.InputStreamsListBox, 1, wx.ALL|wx.EXPAND, 5 )

		self.selectInputStream = wx.Button( self, wx.ID_ANY, u"Select", wx.DefaultPosition, wx.DefaultSize, 0 )
		SidePanelVSizer.Add( self.selectInputStream, 0, wx.ALL|wx.EXPAND, 5 )

		self.PlaybackPanelTitleText = wx.StaticText( self, wx.ID_ANY, u"Playback records", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.PlaybackPanelTitleText.Wrap( -1 )

		SidePanelVSizer.Add( self.PlaybackPanelTitleText, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5 )

		RecordsListBoxChoices = []
		self.RecordsListBox = wx.ListBox( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, RecordsListBoxChoices, 0 )
		SidePanelVSizer.Add( self.RecordsListBox, 1, wx.ALL|wx.EXPAND, 5 )


		MainContentHSizer.Add( SidePanelVSizer, 1, wx.ALL|wx.EXPAND, 5 )

		self.infoText = wx.StaticText( self, wx.ID_ANY, u"*Usage*\n\nAdding a new RTSP source,\nloading and saving projects\nare available with the toolbar's\nrelated elements.\nAfter the sources are added\nto the list, you can activate\none or more by selecting\nthe appropiate item and\nclicking the 'Select' button.\nIn the case of event-backed\nsource, the new recordings will\nappear in the bottom list,\nand by double-clicking\non one element,\nthe corresponding video\nwill start playing.", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.infoText.Wrap( -1 )

		self.infoText.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_INFOBK ) )

		MainContentHSizer.Add( self.infoText, 0, wx.ALL|wx.EXPAND, 5 )


		FrameVSizer.Add( MainContentHSizer, 1, wx.EXPAND, 5 )


		self.SetSizer( FrameVSizer )
		self.Layout()

		self.Centre( wx.BOTH )

	def __del__( self ):
		pass


###########################################################################
## Class InputSetupFrame
###########################################################################

class InputSetupFrame ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"RTSP Setup - Videorotate", pos = wx.DefaultPosition, size = wx.Size( -1,-1 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

		frameVSizer = wx.BoxSizer( wx.VERTICAL )

		InfoToolbarHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.SpacerToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.SpacerToolbar.Realize()

		InfoToolbarHSizer.Add( self.SpacerToolbar, 1, wx.EXPAND, 5 )

		self.infoToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.infoTextBtn = self.infoToolbar.AddTool( wx.ID_ANY, u"tool", wx.ArtProvider.GetBitmap( wx.ART_HELP_BOOK, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, wx.EmptyString, wx.EmptyString, None )

		self.infoToolbar.Realize()

		InfoToolbarHSizer.Add( self.infoToolbar, 0, wx.EXPAND, 5 )


		frameVSizer.Add( InfoToolbarHSizer, 0, wx.EXPAND, 5 )

		self.frameTitle = wx.StaticText( self, wx.ID_ANY, u"RTSP Input", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.frameTitle.Wrap( -1 )

		self.frameTitle.SetFont( wx.Font( 20, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, "Sans" ) )

		frameVSizer.Add( self.frameTitle, 0, 0, 5 )

		mainHSizer = wx.BoxSizer( wx.HORIZONTAL )


		mainHSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		bodyVSizer = wx.BoxSizer( wx.VERTICAL )

		HSizer113 = wx.BoxSizer( wx.HORIZONTAL )

		self.mStaticText813 = wx.StaticText( self, wx.ID_ANY, u"Name", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.mStaticText813.Wrap( -1 )

		HSizer113.Add( self.mStaticText813, 2, wx.ALIGN_CENTER|wx.ALL, 5 )

		self.streamNameTextCtrl = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		HSizer113.Add( self.streamNameTextCtrl, 3, wx.ALL, 5 )


		bodyVSizer.Add( HSizer113, 1, wx.EXPAND, 5 )

		self.sourceSetupFormHolder = FormHolder(self)
		bodyVSizer.Add( self.sourceSetupFormHolder.form, 0, wx.ALL|wx.EXPAND, 5 )

		HSizer11 = wx.BoxSizer( wx.HORIZONTAL )

		self.mStaticText81 = wx.StaticText( self, wx.ID_ANY, u"Recording type", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.mStaticText81.Wrap( -1 )

		HSizer11.Add( self.mStaticText81, 2, wx.ALIGN_CENTER|wx.ALL, 5 )

		recordingTypeChoiceChoices = [ u"Monitor (No recording)", u"Event trigger" ]
		self.recordingTypeChoice = wx.Choice( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, recordingTypeChoiceChoices, 0 )
		self.recordingTypeChoice.SetSelection( 0 )
		HSizer11.Add( self.recordingTypeChoice, 3, wx.ALL, 5 )


		bodyVSizer.Add( HSizer11, 0, wx.EXPAND, 5 )

		HSizer111 = wx.BoxSizer( wx.HORIZONTAL )

		self.mStaticText811 = wx.StaticText( self, wx.ID_ANY, u"Recording dir", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.mStaticText811.Wrap( -1 )

		HSizer111.Add( self.mStaticText811, 2, wx.ALIGN_CENTER|wx.ALL, 5 )

		self.recorderOutputDirCtrl = wx.DirPickerCtrl( self, wx.ID_ANY, u"/home/tger/Letöltések", u"Select a folder", wx.DefaultPosition, wx.DefaultSize, wx.DIRP_DEFAULT_STYLE )
		HSizer111.Add( self.recorderOutputDirCtrl, 3, wx.ALL, 5 )


		bodyVSizer.Add( HSizer111, 0, wx.EXPAND, 5 )

		HSizer112 = wx.BoxSizer( wx.HORIZONTAL )

		self.mStaticText812 = wx.StaticText( self, wx.ID_ANY, u"Event driver", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.mStaticText812.Wrap( -1 )

		HSizer112.Add( self.mStaticText812, 2, wx.ALIGN_CENTER|wx.ALL, 5 )

		bSizer26 = wx.BoxSizer( wx.VERTICAL )

		driverChoiceChoices = [ u"JSON receiver" ]
		self.driverChoice = wx.Choice( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, driverChoiceChoices, 0 )
		self.driverChoice.SetSelection( 0 )
		bSizer26.Add( self.driverChoice, 1, wx.ALL|wx.EXPAND, 5 )

		HSizer32 = wx.BoxSizer( wx.HORIZONTAL )


		HSizer32.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.configuredFlagTextLabel = wx.StaticText( self, wx.ID_ANY, u"Configured", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
		self.configuredFlagTextLabel.Wrap( -1 )

		self.configuredFlagTextLabel.SetFont( wx.Font( wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL, False, wx.EmptyString ) )

		HSizer32.Add( self.configuredFlagTextLabel, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		HSizer32.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.triggerConfigBtn = wx.Button( self, wx.ID_ANY, u"Configure", wx.DefaultPosition, wx.DefaultSize, 0 )
		HSizer32.Add( self.triggerConfigBtn, 0, wx.ALL, 5 )


		bSizer26.Add( HSizer32, 1, wx.EXPAND, 5 )


		HSizer112.Add( bSizer26, 3, wx.EXPAND, 5 )


		bodyVSizer.Add( HSizer112, 0, wx.EXPAND, 5 )

		HSizer31 = wx.BoxSizer( wx.VERTICAL )

		self.submitBtn = wx.Button( self, wx.ID_ANY, u"OK", wx.DefaultPosition, wx.DefaultSize, 0 )
		HSizer31.Add( self.submitBtn, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		bodyVSizer.Add( HSizer31, 1, wx.EXPAND, 5 )


		mainHSizer.Add( bodyVSizer, 3, wx.EXPAND, 5 )


		mainHSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.infoText = wx.StaticText( self, wx.ID_ANY, u"*Usage*\n\nIn addition to providing\nthe essential details\nof the RTSP video source,\nfurther information is required:\n\n - recording type\n - storage location\n - event handler (driver)\n  (if trigger-based recording\n  is selected)\nWhen selecting an event handler,\nit is necessary to configure\nthe characteristics of the trigger\nin a new window\n(Configure button).", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.infoText.Wrap( -1 )

		self.infoText.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_INFOBK ) )

		mainHSizer.Add( self.infoText, 0, wx.ALL|wx.EXPAND, 5 )


		frameVSizer.Add( mainHSizer, 1, wx.EXPAND, 5 )


		self.SetSizer( frameVSizer )
		self.Layout()
		frameVSizer.Fit( self )

		self.Centre( wx.BOTH )

	def __del__( self ):
		pass


###########################################################################
## Class JSONHandlerConfigurator
###########################################################################

class JSONHandlerConfigurator ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"RTSP Event Source - Videorotate", pos = wx.DefaultPosition, size = wx.Size( 800,-1 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.Size( -1,480 ), wx.DefaultSize )

		frameVSizer = wx.BoxSizer( wx.VERTICAL )

		InfoToolbarHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.SpacerToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.SpacerToolbar.Realize()

		InfoToolbarHSizer.Add( self.SpacerToolbar, 1, wx.EXPAND, 5 )

		self.infoToolbar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.infoTextBtn = self.infoToolbar.AddTool( wx.ID_ANY, u"tool", wx.ArtProvider.GetBitmap( wx.ART_HELP_BOOK, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, wx.EmptyString, wx.EmptyString, None )

		self.infoToolbar.Realize()

		InfoToolbarHSizer.Add( self.infoToolbar, 0, wx.EXPAND, 5 )


		frameVSizer.Add( InfoToolbarHSizer, 0, wx.EXPAND, 5 )

		bodyHSizer = wx.BoxSizer( wx.HORIZONTAL )

		configuratorVSizer = wx.BoxSizer( wx.VERTICAL )

		self.ConfiguratorTitle = wx.StaticText( self, wx.ID_ANY, u"JSON Listener\nConfigurator", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.ConfiguratorTitle.Wrap( -1 )

		self.ConfiguratorTitle.SetFont( wx.Font( 12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, wx.EmptyString ) )

		configuratorVSizer.Add( self.ConfiguratorTitle, 0, wx.ALL|wx.EXPAND, 5 )

		self.configuratorNotebook = wx.Notebook( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.settingsPanel = wx.Panel( self.configuratorNotebook, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		ListenConfigVSizer = wx.BoxSizer( wx.VERTICAL )

		self.formHolder = FormHolder(self)
		ListenConfigVSizer.Add( self.formHolder.form, 1, wx.ALL|wx.EXPAND, 5 )

		ListenerControlHSizer = wx.BoxSizer( wx.HORIZONTAL )


		ListenerControlHSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.listenerStatusText = wx.StaticText( self.settingsPanel, wx.ID_ANY, u"...Status...", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.listenerStatusText.Wrap( -1 )

		ListenerControlHSizer.Add( self.listenerStatusText, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		ListenerControlHSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.applyBtn = wx.Button( self.settingsPanel, wx.ID_ANY, u"Start/Apply", wx.DefaultPosition, wx.DefaultSize, 0 )
		ListenerControlHSizer.Add( self.applyBtn, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		ListenerControlHSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )


		ListenConfigVSizer.Add( ListenerControlHSizer, 0, wx.EXPAND, 5 )


		self.settingsPanel.SetSizer( ListenConfigVSizer )
		self.settingsPanel.Layout()
		ListenConfigVSizer.Fit( self.settingsPanel )
		self.configuratorNotebook.AddPage( self.settingsPanel, u"Configurator", True )
		self.triggerSettingsPanel = wx.Panel( self.configuratorNotebook, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		TriggerConfigVSizer = wx.BoxSizer( wx.VERTICAL )

		triggerConfigHeadHSizer = wx.BoxSizer( wx.HORIZONTAL )

		self.newTriggerOutputFormHolder = FormHolder(self)
		triggerConfigHeadHSizer.Add( self.newTriggerOutputFormHolder.form, 1, wx.ALL|wx.EXPAND, 5 )


		TriggerConfigVSizer.Add( triggerConfigHeadHSizer, 0, wx.EXPAND, 5 )

		self.triggerSettingsFormHolder = FormHolder(self)
		TriggerConfigVSizer.Add( self.triggerSettingsFormHolder.form, 1, wx.ALL|wx.EXPAND, 5 )

		self.addTriggerStateFormHolder = FormHolder(self)
		TriggerConfigVSizer.Add( self.addTriggerStateFormHolder.form, 0, wx.ALL|wx.EXPAND, 5 )

		self.selectedStateStatusText = wx.StaticText( self.triggerSettingsPanel, wx.ID_ANY, u"..Selected state..", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.selectedStateStatusText.Wrap( -1 )

		TriggerConfigVSizer.Add( self.selectedStateStatusText, 0, wx.ALL|wx.EXPAND, 5 )


		self.triggerSettingsPanel.SetSizer( TriggerConfigVSizer )
		self.triggerSettingsPanel.Layout()
		TriggerConfigVSizer.Fit( self.triggerSettingsPanel )
		self.configuratorNotebook.AddPage( self.triggerSettingsPanel, u"Triggers", False )

		configuratorVSizer.Add( self.configuratorNotebook, 1, wx.EXPAND |wx.ALL, 5 )


		bodyHSizer.Add( configuratorVSizer, 1, wx.EXPAND, 5 )

		viewerVSizer = wx.BoxSizer( wx.VERTICAL )

		bSizer31 = wx.BoxSizer( wx.HORIZONTAL )

		self.prevInputData = wx.BitmapButton( self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.DefaultSize, wx.BU_AUTODRAW|0 )

		self.prevInputData.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_GO_BACK, wx.ART_BUTTON ) )
		bSizer31.Add( self.prevInputData, 0, wx.ALL, 5 )


		bSizer31.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.inputDataLabel = wx.StaticText( self, wx.ID_ANY, u"Input Data", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.inputDataLabel.Wrap( -1 )

		bSizer31.Add( self.inputDataLabel, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		bSizer31.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.nextInputData = wx.BitmapButton( self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.DefaultSize, wx.BU_AUTODRAW|0 )

		self.nextInputData.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_GO_FORWARD, wx.ART_BUTTON ) )
		bSizer31.Add( self.nextInputData, 0, wx.ALL, 5 )


		viewerVSizer.Add( bSizer31, 0, wx.EXPAND, 5 )

		self.receiverInputFormHolder = FormHolder(self)
		viewerVSizer.Add( self.receiverInputFormHolder.form, 1, wx.ALL|wx.EXPAND, 5 )

		bSizer30 = wx.BoxSizer( wx.VERTICAL )

		self.submitBtn = wx.Button( self, wx.ID_ANY, u"OK", wx.DefaultPosition, wx.DefaultSize, 0 )
		bSizer30.Add( self.submitBtn, 0, wx.ALIGN_CENTER|wx.ALL, 5 )


		viewerVSizer.Add( bSizer30, 0, wx.EXPAND, 5 )


		bodyHSizer.Add( viewerVSizer, 1, wx.EXPAND, 5 )

		self.infoText = wx.StaticText( self, wx.ID_ANY, u"Usage\n\nTwo windows are available\nfor trigger configuration.\nThe configurator describes\nthe parameters of\nthe event-receiving server,\nwhile the triggers process\nthe incoming data.\nThe possible trigger states are:\n - start recording,\n - stop recording, or\n - no intervention.\nOne or more trigger rule group\ncan be created, which connects\nthe incoming, parsed data\nwith recording state.\nThe rule groups are evaluated\nsequentially and the last\nmatching group's target state\nwill be the final state\nwhich set the recording status.\n(Empty rule group\nis matching every input.)\nLabel (and corresponding value)\ncan be attached to a rule group\nat creation time.\nAfter creating and selecting\na rule group, new conditions\ncan be added to a one.\n\nOn the right side of the window,\nyou can see the incoming data.\nThe data is stored in a buffer\nand every item can be accessed.", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.infoText.Wrap( -1 )

		self.infoText.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_INFOBK ) )

		bodyHSizer.Add( self.infoText, 0, wx.ALL|wx.EXPAND, 5 )


		frameVSizer.Add( bodyHSizer, 1, wx.EXPAND, 5 )


		self.SetSizer( frameVSizer )
		self.Layout()

		self.Centre( wx.BOTH )

	def __del__( self ):
		pass


###########################################################################
## Class TestBed
###########################################################################

class TestBed ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 500,500 ), style = wx.CAPTION|wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

		bSizer27 = wx.BoxSizer( wx.VERTICAL )

		self.formHolder = FormHolder(self)
		bSizer27.Add( self.formHolder.form, 1, wx.ALL|wx.EXPAND, 5 )


		self.SetSizer( bSizer27 )
		self.Layout()

		self.Centre( wx.BOTH )

	def __del__( self ):
		pass


