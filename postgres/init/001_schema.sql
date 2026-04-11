CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS logs;
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS security;


CREATE TABLE metadata.service (
    id SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,
    service_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE monitoring.metrics (
    id BIGSERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES metadata.service(id),
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metrics_lookup
ON monitoring.metrics (service_id, metric_name, timestamp DESC);


CREATE TABLE monitoring.heartbeat (
    id BIGSERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES metadata.service(id),
    status TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_heartbeat_lookup
on monitoring.heartbeat (service_id, timestamp DESC);


CREATE TABLE events.service_event (
    id BIGSERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES metadata.service(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_lookup
ON events.service_event (service_id, timestamp DESC);


CREATE TABLE logs.service_log (
    id BIGSERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES metadata.service(id),
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_logs_lookup
ON logs.service_log (service_id, timestamp DESC);


CREATE TABLE security.access_event (
    id BIGSERIAL PRIMARY KEY,
    service_id INT REFERENCES metadata.service(id),
    target_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ip_address INET,
    username TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        (target_type = 'host' AND service_id IS NULL)
        OR
        (target_type = 'service' AND service_id IS NOT NULL)
    )
);

CREATE INDEX idx_access_event_lookup
ON security.access_event (service_id, target_type, event_type, timestamp DESC);

CREATE INDEX idx_access_event_ip
ON security.access_event (ip_address);


CREATE TABLE security.session (
    id BIGSERIAL PRIMARY KEY,
    service_id INT REFERENCES metadata.service(id),
    target_type TEXT NOT NULL,
    username TEXT,
    ip_address INET,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    CHECK (
        (target_type = 'host' AND service_id IS NULL)
        OR
        (target_type = 'service' AND service_id IS NOT NULL)
    )
);

CREATE INDEX idx_session_lookup
ON security.session (service_id, target_type, started_at DESC);

CREATE INDEX idx_session_ip
ON security.session (ip_address);


CREATE TABLE security.action (
    id BIGSERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES security.session(id),
    action_type TEXT,
    description TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
