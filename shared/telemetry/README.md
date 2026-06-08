# telemetry

Shared structured JSON logger for the growth-chat monorepo. Provides component-bound loggers, per-request session-ID context propagation, PII sanitisation, and a registry of named event constants used across all packages.

## Public API

```python
from telemetry import configure_logging, get_logger, sanitize_error, set_session_id
from telemetry import events
```

### `configure_logging()`

Call **once** at process startup (before `FastAPI(...)`) to install a JSON `StreamHandler` on the root logger and route uvicorn loggers through it.

```python
# backend/main.py
configure_logging()
```

All subsequent log output is newline-delimited JSON on stdout, ready for log-aggregation services (e.g. BetterStack).

### `get_logger(component: str) → _StructuredAdapter`

Returns a component-bound logger. Log calls accept arbitrary keyword arguments that are serialised as extra JSON fields.

```python
log = get_logger("orchestrator")
log.error(events.LLM_GENERATION_FAILURE, session_id=sid, turn_index=t, error=str(exc))
log.warning(events.ANALYTICS_EMIT_FAILURE, session_id=sid, error=sanitize_error(str(exc)))
log.info("request_received", path="/chat", method="POST")
```

Each call produces one JSON line:

```json
{
  "level": "error",
  "event": "llm_generation_failure",
  "component": "orchestrator",
  "session_id": "abc-123",
  "turn_index": 2,
  "error": "...",
  "timestamp": "2026-06-08T14:00:00.000Z"
}
```

### `set_session_id(session_id: str | None)`

Stores the session ID in a `contextvars.ContextVar`. Every log record emitted from the same async context automatically includes `session_id` without passing it explicitly.

```python
# router.py — call once per request, before graph execution
set_session_id(zgc_session_id)
```

### `sanitize_error(msg: str) → str`

Strips email addresses and `name=` / `name:` patterns from external API error strings before logging, to avoid leaking PII.

```python
log.error(events.LLM_GENERATION_FAILURE, error=sanitize_error(str(exc)))
```

### `events` module

Named string constants for structured log event names. Import the module and reference constants rather than inline string literals so typos are caught at import time.

| Constant | Value |
|---|---|
| `LLM_GENERATION_FAILURE` | `"llm_generation_failure"` |
| `STATE_EXTRACTION_FAILURE` | `"state_extraction_failure"` |
| `STREAM_TIMEOUT` | `"stream_timeout"` |
| `EMBEDDING_API_FAILURE` | `"embedding_api_failure"` |
| `VECTOR_SEARCH_FAILURE` | `"vector_search_failure"` |
| `CHECKPOINTER_WRITE_FAILURE` | `"checkpointer_write_failure"` |
| `HANDOFF_CHANNEL_FAILURE` | `"handoff_channel_failure"` |
| `HANDOFF_PARTIAL_FAILURE` | `"handoff_partial_failure"` |
| `HANDOFF_TOTAL_FAILURE` | `"handoff_total_failure"` |
| `ANALYTICS_EMIT_FAILURE` | `"analytics_emit_failure"` |
| `LANGFUSE_CLIENT_FAILURE` | `"langfuse_client_failure"` |
| `RATE_LIMIT_HIT` | `"rate_limit_hit"` |
| `SESSION_CORRUPTED` | `"session_corrupted"` |
| `FALLBACK_ACTIVATED` | `"fallback_activated"` |
| `CORRUPT_CHUNK_SKIPPED` | `"corrupt_chunk_skipped"` |
| `RAG_EXTRA_TOOL_CALL_IGNORED` | `"rag_extra_tool_call_ignored"` |
| `PROMPT_COMPLIANCE_VIOLATION` | `"prompt_compliance_violation"` |
| `BACKUP_FAILED` | `"backup_failed"` |

## Workspace membership

`telemetry` is a `uv` workspace member declared in the root `pyproject.toml`. Add it as a dependency in any member that needs structured logging:

```toml
# any member's pyproject.toml
[project]
dependencies = [
    "telemetry",
]
```

No third-party runtime dependencies. Requires Python 3.14+.
