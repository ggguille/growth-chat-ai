---
description: "TRD Section 10 — Component-by-component failure mode table with system behaviour and recovery paths; graceful degradation specifications for AI backend unavailability, handoff partial/total failure, and RAG bypass; and the sliding-window context management strategy — resolves EC-07, FR-19, and EC-13."
---

# TRD Section 10 — Resilience and Degradation

## Failure Modes

The table below consolidates failure modes across all system components. Each row defines the failure condition, the system's behaviour, the user-facing impact, and the recovery path.

| Component | Failure mode | System behaviour | User-facing impact | Recovery |
| --- | --- | --- | --- | --- |
| **Chat API** | Service unreachable (Fly.io machine down, deploy failure) | Widget detects connection error on first request; activates fallback state after `VITE_STREAM_TIMEOUT_MS` (default 10s) | Visitor sees fallback message with link to contact form | Ops alert via uptime monitor; redeploy or Fly.io auto-restart |
| **Chat API** | HTTP 5xx on subsequent turn (session already active) | Widget shows inline error for that turn only; session continues | Turn fails silently with a retry prompt | Automatic — next visitor message retries normally |
| **Conversation Orchestrator** | `update_state` LLM call fails or times out | Log `state_extraction_failure`; proceed to `score_router` with unchanged `SessionState` | No visible impact — LLM continues with prior qualification state | None — next turn retries extraction from current message |
| **Conversation Orchestrator** | `generate_response` LLM call fails | Log `llm_generation_failure`; return graceful fallback message; route to `propose_handoff` with `reason = "llm_failure"` | Visitor receives: *"I'm having trouble responding right now — can I connect you with the team directly?"* | Handoff captures lead; session closes or continues from proposal |
| **Conversation Orchestrator** | `generate_response` stream timeout (`> LLM_STREAM_TIMEOUT_MS`) | Close stream; emit `stream_timeout` event; return same fallback message as LLM call failure | Same as LLM call failure | Same as LLM call failure |
| **LLM — Claude Haiku 4.5** | Anthropic API degradation or outage | `generate_response` and `update_state` calls time out or return errors; Orchestrator error handling activates | Visitors receive fallback message; active sessions trigger `llm_failure` handoff path | Ops alert via LLM error rate metric; no automated recovery — Anthropic SLA |
| **RAG — Knowledge Retriever** | `retrieve_knowledge` returns no results above threshold | Log `rag_no_result`; proceed with response generation without retrieved context; LLM acknowledges knowledge limit | Visitor receives honest "I don't have that information" response | None required — LLM handles gracefully via prompt instruction |
| **RAG — Knowledge Retriever** | Embedding API (OpenAI) unavailable | Log `embedding_api_failure`; retrieval cannot proceed; treat as `rag_no_result` | Same as no-result case above | Ops alert via RAG failure rate metric; no automated retry in v1 |
| **RAG — Knowledge Retriever** | pgvector / vector search failure | Log `vector_search_failure`; treat as `rag_no_result` | Same as no-result case above | Same as embedding API failure |
| **PostgreSQL — Checkpointer** | Read failure at session start | Log `checkpointer_read_failure` at ERROR; initialise fresh `SessionState`; session proceeds as new | Visitor loses prior session context — conversation restarts | No automated recovery; ops alert via checkpointer failure rate metric |
| **PostgreSQL — Checkpointer** | Write failure at turn end | Log `checkpointer_write_failure` at ERROR; turn considered complete (response already streamed) | No visible impact — response was delivered | Next turn loads last good persisted state; current turn's qualification progress may be lost |
| **Human Handoff Subsystem** | Slack delivery fails after 3 retries | Log `handoff_partial_failure` at ERROR; send fallback email to `FALLBACK_EMAIL_ADDRESS`; persist `HandoffRecord` with `slack_ok = False` | No visible impact — visitor has already received the handoff proposal | Manual follow-up via ops alert |
| **Human Handoff Subsystem** | CRM delivery fails after 3 retries | Log `handoff_partial_failure` at ERROR; send fallback email; persist `HandoffRecord` with `crm_ok = False` | No visible impact | Same as Slack failure |
| **Human Handoff Subsystem** | Both Slack and CRM fail after retries | Log `handoff_total_failure` at CRITICAL; send fallback email; `handoff_triggered = False` in `SessionState` | No visible impact — visitor's email was captured | Ops CRITICAL alert; manual follow-up required; `handoff_triggered = False` allows re-attempt if visitor returns (v2 feature) |
| **Human Handoff Subsystem** | Fallback SMTP also fails | Log `fallback_email_failure` at CRITICAL; no further automated delivery in v1 | No visible impact | Ops CRITICAL alert; manual recovery via raw session log in PostgreSQL |
| **Human Handoff Subsystem** | `generate_context_packet()` raises exception | Log `context_packet_generation_failure` at ERROR; abort delivery; emit CRITICAL alert; `handoff_triggered = False` | No visible impact | Ops CRITICAL alert; manual recovery |
| **Chat Widget** | `api-url` attribute missing | Widget logs `ConfigurationError`; renders in permanent fallback state | Visitor sees fallback message without link | Fix configuration and redeploy widget embed |
| **Chat Widget** | `fallback-url` attribute missing | Widget logs `ConfigurationError`; fallback state renders without a link — degraded but functional | Visitor sees fallback message without a clickable link | Fix configuration; not a blocking failure |
| **State Machine** | `update_state` produces invalid `QualificationDelta` | Log `state_update_validation_failure`; discard delta; session continues with unchanged `QualificationState` | No visible impact | Next turn retries extraction from full conversation context |
| **State Machine** | Qualification dimension monotonicity violation | Log `qualification_monotonicity_violation` at WARN; reject downgrade silently; retain higher confidence level | No visible impact | No action required |
| **State Machine** | `CONTEXT_WINDOW_TURNS` set to `0` or negative | Raise `ConfigurationError` at startup; prevent service from starting | Service unavailable — widget activates fallback | Fix configuration and redeploy |
| **Business Hours Detection** | `BUSINESS_HOURS_TIMEZONE` not set or invalid | Default to `Europe/Madrid`; log `ConfigurationError` at WARN | No visible impact — handoff routing proceeds with default timezone | Fix configuration; low urgency |

