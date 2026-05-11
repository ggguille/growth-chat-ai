---
description: "API Specifications for the company AI-powered lead qualification chat: Chat endpoint (SSE streaming), Handoff delivery interfaces (Slack, CRM), Fallback form resolution, and Internal component contracts."
---

# API Specifications

> **Relationship to other TRD sections:**
>
> - Section 3 (Component Specifications) defines the logic that calls and is called by these APIs.
> - Section 4 (Data Models) defines the schemas (`SessionState`, `ContextPacket`, `HandoffRequest`) referenced here.
> - Section 6 (Infrastructure Requirements) defines the environment variables that configure these endpoints.
> - Section 8 (Security Requirements) defines the rate limiting and authentication rules enforced at the API layer.
>
> **What this section specifies and what it does not:**
> This section specifies the contracts — request/response schemas, SSE event formats, error codes,
> and internal interface signatures — that allow frontend and backend to build in parallel.
> It does not specify implementation detail (FastAPI route handlers, middleware order) or
> retry logic (defined per-component in Section 3). It does not repeat rationale for technology
> choices already recorded in ADRs.

---

## Chat Endpoint

**The primary conversation interface.** Accepts a visitor message and returns a streaming
Server-Sent Events response. Each turn maps to one request-response cycle. There is no
persistent WebSocket connection — the visitor's next message is a new HTTP request.

---

### Request

```text
POST /chat
Content-Type: application/json
Accept: text/event-stream
ZGC-Session-ID: <uuid-v4>
ZGC-API-KEY: <static key>
```

**Headers:**

| Header | Required | Description |
| --- | --- | --- |
| `ZGC-Session-ID` | Yes | UUID v4 generated client-side on `connectedCallback`. Used as the LangGraph `thread_id` for checkpointer lookup. Sent on every request. No cross-session persistence (FR-07a). |
| `ZGC-API-KEY` | Yes | Static key issued per widget deployment. Validated before the request reaches the orchestrator. Rotated per environment. |
| `Content-Type` | Yes | Must be `application/json`. |
| `Accept` | Yes | Must be `text/event-stream`. If absent, the server returns 400. |

**Body:**

```json
{
  "message": "string — visitor's message text"
}
```

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `message` | string | Yes | Non-empty. Max 2,000 characters. Stripped of leading/trailing whitespace before processing. |

---

### Response

**Content-Type:** `text/event-stream`
**Transfer-Encoding:** chunked
**Cache-Control:** no-cache
**Connection:** keep-alive

The response is a stream of SSE events. Each event is a line of the form:

```text
data: <json-payload>\n\n
```

**SSE event types:**

#### `token`

Emitted for each LLM response token as it arrives from the Anthropic streaming API.

```text
data: {"type": "token", "content": "..."}
```

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"token"` | Event type discriminator |
| `content` | string | One or more characters of the LLM response |

The widget appends `content` to the displayed message in order. No buffering — tokens are
forwarded as received.

#### `done`

Emitted once, when the turn is complete and `write_state` has persisted the updated
`SessionState`. This event carries the session state metadata the widget needs to fire
analytics events (Section 3 — Analytics Events).

```text
data: {
  "type": "done",
  "session_id": "uuid-v4",
  "lead_level": "hot" | "warm" | "cold",
  "current_stage": 1 | 2 | 3,
  "stage3_proposal_issued": true | false,
  "handoff_reason": "hot_lead" | "explicit_request" | "stall" | "llm_failure" | null,
  "turn_count": integer
}
```

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"done"` | Event type discriminator |
| `session_id` | string | Echo of the `ZGC-Session-ID` header |
| `lead_level` | enum | Current lead classification after this turn |
| `current_stage` | 1 \| 2 \| 3 | Conversation stage at end of turn |
| `stage3_proposal_issued` | boolean | `true` if `propose_handoff` executed on this turn. Widget uses this to fire `zgc:escalation_triggered`. |
| `handoff_reason` | enum \| null | Populated when `stage3_proposal_issued` is `true`; null otherwise |
| `turn_count` | integer | Absolute turn index for this session |

**Widget behaviour on `done`:**

- If `lead_level` differs from the previously received value → fire `zgc:qualification_state_changed`
- If `stage3_proposal_issued == true` → fire `zgc:escalation_triggered`
- Re-enable the message input

#### `error`

Emitted when a non-recoverable error occurs during the turn. The stream closes after this event.

```text
data: {"type": "error", "code": "string", "message": "string"}
```

