from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from fastapi import Request
import asyncio
import logging
import os
import json
import secrets
import httpx
import mysql.connector
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from decimal import Decimal
from .database import init_database, get_db_connection, close_db_connections
from .database import create_reset_token, validate_reset_token, mark_token_as_used, cleanup_expired_tokens
from .auth import verify_password, get_password_hash, create_access_token, decode_token
from .websocket_manager import manager
from .game_logic import determine_game_winner
from .schemas import *
from .bot_service import bot_scheduler, ensure_platform_user
import firebase_admin
from firebase_admin import credentials, messaging as fcm_messaging


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Configuration Brevo
# ─────────────────────────────────────────────
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_EMAIL   = os.getenv("BREVO_EMAIL", "lfdweb123@gmail.com")

if not BREVO_API_KEY:
    logger.warning("⚠️ BREVO_API_KEY non configurée")

configuration = None
if BREVO_API_KEY:
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY


# ─────────────────────────────────────────────
# Firebase Admin Init
# ─────────────────────────────────────────────
_firebase_app = None

def init_firebase_admin():
    global _firebase_app
    if _firebase_app is None:
        try:
            private_key = os.getenv("FIREBASE_PRIVATE_KEY")
            if private_key:
                private_key = private_key.replace('\\n', '\n')
                creds_dict = {
                    "type":                        os.getenv("FIREBASE_TYPE", "service_account"),
                    "project_id":                  os.getenv("FIREBASE_PROJECT_ID"),
                    "private_key_id":              os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key":                 private_key,
                    "client_email":                os.getenv("FIREBASE_CLIENT_EMAIL"),
                    "client_id":                   os.getenv("FIREBASE_CLIENT_ID"),
                    "auth_uri":                    os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri":                   os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
                    "client_x509_cert_url":        os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
                    "universe_domain":             os.getenv("FIREBASE_UNIVERSE_DOMAIN", "googleapis.com"),
                }
                cred = credentials.Certificate(creds_dict)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (variables env)")
                return

            firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
            if firebase_creds_json:
                creds_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(creds_dict)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (JSON env)")
                return

            cred_path = os.path.join(os.path.dirname(__file__), "..", "firebase_credentials.json")
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (fichier local)")
                return

            logger.warning("⚠️ Aucune configuration Firebase trouvée")
        except Exception as e:
            logger.warning(f"⚠️ Firebase init failed: {e}")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def serialize_for_json(obj):
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(i) for i in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


# ─────────────────────────────────────────────
# Géolocalisation IP
# ─────────────────────────────────────────────
async def get_ip_info(ip: str) -> dict:
    """Géolocalise une IP via ip-api.com (gratuit, 45 req/min)."""
    try:
        if ip in ("127.0.0.1", "::1", "testclient", ""):
            return {"city": "Local", "country": "Dev", "regionName": ""}
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"http://ip-api.com/json/{ip}?fields=status,city,country,regionName"
            )
            data = r.json()
            if data.get("status") == "success":
                return data
    except Exception as e:
        logger.warning(f"ip-api error: {e}")
    return {"city": "Inconnue", "country": "", "regionName": ""}


# ─────────────────────────────────────────────
# Notification Push Firebase
# ─────────────────────────────────────────────
async def send_push_notification(user_id: int, title: str, body: str, data: dict = None):
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT fcm_token FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not user.get('fcm_token'):
            logger.warning(f"Pas de FCM token pour user {user_id}")
            return False

        message = fcm_messaging.Message(
            notification=fcm_messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=user['fcm_token'],
            android=fcm_messaging.AndroidConfig(
                priority='high',
                notification=fcm_messaging.AndroidNotification(
                    sound='default',
                    channel_id='guess_number_channel',
                ),
            ),
            apns=fcm_messaging.APNSConfig(
                payload=fcm_messaging.APNSPayload(
                    aps=fcm_messaging.Aps(sound='default', badge=1),
                ),
            ),
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: fcm_messaging.send(message)
        )
        logger.info(f"✅ Push envoyé à user {user_id}: {response}")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur push user {user_id}: {e}")
        return False


