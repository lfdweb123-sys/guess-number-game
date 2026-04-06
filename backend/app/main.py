from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from fastapi import Request
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date
from decimal import Decimal
from .database import init_database, get_db_connection, close_db_connections
from .auth import verify_password, get_password_hash, create_access_token, decode_token
from .websocket_manager import manager
from .game_logic import determine_game_winner
from .schemas import *
import mysql.connector
import secrets
import httpx


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_for_json(obj):
    """Recursively convert non-serializable types in a dict/list."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(i) for i in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    init_database()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")
    close_db_connections()
    logger.info("Database connections closed")

app = FastAPI(
    title="Guess Number Game API",
    description="Multiplayer number guessing game backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Flutter web
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://guessnumbergame-6f0ff.web.app",
        "https://guessnumbergame-6f0ff.firebaseapp.com",
        "https://guess-number-game-production.up.railway.app",
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "Guess Number Game API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/api/register",
            "/api/login",
            "/api/games/create",
            "/api/games/join",
            "/api/games/available",
            "/ws/{game_id}/{token}"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# Authentication dependency
async def get_current_user(request: Request):
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        raise HTTPException(status_code=401, detail="Not authenticated - No Authorization header")
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Use 'Bearer <token>'")
    
    token = parts[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user.pop('password_hash', None)
        return user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/api/verify-token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid": True, 
        "user_id": current_user['id'], 
        "username": current_user['username'],
        "balance": current_user['balance']
    }

# DEPOSIT VIA FEEXPAY (webhook callback)
@app.post("/api/feexpay/webhook")
async def feexpay_webhook(request: Request):
    """Webhook called by FeexPay after payment confirmation"""
    try:
        data = await request.json()
        logger.info(f"FeexPay webhook received: {data}")
        
        transaction_id = data.get('transaction_id')
        amount = data.get('amount')
        user_id = data.get('user_id')
        status = data.get('status')
        
        if status == 'success' and user_id and amount:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if already processed
            cursor.execute("SELECT id FROM transactions WHERE reference = %s", (transaction_id,))
            if cursor.fetchone():
                return {"status": "already_processed"}
            
            # Credit user balance
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
            
            # Record transaction
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, reference, status)
                VALUES (%s, %s, 'deposit', %s, 'completed')
            """, (user_id, amount, transaction_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Deposit confirmed: User {user_id}, Amount {amount}")
            return {"status": "success"}
        
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=500, content={"status": "error"})

# Initiate FeexPay payment (frontend will call FeexPay SDK directly)
@app.post("/api/deposit/initiate")
async def initiate_deposit(deposit: MobileMoneyDeposit, current_user: dict = Depends(get_current_user)):
    """Create a pending deposit record before FeexPay payment"""
    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if deposit.amount < 1000:
        raise HTTPException(status_code=400, detail="Minimum deposit is 1000 XOF")
    
    transaction_id = f"DEP_{int(datetime.now().timestamp())}_{current_user['id']}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reference, status)
        VALUES (%s, %s, 'deposit_pending', %s, 'pending')
    """, (current_user['id'], deposit.amount, transaction_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "amount": deposit.amount,
        "user_id": current_user['id']
    }

# Withdrawal (keep for withdrawals)
@app.post("/api/withdraw")
async def withdraw(withdraw: MobileMoneyWithdraw, current_user: dict = Depends(get_current_user)):
    if withdraw.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if withdraw.amount < 1000:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is 1000 XOF")
    
    if float(current_user['balance']) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    transaction_id = f"WDR_{int(datetime.now().timestamp())}_{current_user['id']}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Deduct balance
    cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (withdraw.amount, current_user['id']))
    
    # Record transaction
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reference, status)
        VALUES (%s, %s, 'withdrawal', %s, 'completed')
    """, (current_user['id'], -withdraw.amount, transaction_id))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logger.info(f"Withdrawal: User {current_user['id']}, Amount {withdraw.amount}")
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "message": "Withdrawal processed successfully"
    }

