-- One row per toll gate crossing; status follows the BR4 state machine
CREATE TABLE IF NOT EXISTS crossings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  vehicle_id VARCHAR(64) NOT NULL,
  gate_id VARCHAR(64) NOT NULL,
  wallet_id BIGINT NULL,
  amount BIGINT NOT NULL,
  status ENUM('PENDING','CHARGED','COMPLETED','FAILED') NOT NULL DEFAULT 'PENDING',
  failure_reason VARCHAR(64) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT chk_crossing_amount_positive CHECK (amount > 0)
) ENGINE=InnoDB;

-- Audit trail of every status a crossing has been through
CREATE TABLE IF NOT EXISTS crossing_status_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  crossing_id BIGINT NOT NULL,
  status ENUM('PENDING','CHARGED','COMPLETED','FAILED') NOT NULL,
  reason VARCHAR(64) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (crossing_id) REFERENCES crossings(id)
) ENGINE=InnoDB;

-- Challenge 2: one row per Idempotency-Key with a fingerprint of the request and the stored response
CREATE TABLE IF NOT EXISTS idempotency_keys (
  idem_key VARCHAR(128) PRIMARY KEY,
  request_hash CHAR(64) NOT NULL,
  status ENUM('IN_PROGRESS','DONE') NOT NULL DEFAULT 'IN_PROGRESS',
  response_code INT NULL,
  response_body JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
