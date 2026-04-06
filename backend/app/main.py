from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
import asyncio
import logging
from contextlib import asynccontextmanager
from .database import init_database, get_db_connection, close_db_connections
from .auth import verify_password, get_password_hash, create_access_token, decode_token
from .websocket_manager import manager
from .game_logic import determine_game_winner
from .mobile_money import mm_api
from .schemas import *
import mysql.connector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    allow_origins=["*"],  # Configure this properly in production
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
        # Test database connection
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

# Authentication dependency with better error handling
async def get_current_user(token: str = Depends(lambda: None)):
    if token is None:
        # Try to get from Authorization header (will be handled by middleware)
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Remove password hash from response
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

# Helper to get token from header (used in WebSocket)
async def get_token_from_header(authorization: str = None):
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token

# User endpoints
@app.post("/api/register")
async def register(user_data: UserCreate):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (user_data.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create user
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
        
        # Deduct bet amount
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", 
                       (game_data.bet_amount, current_user['id']))
        
        # Create game
        cursor.execute("""
            INSERT INTO games (creator_id, bet_amount, total_pot, status)
            VALUES (%s, %s, %s, 'waiting')
        """, (current_user['id'], game_data.bet_amount, game_data.bet_amount))
        
        game_id = cursor.lastrowid
        
        # Record transaction
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
        
        # Get game details with lock for race condition
        cursor.execute("SELECT * FROM games WHERE id = %s AND status = 'waiting' FOR UPDATE", 
                      (join_data.game_id,))
        game = cursor.fetchone()
        
        if not game:
            raise HTTPException(status_code=404, detail="Game not found or already started")
        
        if float(current_user['balance']) < float(game['bet_amount']):
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Check if already joined
        cursor.execute("SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
                       (join_data.game_id, current_user['id']))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already joined this game")
        
        # Deduct bet amount
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                       (float(game['bet_amount']), current_user['id']))
        
        # Add participant
        cursor.execute("""
            INSERT INTO game_participants (game_id, user_id, guessed_number)
            VALUES (%s, %s, %s)
        """, (join_data.game_id, current_user['id'], join_data.guessed_number))
        
        # Update game pot
        cursor.execute("""
            UPDATE games SET total_pot = total_pot + %s WHERE id = %s
        """, (float(game['bet_amount']), join_data.game_id))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
        """, (current_user['id'], float(game['bet_amount']), f"game_{join_data.game_id}_bet"))
        
        # Get participant count
        cursor.execute("SELECT COUNT(*) as count FROM game_participants WHERE game_id = %s", 
                      (join_data.game_id,))
        participant_count = cursor.fetchone()['count']
        
        conn.commit()
        
        logger.info(f"User {current_user['id']} joined game {join_data.game_id}")
        
        # Start game if enough players (minimum 2)
        if participant_count >= 2:
            cursor = conn.cursor(dictionary=True)  # New cursor for new query
            cursor.execute("UPDATE games SET status = 'active' WHERE id = %s", 
                          (join_data.game_id,))
            conn.commit()
            
            # Determine winner in background (don't await to avoid blocking)
            asyncio.create_task(process_game_winner(join_data.game_id))
        
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

async def process_game_winner(game_id: int):
    """Process game winner in background"""
    try:
        await asyncio.sleep(1)  # Small delay to ensure all data is committed
        result = determine_game_winner(game_id)
        
        if result:
            logger.info(f"Game {game_id} finished. Winner: {result['winner_id']}, Amount: {result['winner_amount']}")
            # Broadcast result to all participants via WebSocket
            await manager.broadcast_to_game(game_id, {
                'type': 'game_ended',
                'winning_number': result['winning_number'],
                'winner_id': result['winner_id'],
                'winner_amount': float(result['winner_amount'])
            })
    except Exception as e:
        logger.error(f"Error processing game winner for game {game_id}: {e}")

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
        
        # Convert Decimal to float for JSON serialization
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
        
        # Convert Decimal to float
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

# Mobile Money endpoints
@app.post("/api/mobile-money/deposit")
async def mobile_money_deposit(deposit: MobileMoneyDeposit, current_user: dict = Depends(get_current_user)):
    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if deposit.amount < 5:
        raise HTTPException(status_code=400, detail="Minimum deposit is $5")
    
    try:
        result = await mm_api.initiate_deposit(current_user['id'], deposit.phone_number, deposit.amount)
        
        if result['success']:
            logger.info(f"Deposit initiated: User {current_user['id']}, Amount ${deposit.amount}")
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
    except Exception as e:
        logger.error(f"Mobile money deposit error: {e}")
        raise HTTPException(status_code=500, detail="Deposit failed")

@app.get("/api/mobile-money/status/{transaction_id}")
async def check_deposit_status(transaction_id: str, current_user: dict = Depends(get_current_user)):
    try:
        status = await mm_api.check_deposit_status(transaction_id)
        if not status:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check deposit status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check status")

# WebSocket endpoint with improved error handling
@app.websocket("/ws/{game_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str):
    # Verify user
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
        # Send initial game state
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
            # Convert Decimal to float
            if 'bet_amount' in game_state and game_state['bet_amount']:
                game_state['bet_amount'] = float(game_state['bet_amount'])
            if 'total_pot' in game_state and game_state['total_pot']:
                game_state['total_pot'] = float(game_state['total_pot'])
        
        await websocket.send_json({
            'type': 'game_state',
            'data': game_state
        })
        
        # Keep connection alive
        while True:
            try:
                # Set timeout to detect disconnections
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping/pong if needed
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({'type': 'heartbeat'})
            except WebSocketDisconnect:
                break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: Game {game_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(game_id, websocket)