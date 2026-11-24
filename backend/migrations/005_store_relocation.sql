CREATE TABLE IF NOT EXISTS store_relocations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    store_id INT NOT NULL,
    effective_hour DATETIME NOT NULL,
    floor TINYINT NOT NULL CHECK (floor BETWEEN 1 AND 4),
    x SMALLINT NOT NULL CHECK (x BETWEEN 0 AND 120),
    y SMALLINT NOT NULL CHECK (y BETWEEN 0 AND 64),
    staging_point VARCHAR(80) NOT NULL,
    registered_by INT NOT NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (store_id,effective_hour),
    CHECK (MINUTE(effective_hour) = 0 AND SECOND(effective_hour) = 0),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (registered_by) REFERENCES users(id)
);
