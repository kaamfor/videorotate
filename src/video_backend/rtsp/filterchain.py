from collections import deque
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Tuple, Optional
from functools import cache, partial
import numpy as np
from dataclasses import dataclass
from multiprocessing import Process
import socket
import time

from valkka.core import ForkFrameFilterN, LiveConnectionContext
from valkka.core import LiveConnectionContext, LiveConnectionType_rtsp
from valkka.core import LiveOutboundContext, LiveConnectionType_sdp
from valkka.core import LiveThread, AVThread
from valkka.core import FrameFilter
from valkka.core import RGBShmemFrameFilter, SwScaleFrameFilter, TimeIntervalFrameFilter, setLiveOutPacketBuffermaxSize

from valkka.api2 import ShmemRGBClient
from valkka.core import ValkkaFSWriterThread, FrameFifoContext
from valkka.fs import ValkkaSingleFS, ValkkaFSLoadError

from IFrameProcessAdapter import IFrameProcessAdapter
from video_backend.rtsp.pipeline.Middleware import Middleware

from valkka.fs import ValkkaSingleFS, ValkkaFSLoadError
from valkka.api2 import ValkkaFSManager
#from valkka.fs.manager import ValkkaFSManager

run_once = cache

# WARNING: every Valkka object has to be linked somewhere else the GC will free up
# TODO: deregister context?

@dataclass
class DecoderSpec:
    child_fork_name: str
    decoder_name: str
    avthread_name: str
    #slot_id: int
    
    def create(self): # -> FilterchainDecoder
        return FilterchainDecoder(self)

class RecordingMode(Enum):
    NoAuto = 0,
    Timer = 1,
    Alarm = 2,
    Always = 3


@dataclass
class RGBProcessLink:
    shmem_segment_name: str
    shmem_buffer_size: int
    # used_framefilters: List[FrameFilter]
    width: int
    height: int
    frame_interval_ms: int
    con_timeout_ms: int
    # sync_fd: any
# ENHANCEMENT: use sync_fd instead of time.sleep

@dataclass
class _RGBDecodingTerminalNeccessaryOptions:
    #parent_filter_fork_name: str
    
    #avthread_filter_fork_name: str
    avthread_fork_filter_basename: str
    shmem_filter_name: str
    shmem_buffer_size: int
    width: int
    height: int
    con_timeout_ms: int

@dataclass
class RGBDecodingTerminalData(_RGBDecodingTerminalNeccessaryOptions):
    frame_interval_ms: int = None
    sync_fd = None
    middleware: Middleware = None

@dataclass
class RGBDecodingTerminalComponents(_RGBDecodingTerminalNeccessaryOptions):
    avthread_filter_fork: ForkFrameFilterN
    
    frame_interval_ms: int = None
    sync_fd = None
    middleware: Middleware = None

