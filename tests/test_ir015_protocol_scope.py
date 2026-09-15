from starlette.routing import WebSocketRoute

import proxy_server


def test_tokentotals_exposes_no_websocket_route():
    """The current FastAPI application must not silently grow a WebSocket surface."""
    websocket_routes = [
        route for route in proxy_server.app.routes if isinstance(route, WebSocketRoute)
    ]
    assert websocket_routes == []


def test_streaming_chat_path_is_explicitly_sse_in_runtime_source():
    """The supported streamed transport is SSE over the HTTP chat-completion route."""
    source = open(proxy_server.__file__, encoding="utf-8").read()
    assert 'StreamingResponse(generate(), media_type="text/event-stream")' in source
    assert '@app.post("/v1/chat/completions")' in source
    assert "@app.websocket" not in source
