from __future__ import annotations
from ...components.template import NodeTemplate
import traceback

from typing import Callable, Any
import inspect
from ...components.events.event import NodeEvent, Event
from ...components.events.connect import NodeConnectionType, EventOnConnectRegistry, EventOnDisconnectRegistry
from dataclasses import dataclass
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from ...components.sync.signal import HoldSignal
import time
from ..functional.functional_layer import FunctionalLayer
from colorama import Fore

@dataclass
class IntervalFunctorDefinition:
    interval: int
    functor: Callable[..., Any]


def param_count(fn):
    sig = inspect.signature(fn)
    return len(sig.parameters)


class RoutingLayer(FunctionalLayer):

    def __init__(self):
        super().__init__()
        self.routing_map: dict[str, Callable[..., Any]] = {}
        self.event_maps: dict[NodeEvent, list[Event]] = {
            NodeEvent.ON_CONNECT: [],
            NodeEvent.ON_DISCONNECT: []
        }

        self.interval_functors: list[IntervalFunctorDefinition] = []
        self.plugins: list[object] = []

        # self.stop_event = Event()
        self.ready_signal = HoldSignal()
        self.executor = ThreadPoolExecutor()

        self.generate_routing_templates()

    def _invoke_event(self, event: NodeEvent, *args, **kwargs):
        for fn in self.event_maps[event]:
            fn.invoke(self, *args, **kwargs)

    def _start_routing_layer(self):
        self.ready_signal.ready()

    # def stop(self):
    #     self.stop_event.set()

    def __add_interval_functor(
        self,
        definition: IntervalFunctorDefinition
    ):
        self.interval_functors.append(definition)
        self.launch_interval_functor(definition.functor, definition.interval)

    def launch_background_thread(
        self,
        functor: Callable[..., Any],
        function_args: ...
    ):
        def wrapped(*args, **kwargs):
            # Wait until we are ready to start handling events.
            self.wait_ready()

            return functor(*args, **kwargs)

        if self.is_shutting_down():
            return
        if function_args is None:
            self.executor.submit(wrapped)
        else:
            self.executor.submit(wrapped, *function_args)

    def launch_interval_functor(
        self,
        functor: Callable[..., Any],
        interval: int
    ):
        def runnable():
            self.ready_signal.barrier()
            while not self.is_shutting_down():
                try:
                    functor()
                except Exception as e:
                    print(f'{Fore.RED}[{self.get_network_name()}] Crash in interval functor (interval={interval}): {type(e).__name__}: {e}{Fore.RESET}')
                    traceback.print_exc()
                    # break
                time.sleep(interval / 1000.0)
            
        self.launch_background_thread(runnable, function_args=None)

    def _call_route(
        self,
        source: str,
        route: str,
        body: dict
    ):
        self.ready_signal.barrier()

        if route not in self.routing_map:
            raise RuntimeError(f'Could not find route {route}')

        fn = self.routing_map[route]
        argc = param_count(fn)

        #print(f"[{self.network_name}] _call_route route={route} fn={fn} param_count={argc}")

        if argc == 2:
            result = fn(body, source)
        elif argc == 1:
            result = fn(body)
        else:
            raise RuntimeError(f"Unsupported handler arity {argc} for route {route}")

        #print(f"[{self.network_name}] _call_route result for {route}: {result}")
        return result
    
    
    def _register_route(
        self,
        route: str,
        functor: Callable[..., Any]
    ):
        # def bound(*args, **kwargs):
        #     return functor(*args, **kwargs)
        
        self.routing_map[route] = functor

    def __generate_routing_for_object(self, obj: object):
        for _, class_fn in inspect.getmembers(obj.__class__, predicate=inspect.isfunction):
            annotations: dict = getattr(class_fn, "__annotations__", {})

            if 'node_route' in annotations:
                bound_fn = getattr(obj, class_fn.__name__)
                route: str = annotations['node_route']['name']
                self.routing_map[route] = bound_fn

            elif 'interval_functor' in annotations:
                bound_fn = getattr(obj, class_fn.__name__)
                interval: int = annotations['interval_functor']['interval']
                self.__add_interval_functor(IntervalFunctorDefinition(
                    interval=interval,
                    functor=bound_fn
                ))

            elif 'on_connect' in annotations:
                bound_fn = getattr(obj, class_fn.__name__)
                self.event_maps[NodeEvent.ON_CONNECT].append(EventOnConnectRegistry(
                    functor=bound_fn,
                    method=annotations['on_connect']
                ))

            elif 'on_dc' in annotations:
                bound_fn = getattr(obj, class_fn.__name__)
                self.event_maps[NodeEvent.ON_DISCONNECT].append(EventOnDisconnectRegistry(
                    functor=bound_fn,
                    method=annotations['on_dc']
                ))

    def register_plugin(self, plugin):
        self.plugins.append(plugin)
        self.__generate_routing_for_object(plugin)
        return plugin

    def generate_routing_templates(self):
        self.__generate_routing_for_object(self)

    def shutdown(self):
        # self.stop()
        self.executor.shutdown(False, cancel_futures=True)
        return super().shutdown()


def node_handler(name: str = None, internal_ms: int = None, on_connect: "NodeConnectionType" = None, on_disconnect: "NodeConnectionType" = None):
    if name is not None and internal_ms is not None:
        raise RuntimeError("Both 'name' and 'internal_ms' cannot be set.")
    if name is not None:
        def decorator(fn):
            fn.__annotations__['node_route'] = {
                "name": name,
                "functor": fn
            }
            return fn
        return decorator
    elif internal_ms is not None:
        def decorator(fn):
            fn.__annotations__['interval_functor'] = {
                "interval": internal_ms,
                "functor": fn
            }
            return fn
        return decorator
    elif on_connect is not None:
        def decorator(fn):
            fn.__annotations__['on_connect'] = on_connect
            return fn
        return decorator
    elif on_disconnect is not None:
        def decorator(fn):
            fn.__annotations__['on_dc'] = on_disconnect
            return fn
        return decorator
    else:
        raise RuntimeError("You must specify at least one mode of operation.")