class RGBAdapter(IFrameProcessAdapter):

    @property
    def link(self):
        return self._link

    # access when input is available
    @property
    def width(self) -> int:
        return self._width

    # access when input is available
    @property
    def height(self) -> int:
        return self._height

    def __init__(self, link) -> None:
        assert isinstance(
            link, RGBProcessLink)

        self._link = link
        self._initialized = False

        self._width, self._height = 0, 0

    # implemented by the input block
    def backend__input__setup(self):
        if self._initialized:
            raise RuntimeError('Setup did run before')

        lattr = partial(getattr, self._link)

        ringbuffer_size = lattr('shmem_buffer_size')

        self._client = ShmemRGBClient(
            name=lattr('shmem_segment_name'),
            n_ringbuffer=ringbuffer_size,
            width=lattr('width'),
            height=lattr('height'),
            mstimeout=lattr('con_timeout_ms')
        )

        self._cached_indices = deque([], ringbuffer_size)
        self._cache_is_empty = True

        self._initialized = True

    # implemented by the input block
    def backend__input__cleanup(self):
        if not self._initialized:
            return

        del self._client

        self._initialized = False

    def backend__wait_one_frame_interval(self):
        # time.sleep(self._link.frame_interval_ms / 1000.0)
        # wait_frame = not self.backend__input__is_ready(False)
        pass

    # implemented by the input block
    # WARNING: no check on '_initialized' for performance reasons
    # Explain parameters via behaviour
    # - (internal) cache_is_empty - do we _have to_ retrieve new frame?
    # - ignore_cache - de we _want to_ retrieve new frame?
    # - invalidate_cache - do we _have to_ retrieve new frame _before_ invalidating cache?
    #   <- frame source still depends on 'ignore_cache' value

    def backend__input__grab_frame(self,
                                   ignore_cache: bool = False,
                                   invalidate_cache: bool = False,
                                   cache_new_frame_descriptor: bool = False,
                                   ) -> Tuple[bool, np.ndarray, any]:

        new_frame_required = ignore_cache or self._cache_is_empty

        shmem_index, metadata = None, None
        if not new_frame_required:
            shmem_index, metadata = self._cached_indices.popleft()
            self._cache_is_empty = not len(self._cached_indices)

        if invalidate_cache:
            self._cached_indices.clear()
            self._cache_is_empty = True

        if new_frame_required:
            shmem_index, metadata = self._client.pullFrame()

            if shmem_index is None:
                # Image not yet available
                # Waiting..
                self.backend__wait_one_frame_interval()

                shmem_index, metadata = self._client.pullFrame()

                # Last chance
                if shmem_index is None:
                    return False, None, None

            if cache_new_frame_descriptor:
                self._cached_indices.append((shmem_index, metadata))
                self._cache_is_empty = False

        img_data = self._client.shmem_list[shmem_index][0:metadata.size]

        img = img_data.reshape((metadata.height, metadata.width, 3))

        # set params
        self._width, self._height = metadata.width, metadata.height

        return True, img, metadata

    # implemented by the input block
    def backend__input__is_ready(self, ignore_cache: bool) -> bool:
        is_ready, _, _ = self.backend__input__grab_frame(
            ignore_cache=ignore_cache,
            cache_new_frame_descriptor=True
        )

        return is_ready


class RGBDecodingTerminal:
    def __init__(self, terminal_data: RGBDecodingTerminalComponents) -> None:
        data = self._terminal_data = terminal_data

        self.middleware = None
        self.__middleware_framefilter_storage = []

        # assert isinstance(fixed_fps, int) or sync_fd is not None
        
        swscale_filter_name = data.avthread_fork_filter_basename + '_swscale'

        fpslimiter_middleware = None
        if data.frame_interval_ms is not None:
            fpslimiter_filter_name = swscale_filter_name+'_fpslimiter'

            fpslimiter_middleware = Middleware(
                lambda child:
                    self.__add_middleware_framefilter(
                        TimeIntervalFrameFilter(
                            fpslimiter_filter_name,
                            data.frame_interval_ms,
                            child
                        ))
            )

        swscale_middleware = Middleware(
            lambda child:
                self.__add_middleware_framefilter(
                    SwScaleFrameFilter(
                        swscale_filter_name,
                        data.width,
                        data.height,
                        child
                    )
                ),
                fpslimiter_middleware
        )
        self.middleware = swscale_middleware

    def add_output(self, output_suffix: str, sync_fd=None):
        assert isinstance(output_suffix, str)
        
        data = self._terminal_data

        output_reference_name = data.shmem_filter_name + '_' + output_suffix

        shmem_filter = self.__add_middleware_framefilter(
            RGBShmemFrameFilter(output_reference_name,
                                data.shmem_buffer_size,
                                data.width,
                                data.height,
                                data.con_timeout_ms
                                )
        )

        if sync_fd is not None:
            shmem_filter.useFd(sync_fd)

        decoding_chain_input = None
        if self.middleware is None:
            # swScale is required
            raise RuntimeError('Middleware is required but not exists')

        decoding_chain_input = self.middleware.generate_filter(
            shmem_filter)

        self._shmem_filter_link = RGBProcessLink(
            shmem_segment_name=output_reference_name,
            shmem_buffer_size=data.shmem_buffer_size,
            width=data.width,
            height=data.height,
            frame_interval_ms=data.frame_interval_ms,
            con_timeout_ms=data.con_timeout_ms
        )

        data.avthread_filter_fork.connect(data.avthread_fork_filter_basename + '_' + output_suffix,
                                           decoding_chain_input)

        return self._shmem_filter_link

    def __add_middleware_framefilter(self, framefilter):
        self.__middleware_framefilter_storage.append(framefilter)
        return framefilter

    def __get_middleware_framefilters(self):
        return self.__middleware_framefilter_storage

