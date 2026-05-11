---
description: "Data models for the Zartis AI-powered lead qualification chat — canonical schemas for SessionState, QualificationState, ContextPacket, HandoffRecord, Message, and KnowledgeChunk, with PII classification, retention rules, and database DDL."
---

# Data Models

> **Relationship to Section 3 - Component Specification:**
> This section is the authoritative schema reference for all data structures used by the system.
> Sections 3.1 (Conversation Orchestrator), 3.2 (Qualification State Machine), 3.4 (Human Handoff
> Subsystem), and 3.6 (Context Packet Generator) describe the logic that reads and writes these
> structures. Where those sections previously contained inline schema definitions, they now
> reference this section instead.
>
> **Lead records are out of scope.** The system does not maintain its own lead records.
> The CRM (external system, OQ-04) is the system of record for leads. The `HandoffRecord`
> (Section 4.4) is the system's own audit artefact — it is not a lead record.

---

## SessionState

`SessionState` is the typed dict passed as LangGraph graph state. It is the single source of
truth for all per-session data. Every node in the Conversation Orchestrator reads from and
writes to this object via the LangGraph state-passing contract.

### Session Schema

```text
SessionState {

  # ── Session identity ─────────────────────────────────────────────
  session_id          : str          // UUID v4; used as LangGraph thread_id
  created_at          : datetime     // UTC; set on first turn, never updated
  last_updated_at     : datetime     // UTC; updated at write_state node on every turn

  # ── Conversation history (sliding window) ────────────────────────
  messages            : list[Message]
  // Sliding window of the last CONTEXT_WINDOW_TURNS exchange pairs.
  // Oldest entries are evicted when the window is full — see Section 4.5.
  // Schema: see Section 4.5.

  # ── Qualification state ──────────────────────────────────────────
  qualification       : QualificationState
  // See Section 4.2 for full schema and transition rules.

  # ── Session control ──────────────────────────────────────────────
  lead_level          : "hot" | "warm" | "cold"   // default: "cold"
  current_stage       : 1 | 2 | 3                 // default: 1
  turn_counter        : int                        // default: 0; resets on Stage 3 proposal
  stage3_proposals_issued : int                    // default: 0; incremented in propose_handoff
  explicit_human_request  : bool                   // default: False; set by update_state

  # ── Visitor data ─────────────────────────────────────────────────
  visitor_email       : str | None    // default: None — PII (see Section 4.6)
  visitor_name        : str | None    // default: None — PII (see Section 4.6)
  visitor_company     : str | None    // default: None — business data, not PII
  visitor_role        : str | None    // default: None — business data, not PII
  is_consultant       : bool          // default: False
  referral_mentioned  : bool          // default: False

  # ── Session outcome ──────────────────────────────────────────────
  handoff_triggered   : bool          // default: False
  handoff_reason      : "hot_lead" | "explicit_request" | "stall" | "llm_failure" | None
  termination_type    : "explicit_close" | "inactivity_timeout" | "session_expiry" | None
}
```

### Field notes

| Field | Notes |
| --- | --- |
| `session_id` | Generated client-side as UUID v4; sent in every API request as the `ZGC-Session-ID` header; used as the LangGraph `thread_id` for checkpointer lookup |
| `lead_level` | Derived by `score_router` at each turn from `QualificationState` — see `derive_lead_level()` in Section 3.2. The stored value reflects the last computed level and is used for context packet generation only; routing always recomputes from raw dimensions |
| `current_stage` | Follows the respond → advance → propose sequence; Stage 3 is not terminal — see stage transition rules in Section 3.2 |
| `turn_counter` | Incremented by the `stall_check` node; resets to `0` when `propose_handoff` executes; used exclusively for stall detection |
| `stage3_proposals_issued` | Monotonically increasing across the session; used to distinguish first-time proposals from repeat proposals after the visitor declines |
| `explicit_human_request` | Set to `True` by `update_state` when explicit human request patterns are detected; once set, never unset within the session |
| `handoff_triggered` | `True` when at least one handoff delivery attempt completed (both channels confirmed, or partial failure accepted); `False` on total failure — see Section 3.4 |

