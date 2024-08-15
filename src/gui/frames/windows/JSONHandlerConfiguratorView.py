import dataclasses
from dataclasses import dataclass
import functools
from functools import partial
import enum
from typing import Callable, Any, Mapping, List, Dict, Iterable, Optional
import wx
import wx.lib.agw.customtreectrl
import wx.lib.agw.hypertreelist

import notifier
import gui.controls.wx_form as wx_form

from gui.frames.windows.AppWindowDescription import JSONHandlerConfigurator

import gui.backend.event.receiver as event_receiver
import gui.backend.event.processing as event_processing

class TriggerTargetStateForm:
    TRIGGER_TARGET_STATE = 'target_state'
    TRIGGER_TAG_NAME = 'tag_name'
    TRIGGER_TAG_VALUE = 'tag_value'

    @property
    def form(self) -> wx_form.Form:
        return self._form

    @property
    def submit_evt_channel(self) -> notifier.UpdateChannel:
        return self._submit_evt_channel

    def __init__(self, parent) -> None:
        self._form = wx_form.BulkForm(parent, wx.HORIZONTAL)

        self._form.add_control(
            self.TRIGGER_TARGET_STATE,
            wx_form.TextOptionSelect(parent, options=event_processing.SimpleTrigger._member_names_),
            3
        )
        self._form.add_item(wx_form.Label(parent, ' LABEL: '), 1)
        self._form.add_control(
            self.TRIGGER_TAG_NAME,
            wx_form.TextInput(parent),
            3
        )
        self._form.add_item(wx_form.Label(parent, ' = '), 1)
        self._form.add_control(
            self.TRIGGER_TAG_VALUE,
            wx_form.TextInput(parent),
            3
        )
        
        submit_btn = self._form.add_submit_button()

        self._submit_evt_channel = submit_btn.event_channel
        submit_btn.bind_event_channel(wx.EVT_BUTTON)
    
    def get_as_conditions(self) -> event_processing.TriggerConditions:
        values = self.form.get_values()
        
        target_state = event_processing.SimpleTrigger._member_map_[values[self.TRIGGER_TARGET_STATE]]
        return event_processing.TriggerConditions(
            state_on_match=target_state,
            criterion_list=[],
            tag_name=values[self.TRIGGER_TAG_NAME] or None,
            tag_value=values[self.TRIGGER_TAG_VALUE] or None
        )


class TriggerCriterionForm:
    TRIGGER_FIELD_SELECT = 'field'
    TRIGGER_FIELD_CMP_OPERATOR = 'field_comparator'
    TRIGGER_FIELD_VALUE = 'field_value'
    
    @property
    def form(self) -> wx_form.Form:
        return self._form
    
    @property
    def form_field_name_option(self) -> wx_form.ModifiableTextOptionSelect:
        return self._input_data_fields
    
    @property
    def submit_evt_channel(self) -> notifier.UpdateChannel:
        return self._submit_evt_channel
    
    def __init__(self, parent) -> None:
        self._form = wx_form.BulkForm(parent, wx.HORIZONTAL)
        
        self._input_data_fields = wx_form.ModifiableTextOptionSelect(parent, options=('.'))
        self._form.add_control(
            self.TRIGGER_FIELD_SELECT,
            self._input_data_fields,
            3
        )
        self._form.add_control(
            self.TRIGGER_FIELD_CMP_OPERATOR,
            wx_form.TextOptionSelect(parent, options=list(event_processing.ValueComparison.operators()))
        )
        self._form.add_control(
            self.TRIGGER_FIELD_VALUE,
            wx_form.TextInput(parent),
            3
        )
        submit_btn = self._form.add_submit_button()
        
        self._submit_evt_channel = submit_btn.event_channel
        submit_btn.bind_event_channel(wx.EVT_BUTTON)
    
    def get_as_criterion(self) -> event_processing.TriggerCriterion:
        values = self.form.get_values()
        return event_processing.TriggerCriterion(
            field=values[self.TRIGGER_FIELD_SELECT],
            reference_value=values[self.TRIGGER_FIELD_VALUE],
            comparison=event_processing.ValueComparison.get_enum(values[self.TRIGGER_FIELD_CMP_OPERATOR])
        )



