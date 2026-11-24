CREATE TABLE IF NOT EXISTS coverage_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hour_id INT NOT NULL,
    store_id INT NOT NULL,
    status ENUM('open','complete','waived') NOT NULL DEFAULT 'open',
    assigned_by INT NOT NULL,
    resolved_by INT NULL,
    waiver_reason VARCHAR(200) NULL,
    resolved_at TIMESTAMP NULL,
    UNIQUE (hour_id,store_id),
    INDEX (hour_id,status),
    CHECK ((status = 'open' AND resolved_by IS NULL AND resolved_at IS NULL) OR
           (status <> 'open' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)),
    CHECK ((status = 'waived' AND waiver_reason IS NOT NULL) OR
           (status <> 'waived' AND waiver_reason IS NULL)),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (assigned_by) REFERENCES users(id),
    FOREIGN KEY (resolved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS queue_lanes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    floor TINYINT NOT NULL CHECK (floor BETWEEN 1 AND 4),
    name VARCHAR(60) NOT NULL,
    capacity SMALLINT NOT NULL CHECK (capacity BETWEEN 1 AND 150),
    UNIQUE (floor,name)
);

CREATE TABLE IF NOT EXISTS lane_bookings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT NOT NULL,
    lane_id INT NOT NULL,
    slot_start DATETIME NOT NULL,
    seats SMALLINT NOT NULL CHECK (seats BETWEEN 1 AND 150),
    status ENUM('booked','in_use','released','cancelled') NOT NULL DEFAULT 'booked',
    blocking_task_id INT GENERATED ALWAYS AS (CASE WHEN status <> 'cancelled' THEN task_id ELSE NULL END) STORED UNIQUE,
    moved_count SMALLINT NULL,
    booked_by INT NOT NULL,
    guide_id INT NULL,
    INDEX (lane_id,slot_start,status),
    INDEX (task_id),
    CHECK (MINUTE(slot_start) IN (0,15,30,45) AND SECOND(slot_start) = 0),
    CHECK ((status IN ('in_use','released') AND moved_count IS NOT NULL AND moved_count BETWEEN 1 AND seats
            AND guide_id IS NOT NULL) OR (status IN ('booked','cancelled') AND moved_count IS NULL AND guide_id IS NULL)),
    FOREIGN KEY (task_id) REFERENCES dispatch_tasks(id),
    FOREIGN KEY (lane_id) REFERENCES queue_lanes(id),
    FOREIGN KEY (booked_by) REFERENCES users(id),
    FOREIGN KEY (guide_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS floor_handoffs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hour_id INT NOT NULL UNIQUE,
    report JSON NOT NULL,
    published_by INT NOT NULL,
    publish_note VARCHAR(200) NOT NULL,
    published_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_by INT NULL,
    receive_note VARCHAR(200) NULL,
    received_at TIMESTAMP NULL,
    CHECK ((received_by IS NULL AND receive_note IS NULL AND received_at IS NULL) OR
           (received_by IS NOT NULL AND receive_note IS NOT NULL AND received_at IS NOT NULL)),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (published_by) REFERENCES users(id),
    FOREIGN KEY (received_by) REFERENCES users(id)
);
