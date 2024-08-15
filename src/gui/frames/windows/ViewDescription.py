# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 3.10.1-0-g8feb16b)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
import wx.aui
from .CustomControls.LiveVideoCapturePanel import LiveVideoCapturePanel

###########################################################################
## Class Main
###########################################################################

class Main ( wx.Frame ):

    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"Új Project - main", pos = wx.DefaultPosition, size = wx.Size( 581,371 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

        self.SetSizeHints( wx.Size( 600,400 ), wx.DefaultSize )

        mainVerticalSizer = wx.BoxSizer( wx.VERTICAL )

        self.mainToolBar = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
        self.loadFile = self.mainToolBar.AddTool( wx.ID_ANY, u"Load project collection...", wx.ArtProvider.GetBitmap( wx.ART_PLUS, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, u"Load project collection...", u"Load project collection...", None )

        self.fileLoadBtn = self.mainToolBar.AddTool( wx.ID_ANY, u"Save all project collections...", wx.ArtProvider.GetBitmap( wx.ART_FILE_SAVE, wx.ART_TOOLBAR ), wx.NullBitmap, wx.ITEM_NORMAL, u"Save all project collections...", u"Save all project collections...", None )

        self.mainToolBar.Realize()

        mainVerticalSizer.Add( self.mainToolBar, 0, wx.EXPAND, 5 )

        bodyHorizontalSizer = wx.BoxSizer( wx.HORIZONTAL )

        self.projectCollectionTree = wx.TreeCtrl( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TR_DEFAULT_STYLE )
        bodyHorizontalSizer.Add( self.projectCollectionTree, 1, wx.ALL|wx.EXPAND, 5 )

        leftPanelSizer = wx.BoxSizer( wx.VERTICAL )

        bSizer4 = wx.BoxSizer( wx.HORIZONTAL )

        self.addDirBtn = wx.Button( self, wx.ID_ANY, u"Mappa hozzáadása...", wx.DefaultPosition, wx.DefaultSize, 0 )
        bSizer4.Add( self.addDirBtn, 0, wx.ALL, 5 )


        bSizer4.Add( ( 0, 0), 1, wx.EXPAND, 5 )

        self.createCategoryBtn = wx.Button( self, wx.ID_ANY, u"Új kategória...", wx.DefaultPosition, wx.DefaultSize, 0 )

        self.createCategoryBtn.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_PLUS, wx.ART_BUTTON ) )
        self.createCategoryBtn.SetToolTip( u"Create new category for one or more projects..." )

        bSizer4.Add( self.createCategoryBtn, 0, wx.ALL, 5 )


        leftPanelSizer.Add( bSizer4, 0, wx.EXPAND, 5 )

        self.collectionCategoryView = wx.aui.AuiNotebook( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.aui.AUI_NB_DEFAULT_STYLE )

        leftPanelSizer.Add( self.collectionCategoryView, 1, wx.EXPAND |wx.ALL, 5 )


        bodyHorizontalSizer.Add( leftPanelSizer, 3, wx.EXPAND, 5 )


        mainVerticalSizer.Add( bodyHorizontalSizer, 1, wx.EXPAND, 5 )


        self.SetSizer( mainVerticalSizer )
        self.Layout()
        self.mainStatusBar = self.CreateStatusBar( 1, wx.STB_SIZEGRIP, wx.ID_ANY )

        self.Centre( wx.BOTH )

        # Connect Events
        self.Bind( wx.EVT_TOOL, self.onLoadProjectFile, id = self.loadFile.GetId() )
        self.Bind( wx.EVT_TOOL, self.onSaveProjectFile, id = self.fileLoadBtn.GetId() )
        self.addDirBtn.Bind( wx.EVT_BUTTON, self.onAddSourceDirectory )
        self.createCategoryBtn.Bind( wx.EVT_BUTTON, self.onAddCategory )

    def __del__( self ):
        pass


    # Virtual event handlers, override them in your derived class
    def onLoadProjectFile( self, event ):
        event.Skip()

    def onSaveProjectFile( self, event ):
        event.Skip()

    def onAddSourceDirectory( self, event ):
        event.Skip()

    def onAddCategory( self, event ):
        event.Skip()


###########################################################################
## Class ImgClassifier
###########################################################################