### Persistence backend

| Environment | Backend | Notes |
| --- | --- | --- |
| Local development | `MemorySaver` (LangGraph built-in) | Zero configuration; state lost on process restart |
| Staging / Production | `langgraph-checkpoint-postgres` | `CHECKPOINT_DB_URL` env variable; `AsyncPostgresSaver.setup()` migration required before first deployment |

State is written once per turn at the `write_state` node, after the response stream closes.
State is read once per turn at session start, before `update_state` executes.

### Session Retention

| Condition | Retention |
| --- | --- |
| Default | 90 days from `last_updated_at`, then hard-deleted from the checkpointer |
| `handoff_triggered = True` | Retained indefinitely — deletion deferred until the corresponding CRM lead record is closed or the data subject requests erasure |

The `handoff_triggered` flag is the retention signal. A session where `handoff_triggered = False`
(including total handoff failure) is subject to the 90-day default regardless of session content.

A scheduled job evaluates `last_updated_at` and `handoff_triggered` daily and soft-deletes
expired sessions. The job implementation is specified in Section 8 (Security Requirements).

---

## QualificationState

`QualificationState` is a nested object within `SessionState`. It tracks the four fit dimensions
defined in `qualification-signals.md` and additional flags required for routing and handoff.

The `update_state` node in the Conversation Orchestrator is the **only writer** to
`QualificationState` dimensions. No other node modifies these fields.

### Qualification Schema

```text
QualificationState {

  # ── Four fit dimensions ──────────────────────────────────────────
  problem_fit         : ConfidenceLevel   // default: "not_detected"
  authority_fit       : ConfidenceLevel   // default: "not_detected"
  company_fit         : ConfidenceLevel   // default: "not_detected"
  timing_fit          : ConfidenceLevel   // default: "not_detected"

  # ── Disqualification flags ───────────────────────────────────────
  is_negative_persona : bool              // default: False
  is_no_fit           : bool              // default: False

  # ── Signal audit trail ───────────────────────────────────────────
  signals_observed    : list[SignalEntry]
  // Append-only. Never used in routing. Used by Context Packet Generator
  // and eval framework. See SignalEntry below.
}

ConfidenceLevel : "not_detected" | "partially_confirmed" | "confirmed"
```

### SignalEntry

```text
SignalEntry {
  dimension   : "problem_fit" | "authority_fit" | "company_fit" | "timing_fit"
  signal_type : "explicit" | "implicit"
  evidence    : str        // raw visitor phrase or behaviour that triggered this signal
  turn_index  : int        // absolute turn number within the session
}
```

### Confidence level transitions

Transitions are **monotonic within a session**. A dimension that has reached `confirmed`
cannot be downgraded in the same session. New evidence can only move a dimension upward.

```text
not_detected  →  partially_confirmed   (implicit signal observed)
not_detected  →  confirmed             (explicit signal observed)
partially_confirmed  →  confirmed      (explicit signal observed)
confirmed  →  confirmed                (no change on further signals)
```

Any attempt to downgrade a dimension (e.g. setting `confirmed` → `partially_confirmed`) is
rejected silently and logged as a `qualification_monotonicity_violation` WARN event.

### Lead level derivation

`lead_level` on `SessionState` is **derived**, not stored as a primary value. It is recomputed
by `score_router` on every turn using `derive_lead_level(QualificationState)`:

```python
def derive_lead_level(q: QualificationState, referral_mentioned: bool) -> "hot" | "warm" | "cold":

    # Disqualified sessions never escalate
    if q.is_negative_persona or q.is_no_fit:
        return "cold"

    # Hot: Problem(confirmed) + Authority(confirmed) + one more (≥ partially_confirmed)
    if (q.problem_fit == "confirmed"
            and q.authority_fit == "confirmed"
            and (q.company_fit in ["partially_confirmed", "confirmed"]
                 or q.timing_fit in ["partially_confirmed", "confirmed"])):
        return "hot"

    # P3 pattern: referred visitor with confirmed authority substitutes for problem_fit
    if (referral_mentioned
            and q.authority_fit == "confirmed"
            and (q.company_fit in ["partially_confirmed", "confirmed"]
                 or q.timing_fit in ["partially_confirmed", "confirmed"])):
        return "hot"

    # Warm: Problem(confirmed) + at least one additional dimension (≥ partially_confirmed)
    if (q.problem_fit == "confirmed"
            and any(d in ["partially_confirmed", "confirmed"]
                    for d in [q.authority_fit, q.company_fit, q.timing_fit])):
        return "warm"

    return "cold"
```

