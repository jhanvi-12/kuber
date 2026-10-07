-- App force-update version config
-- Run once on your MySQL DB. Does not alter existing tables.

CREATE TABLE IF NOT EXISTS app_version_config (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    app_type ENUM('customer', 'driver') NOT NULL,
    platform ENUM('android', 'ios') NOT NULL,
    min_supported_version VARCHAR(20) NOT NULL,
    latest_version VARCHAR(20) NOT NULL,
    force_update TINYINT(1) NOT NULL DEFAULT 0,
    message TEXT NULL,
    store_url VARCHAR(500) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NULL,
    deleted_at DATETIME NULL,
    UNIQUE KEY uq_app_version_config_app_type_platform (app_type, platform)
);

-- Seed defaults (safe to re-run with IGNORE)
INSERT IGNORE INTO app_version_config
    (app_type, platform, min_supported_version, latest_version, force_update, message, store_url, is_active, created_at)
VALUES
    ('customer', 'android', '1.0.0', '1.0.0', 0, 'Please update the app to continue.', NULL, 1, NOW()),
    ('customer', 'ios',     '1.0.0', '1.0.0', 0, 'Please update the app to continue.', NULL, 1, NOW()),
    ('driver',   'android', '1.0.0', '1.0.0', 0, 'Please update the app to continue.', NULL, 1, NOW()),
    ('driver',   'ios',     '1.0.0', '1.0.0', 0, 'Please update the app to continue.', NULL, 1, NOW());