| Code | Condition | Widget behaviour |
| --- | --- | --- |
| `LLM_UNAVAILABLE` | Anthropic API unreachable or returning 5xx | Show inline error message for this turn; session continues |
| `STREAM_TIMEOUT` | First token not received within `LLM_STREAM_TIMEOUT_MS` | Same as `LLM_UNAVAILABLE` |
| `ORCHESTRATOR_ERROR` | Unhandled exception in the orchestration graph | Show inline error; session continues |
| `SESSION_CORRUPTED` | Checkpointer read returns an unresolvable state | Show inline error; widget reloads session (new `session_id`) |

**Important:** `error` events are turn-level failures. They do not activate the widget's
fallback state (Section 3 — Graceful Degradation). Fallback is only activated by
HTTP-level failures before the stream opens (see HTTP Error Responses below).

---

### HTTP Error Responses (pre-stream)

These are returned as standard JSON responses before the SSE stream is opened. On receiving
any of these, the widget does not attempt to render a partial stream.

```json
{
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

| Status | Code | Condition | Widget behaviour |
| --- | --- | --- | --- |
| 400 | `INVALID_MESSAGE` | `message` empty, exceeds 2,000 characters, or `session_id` not a valid UUID v4 | Show inline validation message; do not activate fallback |
| 400 | `MISSING_ACCEPT_HEADER` | `Accept: text/event-stream` absent | Configuration error — log to console |
| 401 | `INVALID_API_KEY` | `ZGC-API-KEY` absent or does not match any issued key | Activate fallback (widget deployment misconfiguration) |
| 429 | `RATE_LIMITED` | Per-IP or per-session limit exceeded (EC-12; limits defined in Section 8) | Show rate limit message for this turn; include `retry_after_seconds` in the response body |
| 503 | `SERVICE_UNAVAILABLE` | AI backend not reachable (upstream health check failed) | **Activate fallback state** |

**`429` response body extension:**

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many messages. Please wait before sending another.",
    "retry_after_seconds": 30
  }
}
```

---

### GDPR and PII at the API layer

The Chat API is a transport layer. It does not inspect or transform message content.
PII scrubbing (Section 4) is applied inside the orchestrator before content reaches
the Anthropic API. The Chat API does not log `message` body content — it logs only
`session_id`, request timestamp, HTTP status, and latency.

No visitor data is stored by the API layer. The single source of storage for session
content is the PostgreSQL checkpointer, governed by the retention rules in Section 4.

---

### Chat Endpoint Configuration

| Variable | Description | Section reference |
| --- | --- | --- |
| `ZGC_API_KEY` | Static key for widget authentication | Section 8 |
| `LLM_STREAM_TIMEOUT_MS` | Max ms to wait for first token before emitting `STREAM_TIMEOUT` error event | Section 3 — Orchestrator Configuration |
| Rate limiting variables | Per-IP and per-session limits | Section 8 — Security Requirements |

---

## Handoff Delivery Interfaces

The Human Handoff Subsystem (Section 3) delivers the `ContextPacket` to two external
destinations. This section specifies the outbound contracts — the payloads sent by the
system, not endpoints the system exposes. Both deliveries are triggered by a `HandoffRequest`
from the `propose_handoff` node and are dispatched in parallel.

Full delivery logic (retry, partial failure, email fallback) is specified in Section 3.
This section specifies only the payload schemas and confirmation criteria.

---

### Slack — `#new-leads` Webhook

**Destination:** Incoming webhook URL, configured via `SLACK_WEBHOOK_URL`.

**Method:** `POST`

**Confirmation criterion:** HTTP 200 response from the Slack webhook endpoint. Any non-200
response triggers the retry sequence defined in Section 3.

**Payload (Slack Block Kit):**

> *This is the canonical Slack payload. Section 3 references this specification.*

```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "{emoji} {lead_level_label} Lead — {visitor_company}"
      }
    },
    {
      "type": "section",
      "fields": [
        { "type": "mrkdwn", "text": "*Email:*\n{visitor_email}" },
        { "type": "mrkdwn", "text": "*Role:*\n{visitor_role}" },
        { "type": "mrkdwn", "text": "*Trigger:*\n{handoff_reason}" },
        { "type": "mrkdwn", "text": "*Turns:*\n{turn_count}" }
      ]
    },
    {
      "type": "section",
      "text": { "type": "mrkdwn", "text": "*Summary:*\n{conversation_summary}" }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Qualification:* Problem: {problem_fit} | Authority: {authority_fit} | Company: {company_fit} | Timing: {timing_fit}"
      }
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "View CRM Record" },
          "url": "{crm_record_url}"
        }
      ]
    }
  ]
}
```

