from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    id: Optional[int]
    username: str
    balance: float
    created_at: datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Game(BaseModel):
    id: Optional[int]
    creator_id: int
    bet_amount: float
    total_pot: float
    status: str
    winning_number: Optional[int]
    winner_id: Optional[int]
    created_at: datetime

class GameCreate(BaseModel):
    bet_amount: float

class JoinGame(BaseModel):
    game_id: int
    guessed_number: int

class MobileMoneyDeposit(BaseModel):
    phone_number: str
    amount: float