# ─────────────────────────────────────────────
# Notifications Login / Register
# ─────────────────────────────────────────────
async def _notify_login(
    user_id: int,
    username: str,
    ip: str,
    device_os: str,
    device_model: str,
    device_brand: str,
):
    """Push de sécurité envoyée à l'utilisateur après connexion."""
    geo      = await get_ip_info(ip)
    now      = datetime.now().strftime("%d/%m/%Y %H:%M")
    city     = geo.get("city", "?")
    country  = geo.get("country", "")
    location = f"{city}, {country}".strip(", ")

    await send_push_notification(
        user_id=user_id,
        title="🔐 Nouvelle connexion",
        body=f"{device_brand} {device_model} · {device_os}\n{now} · {location} · {ip}",
        data={
            "type":         "security_login",
            "ip":           ip,
            "city":         city,
            "country":      country,
            "time":         now,
            "device_os":    device_os,
            "device_model": device_model,
            "device_brand": device_brand,
        }
    )
    logger.info(f"🔐 Login notif → {username} | {ip} | {location} | {device_brand} {device_model} {device_os}")


async def _notify_register(
    user_id: int,
    username: str,
    ip: str,
    device_os: str,
    device_model: str,
    device_brand: str,
):
    """Push de bienvenue envoyée à l'utilisateur après inscription."""
    geo      = await get_ip_info(ip)
    now      = datetime.now().strftime("%d/%m/%Y %H:%M")
    city     = geo.get("city", "?")
    country  = geo.get("country", "")
    location = f"{city}, {country}".strip(", ")

    await send_push_notification(
        user_id=user_id,
        title="🎉 Compte créé avec succès",
        body=f"Bienvenue {username} !\n{device_brand} {device_model} · {device_os}\n{now} · {location}",
        data={
            "type":         "security_register",
            "ip":           ip,
            "city":         city,
            "country":      country,
            "time":         now,
            "device_os":    device_os,
            "device_model": device_model,
            "device_brand": device_brand,
        }
    )
    logger.info(f"🎉 Register notif → {username} | {ip} | {location} | {device_brand} {device_model} {device_os}")