class IFilterchainSource(ABC):
    @property
    @abstractmethod
    def root_fork(self) -> ForkFrameFilterN:
        pass
    
    @abstractmethod
    def start(self):
        pass
    
    @abstractmethod
    def stop(self):
        pass

@dataclass
class SourceSpec(ABC):
    root_fork_name: str
    source_livethread_name: str
    source_slot_id: int
    
    @abstractmethod
    def create(self) -> IFilterchainSource:
        pass

@dataclass
class RTSPStreamSpec(SourceSpec):
    stream_url: str
    source_timeout_ms: int
    
    # lot of options missing?
    def create(self) -> IFilterchainSource:
        return FilterchainNetworkSource(self)

@dataclass
class RecordDirSpec(SourceSpec):
    input_dir_path: str
    
    # lot of options missing?

class FilterchainNetworkSource(IFilterchainSource):
    
    def __init__(self, input_stream: RTSPStreamSpec) -> None:
        self._input_stream = input_stream
        
        self._main_fork = None
        self._create_filterchain()
    
    @property
    def input_stream(self) -> RTSPStreamSpec:
        return self._input_stream
    
    @property
    def root_fork(self):
        return self._main_fork

    def start(self):
        self.enable_receiver()
    
    def stop(self):
        self.disable_receiver()

    def enable_receiver(self, start_receiving: bool = True):
        import multiprocessing

        if not getattr(self, '_src_livethread_running', False):
            print(
                f' <{multiprocessing.current_process().name}> START INPUT THREAD <{id(self._src_livethread)}> <{id(self._con_ctx)}>')
            self._src_livethread.startCall()
            self._src_livethread_running = True

        playing = getattr(self, '_src_livethread_playing', False)

        if start_receiving and not playing:
            print(
                f' <{multiprocessing.current_process().name}> RECEIVE INPUT <{id(self._src_livethread)}> <{id(self._con_ctx)}>')
            self._src_livethread.playStreamCall(self._con_ctx)
            self._src_livethread_playing = True

    def stop_receiver(self, disable_thread: bool = False):
        playing = getattr(self, '_src_livethread_playing', False)

        import multiprocessing

        if playing:
            print(
                f' <{multiprocessing.current_process().name}> STOP RECEIVE INPUT <{id(self._src_livethread)}> <{id(self._con_ctx)}>')
            self._src_livethread.stopStreamCall(self._con_ctx)
            self._src_livethread_playing = False

        if getattr(self, '_src_livethread_running', False) and disable_thread:
            print(
                f' <{multiprocessing.current_process().name}> STOP INPUT THREAD <{id(self._src_livethread)}> <{id(self._con_ctx)}>')
            self._src_livethread.stopCall()
            self._src_livethread_running = False

    def disable_receiver(self):
        return self.stop_receiver(True)

    def _create_filterchain(self):
        import multiprocessing
        print(
            f"========================== FILTERCHAIN SETUP <{multiprocessing.current_process().name}> =================")

        # test
        setLiveOutPacketBuffermaxSize(95000)

        # LiveThread
        self._src_livethread = LiveThread(
            self.input_stream.source_livethread_name)

        # Connection + Fork
        self._main_fork = ForkFrameFilterN(self.input_stream.root_fork_name)

        self._con_ctx = LiveConnectionContext(LiveConnectionType_rtsp,
                                              self.input_stream.stream_url,
                                              self.input_stream.source_slot_id,
                                              self._main_fork)

        print(
            f"IN:  {LiveConnectionType_rtsp} {str(self.input_stream.stream_url)}")
        # NAT or Internet-streaming?:
        # self._con_ctx.request_tcp = True
        # Timeout
        if self.input_stream.source_timeout_ms is not None:
            self._con_ctx.mstimeout = self.input_stream.source_timeout_ms

        # Add/set ConnectionContext
        self._src_livethread.registerStreamCall(self._con_ctx)

        print(
            f'========================== FILTERCHAIN SETUP DONE <{id(self._src_livethread)}> <{id(self._con_ctx)}> =================')


    def _is_port_open(self, host: str, port: int):
        address = (str(host), int(port))

        try:
            with socket.create_server(address, reuse_port=True):
                return True
        except Exception as e:
            import sys
            print(e)
            sys.stdout.flush()

        return False


