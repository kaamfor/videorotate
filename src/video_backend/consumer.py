from dataclasses import dataclass
from typing import Any, List, Dict, Tuple, Callable, Optional
from functools import partial, cache
import sys
import multiprocessing
from multiprocessing import shared_memory
import threading
import queue
import cv2
import numpy as np

import videorotate_constants

from IFrameProcessAdapter import IFrameProcessAdapter

from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl

from video_backend.FilterBlockLogic import FilterBlockLogic

from video_backend.processing.register_bgr_transform import get_bgr_transform
from video_backend.processing.RGBFilterInput import RGBFilterInput

from videorotate_utils import print_exception, log_context, run_once_strict

from backend_context import BackendProcess, TaskProcess, ExtendedBackendProcess

@dataclass
class RGBSharedMemoryImage:
    filter_id: str
    width: int
    height: int
    frame_interval_ms: int = None

    buffer_name: str = None
    buffer_nsize: int = None
    ndarray_dtype: any = None
    ndarray_shape: any = None

    pending: bool = True


class RGBSharedMemoryAdapter(IFrameProcessAdapter):

    # access when input is available
    @property
    def width(self) -> int:
        return self._width

    # access when input is available
    @property
    def height(self) -> int:
        return self._height

    def __init__(self, shmem_image: RGBSharedMemoryImage) -> None:
        assert isinstance(shmem_image, RGBSharedMemoryImage)

        self._shmem_image = shmem_image

        self._width, self._height = 0, 0

    # overridden by the input block implementor if needed
    def backend__input__setup(self):
        if videorotate_constants.DEBUG:
            print('SHMEM SETUP STARTED')
            sys.stdout.flush()

        self._shmem = shared_memory.SharedMemory(
            self._shmem_image.buffer_name,
            create=False,
            size=self._shmem_image.buffer_nsize
        )
        self._ndarray = np.ndarray(
            self._shmem_image.ndarray_shape,
            dtype=self._shmem_image.ndarray_dtype,
            buffer=self._shmem.buf
        ).reshape(self._shmem_image.ndarray_shape)
        
        if videorotate_constants.DEBUG:
            print('SHMEM SETUP DONE')
            sys.stdout.flush()

    # overridden by the input block implementor if needed
    def backend__input__cleanup(self):
        self._shmem.close()

    # overridden by the input block implementor if needed
    def backend__input__grab_frame(self,
                                   ignore_cache: bool = False,
                                   invalidate_cache: bool = False,
                                   cache_new_frame_descriptor: bool = False
                                   ) -> Tuple[bool, np.ndarray, any]:

        self._width, self._height, _ = self._shmem_image.ndarray_shape

        return True, self._ndarray, object()

    # overridden by the input block implementor if needed
    def backend__input__is_ready(self, ignore_cache: bool) -> bool:
        return True

    # overridden by the input block implementor if needed
    def backend__input__set_callback(self, cb: Callable[[bool, np.ndarray, any], Any]):
        raise NotImplementedError()

    # overridden by the input block implementor if needed
    def backend__input__is_callback_available(self) -> bool:
        return False

class RecorderControl:
    # fixed file
    @property
    def filename_extension(self) -> str:
        return 'mp4'
    
    @property
    def active(self) -> bool:
        return self._active
    
    def __init__(self, fps: int, set_filepath: Optional[str] = None) -> None:
        self._fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        self._filepath = set_filepath
        self._active = False
        self._writer = None
        self._fps = fps
        
        self._input_queue = queue.Queue()
        self._writer_thread = None
    
    
    # TODO: optimize this (e.g. replace function before-after activating)
    def handle_recording(self, input: RGBFilterInput) -> bool:
        img = input.get_as_immutable_input(RGBFilterInput.ColorSpace.BGR)
        
        if self._active:
            if not self._writer:
                self._new_writer(input.width, input.height)
            
            if videorotate_constants.DEBUG:
                import sys
                print('WRITTEN_WABA', input.width, input.height, self._filepath, self._input_queue.qsize())
                sys.stdout.flush()
            self._input_queue.put_nowait(img)
        
        return img
    
    def activate(self, set_filepath: Optional[str] = None):
        if self._filepath is None and set_filepath is None:
            raise RuntimeError('Filepath not set')
        
        self.deactivate()
        
        self._writer_thread = threading.Thread(target=self._write_image)
        self._writer_thread.daemon = True
        self._writer_thread.start()
        
        self._filepath = set_filepath or self._filepath
        self._active = True
    
    def deactivate(self, set_filepath: Optional[str] = None):
        self._active = False
        
        if self._writer_thread is not None and self._writer_thread.is_alive():
            self._input_queue.put(None)

    def _new_writer(self, width: int, height: int):
        self._writer = cv2.VideoWriter(
                self._filepath,
                self._fourcc,
                self._fps,
                (width, height),
                isColor=True
            )
    
    @print_exception
    def _write_image(self):
        while True:
            img = self._input_queue.get()
            
            if img is None:
                if self._writer is not None and self._writer.isOpened():
                    self._writer.release()
                self._writer = None
                return
            self._writer.write(img)
    