---

## Graceful Degradation

### AI Backend Unavailable — Fallback Form

**Resolution of EC-07.**

When the AI backend is unavailable, the Chat Widget activates a permanent fallback state for the duration of the browser session. The fallback path has zero dependency on the AI backend — it is architecturally independent by design.

**Fallback activation conditions:**

| Condition | Trigger |
| --- | --- |
| Connection error on first request | Widget cannot reach `api-url` within `VITE_STREAM_TIMEOUT_MS` |
| HTTP 5xx on first request | Chat API returns a server error before any tokens are streamed |
| Stream timeout on first request | No token received within `VITE_STREAM_TIMEOUT_MS` ms |

**Note:** A connection error or timeout on a *subsequent* turn (session already active) does **not** activate fallback — it shows an inline error for that turn only. Fallback is only triggered on the first request failure, when no session context has been established.

**Fallback UI:**

The chat panel replaces the message input with:

> *"Our chat assistant isn't available right now. You can still reach us using our contact form."*
> **[Contact us →]** *(opens `fallback-url` in a new tab)*

The visitor cannot send messages in fallback state. The launcher button remains visible.

**Fallback is session-permanent.** Once activated, no retry is attempted from the widget. Repeated retries on a down backend generate noise in error logs without improving the visitor experience.

**Fallback form submission path:**

The `fallback-url` attribute points to the existing company contact form or any external URL. The form submission is handled entirely by the host site's own infrastructure. This system builds no backend endpoint for fallback submissions.

**Known gap:** Leads submitted via the fallback form are not automatically created in the CRM by this system. They are handled by whatever process currently handles the company contact form. The sales team has been informed. This is an accepted limitation for MVP. See also: Section 12 — Open Questions.

---

### Handoff Partial Failure — One Channel Down

**Resolution of FR-19.**

When one delivery channel (Slack or CRM) fails after exhausting retries and the other succeeds, the handoff is considered partially failed.

```text
Partial failure handling:

1. Log failed channel at ERROR:
     fields: session_id, failed_channel, last_http_status, attempt_count, triggered_at

2. Emit WARN-level ops alert (Better Stack)

3. Send fallback email to FALLBACK_EMAIL_ADDRESS:
     Subject: "[HANDOFF FALLBACK] [lead_level] lead — [visitor_email or session_id]"
     Body: full ContextPacket as plain text

4. Persist HandoffRecord:
     slack_ok / crm_ok reflects actual delivery outcome

5. Set SessionState.handoff_triggered = True
     (one channel confirmed — handoff is considered dispatched)
```

The visitor is not informed of the delivery failure in either case. The `propose_handoff` node has already delivered its proposal and collected the visitor's email before delivery is attempted.

---

### Handoff Total Failure — Both Channels Down

When both Slack and CRM fail after exhausting retries:

```text
Total failure handling:

1. Log both channels at ERROR
2. Emit CRITICAL-level ops alert (Better Stack)
3. Send fallback email to FALLBACK_EMAIL_ADDRESS (same format as partial failure)
4. Persist HandoffRecord: slack_ok = False, crm_ok = False
5. Set SessionState.handoff_triggered = False
   // False allows re-attempt if the visitor returns (v2 feature)
```

If SMTP also fails, log `fallback_email_failure` at CRITICAL. No further automated delivery in v1. Manual recovery is required via the raw session log in PostgreSQL.

---

### LLM Failure Mid-Conversation — Capture Handoff

When `generate_response` fails or times out during an active session, the orchestrator does not terminate the session silently. Instead:

1. It returns a graceful fallback message: *"I'm having trouble responding right now — can I connect you with the team directly?"*
2. It routes to `propose_handoff` with `reason = "llm_failure"`.
3. The handoff proposal captures the visitor's email before the session ends.

