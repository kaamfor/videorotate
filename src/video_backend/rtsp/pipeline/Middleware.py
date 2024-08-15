from valkka.core import FrameFilter

class Middleware:
    def __init__(self,
                 filter_create_callback: callable,
                 chain_next_middleware=None,
                 default_params: dict = {},
                 force_params: dict = {}) -> None:
        is_corrent_type = isinstance(chain_next_middleware, type(self))
        assert chain_next_middleware is None or is_corrent_type

        assert callable(filter_create_callback)
        
        assert isinstance(default_params, dict)
        assert isinstance(force_params, dict)

        self._chain_next_middleware = chain_next_middleware
        self._filter_create_callback = filter_create_callback
        
        self.__default_params = {}
        self.__default_params.update(default_params)
        
        self.__force_params = {}
        self.__force_params.update(force_params)

    def generate_filter(self,
                        child_filter: FrameFilter,
                        **generator_params) -> FrameFilter:
        assert isinstance(child_filter, FrameFilter)

        kwargs = {}
        kwargs.update(self.__default_params)
        kwargs.update(generator_params)
        kwargs.update(self.__force_params)

        actual_child = child_filter
        if self._chain_next_middleware is not None:
            actual_child = self._chain_next_middleware.generate_filter(
                child_filter,
                **kwargs)

        return self._filter_create_callback(actual_child, **kwargs)