### Disqualification flags

`is_negative_persona = True` is set when the visitor's behaviour matches N1 (competitor) or N2
(researcher/journalist/student). Once set, it is never unset in the same session.

`is_no_fit = True` is set when the visitor expresses individual contractor scope, geographic
or regulatory mismatch, academic purpose, or any other context in the explicit disqualification
list in `chat-behaviour.md`. The `is_consultant` flag on `SessionState` is **not** a
disqualification — consultant visitors are qualified against their client's context.

When either flag is `True`, `derive_lead_level()` always returns `"cold"` and `score_router`
never routes to `propose_handoff` with `reason = "hot_lead"`. Explicit human requests
(`explicit_human_request = True`) still trigger `propose_handoff` regardless — refusing an
explicit request is prohibited (FR-10).

---

## ContextPacket

`ContextPacket` is the structured artefact generated at the point of any handoff and delivered
to the sales team via Slack and CRM. It is produced by the Context Packet Generator (Section 3.6)
as a deterministic function of `SessionState` — the same `SessionState` always produces the same
`ContextPacket`, with no LLM call and no external dependency.

### ContextPacket Schema

```text
ContextPacket {

  # ── Identity ─────────────────────────────────────────────────────
  session_id          : str           // from SessionState.session_id
  triggered_at        : datetime      // UTC — from SessionState.last_updated_at
  lead_level          : "hot" | "warm" | "cold"
  handoff_reason      : "hot_lead" | "explicit_request" | "stall" | "llm_failure"

  # ── Qualification state ──────────────────────────────────────────
  qualification : {
    problem_fit         : ConfidenceLevel
    authority_fit       : ConfidenceLevel
    company_fit         : ConfidenceLevel
    timing_fit          : ConfidenceLevel
    is_consultant       : bool
    referral_mentioned  : bool
  }

  # ── Visitor data ─────────────────────────────────────────────────
  visitor : {
    email    : str | None
    name     : str | None
    company  : str | None
    role     : str | None
  }

  # ── Conversation metadata ────────────────────────────────────────
  conversation : {
    turn_count              : int
    stage3_proposals_issued : int
    signals_observed        : list[SignalEntry]
  }

  # ── Summary ──────────────────────────────────────────────────────
  conversation_summary : str
  // 2–4 sentence template-generated summary.
  // Generated by build_summary() — see Section 3.6.
}
```

### Field derivation

Every field is derived mechanically from `SessionState`. There is no interpretation,
inference, or generation step.

| `ContextPacket` field | Derived from | Notes |
| --- | --- | --- |
| `session_id` | `SessionState.session_id` | Direct copy |
| `triggered_at` | `SessionState.last_updated_at` | Reflects the turn at which handoff was triggered |
| `lead_level` | `SessionState.lead_level` | Last computed value |
| `handoff_reason` | `SessionState.handoff_reason` | Set by `propose_handoff` node before generator is called |
| `qualification.*` | `SessionState.qualification.*` | Direct copy of all four dimensions and flags |
| `visitor.*` | `SessionState.visitor_*` fields | Direct copy; `None` for any uncollected field |
| `conversation.turn_count` | `SessionState.messages[-1].turn_index` | `0` if `messages` is empty |
| `conversation.stage3_proposals_issued` | `SessionState.stage3_proposals_issued` | Direct copy |
| `conversation.signals_observed` | `SessionState.qualification.signals_observed` | Full list — not filtered |
| `conversation_summary` | `build_summary(signals_observed)` | Template function — Section 3.6 |

### Validation preconditions

The generator raises `ContextPacketGenerationError` if any of the following checks fail:

