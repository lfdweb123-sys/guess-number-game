import asyncio
import random
import logging
from datetime import datetime
from .database import get_db_connection
from .websocket_manager import manager

logger = logging.getLogger(__name__)

PLATFORM_USER_ID = 1
PLATFORM_USERNAME = "Joueur_Virtuel"

ADMIN_USER_ID = 2
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Guess123"

BOT_BET_AMOUNTS  = [500, 1000, 2000, 5000]
BOT_GAME_INTERVAL = 30


def ensure_platform_user():
    """Crée le compte plateforme s'il n'existe pas encore."""
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE id = %s", (PLATFORM_USER_ID,))
        if cursor.fetchone():
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
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


def ensure_admin_user():
    """Crée le compte admin s'il n'existe pas encore."""
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Vérifier si l'admin existe déjà
        cursor.execute("SELECT id FROM users WHERE username = %s", (ADMIN_USERNAME,))
        admin_exists = cursor.fetchone()

        if admin_exists:
            logger.info(f"Compte admin (username={ADMIN_USERNAME}) existe déjà.")
        else:
            from .auth import get_password_hash
            # Créer le compte admin
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, balance, is_banned)
                VALUES (%s, %s, %s, FALSE)
                """,
                (ADMIN_USERNAME, get_password_hash(ADMIN_PASSWORD), 0)
            )
            conn.commit()
            logger.info(f"✅ Compte admin créé - Username: {ADMIN_USERNAME}, Mot de passe: {ADMIN_PASSWORD}")

        # S'assurer que la colonne is_banned existe (au cas où)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'users' 
            AND column_name = 'is_banned'
        """)
        column_exists = cursor.fetchone()
        
        if column_exists and column_exists[0] == 0:
            cursor.execute("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE")
            conn.commit()
            logger.info("✅ Colonne is_banned ajoutée")

    except Exception as e:
        logger.error(f"Erreur ensure_admin_user: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


def create_bot_game(bet_amount: float) -> int | None:
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

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
        if conn: conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


def bot_join_game(game_id: int, bet_amount: float) -> bool:
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM games WHERE id = %s AND status = 'waiting' FOR UPDATE",
            (game_id,)
        )
        game = cursor.fetchone()
        if not game:
            return False

        cursor.execute(
            "SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
            (game_id, PLATFORM_USER_ID)
        )
        if cursor.fetchone():
            return False

        cursor.execute(
            "UPDATE users SET balance = balance - %s WHERE id = %s",
            (bet_amount, PLATFORM_USER_ID)
        )
        cursor.execute(
            """
            INSERT INTO game_participants (game_id, user_id, guessed_number)
            VALUES (%s, %s, %s)
            """,
            (game_id, PLATFORM_USER_ID, 0)
        )
        cursor.execute(
            "UPDATE games SET total_pot = total_pot + %s WHERE id = %s",
            (bet_amount, game_id)
        )
        cursor.execute(
            """
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
            """,
            (PLATFORM_USER_ID, bet_amount, f"bot_game_{game_id}_join")
        )
        cursor.execute(
            "UPDATE games SET status = 'active' WHERE id = %s",
            (game_id,)
        )

        conn.commit()
        logger.info(f"[BOT] Bot a rejoint la partie #{game_id}")
        return True

    except Exception as e:
        logger.error(f"[BOT] Erreur bot_join_game: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────────────────────
# Récupère les user_ids réels d'une partie (sans le bot)
# ─────────────────────────────────────────────────────────────
def _get_real_participants(game_id: int) -> list[int]:
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id FROM game_participants WHERE game_id = %s",
            (game_id,)
        )
        rows = cursor.fetchall()
        return [r['user_id'] for r in rows if r['user_id'] != PLATFORM_USER_ID]
    except Exception as e:
        logger.error(f"[BOT] Erreur _get_real_participants: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────────────────────
# Cycle complet d'une partie bot
# ─────────────────────────────────────────────────────────────
async def run_bot_game_cycle(game_id: int, bet_amount: float):
    from .game_logic import determine_game_winner_with_bot
    from .main import send_push_notification   # import local pour éviter les imports circulaires

    logger.info(f"[BOT] Cycle démarré pour partie #{game_id}")

    max_wait_seconds = 25
    check_interval   = 2
    waited           = 0

    while waited < max_wait_seconds:
        await asyncio.sleep(check_interval)
        waited += check_interval

        conn = cursor = None
        try:
            conn   = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT status FROM games WHERE id = %s", (game_id,))
            game_row = cursor.fetchone()

            if not game_row:
                logger.warning(f"[BOT] Partie #{game_id} introuvable")
                return

            if game_row['status'] == 'cancelled':
                logger.info(f"[BOT] Partie #{game_id} déjà annulée")
                return

            # ── Partie déjà active (joueur a rejoint via /api/games/join) ──
            if game_row['status'] == 'active':
                cursor.close(); conn.close()

                joined = bot_join_game(game_id, bet_amount)
                if joined:
                    real_players = _get_real_participants(game_id)

                    await manager.broadcast_to_game(game_id, {
                        'type': 'game_state_update',
                        'status': 'active',
                        'message': 'Un adversaire a rejoint ! La partie commence…'
                    })

                    # ── Push "game_started" à tous les vrais joueurs ──
                    for uid in real_players:
                        asyncio.create_task(send_push_notification(
                            user_id=uid,
                            title="🎮 La partie commence !",
                            body="Un adversaire a rejoint. Vous avez 30 secondes !",
                            data={'type': 'game_started', 'game_id': str(game_id)}
                        ))

                    for i in range(30, 0, -1):
                        await manager.broadcast_to_game(game_id, {'type': 'timer', 'seconds': i})
                        await asyncio.sleep(1)

                    result = determine_game_winner_with_bot(game_id)
                    if result:
                        await _notify_game_result(game_id, result)
                return

            # ── Vérifier si des joueurs ont rejoint ──
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM game_participants WHERE game_id = %s",
                (game_id,)
            )
            row = cursor.fetchone()
            participant_count = row['cnt'] if row else 0

            if participant_count > 0:
                cursor.close(); conn.close()

                joined = bot_join_game(game_id, bet_amount)
                if not joined:
                    logger.warning(f"[BOT] Impossible de rejoindre la partie #{game_id}")
                    return

                real_players = _get_real_participants(game_id)

                await manager.broadcast_to_game(game_id, {
                    'type': 'game_state_update',
                    'status': 'active',
                    'message': 'Un adversaire a rejoint ! La partie commence…'
                })

                # ── Push "game_started" à tous les vrais joueurs ──
                for uid in real_players:
                    asyncio.create_task(send_push_notification(
                        user_id=uid,
                        title="🎮 La partie commence !",
                        body="Un adversaire a rejoint. Vous avez 30 secondes !",
                        data={'type': 'game_started', 'game_id': str(game_id)}
                    ))

                for i in range(30, 0, -1):
                    await manager.broadcast_to_game(game_id, {'type': 'timer', 'seconds': i})
                    await asyncio.sleep(1)

                result = determine_game_winner_with_bot(game_id)
                if result:
                    await _notify_game_result(game_id, result)
                return

        except Exception as e:
            logger.error(f"[BOT] Erreur vérification partie #{game_id}: {e}")
        finally:
            if cursor: cursor.close()
            if conn:   conn.close()

    # Personne n'a rejoint après 25s → annulation
    logger.info(f"[BOT] Partie #{game_id} annulée (aucun joueur après {max_wait_seconds}s)")
    _cancel_bot_game(game_id, bet_amount)