# class FilterchainPlaybackSource(IFilterchainSource):
    
#     def __init__(self, input_dir: RecordDirSpec) -> None:
#         self._input_dir = input_dir
        
#         self._main_fork = None
#         self._recording_objects = {}
#         self._create_filterchain()
    
#     @property
#     def root_fork(self):
#         return self._main_fork
    
#     ############################################## NOT WORKING!
#     def _create_filterchain(self):
#         import multiprocessing
#         print(
#             f"========================== FILTERCHAIN SETUP <{multiprocessing.current_process().name}> =================")

#         # test
#         setLiveOutPacketBuffermaxSize(95000)

#         # LiveThread
#         self._src_livethread = LiveThread(
#             self.input_stream.source_livethread_name)

#         # Connection + Fork
#         self._main_fork = ForkFrameFilterN(self.input_stream.root_fork_name)

#         self._con_ctx = LiveConnectionContext(LiveConnectionType_rtsp,
#                                               self.input_stream.input_address,
#                                               self.input_stream.source_slot_id,
#                                               self._main_fork)

#         print(
#             f"IN:  {LiveConnectionType_rtsp} {str(self.input_stream.input_address)} {int(self.input_stream.input_address)}")
#         # NAT or Internet-streaming?:
#         # self._con_ctx.request_tcp = True
#         # Timeout
#         if self.input_stream.source_timeout_ms is not None:
#             self._con_ctx.mstimeout = self.input_stream.source_timeout_ms

#         # Add/set ConnectionContext
#         self._src_livethread.registerStreamCall(self._con_ctx)

#         print(
#             f'========================== FILTERCHAIN SETUP DONE <{id(self._src_livethread)}> <{id(self._con_ctx)}> =================')


class FilterchainDecoder:
    def __init__(self, decoder_spec: DecoderSpec) -> None:
        self._decoder_spec = decoder_spec
        self._output_fork = ForkFrameFilterN(decoder_spec.child_fork_name)
        
        self._create_decoder()
        self._decoder_enabled = False
        self._decoder_running = False
    
    @property
    def output_fork(self) -> ForkFrameFilterN:
        return self._output_fork
    
    @property
    def input_framefilter(self) -> FrameFilter:
        return self._avthread_filter
    
    def start_decoder_thread(self, start_decoding: bool = True):
        if not self._decoder_enabled:
            self._avthread.startCall()
            self._decoder_enabled = True
        
        if not self._decoder_running and start_decoding:
            self._avthread.decodingOnCall()
            self._decoder_running = True

    def stop_decoding(self, stop_thread: bool = False):
        if self._decoder_running and stop_thread:
            self._avthread.decodingOffCall()
            self._decoder_running = False
        
        if self._decoder_enabled:
            self._avthread.stopCall()
            self._decoder_enabled = False

    def kill_decoder(self):
        return self.stop_decoding(True)
    
    # return (input-FrameFilter, decoded-ForkFrameFilterN)
    def _create_decoder(self) -> FrameFilter:
        avthread_name = self._decoder_spec.avthread_name
        #slot_id = self._decoder_spec.slot_id

        self._avthread = AVThread(avthread_name, self.output_fork)
        self._avthread_filter = self._avthread.getFrameFilter()


# class FilterchainRecorder:
    
#     @property
#     def input_filter(self) -> FrameFilter:
#         return self._input_filter
    
#     @property
#     def fs(self) -> ValkkaSingleFS:
#         return self._fs

#     @property
#     def manager(self) -> ValkkaFSManager:
#         return self._manager

#     def __init__(self,
#                  dirname: str,
#                  writer_slot_id: int,
#                  source_slot_id: int,
#                  output_fork: ForkFrameFilterN) -> None:
#         self._create_recorder(dirname)
        
