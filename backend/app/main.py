from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio
from .database import init_database, get_db_connection
from .auth import verify_password, get_password_hash, create_access_token, decode_token
from .websocket_manager import manager
from .game_logic import determine_game_winner
from .mobile_money import mm_api
from .schemas import *
import mysql.connector

app = FastAPI(title="Guess Number Game API")

# CORS for Flutter web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_database()

# Authentication dependency
async def get_current_user(token: str):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# User endpoints
@app.post("/api/register")
async def register(user_data: UserCreate):
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
    
    cursor.close()
    conn.close()
    
    return {"message": "User created successfully", "user_id": user_id}

@app.post("/api/login")
async def login(user_data: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE username = %s", (user_data.username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user or not verify_password(user_data.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"user_id": user['id'], "username": user['username']})
    return {"access_token": token, "token_type": "bearer", "user_id": user['id'], "balance": user['balance']}

@app.get("/api/user/balance")
async def get_balance(current_user: dict = Depends(get_current_user)):
    return {"balance": current_user['balance']}

# Game endpoints
@app.post("/api/games/create")
async def create_game(game_data: GameCreate, current_user: dict = Depends(get_current_user)):
    if game_data.bet_amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")
    
    if current_user['balance'] < game_data.bet_amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
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
    cursor.close()
    conn.close()
    
    return {"game_id": game_id, "message": "Game created successfully"}

@app.post("/api/games/join")
async def join_game(join_data: JoinGame, current_user: dict = Depends(get_current_user)):
    if join_data.guessed_number < 1 or join_data.guessed_number > 100:
        raise HTTPException(status_code=400, detail="Number must be between 1 and 100")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get game details
    cursor.execute("SELECT * FROM games WHERE id = %s AND status = 'waiting'", (join_data.game_id,))
    game = cursor.fetchone()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found or already started")
    
    if current_user['balance'] < game['bet_amount']:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Check if already joined
    cursor.execute("SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
                   (join_data.game_id, current_user['id']))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Already joined this game")
    
    # Deduct bet amount
    cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                   (game['bet_amount'], current_user['id']))
    
    # Add participant
    cursor.execute("""
        INSERT INTO game_participants (game_id, user_id, guessed_number)
        VALUES (%s, %s, %s)
    """, (join_data.game_id, current_user['id'], join_data.guessed_number))
    
    # Update game pot
    cursor.execute("""
        UPDATE games SET total_pot = total_pot + %s WHERE id = %s
    """, (game['bet_amount'], join_data.game_id))
    
    # Record transaction
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reference, status)
        VALUES (%s, %s, 'bet', %s, 'completed')
    """, (current_user['id'], game['bet_amount'], f"game_{join_data.game_id}_bet"))
    
    # Get participant count
    cursor.execute("SELECT COUNT(*) as count FROM game_participants WHERE game_id = %s", (join_data.game_id,))
    participant_count = cursor.fetchone()['count']
    
    conn.commit()
    
    # Start game if enough players (minimum 2)
    if participant_count >= 2:
        cursor.execute("UPDATE games SET status = 'active' WHERE id = %s", (join_data.game_id,))
        conn.commit()
        
        # Determine winner in background
        result = determine_game_winner(join_data.game_id)
        
        if result:
            # Broadcast result to all participants via WebSocket
            await manager.broadcast_to_game(join_data.game_id, {
                'type': 'game_ended',
                'winning_number': result['winning_number'],
                'winner_id': result['winner_id'],
                'winner_amount': result['winner_amount']
            })
    
    cursor.close()
    conn.close()
    
    return {"message": "Joined game successfully"}

@app.get("/api/games/available")
async def get_available_games(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT g.*, 
               COUNT(gp.id) as participants_count,
               u.username as creator_name
        FROM games g
        LEFT JOIN game_participants gp ON g.id = gp.game_id
        JOIN users u ON g.creator_id = u.id
        WHERE g.status = 'waiting'
        GROUP BY g.id
        ORDER BY g.created_at DESC
    """)
    
    games = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return games

@app.get("/api/games/{game_id}/details")
async def get_game_details(game_id: int):
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
    cursor.close()
    conn.close()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return game

# Mobile Money endpoints
@app.post("/api/mobile-money/deposit")
async def mobile_money_deposit(deposit: MobileMoneyDeposit, current_user: dict = Depends(get_current_user)):
    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    result = await mm_api.initiate_deposit(current_user['id'], deposit.phone_number, deposit.amount)
    
    if result['success']:
        return result
    else:
        raise HTTPException(status_code=400, detail=result['message'])

@app.get("/api/mobile-money/status/{transaction_id}")
async def check_deposit_status(transaction_id: str, current_user: dict = Depends(get_current_user)):
    status = await mm_api.check_deposit_status(transaction_id)
    if not status:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return status

# WebSocket endpoint
@app.websocket("/ws/{game_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str):
    user = await get_current_user(token)
    if not user:
        await websocket.close(code=1008)
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
        
        await websocket.send_json({
            'type': 'game_state',
            'data': game_state
        })
        
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            # Handle any client messages if needed
            
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)