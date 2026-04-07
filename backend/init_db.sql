-- Créer un utilisateur admin (si pas déjà fait)
INSERT IGNORE INTO users (id, username, password_hash, balance) 
VALUES (1, 'admin', 'admin_hash', 0);

CREATE TABLE IF NOT EXISTS withdrawal_requests (
 id INT AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 phone_number VARCHAR(20) NOT NULL,
 amount DECIMAL(10,2) NOT NULL,
 provider VARCHAR(20) NOT NULL DEFAULT 'MTN',
 transaction_id VARCHAR(100) UNIQUE,
 status VARCHAR(20) NOT NULL DEFAULT 'pending',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 processed_at TIMESTAMP NULL,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 INDEX idx_user (user_id),
 INDEX idx_status (status),
 INDEX idx_transaction (transaction_id)
);
