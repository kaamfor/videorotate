from operator import itemgetter
from functools import cache, partial
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable, Any, Union


from messenger import Promise

import videorotate_constants

# Anything picklable
KeyId = Any


# Creates comm. channel between messenger and gui controller class with properties

run_once = cache

# Pass input directly to the listener


# @dataclass
# class TriggerPolicy:
#     key: KeyId
#     property_list: dict
#     store_change: bool = False
#     invalidate_cache: bool = False
#     mask_handler: Optional[List[str]] = None


@dataclass
class UpdateBase:
    key: KeyId
    value: Any
    
    def extract_nested_value(self) -> Any:
        update = self
        while isinstance(update.value, Update):
            update = update.value
        return update.value


@dataclass
class Update(UpdateBase):
    emitted_by: Optional[Any] = None
    # override_policy: Optional[TriggerPolicy] = None


ProxyPromiseValueCallback = Callable[[Update], Any]

# class TriggerResult:
#     def __repr__(self) -> str:
#         return (f"{self.__class__.__name__}: Callback results: {self._cb_results}, "
#                 f"Messenger callback results: {self._messenger_cb_results}")


class UpdateChannel(Promise):
    def __init__(self) -> None:
        self._callbacks: List[ProxyPromiseValueCallback] = []

    def thenPermanent(self, promise_callback: ProxyPromiseValueCallback):
        self._callbacks.append(promise_callback)
    
    def subscribe(self, promise_callback: ProxyPromiseValueCallback):
        return self.thenPermanent(promise_callback)
    def unsubscribe(self, promise_callback: ProxyPromiseValueCallback):
        self._callbacks.remove(promise_callback)

    def send_to(self, destination_channel: 'UpdateChannel'):
        self.thenPermanent(destination_channel.send)

    def receive_from(self, source_channel: 'UpdateChannel'):
        source_channel.thenPermanent(self.send)

    def send(self, update: Update):
        assert isinstance(update, Update)

        for cb in self._callbacks:
            cb(update)


class MultiContextChannel(UpdateChannel, ABC):
    @abstractmethod
    def deregister_context(self):
        pass


@dataclass
class MultiContextUpdateBase(UpdateBase):
    pass


@dataclass
class MultiContextUpdate(MultiContextUpdateBase, Update):
    context_channel: Optional[MultiContextChannel] = None

# https://medium.com/@abulka/async-await-for-wxpython-c78c667e0872 ?
# decoupler
# separator
# isolator?
# aggregator
# redirector
# collector
# distributor, propagate
# proxy
# known, trackable sources; update channel; handler
class Distributor(UpdateChannel):
    class _TappedChannel(UpdateChannel):
        def __init__(self, aggregated_listener: UpdateChannel) -> None:
            super().__init__()
            self._aggregated_listener = aggregated_listener

        def send(self, update: Update):
            res = super().send(update)
            self._aggregated_listener.send(update)
            return res

    @dataclass
    class _PropertyMetadata:
        root_listener: UpdateChannel  # actually its _TappedChannel
        referenced_sources: List[Promise]

    def __init__(self) -> None:
        self._property: Dict[KeyId, Distributor._PropertyMetadata] = {}
        self._aggregated_listener = UpdateChannel()

    # TODO: naming convention - get initialized metadata?
    def _get_metadata(self, property_id: KeyId, create_on_demand: bool = False) -> _PropertyMetadata:
        if property_id not in self._property:
            if not create_on_demand:
                raise RuntimeError(f"Channel {property_id} not exists")

            new_channel = Distributor._TappedChannel(self._aggregated_listener)
            self._property[property_id] = Distributor._PropertyMetadata(new_channel, [])

        return self._property[property_id]

    def subscribe(self, property_id: KeyId, must_exists: bool = True) -> UpdateChannel:
        return self._get_metadata(property_id, not must_exists).root_listener

    def init_channel(self, property_id: KeyId, fail_if_exists: bool = True) -> None:
        if fail_if_exists and property_id in self._property:
            raise RuntimeError(f"Channel {property_id} exists")
        
        self._get_metadata(property_id, True)

    def add_source(self,
                   property_id: KeyId,
                   source: Promise,
                   store_source: bool = True,
                   must_exists: bool = False) -> None:
        metadata = self._get_metadata(property_id, not must_exists)

        source.thenPermanent(metadata.root_listener.send)
        if store_source:
            metadata.referenced_sources.append(source)

    def update(self, update: Update) -> None:
        if videorotate_constants.DEBUG:
            print('TRGGER', update)

        metadata = self._get_metadata(update.key)
        metadata.root_listener.send(update)

    def send(self, update: Update):
        return self.update(update)

    def thenPermanent(self, promise_callback: ProxyPromiseValueCallback, property_id: Optional[KeyId] = None):
        if property_id is not None:
            return self._property[property_id].root_listener.thenPermanent(promise_callback)

        return self._aggregated_listener.thenPermanent(promise_callback)
