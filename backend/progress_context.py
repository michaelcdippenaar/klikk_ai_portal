"""
Thread-local progress callback — lets tool functions emit status messages
back to the WebSocket chat without needing to know about asyncio.

Usage in a tool function:
    from progress_context import emit_progress
    emit_progress("Connecting to TM1...")
    emit_progress("Found 65 share codes", "fetching yfinance data...")

Usage in the WebSocket handler (done in chat.py):
    from progress_context import set_progress_callback, clear_progress_callback
    set_progress_callback(lambda msg: loop.call_soon_threadsafe(queue.put_nowait, msg))
"""
import threading

_local = threading.local()


def set_progress_callback(fn) -> None:
    """Set the progress callback for the current thread."""
    _local.callback = fn


def clear_progress_callback() -> None:
    """Clear the progress callback for the current thread."""
    _local.callback = None


def emit_progress(message: str, detail: str = "") -> None:
    """Emit a status progress message. No-op if no callback is set."""
    fn = getattr(_local, "callback", None)
    if fn:
        payload = {"type": "status", "message": message}
        if detail:
            payload["detail"] = detail
        fn(payload)
