USE queue_ops;
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(40) NOT NULL UNIQUE,
    password_hash VARCHAR(150) NOT NULL,
    role ENUM('observer','operator','steward') NOT NULL
);
CREATE TABLE stores (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(16) NOT NULL UNIQUE,
    name VARCHAR(60) NOT NULL,
    floor TINYINT NOT NULL CHECK (floor BETWEEN 1 AND 4),
    x SMALLINT NOT NULL CHECK (x BETWEEN 0 AND 120),
    y SMALLINT NOT NULL CHECK (y BETWEEN 0 AND 64),
    staging_point VARCHAR(80) NOT NULL,
    UNIQUE (floor,x,y)
);
CREATE TABLE floor_hours (
    id INT PRIMARY KEY AUTO_INCREMENT,
    floor TINYINT NOT NULL CHECK (floor BETWEEN 1 AND 4),
    hour_start DATETIME NOT NULL,
    status ENUM('collecting','queued','ready','failed') NOT NULL DEFAULT 'collecting',
    generated_at TIMESTAMP NULL,
    UNIQUE (floor,hour_start),
    INDEX (status,id)
);
CREATE TABLE observations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hour_id INT NOT NULL,
    store_id INT NOT NULL,
    window_start DATETIME NOT NULL,
    queue_count SMALLINT NOT NULL CHECK (queue_count BETWEEN 0 AND 300),
    recorded_by INT NOT NULL,
    UNIQUE (store_id,window_start),
    INDEX (hour_id,store_id),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (recorded_by) REFERENCES users(id)
);
CREATE TABLE hotspots (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hour_id INT NOT NULL,
    zone_number SMALLINT NOT NULL,
    anchor_store_id INT NOT NULL,
    status ENUM('proposed','confirmed') NOT NULL DEFAULT 'proposed',
    confirmed_by INT NULL,
    UNIQUE (hour_id,zone_number),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (anchor_store_id) REFERENCES stores(id),
    FOREIGN KEY (confirmed_by) REFERENCES users(id)
);
CREATE TABLE analysis_points (
    hour_id INT NOT NULL,
    store_id INT NOT NULL,
    hotspot_id INT NULL,
    windows TINYINT NOT NULL,
    median_queue DECIMAL(5,1) NULL,
    kind ENUM('insufficient','below_threshold','noise','core','border') NOT NULL,
    PRIMARY KEY (hour_id,store_id),
    FOREIGN KEY (hour_id) REFERENCES floor_hours(id),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (hotspot_id) REFERENCES hotspots(id)
);
CREATE TABLE dispatch_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    hotspot_id INT NOT NULL UNIQUE,
    staging_point VARCHAR(80) NOT NULL,
    instruction VARCHAR(200) NOT NULL,
    status ENUM('assigned','active','closed') NOT NULL DEFAULT 'assigned',
    handled_by INT NULL,
    cleared_queue SMALLINT NULL,
    close_note VARCHAR(160) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (hotspot_id) REFERENCES hotspots(id),
    FOREIGN KEY (handled_by) REFERENCES users(id)
);
CREATE TABLE audit_events (
    id INT PRIMARY KEY AUTO_INCREMENT,
    actor_id INT NULL,
    action VARCHAR(40) NOT NULL,
    target VARCHAR(70) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES users(id)
);