#         # self._inputfilter = ForkFrameFilterN('aaaakamar')
        
#         # valkka-examples magic constants
#         # self._framefifo_ctx = FrameFifoContext()
#         # self._framefifo_ctx.n_basic = 20
#         # self._framefifo_ctx.n_setup = 20
#         # self._framefifo_ctx.n_signal = 20
#         # self._framefifo_ctx.flush_when_full = True
#         # import sys
#         # print('AKARMI')
#         # sys.stdout.flush()
#         # self._avthread = AVThread(
#         #     'avthread_name',
#         #     output_fork,
#         #     self._framefifo_ctx
#         # )
#         # self._inputfilter = self._avthread.getBlockingFrameFilter()
        
#         # self._manager.map_(
#         #     valkkafs=self.fs,
#         #     framefilter=self.input_filter,
#         #     write_slot=writer_slot_id,
#         #     read_slot=source_slot_id,
#         #     _id=writer_slot_id
#         # )
#         self._manager.setOutput(
#             _id=writer_slot_id,
#             slot=source_slot_id,
#             framefilter=output_fork
#         )
#         self._output_fork = output_fork
#         #for fs, inputfilter in self._manager.iterateFsInput():
#         import sys
#         print('GAGABABA')
#         sys.stdout.flush()

#     def _backend__create_decoder_fork(self, parent_fork_name: str, decoder_name: str):
#         assert isinstance(parent_fork_name, str)
#         assert isinstance(decoder_name, str)

#         decoder = self._decoder_objects[decoder_name] = {}

#         decoder_fork_name = parent_fork_name+'_'+decoder_name
#         avthread_name = decoder_fork_name+'_avthread'+self.input_stream.input_address+'_'+decoder_name
#         avthread_connection = decoder_fork_name + \
#             '_connect_avthread'+self.input_stream.input_address+'_'+decoder_name

#         decoder['fork'] = ForkFrameFilterN(decoder_fork_name)

#         avthread = AVThread(avthread_name, decoder['fork'])

#         decoder['avthread'] = avthread.getFrameFilter()

#         decoder['fork'].connect(avthread_connection, decoder['avthread'])

#         return decoder['avthread']

#     def start_recording(self, writer_thread_name: str):
#         is_changed = _object_set_status(
#             self._recording_objects,
#             writer_thread_name,

#             target_status=True,
#             callback_with_object=lambda target: target['writer_thread'].startCall(
#             ),
#             err_id_not_in_container_msg=f"Recording {writer_thread_name} not found",
#             status_key='recorder_enabled'
#         )
#         print(
#             f"Trying to start recording thread, is status changed: {is_changed}")

#     def stop_recording(self, writer_thread_name: str):
#         is_changed = _object_set_status(
#             self._recording_objects,
#             writer_thread_name,

#             target_status=False,
#             callback_with_object=lambda target: target['writer_thread'].stopCall(
#             ),
#             err_id_not_in_container_msg=f"Recording {writer_thread_name} not found",
#             status_key='recorder_running'
#         )
#         print(f"Trying to stop recording, is status changed: {is_changed}")

#     def delete_recorder(self, writer_thread_name: str):

#         # Raises exception if livethread not exists
#         self.stop_recording(writer_thread_name)
#         del self._recording_objects[writer_thread_name]

#     def _backend__new_recording_dir(self,
#                                     dirname: str,
#                                     blocksize: int,
#                                     n_blocks: int):
#         print("It's verbose")
#         ValkkaSingleFS.newFromDirectory(dirname=dirname,
#                                         blocksize=blocksize,
#                                         n_blocks=n_blocks,
#                                         verbose=True)

#     def _is_recording_dir_exists(self, dirname: str):
#         try:
#             print("It's verbose")
#             ValkkaSingleFS.loadFromDirectory(dirname=dirname,
#                                              verbose=True)
#         except ValkkaFSLoadError:
#             return False

#         return True

#     def add_recording(self,
#                                writer_thread_name: str,
#                                dirname: str) -> FrameFilter:
#         if writer_thread_name in self._decoder_objects:
#             raise ValueError(f"Writer thread {writer_thread_name} is exists")