# Transaction history
@app.get("/api/user/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM transactions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 50
    """, (current_user['id'],))
    
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {"transactions": transactions}

# User statistics
@app.get("/api/user/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_games,
            SUM(CASE WHEN winner_id = %s THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN winner_id = %s THEN amount ELSE 0 END) as total_won
        FROM game_participants gp
        JOIN games g ON gp.game_id = g.id
        WHERE gp.user_id = %s
    """, (current_user['id'], current_user['id'], current_user['id']))
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return stats

# Leaderboard
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            u.id,
            u.username,
            COUNT(CASE WHEN g.winner_id = u.id THEN 1 END) as wins,
            COALESCE(SUM(CASE WHEN g.winner_id = u.id THEN g.total_pot * 0.75 ELSE 0 END), 0) as total_won
        FROM users u
        LEFT JOIN games g ON g.winner_id = u.id
        WHERE u.id > 1
        GROUP BY u.id
        ORDER BY wins DESC
        LIMIT %s
    """, (limit,))
    
    leaderboard = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return leaderboard

# User endpoints
@app.post("/api/register")
async def register(user_data: UserCreate):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM users WHERE username = %s", (user_data.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        password_hash = get_password_hash(user_data.password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, balance) VALUES (%s, %s, 0)",
            (user_data.username, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        
        logger.info(f"New user registered: {user_data.username} (ID: {user_id})")
        
        return {"message": "User created successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/api/login")
async def login(user_data: UserLogin):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (user_data.username,))
        user = cursor.fetchone()
        
        if not user or not verify_password(user_data.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"user_id": user['id'], "username": user['username']})
        
        logger.info(f"User logged in: {user_data.username}")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user['id'],
            "username": user['username'],
            "balance": float(user['balance'])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/api/user/balance")
async def get_balance(current_user: dict = Depends(get_current_user)):
    return {"balance": float(current_user['balance'])}

# Game endpoints
@app.post("/api/games/create")
async def create_game(game_data: GameCreate, current_user: dict = Depends(get_current_user)):
    if game_data.bet_amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")
    
    if float(current_user['balance']) < game_data.bet_amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", 
                       (game_data.bet_amount, current_user['id']))
        
        cursor.execute("""
            INSERT INTO games (creator_id, bet_amount, total_pot, status)
            VALUES (%s, %s, %s, 'waiting')
        """, (current_user['id'], game_data.bet_amount, game_data.bet_amount))
        
        game_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
        """, (current_user['id'], game_data.bet_amount, f"game_{game_id}_bet"))
        
        conn.commit()
        
        logger.info(f"Game created: ID {game_id} by user {current_user['id']}")
        
        return {"game_id": game_id, "message": "Game created successfully"}
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Create game error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create game")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/api/games/join")
async def join_game(join_data: JoinGame, current_user: dict = Depends(get_current_user)):
    if join_data.guessed_number < 1 or join_data.guessed_number > 100:
        raise HTTPException(status_code=400, detail="Number must be between 1 and 100")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM games WHERE id = %s AND status = 'waiting' FOR UPDATE", 
                      (join_data.game_id,))
        game = cursor.fetchone()
        
        if not game:
            raise HTTPException(status_code=404, detail="Game not found or already started")
        
        if float(current_user['balance']) < float(game['bet_amount']):
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        cursor.execute("SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
                       (join_data.game_id, current_user['id']))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already joined this game")
        
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                       (float(game['bet_amount']), current_user['id']))
        
        cursor.execute("""
            INSERT INTO game_participants (game_id, user_id, guessed_number)
            VALUES (%s, %s, %s)
        """, (join_data.game_id, current_user['id'], join_data.guessed_number))
        
        cursor.execute("""
            UPDATE games SET total_pot = total_pot + %s WHERE id = %s
        """, (float(game['bet_amount']), join_data.game_id))
        
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
        """, (current_user['id'], float(game['bet_amount']), f"game_{join_data.game_id}_bet"))
        
        cursor.execute("SELECT COUNT(*) as count FROM game_participants WHERE game_id = %s", 
                      (join_data.game_id,))
        participant_count = cursor.fetchone()['count']
        
        conn.commit()
        
        logger.info(f"User {current_user['id']} joined game {join_data.game_id}")
        
        if participant_count >= 2:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("UPDATE games SET status = 'active' WHERE id = %s", 
                          (join_data.game_id,))
            conn.commit()
            
            asyncio.create_task(start_game_timer(join_data.game_id))
        
        return {"message": "Joined game successfully"}
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Join game error: {e}")
        raise HTTPException(status_code=500, detail="Failed to join game")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def start_game_timer(game_id: int):
    """30 second timer before game ends, broadcasts countdown"""
    try:
        for i in range(30, 0, -1):
            logger.info(f"Game {game_id} ends in {i} seconds...")
            await manager.broadcast_to_game(game_id, {
                'type': 'timer',
                'seconds': i
            })
            await asyncio.sleep(1)
        
        result = determine_game_winner(game_id)
        
        if result:
            winner_id = result['winner_id']
            winner_amount = result['winner_amount']
            winning_number = result['winning_number']
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id FROM game_participants WHERE game_id = %s
            """, (game_id,))
            participants = cursor.fetchall()
            cursor.close()
            conn.close()
            
            loser_ids = [p['user_id'] for p in participants if p['user_id'] != winner_id]
            
            logger.info(f"Game {game_id} finished. Winner: {winner_id}, Amount: {winner_amount}")
            
            await manager.broadcast_to_game(game_id, {
                'type': 'game_ended',
                'winning_number': winning_number,
                'winner_id': winner_id,
                'winner_amount': float(winner_amount),
                'loser_ids': loser_ids
            })
    except Exception as e:
        logger.error(f"Error in game timer for game {game_id}: {e}")

