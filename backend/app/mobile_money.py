import hashlib
import time
import random
import string
from datetime import datetime
from .database import get_db_connection
import os
import httpx
import asyncio

class MobileMoneyAPI:
    def __init__(self):
        # In production, replace with actual Mobile Money API credentials
        self.api_key = os.getenv('MM_API_KEY', 'test_api_key')
        self.api_secret = os.getenv('MM_API_SECRET', 'test_api_secret')
        self.api_url = os.getenv('MM_API_URL', 'https://api.mobilemoney.com/v1')
        self.is_test_mode = os.getenv('MM_TEST_MODE', 'True') == 'True'
    
    def generate_transaction_id(self):
        timestamp = str(int(time.time()))
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        return hashlib.md5(f"{timestamp}{random_str}".encode()).hexdigest()
    
    async def initiate_deposit(self, user_id: int, phone_number: str, amount: float):
        """Initiate a mobile money deposit"""
        transaction_id = self.generate_transaction_id()
        
        # Store deposit request
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mobile_money_deposits (user_id, phone_number, amount, transaction_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (user_id, phone_number, amount, transaction_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        if self.is_test_mode:
            # Simulate successful deposit in test mode
            await self.simulate_deposit_confirmation(transaction_id, True)
            return {
                'success': True,
                'transaction_id': transaction_id,
                'message': 'Deposit initiated in test mode'
            }
        else:
            # Call actual Mobile Money API
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/deposit",
                        json={
                            'transaction_id': transaction_id,
                            'phone_number': phone_number,
                            'amount': amount,
                            'api_key': self.api_key
                        },
                        headers={'Authorization': f'Bearer {self.api_secret}'}
                    )
                    
                    if response.status_code == 200:
                        return {
                            'success': True,
                            'transaction_id': transaction_id,
                            'message': 'Deposit initiated successfully'
                        }
                    else:
                        return {
                            'success': False,
                            'message': 'Deposit failed'
                        }
            except Exception as e:
                return {
                    'success': False,
                    'message': str(e)
                }
    
    async def simulate_deposit_confirmation(self, transaction_id: str, success: bool):
        """Simulate deposit confirmation (for testing)"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if success:
            # Get deposit details
            cursor.execute("SELECT * FROM mobile_money_deposits WHERE transaction_id = %s", (transaction_id,))
            deposit = cursor.fetchone()
            
            if deposit and deposit['status'] == 'pending':
                # Update deposit status
                cursor.execute("""
                    UPDATE mobile_money_deposits 
                    SET status = 'completed', completed_at = NOW()
                    WHERE transaction_id = %s
                """, (transaction_id,))
                
                # Credit user balance
                cursor.execute("""
                    UPDATE users SET balance = balance + %s WHERE id = %s
                """, (deposit['amount'], deposit['user_id']))
                
                # Record transaction
                cursor.execute("""
                    INSERT INTO transactions (user_id, amount, type, reference, status)
                    VALUES (%s, %s, 'deposit', %s, 'completed')
                """, (deposit['user_id'], deposit['amount'], transaction_id))
                
                conn.commit()
        
        cursor.close()
        conn.close()
    
    async def initiate_withdrawal(self, user_id: int, phone_number: str, amount: float):
        """Initiate a mobile money withdrawal"""
        transaction_id = self.generate_transaction_id()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Vérifier le solde
        cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        current_balance = float(result['balance']) if result else 0
        
        if current_balance < amount:
            cursor.close()
            conn.close()
            return {
                'success': False,
                'message': 'Insufficient balance'
            }
        
        # Enregistrer la demande de retrait
        cursor.execute("""
            INSERT INTO mobile_money_withdrawals (user_id, phone_number, amount, transaction_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (user_id, phone_number, amount, transaction_id))
        conn.commit()
        
        if self.is_test_mode:
            # Simuler un retrait réussi en test
            cursor.close()
            conn.close()
            await self.simulate_withdrawal_confirmation(transaction_id, True)
            return {
                'success': True,
                'transaction_id': transaction_id,
                'message': 'Withdrawal initiated in test mode'
            }
        else:
            # Appel API Mobile Money réel
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/withdraw",
                        json={
                            'transaction_id': transaction_id,
                            'phone_number': phone_number,
                            'amount': amount,
                            'api_key': self.api_key
                        },
                        headers={'Authorization': f'Bearer {self.api_secret}'}
                    )
                    
                    cursor.close()
                    conn.close()
                    
                    if response.status_code == 200:
                        return {
                            'success': True,
                            'transaction_id': transaction_id,
                            'message': 'Withdrawal initiated successfully'
                        }
                    else:
                        return {
                            'success': False,
                            'message': 'Withdrawal failed'
                        }
            except Exception as e:
                cursor.close()
                conn.close()
                return {
                    'success': False,
                    'message': str(e)
                }
    
    async def simulate_withdrawal_confirmation(self, transaction_id: str, success: bool):
        """Simulate withdrawal confirmation (for testing)"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if success:
            cursor.execute("SELECT * FROM mobile_money_withdrawals WHERE transaction_id = %s", (transaction_id,))
            withdrawal = cursor.fetchone()
            
            if withdrawal and withdrawal['status'] == 'pending':
                # Débiter le compte utilisateur
                cursor.execute("""
                    UPDATE users SET balance = balance - %s WHERE id = %s
                """, (withdrawal['amount'], withdrawal['user_id']))
                
                # Mettre à jour le statut du retrait
                cursor.execute("""
                    UPDATE mobile_money_withdrawals 
                    SET status = 'completed', completed_at = NOW()
                    WHERE transaction_id = %s
                """, (transaction_id,))
                
                # Enregistrer la transaction
                cursor.execute("""
                    INSERT INTO transactions (user_id, amount, type, reference, status)
                    VALUES (%s, %s, 'withdrawal', %s, 'completed')
                """, (withdrawal['user_id'], -withdrawal['amount'], transaction_id))
                
                conn.commit()
        
        cursor.close()
        conn.close()
    
    async def check_deposit_status(self, transaction_id: str):
        """Check status of a deposit"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM mobile_money_deposits WHERE transaction_id = %s", (transaction_id,))
        deposit = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if deposit:
            return {
                'status': deposit['status'],
                'amount': float(deposit['amount']),
                'completed_at': deposit['completed_at']
            }
        return None
    
    async def check_withdrawal_status(self, transaction_id: str):
        """Check status of a withdrawal"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM mobile_money_withdrawals WHERE transaction_id = %s", (transaction_id,))
        withdrawal = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if withdrawal:
            return {
                'status': withdrawal['status'],
                'amount': float(withdrawal['amount']),
                'completed_at': withdrawal['completed_at']
            }
        return None

mm_api = MobileMoneyAPI()