**Field rendering rules:**

| Template field | Source | Fallback if absent |
| --- | --- | --- |
| `{emoji}` | Derived from `lead_level`: hot → 🔥, warm → 🌡️, cold → ❄️. Outside hours prefix: 📬 | — |
| `{lead_level_label}` | `lead_level` capitalised: `Hot`, `Warm`, `Cold` | — |
| `{visitor_company}` | `ContextPacket.visitor.company` | `"Unknown company"` |
| `{visitor_email}` | `ContextPacket.visitor.email` | `"Not captured"` |
| `{visitor_role}` | `ContextPacket.visitor.role` | `"Unknown"` |
| `{handoff_reason}` | `HandoffRequest.handoff_reason` | — |
| `{turn_count}` | `ContextPacket.conversation.turn_count` | — |
| `{conversation_summary}` | `ContextPacket.conversation_summary` | — |
| `{problem_fit}` / `{authority_fit}` / `{company_fit}` / `{timing_fit}` | `ContextPacket.qualification.*_fit` | — |
| `{crm_record_url}` | `LeadCreationResult.crm_record_url` — available only after CRM delivery succeeds | Button omitted if CRM fails |

**CRM URL availability:** Slack and CRM are dispatched in parallel. If the Slack delivery
completes before the CRM record ID is available, the message is sent without the button.
Once the CRM record ID is received, the Slack message is updated via `chat.update` API
to add the button. If CRM delivery fails entirely, the button is permanently omitted.
This requires the `SLACK_BOT_TOKEN` environment variable in addition to `SLACK_WEBHOOK_URL`
(the `chat.update` API requires a bot token; the incoming webhook alone is insufficient).

---

### CRM Delivery

**Platform:** TBD — pending OQ-04. The concrete implementation is a Phase 3 deliverable
specified in a supplementary ADR once the platform is confirmed.

**Integration pattern:** The Human Handoff Subsystem calls an abstract `CRMClient` interface.
Phase 1–2 engineering uses a stub implementation. The concrete adapter is a drop-in replacement
conforming to the same interface.

**`CRMClient` interface:**

```python
class CRMClient(Protocol):
    async def create_lead(self, payload: CRMLeadPayload) -> LeadCreationResult:
        """
        Create a lead record in the CRM.
        Returns LeadCreationResult on success.
        Raises CRMDeliveryError on failure — caller handles retry.
        """
        ...

@dataclass
class LeadCreationResult:
    crm_record_id:  str   # CRM-assigned record identifier
    crm_record_url: str   # Direct URL to the record in the CRM UI

@dataclass
class CRMDeliveryError(Exception):
    http_status: int | None
    message:     str
```

**Confirmation criterion:** `create_lead()` returns a `LeadCreationResult` with a
non-null `crm_record_id`. A response without a record ID is treated as a failure —
async creation patterns that return 202 without an ID do not satisfy the confirmation
criterion.

**Canonical CRM payload schema (platform-agnostic):**

This is the input to `create_lead()`. The concrete CRM adapter maps these fields to
the platform's own schema.

```json
{
  "contact": {
    "email":   "string | null",
    "name":    "string | null",
    "company": "string | null",
    "role":    "string | null"
  },
  "lead": {
    "source":         "website-chat",
    "lead_level":     "hot | warm | cold",
    "handoff_reason": "hot_lead | explicit_request | stall | llm_failure",
    "triggered_at":   "ISO 8601 UTC datetime",
    "session_id":     "uuid-v4"
  },
  "qualification": {
    "problem_fit":        "not_detected | partially_confirmed | confirmed",
    "authority_fit":      "not_detected | partially_confirmed | confirmed",
    "company_fit":        "not_detected | partially_confirmed | confirmed",
    "timing_fit":         "not_detected | partially_confirmed | confirmed",
    "is_consultant":      "boolean",
    "referral_mentioned": "boolean"
  },
  "notes": {
    "summary":          "string — output of build_summary()",
    "signals_observed": "serialised list[SignalEntry]",
    "turn_count":       "integer"
  }
}
```

