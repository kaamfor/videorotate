from enum import Enum
from abc import ABC, abstractmethod
import dataclasses
from dataclasses import dataclass, is_dataclass, fields
from collections import UserDict
import functools
import operator
from typing import Any, List, Dict, Tuple, Iterable, Union, Optional, Mapping, MutableMapping, Type, Callable, Sequence, Set, Literal
import types
import inspect
import weakref
import wx

import wx.dataview
import wx.lib.gizmos as gizmos
import wx.lib.agw.hypertreelist
import wx.lib.mixins.listctrl
from reactivex import Observable
import notifier

from videorotate_typedefs import Number, Alphanumeric

WxChild = Union[wx.Sizer, wx.Window]
WxIndex = int # or wx.NOT_FOUND

KVFormRowProportion = Tuple[int, int]
FieldOutput = Union[Alphanumeric,
                    Sequence[Alphanumeric],
                    Set[Alphanumeric],
                    Mapping[Alphanumeric, 'FieldOutput']]
KVFormOutput = Mapping[str, FieldOutput]

class Control(ABC):
    @property
    @abstractmethod
    def control(self) -> wx.Window:
        pass

class ValueReadableControl(Control, ABC):
    @property
    @abstractmethod
    def control_value(self) -> FieldOutput:
        pass

class ValueProgrammableInput(ValueReadableControl, ABC):
    @ValueReadableControl.control_value.setter
    @abstractmethod
    def control_value(self, value) -> None:
        pass


class CursorReadableControl(Control, ABC):
    @property
    @abstractmethod
    def cursor_position(self) -> Union[List, Set]:
        pass

class CursorProgrammable(Control, ABC):
    @abstractmethod
    def set_cursor_position(self, position: Union[List, Set]) -> None:
        pass


# __init__ called with parent and value parameters!
class FieldBuildableControl(Control):
    @staticmethod
    def get_builder(field: dataclasses.Field) -> Optional[Callable[..., 'FieldBuildableControl']]:
        return field.metadata.get(FieldBuildableControl, None)
    
    @staticmethod
    def get_field_data(field: dataclasses.Field) -> Mapping:
        return field.metadata.get((FieldBuildableControl, 'data'), {})
    
    # TODO: document default <-> value parameter
    @classmethod
    def field(cls, *control_args, **mixed_kwargs) -> dataclasses.Field:
        builder_params = set([name for name in inspect.signature(cls).parameters])
        field_params = set([name for name in inspect.signature(dataclasses.field).parameters])
        
        control_kwargs = {f: mixed_kwargs.get(f) for f in builder_params if f in mixed_kwargs}
        field_kwargs = {f: mixed_kwargs.get(f) for f in field_params if f in mixed_kwargs}
        
        metadata = field_kwargs.setdefault('metadata', {})
        field: dataclasses.Field = dataclasses.field(**field_kwargs)

        metadata[FieldBuildableControl] = functools.partial(
            cls,
            *control_args,
            **{k: v for k, v in control_kwargs.items() if k in builder_params}
        )
        metadata[(FieldBuildableControl, 'data')] = dict(mixed_kwargs)
        return field
    
    # @classmethod
    # def field(cls, *control_args, **mixed_kwargs) -> dataclasses.Field:
    #     # Assume dataclass
    #     controls_params = [f.name for f in fields(cls)]
    #     controls_params.extend(
    #         inspect.signature(cls).parameters
    #     )

    #     control_kwargs = {f.name: mixed_kwargs.get(
    #         f.name) for f in fields(cls)}

    #     mixed_kvset = set(mixed_kwargs.items())
    #     control_kvset = set(control_kwargs.items())
    #     field_kwargs = dict(mixed_kvset - control_kvset)

    #     metadata = field_kwargs.setdefault('metadata', {})
    #     field: dataclasses.Field = dataclasses.field(**field_kwargs)

    #     metadata[FieldBuildableControl] = functools.partial(
    #         cls._control_builder,
    #         *control_args,
    #         **control_kwargs
    #     )
    #     return field
    
    # @classmethod
    # def _control_builder(cls, *args, **kwargs) -> 'FieldBuildableControl':
    #     return cls(*args, **kwargs)

