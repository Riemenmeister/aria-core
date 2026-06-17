import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List

logger = logging.getLogger('aria_events')


class EventType(Enum):
    CORE_STARTED = 'CORE_STARTED'
    CLIENT_CONNECTED = 'CLIENT_CONNECTED'
    CLIENT_DISCONNECTED = 'CLIENT_DISCONNECTED'
    STREAM_ERROR = 'STREAM_ERROR'
    CRITICAL_ERROR = 'CRITICAL_ERROR'


@dataclass
class AriaEvent:
    event_type: EventType
    payload: Dict[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[AriaEvent], None]


class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)
            logger.debug('Handler subscribed for event %s: %s', event_type, handler)

    def publish(self, event: AriaEvent) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        if not handlers:
            logger.debug('No handlers for event %s', event.event_type)
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception('Exception in event handler for %s', event.event_type)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
                logger.debug('Handler unsubscribed for event %s: %s', event_type, handler)
                if not handlers:
                    self._handlers.pop(event_type, None)

    def reset(self, event_type: EventType = None) -> None:
        with self._lock:
            if event_type is None:
                self._handlers.clear()
                logger.debug('EventBus reset all handlers')
            else:
                self._handlers.pop(event_type, None)
                logger.debug('EventBus reset handlers for %s', event_type)


_bus = EventBus()


def subscribe(event_type: EventType, handler: EventHandler) -> None:
    _bus.subscribe(event_type, handler)


def unsubscribe(event_type: EventType, handler: EventHandler) -> None:
    _bus.unsubscribe(event_type, handler)


def publish(event: AriaEvent) -> None:
    _bus.publish(event)


def reset(event_type: EventType = None) -> None:
    _bus.reset(event_type)