> *`ContextPacket` schema: see [Data Models — ContextPacket](./trd-data-model.md#contextpacket).*

---

### Email Fallback

**Trigger:** Both Slack and CRM have exhausted retries (total failure path — Section 3).

**Destination:** `sales@` — configured via `HANDOFF_FALLBACK_EMAIL`.

**Implementation:** SMTP via the configured mail provider. This is not a visitor-facing
email — it is an internal operational fallback. Configured via `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER`, `SMTP_PASSWORD`.

**Content:** Plain text summary derived from the `ContextPacket`:

```text
Subject: [CHAT FALLBACK] {lead_level} Lead — {visitor_company or Unknown}

This lead notification was delivered by email because both Slack and CRM delivery failed.

Session ID:   {session_id}
Lead level:   {lead_level}
Trigger:      {handoff_reason}
Timestamp:    {triggered_at}

Visitor:
  Email:      {visitor_email or Not captured}
  Name:       {visitor_name or Unknown}
  Company:    {visitor_company or Unknown}
  Role:       {visitor_role or Unknown}

Qualification:
  Problem:    {problem_fit}
  Authority:  {authority_fit}
  Company:    {company_fit}
  Timing:     {timing_fit}

Summary:
{conversation_summary}

---
Slack delivery status:  FAILED
CRM delivery status:    FAILED
```

This email is the last-resort channel. It has no confirmation mechanism beyond SMTP
delivery. If SMTP also fails, the failure is logged at CRITICAL and no further
delivery is attempted. The `HandoffRecord` records all three channels' final status.

---

## Fallback Form

**There is no fallback form endpoint in this system.**

EC-07 is resolved by design: the widget's graceful degradation state displays a link to `fallback-url` — an HTML attribute pointing to the existing company contact form or any external form URL. Form submission is handled entirely by the host site's own infrastructure.

This is an explicit architectural boundary: the fallback submission path has zero dependency on the AI backend. If the AI backend is down, the fallback form still works because it does not interact with this system at all.

**Implications:**

- No backend endpoint is built for fallback form submission.
- The `fallback-url` attribute is validated as a non-empty string on widget
  `connectedCallback`. If absent, the widget logs a `ConfigurationError` and renders
  a fallback message without a link (degraded but functional — Section 3).
- Leads submitted via the fallback form are not automatically created in the CRM by
  this system. They are handled by whatever process currently handles the company
  contact form. This is a known gap — the sales team has been informed (human-handoff.md).

---

## Internal Component Interfaces

These are the contracts between internal components — not HTTP APIs, but typed function
interfaces. Specifying them here allows components to be developed and tested in isolation
against stubs before integration.

---

### `retrieve_knowledge` — LLM Tool Definition

This is the tool specification passed to Claude Haiku 4.5 in the `generate_response` node.
It is reproduced here as the canonical definition; Section 3.1 references this section.

```json
{
  "name": "retrieve_knowledge",
  "description": "Retrieve relevant information from the company knowledge base. Call this tool when the visitor asks about company services, case studies, team expertise, engagement models, or any question that requires specific company information beyond what is in your instructions. Do not call this tool for pricing questions, handoff mechanics, or general conversation process — those are handled from your instructions.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The search query to use for retrieval. Should be a precise restatement of what the visitor needs to know, not a copy of the visitor's exact words."
      }
    },
    "required": ["query"]
  }
}
```

**Invocation contract:**

```python
# The orchestrator registers this as a LangGraph tool callback:
async def retrieve_knowledge(query: str) -> RetrievalResult:
    """
    Called by the LLM when it issues a retrieve_knowledge tool call.
    Delegates to the RAG Triage Module (Section 3).
    Returns RetrievalResult — see Section 3 for the full schema.
    """
    ...
```

**Single call per turn:** `MAX_TOOL_CALLS_PER_TURN = 1` is enforced by the orchestrator.
If the LLM issues a second `retrieve_knowledge` call within the same turn, the call is
ignored and logged as `rag_extra_tool_call_ignored` at WARN. The `generate_response` node
proceeds with the result from the first call only.

---

### `dispatch_handoff` — Orchestrator → Human Handoff Subsystem

```python
async def dispatch_handoff(request: HandoffRequest) -> None:
    """
    Called by the propose_handoff node when a handoff is triggered.
    Fire-and-forget from the orchestrator's perspective — the orchestrator
    does not await delivery confirmation. Delivery status is tracked
    independently by the Human Handoff Subsystem and persisted to HandoffRecord.
    """
    ...
```

**`HandoffRequest` schema** (canonical definition — Section 3 and Section 4 reference this):

```python
@dataclass
class HandoffRequest:
    session_id:     str
    handoff_reason: Literal["hot_lead", "explicit_request", "stall", "llm_failure"]
    lead_level:     Literal["hot", "warm", "cold"]
    business_hours: bool          # from Business Hours Detection Module (Section 3)
    session_state:  SessionState  # full snapshot at point of handoff trigger
    triggered_at:   datetime      # UTC
```

**Fire-and-forget rationale:** The `propose_handoff` node streams a response to the visitor
before `dispatch_handoff` completes. Awaiting delivery confirmation would block the response
stream and add 1–10s of latency (including retry wait time) to the visitor's perceived
response time. The delivery outcome does not affect what the visitor sees.

---

### `is_business_hours` — Business Hours Detection Module

```python
def is_business_hours(at: datetime | None = None) -> bool:
    """
    Returns True if the given UTC datetime falls within Company business hours:
    Monday–Friday, 09:00–18:00 CET/CEST.

    Uses IANA timezone identifier 'Europe/Madrid' via Python zoneinfo.
    DST transitions are handled automatically.

    If `at` is None, uses datetime.now(UTC).
    No public holiday awareness in v1 — documented as a known limitation (EC-04).
    """
    ...
```

**Called by:** `propose_handoff` node to determine which proposal template to use
(in-hours direct connection offer vs. outside-hours capture flow — Section 3).

**Implementation note (EC-04):** The function uses `zoneinfo.ZoneInfo("Europe/Madrid")`
and Python's standard `datetime` library for DST-aware conversion. It does not use a
fixed UTC offset. Public holiday awareness is not implemented in v1 — the service
operates as if every weekday is a working day. This is a known limitation, documented
in Section 11.

---

### `emit_event` — Analytics Event Interface

```python
async def emit_event(event: AnalyticsEvent) -> None:
    """
    Emits a backend analytics event to the analytics pipeline.
    Called by the write_state node at the end of each turn.
    Fire-and-forget — analytics failures do not affect the session.
    """
    ...
```

**Backend analytics events** (complement to the client-side events defined in Section 3):

| Event name | Trigger | Backend fields |
| --- | --- | --- |
| `qualification_state_changed` | A `QualificationState` dimension changed level on this turn | `session_id`, `dimension`, `from_level`, `to_level`, `signal_type`, `turn_index`, `timestamp` |
| `handoff_dispatched` | `dispatch_handoff` called | `session_id`, `handoff_reason`, `lead_level`, `business_hours`, `timestamp` |
| `handoff_delivered` | Both channels confirmed | `session_id`, `slack_ok`, `crm_ok`, `timestamp` |
| `handoff_partial_failure` | One channel failed after retries | `session_id`, `failed_channel`, `timestamp` |
| `handoff_total_failure` | Both channels failed | `session_id`, `timestamp` |
| `rag_retrieved` | `retrieve_knowledge` returned results above threshold | `session_id`, `query_length`, `chunks_returned`, `top_score`, `turn_index`, `timestamp` |
| `rag_no_result` | `retrieve_knowledge` returned no results above threshold | `session_id`, `turn_index`, `timestamp` |
| `prompt_compliance_violation` | LLM generated a Stage 3 proposal outside `propose_handoff` | `session_id`, `turn_index`, `timestamp` |

> *Client-side analytics events (fired by the widget) are specified in Section 3 —
> Analytics Events. Backend events defined here are complementary and fired server-side.*

---

## SSE Format Agreement (Blocker for Phase 2)

ADR-005 explicitly leaves the SSE event format as an open item to be agreed between
frontend and backend engineers before Phase 2 integration begins. Previous section defines
this format. The items below must be confirmed by both teams before Phase 2 starts:

| Item | Specification (this document) | Action required |
| --- | --- | --- |
| SSE event format | `data: <json>\n\n` — one JSON object per event, no `id:` or `event:` fields | Confirm with frontend |
| Event types | `token`, `done`, `error` | Confirm with frontend |
| `done` event fields | `lead_level`, `current_stage`, `stage3_proposal_issued`, `handoff_reason`, `turn_count` | Confirm widget analytics event mapping (Section 3) |
| LangGraph `astream_events` → SSE mapping | `on_chat_model_stream` events → `token` events; graph completion → `done` event | Confirm with backend implementer |
| Error event scope | Turn-level only; does not activate widget fallback | Confirm with frontend |
| HTTP 503 activates fallback | Yes — pre-stream HTTP errors trigger fallback state | Confirm with frontend |

This agreement must be documented as a comment block in the `assistant-ui` runtime adapter implementation.

---

*Engineering concerns resolved by this section:*
*— EC-07: No fallback form endpoint exists in this system. The fallback is a widget UI state linking to `fallback-url`. The submission path is entirely independent of the AI backend.*
