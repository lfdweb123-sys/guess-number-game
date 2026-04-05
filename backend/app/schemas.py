from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    balance: float
    created_at: datetime

class GameCreate(BaseModel):
    bet_amount: float

class JoinGame(BaseModel):
    game_id: int
    guessed_number: int

class GameResponse(BaseModel):
    id: int
    creator_id: int
    creator_name: Optional[str]
    bet_amount: float
    total_pot: float
    status: str
    winning_number: Optional[int]
    winner_id: Optional[int]
    participants_count: int
    participants: Optional[str]
    created_at: datetime

class MobileMoneyDeposit(BaseModel):
    phone_number: str
    amount: float

class TransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    type: str
    reference: str
    status: str
    created_at: datetime

class WebSocketMessage(BaseModel):
    type: str
    data: dict