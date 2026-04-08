-- Créer un utilisateur admin (si pas déjà fait)
INSERT IGNORE INTO users (id, username, password_hash, balance) 
VALUES (1, 'admin', 'admin_hash', 0);

-- Add is_banned column to users table if it doesn't exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;

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

CREATE TABLE IF NOT EXISTS chat_messages (
 id INT AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 message TEXT NOT NULL,
 is_admin BOOLEAN DEFAULT FALSE,
 is_read BOOLEAN DEFAULT FALSE,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 INDEX idx_user_id (user_id),
 INDEX idx_created_at (created_at),
 INDEX idx_is_read (is_read)
);