# ─────────────────────────────────────────────
# Notification Email Admin (Brevo)
# ─────────────────────────────────────────────
async def send_withdrawal_notification(user_info: dict):
    if not BREVO_API_KEY or not configuration:
        logger.error("❌ BREVO_API_KEY non configurée")
        return False

    try:
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
            <div style="background-color: #1a1a2e; padding: 20px; border-radius: 10px 10px 0 0;">
                <h2 style="color: #FFD700; margin: 0;">🎮 Guess Number Game</h2>
                <p style="color: #aaa; margin: 5px 0 0;">Nouvelle demande de retrait</p>
            </div>
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; border: 1px solid #ddd;">
                <h3 style="color: #333; border-bottom: 2px solid #FFD700; padding-bottom: 5px;">
                    👤 Informations utilisateur
                </h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; color: #555; width: 40%;"><strong>Nom :</strong></td>
                        <td style="padding: 8px; color: #222;">{user_info['username']}</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td style="padding: 8px; color: #555;"><strong>ID :</strong></td>
                        <td style="padding: 8px; color: #222;">{user_info['user_id']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #555;"><strong>Solde après :</strong></td>
                        <td style="padding: 8px; color: #c0392b;"><strong>{user_info['current_balance']:,.0f} XOF</strong></td>
                    </tr>
                </table>
                <h3 style="color: #333; border-bottom: 2px solid #FFD700; padding-bottom: 5px; margin-top: 20px;">
                    💰 Détails du retrait
                </h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; color: #555; width: 40%;"><strong>Montant :</strong></td>
                        <td style="padding: 8px; color: #27ae60;"><strong>{user_info['amount']:,.0f} XOF</strong></td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td style="padding: 8px; color: #555;"><strong>Téléphone :</strong></td>
                        <td style="padding: 8px; color: #222;">{user_info['phone']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #555;"><strong>Opérateur :</strong></td>
                        <td style="padding: 8px; color: #222;">{user_info['provider']}</td>
                    </tr>
                    <tr style="background-color: #f0f0f0;">
                        <td style="padding: 8px; color: #555;"><strong>Date :</strong></td>
                        <td style="padding: 8px; color: #222;">{user_info['date']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #555;"><strong>Transaction ID :</strong></td>
                        <td style="padding: 8px; color: #2980b9; font-family: monospace;">{user_info['transaction_id']}</td>
                    </tr>
                </table>
                <div style="margin-top: 20px; background-color: #fff3cd; border: 1px solid #ffc107;
                            border-radius: 8px; padding: 15px;">
                    <p style="margin: 0; color: #856404;">
                        📱 <strong>Action requise :</strong> Veuillez traiter ce retrait manuellement
                        via votre interface Mobile Money et confirmer dans le tableau de bord admin.
                    </p>
                </div>
                <hr style="margin-top: 30px;">
                <p style="color: #999; font-size: 11px; text-align: center;">
                    Message automatique envoyé depuis Guess Number Game
                </p>
            </div>
        </body>
        </html>
        """

        api_instance    = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": BREVO_EMAIL, "name": "Admin Guess Game"}],
            sender={"email": BREVO_EMAIL, "name": "Guess Number Game"},
            subject=f"🔄 Demande de retrait - {user_info['username']}",
            html_content=html_content,
            reply_to={"email": BREVO_EMAIL, "name": "Support Guess Game"}
        )

        loop     = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: api_instance.send_transac_email(send_smtp_email)
        )
        logger.info(f"✅ Email envoyé via Brevo! ID: {response.message_id}")
        return True
    except ApiException as e:
        logger.error(f"❌ Brevo API Exception: {e.status} - {e.body}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur envoi email: {e}")
        return False


# ─────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    init_database()
    logger.info("Database initialized")
    init_firebase_admin()
    ensure_platform_user()
    bot_task = asyncio.create_task(bot_scheduler())
    logger.info("Bot scheduler démarré")
    yield
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down...")
    close_db_connections()
    logger.info("Database connections closed")


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="Guess Number Game API",
    description="Multiplayer number guessing game backend",
    version="1.0.0",
    lifespan=lifespan
)

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


# ─────────────────────────────────────────────
# Auth dependency
# ─────────────────────────────────────────────
async def get_current_user(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token   = parts[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop('password_hash', None)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────
# Endpoints de base
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "Guess Number Game API",
        "status":  "running",
        "version": "1.0.0",
    }

@app.get("/health")
async def health_check():
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={
            "status": "unhealthy", "database": "disconnected",
            "error": str(e), "timestamp": datetime.now().isoformat()
        })


# ─────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────
@app.post("/api/register")
async def register(user_data: UserCreate, request: Request):
    conn = cursor = None
    try:
        conn   = get_db_connection()
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

        # ── Récupérer IP et infos appareil ──
        ip           = request.headers.get("X-Forwarded-For", request.client.host or "")
        ip           = ip.split(",")[0].strip()
        device_os    = request.headers.get("X-Device-OS", "Unknown")
        device_model = request.headers.get("X-Device-Model", "Unknown")
        device_brand = request.headers.get("X-Device-Brand", "Unknown")

        # Push en différé (le token FCM sera envoyé après par Flutter)
        asyncio.create_task(_notify_register(
            user_id, user_data.username, ip,
            device_os, device_model, device_brand
        ))

        return {"message": "User created successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────
@app.post("/api/login")
async def login(user_data: UserLogin, request: Request):
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (user_data.username,))
        user = cursor.fetchone()

        if not user or not verify_password(user_data.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if user.get('is_banned'):
            raise HTTPException(status_code=403, detail="Account banned")

        token = create_access_token({"user_id": user['id'], "username": user['username']})
        logger.info(f"User logged in: {user_data.username}")

        # ── Récupérer IP et infos appareil ──
        ip           = request.headers.get("X-Forwarded-For", request.client.host or "")
        ip           = ip.split(",")[0].strip()
        device_os    = request.headers.get("X-Device-OS", "Unknown")
        device_model = request.headers.get("X-Device-Model", "Unknown")
        device_brand = request.headers.get("X-Device-Brand", "Unknown")

        asyncio.create_task(_notify_login(
            user['id'], user['username'], ip,
            device_os, device_model, device_brand
        ))

        return {
            "access_token": token,
            "token_type":   "bearer",
            "user_id":      user['id'],
            "username":     user['username'],
            "balance":      float(user['balance'])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.get("/api/verify-token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid":    True,
        "user_id":  current_user['id'],
        "username": current_user['username'],
        "balance":  current_user['balance']
    }


# ─────────────────────────────────────────────
# FCM Token
# ─────────────────────────────────────────────
@app.post("/api/user/fcm-token")
async def save_fcm_token(request: Request, current_user: dict = Depends(get_current_user)):
    data      = await request.json()
    fcm_token = data.get('fcm_token')
    if not fcm_token:
        raise HTTPException(status_code=400, detail="fcm_token manquant")

    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET fcm_token = %s WHERE id = %s", (fcm_token, current_user['id']))
    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"FCM token sauvegardé pour user {current_user['id']}")
    return {"success": True}


# ─────────────────────────────────────────────
# Dépôt (FeexPay webhook)
# ─────────────────────────────────────────────
@app.post("/api/feexpay/webhook")
async def feexpay_webhook(request: Request):
    try:
        data           = await request.json()
        transaction_id = data.get('transaction_id')
        amount         = data.get('amount')
        user_id        = data.get('user_id')
        status         = data.get('status')

        if status == 'success' and user_id and amount:
            conn   = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM transactions WHERE reference = %s", (transaction_id,))
            if cursor.fetchone():
                return {"status": "already_processed"}

            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, reference, status)
                VALUES (%s, %s, 'deposit', %s, 'completed')
            """, (user_id, amount, transaction_id))
            conn.commit()
            cursor.close()
            conn.close()

            asyncio.create_task(send_push_notification(
                user_id=int(user_id),
                title="💰 Dépôt confirmé !",
                body=f"Votre dépôt de {float(amount):,.0f} XOF a été crédité.",
                data={'type': 'deposit_confirmed'}
            ))
            return {"status": "success"}
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=500, content={"status": "error"})


@app.post("/api/deposit/initiate")
async def initiate_deposit(deposit: MobileMoneyDeposit, current_user: dict = Depends(get_current_user)):
    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if deposit.amount < 1000:
        raise HTTPException(status_code=400, detail="Minimum deposit is 1000 XOF")

    transaction_id = f"DEP_{int(datetime.now().timestamp())}_{current_user['id']}"

    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reference, status)
        VALUES (%s, %s, 'deposit_pending', %s, 'pending')
    """, (current_user['id'], deposit.amount, transaction_id))
    conn.commit()
    cursor.close()
    conn.close()

    return {"success": True, "transaction_id": transaction_id, "amount": deposit.amount}


# ─────────────────────────────────────────────
# Retrait
# ─────────────────────────────────────────────
@app.post("/api/withdraw")
async def withdraw(withdraw: MobileMoneyWithdraw, current_user: dict = Depends(get_current_user)):
    if withdraw.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if withdraw.amount < 1000:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is 1000 XOF")
    if float(current_user['balance']) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    transaction_id = f"WDR_{int(datetime.now().timestamp())}_{current_user['id']}"
    new_balance    = float(current_user['balance']) - withdraw.amount

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                       (withdraw.amount, current_user['id']))
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'withdrawal', %s, 'pending')
        """, (current_user['id'], -withdraw.amount, transaction_id))
        cursor.execute("""
            INSERT INTO withdrawal_requests
                (user_id, phone_number, amount, provider, transaction_id, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (current_user['id'], withdraw.phone_number, withdraw.amount,
              withdraw.provider, transaction_id))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"❌ Withdrawal DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process withdrawal: {str(e)}")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()

    user_info = {
        'username':        current_user['username'],
        'email':           current_user.get('email', 'Non renseigné'),
        'user_id':         current_user['id'],
        'current_balance': new_balance,
        'amount':          withdraw.amount,
        'phone':           withdraw.phone_number,
        'provider':        withdraw.provider,
        'date':            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'transaction_id':  transaction_id
    }
    await send_withdrawal_notification(user_info)

    asyncio.create_task(send_push_notification(
        user_id=current_user['id'],
        title="🔄 Retrait en cours",
        body=f"Votre demande de retrait de {withdraw.amount:,.0f} XOF est en cours de traitement.",
        data={'type': 'withdrawal_pending', 'transaction_id': transaction_id}
    ))

    return {
        "success":        True,
        "transaction_id": transaction_id,
        "new_balance":    new_balance,
        "message":        "Demande de retrait enregistrée."
    }


# ─────────────────────────────────────────────
# Historique & Stats
# ─────────────────────────────────────────────
@app.get("/api/user/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM transactions WHERE user_id = %s
        ORDER BY created_at DESC LIMIT 50
    """, (current_user['id'],))
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"transactions": serialize_for_json(transactions)}