class ImgClassifier ( wx.Frame ):

    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 500,300 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

        self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

        mainVerticalSizer = wx.BoxSizer( wx.VERTICAL )

        TitleHorizontalSizer = wx.BoxSizer( wx.HORIZONTAL )


        TitleHorizontalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

        self.title = wx.StaticText( self, wx.ID_ANY, u"Osztályozás", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.title.Wrap( -1 )

        self.title.SetFont( wx.Font( 12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, wx.EmptyString ) )

        TitleHorizontalSizer.Add( self.title, 0, wx.ALL, 5 )


        TitleHorizontalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )


        mainVerticalSizer.Add( TitleHorizontalSizer, 0, wx.EXPAND, 5 )

        headHorizontalSizer = wx.BoxSizer( wx.HORIZONTAL )

        self.showPrevImgLabel = wx.StaticText( self, wx.ID_ANY, u"Előző", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.showPrevImgLabel.Wrap( -1 )

        headHorizontalSizer.Add( self.showPrevImgLabel, 0, wx.ALIGN_BOTTOM|wx.ALL, 5 )

        self.imgClassText = wx.StaticText( self, wx.ID_ANY, u"[Nincs kategória]", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
        self.imgClassText.Wrap( -1 )

        self.imgClassText.SetFont( wx.Font( wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, wx.EmptyString ) )

        headHorizontalSizer.Add( self.imgClassText, 1, wx.ALL, 5 )

        self.showNextImgLabel = wx.StaticText( self, wx.ID_ANY, u"Következő", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.showNextImgLabel.Wrap( -1 )

        headHorizontalSizer.Add( self.showNextImgLabel, 0, wx.ALIGN_BOTTOM|wx.ALL, 5 )


        mainVerticalSizer.Add( headHorizontalSizer, 0, wx.EXPAND, 5 )

        bodyHorizontalSizer = wx.BoxSizer( wx.HORIZONTAL )

        prevImgBtnVerticalSizer = wx.BoxSizer( wx.VERTICAL )


        prevImgBtnVerticalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

        self.showPrevImgBtn = wx.BitmapButton( self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.DefaultSize, wx.BU_AUTODRAW|0 )

        self.showPrevImgBtn.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_GO_BACK, wx.ART_BUTTON ) )
        prevImgBtnVerticalSizer.Add( self.showPrevImgBtn, 0, wx.ALL, 5 )


        prevImgBtnVerticalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )


        bodyHorizontalSizer.Add( prevImgBtnVerticalSizer, 0, wx.EXPAND, 5 )

        self.imgInspector = wx.Panel( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bodyHorizontalSizer.Add( self.imgInspector, 1, wx.EXPAND |wx.ALL, 5 )

        nextImgBtnVerticalSizer = wx.BoxSizer( wx.VERTICAL )


        nextImgBtnVerticalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )

        self.showNextImgBtn = wx.BitmapButton( self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.DefaultSize, wx.BU_AUTODRAW|0 )

        self.showNextImgBtn.SetBitmap( wx.ArtProvider.GetBitmap( wx.ART_GO_FORWARD, wx.ART_BUTTON ) )
        nextImgBtnVerticalSizer.Add( self.showNextImgBtn, 0, wx.ALL, 5 )


        nextImgBtnVerticalSizer.Add( ( 0, 0), 1, wx.EXPAND, 5 )


        bodyHorizontalSizer.Add( nextImgBtnVerticalSizer, 0, wx.EXPAND, 5 )


        mainVerticalSizer.Add( bodyHorizontalSizer, 1, wx.EXPAND, 5 )

        self.placeholder_chooseCategoryBtnView = wx.StaticText( self, wx.ID_ANY, u"Constructor replaces me : chooseCategoryBtnView", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
        self.placeholder_chooseCategoryBtnView.Wrap( -1 )

        self.placeholder_chooseCategoryBtnView.SetForegroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNTEXT ) )
        self.placeholder_chooseCategoryBtnView.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_HIGHLIGHT ) )

        mainVerticalSizer.Add( self.placeholder_chooseCategoryBtnView, 0, wx.ALL|wx.EXPAND, 5 )


        self.SetSizer( mainVerticalSizer )
        self.Layout()

        self.Centre( wx.BOTH )

        # Connect Events
        self.showPrevImgBtn.Bind( wx.EVT_BUTTON, self.onAskPrevImg )
        self.showNextImgBtn.Bind( wx.EVT_BUTTON, self.onAskNextImg )

    def __del__( self ):
        pass


    # Virtual event handlers, override them in your derived class
    def onAskPrevImg( self, event ):
        event.Skip()

    def onAskNextImg( self, event ):
        event.Skip()


###########################################################################
## Class ImgGrabbing
###########################################################################

class ImgGrabbing ( wx.Frame ):

    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 500,300 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

        self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

        mainVerticalSizer = wx.BoxSizer( wx.VERTICAL )

        SourceSelectorHorizontalSizer = wx.BoxSizer( wx.HORIZONTAL )

        srcChooserListChoices = []
        self.srcChooserList = wx.ComboBox( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, srcChooserListChoices, 0 )
        SourceSelectorHorizontalSizer.Add( self.srcChooserList, 1, wx.ALL|wx.EXPAND, 5 )

        self.controlBtn = wx.Button( self, wx.ID_OK, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        SourceSelectorHorizontalSizer.Add( self.controlBtn, 0, wx.ALL|wx.EXPAND, 5 )


        mainVerticalSizer.Add( SourceSelectorHorizontalSizer, 0, wx.EXPAND, 5 )

        self.warning_msg = wx.StaticText( self, wx.ID_ANY, u"Válassz ki egy forrást!", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
        self.warning_msg.Wrap( -1 )

        self.warning_msg.SetFont( wx.Font( wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, wx.EmptyString ) )
        self.warning_msg.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_HIGHLIGHT ) )

        mainVerticalSizer.Add( self.warning_msg, 0, wx.ALL|wx.EXPAND, 5 )

        self.liveVideoCapturePanel = LiveVideoCapturePanel(self)
        mainVerticalSizer.Add( self.liveVideoCapturePanel, 1, wx.ALL|wx.EXPAND, 5 )


        self.SetSizer( mainVerticalSizer )
        self.Layout()

        self.Centre( wx.BOTH )

        # Connect Events
        self.controlBtn.Bind( wx.EVT_BUTTON, self.onTriggerAction )

    def __del__( self ):
        pass


    # Virtual event handlers, override them in your derived class
    def onTriggerAction( self, event ):
        event.Skip()


###########################################################################
## Class SourceEventLog
###########################################################################

class SourceEventLog ( wx.Frame ):

    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 500,300 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

        self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

        mainVerticalSizer = wx.BoxSizer( wx.VERTICAL )

        self.eventList = wx.ListCtrl( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LC_ICON|wx.LC_REPORT )
        mainVerticalSizer.Add( self.eventList, 1, wx.ALL|wx.EXPAND, 5 )


        self.SetSizer( mainVerticalSizer )
        self.Layout()

        self.Centre( wx.BOTH )

    def __del__( self ):
        pass


