-- One row per registered vehicle; only IDs of other services' entities are stored (no cross-service FKs)
CREATE TABLE IF NOT EXISTS vehicles (
  vehicle_id VARCHAR(64) PRIMARY KEY,
  fleet_id VARCHAR(64) NOT NULL,
  wallet_id BIGINT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_fleet (fleet_id)
) ENGINE=InnoDB;