@app.get("/api/user/balance")
async def get_balance(current_user: dict = Depends(get_current_user)):
    return {"balance": float(current_user['balance'])}

@app.get("/api/user/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            COUNT(DISTINCT gp.game_id) as total_games,
            SUM(CASE WHEN g.winner_id = %s THEN 1 ELSE 0 END) as wins,
            COALESCE(SUM(CASE WHEN g.winner_id = %s THEN g.total_pot * 0.75 ELSE 0 END), 0) as total_won
        FROM game_participants gp
        JOIN games g ON gp.game_id = g.id
        WHERE gp.user_id = %s
    """, (current_user['id'], current_user['id'], current_user['id']))
    stats = cursor.fetchone()
    cursor.close()
    conn.close()

    total = stats['total_games'] or 0
    wins  = stats['wins']        or 0
    return {
        "total_games": total,
        "wins":        wins,
        "total_won":   float(stats['total_won']) if stats['total_won'] else 0.0,
        "win_rate":    (wins / total * 100) if total > 0 else 0.0
    }

@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            u.id, u.username,
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
    return serialize_for_json(leaderboard)


# ─────────────────────────────────────────────
# Jeux
# ─────────────────────────────────────────────
@app.post("/api/games/create")
async def create_game(game_data: GameCreate, current_user: dict = Depends(get_current_user)):
    if game_data.bet_amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")
    if float(current_user['balance']) < game_data.bet_amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    conn = cursor = None
    try:
        conn   = get_db_connection()
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
        return {"game_id": game_id, "message": "Game created successfully"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create game")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.post("/api/games/join")
async def join_game(join_data: JoinGame, current_user: dict = Depends(get_current_user)):
    if join_data.guessed_number < 1 or join_data.guessed_number > 100:
        raise HTTPException(status_code=400, detail="Number must be between 1 and 100")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM games WHERE id = %s AND status = 'waiting' FOR UPDATE",
            (join_data.game_id,)
        )
        game = cursor.fetchone()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found or already started")

        if float(current_user['balance']) < float(game['bet_amount']):
            raise HTTPException(status_code=400, detail="Insufficient balance")

        cursor.execute(
            "SELECT id FROM game_participants WHERE game_id = %s AND user_id = %s",
            (join_data.game_id, current_user['id'])
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already joined this game")

        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                       (float(game['bet_amount']), current_user['id']))
        cursor.execute("""
            INSERT INTO game_participants (game_id, user_id, guessed_number)
            VALUES (%s, %s, %s)
        """, (join_data.game_id, current_user['id'], join_data.guessed_number))
        cursor.execute("UPDATE games SET total_pot = total_pot + %s WHERE id = %s",
                       (float(game['bet_amount']), join_data.game_id))
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'bet', %s, 'completed')
        """, (current_user['id'], float(game['bet_amount']), f"game_{join_data.game_id}_bet"))

        cursor.execute(
            "SELECT COUNT(*) as count FROM game_participants WHERE game_id = %s",
            (join_data.game_id,)
        )
        participant_count = cursor.fetchone()['count']
        conn.commit()

        if game['creator_id'] != current_user['id']:
            asyncio.create_task(send_push_notification(
                user_id=game['creator_id'],
                title="👤 Nouveau joueur !",
                body=f"{current_user['username']} a rejoint votre partie.",
                data={'type': 'player_joined', 'game_id': str(join_data.game_id)}
            ))

        if participant_count >= 2:
            cursor2 = conn.cursor()
            cursor2.execute("UPDATE games SET status = 'active' WHERE id = %s", (join_data.game_id,))
            conn.commit()
            cursor2.close()
            asyncio.create_task(start_game_timer(join_data.game_id))

        return {"message": "Joined game successfully"}
    except HTTPException:
        raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to join game")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