@app.get("/api/games/available")
async def get_available_games(current_user: dict = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT g.*, 
                   COUNT(gp.id) as participants_count,
                   COALESCE(u.username, 'Unknown') as creator_name
            FROM games g
            LEFT JOIN game_participants gp ON g.id = gp.game_id
            LEFT JOIN users u ON g.creator_id = u.id
            WHERE g.status = 'waiting'
            GROUP BY g.id
            ORDER BY g.created_at DESC
        """)
        
        games = cursor.fetchall()
        
        for game in games:
            if 'bet_amount' in game:
                game['bet_amount'] = float(game['bet_amount'])
            if 'total_pot' in game:
                game['total_pot'] = float(game['total_pot'])
        
        return games
    except Exception as e:
        logger.error(f"Get available games error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch games")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/api/games/{game_id}/details")
async def get_game_details(game_id: int):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT g.*, 
                   COUNT(gp.id) as participants_count,
                   GROUP_CONCAT(CONCAT(u.username, ':', gp.guessed_number)) as participants
            FROM games g
            LEFT JOIN game_participants gp ON g.id = gp.game_id
            LEFT JOIN users u ON gp.user_id = u.id
            WHERE g.id = %s
            GROUP BY g.id
        """, (game_id,))
        
        game = cursor.fetchone()
        
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        
        if 'bet_amount' in game and game['bet_amount']:
            game['bet_amount'] = float(game['bet_amount'])
        if 'total_pot' in game and game['total_pot']:
            game['total_pot'] = float(game['total_pot'])
        
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch game details")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# WebSocket endpoint
@app.websocket("/ws/{game_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str):
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        logger.info(f"WebSocket connected: User {user['id']} to game {game_id}")
        
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        return
    
    await manager.connect(game_id, websocket)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT g.*, 
                   COUNT(gp.id) as participants_count,
                   GROUP_CONCAT(DISTINCT u.username) as participants
            FROM games g
            LEFT JOIN game_participants gp ON g.id = gp.game_id
            LEFT JOIN users u ON gp.user_id = u.id
            WHERE g.id = %s
            GROUP BY g.id
        """, (game_id,))
        
        game_state = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if game_state:
            game_state = serialize_for_json(game_state)
        
        await websocket.send_json({
            'type': 'game_state',
            'data': game_state
        })
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_json({'type': 'heartbeat'})
            except WebSocketDisconnect:
                break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: Game {game_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(game_id, websocket)
