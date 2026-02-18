import requests
import base64
from datetime import datetime
from django.conf import settings
import json

class MpesaAPI:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONFIG.get('CONSUMER_KEY', '')
        self.consumer_secret = settings.MPESA_CONFIG.get('CONSUMER_SECRET', '')
        self.shortcode = settings.MPESA_CONFIG.get('SHORTCODE', '')
        self.passkey = settings.MPESA_CONFIG.get('PASSKEY', '')
        self.callback_url = settings.MPESA_CONFIG.get('CALLBACK_URL', '')
        self.environment = settings.MPESA_CONFIG.get('ENVIRONMENT', 'sandbox')
        
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
        
        self.access_token = None
        self.token_expiry = None
    
    def get_access_token(self):
        """Get OAuth access token from Safaricom API"""
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_auth}'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                self.token_expiry = datetime.now().timestamp() + data['expires_in']
                return self.access_token
            else:
                print(f"Token Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Token Exception: {str(e)}")
            return None
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push payment request"""
        try:
            if not self.access_token or datetime.now().timestamp() >= self.token_expiry:
                if not self.get_access_token():
                    return {'success': False, 'error': 'Failed to get access token'}
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(
                f"{self.shortcode}{self.passkey}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": str(int(amount)),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ResponseCode') == '0':
                    return {
                        'success': True,
                        'response_code': data.get('ResponseCode'),
                        'merchant_request_id': data.get('MerchantRequestID'),
                        'checkout_request_id': data.get('CheckoutRequestID'),
                        'response_description': data.get('ResponseDescription'),
                        'customer_message': data.get('CustomerMessage')
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('ResponseDescription', 'Payment request failed'),
                        'response_code': data.get('ResponseCode')
                    }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'details': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_transaction_status(self, checkout_request_id):
        """Check status of a transaction"""
        try:
            if not self.access_token or datetime.now().timestamp() >= self.token_expiry:
                if not self.get_access_token():
                    return {'success': False, 'error': 'Failed to get access token'}
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(
                f"{self.shortcode}{self.passkey}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'details': response.text
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_callback_data(self, callback_data):
        """Validate M-Pesa callback data"""
        try:
            if not callback_data:
                return False, "Empty callback data"
            
            # Check required fields
            required_fields = ['Body', 'stkCallback']
            for field in required_fields:
                if field not in callback_data:
                    return False, f"Missing required field: {field}"
            
            stk_callback = callback_data['Body']['stkCallback']
            required_callback_fields = ['ResultCode', 'ResultDesc', 'CheckoutRequestID']
            
            for field in required_callback_fields:
                if field not in stk_callback:
                    return False, f"Missing required callback field: {field}"
            
            return True, "Valid callback data"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def parse_callback_result(self, callback_data):
        """Parse callback result and extract payment details"""
        try:
            stk_callback = callback_data['Body']['stkCallback']
            
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            
            # Extract payment details if successful
            mpesa_code = None
            amount = None
            phone_number = None
            
            if result_code == '0':
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        mpesa_code = item.get('Value')
                    elif item.get('Name') == 'Amount':
                        amount = item.get('Value')
                    elif item.get('Name') == 'PhoneNumber':
                        phone_number = item.get('Value')
            
            return {
                'success': result_code == '0',
                'result_code': result_code,
                'result_desc': result_desc,
                'checkout_request_id': checkout_request_id,
                'mpesa_code': mpesa_code,
                'amount': amount,
                'phone_number': phone_number
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Parse error: {str(e)}"
            }