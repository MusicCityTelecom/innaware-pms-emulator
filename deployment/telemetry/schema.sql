CREATE TABLE IF NOT EXISTS telemetry_installations (
    install_id CHAR(36) NOT NULL PRIMARY KEY,
    first_seen_at DATETIME(6) NOT NULL,
    last_seen_at DATETIME(6) NOT NULL,
    install_received TINYINT(1) NOT NULL DEFAULT 0,
    app_version VARCHAR(32) NOT NULL,
    platform VARCHAR(24) NOT NULL,
    architecture VARCHAR(24) NOT NULL,
    protocol_pack_version VARCHAR(64) NOT NULL,
    INDEX idx_installations_last_seen (last_seen_at),
    INDEX idx_installations_first_seen (first_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS telemetry_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    install_id CHAR(36) NOT NULL,
    event_type ENUM('install', 'run') NOT NULL,
    event_key CHAR(36) NULL,
    occurred_at DATETIME(6) NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    platform VARCHAR(24) NOT NULL,
    architecture VARCHAR(24) NOT NULL,
    protocol_pack_version VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_install_event (event_key),
    INDEX idx_events_occurred (occurred_at),
    INDEX idx_events_install_time (install_id, occurred_at),
    CONSTRAINT fk_events_installation
        FOREIGN KEY (install_id) REFERENCES telemetry_installations (install_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
