-- Créer un utilisateur admin (si pas déjà fait)
INSERT IGNORE INTO users (id, username, password_hash, balance) 
VALUES (1, 'admin', 'admin_hash', 0);
