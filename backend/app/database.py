import mysql.connector
from mysql.connector import pooling
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for Railway MySQL
db_config = {
    'host': os.getenv('MYSQLHOST'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'user': os.getenv('MYSQLUSER'),
    'password': os.getenv('MYSQLPASSWORD'),
    'database': os.getenv('MYSQLDATABASE'),
    'pool_name': 'mypool',
    'pool_size': int(os.getenv('DB_POOL_SIZE', 10)),
    'pool_reset_session': True,
    'autocommit': False,
    'use_pure': True,  # Better compatibility for Railway
    'connection_timeout': 30,  # Timeout for connections
}

# Global connection pool
connection_pool = None

def init_connection_pool():
    """Initialize the database connection pool"""
    global connection_pool
    try:
        # Validate required config values
        required_keys = ['host', 'user', 'password', 'database']
        for key in required_keys:
            if not db_config.get(key):
                raise ValueError(f"Missing required database config: {key}")
        
        connection_pool = pooling.MySQLConnectionPool(**db_config)
        logger.info(f"Database connection pool '{db_config['pool_name']}' initialized on {db_config['host']}:{db_config['port']}")
        
        # Test connection
        test_conn = connection_pool.get_connection()
        test_conn.ping(reconnect=True)
        test_conn.close()
        logger.info("Database connection test successful")
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        # Don't raise, let the app try to reconnect later
        connection_pool = None
        return False

def get_db_connection():
    """Get a connection from the pool with retry logic"""
    global connection_pool
    
    # Try to initialize if not already done
    if connection_pool is None:
        if not init_connection_pool():
            raise Exception("Database connection pool not initialized")
    
    # Try to get connection with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            connection = connection_pool.get_connection()
            # Verify connection is alive
            connection.ping(reconnect=True)
            return connection
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            # Reinitialize pool on failure
            connection_pool = None
            init_connection_pool()
    
    raise Exception("Failed to get database connection after retries")

def close_db_connections():
    """Close all database connections from the pool"""
    global connection_pool
    try:
        if connection_pool:
            # Close all connections in the pool
            if hasattr(connection_pool, '_cnx_queue'):
                closed_count = 0
                while not connection_pool._cnx_queue.empty():
                    try:
                        conn = connection_pool._cnx_queue.get_nowait()
                        if conn.is_connected():
                            conn.close()
                            closed_count += 1
                    except:
                        pass
                logger.info(f"Closed {closed_count} database connections")
            
            # Clear the pool reference
            connection_pool = None
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

def test_connection():
    """Test database connection"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        logger.info(f"Database connection test successful: {result}")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def init_database():
    """Initialize database tables with error handling"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                balance DECIMAL(10,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fcm_token VARCHAR(255) NULL,
                INDEX idx_username (username),
                INDEX idx_balance (balance)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Users table ready")
        
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
                FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (winner_id) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at),
                INDEX idx_creator (creator_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Games table ready")
        
        # Game participants
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                game_id INT NOT NULL,
                user_id INT NOT NULL,
                guessed_number INT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_participation (game_id, user_id),
                INDEX idx_game (game_id),
                INDEX idx_user (user_id),
                INDEX idx_guessed_number (guessed_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Game participants table ready")

        # Dans init_database(), ajoute :
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobile_money_withdrawals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                phone_number VARCHAR(20) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                transaction_id VARCHAR(100) UNIQUE,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user (user_id),
                INDEX idx_status (status),
                INDEX idx_transaction (transaction_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user (user_id),
                INDEX idx_type (type),
                INDEX idx_status (status),
                INDEX idx_created_at (created_at),
                UNIQUE KEY unique_reference (reference)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Transactions table ready")
        
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
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user (user_id),
                INDEX idx_status (status),
                INDEX idx_transaction (transaction_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Mobile money deposits table ready")
        
        # Create additional indexes for better performance
        try:
            cursor.execute("CREATE INDEX idx_games_status_created ON games(status, created_at)")
            logger.info("Created index idx_games_status_created")
        except Exception as e:
            logger.info(f"Index idx_games_status_created already exists or error: {e}")
        
        try:
            cursor.execute("CREATE INDEX idx_participants_game_user ON game_participants(game_id, user_id)")
            logger.info("Created index idx_participants_game_user")
        except Exception as e:
            logger.info(f"Index idx_participants_game_user already exists or error: {e}")
        
        # Seed initial data from SQL file
        sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'init_db.sql')
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            # Execute each non-empty, non-comment statement
            for statement in sql_content.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)
            logger.info("Database seed from init_db.sql completed")
        except FileNotFoundError:
            logger.warning(f"init_db.sql not found at {sql_file_path}, skipping seed")
        except Exception as e:
            logger.warning(f"Error executing init_db.sql: {e}")

        conn.commit()
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_user_balance(user_id: int):
    """Get user balance"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        return float(result['balance']) if result else 0.0
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def update_user_balance(user_id: int, amount: float, transaction_type: str, reference: str):
    """Update user balance and record transaction"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update balance
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, %s, %s, 'completed')
        """, (user_id, amount, transaction_type, reference))
        
        conn.commit()
        logger.info(f"Balance updated: User {user_id}, Amount ${amount}, Type {transaction_type}")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating user balance: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_game_participants(game_id: int):
    """Get all participants of a game"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT gp.user_id, gp.guessed_number, u.username, u.balance
            FROM game_participants gp
            JOIN users u ON gp.user_id = u.id
            WHERE gp.game_id = %s
        """, (game_id,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting game participants: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_game_by_id(game_id: int):
    """Get game details by ID"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*, u.username as creator_name
            FROM games g
            JOIN users u ON g.creator_id = u.id
            WHERE g.id = %s
        """, (game_id,))
        result = cursor.fetchone()
        if result:
            # Convert Decimal to float
            if 'bet_amount' in result and result['bet_amount']:
                result['bet_amount'] = float(result['bet_amount'])
            if 'total_pot' in result and result['total_pot']:
                result['total_pot'] = float(result['total_pot'])
        return result
    except Exception as e:
        logger.error(f"Error getting game by ID: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Initialize connection pool on module load
init_connection_pool()