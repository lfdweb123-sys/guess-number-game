import random
from typing import List, Dict
from decimal import Decimal
from .database import get_db_connection

def calculate_winner(participants: List[Dict], winning_number: int):
    if not participants:
        return None
    
    closest = min(participants, key=lambda p: abs(int(p['guessed_number']) - winning_number))
    return closest['user_id']

def calculate_payout(total_pot):
    # Convertir Decimal en float si nécessaire
    if isinstance(total_pot, Decimal):
        total_pot = float(total_pot)
    
    winner_payout = total_pot * 0.75
    commission = total_pot * 0.25
    return winner_payout, commission

def determine_game_winner(game_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get game details
        cursor.execute("SELECT * FROM games WHERE id = %s", (game_id,))
        game = cursor.fetchone()
        
        if not game or game['status'] != 'active':
            return None
        
        # Get participants with their guesses
        cursor.execute("""
            SELECT gp.user_id, gp.guessed_number, u.balance
            FROM game_participants gp
            JOIN users u ON gp.user_id = u.id
            WHERE gp.game_id = %s
        """, (game_id,))
        participants = cursor.fetchall()
        
        if len(participants) < 2:
            return None
        
        # Generate random winning number
        winning_number = random.randint(1, 100)
        
        # Find winner
        winner_id = calculate_winner(participants, winning_number)
        
        # Convertir Decimal en float pour le calcul
        total_pot = float(game['total_pot']) if isinstance(game['total_pot'], Decimal) else game['total_pot']
        
        # Calculate payouts
        winner_amount, commission = calculate_payout(total_pot)
        
        # Update game
        cursor.execute("""
            UPDATE games 
            SET status = 'ended', winning_number = %s, winner_id = %s, ended_at = NOW()
            WHERE id = %s
        """, (winning_number, winner_id, game_id))
        
        # Credit winner
        cursor.execute("""
            UPDATE users SET balance = balance + %s WHERE id = %s
        """, (winner_amount, winner_id))
        
        # Record winner transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'win', %s, 'completed')
        """, (winner_id, winner_amount, f"game_{game_id}_win"))
        
        # Record commission transaction (site revenue)
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'commission', %s, 'completed')
        """, (0, commission, f"game_{game_id}_commission"))
        
        conn.commit()
        
        return {
            'winning_number': winning_number,
            'winner_id': winner_id,
            'winner_amount': winner_amount,
            'commission': commission
        }
    except Exception as e:
        print(f"Error in determine_game_winner: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()