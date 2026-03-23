-- Extension pgvector pour les embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Utilisateurs ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                  TEXT PRIMARY KEY,
    username            TEXT,
    public_key          TEXT,
    stripe_customer_id  TEXT,
    is_premium          BOOLEAN DEFAULT FALSE,
    premium_until       TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── Mémoires vectorielles ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memories (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB DEFAULT '{}',
    category    TEXT DEFAULT 'general',
    importance  INTEGER DEFAULT 1,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS memories_user_id_idx ON memories(user_id);
CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── États des companions ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companion_states (
    user_id             TEXT NOT NULL,
    companion_id        TEXT NOT NULL,
    attachment          INTEGER DEFAULT 0,
    mood                TEXT DEFAULT 'neutre',
    message_count       INTEGER DEFAULT 0,
    last_seen           TIMESTAMP WITH TIME ZONE,
    relationship_notes  TEXT,
    PRIMARY KEY (user_id, companion_id)
);

-- ── Conversations (pour l'entraînement) ───────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    companion_id    TEXT NOT NULL,
    user_message    TEXT NOT NULL,
    ai_response     TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversations_companion_idx ON conversations(companion_id);
CREATE INDEX IF NOT EXISTS conversations_created_at_idx ON conversations(created_at DESC);

-- ── Prompts des companions (historique des améliorations) ──────────────
CREATE TABLE IF NOT EXISTS companion_prompts (
    id              SERIAL PRIMARY KEY,
    companion_id    TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    version         INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT FALSE,
    analysis_notes  TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS companion_prompts_active_idx ON companion_prompts(companion_id, is_active);