class ObservableInput(Control, ABC):
    @property
    def event_channel(self) -> notifier.UpdateChannel:
        if not hasattr(self, '_event_channel'):
            self._event_channel = notifier.UpdateChannel()
        
        return self._event_channel
    
    def bind_event_channel(self, event, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        self.control.Bind(event, self._process_event, source=source, id=id, id2=id2)
    
    def _process_event(self, event: wx.Event) -> notifier.UpdateChannel:
        self._event_channel.send(
            notifier.Update(
                key=event.EventType,
                value=event,
                emitted_by=self
            )
        )

@dataclass
class TextInput(ValueProgrammableInput, FieldBuildableControl, ObservableInput):
    parent: wx.Window
    value: str = ''
    
    @property
    def control(self) -> wx.Window:
        return self._control
    
    @property
    def control_value(self) -> str:
        return self._control.GetValue()
    
    @control_value.setter
    def control_value(self, value: str) -> None:
        self._control.SetValue(value)
    
    def __post_init__(self):
        self._control = wx.TextCtrl(
            parent=self.parent,
            value=self.value,
            style=wx.ALIGN_LEFT)


@dataclass
class Label(ValueProgrammableInput, FieldBuildableControl):
    parent: wx.Window
    value: str = ''

    @property
    def control(self) -> wx.Window:
        return self._control

    @property
    def control_value(self) -> str:
        return self._control.GetLabelText()

    @control_value.setter
    def control_value(self, value: str) -> None:
        self._control.SetLabelText(value)

    def __post_init__(self):
        self._control = wx.StaticText(
            parent=self.parent,
            label=self.value,
            style=wx.ALIGN_CENTER | wx.EXPAND | wx.ALL | wx.CENTER)


@dataclass
class NumberInput(ValueProgrammableInput, FieldBuildableControl, ObservableInput):
    parent: wx.Window
    value: Number = 0
    min_value: Number = 0
    max_value: Number = 100
    
    @property
    def control(self) -> wx.Window:
        return self._control
    
    @property
    def control_value(self) -> Number:
        return self._control.GetValue()
    
    @control_value.setter
    def control_value(self, value: Number) -> None:
        self._control.SetValue(value)
    
    def __post_init__(self):
        self._control = wx.SpinCtrl(
            self.parent,
            value=str(self.value),
            min=self.min_value,
            max=self.max_value,
            initial=self.value,
            style=wx.ALIGN_CENTER
        )


@dataclass
class SubmitBtn(FieldBuildableControl, ObservableInput):
    parent: wx.Window
    title: str = 'Send'

    @property
    def control(self) -> wx.Window:
        return self._control

    def __post_init__(self):
        self._control = wx.Button(self.parent, label=str(self.title))
        # wx.SP_ARROW_KEYS?


# Option List Control
# value has to be an option when it's a string and control is read-only
@dataclass
class TextOptionSelect(ValueProgrammableInput, FieldBuildableControl, ObservableInput):
    parent: wx.Window
    options: Union[List[Alphanumeric], Dict[Alphanumeric, Alphanumeric]]
    value: Union[WxIndex, str] = 0 # index or string (error if index is out-of-boundary); WARNING: sort=True can be a problem!
    editable: bool = False
    sort: bool = False
    
    @property
    def control(self) -> wx.Window:
        return self._control
    
    @property
    def control_value(self) -> Alphanumeric:
        displayed_text = self._control.GetStringSelection()
        
        return self._value[displayed_text] if displayed_text in self._value else displayed_text
    
    # setting index or string (includes wx.NOT_FOUND)
    @control_value.setter
    def control_value(self, value: Union[WxIndex, str]) -> None:
        if isinstance(value, WxIndex) or value == wx.NOT_FOUND:
            self._control.SetSelection(value)
        else:
            self._control.SetValue(value)
    
    # set selection via index (includes wx.NOT_FOUND)
    def select_via_index(self, index: WxIndex):
        assert isinstance(index, WxIndex) or index == wx.NOT_FOUND
        self._control.SetSelection(index)
    
    def __post_init__(self):
        #assert isinstance(self.options, (Dict, List))
        
        assert isinstance(self.value, (WxIndex, str)
                          ) or self.value == wx.NOT_FOUND
        
        self._control = None
        self._setup_control()
    
    def _setup_control(self):
        if isinstance(self.options, Dict):
            self._value = self.options
        else:
            self._value = {name: name for name in self.options}
        keys = list(self._value.keys())

        if self._control is not None:
            self._control.SetItems(keys)
            return

        style = 0
        if not self.editable:
            style |= wx.CB_READONLY
        if self.sort:
            style |= wx.CB_SORT

        value = self.value
        if self.value == wx.NOT_FOUND:
            value = ''
        elif isinstance(self.value, WxIndex):
            if 0 <= self.value < len(keys):
                index, value = self.value, ''
            else:
                raise IndexError

        self._control = wx.ComboBox(
            parent=self.parent,
            choices=keys,
            style=style,
            value=value
        )

        if isinstance(value, WxIndex):
            self._control.SetSelection(value)


@dataclass
class ModifiableTextOptionSelect(TextOptionSelect):
    def set_options(self, options):
        self.options = options
        
        self._setup_control()


IndentedDataInputType = FieldOutput

# or DataHierarchy
@dataclass
class IndentedDataDisplay(ValueProgrammableInput,
                          CursorReadableControl,
                          #CursorProgrammable,
                          FieldBuildableControl,
                          ObservableInput):
    parent: wx.Window
    value: dataclasses.InitVar[Optional[IndentedDataInputType]] = dataclasses.field(default=())
    cursor_position: dataclasses.InitVar[Union[List[Alphanumeric], Set[Alphanumeric]]] = (
    )
    editable: dataclasses.InitVar[bool] = False
    sort: dataclasses.InitVar[bool] = False

    @property
    def control(self) -> wx.Window:
        return self._control

    @property
    def control_value(self) -> Alphanumeric:
        return self._data

    # setting index or string (includes wx.NOT_FOUND)
    @control_value.setter
    def control_value(self, value: IndentedDataInputType) -> None:
        #assert isinstance(value, IndentedDataInputType)
        
        self.change_display(value)
        self._data = value

    @property
    def item_list(self) -> Iterable[Tuple[str, str]]:
        result = []
        
        # TODO: using only parent_name array?
        root = self._data
        iterables = [root]
        parent_name = {root: '$'}
        while len(iterables):
            input = iterables.pop(0)
            assert isinstance(input, Iterable)
            
            datalist = iterables.input() if isinstance(input, Mapping) else enumerate(input)
            
            prefix = str(parent_name[input])
            for key,value in datalist:
                substit_key = str(key).replace("'", '')
                result_path = f"{prefix}['{substit_key}']"
                
                if not isinstance(value, Iterable):
                    result.append(result_path)
                else:
                    parent_name[value] = result_path
                    iterables.append(value)

    class _IndentedDataDisplayCtrl(gizmos.TreeListCtrl, wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin):
        def __init__(self, parent, *args, **kwargs):
            gizmos.TreeListCtrl.__init__(self, parent, *args, **kwargs)
            wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin.__init__(self)
            self.resizeColumn(0)

    def __post_init__(self, data, cursor_position, editable, sort):
        self._display_items = weakref.WeakKeyDictionary()
        self._data_lookup_table = weakref.WeakValueDictionary()
        
        self.setup_display(data)
        self._data = data
    
    def setup_display(self, data: IndentedDataInputType) -> None:
        control = self._control = self._IndentedDataDisplayCtrl(self.parent)
        
        width, height = control.GetClientSize()
        index = control.AddColumn('data', width=width)
        
        assert index != -1, 'TreeList cannot create column'
        
        if not isinstance(data, (List, Set, Tuple)):
            data = [data]
        
        for item in data:
            root = self._tree_root = control.AddRoot(f"{type(item).__name__}")
            self._add_items(root, item)
            control.Expand(root)
    
    def change_display(self, new_data: IndentedDataInputType) -> None:
        self._control.DeleteAllItems()
        
        root = self._tree_root = self._control.AddRoot(f"{type(new_data).__name__}")
        self._add_items(root, new_data)
        self._control.Expand(root)
    
    def rebuild(self):
        # TODO: refactor - code dup
        self._control.DeleteAllItems()
        
        root = self._tree_root = self._control.AddRoot(f"{type(self._data).__name__}")
        self._add_items(root, self._data)
        self._control.Expand(root)
    
    def _add_items(self,
                   parent: wx.lib.agw.hypertreelist.TreeListItem,
                   item: IndentedDataInputType,
                   additional_name: Optional[str] = None,
                   path: Optional[List[Alphanumeric]] = None,
                   root_level: bool = True) -> List:
        control = self._control
        
        assert path is None or isinstance(path, List)
        if path is None:
            path = []
        
        if isinstance(item, Alphanumeric) or not isinstance(item, (Mapping, Iterable)):
            item_name = str(item)
            if additional_name is None:
                additional_name = ''
            item_name = ' : '.join([str(additional_name), str(item)])
            
            appended = control.AppendItem(parent, item_name)
            
            self._display_items[appended] = path.copy()
            
            # TODO: high memory consumption!
            lookup_path = path.copy()
            lookup_path.append(item_name)
            try:
                self._data_lookup_table[tuple(lookup_path)] = item
            except TypeError:
                # TypeError: cannot create weak reference to '***' object
                appended.SetData(item)
        else:
            if additional_name is None:
                additional_name = '.'
            
            if not root_level:
                parent_name = f"{additional_name}: {type(item).__name__}"
                parent = control.AppendItem(parent, parent_name)
                
                parent_path = path.copy()
                self._display_items[parent] = parent_path
                path.append(additional_name)
                
                # TODO: high memory consumption!
                lookup_path = parent_path.copy()
                lookup_path.append(parent_name)
                self._data_lookup_table[tuple(lookup_path)] = item # lookup by display name
                
                self._data_lookup_table[tuple(path)] = item # lookup by 'clean' name
            
            if isinstance(item, Mapping):
                for name,i in item.items():
                    self._add_items(parent, i, name, path=path.copy(), root_level=False)
            elif isinstance(item, Iterable):
                for i in item:
                    self._add_items(parent, i, path=path.copy(), root_level=False)
            
            control.Expand(parent)

    @property
    def cursor_position(self) -> List[Alphanumeric]:
        entry = self._control.GetSelection()
        path = self._display_items.get(entry, []).copy()
        if entry in self._display_items:
                path.append(entry.GetText())
        
        return path
    
    # def set_cursor_position(self, position: Union[List[Alphanumeric], Set[Alphanumeric]]) -> None:
    #     return super().set_cursor_position(position)
    
    def cursor_data(self) -> Any:
        return (self._data_lookup_table.get(tuple(self.cursor_position),
                                            self._control.GetSelection().GetData()))
    
    # TODO: document
    def get_parent(self, cursor: List[Alphanumeric]) -> Tuple[Any, Any]:
        parent_cursor = cursor.copy()
        parent_cursor.pop()
        return parent_cursor, self._data_lookup_table[tuple(parent_cursor)]



@dataclass
class TabbedDataDisplay(IndentedDataDisplay):
    # TODO: lazy evaluation?
    @property
    def tab_list(self) -> Iterable[Any]:
        for _,tab in self.control_value.items():
            yield tab
    
    def __post_init__(self, data, cursor_position, editable, sort):
        data = dict(data)
        
        res = super().__post_init__(data, cursor_position, editable, sort)
        return res
    
    def add_tab(self, tab_name: str, factory: Callable = dict) -> Tuple[Any, Any]:
        self.control_value[tab_name] = tab = factory()
        
        # update
        # TODO: more efficient way
        self.control_value = self.control_value
        
        return tab
    
    def get_tab(self, tab_name: str) -> Any:
        return self.control_value[tab_name]
    
    def del_tab(self, tab_name: str) -> Any:
        del self.control_value[tab_name]
    
    def update_tab(self, key: str):
        # TODO: more efficient way
        self.change_display(self.control_value)


@dataclass
class ListDisplay(CursorReadableControl,
                  FieldBuildableControl,
                  ObservableInput):
    parent: wx.Window
    data: dataclasses.InitVar[Optional[List[Mapping[str, str]]]] = dataclasses.field()
    
    @property
    def control(self) -> wx.Window:
        return self._control

    @property
    def control_value(self) -> Alphanumeric:
        return self._data

    def __post_init__(self, data = None):
        if data is None:
            data = []
        self.setup_display(data)
        
        self._control = None
        self._data = data
        self._column_names = []

        
        #self.bind_event_channel(wx.EVT_TREE_ITEM_RIGHT_CLICK)
        #self.event_channel.thenPermanent(ex)

    def setup_display(self,
                      data: Optional[Union[List[Mapping[str, str]], Mapping[str, str]]],
                      single_data: Any = None) -> None:
        if data is None or not len(data):
            return
        
        assert isinstance(data, (List, Mapping))
        
        if isinstance(data, Mapping):
            data = [data]
        
        self._setup_control()
        
        columns_created = False
        for item in data:
            assert isinstance(item, Mapping)
            
            if not columns_created:
                self.add_columns(item.keys())
                
                columns_created = True
            
            self._add_row(item, single_data)

    def add_item(self, item: Mapping[str, str], data: Any = None):
        if self._control is None:
            self.setup_display(item, data)
        else:
            self._add_row(item, data)

    def add_columns(self, column_names: List[str]):
        if self._control is None:
            self._setup_control()
        
        for name in column_names:
            self._control.AppendTextColumn(name)
            self._column_names.append(name)

    def _add_row(self, item: Mapping[str, str], data: Any):
        row = [item[name] for name in self._column_names if name in item]
        
        self._control.AppendItem(row)
        # if data is not None:
        #     self._control.AppendItem(row, data)
        # else:
        #     self._control.AppendItem(row)

    def _setup_control(self):
        self._control = wx.dataview.DataViewListCtrl(self.parent)

    @property
    def cursor_position(self) -> Tuple[Mapping[str, str], Any]:
        entry = self._control.GetSelection()
    

#######################
# selection, radio+checkbox buttons...
#######################

class Form(ABC):
    @property
    @abstractmethod
    def form(self) -> WxChild:
        pass
    
    @abstractmethod
    def get_values(self) -> Any:
        pass

class FormHolder(Form):
    @property
    def form(self) -> WxChild:
        return self._container
    
    def get_values(self) -> Dict[str, Alphanumeric]:
        if self._current_form is not None:
            return self._current_form.get_values()
        
        return {}
    
    def __init__(self, parent: wx.Window) -> None:
        super().__init__()
        
        self._parent = parent
        self._container = wx.BoxSizer()
        self._current_form = None
    
    def set_form(self, form: Form):
        if self._current_form is not None:
            self._container.Detach(self._current_form.form)
        
        self._container.Add(form.form, 1, wx.ALL)
        self._current_form = form


class KeyValueForm(Form):
    @property
    def form(self) -> WxChild:
        return self._container

    @property
    def schematic(self) -> Mapping[str, ValueReadableControl]:
        return types.MappingProxyType(self._schematic)

    def __init__(self, widget_parent: wx.Window) -> None:
        super().__init__()
        self._parent = widget_parent
        self._container = wx.BoxSizer(wx.VERTICAL)
        self._schematic: Dict[str, ValueReadableControl] = {}

    def add_keypair(self,
                    name: str,
                    form_input: ValueReadableControl,
                    display_name: Optional[str] = None
                    # sizing_proportion: KVFormRowProportion = (1, 1)
                    ) -> Tuple[wx.Sizer, wx.StaticText, ValueReadableControl]:
        if display_name is None:
            display_name = name
        
        label = wx.StaticText(self._parent, label=display_name, style=wx.ALIGN_CENTER)
        label.Wrap(-1)

        self._schematic[name] = form_input

        row_sizer = wx.BoxSizer()
        #####row_sizer.Add((0, 0), 1, wx.EXPAND)
        row_sizer.Add(label,
                      # sizing_proportion[0],
                      2,
                      wx.ALIGN_CENTER | wx.ALL)

        # This is lame
        # TODO
        if isinstance(form_input, TextInput):
            #####row_sizer.Add((0, 0), 1, wx.EXPAND)
            row_sizer.Add(form_input.control,
                          # sizing_proportion[1],
                          #####5,
                          3,
                          
                          border=5)
            #####row_sizer.Add((0, 0), 1, wx.EXPAND)
        else:
            right_sizer = wx.BoxSizer()
            
            #####row_sizer.Add((0, 0), 1, wx.EXPAND)
            right_sizer.Add(form_input.control,
                            # sizing_proportion[1],
                            3,
                            )
            right_sizer.Add((0, 0), 2, wx.EXPAND)
            
            row_sizer.Add(right_sizer, 3, wx.EXPAND, border=5)

        self._container.Add(row_sizer, 1, wx.EXPAND | wx.ALL, border=5)
        self._parent.Refresh()
        self._container.Layout()

        return row_sizer, label, form_input

    def add_submit_button(self) -> SubmitBtn:
        submit_btn = SubmitBtn(self._parent)
        self._schematic[SubmitBtn] = submit_btn

        self._container.Add(submit_btn.control, 0, wx.ALIGN_CENTER)
        self._parent.Refresh()
        return submit_btn

    def get_values(self) -> KVFormOutput:
        values = {}
        
        for name, control in self._schematic.items():
            if isinstance(control, ValueReadableControl):
                values[name] = control.control_value
            

        return values


class SingleControlForm(Form):
    @property
    def form(self) -> WxChild:
        return self._control.control
    
    @property
    def control(self) -> ValueReadableControl:
        return self._control
    
    def __init__(self,
                 form_input: ValueReadableControl) -> None:
        super().__init__()
        self._control = form_input

    def get_values(self) -> KVFormOutput:
        return self._control.control_value


class BulkForm(Form):
    @property
    def form(self) -> WxChild:
        return self._container

    # sizer_orientation: wx.HORIZONTAL or wx.VERTICAL
    def __init__(self, widget_parent: wx.Window, sizer_orientation) -> None:
        super().__init__()
        
        self._parent = widget_parent
        self._container = wx.BoxSizer(sizer_orientation)
        self._controls = {}

    def add_item(self, form_item: Control, proportion: int = 1):
        self._container.Add(form_item.control, proportion, wx.EXPAND | wx.ALL)
        self._parent.Refresh()

    def add_control(self, name: str, form_input: ValueReadableControl, proportion: int = 1):
        self._container.Add(form_input.control, proportion, wx.EXPAND | wx.ALL)
        self._parent.Refresh()
        
        self._controls[name] = form_input

    def add_submit_button(self) -> SubmitBtn:
        submit_btn = SubmitBtn(self._parent)
        self._controls[SubmitBtn] = submit_btn
        
        self._container.Add(submit_btn.control, 0, wx.ALIGN_CENTER)
        self._parent.Refresh()
        return submit_btn

    def get_values(self) -> KVFormOutput:
        values = {}

        for name, control in self._controls.items():
            if isinstance(control, ValueReadableControl):
                values[name] = control.control_value

        return values

class EvtDriverParametersForm(wx.BoxSizer):

    def __init__(self, parent, field_defs: Dict[str, Any]) -> None:
        super().__init__()

        self._parent = parent
        self._field_defs = field_defs
        self._fields = {}

        self.__build_form()

    def __build_form(self):
        for name, field_type in self._field_defs.items():
            HSizer = wx.BoxSizer(wx.HORIZONTAL)

            label = wx.StaticText(
                self, wx.ID_ANY, name, wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT)
            label.Wrap(-1)

            field = self._fields[name] = field_type.value(self._parent)
            HSizer.Add(label, 2, wx.ALIGN_CENTER | wx.ALL, 5)
            HSizer.Add(field, 3, wx.ALIGN_CENTER | wx.ALL, 5)

            self.Add(HSizer)


class ListenerDriverForm(wx.BoxSizer):
    def __init__(self, parent) -> None:
        super().__init__(wx.HORIZONTAL)

        self._parent = parent
        self._add_listener_tester()

    def _add_listener_tester(self):
        VSizer = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self._parent,
                             wx.ID_ANY,
                             "Received event",
                             wx.DefaultPosition,
                             wx.DefaultSize,
                             0)
        text.Wrap(-1)

        VSizer.Add(text, 1, wx.ALIGN_CENTER | wx.ALL, 5)

        self._event_loading_activity = wx.ActivityIndicator(self._parent)
        VSizer.Add(self._event_loading_activity, 0, wx.ALL, 5)

        self._action_btn = wx.Button(self._parent,
                                     wx.ID_ANY,
                                     'Start listening',
                                     wx.DefaultPosition,
                                     wx.DefaultSize,
                                     0)
        VSizer.Add(self._action_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)
        
        self.Add(VSizer)
        
        treeDisplay = wx.TreeCtrl(self._parent,
                                  wx.ID_ANY,
                                  wx.DefaultPosition,
                                  wx.DefaultSize,
                                  wx.TR_DEFAULT_STYLE)
        self.Add(treeDisplay, 3, wx.ALL, 5)


    def listen(self, observable: Observable):
        observable.subscribe(
            on_next=self._receive,
            #on_next=lambda _: self._event_loading_activity.Stop()
        )
        
        self._event_loading_activity.Start()
    
    def _receive(self, data: Iterable):
        assert isinstance(data, Iterable)
        
        