async def start_game_timer(game_id: int):
    from .bot_service import _notify_game_result
    try:
        for i in range(30, 0, -1):
            await manager.broadcast_to_game(game_id, {'type': 'timer', 'seconds': i})
            await asyncio.sleep(1)

        result = determine_game_winner(game_id)
        if result:
            winner_id     = result['winner_id']
            winning_number = result['winning_number']
            winner_amount  = float(result['winner_amount'])

            conn   = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s",
                           (winner_amount, winner_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, reference, status)
                VALUES (%s, %s, 'win', %s, 'completed')
            """, (winner_id, winner_amount, f"game_{game_id}_win"))
            conn.commit()
            cursor.close()
            conn.close()

            conn   = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT gp.user_id, gp.guessed_number, u.username
                FROM game_participants gp
                JOIN users u ON gp.user_id = u.id
                WHERE gp.game_id = %s
            """, (game_id,))
            participants = cursor.fetchall()
            cursor.close()
            conn.close()

            winner_username = next(
                (p['username'] for p in participants if p['user_id'] == winner_id), 'Inconnu'
            )

            await manager.broadcast_to_game(game_id, {
                'type':             'game_ended',
                'winner_id':        winner_id,
                'winner_username':  winner_username,
                'winning_number':   winning_number,
                'winner_amount':    winner_amount,
                'participants': [
                    {
                        'user_id':        p['user_id'],
                        'username':       p['username'],
                        'guessed_number': p['guessed_number']
                    }
                    for p in participants
                ]
            })

            for p in participants:
                if p['user_id'] == winner_id:
                    asyncio.create_task(send_push_notification(
                        user_id=p['user_id'],
                        title="🎉 FÉLICITATIONS !",
                        body=f"Vous avez gagné {winner_amount:,.0f} XOF !",
                        data={'type': 'game_won', 'game_id': str(game_id)}
                    ))
                else:
                    asyncio.create_task(send_push_notification(
                        user_id=p['user_id'],
                        title="😢 Partie terminée",
                        body=f"Le numéro gagnant était {winning_number}. Meilleure chance !",
                        data={'type': 'game_lost', 'game_id': str(game_id)}
                    ))

            await _notify_game_result(game_id, result)
    except Exception as e:
        logger.error(f"Erreur timer partie {game_id}: {e}")