class JSONHandlerConfiguratorView(JSONHandlerConfigurator):
    TRIGGER_FIELD_SELECT = 'field'
    TRIGGER_FIELD_CMP_OPERATOR = 'field_comparator'
    TRIGGER_FIELD_VALUE = 'field_value'
    
    DASHBOARD_DISPLAY = wx_form.TabbedDataDisplay
    
    @property
    def dashboard_cursor(self) -> List:
        return list(self._rule_dashboard.cursor_position)
    
    # TODO: move into a shared class
    def toggle_info(self, evt):
        self.infoText.Show(not self.infoText.IsShown())
        self.Layout()
        
        evt.Skip()
    
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        
        info_btn_id = self.infoTextBtn.GetId()
        self.Bind(wx.EVT_TOOL, self.toggle_info, id=info_btn_id)
        self.infoText.Show(False)
        self.Layout()
        
        self._trigger_conditions_cursor = None
        self.selectedStateStatusText.SetLabelText('')
        
        # Criterion Form create
        self._criterion_form = TriggerCriterionForm(self.triggerSettingsPanel)

        # Dashboard create
        self._rule_dashboard = self.DASHBOARD_DISPLAY(self.triggerSettingsPanel)
        self.triggerSettingsFormHolder.set_form(
            wx_form.SingleControlForm(self._rule_dashboard)
        )
        
        # Criterion Form events
        self._criterion_form.submit_evt_channel.thenPermanent(
            partial(self._form_output__add_trigger_criterion, self._rule_dashboard, self._criterion_form)
        )
        self.newTriggerOutputFormHolder.set_form(self._criterion_form.form)
        

        # Dashboard events
        self._rule_dashboard.bind_event_channel(wx.EVT_TREE_SEL_CHANGED)
        self._rule_dashboard.event_channel.subscribe(partial(self._process_dashboard_click,self._rule_dashboard))
        
        # Stage creation setup
        self._target_form = TriggerTargetStateForm(self.triggerSettingsPanel)

        self._target_form.submit_evt_channel.thenPermanent(
            partial(self._form_output__add_trigger_target, self._rule_dashboard, self._target_form)
        )
        self.addTriggerStateFormHolder.set_form(self._target_form.form)
        
        self._setup_history_display()
        
    
    def _setup_history_display(self):
        self.history_display = wx_form.IndentedDataDisplay(self)
        self.receiverInputFormHolder.set_form(
            wx_form.SingleControlForm(self.history_display)
        )

        self._receiver_history = []
        self._receiver_history_cursor = -1
        
        ## buttons
        self.prevInputData.Disable()
        self.nextInputData.Disable()

        self.prevInputData.Bind(
            wx.EVT_BUTTON,
            partial(self.__change_history_pos, -1)
        )
        self.nextInputData.Bind(
            wx.EVT_BUTTON,
            partial(self.__change_history_pos, +1)
        )
    
    def append_test_data(self, data):
        self._receiver_history.append(data)
        
        if self._receiver_history_cursor == -1:
            self._receiver_history_cursor = 0
            self.__update_history_data()
        
        else:
            self.nextInputData.Enable()
    
    def __update_history_data(self):
        history_len = len(self._receiver_history)
        cursor = self._receiver_history_cursor
        data = self._receiver_history[cursor]
        
        self.history_display.control_value = data
        
        if 0 < cursor:
            self.prevInputData.Enable()
        else:
            self.prevInputData.Disable()
        
        if cursor < history_len-1:
            self.nextInputData.Enable()
        else:
            self.nextInputData.Disable()
        
        self._criterion_form.form_field_name_option.set_options(data.keys())
    
    def __change_history_pos(self,
                             pos_increment: int,
                             update_display: bool = True):
        self._receiver_history_cursor += pos_increment
        
        if update_display:
            self.__update_history_data()
    
    
    def _form_output__add_trigger_criterion(self,
                                            dashboard: DASHBOARD_DISPLAY,
                                            form: TriggerCriterionForm,
                                            update: notifier.Update):
        if not len(self.dashboard_cursor):
            raise LookupError('No target state selected')
        
        path, target = dashboard.cursor_position, dashboard.cursor_data()
        while not isinstance(target, event_processing.TriggerConditions):
            path, target = dashboard.get_parent(path)
        
        target.criterion_list.append(form.get_as_criterion())
        
        dashboard.rebuild()
        self._process_dashboard_click(dashboard)
    
    def _form_output__add_trigger_target(self,
                                         dashboard: DASHBOARD_DISPLAY,
                                         form: TriggerTargetStateForm,
                                         update: notifier.Update):
        sample_form_data = form.get_as_conditions()
        
        display_tag = f"{sample_form_data.tag_name}={sample_form_data.tag_value}"
        if not isinstance(sample_form_data.tag_value, str) or not sample_form_data.tag_value:
            display_tag = str(sample_form_data.tag_name)
        if not isinstance(sample_form_data.tag_name, str) or not sample_form_data.tag_name:
            display_tag = ''
        
        tab_id = sum(1 for tab in dashboard.tab_list)
        
        tab_name = f"{tab_id}_{sample_form_data.state_on_match.name}"
        if not display_tag:
            tab_name += f": {display_tag}"
        
        tab = self._rule_dashboard.add_tab(tab_name, form.get_as_conditions)
    
    def _process_dashboard_click(self, dashboard: DASHBOARD_DISPLAY, evt: Optional[notifier.Update] = None):
        #if evt is not None and isinstance(evt.value, wx.lib.agw.customtreectrl.TreeEvent):
        
        
        self.selectedStateStatusText.SetLabelText(''.join(dashboard.cursor_position))
        
        # import sys
        # print('stata', dict(dashboard._data_lookup_table), dict(dashboard._display_items))
        # sys.stdout.flush()
        
        # assert isinstance(evt, notifier.Update)
        # if not isinstance(evt.value, wx.lib.agw.customtreectrl.TreeEvent):
        #     return
        
        # item: wx.lib.agw.hypertreelist.TreeListItem = evt.value.GetItem()
        
        # print('_process_dashboard_click', item.get)
