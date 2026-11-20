-- Review before applying. This migration is never run by app startup.
CREATE TABLE IF NOT EXISTS reading_revisions (
    reading_id INT NOT NULL PRIMARY KEY,
    version INT NOT NULL,
    CONSTRAINT fk_reading_revision_reading FOREIGN KEY (reading_id) REFERENCES utility_readings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
