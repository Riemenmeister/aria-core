import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aria_events import AriaEvent, EventBus, EventType
import aria_voice_notifier
from aria_voice_notifier import VoiceProfile


class EventBusTests(unittest.TestCase):
    def test_publish_routes_to_subscriber(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.CLIENT_CONNECTED, handler)
        bus.publish(AriaEvent(event_type=EventType.CLIENT_CONNECTED, payload={'message': 'ok'}))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload['message'], 'ok')

    def test_multiple_subscribers_receive_event(self):
        bus = EventBus()
        calls = []

        def handler_one(event):
            calls.append('one')

        def handler_two(event):
            calls.append('two')

        bus.subscribe(EventType.STREAM_ERROR, handler_one)
        bus.subscribe(EventType.STREAM_ERROR, handler_two)
        bus.publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'message': 'test'}))

        self.assertEqual(calls, ['one', 'two'])

    def test_subscriber_exception_does_not_break_bus(self):
        bus = EventBus()
        calls = []

        def brittle(event):
            raise ValueError('handler failed')

        def robust(event):
            calls.append('ok')

        bus.subscribe(EventType.STREAM_ERROR, brittle)
        bus.subscribe(EventType.STREAM_ERROR, robust)

        bus.publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'message': 'failover'}))

        self.assertEqual(calls, ['ok'])

    def test_unsubscribe_removes_handler(self):
        bus = EventBus()
        calls = []

        def handler(event):
            calls.append('called')

        bus.subscribe(EventType.CORE_STARTED, handler)
        bus.unsubscribe(EventType.CORE_STARTED, handler)
        bus.publish(AriaEvent(event_type=EventType.CORE_STARTED, payload={'message': 'ignored'}))

        self.assertEqual(calls, [])


class VoiceNotifierEventMappingTests(unittest.TestCase):
    def test_event_type_maps_to_expected_voice_profile(self):
        expected = {
            EventType.CORE_STARTED: VoiceProfile.INFO,
            EventType.CLIENT_CONNECTED: VoiceProfile.SUCCESS,
            EventType.CLIENT_DISCONNECTED: VoiceProfile.INFO,
            EventType.STREAM_ERROR: VoiceProfile.WARNING,
            EventType.CRITICAL_ERROR: VoiceProfile.CRITICAL,
        }

        for event_type, expected_profile in expected.items():
            result = aria_voice_notifier._event_to_voice_profile(event_type)
            self.assertEqual(result, expected_profile)

    def test_critical_error_event_forces_tts(self):
        original_notifier = getattr(aria_voice_notifier, '_notifier', None)
        try:
            class DummyNotifier:
                def __init__(self):
                    self.calls = []

                def speak(self, text, profile=VoiceProfile.INFO, force=False):
                    self.calls.append({'text': text, 'profile': profile, 'force': force})
                    return True

            aria_voice_notifier._notifier = DummyNotifier()
            event = AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'critical failure'})
            aria_voice_notifier._handle_aria_event(event)

            self.assertEqual(len(aria_voice_notifier._notifier.calls), 1)
            call = aria_voice_notifier._notifier.calls[0]
            self.assertEqual(call['profile'], VoiceProfile.CRITICAL)
            self.assertTrue(call['force'])
        finally:
            aria_voice_notifier._notifier = original_notifier


if __name__ == '__main__':
    unittest.main()
