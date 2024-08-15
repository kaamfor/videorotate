import json
from typing import Mapping, Sequence, Dict
import dataclasses

import gui.datamodel
import gui.backend.event.processing as event_processing
import gui.backend.event.receiver as event_receiver
import net.receiver

from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver
from gui.backend.event.receiver import FlattenedJSONParser

def load_config(filepath: str) -> Mapping[str, gui.datamodel.Recorder]:
    data = None
    recorder_collection = {}
    
    with open(filepath, "r") as savefile:
        data = json.load(savefile)
    
    for name, recorder_data in data.items():
        evt_processor_setup_done = False
        
        recorder_data['recorder_stage'] = RGBFilterTerminal
        recorder = gui.datamodel.Recorder(
            **recorder_data
        )
        
        if recorder_data['event_driver'] is not None:
            recorder.event_driver = gui.datamodel.EventDriver(
                ThreadedEventReceiver,
                {
                    **recorder_data['event_driver']['provider_parameters']
                }
            )
        
        
            recparams_base = recorder_data['event_driver']['provider_parameters']
            if 'processor' in recparams_base:
                processor_data = recparams_base['processor']
                
                if isinstance(processor_data, Dict):
                    processor_data.setdefault('distributor', {})
                    
                    rule_container = []
                    
                    for rule in processor_data['distributor']['rules']:
                        rule_obj = event_processing.TriggerConditions(**rule)
                        
                        rule_obj.criterion_list = []
                        for criterion in rule['criterion_list']:
                            crit_obj = event_processing.TriggerCriterion(**criterion)
                            
                            crit_obj.comparison = event_processing.ValueComparison[criterion['comparison']]
                            
                            rule_obj.criterion_list.append(crit_obj)
                        
                        rule_obj.state_on_match = event_processing.SimpleTrigger[rule['state_on_match']]
                        
                        rule_container.append(rule_obj)

                    processor_data['distributor']['rules'] = rule_container
                    
                    processor_data['parser'] = event_receiver.FlattenedJSONParser
                    processor_data['distributor'] = event_receiver.BinaryRuledTrigger(
                        **processor_data['distributor']
                    )

                    recparams_base['processor'] = net.receiver.EventProcessor(
                        **processor_data
                    )
                    
                    evt_processor_setup_done = True

    
        if recorder.event_driver is not None and evt_processor_setup_done:
            driver_params = recorder.event_driver.provider_parameters
            
            driver_params['processor'] = recparams_base['processor']
        
        recorder_collection[name] = recorder
    
    
    return recorder_collection

def save_config(filepath: str, config: Mapping[str, gui.datamodel.Recorder]):
    output_data = {}
    
    for name, recorder in config.items():
        dict_data = dataclasses.asdict(recorder)
        del dict_data['recorder_stage']  # RGBFilterTerminal
        
        if dict_data['event_driver'] is not None:
            del dict_data['event_driver']['provider_stage']  # ThreadedEventReceiver
        
            recparams_base = dict_data['event_driver']['provider_parameters']
            if 'processor' in recparams_base:
                del recparams_base['processor']['parser'] # gui.backend.event.receiver.FlattenedJSONParser
            
                for rule in recparams_base['processor']['distributor']['rules']:
                    rule['state_on_match'] = rule['state_on_match'].name
                    
                    for criterion in rule['criterion_list']:
                        criterion['comparison'] = criterion['comparison'].name
        
        # # duplicate
        # if dict_data['event_driver'] is not None and 'processor' in dict_data['event_driver']['provider_parameters']:
        #     del dict_data['event_driver']['provider_parameters']['processor']
        
        output_data[name] = dict_data
    
    with open(filepath, "w") as savefile:
        json.dump(output_data, savefile)
    
