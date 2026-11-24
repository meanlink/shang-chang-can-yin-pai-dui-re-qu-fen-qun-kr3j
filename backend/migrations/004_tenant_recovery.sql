CREATE TABLE IF NOT EXISTS tenant_recoveries (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hour_id INT NOT NULL,
    store_id INT NOT NULL,
    surge_id INT,
    issue_note VARCHAR(200) NOT NULL,
    source_queue DECIMAL(5,1) NOT NULL,
    action_note VARCHAR(200),
    action_slot DATETIME,
    close_note VARCHAR(200),
    status ENUM('open','monitoring','closed') NOT NULL DEFAULT 'open',
    opened_by INT NOT NULL,
    action_by INT,
    closed_by INT,
    opened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    UNIQUE KEY recovery_per_store_hour (hour_id,store_id),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (surge_id) REFERENCES surge_responses(id),
    FOREIGN KEY (opened_by) REFERENCES users(id),
    FOREIGN KEY (action_by) REFERENCES users(id),
    FOREIGN KEY (closed_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS recovery_checks (
    case_id INT NOT NULL,
    slot_start DATETIME NOT NULL,
    queue_count SMALLINT UNSIGNED NOT NULL CHECK (queue_count <= 300),
    note VARCHAR(200) NOT NULL,
    recorded_by INT NOT NULL,
    recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id,slot_start),
    FOREIGN KEY (case_id) REFERENCES tenant_recoveries(id),
    FOREIGN KEY (recorded_by) REFERENCES users(id)
) ENGINE=InnoDB;
