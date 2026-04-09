from __future__ import annotations
from ...template import NodeTemplate
# from ...routing.router import Router
from abc import abstractmethod


from typing import Callable, Any, Optional
import inspect
from ...events.event import NodeEvent, Event
from ...events.connect import NodeConnectionType, EventOnConnectRegistry, EventOnDisconnectRegistry
from dataclasses import dataclass
from threading import Thread, Event
from concurrent.futures import ThreadPoolExecutor
from ....sync.signal import HoldSignal
import time

@dataclass
class IntervalFunctorDefinition:
    interval: int
    functor: Callable[..., Any]

def param_count(fn):
    sig = inspect.signature(fn)
    return len(sig.parameters)

class RoutingLayer(NodeTemplate):

    def __init__(self):
        super().__init__()
        # Create the routing map that will house the methods.
        self.routing_map: dict[str, Callable[..., Any]] = {}
        self.event_maps: dict[NodeEvent, list[Event]] = {
            NodeEvent.ON_CONNECT: [],
            NodeEvent.ON_DISCONNECT: []
        }

        # Get the interval functors
        self.interval_functors = []

        # self.ready_signal = HoldSignal()
        self.stop_event = Event()

        self.ready_signal = HoldSignal()

        self.executor = ThreadPoolExecutor()

        self.generate_routing_templates()
        # self.ready_signal.re

    def _invoke_event(self, event: NodeEvent, *args, **kwargs):
        for fn in self.event_maps[event]:
            # print(f'Invoking function with {args}')
            fn.invoke(self, *args, **kwargs)
        
        
    def _start_routing_layer(self):
        self.ready_signal.ready()

    def stop(self):
        self.stop_event.set()

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
        if self.stop_event.is_set():
            return
        if function_args is None:
            self.executor.submit(functor)
        else:
            self.executor.submit(functor, *function_args)
        # print(f'Startting {functor}')
        # if function_args is None:
        #     self.executor.submit
        #     Thread(target=functor, daemon=True).start()
        # else:
        #     Thread(target=functor, args=function_args, daemon=True).start()

    def launch_interval_functor(
        self,
        functor: Callable[..., Any],
        interval: int
    ):
        def runnable():
            self.ready_signal.barrier()
            while not self.stop_event.is_set():
                functor(self)
                time.sleep(interval / 1000.0)
        self.launch_background_thread(runnable, function_args=None)

    def _call_route(
        self,
        source: str,
        route: str,
        body: dict
    ) -> Any:
        self.ready_signal.barrier()
        # print(f'CALLED ROUTE: {route}, body: {body}')
        if route in self.routing_map:
            fn: Callable = self.routing_map[route]
            if param_count(fn) == 3:
                # May optionally include the name
                return fn(self, body, source)
            else:
                return fn(self, body)
        else:
            raise RuntimeError(f'Could not find route {route}')
        pass

    # @staticmethod
    def generate_routing_templates(self) -> Router:
        # router = Router()
        for _, fn in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            annotations: dict = fn.__annotations__
            if 'node_route' in annotations:
                # We have a node route.
                route: str = annotations['node_route']['name']
                self.routing_map[route] = fn
            elif 'interval_functor' in annotations:
                interval: int = annotations['interval_functor']['interval']
                # router.__launch_interval_functor(fn, interval)
                
                self.__add_interval_functor(IntervalFunctorDefinition(
                    interval=interval,
                    functor=fn
                ))
            elif 'on_connect' in annotations:
                self.event_maps[NodeEvent.ON_CONNECT].append(EventOnConnectRegistry(
                    functor=fn,
                    method=annotations['on_connect']
                ))
            elif 'on_dc' in annotations:
                self.event_maps[NodeEvent.ON_DISCONNECT].append(EventOnDisconnectRegistry(
                    functor=fn,
                    method=annotations['on_dc']
                ))
        # print(f'Rotuer: {router.routing_map}')
        # return router

    def shutdown(self):
        self.stop()
        self.executor.shutdown(False, cancel_futures=True)
        
        return super().shutdown()


def node_handler(name: str = None, internal_ms: int = None, on_connect: "NodeConnectionType" = None, on_disconnect: "NodeConnectionType" = None):
    if name is not None and internal_ms is not None:
        raise RuntimeError("Both 'name' and 'internal_ms' cannot be set.")
    if name is not None:
        # print(f'Function: {name}')
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
    

# class RoutingLayer(NodeTemplate):

#     def __init__(self):
#         super().__init__()

#         self.router = Router.generate_routing_templates(self)
#         self.router.start()

    
        
#     @abstractmethod
#     def _call_route(
#         self
#     ):
#         pass

#     def shutdown(self):
#         self.router.stop()