#         print("It's verbose")
#         valkkafs = ValkkaSingleFS.loadFromDirectory(dirname=dirname,
#                                                     # blocksize=blocksize,
#                                                     # n_blocks=n_blocks,
#                                                     verbose=True)

#         recorder = self._recording_objects[writer_thread_name] = {}
#         writer_thread = ValkkaFSWriterThread(writer_thread_name, valkkafs.core)
#         framefilter = writer_thread.getFrameFilter()

#         recorder['valkkafs'] = valkkafs
#         recorder['writer_thread'] = writer_thread
#         recorder['writer_thread_filter'] = framefilter

#         print('EXPERIMENTAL!!!:')
#         recorder['writer_thread'].setSlotIdCall(
#             self.input_stream.input_address, 925412)

#         return recorder['writer_thread_filter']
    
#     def _create_recorder(self, dirname: str):
#         try:
#             import sys
#             print("It's verbose")
#             sys.stdout.flush()
#             self._fs = ValkkaSingleFS.loadFromDirectory(dirname=dirname,
#                                              verbose=True)
#         except ValkkaFSLoadError:
#             self._fs = ValkkaSingleFS.newFromDirectory(
#                 dirname=dirname,
#                 blocksize=512*(2048//8)*1024,
#                 n_blocks=10
#             )
        
#         self._manager = ValkkaFSManager(self._fs)
        
#         self._input_filter = self.manager.getInputFrameFilter(self.fs)
    

#     # call_on_change - calls without argument
#     # call_on_change_object_arg - calls with object as argument
#     # err_obj_not_in_container_msg <- None -> supress exception
#     # err_obj_not_in_container_msg is string -> can raise Exception
#     # return True on change, False otherwise


