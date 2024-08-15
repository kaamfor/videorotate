from typing import Iterable, Dict, Any, Optional
import dirtyjson
from dirtyjson.attributed_containers import AttributedDict, AttributedList

import net.receiver as receiver
from net.receiver import ChangeEvent, IncomingEvent

class JSONParser(receiver.EventParser):
    def __call__(self, msg: IncomingEvent) -> Optional[ChangeEvent]:
        message_cleaned = dirtyjson.loads(
            str(msg),
            search_for_first_object=True
        )
        return ChangeEvent(
            value=message_cleaned,
            source=JSONParser
        )