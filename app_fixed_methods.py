# This is a fixed version with proper phone number formatting
# You'll need to manually replace the methods in your app.py

# NEW STK_PUSH METHOD:
    def stk_push(self, phone_number, amount, account_reference, description):
        """Initiate STK Push request"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'error': 'Failed to get access token'}, 500
            
            password, timestamp = self.generate_password()
            
            # FIXED: Better phone number formatting
            # Remove any non-digit characters first
            phone_number = ''.join(filter(str.isdigit, phone_number))
            
            # Format phone number for M-Pesa
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                phone_number = phone_number[1:]  # Remove the +
            elif phone_number.startswith('254'):
                phone_number = phone_number  # Already correct
            elif len(phone_number) == 9:
                phone_number = '254' + phone_number  # 712345678 -> 254712345678
            else:
                return {'success': False, 'error': 'Invalid phone number format'}, 400
            
            # Validate phone number length
            if len(phone_number) != 12 or not phone_number.startswith('254'):
                return {'success': False, 'error': 'Phone number must be 12 digits starting with 254'}, 400
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": app.config['MPESA_CALLBACK_URL'],
                "AccountReference": account_reference,
                "TransactionDesc": description
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            app.logger.info(f"M-Pesa STK Push Response: {response_data}")
            
            if response.status_code == 200:
                if 'ResponseCode' in response_data and response_data['ResponseCode'] == '0':
                    return {
                        'success': True,
                        'checkout_request_id': response_data.get('CheckoutRequestID'),
                        'customer_message': response_data.get('CustomerMessage'),
                        'merchant_request_id': response_data.get('MerchantRequestID'),
                        'response_code': response_data.get('ResponseCode')
                    }, 200
                else:
                    error_msg = response_data.get('CustomerMessage', 'Payment request failed')
                    if 'Invalid PhoneNumber' in error_msg:
                        error_msg = 'Invalid phone number format. Please use format: 0712345678 or 254712345678'
                    return {
                        'success': False,
                        'error': error_msg,
                        'response_code': response_data.get('ResponseCode')
                    }, 400
            else:
                error_msg = response_data.get('errorMessage', 'Payment request failed')
                return {
                    'success': False,
                    'error': error_msg
                }, response.status_code
                
        except Exception as e:
            app.logger.error(f"Error in STK Push: {str(e)}")
            return {'success': False, 'error': 'An unexpected error occurred'}, 500

# NEW INITIATE_STK_PUSH FUNCTION:  
def initiate_stk_push(phone_number, amount, order_id, description):
    """Initiate M-Pesa STK Push payment"""
    print(f"?? INITIATING STK PUSH...")
    
    # Debug the request first
    print(f"?? DEBUG: Phone: {phone_number}, Amount: {amount}, Order: {order_id}")
    
    # FIXED: Phone number formatting
    original_phone = phone_number
    phone_number = ''.join(filter(str.isdigit, phone_number))
    
    if phone_number.startswith('0') and len(phone_number) == 10:
        phone_number = '254' + phone_number[1:]
    elif len(phone_number) == 9:
        phone_number = '254' + phone_number
    elif phone_number.startswith('254') and len(phone_number) == 12:
        phone_number = phone_number
    else:
        return None, f"Invalid phone number format: {original_phone} -> {phone_number}"
    
    print(f"?? DEBUG: Formatted Phone: {phone_number}")
    
    access_token = get_mpesa_access_token()
    if not access_token:
        print("? Failed to get access token")
        return None, "Failed to get access token"
    
    print(f"? Access token obtained")
    
    password, timestamp = generate_mpesa_password()
    
    if app.config['MPESA_ENVIRONMENT'] == 'sandbox':
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    else:
        url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    
    payload = {
        "BusinessShortCode": app.config['MPESA_SHORTCODE'],
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": app.config['MPESA_SHORTCODE'],
        "PhoneNumber": phone_number,
        "CallBackURL": app.config['MPESA_CALLBACK_URL'],
        "AccountReference": f"ORDER{order_id}",
        "TransactionDesc": description
    }
    
    print(f"?? Payload: {json.dumps(payload)}")
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        print(f"?? Sending request to M-Pesa...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response_data = response.json()
        
        print(f"?? Response: {json.dumps(response_data)}")
        print(f"?? Status Code: {response.status_code}")
        
        if response.status_code == 200:
            if 'ResponseCode' in response_data and response_data['ResponseCode'] == '0':
                print("? STK Push initiated successfully!")
                payment = MpesaPayment(
                    order_id=order_id,
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    phone_number=phone_number,
                    amount=amount,
                    status='pending'
                )
                db.session.add(payment)
                db.session.commit()
                return response_data, None
            else:
                error_msg = response_data.get('CustomerMessage', 'Payment request failed')
                print(f"? STK Push failed: {error_msg}")
                return None, error_msg
        else:
            error_msg = response_data.get('errorMessage', 'Unknown error')
            print(f"? HTTP Error: {error_msg}")
            return None, error_msg
            
    except Exception as e:
        print(f"?? Exception: {str(e)}")
        return None, str(e)
