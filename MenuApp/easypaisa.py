import os
import hashlib
import requests
from django.conf import settings

EASYPAISA_CONFIG = {
    'STORE_ID': os.getenv('EASYPAISA_STORE_ID'),
    'HASH_KEY': os.getenv('EASYPAISA_HASH_KEY'),
    'BASE_URL': os.getenv('EASYPAISA_BASE_URL'),
}

def generate_hash(*args):
    concatenated = ''.join(str(arg) for arg in args)
    return hashlib.sha256(concatenated.encode()).hexdigest()

# For Deposits (User -> Gaming Platform)
def initiate_deposit(amount, account_number, order_id):
    url = f"{EASYPAISA_CONFIG['BASE_URL']}/api/v2/deposit"
    hash_data = f"{EASYPAISA_CONFIG['STORE_ID']}{amount}{account_number}{order_id}{EASYPAISA_CONFIG['HASH_KEY']}"
    hash_value = generate_hash(hash_data)
    
    payload = {
        "storeId": EASYPAISA_CONFIG['STORE_ID'],
        "amount": amount,
        "mobileNumber": account_number,
        "orderRefNum": order_id,
        "hash": hash_value
    }
    
    response = requests.post(url, json=payload)
    return response.json()

# For Withdrawals (Gaming Platform -> User)
def initiate_withdrawal(amount, account_number, order_id):
    url = f"{EASYPAISA_CONFIG['BASE_URL']}/api/v2/withdraw"
    hash_data = f"{EASYPAISA_CONFIG['STORE_ID']}{amount}{account_number}{order_id}{EASYPAISA_CONFIG['HASH_KEY']}"
    hash_value = generate_hash(hash_data)
    
    payload = {
        "storeId": EASYPAISA_CONFIG['STORE_ID'],
        "amount": amount,
        "mobileNumber": account_number,
        "orderRefNum": order_id,
        "hash": hash_value
    }
    
    response = requests.post(url, json=payload)
    return response.json()