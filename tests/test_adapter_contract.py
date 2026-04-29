from lssa.adapters.base import AdapterRequest
from lssa.adapters.mock import MockProviderAdapter, MockScenario, request_for_scenario
from lssa.schema.events import ResponseMode, StreamEvent


def test_adapter_request_is_provider_neutral() -> None:
    request = AdapterRequest(
        trace_id="trace-1",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="mock-model",
    )

    assert request.trace_id == "trace-1"
    assert request.response_mode == ResponseMode.STREAMING
    assert request.provider_family == "mock"


def test_mock_adapter_returns_normalized_stream_events() -> None:
    adapter = MockProviderAdapter()
    request = request_for_scenario(MockScenario.STREAMING_BENIGN)

    events = list(adapter.run(request))

    assert events
    assert all(isinstance(event, StreamEvent) for event in events)
    assert {event.trace_id for event in events} == {request.trace_id}