| Precondition | Check |
| --- | --- |
| `session_id` is present | Non-empty string |
| `handoff_reason` is set | Not `None` |
| `lead_level` is valid | One of `"hot"`, `"warm"`, `"cold"` |
| `triggered_at` is present | Valid `datetime` |

Optional visitor fields (`visitor_email`, `visitor_name`, `visitor_company`, `visitor_role`)
are not validated — `None` is a valid value for all of them.

### Storage

`ContextPacket` is not persisted independently. It is:

1. Delivered to Slack and CRM at handoff time (Section 3.4).
2. Serialised as the body of the fallback email on dual-channel delivery failure.
3. Reconstructable on demand from the stored `SessionState` by calling
   `generate_context_packet(session_state)`.

There is no `context_packets` table. The `SessionState` in the checkpointer is the source
of truth; the `HandoffRecord` (Section 4.4) is the audit trail for delivery outcomes.

---

## HandoffRecord

`HandoffRecord` is the system's audit artefact for every handoff attempt. It records delivery
status per channel, retry outcomes, and the final outcome of the handoff operation. It is
persisted to PostgreSQL by the Human Handoff Subsystem (Section 3.4) after every dispatch
attempt, regardless of outcome.

The `HandoffRecord` is **not** a lead record. The external CRM is the system of record for
leads. The `HandoffRecord` exists to make handoff delivery auditable and diagnosable without
querying the CRM.

### HandoffRecord Schema

```text
HandoffRecord {
  session_id        : str             // foreign key → SessionState.session_id
  triggered_at      : datetime        // UTC; from HandoffRequest.triggered_at
  lead_level        : "hot" | "warm" | "cold"
  handoff_reason    : "hot_lead" | "explicit_request" | "stall" | "llm_failure"
  visitor_email     : str | None      // PII — see Section 4.6

  slack_status      : "ok" | "failed"
  slack_attempts    : int
  slack_last_http   : int | None      // last HTTP status received from Slack webhook

  crm_status        : "ok" | "failed"
  crm_attempts      : int
  crm_record_id     : str | None      // populated when CRM confirms creation
  crm_last_http     : int | None      // last HTTP status received from CRM API

  fallback_sent     : bool
  outcome           : "complete" | "partial_failure" | "total_failure"
  completed_at      : datetime        // UTC; when the subsystem finished processing
}
```

### Outcome definitions

| Outcome | Condition |
| --- | --- |
| `complete` | Both Slack and CRM confirmed delivery |
| `partial_failure` | One channel confirmed; one exhausted retries |
| `total_failure` | Both channels exhausted retries |

On `partial_failure` and `total_failure`, a fallback email is sent to `FALLBACK_EMAIL_ADDRESS`
and `fallback_sent` is set to `True`. The `SessionState.handoff_triggered` flag is set to `True`
on `complete` and `partial_failure`; it remains `False` on `total_failure` to allow re-attempt
if the visitor returns (v2).

### Database DDL

```sql
CREATE TABLE handoff_records (
  session_id        TEXT        NOT NULL,
  triggered_at      TIMESTAMPTZ NOT NULL,
  lead_level        TEXT        NOT NULL CHECK (lead_level IN ('hot', 'warm', 'cold')),
  handoff_reason    TEXT        NOT NULL,
  visitor_email     TEXT,                    -- PII: scrubbed on retention expiry

  slack_status      TEXT        NOT NULL CHECK (slack_status IN ('ok', 'failed')),
  slack_attempts    INT         NOT NULL DEFAULT 0,
  slack_last_http   INT,

  crm_status        TEXT        NOT NULL CHECK (crm_status IN ('ok', 'failed')),
  crm_attempts      INT         NOT NULL DEFAULT 0,
  crm_record_id     TEXT,
  crm_last_http     INT,

  fallback_sent     BOOLEAN     NOT NULL DEFAULT FALSE,
  outcome           TEXT        NOT NULL CHECK (outcome IN ('complete', 'partial_failure', 'total_failure')),
  completed_at      TIMESTAMPTZ NOT NULL,

  PRIMARY KEY (session_id, triggered_at)
);

CREATE INDEX ON handoff_records (outcome) WHERE outcome != 'complete';
CREATE INDEX ON handoff_records (triggered_at DESC);
```

