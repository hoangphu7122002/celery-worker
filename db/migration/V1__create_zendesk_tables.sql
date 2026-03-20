-- Zendesk webhook events
CREATE TABLE IF NOT EXISTS zendesk_webhooks (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL DEFAULT '{}',
    processed_at TIMESTAMP WITH TIME ZONE,
    error TEXT
);

-- Zendesk tickets (synced from API)
CREATE TABLE IF NOT EXISTS zendesk_tickets (
    id SERIAL PRIMARY KEY,
    zendesk_ticket_id INTEGER NOT NULL UNIQUE,
    payload JSONB DEFAULT '{}',
    audit_events JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error TEXT
);

-- Sync run tracking
CREATE TABLE IF NOT EXISTS sync_requests (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    start_date DATE,
    updated_ticket_ids JSONB,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- Motion records (upserted from tickets)
CREATE TABLE IF NOT EXISTS motions (
    id SERIAL PRIMARY KEY,
    source_key VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    result VARCHAR(50) NOT NULL DEFAULT 'unknown',
    status VARCHAR(50) NOT NULL DEFAULT 'unknown'
);