@app.get("/api/games/available")
async def get_available_games(current_user: dict = Depends(get_current_user)):
    conn = cursor = None
    try:
        conn   = get_db_connection()
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
            if 'bet_amount' in game: game['bet_amount'] = float(game['bet_amount'])
            if 'total_pot'  in game: game['total_pot']  = float(game['total_pot'])
        return games
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch games")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.get("/api/games/{game_id}/details")
async def get_game_details(game_id: int):
    conn = cursor = None
    try:
        conn   = get_db_connection()
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
        if game.get('bet_amount'): game['bet_amount'] = float(game['bet_amount'])
        if game.get('total_pot'):  game['total_pot']  = float(game['total_pot'])
        return game
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch game details")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ─────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────
@app.websocket("/ws/{game_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str):
    user = None
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Token invalide")
            return
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (payload.get('user_id'),))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            await websocket.close(code=1008, reason="Utilisateur introuvable")
            return
    except Exception as e:
        await websocket.close(code=1008, reason="Authentification échouée")
        return

    await manager.connect(game_id, websocket, user_id=user['id'])

    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*, COUNT(gp.id) as participants_count,
                   GROUP_CONCAT(DISTINCT u.username) as participants
            FROM games g
            LEFT JOIN game_participants gp ON g.id = gp.game_id
            LEFT JOIN users u ON gp.user_id = u.id
            WHERE g.id = %s GROUP BY g.id
        """, (game_id,))
        game_state = cursor.fetchone()
        cursor.close()
        conn.close()
        if game_state:
            game_state = serialize_for_json(game_state)
        await websocket.send_json({'type': 'game_state', 'data': game_state})

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
        pass
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        manager.disconnect(game_id, websocket, user_id=user['id'] if user else None)


# ─────────────────────────────────────────────
# Mot de passe & Username
# ─────────────────────────────────────────────
@app.post("/api/change-password")
async def change_password(request: Request):
    data         = await request.json()
    username     = data.get('username', '').strip()
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()

    if not username or not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Champs manquants")
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Nouveau mot de passe trop court")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user or not verify_password(old_password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Identifiants incorrects")
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                       (get_password_hash(new_password), user['id']))
        conn.commit()
        return {"success": True, "message": "Mot de passe modifié"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.post("/api/generate-reset-token")
async def generate_reset_token(request: Request):
    data     = await request.json()
    username = data.get('username', '').strip()
    if not username:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur requis")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        token   = secrets.token_urlsafe(32)
        success = create_reset_token(user['id'], token, expires_minutes=15)
        if not success:
            raise HTTPException(status_code=500, detail="Erreur création token")
        return {"success": True, "token": token}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.post("/api/reset-password-with-token")
async def reset_password_with_token(request: Request):
    data         = await request.json()
    token        = data.get('token', '').strip()
    new_password = data.get('new_password', '').strip()

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token et mot de passe requis")
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")

    user_id = validate_reset_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                       (get_password_hash(new_password), user_id))
        mark_token_as_used(token)
        conn.commit()
        return {"success": True, "message": "Mot de passe réinitialisé"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.post("/api/change-username")
async def change_username(request: Request, current_user: dict = Depends(get_current_user)):
    data         = await request.json()
    new_username = data.get('new_username', '').strip()
    password     = data.get('password', '').strip()

    if not new_username or not password:
        raise HTTPException(status_code=400, detail="Champs manquants")
    if len(new_username) < 3:
        raise HTTPException(status_code=400, detail="Nom trop court")

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (current_user['id'],))
        user = cursor.fetchone()
        if not user or not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Mot de passe incorrect")
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s",
                       (new_username, current_user['id']))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Nom déjà pris")
        cursor.execute("UPDATE users SET username = %s WHERE id = %s",
                       (new_username, current_user['id']))
        conn.commit()
        return {"success": True, "message": "Nom d'utilisateur modifié"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


@app.post("/api/cleanup-tokens")
async def cleanup_tokens():
    cleanup_expired_tokens()
    return {"success": True}


# ─────────────────────────────────────────────
# Admin — Stats
# ─────────────────────────────────────────────
@app.get("/api/admin/stats")
async def get_admin_stats(current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE LOWER(username) != 'admin'")
    total_users = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM games")
    total_games = cursor.fetchone()['total']
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'withdrawal' AND status = 'completed'")
    total_withdrawn = cursor.fetchone()['total'] or 0
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'win' AND status = 'completed'")
    total_won = cursor.fetchone()['total'] or 0
    cursor.execute("SELECT COUNT(*) as pending FROM withdrawal_requests WHERE status = 'pending'")
    pending_withdrawals = cursor.fetchone()['pending']
    cursor.execute("SELECT COUNT(*) as total FROM transactions")
    total_transactions = cursor.fetchone()['total']
    cursor.close()
    conn.close()

    return {
        "total_users":        total_users,
        "total_games":        total_games,
        "total_withdrawn":    float(total_withdrawn),
        "total_won":          float(total_won),
        "pending_withdrawals": pending_withdrawals,
        "platform_balance":   float(total_won) - float(total_withdrawn),
        "total_transactions": total_transactions,
    }


# ─────────────────────────────────────────────
# Admin — Users
# ─────────────────────────────────────────────
@app.get("/api/admin/users")
async def get_admin_users(current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, balance, is_banned, created_at FROM users ORDER BY id")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"users": serialize_for_json(users)}

@app.get("/api/admin/users/{user_id}")
async def get_user_details(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, balance, is_banned, created_at FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_for_json(user)

@app.post("/api/admin/users/{user_id}/toggle-ban")
async def toggle_ban_user(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_status = not user[0]
    cursor.execute("UPDATE users SET is_banned = %s WHERE id = %s", (new_status, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True, "is_banned": new_status}

@app.put("/api/admin/users/{user_id}/balance")
async def update_user_balance(user_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    data        = await request.json()
    new_balance = data.get('balance')
    if new_balance is None or new_balance < 0:
        raise HTTPException(status_code=400, detail="Invalid balance")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True}

@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user[0].lower() == 'admin':
            raise HTTPException(status_code=403, detail="Cannot delete admin")
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM game_participants WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM chat_messages WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM withdrawal_requests WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM mobile_money_deposits WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM mobile_money_withdrawals WHERE user_id = %s", (user_id,))
        cursor.execute("UPDATE games SET creator_id = 1 WHERE creator_id = %s", (user_id,))
        cursor.execute("UPDATE games SET winner_id = NULL WHERE winner_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
    finally:
        cursor.close()
        conn.close()
    return {"success": True}


# ─────────────────────────────────────────────
# Admin — Retraits
# ─────────────────────────────────────────────
@app.get("/api/admin/withdrawals")
async def get_admin_withdrawals(current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT wr.*, u.username FROM withdrawal_requests wr
        JOIN users u ON wr.user_id = u.id
        ORDER BY wr.created_at DESC
    """)
    withdrawals = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"withdrawals": serialize_for_json(withdrawals)}