The composite primary key `(session_id, triggered_at)` allows multiple handoff attempts
per session (e.g. a visitor who accepts a stall proposal and later triggers a hot lead
escalation in the same session). In practice, most sessions produce one record.

### HandoffRecord Retention

`HandoffRecord` rows are retained for 2 years from `triggered_at` for commercial audit purposes,
then hard-deleted. The `visitor_email` field is scrubbed (set to `NULL`) at the same time as the
corresponding `SessionState` is deleted (90-day default, or when the CRM lead is closed), even
though the record itself is retained longer. This ensures PII does not outlive its justification
while preserving the non-PII audit trail.

---

## Message

`Message` is the unit of conversation history stored in the `SessionState.messages` sliding
window. Messages are not persisted in their own database table — they exist exclusively as
part of the `SessionState` object in the LangGraph checkpointer.

### Message Schema

```text
Message {
  role        : "visitor" | "assistant"
  content     : str        // raw text of the turn
  turn_index  : int        // monotonically increasing within the session; never reset
  timestamp   : datetime   // UTC
}
```

### Sliding window mechanics

The `messages` list is capped at `CONTEXT_WINDOW_TURNS * 2` entries (each turn = one visitor
message + one assistant message). When the cap is reached and a new message is added, the
oldest entry is evicted.

```python
def add_message(state: SessionState, new_message: Message) -> SessionState:
    state.messages.append(new_message)
    if len(state.messages) > CONTEXT_WINDOW_TURNS * 2:
        state.messages = state.messages[-(CONTEXT_WINDOW_TURNS * 2):]
    return state
```

`turn_index` is not reset when entries are evicted. It always reflects the absolute position
in the session, allowing analytics to reason about conversation depth even after window eviction.

**What is preserved on eviction:** `QualificationState` dimensions, `lead_level`,
`turn_counter`, `stage3_proposals_issued`, all `visitor_*` fields, and `signals_observed`.
These are stored independently on `SessionState` and are never evicted. Eviction only affects
the raw message history passed to the LLM on each turn.

**Configuration:** `CONTEXT_WINDOW_TURNS` is a configurable environment variable
(default: `10`). A value of `0` or negative raises a `ConfigurationError` at startup.

### Message Storage

`Message` objects have no independent persistence. They are serialised as part of
`SessionState` by the LangGraph checkpointer and written to the `checkpoints` table in
PostgreSQL (see Section 4.1 — Persistence backend). They are subject to the same
retention rules as `SessionState`.

No raw message content is stored outside the checkpointer. In particular:

- Message content is **not** written to application logs.
- Message content is **not** persisted to any table other than the checkpointer.
- PII within message content (e.g. a visitor who types their email into the chat body before
  the structured capture step) is subject to the same 90-day retention as `SessionState`.

---

## KnowledgeChunk

`KnowledgeChunk` is a single embedded text segment from the company knowledge base, stored
in pgvector and retrieved by the RAG Triage Module (Section 3.3) at query time.

Knowledge chunks are written by the offline indexing pipeline and read by the per-turn
retrieval flow. They are never modified after indexing — updates require re-indexing the
affected source document.

### KnowledgeChunk Schema

```text
KnowledgeChunk {
  chunk_id      : str        // UUID or deterministic hash of (source, chunk_index)
  source        : str        // document title or URL slug (e.g. "case-study-fintech-rag")
  chunk_index   : int        // zero-based position within the source document
  content       : str        // raw text of the chunk
  content_hash  : str        // SHA-256 of content; used for deduplication on re-index
  embedding     : vector     // text-embedding-3-small: 1536 dimensions (production)
                             // all-MiniLM-L6-v2: 384 dimensions (local dev only)
  created_at    : timestamptz
}
```

### KnowledgeChunk Database DDL