# innen meg kiszedni a hasznos dolgokat...
class FilterchainProcessComponents(Process, ABC):

    
    def frontend__setup(self) -> None:
        try:
            if self.__components_setup:
                raise ValueError('Setup did run before')
        except AttributeError:
            pass

        assert self.input_stream is not None or self.input_dir is not None

        # recording livecycle
        self._live = True

        # Decoders
        self._decoder_objects = {}
        # Streaming
        self._streaming_out_objects = {}
        # Recording
        self._recording_objects = {}

        self.__components_setup = True

    # def playback_setup(self,
    #                 stream_fork_name: str,
    #                 livethread_name: str,
    #                 input_address: str,
    #                 slot_id: int,
    #                 timeout_ms: int = None) -> None:
    #     try:
    #         if self.__playback_setup:
    #             raise ValueError('Setup did run before')
    #     except AttributeError:
    #         pass

    #     # Type-checking
    #     assert isinstance(input_address, str)
    #     assert isinstance(stream_fork_name, str)
    #     assert isinstance(livethread_name, str)

    #     assert timeout_ms is None or isinstance(timeout_ms, int)

    #     # Save params
    #     self.input_stream.input_address = str(input_address)
    #     self.input_stream.input_address = slot_id

    #     if timeout_ms is not None:
    #         self.input_stream.source_timeout_ms = int(timeout_ms)
    #     else:
    #         self.input_stream.source_timeout_ms = timeout_ms

    #     # create source constants
    #     self.input_stream.root_fork_name = stream_fork_name
    #     self.input_stream.source_livethread_name = livethread_name

    #     # recording livecycle
    #     self._live = True

    #     # Decoders
    #     self._decoder_objects = {}
    #     # Streaming
    #     self._streaming_out_objects = {}
    #     # Recording
    #     self._recording_objects = {}

    #     self.__playback_setup = True

    

    def start_streaming_out(self, livethread_name: str):

        _object_set_status(
            self._streaming_out_objects,
            livethread_name,

            target_status=True,
            callback_with_object=lambda object: object['livethread'].startCall(
            ),
            err_id_not_in_container_msg=f"Livethread {livethread_name} \
                is not exists for outbound live streaming"
        )

    def stop_streaming_out(self, livethread_name: str):

        _object_set_status(
            self._streaming_out_objects,
            livethread_name,

            target_status=False,
            callback_with_object=lambda object: object['livethread'].stopCall(
            ),
            err_id_not_in_container_msg=f"Livethread {livethread_name} \
                is not exists for outbound live streaming"
        )

    def delete_streaming_out(self, livethread_name: str):

        # Raises exception if livethread not exists
        self.stop_streaming_out(livethread_name)
        del self._streaming_out_objects[livethread_name]

    def backend__streaming_local(self,
                                 livethread_name: str,
                                 substream_id: str,
                                 stream_port: int,
                                 slot_id: int) -> FrameFilter:
        assert isinstance(livethread_name, str)
        assert isinstance(substream_id, str)
        assert isinstance(stream_port, int)
        assert isinstance(slot_id, int)

        if livethread_name in self._streaming_out_objects:
            raise ValueError(
                f"Livethread {livethread_name} is exists for outbound live streaming")

        if not self._is_port_open('127.0.0.1', int(stream_port)):
            raise ValueError(
                f"Port {stream_port} is not accessible for streaming - port is in use")

        streamer = self._streaming_out_objects[livethread_name] = {}

        print('===== 4 =====')
        print(
            f"Streaming out: {livethread_name}, stream {substream_id}, port {stream_port}, {slot_id}")
        streamer['livethread'] = LiveThread(livethread_name)

        # out_ctx = LiveOutboundContext(LiveConnectionType_sdp,
        #                              str(stream_address),
        #                              int(slot_id),
        #                              int(stream_port))
        # outbound_livethread.registerOutboundCall(out_ctx)

        streamer['livethread'].setRTSPServer(int(stream_port))
        streamer['connection_type'] = LiveConnectionType_rtsp
        streamer['context'] = LiveOutboundContext(streamer['connection_type'],
                                                  str(substream_id),
                                                  int(slot_id),
                                                  0)

        print(
            f"OUT:  {LiveConnectionType_rtsp} {str(substream_id)} {int(slot_id)}")
        streamer['livethread'].registerOutboundCall(streamer['context'])

        print('DEBUG: additional outbound filter')

        streamer['livethread_filter'] = streamer['livethread'].getFrameFilter()

        return streamer['livethread_filter']

    
    
    # def _backend__create_decoder_fork(self, parent_fork_name: str, decoder_name: str):
    #     assert isinstance(parent_fork_name, str)
    #     assert isinstance(decoder_name, str)

    #     decoder = self._decoder_objects[decoder_name] = {}

    #     decoder_fork_name = parent_fork_name+'_'+decoder_name
    #     avthread_name = decoder_fork_name+'_avthread'+self.input_stream.input_address+'_'+decoder_name
    #     avthread_connection = decoder_fork_name + \
    #         '_connect_avthread'+self.input_stream.input_address+'_'+decoder_name

    #     decoder['fork'] = ForkFrameFilterN(decoder_fork_name)

    #     avthread = AVThread(avthread_name, decoder['fork'])

    #     decoder['avthread'] = avthread.getFrameFilter()

    #     decoder['fork'].connect(avthread_connection, decoder['avthread'])

    #     return decoder['avthread']

    # call_on_change - calls without argument
    # call_on_change_object_arg - calls with object as argument
    # err_obj_not_in_container_msg <- None -> supress exception
    # err_obj_not_in_container_msg is string -> can raise Exception
    # return True on change, False otherwise

    

def _object_set_status(self,
                       object_container: dict,
                       object_id,
                       target_status: bool,
                       call_on_change=None,
                       callback_with_object=None,
                       err_id_not_in_container_msg: str = None,
                       status_key: str = 'enabled') -> bool:
    assert isinstance(object_container, dict)
    assert callable(call_on_change) or callable(callback_with_object)
    assert isinstance(status_key, str)

    if object_id not in object_container:
        if err_id_not_in_container_msg is None:
            return
        else:
            raise ValueError(err_id_not_in_container_msg)

    target = object_container[object_id]

    status = target.get(status_key)
    if bool(status) != bool(target_status):

        if callable(call_on_change):
            call_on_change()
        if callable(callback_with_object):
            callback_with_object(target)

        target[status_key] = bool(target_status)
        return True

    return False