This ensures that even a hard LLM failure produces a lead capture attempt, not a silent drop.

---

### RAG Unavailable — Retrieval Bypass

When the Knowledge Retriever cannot return results (embedding API failure, vector search failure, or no results above threshold):

- The orchestrator proceeds with response generation without retrieved context.
- The LLM is instructed to acknowledge the knowledge limit honestly: *"I don't have specific information on that — let me connect you with the team."*
- If the query was domain-specific, this typically triggers a natural handoff.
- No fallback retrieval source is implemented in v1.

RAG failure does not affect session continuity. The conversation continues; only the quality of domain-specific answers is degraded.

---

### Checkpointer Failure — State Loss Scenarios

| Scenario | Behaviour | Data lost |
| --- | --- | --- |
| **Read failure at session start** | Fresh `SessionState` initialised; session proceeds as new | All prior session context — conversation restarts from scratch |
| **Write failure at turn end** | Turn completes normally (response already streamed) | Current turn's qualification dimension updates |

Neither failure terminates the session from the visitor's perspective. The risk is qualification state loss, which may cause the LLM to re-ask questions already answered in the evicted turn. This is acceptable for MVP given the low expected frequency of checkpointer failures.

---

## Context Window Management

**Resolution of EC-13.**

### Strategy

The conversation history passed to the LLM is a **sliding window** of fixed maximum size. When the window is full and a new message is added, the oldest exchange pair (one visitor message + one assistant message) is evicted.

This strategy is chosen over hard limits (which terminate conversations abruptly) and summarisation (which adds LLM cost and latency per turn) for MVP. See Engineering Review EC-13 for the evaluation.

### What the Sliding Window Contains

The window holds the last `CONTEXT_WINDOW_TURNS` visitor/assistant exchange pairs. Default: `10` pairs (20 individual messages).

**What is evicted:** raw message history — the text of older exchanges.

**What is never evicted:** qualification state. The `QualificationState` object (`problem_fit`, `authority_fit`, `company_fit`, `timing_fit`, confidence levels, `signals_observed`) is stored independently of the message window and injected fresh every turn. The LLM never loses qualification context due to window eviction.

Additionally, the following `SessionState` fields survive window eviction and are always available:

- `lead_level`
- `turn_counter`
- `stage3_proposals_issued`
- `visitor_email`, `visitor_name`, `visitor_company`, `visitor_role`
- `is_consultant`, `is_negative_persona`, `is_no_fit`
- `referral_mentioned`
- `signals_observed`

### Eviction Behaviour

```text
On each new exchange:

if len(messages) >= CONTEXT_WINDOW_TURNS * 2:
    messages.pop(0)  # evict oldest visitor message
    messages.pop(0)  # evict oldest assistant message

messages.append(new_visitor_message)
messages.append(new_assistant_message)
```

Eviction happens before the new exchange is appended, ensuring the window never exceeds the configured size.

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `CONTEXT_WINDOW_TURNS` | `10` | Number of visitor/assistant exchange pairs retained in the sliding window. Setting to `0` or negative raises a `ConfigurationError` at startup. |

The window size is tunable post-launch. Increasing the window increases per-turn token cost and latency. Decreasing it risks the LLM re-asking questions already answered in evicted turns (mitigated by the always-fresh `QualificationState` injection).

### Context Window Budget

The full context budget per turn is allocated as follows (reference values for `CONTEXT_WINDOW_TURNS = 10`):

| Layer | Allocation | Notes |
| --- | --- | --- |
| System prompt (stable layers 1–6) | ~2,000 tokens | Role, conversation model, prohibited behaviours, knowledge scope, handoff instructions |
| Qualification state (layer 7) | ~500 tokens | JSON-serialised `QualificationState`; injected fresh every turn |
| Retrieved chunks (layer 8) | ~1,500 tokens | Only when `retrieve_knowledge` is called; omitted otherwise |
| Conversation history (layer 9) | ~5,000 tokens | Last 10 exchange pairs at ~250 tokens per pair |
| **Total (with retrieval)** | **~9,000 tokens** | Well within Claude Haiku 4.5's 200K token context window |

The system is not at risk of context overflow at default configuration. The `CONTEXT_WINDOW_TURNS` cap is a **cost control**, not a hard technical constraint at current window sizes.

### v1 Limitation

No summarisation of evicted turns is performed. If a visitor references something said in an evicted exchange, the LLM will not have that context. In practice, the `QualificationState` injection mitigates most continuity risks — the key facts (problem, authority, company, timing) are always present regardless of window eviction.

Summarisation-based context compression is identified as a v2 enhancement if post-launch conversation depth metrics indicate meaningful continuity failures.

---

*Engineering concerns resolved by this section: EC-07 (graceful degradation fallback destination), EC-13 (context window strategy and turn limit). FR-19 (partial handoff failure behaviour) is fully specified here. The failure mode table in consolidates error handling dispersed across Section 3 into a single reference.*