```sql
CREATE TABLE knowledge_chunks (
  chunk_id      TEXT        PRIMARY KEY,
  source        TEXT        NOT NULL,
  chunk_index   INT         NOT NULL,
  content       TEXT        NOT NULL,
  content_hash  TEXT        NOT NULL,
  embedding     VECTOR(1536) NOT NULL,  -- production dimensions; see note below
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (source, chunk_index)
);

CREATE INDEX ON knowledge_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

**Local development table:** Because `all-MiniLM-L6-v2` produces 384-dimensional vectors
and `text-embedding-3-small` produces 1536-dimensional vectors, local and production indexes
are **incompatible**. Local development uses a separate table:

```sql
CREATE TABLE knowledge_chunks_dev (
  -- identical to knowledge_chunks except:
  embedding     VECTOR(384) NOT NULL
);
```

The table used is controlled by the `KNOWLEDGE_TABLE_NAME` environment variable
(default: `knowledge_chunks`). Local environments set this to `knowledge_chunks_dev`.
Local indexes are never promoted to production.

### HNSW index parameters

| Parameter | Value | Notes |
| --- | --- | --- |
| `m` | `16` | Number of connections per node; controls graph density |
| `ef_construction` | `64` | Build-time recall/speed trade-off |
| `ef_search` | `40` (default) | Query-time recall/latency trade-off; configurable via `RAG_HNSW_EF_SEARCH` |

Default values are appropriate for corpora under ~100K vectors. Re-evaluate if the corpus
grows past 1M vectors — see ADR-003 review triggers.

### KnowledgeChunk Retention

Knowledge chunks are retained indefinitely and updated only by re-indexing. There is no
time-based expiry. Chunks from a document that has been removed from the knowledge base
must be explicitly deleted by running the indexing pipeline with a `--delete` flag for
the affected source.

Knowledge chunk content is company-published material and contains no visitor PII. No
GDPR retention rules apply to this table.

---

## PII Classification

This section is the authoritative reference for PII classification across all data structures.
It governs: what is scrubbed before LLM API calls, what is excluded from raw logs,
and what triggers extended retention rules.

### PII fields

| Field | Location | Classification | Treatment |
| --- | --- | --- | --- |
| `visitor_email` | `SessionState`, `HandoffRecord` | **PII** | Scrubbed before LLM API calls; excluded from application logs; deleted on retention expiry; scrubbed from `HandoffRecord` at 90 days even if the record itself is retained longer |
| `visitor_name` | `SessionState`, `ContextPacket` | **PII** | Same treatment as `visitor_email` |

### Non-PII fields

| Field | Location | Classification | Notes |
| --- | --- | --- | --- |
| `visitor_company` | `SessionState`, `ContextPacket` | Business data | Company name is not considered personal data under GDPR for this system |
| `visitor_role` | `SessionState`, `ContextPacket` | Business data | Generic role description (e.g. "CTO") is not sufficient to identify a natural person |
| `session_id` | All | Technical identifier | Pseudonymous; linkable to PII only via `SessionState` |
| All `QualificationState` dimensions | `SessionState`, `ContextPacket` | Business data | Derived assessments, not personal attributes |
| `signals_observed[].evidence` | `SessionState` | May contain PII | Raw visitor phrases stored in `evidence` may incidentally contain PII (e.g. a visitor types their name into the chat). Treated as PII-adjacent: not logged separately; subject to the same 90-day `SessionState` retention |

### PII scrubbing before LLM API calls

Before any `SessionState` content is included in a prompt sent to the Anthropic API or the
OpenAI Embeddings API, the following fields are scrubbed:

- `SessionState.visitor_email` → replaced with `"[email redacted]"`
- `SessionState.visitor_name` → replaced with `"[name redacted]"`

Scrubbing is applied to the serialised qualification state injected into the `generate_response`
prompt (Section 3.1) and to query strings sent to the embedding API (Section 3.3).

The scrubbing step is applied unconditionally — even if the fields are `None` — to prevent
accidental transmission if the default changes in future.

### GDPR data notice

The chat widget displays a data notice on the visitor's first interaction (Section 3.7).
The notice must be acknowledged before any message is transmitted to the Chat API.
No visitor data reaches the backend before acknowledgement.

---

*This section is the authoritative schema reference for the Zartis lead qualification chat. Any change to a schema defined here requires a version increment to this document and, if the change affects a database table, a corresponding migration script.*