def _cancel_bot_game(game_id: int, bet_amount: float):
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE games SET status = 'cancelled' WHERE id = %s", (game_id,))
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (bet_amount, PLATFORM_USER_ID)
        )
        conn.commit()
        logger.info(f"[BOT] Partie #{game_id} annulée, remboursement {bet_amount} XOF")
    except Exception as e:
        logger.error(f"[BOT] Erreur _cancel_bot_game: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────────────────────
# Notification de fin de partie + push Firebase
# ─────────────────────────────────────────────────────────────
async def _notify_game_result(game_id: int, result: dict):
    """
    Notifie chaque participant du résultat via :
    1. WebSocket (canal partie + canal personnel)
    2. Notification push Firebase (game_won / game_lost)
    """
    from .main import send_push_notification

    conn = cursor = None
    try:
        conn   = get_db_connection()
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
        if cursor: cursor.close()
        if conn:   conn.close()

    winner_id      = result['winner_id']
    winning_number = result['winning_number']
    winner_amount  = result['winner_amount']

    real_participants = [
        p for p in participants if p['user_id'] != PLATFORM_USER_ID
    ]

    # ── 1. Broadcast WebSocket général ───────────────────────
    await manager.broadcast_to_game(game_id, {
        'type':           'game_ended',
        'winning_number': winning_number,
        'winner_id':      winner_id,
        'winner_amount':  float(winner_amount),
        'loser_ids': [
            p['user_id'] for p in real_participants
            if p['user_id'] != winner_id
        ]
    })

    # ── 2. WebSocket personnel + Push Firebase par joueur ────
    for p in real_participants:
        uid        = p['user_id']
        is_winner  = (uid == winner_id)

        # WebSocket personnel (cross-screen)
        personal_msg = {
            'type':           'personal_notification',
            'game_id':        game_id,
            'is_winner':      is_winner,
            'winning_number': winning_number,
            'amount':         float(winner_amount) if is_winner else 0.0,
            'message': (
                f"🎉 Vous avez gagné {winner_amount:.0f} XOF !"
                if is_winner
                else f"😢 Perdu ! Le numéro gagnant était {winning_number}"
            )
        }
        await manager.send_to_user(uid, personal_msg)

        # Push Firebase
        if is_winner:
            asyncio.create_task(send_push_notification(
                user_id=uid,
                title="🏆 Tu as gagné !",
                body=f"Félicitations ! Tu remportes {float(winner_amount):,.0f} XOF. Numéro gagnant : {winning_number}.",
                data={
                    'type':    'game_won',
                    'game_id': str(game_id),
                    'amount':  str(winner_amount),
                }
            ))
        else:
            asyncio.create_task(send_push_notification(
                user_id=uid,
                title="😔 Partie perdue",
                body=f"Le numéro gagnant était {winning_number}. Bonne chance la prochaine fois !",
                data={
                    'type':    'game_lost',
                    'game_id': str(game_id),
                }
            ))

    logger.info(
        f"[BOT] Partie #{game_id} — gagnant: {winner_id}, "
        f"numéro: {winning_number}, gain: {winner_amount} XOF"
    )


# ─────────────────────────────────────────────────────────────
# Scheduler principal
# ─────────────────────────────────────────────────────────────
async def bot_scheduler():
    ensure_platform_user()
    ensure_admin_user()  # ✅ AJOUTÉ : Créer le compte admin automatiquement
    logger.info("[BOT] Scheduler démarré — parties automatiques toutes les 30s")

    while True:
        try:
            bet_amount = random.choice(BOT_BET_AMOUNTS)
            game_id    = create_bot_game(bet_amount)

            if game_id:
                asyncio.create_task(run_bot_game_cycle(game_id, bet_amount))

        except Exception as e:
            logger.error(f"[BOT] Erreur scheduler: {e}")

        await asyncio.sleep(BOT_GAME_INTERVAL)