@app.post("/api/admin/withdrawals/{withdrawal_id}/confirm")
async def confirm_withdrawal(withdrawal_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, amount FROM withdrawal_requests WHERE id = %s", (withdrawal_id,))
    wr = cursor.fetchone()
    if not wr:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    cursor.execute("""
        UPDATE withdrawal_requests SET status = 'completed', processed_at = NOW()
        WHERE id = %s AND status = 'pending'
    """, (withdrawal_id,))
    cursor.execute("""
        UPDATE transactions t
        JOIN withdrawal_requests wr ON t.reference = wr.transaction_id
        SET t.status = 'completed' WHERE wr.id = %s
    """, (withdrawal_id,))
    conn.commit()
    cursor.close()
    conn.close()
    if wr:
        asyncio.create_task(send_push_notification(
            user_id=wr['user_id'],
            title="✅ Retrait confirmé !",
            body=f"Votre retrait de {float(wr['amount']):,.0f} XOF a été traité.",
            data={'type': 'withdrawal_confirmed'}
        ))
    return {"success": True}

@app.post("/api/admin/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT user_id, amount, transaction_id FROM withdrawal_requests
        WHERE id = %s AND status = 'pending'
    """, (withdrawal_id,))
    wr = cursor.fetchone()
    if not wr:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (wr['amount'], wr['user_id']))
    cursor.execute("UPDATE withdrawal_requests SET status = 'rejected', processed_at = NOW() WHERE id = %s", (withdrawal_id,))
    cursor.execute("UPDATE transactions SET status = 'rejected' WHERE reference = %s", (wr['transaction_id'],))
    conn.commit()
    cursor.close()
    conn.close()
    asyncio.create_task(send_push_notification(
        user_id=wr['user_id'],
        title="❌ Retrait refusé",
        body=f"Votre retrait de {float(wr['amount']):,.0f} XOF a été refusé. Solde recrédité.",
        data={'type': 'withdrawal_rejected'}
    ))
    return {"success": True}


# ─────────────────────────────────────────────
# Admin — Jeux & Transactions
# ─────────────────────────────────────────────
@app.get("/api/admin/games")
async def get_admin_games(current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT g.*, u.username as creator_name, w.username as winner_name,
               COUNT(gp.id) as participants_count
        FROM games g
        LEFT JOIN users u  ON g.creator_id = u.id
        LEFT JOIN users w  ON g.winner_id  = w.id
        LEFT JOIN game_participants gp ON g.id = gp.game_id
        GROUP BY g.id ORDER BY g.created_at DESC LIMIT 100
    """)
    games = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"games": serialize_for_json(games)}

