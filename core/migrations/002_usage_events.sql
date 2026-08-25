-- core/migrations/002_usage_events.sql
-- Cost Telemetry Reliability PR2 — durable usage event log (shadow only)
--
-- Single durable source of truth for every paid AI provider call (Anthropic
-- text, OpenAI text fallback, OpenAI Whisper STT — and whatever gets added
-- next). Replaces /tmp/usage.jsonl (ephemeral, per-instance, wiped on
-- restart/redeploy) as the intended long-term source, but this PR is
-- SHADOW ONLY: nothing reads from this table to drive AI_Usage_Daily or
-- the EMERGENCY_STOP_AI trigger yet — see core/usage_telemetry.py's
-- module docstring. cost_monitor.py's existing trigger is untouched.
--
-- Deliberately NOT Anthropic-token-shaped: provider/service/model are all
-- data, not schema. quantity_in/quantity_out + unit describe what was
-- actually billed (tokens for LLM text calls, seconds for STT) so a new
-- provider or service (embeddings, images, ...) is a new row shape, not a
-- new table or new columns.
--
-- request_id is the provider's own response/request id when available
-- (Anthropic Message.id "msg_...", OpenAI response id). Deduplicated as
-- UNIQUE(provider, request_id), NOT a bare UNIQUE(request_id) — different
-- providers mint ids from separate namespaces (Anthropic's "msg_..." and
-- OpenAI's own id format aren't guaranteed disjoint against every future
-- provider this table might grow to include), so scoping the uniqueness
-- constraint to the provider avoids a same-string-different-provider
-- collision silently swallowing a real, distinct call as a "duplicate".
-- This is still exactly what prevents the same underlying API call from
-- being double-counted even if it's observed from more than one call site
-- (e.g. an Anthropic->OpenAI fallback must record the OpenAI call once,
-- not the Anthropic attempt AND the OpenAI call — see
-- core/usage_telemetry.py's module docstring). NULL request_id is allowed
-- (some SDK responses don't expose one) and is never deduplicated against
-- other NULLs for the same provider — standard Postgres NULL-not-equal-
-- NULL semantics, unaffected by the two-column constraint.

CREATE TABLE IF NOT EXISTS usage_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    provider TEXT NOT NULL,              -- "anthropic" | "openai"
    service TEXT NOT NULL,               -- "text" | "stt" | ... (extensible)
    model TEXT NOT NULL,                 -- exact model string in the provider's own namespace
    source TEXT NOT NULL,                -- calling code site: run_agent, llm_fallback, interaction_engine, creative_generator, voice_stt_adapter, ...
    caller TEXT,                         -- free-form context (e.g. ctx.memory_key)
    unit TEXT NOT NULL,                  -- "tokens" | "seconds" — what quantity_in/quantity_out mean
    quantity_in NUMERIC,                 -- e.g. input tokens; NULL when not applicable (STT has no "in" side)
    quantity_out NUMERIC NOT NULL,       -- e.g. output tokens, or STT duration_seconds — always the primary billed quantity
    cost_usd NUMERIC NOT NULL,           -- computed via core.model_pricing at write time
    cost_is_estimate BOOLEAN NOT NULL DEFAULT FALSE,  -- true when pricing hit the documented fail-safe (unrecognized model)
    request_id TEXT,
    meta JSONB,                          -- e.g. {"fallback_from": "anthropic", "fallback_reason": "timeout"}
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    capability_id TEXT NOT NULL DEFAULT 'legacy.unknown',
    execution_class TEXT NOT NULL DEFAULT 'UNKNOWN',
    UNIQUE(provider, request_id)
);

-- Keep existing installations readable while adding the first semantic
-- attribution dimensions. Legacy rows are explicit unknowns, never inferred.
ALTER TABLE usage_events
    ADD COLUMN IF NOT EXISTS capability_id TEXT NOT NULL DEFAULT 'legacy.unknown';
ALTER TABLE usage_events
    ADD COLUMN IF NOT EXISTS execution_class TEXT NOT NULL DEFAULT 'UNKNOWN';

CREATE INDEX IF NOT EXISTS idx_usage_events_ts
    ON usage_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_provider_service
    ON usage_events(provider, service);
CREATE INDEX IF NOT EXISTS idx_usage_events_model
    ON usage_events(model);
CREATE INDEX IF NOT EXISTS idx_usage_events_source
    ON usage_events(source);
