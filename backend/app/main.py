from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from fastapi import Request
import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import asynccontextmanager
from datetime import datetime, date
from decimal import Decimal
from .database import init_database, get_db_connection, close_db_connections
from .auth import verify_password, get_password_hash, create_access_token, decode_token
from .websocket_manager import manager
from .game_logic import determine_game_winner
from .schemas import *
from .bot_service import bot_scheduler, ensure_platform_user
import mysql.connector
import secrets
import httpx

import secrets
from datetime import datetime, timedelta
from .database import create_reset_token, validate_reset_token, mark_token_as_used, cleanup_expired_tokens

# ============================================================
# Firebase Admin SDK
# pip install firebase-admin
# Place firebase_credentials.json à la racine du projet backend
# ============================================================
import firebase_admin
from firebase_admin import credentials, messaging as fcm_messaging


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Configuration Email Admin
# ─────────────────────────────────────────────
EMAIL_ADMIN    = "lfdweb123@gmail.com"
EMAIL_PASSWORD = "rwyezyfswwurmmji"   # ← Remplace par ton mot de passe d'application Gmail


# ─────────────────────────────────────────────
# Firebase Admin Init - Version Variables d'environnement
# ─────────────────────────────────────────────
import os
import json
import firebase_admin
from firebase_admin import credentials

_firebase_app = None

def init_firebase_admin():
    """Initialiser Firebase Admin SDK avec variables d'environnement."""
    global _firebase_app
    if _firebase_app is None:
        try:
            # Méthode 1: Variables individuelles
            private_key = os.getenv("FIREBASE_PRIVATE_KEY")
            
            if private_key:
                # Remplacer les \n littéraux par de vrais sauts de ligne
                private_key = private_key.replace('\\n', '\n')
                
                creds_dict = {
                    "type": os.getenv("FIREBASE_TYPE", "service_account"),
                    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": private_key,
                    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                    "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
                    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
                    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN", "googleapis.com")
                }
                
                cred = credentials.Certificate(creds_dict)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (depuis variables env)")
                return
            
            # Méthode 2: JSON complet (fallback)
            firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
            if firebase_creds_json:
                creds_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(creds_dict)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (depuis JSON env)")
                return
            
            # Méthode 3: Fichier local (développement uniquement)
            cred_path = os.path.join(os.path.dirname(__file__), "..", "firebase_credentials.json")
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé (depuis fichier local)")
                return
                
            logger.warning("⚠️ Aucune configuration Firebase trouvée")
            
        except Exception as e:
            logger.warning(f"⚠️ Firebase Admin SDK initialization failed: {e}")
# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def serialize_for_json(obj):
    """Convertit récursivement les types non-sérialisables."""
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
# Notification Push Firebase
# ─────────────────────────────────────────────
async def send_push_notification(user_id: int, title: str, body: str, data: dict = None):
    """
    Récupère le token FCM de l'utilisateur en base et envoie une notification.
    data = dict pour la navigation Flutter, ex: {'type': 'game_won', 'game_id': '42'}
    """
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
# Notification Email Admin - Version Brevo API
# ─────────────────────────────────────────────
import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Configuration Brevo avec variables d'environnement (SÉCURISÉ)
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_EMAIL = os.getenv("BREVO_EMAIL", "lfdweb123@gmail.com")

# Vérification de la configuration
if not BREVO_API_KEY:
    logger.warning("⚠️ BREVO_API_KEY non configurée - Les emails ne seront pas envoyés")

# Configuration du SDK Brevo (uniquement si la clé existe)
configuration = None
if BREVO_API_KEY:
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY

async def send_withdrawal_notification(user_info: dict):
    """Envoie un email via l'API Brevo."""
    
    # Vérifier que la clé API est configurée
    if not BREVO_API_KEY or not configuration:
        logger.error("❌ BREVO_API_KEY non configurée - Email non envoyé")
        logger.warning("   Ajoute BREVO_API_KEY dans les variables d'environnement Railway")
        return False
    
    try:
        logger.info("=" * 40)
        logger.info("📧 TENTATIVE D'ENVOI D'EMAIL VIA BREVO")
        logger.info(f"   Destinataire: {BREVO_EMAIL}")
        logger.info(f"   Username: {user_info['username']}")
        logger.info(f"   Montant: {user_info['amount']} XOF")
        
        # Construction du contenu HTML
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
        
        # Création de l'instance API
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        # Création de l'email
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": BREVO_EMAIL, "name": "Admin Guess Game"}],
            sender={"email": BREVO_EMAIL, "name": "Guess Number Game"},
            subject=f"🔄 Demande de retrait - {user_info['username']}",
            html_content=html_content,
            reply_to={"email": BREVO_EMAIL, "name": "Support Guess Game"}
        )
        
        # Envoi en asynchrone (pour ne pas bloquer)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: api_instance.send_transac_email(send_smtp_email)
        )
        
        logger.info(f"✅ Email envoyé avec succès via Brevo! Message ID: {response.message_id}")
        return True
        
    except ApiException as e:
        logger.error(f"❌ Brevo API Exception: {e}")
        logger.error(f"   Status: {e.status}")
        logger.error(f"   Body: {e.body}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur envoi email: {e}")
        import traceback
        traceback.print_exc()
        return False