@app.delete("/api/admin/games/{game_id}")
async def delete_game(game_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM game_participants WHERE game_id = %s", (game_id,))
    cursor.execute("DELETE FROM games WHERE id = %s", (game_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True}

@app.get("/api/admin/transactions")
async def get_admin_transactions(current_user: dict = Depends(get_current_user)):
    if current_user.get('username').lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.*, u.username FROM transactions t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC LIMIT 200
    """)
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"transactions": serialize_for_json(transactions)}


# ─────────────────────────────────────────────
# Admin — Chat
# ─────────────────────────────────────────────
@app.get("/api/admin/chats")
async def get_admin_chats(current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            u.id as user_id, u.username, u.is_banned,
            (SELECT message FROM chat_messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message,
            (SELECT created_at FROM chat_messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message_date,
            (SELECT COUNT(*) FROM chat_messages WHERE user_id = u.id AND is_read = FALSE AND is_admin = FALSE) as unread_count
        FROM users u
        WHERE u.username != 'admin'
        ORDER BY last_message_date DESC
    """)
    chats = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"chats": serialize_for_json(chats)}

@app.get("/api/admin/chats/{user_id}/messages")
async def get_chat_messages(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        UPDATE chat_messages SET is_read = TRUE
        WHERE user_id = %s AND is_admin = FALSE
    """, (user_id,))
    cursor.execute("""
        SELECT * FROM chat_messages WHERE user_id = %s
        ORDER BY created_at ASC LIMIT 200
    """, (user_id,))
    messages = cursor.fetchall()
    conn.commit()
    cursor.close()
    conn.close()
    return {"messages": serialize_for_json(messages)}

@app.post("/api/admin/chats/{user_id}/send")
async def send_admin_message(user_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    data    = await request.json()
    message = data.get('message')
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_messages (user_id, message, is_admin, is_read)
        VALUES (%s, %s, TRUE, TRUE)
    """, (user_id, message))
    conn.commit()
    cursor.close()
    conn.close()
    asyncio.create_task(send_push_notification(
        user_id=user_id,
        title="📩 Nouveau message du support",
        body=message[:100],
        data={'type': 'admin_message'}
    ))
    return {"success": True}


# ─────────────────────────────────────────────
# Debug & Test
# ─────────────────────────────────────────────
@app.get("/api/debug/brevo")
async def debug_brevo():
    return {
        "brevo_configured": bool(os.getenv("BREVO_API_KEY")),
        "brevo_email":      os.getenv("BREVO_EMAIL"),
    }

@app.get("/api/debug/firebase")
async def debug_firebase():
    return {
        "firebase_configured": bool(os.getenv("FIREBASE_PRIVATE_KEY")),
        "project_id":          os.getenv("FIREBASE_PROJECT_ID"),
        "client_email":        os.getenv("FIREBASE_CLIENT_EMAIL"),
    }

@app.post("/api/test-push")
async def test_push(current_user: dict = Depends(get_current_user)):
    result = await send_push_notification(
        user_id=current_user['id'],
        title="🎮 Test Notification",
        body="Ceci est un test de notification push !",
        data={'type': 'test', 'timestamp': str(datetime.now())}
    )
    return {
        "success": result,
        "message": "Notification envoyée !" if result else "Échec",
        "user_id": current_user['id']
    }

# ─────────────────────────────────────────────
# Admin add balance (test/admin)
# ─────────────────────────────────────────────
@app.post("/api/admin/add-balance")
async def admin_add_balance(username: str, amount: float):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, balance FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user['id']))
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'admin_credit', %s, 'completed')
        """, (user['id'], amount, f"ADMIN_CREDIT_{int(datetime.now().timestamp())}"))
        conn.commit()
        return {"success": True, "new_balance": float(user['balance']) + amount}
    except HTTPException:
        raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to add balance")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()

# ─────────────────────────────────────────────
# SQL reminder
# ALTER TABLE users ADD COLUMN fcm_token VARCHAR(255) NULL;
# CREATE INDEX idx_fcm_token ON users(fcm_token);
# ─────────────────────────────────────────────
