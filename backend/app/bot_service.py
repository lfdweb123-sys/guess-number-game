import asyncio
import random
import logging
from datetime import datetime
from .database import get_db_connection
from .websocket_manager import manager

logger = logging.getLogger(__name__)

# ID du compte plateforme (user_id = 1, créé au démarrage si absent)
PLATFORM_USER_ID = 1
PLATFORM_USERNAME = "Joueur_Virtuel"

# Mises disponibles pour les parties automatiques (en XOF)
BOT_BET_AMOUNTS = [500, 1000, 2000, 5000]

# Intervalle entre chaque partie bot (secondes)
BOT_GAME_INTERVAL = 30


def ensure_platform_user():
    """Crée le compte plateforme s'il n'existe pas encore."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE id = %s", (PLATFORM_USER_ID,))
        if cursor.fetchone():
            # Met à jour le solde si nécessaire pour qu'il puisse toujours miser
            cursor.execute(
                "UPDATE users SET balance = 9999999 WHERE id = %s",
                (PLATFORM_USER_ID,)
            )
        else:
            from .auth import get_password_hash
            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, balance)
                VALUES (%s, %s, %s, 9999999)
                ON DUPLICATE KEY UPDATE balance = 9999999
                """,
                (PLATFORM_USER_ID, PLATFORM_USERNAME, get_password_hash("platform_secret_x9z"))
            )

        conn.commit()
        logger.info(f"Compte plateforme (id={PLATFORM_USER_ID}) prêt.")
    except Exception as e:
        logger.error(f"Erreur ensure_platform_user: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_bot_game(bet_amount: float) -> int | None:
    """
    Crée une partie en attente dont le créateur est la plateforme.
    Retourne le game_id ou None en cas d'erreur.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Débiter la mise du compte plateforme
        cursor.execute(
            "UPDATE users SET balance = balance - %s WHERE id = %s",
            (bet_amount, PLATFORM_USER_ID)
        )

        cursor.execute(
            """
            INSERT INTO games (creator_id, bet_amount, total_pot, status)
            VALUES (%s, %s, %s, 'waiting')
            """,
            (PLATFORM_USER_ID, bet_amount, bet_amount)
        )
        game_id = cursor.lastrowid

        # Enregistrer la transaction
        cursor.execute(
            """
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
            """,
            (PLATFORM_USER_ID, bet_amount, f"bot_game_{game_id}_create")
        )

        conn.commit()
        logger.info(f"[BOT] Partie #{game_id} créée — mise {bet_amount} XOF")
        return game_id

    except Exception as e:
        logger.error(f"[BOT] Erreur create_bot_game: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def bot_join_game(game_id: int, bet_amount: float) -> bool:
    """
    Fait rejoindre le bot à une partie existante avec un numéro
    volontairement mauvais (sera ajusté dans determine_game_winner).
    Le numéro réel est choisi APRÈS les vrais joueurs dans game_logic.
    Ici on stocke 0 comme placeholder.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Vérifier que la partie est en attente
        cursor.execute(
            "SELECT * FROM games WHERE id = %s AND status = 'waiting' FOR UPDATE",
            (game_id,)
        )
        game = cursor.fetchone()
        if not game:
            return False

        # Vérifier que le bot n'a pas déjà rejoint
        cursor.execute(
            "SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
            (game_id, PLATFORM_USER_ID)
        )
        if cursor.fetchone():
            return False

        # Débiter la mise
        cursor.execute(
            "UPDATE users SET balance = balance - %s WHERE id = %s",
            (bet_amount, PLATFORM_USER_ID)
        )

        # Rejoindre avec numéro placeholder 0 (sera ignoré dans la logique)
        cursor.execute(
            """
            INSERT INTO game_participants (game_id, user_id, guessed_number)
            VALUES (%s, %s, %s)
            """,
            (game_id, PLATFORM_USER_ID, 0)
        )

        # Mettre à jour la cagnotte
        cursor.execute(
            "UPDATE games SET total_pot = total_pot + %s WHERE id = %s",
            (bet_amount, game_id)
        )

        # Transaction
        cursor.execute(
            """
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
            """,
            (PLATFORM_USER_ID, bet_amount, f"bot_game_{game_id}_join")
        )

        # Passer la partie en 'active'
        cursor.execute(
            "UPDATE games SET status = 'active' WHERE id = %s",
            (game_id,)
        )

        conn.commit()
        logger.info(f"[BOT] Bot a rejoint la partie #{game_id}")
        return True

    except Exception as e:
        logger.error(f"[BOT] Erreur bot_join_game: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


async def run_bot_game_cycle(game_id: int, bet_amount: float):
    """
    Cycle complet d'une partie bot :
    - Attend que des joueurs rejoignent (max 25s)
    - Si personne n'a rejoint → annule et rembourse
    - Si un joueur a rejoint → bot rejoint, timer, résolution
    """
    from .game_logic import determine_game_winner_with_bot

    logger.info(f"[BOT] Cycle démarré pour partie #{game_id}")

    # ✅ Vérification périodique au lieu d'un seul sleep de 25s
    max_wait_seconds = 25
    check_interval = 2  # Vérifier toutes les 2 secondes
    waited = 0

    while waited < max_wait_seconds:
        await asyncio.sleep(check_interval)
        waited += check_interval

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Vérifier si la partie existe encore et son statut
            cursor.execute(
                "SELECT status FROM games WHERE id = %s",
                (game_id,)
            )
            game_row = cursor.fetchone()
            
            if not game_row:
                logger.warning(f"[BOT] Partie #{game_id} n'existe plus")
                return
            
            if game_row['status'] == 'cancelled':
                logger.info(f"[BOT] Partie #{game_id} déjà annulée")
                return
            
            if game_row['status'] == 'active':
                # Quelqu'un a rejoint et a démarré la partie
                logger.info(f"[BOT] Partie #{game_id} déjà active, bot va rejoindre")
                cursor.close()
                conn.close()
                
                joined = bot_join_game(game_id, bet_amount)
                if joined:
                    await manager.broadcast_to_game(game_id, {
                        'type': 'game_state_update',
                        'status': 'active',
                        'message': 'Un adversaire a rejoint ! La partie commence…'
                    })
                    # Timer de 30 secondes
                    for i in range(30, 0, -1):
                        await manager.broadcast_to_game(game_id, {
                            'type': 'timer',
                            'seconds': i
                        })
                        await asyncio.sleep(1)
                    
                    result = determine_game_winner_with_bot(game_id)
                    if result:
                        await _notify_game_result(game_id, result)
                        logger.info(
                            f"[BOT] Partie #{game_id} terminée — "
                            f"gagnant: {result['winner_id']}, numéro: {result['winning_number']}"
                        )
                return

            # Vérifier combien de participants
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM game_participants WHERE game_id = %s",
                (game_id,)
            )
            row = cursor.fetchone()
            participant_count = row['cnt'] if row else 0

            if participant_count > 0:
                # ✅ Des joueurs ont rejoint ! Le bot rejoint maintenant
                logger.info(f"[BOT] {participant_count} joueur(s) ont rejoint la partie #{game_id}")
                cursor.close()
                conn.close()
                
                joined = bot_join_game(game_id, bet_amount)
                if not joined:
                    logger.warning(f"[BOT] Impossible de rejoindre la partie #{game_id}")
                    return

                await manager.broadcast_to_game(game_id, {
                    'type': 'game_state_update',
                    'status': 'active',
                    'message': 'Un adversaire a rejoint ! La partie commence…'
                })

                # Timer de 30 secondes avec countdown
                for i in range(30, 0, -1):
                    await manager.broadcast_to_game(game_id, {
                        'type': 'timer',
                        'seconds': i
                    })
                    await asyncio.sleep(1)

                # Résolution avec logique bot
                result = determine_game_winner_with_bot(game_id)

                if result:
                    await _notify_game_result(game_id, result)
                    logger.info(
                        f"[BOT] Partie #{game_id} terminée — "
                        f"gagnant: {result['winner_id']}, numéro: {result['winning_number']}"
                    )
                return

        except Exception as e:
            logger.error(f"[BOT] Erreur vérification partie #{game_id}: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ✅ Si on arrive ici, personne n'a rejoint après 25s → annuler
    logger.info(f"[BOT] Partie #{game_id} annulée (aucun joueur après {max_wait_seconds}s)")
    _cancel_bot_game(game_id, bet_amount)


def _cancel_bot_game(game_id: int, bet_amount: float):
    """Annule une partie bot sans joueurs et rembourse le bot."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE games SET status = 'cancelled' WHERE id = %s",
            (game_id,)
        )
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (bet_amount, PLATFORM_USER_ID)
        )
        conn.commit()
        logger.info(f"[BOT] Partie #{game_id} annulée, remboursement de {bet_amount} XOF")
    except Exception as e:
        logger.error(f"[BOT] Erreur _cancel_bot_game: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


async def _notify_game_result(game_id: int, result: dict):
    """
    Notifie chaque participant du résultat via :
    1. Le canal de la partie (game_{id})
    2. Le canal personnel du joueur (user_{id}) pour les notifications cross-screen
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_id FROM game_participants WHERE game_id = %s",
            (game_id,)
        )
        participants = cursor.fetchall()

    except Exception as e:
        logger.error(f"[BOT] Erreur récupération participants: {e}")
        participants = []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    winner_id = result['winner_id']
    winning_number = result['winning_number']
    winner_amount = result['winner_amount']

    # Broadcast général sur le canal de la partie
    await manager.broadcast_to_game(game_id, {
        'type': 'game_ended',
        'winning_number': winning_number,
        'winner_id': winner_id,
        'winner_amount': float(winner_amount),
        'loser_ids': [
            p['user_id'] for p in participants
            if p['user_id'] != winner_id and p['user_id'] != PLATFORM_USER_ID
        ]
    })

    # Notification personnelle pour chaque vrai joueur (cross-screen)
    for p in participants:
        uid = p['user_id']
        if uid == PLATFORM_USER_ID:
            continue

        is_winner = (uid == winner_id)
        personal_msg = {
            'type': 'personal_notification',
            'game_id': game_id,
            'is_winner': is_winner,
            'winning_number': winning_number,
            'amount': float(winner_amount) if is_winner else 0.0,
            'message': (
                f"🎉 Vous avez gagné {winner_amount:.0f} XOF !"
                if is_winner
                else f"😢 Perdu ! Le numéro gagnant était {winning_number}"
            )
        }
        await manager.send_to_user(uid, personal_msg)


async def bot_scheduler():
    """
    Boucle principale : toutes les 30 secondes, crée une partie bot
    avec une mise aléatoire.
    """
    ensure_platform_user()
    logger.info("[BOT] Scheduler démarré — parties automatiques toutes les 30s")

    while True:
        try:
            bet_amount = random.choice(BOT_BET_AMOUNTS)
            game_id = create_bot_game(bet_amount)

            if game_id:
                # Lancer le cycle sans bloquer le scheduler
                asyncio.create_task(run_bot_game_cycle(game_id, bet_amount))

        except Exception as e:
            logger.error(f"[BOT] Erreur scheduler: {e}")

        await asyncio.sleep(BOT_GAME_INTERVAL)
