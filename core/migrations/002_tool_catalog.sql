-- SCOREBOS Tool Catalog Phase 2
-- Canonical editorial catalog only. Runtime reads the generated local snapshot.

CREATE TABLE IF NOT EXISTS tools (
    tool_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    tool_class TEXT NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    playbook JSONB,
    execution_mode TEXT NOT NULL,
    agent_mode TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    decision TEXT NOT NULL,
    privacy_class TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    last_verified_at TEXT,
    next_verification_at TEXT,
    verification_source TEXT,
    owner_notes TEXT,
    next_trigger TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capabilities (
    capability_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    lifecycle_status TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tool_capabilities (
    tool_capability_id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL REFERENCES tools(tool_id) ON DELETE CASCADE,
    capability_id TEXT NOT NULL REFERENCES capabilities(capability_id) ON DELETE CASCADE,
    execution_mode TEXT NOT NULL,
    agent_mode TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (tool_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_tools_tool_class ON tools(tool_class);
CREATE INDEX IF NOT EXISTS idx_tools_lifecycle_status ON tools(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_tool_capabilities_capability_id ON tool_capabilities(capability_id);