# ─────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    init_database()
    logger.info("Database initialized")

    init_firebase_admin()  # ← Initialisation Firebase Admin

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
        raise HTTPException(status_code=401, detail="Not authenticated - No Authorization header")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Use 'Bearer <token>'")

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
        "status": "running",
        "version": "1.0.0",
        "endpoints": [
            "/health", "/api/register", "/api/login",
            "/api/games/create", "/api/games/join",
            "/api/games/available", "/ws/{game_id}/{token}"
        ]
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
# Auth endpoints
# ─────────────────────────────────────────────
@app.post("/api/register")
async def register(user_data: UserCreate):
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
        return {"message": "User created successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()

@app.post("/api/login")
async def login(user_data: UserLogin):
    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (user_data.username,))
        user = cursor.fetchone()

        if not user or not verify_password(user_data.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"user_id": user['id'], "username": user['username']})
        logger.info(f"User logged in: {user_data.username}")

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
    """Sauvegarder le token FCM après login Flutter."""
    data      = await request.json()
    fcm_token = data.get('fcm_token')

    if not fcm_token:
        raise HTTPException(status_code=400, detail="fcm_token manquant")

    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET fcm_token = %s WHERE id = %s",
        (fcm_token, current_user['id'])
    )
    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"FCM token sauvegardé pour user {current_user['id']}")
    return {"success": True}


