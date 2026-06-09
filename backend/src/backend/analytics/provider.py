from __future__ import annotations

import contextlib
from typing import Any, Protocol


class AnalyticsProvider(Protocol):
    def initialize(self) -> None: ...
    def flush(self) -> None: ...
    def request_context(self, session_id: str) -> contextlib.AbstractContextManager[None]: ...
    def get_callback_handler(self) -> Any | None: ...
    def create_event(self, name: str, payload: dict) -> None: ...


class NullProvider:
    def initialize(self) -> None:
        pass

    def flush(self) -> None:
        pass

    def request_context(self, session_id: str) -> contextlib.AbstractContextManager[None]:
        return contextlib.nullcontext()

    def get_callback_handler(self) -> None:
        return None

    def create_event(self, name: str, payload: dict) -> None:
        pass
