from lssa.adapters.mock import MockProviderAdapter, MockScenario, request_for_scenario
from lssa.schema.events import EventType
from lssa.schema.metrics import settlement_lag_ms
from lssa.tracing.validator import validate_trace


def test_all_mock_scenarios_emit_valid_traces() -> None:
    adapter = MockProviderAdapter()

    for scenario in MockScenario:
        events = list(adapter.run(request_for_scenario(scenario)))
        result = validate_trace(events)
        assert result.ok, (scenario, result.errors)


def test_nonstreaming_mock_trace_has_final_response_without_chunks() -> None:
    adapter = MockProviderAdapter()
    events = list(adapter.run(request_for_scenario(MockScenario.NONSTREAMING_BENIGN)))

    event_types = [event.event_type for event in events]

    assert EventType.FINAL_RESPONSE in event_types
    assert EventType.CHUNK not in event_types


def test_streaming_delayed_settlement_has_positive_settlement_lag() -> None:
    adapter = MockProviderAdapter()
    events = list(adapter.run(request_for_scenario(MockScenario.STREAMING_DELAYED_SETTLEMENT)))

    assert settlement_lag_ms(events) == 50


def test_streaming_cancel_lifecycle_contains_cleanup_events() -> None:
    adapter = MockProviderAdapter()
    events = list(adapter.run(request_for_scenario(MockScenario.STREAMING_CANCEL)))
    event_types = [event.event_type for event in events]

    assert event_types.index(EventType.CANCEL) < event_types.index(EventType.ITERATOR_END)
    assert event_types.index(EventType.ITERATOR_END) < event_types.index(EventType.SETTLED)
