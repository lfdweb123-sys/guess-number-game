import mysql.connector
from mysql.connector import pooling
import os
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'host': os.getenv('MYSQLHOST'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'user': os.getenv('MYSQLUSER'),
    'password': os.getenv('MYSQLPASSWORD'),
    'database': os.getenv('MYSQLDATABASE'),
    'pool_name': 'mypool',
    'pool_size': 10
}

connection_pool = pooling.MySQLConnectionPool(**db_config)

def get_db_connection():
    return connection_pool.get_connection()

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            balance DECIMAL(10,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Games table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INT AUTO_INCREMENT PRIMARY KEY,
            creator_id INT NOT NULL,
            bet_amount DECIMAL(10,2) NOT NULL,
            total_pot DECIMAL(10,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'waiting',
            winning_number INT,
            winner_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP NULL,
            FOREIGN KEY (creator_id) REFERENCES users(id),
            FOREIGN KEY (winner_id) REFERENCES users(id)
        )
    """)
    
    # Game participants
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_participants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            game_id INT NOT NULL,
            user_id INT NOT NULL,
            guessed_number INT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE KEY unique_participation (game_id, user_id)
        )
    """)
    
    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            type VARCHAR(50) NOT NULL,
            reference VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Mobile money deposits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_money_deposits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            phone_number VARCHAR(20) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            transaction_id VARCHAR(100) UNIQUE,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()