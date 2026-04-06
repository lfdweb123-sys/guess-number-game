from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Clé secrète pour JWT (à stocker dans .env)
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# CryptContext pour bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie le mot de passe en tronquant à 72 caractères"""
    try:
        truncated = plain_password[:72]  # bcrypt limite à 72 octets
        return pwd_context.verify(truncated, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash le mot de passe avec bcrypt, tronqué à 72 caractères"""
    try:
        truncated = password[:72]
        return pwd_context.hash(truncated)
    except Exception as e:
        print(f"Password hash error: {e}")
        raise

def create_access_token(data: dict) -> str:
    """Crée un JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    """Décode un JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None