# ─────────────────────────────────────────────
# Dépôt (FeexPay)
# ─────────────────────────────────────────────
@app.post("/api/feexpay/webhook")
async def feexpay_webhook(request: Request):
    try:
        data           = await request.json()
        logger.info(f"FeexPay webhook received: {data}")
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
            logger.info(f"Deposit confirmed: User {user_id}, Amount {amount}")

            # ── Push notification dépôt confirmé ──
            asyncio.create_task(send_push_notification(
                user_id=int(user_id),
                title="💰 Dépôt confirmé !",
                body=f"Votre dépôt de {float(amount):,.0f} XOF a été crédité sur votre compte.",
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

    return {
        "success":        True,
        "transaction_id": transaction_id,
        "amount":         deposit.amount,
        "user_id":        current_user['id']
    }


# ─────────────────────────────────────────────
# Retrait ← VERSION COMPLÈTE AVEC EMAIL + PUSH
# ─────────────────────────────────────────────
@app.post("/api/withdraw")
async def withdraw(withdraw: MobileMoneyWithdraw, current_user: dict = Depends(get_current_user)):
    # LOGS DÉTAILLÉS
    logger.info("=" * 50)
    logger.info(f"📞 WITHDRAW REQUEST")
    logger.info(f"   User ID: {current_user['id']}")
    logger.info(f"   Username: {current_user['username']}")
    logger.info(f"   Amount: {withdraw.amount}")
    logger.info(f"   Phone: {withdraw.phone_number}")
    logger.info(f"   Provider: {withdraw.provider}")
    logger.info(f"   Current balance: {current_user['balance']}")
    logger.info("=" * 50)
    
    # ── Validations ──────────────────────────────────
    if withdraw.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if withdraw.amount < 1000:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is 1000 XOF")
    
    if float(current_user['balance']) < withdraw.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    transaction_id = f"WDR_{int(datetime.now().timestamp())}_{current_user['id']}"
    new_balance = float(current_user['balance']) - withdraw.amount  # ← CORRIGÉ
    
    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Déduire le solde
        cursor.execute(
            "UPDATE users SET balance = balance - %s WHERE id = %s",
            (withdraw.amount, current_user['id'])
        )
        logger.info(f"✅ Balance updated for user {current_user['id']}")
        
        # 2. Enregistrer dans transactions
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, reference, status)
            VALUES (%s, %s, 'withdrawal', %s, 'pending')
        """, (current_user['id'], -withdraw.amount, transaction_id))
        logger.info(f"✅ Transaction recorded: {transaction_id}")
        
        # 3. Enregistrer dans withdrawal_requests
        cursor.execute("""
            INSERT INTO withdrawal_requests
                (user_id, phone_number, amount, provider, transaction_id, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (
            current_user['id'],
            withdraw.phone_number,
            withdraw.amount,
            withdraw.provider,
            transaction_id
        ))
        logger.info(f"✅ Withdrawal request recorded")
        
        conn.commit()
        logger.info(f"✅ Withdrawal transaction COMMITTED: {transaction_id}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Withdrawal DB error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process withdrawal: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    # 4. Email à l'admin (ATTENDU avec await)
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
    
    # ← ICI: await au lieu de asyncio.create_task
    await send_withdrawal_notification(user_info)
    
    # 5. Push notification (peut rester en create_task)
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
        "message":        "Demande de retrait enregistrée. Vous serez notifié une fois traité."
    }


# ─────────────────────────────────────────────
# Historique & Stats
# ─────────────────────────────────────────────
@app.get("/api/user/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    conn   = get_db_connection()
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
    return serialize_for_json(leaderboard)


# ─────────────────────────────────────────────
# Retraits en attente (admin)
# ─────────────────────────────────────────────
@app.get("/api/admin/withdrawals")
async def get_pending_withdrawals(current_user: dict = Depends(get_current_user)):
    """Liste des retraits en attente — accessible uniquement à l'admin."""
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT wr.*, u.username, u.email
        FROM withdrawal_requests wr
        JOIN users u ON wr.user_id = u.id
        WHERE wr.status = 'pending'
        ORDER BY wr.created_at DESC
    """)
    withdrawals = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"withdrawals": serialize_for_json(withdrawals)}

@app.post("/api/admin/withdrawals/{withdrawal_id}/confirm")
async def confirm_withdrawal(withdrawal_id: int, current_user: dict = Depends(get_current_user)):
    """Marquer un retrait comme traité."""
    if current_user.get('username') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Récupérer les infos du retrait avant commit pour le push
    cursor.execute(
        "SELECT user_id, amount FROM withdrawal_requests WHERE id = %s",
        (withdrawal_id,)
    )
    wr = cursor.fetchone()

    cursor.execute("""
        UPDATE withdrawal_requests
        SET status = 'completed', processed_at = NOW()
        WHERE id = %s AND status = 'pending'
    """, (withdrawal_id,))

    # Mettre à jour aussi la transaction
    cursor.execute("""
        UPDATE transactions t
        JOIN withdrawal_requests wr ON t.reference = wr.transaction_id
        SET t.status = 'completed'
        WHERE wr.id = %s
    """, (withdrawal_id,))

    conn.commit()
    cursor.close()
    conn.close()

    # ── Push notification retrait confirmé ──
    if wr:
        asyncio.create_task(send_push_notification(
            user_id=wr['user_id'],
            title="✅ Retrait confirmé !",
            body=f"Votre retrait de {float(wr['amount']):,.0f} XOF a été traité avec succès.",
            data={'type': 'withdrawal_confirmed'}
        ))

    return {"success": True, "message": "Retrait confirmé"}


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
        logger.info(f"Game created: ID {game_id} by user {current_user['id']}")
        return {"game_id": game_id, "message": "Game created successfully"}
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Create game error: {e}")
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
        logger.info(f"User {current_user['id']} joined game {join_data.game_id}")

        # ── Push notification au créateur de la partie ──
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
        logger.error(f"Join game error: {e}")
        raise HTTPException(status_code=500, detail="Failed to join game")
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()

async def start_game_timer(game_id: int):
    """Timer avec notification immédiate à TOUS les joueurs à la fin"""
    from .bot_service import _notify_game_result
    try:
        # Timer de 30 secondes
        for i in range(30, 0, -1):
            logger.info(f"Partie {game_id} — fin dans {i}s")
            await manager.broadcast_to_game(game_id, {'type': 'timer', 'seconds': i})
            await asyncio.sleep(1)
        
        # FIN DU TIMER - Déterminer le gagnant
        result = determine_game_winner(game_id)
        
        if result:
            winner_id = result['winner_id']
            winning_number = result['winning_number']
            winner_amount = float(result['winner_amount'])

            # ✅ AJOUTER LE GAIN AU SOLDE DU GAGNANT
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Créditer le gagnant
            cursor.execute("""
                UPDATE users 
                SET balance = balance + %s 
                WHERE id = %s
            """, (winner_amount, winner_id))
            
            # Enregistrer la transaction de gain
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, reference, status)
                VALUES (%s, %s, 'win', %s, 'completed')
            """, (winner_id, winner_amount, f"game_{game_id}_win"))
            
            conn.commit()
            logger.info(f"💰 Gain crédité: User {winner_id} a reçu {winner_amount} XOF")
            cursor.close()
            conn.close()

            # Récupérer tous les participants AVEC leur numéro joué
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT gp.user_id, gp.guessed_number, u.username
                FROM game_participants gp
                JOIN users u ON gp.user_id = u.id
                WHERE gp.game_id = %s
            """, (game_id,))
            participants = cursor.fetchall()

            # Récupérer le username du gagnant
            winner_username = next(
                (p['username'] for p in participants if p['user_id'] == winner_id),
                'Inconnu'
            )
            cursor.close()
            conn.close()

            # ── Broadcast à TOUTE la partie ──
            game_end_message = {
                'type': 'game_ended',
                'winner_id': winner_id,
                'winner_username': winner_username,
                'winning_number': winning_number,
                'winner_amount': winner_amount,
                'participants': [
                    {
                        'user_id': p['user_id'],
                        'username': p['username'],
                        'guessed_number': p['guessed_number']
                    }
                    for p in participants
                ]
            }

            await manager.broadcast_to_game(game_id, game_end_message)
            logger.info(f"✅ game_ended broadcasté à toute la partie {game_id}")

            # Push notifications
            for p in participants:
                user_id = p['user_id']
                if user_id == winner_id:
                    asyncio.create_task(send_push_notification(
                        user_id=user_id,
                        title="🎉 FÉLICITATIONS !",
                        body=f"Vous avez gagné {winner_amount:,.0f} XOF !",
                        data={'type': 'game_won', 'game_id': str(game_id)}
                    ))
                else:
                    asyncio.create_task(send_push_notification(
                        user_id=user_id,
                        title="😢 Partie terminée",
                        body=f"Le numéro gagnant était {winning_number}. Meilleure chance !",
                        data={'type': 'game_lost', 'game_id': str(game_id)}
                    ))

            await _notify_game_result(game_id, result)
            logger.info(f"Partie {game_id} terminée — gagnant: {winner_id} ({winner_username}), numéro: {winning_number}")

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
        logger.error(f"Get available games error: {e}")
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
        if 'bet_amount' in game and game['bet_amount']: game['bet_amount'] = float(game['bet_amount'])
        if 'total_pot'  in game and game['total_pot']:  game['total_pot']  = float(game['total_pot'])
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game details error: {e}")
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

        logger.info(f"WS connecté: user {user['id']} → partie {game_id}")
    except Exception as e:
        logger.error(f"WS auth error: {e}")
        await websocket.close(code=1008, reason="Authentification échouée")
        return

    await manager.connect(game_id, websocket, user_id=user['id'])

    try:
        conn   = get_db_connection()
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
        logger.info(f"WS déconnecté: partie {game_id}")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        manager.disconnect(game_id, websocket, user_id=user['id'] if user else None)


#// ═══════════════════════════════════════════════════════════════
#// À AJOUTER dans main.py (FastAPI) — endpoint change-password
#// ═══════════════════════════════════════════════════════════════
# ============================================================
# ENDPOINT: Changer le mot de passe
# ============================================================

@app.post("/api/change-password")
async def change_password(request: Request):
    data = await request.json()
    username = data.get('username', '').strip()
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()

    if not username or not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Champs manquants")

    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Nouveau mot de passe trop court (minimum 4 caracteres)")

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user or not verify_password(old_password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Identifiants incorrects")

        new_hash = get_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user['id'])
        )
        conn.commit()
        logger.info(f"Mot de passe change pour {username}")

        return {"success": True, "message": "Mot de passe modifie avec succes"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()




# Ajoutez ces endpoints dans votre main.py

@app.post("/api/reset-password")
async def reset_password(request: Request):
    data = await request.json()
    username = data.get('username', '').strip()
    new_password = data.get('new_password', '').strip()

    if not username or not new_password:
        raise HTTPException(status_code=400, detail="Champs manquants")

    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Nouveau mot de passe trop court")

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        new_hash = get_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user['id'])
        )
        conn.commit()
        logger.info(f"Mot de passe reinitialise par email pour {username}")

        return {"success": True, "message": "Mot de passe reinitialise avec succes"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/api/change-username")
async def change_username(request: Request, current_user: dict = Depends(get_current_user)):
    data = await request.json()
    new_username = data.get('new_username', '').strip()
    password = data.get('password', '').strip()

    if not new_username or not password:
        raise HTTPException(status_code=400, detail="Champs manquants")

    if len(new_username) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court (minimum 3 caracteres)")

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verifier mot de passe
        cursor.execute("SELECT * FROM users WHERE id = %s", (current_user['id'],))
        user = cursor.fetchone()

        if not user or not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Mot de passe incorrect")

        # Verifier si nouveau nom existe
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s",
                       (new_username, current_user['id']))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Nom d'utilisateur deja pris")

        cursor.execute(
            "UPDATE users SET username = %s WHERE id = %s",
            (new_username, current_user['id'])
        )
        conn.commit()
        logger.info(f"Username changed: {current_user['username']} -> {new_username}")

        return {"success": True, "message": "Nom d'utilisateur modifie avec succes"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change username error: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================
# GENERER UN TOKEN DE REINITIALISATION
# ============================================================
@app.post("/api/generate-reset-token")
async def generate_reset_token(request: Request):
    data = await request.json()
    username = data.get('username', '').strip()

    if not username:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur requis")

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouve")

        # Generer un token unique
        token = secrets.token_urlsafe(32)
        
        # Sauvegarder en base
        success = create_reset_token(user['id'], token, expires_minutes=15)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la creation du token")

        logger.info(f"Token genere pour {username}: {token[:10]}...")

        return {"success": True, "token": token}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate token error: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ============================================================
# REINITIALISER LE MOT DE PASSE AVEC TOKEN
# ============================================================
@app.post("/api/reset-password-with-token")
async def reset_password_with_token(request: Request):
    data = await request.json()
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '').strip()

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token et mot de passe requis")

    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (minimum 4 caracteres)")

    # Valider le token
    user_id = validate_reset_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide ou expire")

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        new_hash = get_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user_id)
        )
        
        # Marquer le token comme utilise
        mark_token_as_used(token)
        
        conn.commit()

        logger.info(f"Mot de passe reinitialise avec token pour user_id {user_id}")

        return {"success": True, "message": "Mot de passe reinitialise avec succes"}

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ============================================================
# NETTOYER LES TOKENS EXPIres (appeler periodiquement)
# ============================================================
@app.post("/api/cleanup-tokens")
async def cleanup_tokens():
    """Nettoie les tokens expirés (peut être appelé par un cron job)"""
    cleanup_expired_tokens()
    return {"success": True, "message": "Tokens expirés supprimés"}


@app.get("/api/debug/brevo")
async def debug_brevo():
    """Vérifier la configuration Brevo"""
    return {
        "brevo_api_key_configured": bool(os.getenv("BREVO_API_KEY")),
        "brevo_email": os.getenv("BREVO_EMAIL"),
        "key_preview": os.getenv("BREVO_API_KEY", "")[:20] + "..." if os.getenv("BREVO_API_KEY") else "None"
    }


@app.get("/api/debug/firebase")
async def debug_firebase():
    """Vérifier la configuration Firebase"""
    return {
        "firebase_configured": bool(os.getenv("FIREBASE_PRIVATE_KEY")),
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    }


# ─────────────────────────────────────────────
# Test Push Notification
# ─────────────────────────────────────────────
@app.post("/api/test-push")
async def test_push(current_user: dict = Depends(get_current_user)):
    """Endpoint de test pour les notifications push"""
    logger.info("=" * 40)
    logger.info("📱 TEST PUSH NOTIFICATION")
    logger.info(f"   User ID: {current_user['id']}")
    logger.info(f"   Username: {current_user['username']}")
    
    result = await send_push_notification(
        user_id=current_user['id'],
        title="🎮 Test Notification",
        body="Ceci est un test de notification push avec l'icône de l'application !",
        data={
            'type': 'test',
            'timestamp': str(datetime.now()),
            'user_id': str(current_user['id'])
        }
    )
    
    logger.info(f"   Result: {result}")
    logger.info("=" * 40)
    
    return {
        "success": result,
        "message": "Notification envoyée avec succès!" if result else "Échec de l'envoi",
        "user_id": current_user['id']
    }
    
# ============================================================
# SQL — À exécuter UNE SEULE FOIS sur Railway
# ALTER TABLE users ADD COLUMN fcm_token VARCHAR(255) NULL;
# CREATE INDEX idx_fcm_token ON users(fcm_token);
# ============================================================