# Consumer -> ExtendedBackendProcess+Consumer change
# TODO: make this fixed thing flexible, not wired in
class Consumer(TaskProcess, ExtendedBackendProcess):
    @property
    def adapter(self) -> Optional[IFrameProcessAdapter]:
        return self._adapter
    
    @adapter.setter
    def adapter(self, adapter: IFrameProcessAdapter):
        assert isinstance(adapter, IFrameProcessAdapter)

        self._adapter = adapter
    
    @property
    def backend__filter_tree(self) -> FilterBlockLogic:
        return self.__filter_tree
    
    # @property
    # @cache
    # def notifier(self) -> PropertyChangeNotifier:
    #     return PropertyChangeNotifier()
    
    def backend__start_processing(self):
        self.adapter.backend__input__setup()
        
        self.messenger_timeout_sec = 0.0
        self.backend__process_loop = self.backend__process_loop_extended
    
    # TODO: optimize instance creation
    def backend__process_image(self,
                               filter_input: RGBFilterInput,
                               metadata: any,
                               filters: List[Dict] = None):

        single_child = len(filters) == 1

        # Assume we can modify
        filter_input.configure(is_mutable=single_child)

        for filter_dict in filters:
            got_filter_dict = filter_dict['object']

            assert isinstance(got_filter_dict['filter_parameters'], dict)

            filter_cb = got_filter_dict['filter_obj']
            img_res = filter_cb(
                filter_input, **got_filter_dict['filter_parameters'])

            children = self.backend__filter_tree.get_children_filters(
                got_filter_dict['filter_id'])

            children_filter_input = filter_input
            # check if image's object (location) changed
            if img_res is not None and not filter_input.is_same_images(img_res):
                children_filter_input = RGBFilterInput.clone(filter_input)

                children_filter_input.configure(input=img_res)

            self.backend__process_image(
                children_filter_input, metadata, children)

    # return shmem object
    # assuming filter returns numpy array with the same size in the lifetime of output
    def backend__request_filter_output(self, filter_id) -> None:
        assert filter_id not in self.__shmem_output, 'one shmem output allowed per filter'

        if videorotate_constants.DEBUG:
            print('Request_filter_output', filter_id)
            sys.stdout.flush()

        filter_search = self.backend__filter_tree.get_filter_by_id(filter_id)
        if not filter_search:
            raise ValueError(f"Filter {filter_id} not found")

        filter_obj = filter_search['filter_obj']

        # Embed the setup code
        filter_obj['filter_shmem_output'] = {
            'filter_original': filter_obj['filter_obj'],
            'request': RGBSharedMemoryImage(filter_id, 0, 0)
        }
        
        if videorotate_constants.DEBUG:
            print('ffilter_array', filter_obj['filter_shmem_output'])
            sys.stdout.flush()

        # Setup function to acquire 'static' image metadata on first run
        def setup_filter_output(*args, **kwargs):
            img = filter_obj['filter_shmem_output']['filter_original'](
                *args, **kwargs)

            if videorotate_constants.DEBUG:
                print('FILTER_OUTPUT'+'1'*17)
                sys.stdout.flush()

            shmem_data = filter_obj['filter_shmem_output']['request']

            if not isinstance(img, np.ndarray):
                self.backend__revoke_filter_output(shmem_data)
                return

            shmem_data.buffer_nsize = img.nbytes
            shmem_data.height = img.shape[0]
            shmem_data.width = img.shape[1]
            shmem_data.ndarray_dtype = img.dtype
            shmem_data.ndarray_shape = img.shape

            if videorotate_constants.DEBUG:
                print('1')
                print()
                print(shmem_data.width, shmem_data.height)
                print()
                print('-1-')
                sys.stdout.flush()

            # TODO: multiple instance of filter output created? check this code
            shmem = self._backend__create_filter_output(shmem_data)

            shmem_data.buffer_name = shmem.name

            return img

        filter_obj['filter_obj'] = setup_filter_output

    # TODO: write documentation for ReplyControl handling - it's a delicate component which is very fragile
    # (changes the underlying functions' behavior unexpectedly)
    def backend__send_filter_output_when_ready(self, control: ReplyControl, filter_id):
        if videorotate_constants.DEBUG:
            print('Eleme eleme')
            sys.stdout.flush()

        filter_search = self.backend__filter_tree.get_filter_by_id(filter_id)
        
        if videorotate_constants.DEBUG:
            print('Eleme', filter_search)
            sys.stdout.flush()
        if not filter_search:
            raise ValueError(f"Filter {filter_id} not found")

        filter_obj = filter_search['filter_obj']

        # Embed setup code

        def send_and_unsubscribe(*args, **kwargs):
            filter_obj['filter_obj'] = filter_obj['filter_new_shmem_old_cb']
            del filter_obj['filter_new_shmem_old_cb']

            result = filter_obj['filter_obj'](*args, **kwargs)
            
            if videorotate_constants.DEBUG:
                print('FILTER_OUTPUT'+'2'*17)

            shmem_image = self.backend__get_stream_output(filter_id)

            self.backend_messenger.deferred_reply(control, shmem_image)

            return result

        filter_obj['filter_new_shmem_old_cb'] = filter_obj['filter_obj']

        filter_obj['filter_obj'] = send_and_unsubscribe

        control.keep_control = True
        # control.reply_to_message = False

    # receive
    def backend__get_stream_output(self, filter_id) -> RGBSharedMemoryImage:
        shmem_image = None

        if filter_id in self.__shmem_output:
            shmem_ready = self.__shmem_output[filter_id]['open']

            if shmem_ready:
                shmem_image = self.__shmem_output[filter_id]['shmem_image']

        if videorotate_constants.DEBUG:
            print('456'*34, filter_id in self.__shmem_output, filter_id)

        return shmem_image

    # Allowed to call multiple times under filter's lifecycle
    def backend__revoke_filter_output(self,
                                      shmem_image: RGBSharedMemoryImage,
                                      destroy_shmem: bool = True):
        assert isinstance(shmem_image, RGBSharedMemoryImage)

        filter_search = self.backend__filter_tree.get_filter_by_id(
            shmem_image.filter_id)

        if videorotate_constants.DEBUG:
            import sys
            print('REVOK:', shmem_image.buffer_name)
            print('searching, got', filter_search)
            sys.stdout.flush()

        if not filter_search:
            raise ValueError(f"Filter {shmem_image.filter_id} not found")

        filter_obj = filter_search['filter_obj']

        # Calling this method multiple times are permitted
        #  so watch out for indexing
        if 'filter_shmem_output' in filter_obj:
            # Restore filter callback
            filter_obj['filter_obj'] = filter_obj['filter_shmem_output']['filter_original']

            del filter_obj['filter_shmem_output']

        is_shmem_allocated = (not shmem_image.pending
                              and shmem_image.filter_id in self.__shmem_output)

        allocation = self.__shmem_output[shmem_image.filter_id]

        if videorotate_constants.DEBUG:
            print('shmem allocated?', is_shmem_allocated)
            sys.stdout.flush()

        if is_shmem_allocated:
            if allocation['open']:
                allocation['shmem'].close()
                allocation['open'] = False

            if destroy_shmem:
                allocation['shmem'].unlink()

                del self.__shmem_output[shmem_image.filter_id]

    def backend__save_stream_to_file(self,
                                     input_filter_id: Any,
                                     record_controller: RecorderControl):
        
        if videorotate_constants.DEBUG:
            import sys
            print('AFGFILTER', self.__filter_tree)
            sys.stdout.flush()
        
        output_filter = 'root_stream_out'
        if input_filter_id is not None:
            filter_search = self.backend__filter_tree.get_filter_by_id(
                input_filter_id)
            
            if not filter_search:
                raise ValueError(f"Filter {input_filter_id} not found")

            output_filter = str(input_filter_id)+'_stream_out'
            
            child_search = self.backend__filter_tree.get_filter_by_id(output_filter)
            if child_search:
                raise ValueError(f"Stream output for filter {input_filter_id} is exists!")

        self.__filter_tree.add_filter(
            output_filter,
            input_filter_id,
            {
                'filter': output_filter,
                'filter_obj': record_controller.handle_recording,
                'record_controller': record_controller,
                'filter_parameters': { }
            }
        )
        
        if videorotate_constants.DEBUG:
            import sys
            print('FGFILTER', self.__filter_tree)
            sys.stdout.flush()
    
    def backend__process_loop_extended(self):
        super().backend__process_loop()
        
        is_ready, img, metadata = self.adapter.backend__input__grab_frame()
        if is_ready:
            if videorotate_constants.DEBUG:
                print(img.shape)
                sys.stdout.flush()

            self.backend__process_image(
                RGBFilterInput(img, False, RGBFilterInput.ColorSpace.RGB),
                metadata,
                self.backend__filter_tree.list_matching_filters(max_level=0))
    
    def backend__setup(self):
        super().backend__setup()
        self.__filter_tree = FilterBlockLogic()
        
        # {filter_id: {'shmem': SharedMemory, 'open': bool}, ..}
        self.__shmem_output = {}
    
    def backend__exit(self):
        self.adapter.backend__input__cleanup()
        super().backend__exit()


    # def backend__add_filter(self, filter: str, filter_id, parent_id, filter_parameters: dict = None):
    #     assert filter_parameters is None or isinstance(filter_parameters, dict)

    #     filter_obj = get_bgr_transform(filter)

    #     # if not filter_obj:
    #     #     raise ValueError(f"Filter {filter} not found")

    #     # parent_search = None
    #     # if parent_id is not None:
    #     #     parent_search = self.__backend_tree.get_filter_by_id(parent_id)
    #     #     if parent_search is None:
    #     #         raise ValueError(f"Parent filter {parent_id} not found")

    #     #     parent = parent_search['filter_obj']

    #     self.__backend_tree.add_filter(filter_id, parent_id, {
    #         'filter_obj': filter_obj,
    #         'filter_parameters': filter_parameters or {}
    #     })

    #     print()
    #     print(parent_id, self.__backend_tree._filters)
    #     print()
    #     sys.stdout.flush()

    # def backend__change_filter(self, filter_id, filter_parameters: dict = None):
    #     if filter_parameters is None:
    #         return

    #     assert isinstance(filter_parameters, dict)

    #     filter_search = self.__backend_tree.get_filter_by_id(filter_id)

    #     if not filter_search:
    #         raise ValueError(f"Filter {filter_id} not found")

    #     filter_obj = filter_search['filter_obj']

    #     print('ADD', filter_parameters, 'TO', filter_obj)
    #     sys.stdout.flush()

    #     filter_obj.update(filter_parameters)
    #     print('AFTER ADD:', filter_obj)

    # def backend__delete_filter(self, filter_id: str):
    #     # free up/move shmem object before delete
    #     raise NotImplementedError

    

    def _backend__create_filter_output(self, shmem_image: RGBSharedMemoryImage):
        filter_search = self.backend__filter_tree.get_filter_by_id(
            shmem_image.filter_id)

        assert filter_search, f"Filter {shmem_image.filter_id} not exists?"

        filter_obj = filter_search['filter_obj']

        shmem = shared_memory.SharedMemory(
            create=True, size=shmem_image.buffer_nsize)

        ndarray_shape = shmem_image.ndarray_shape

        self.__shmem_output[shmem_image.filter_id] = {
            'shmem_image': shmem_image,
            'shmem': shmem,
            'shmem_ndarray': np.ndarray(ndarray_shape, dtype=shmem_image.ndarray_dtype, buffer=shmem.buf),
            'open': True
        }
        filter_entry = self.__shmem_output[shmem_image.filter_id]

        def img_copy_proxy(*args, **kwargs):
            img = filter_obj['filter_shmem_output']['filter_original'](
                *args, **kwargs)

            np.copyto(filter_entry['shmem_ndarray'], img)
            return img

        filter_obj['filter_obj'] = img_copy_proxy
        shmem_image.pending = False

        return shmem


if __name__ == '__main__':
    class ABCUG(IFrameProcessAdapter):
        pass

    from multiprocessing import Pipe
    consumer = RGBConsumer()

    front_pipe, back_pipe = Pipe()
    messenger = FilterProcessDispatcher(front_pipe, back_pipe)

    consumer.frontend__set_dispatcher(messenger)
    consumer.frontend__set_adapter(ABCUG())

    consumer.start()

    print('run OK')

    # test
    messenger.messenger__send_message(None, 'etap')

    import time
    time.sleep(4)
    print('Terminating..')
    messenger.messenger__send_message(None, 'dispose')
