from os import times
import requests
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from marshmallow.utils import timestamp

from .models import Transaction
import base64
from datetime import datetime
import json
from django.core.mail import send_mail
from django.core.paginator import Paginator
from .utility import CONSUMER_KEY,CONSUMER_SECRET,BASE_NGROK_URL,BASE_URL,SHORTCODE,PASSKEY,NGROK_URL
# Create your views here.
## CREATING THE MPESA PASSKEY
class MpesaPassword:
    @staticmethod
    def generate_security_credentials():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = SHORTCODE + PASSKEY + timestamp
        online_password = base64.b64encode(data_to_encode.encode()).decode()
        return online_password

# Access token : security credentials provided from daraja mpesa to authorize requests
def generate_access_token():
    auth_url = f'{BASE_URL}/oauth/v1/generate?grant_type=client_credentials'
    response = requests.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    result = response.json().get('access_token')
    print(result)
    return result

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def stk_push(request):
    if request.method == 'POST':
#         capture the form inputs
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')
        name = request.POST.get('name')
        email = request.POST.get('email')
        # create a transaction record
        transaction = Transaction.objects.create(
            phone_number = phone,
            amount = amount,
            status = 'Pending',
            description = "awaiting status result",
            name= name,
            email = email,
        )
#         sending stk push to mpesa via daraja api
        access_token = generate_access_token()
        print(access_token)
        stk_url = f'{BASE_URL}/mpesa/stkpush/v1/processrequest'
        headers = {'Authorization': f'Bearer {access_token}'
                   , 'Content-Type': 'application/json'}
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f'{SHORTCODE}{PASSKEY}{timestamp}'
        .encode()).decode()
        print(stk_url)
        print(password)
        print(timestamp)
        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password" : password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": f"{NGROK_URL}/callback/",
            "AccountReference": f"Transaction_{transaction.id}",
            "TransactionDesc": "Payment Request",
        }
        response = requests.post(stk_url, json=payload,
                                 headers = headers)
        print('response', response)
        response_data = response.json()
        print(response_data)
        #update the transaction with current status frm resp.
        transaction_id = response_data.get(
            'CheckoutRequestId',None)
        transaction.transaction_id = transaction_id
        transaction.description = response_data.get(
            'ResponseDescription',"No Description"
        )
        transaction.save()
        # updating user on process
        return redirect('waiting_page',
                        transaction_id = transaction.id)
    return JsonResponse({'error': "Invalid Request",
                         }, status=400)



def waiting_page(request, transaction_id):
    transaction = Transaction.objects.get(id = transaction_id)
    return render(request, 'waiting.html',
                  {'transaction_id': transaction_id})


### CALLBACK METHOD L: THIS METHOD WILL FETCH OUR RESULTS FOR A TRANSACTION
@csrf_exempt
def callback(request):
    if request.method == 'POST':
        try:
            # load the response from the payment attempt
            data = json.loads(request.body)
            print("received callback data ",data)
            stk_callback = data.get('Body',{}).get('stkCallback',{})
            result_code = stk_callback.get('ResultCode',None)
            result_desc = stk_callback.get('ResultDesc','')
            transaction_id  = stk_callback.get('CheckoutRequestId',None)
            print("callback result")
            print(transaction_id,result_code)
            # we now check the transaction result . i.e. did user pay or not
            if transaction_id:
                transaction = Transaction.objects.get(id = transaction_id)
                print("current transaction in db", transaction)
                if transaction:
                    if result_code == 0:
                        callback_metadata = stk_callback.get('CallbackMetadata',{}
                                                             ).get('Item',[])
                        receipt_number = next((item.get('Value')
                                               for item in callback_metadata
                                               if item.get('Name') == 'MpesaReceiptNumber'),
                                              None)
                        amount = next((item.get('Value') for item in callback_metadata
                                       if item.get('Name') == 'Amount'),None)
                        transaction_date_str = next((item.get('Value')
                                                     for item in callback_metadata
                                                     if item.get('Name') == 'TransactionDate')
                                                    ,None)
                        # cleaning our transaction date
                        transaction_date = None
                        if transaction_date_str:
                            transaction_date = datetime.strptime(str(transaction_date_str),
                                                                 '%Y%m%d%H%M%S')
                        # update our transaction
                        transaction.mpesa_receipt_number = receipt_number
                        transaction.transaction_date = transaction_date
                        transaction.amount = amount
                        transaction.status = 'Success'
                        transaction.description = 'Payment Successful'
                        transaction.save()
                        print(f"transaction update {transaction_id} - {transaction.status}")

                        ### SEND EMAIL TO USER
                        if transaction.email:
                            subject = "Payment Receipt"
                            message = (
                                f"Dear {transaction.name}, \n\n"
                                f"Thank you for your payment {transaction.amount}"
                                f"You confirmation receipt is {transaction.mpesa_receipt_number}"
                            )
                            send_mail(subject,message,"josephbill00@gmail.com",
                                      [transaction.email], fail_silently=False)
                            print("payment receipt received via email")
                    elif result_code == 1:
                        transaction.status = 'Failed'
                        transaction.description = result_desc
                        transaction.save()
                        print(f"transaction failed {transaction_id}")
                    elif result_code == 1032:
                        transaction.status = 'Cancelled'
                        transaction.description = "Cancelled"
                        transaction.save()
                        print(f"transaction cancelled{transaction.transaction_id}")
            return JsonResponse({"message":"Callback received"}
                                ,status=200)

        except Exception as e:
            print(f"Error is from callback{e}")
            return JsonResponse({"error": f"Error is from callback{e}"}
                                , status=500)
    return JsonResponse({"error" : "Invalid request method"},
                        status=400)
### Check status will enable us to track the status of a transaction
def check_status(request, transaction_id):
    # get the transaction needed for status prompt
    transaction = Transaction.objects.filter(id = transaction_id).first()
    if not transaction:
        return JsonResponse({"status": "failed", "message":
            "Transaction not found!"}, status=400)
    '''
    - on stk push method -> transaction status is pending 
    - on successful payment -> transaction status is successful 
    - on failed payment -> transaction status is failed 
    - on cancellation -> transaction status is cancelled 
    '''
    if transaction.status == "Success":
        return JsonResponse({"status": "Success", "message":
                             "Payment Successful"}, status=200)
    elif transaction.status == "Failed":
        return JsonResponse({"status": "Failed", "message":
            "Payment Failed"}, status=200)
    elif transaction.status == "Cancelled":
        return JsonResponse({"status": "Cancelled", "message":
                             "Transaction cancelled"}, status=200)
    else:
        return JsonResponse({"status": "Pending", "message":
                             "Transaction pending"}, status=400)
def payment_success(request):
    return render(request,'payment_success.html')

def payment_failed(request):
    return render(request,'payment_failed.html')

def payment_cancelled(request):
    return render(request,'payment_cancelled.html')



















