from django.http import JsonResponse
from django.template.loader import render_to_string
import  uuid, random,  string, smtplib, logging, jwt,  turtle , time   
from django.core.mail import send_mail
from django.utils.html import strip_tags 
from rest_framework.response import Response
from Earn9Game import settings    
from AccountApp.models import db_Profile
from django.utils import timezone
from datetime import timedelta   
from rest_framework import serializers
from django.conf import settings  
from datetime import datetime  

import pywhatkit as kit  
# from tkinter import *   
from twilio.rest import Client

logger = logging.getLogger(__name__)
  
 
def send_whatsapp_token(to_number, otp_code): 
    t = time.localtime(time.time())
    hor = t.tm_hour
    mint = t.tm_min
    new_min = mint + 1

    message = f'\n\t\t\t Welcome To *Earn9Game* \n\n\n You\'r verification code is *{otp_code}*'
    kit.sendwhatmsg( to_number, message, 
        hor, new_min, 10
    )

    return
    # url = f"https://wa.me/{to_number[1:]}?text={message}"

 

# def send_verification_sms(phone_number, code):
#     verification_code = random.randint(100000, 999999)
#     client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
#     message_body = f"Your password reset verification code is: {code}"

#     try:
#         message = client.messages.create(
#             body=message_body,
#             from_=settings.TWILIO_PHONE_NUMBER,
#             to=str(phone_number)
#         )
#         print(f"SMS successfully sent to {phone_number}. SID: {message.sid}")
#         return verification_code
#     except Exception as e:
#         print(f"Failed to send SMS: {e}")
#         return False


# def send_whatsapp_token_twilio(to_number, otp_code): 
#     account_sid = settings.TWILIO_ACCOUNT_SID
#     auth_token_twilio = settings.TWILIO_AUTH_TOKEN
#     from_whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
#     to_whatsapp_number = f'whatsapp:{to_number}'
#     client = Client(account_sid, auth_token_twilio)

#     try:
#         message = client.messages.create(
#             body=f"Your verify OTP code are: {otp_code}",
#             from_=from_whatsapp_number,
#             to=to_whatsapp_number
#         )
#         return {"status": "sent", "sid": message.sid}
#     except Exception as e:
#         return {"status": "failed", "error": str(e)} 


def generate_random_name():
    length = random.randint(4, 7)
    name = ''.join(random.choices(string.ascii_lowercase, k=length))
    return name.capitalize()

def anyNumber():
    number = random.randint(000000, 999999)
    return number

def  DateTimeExpired():
    date = timezone.now()
    expiry_time = date + timedelta(minutes=15)
    date_time_expired = expiry_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    return date_time_expired

def long_token_by_username(var_username):
    date = timezone.now()
    datefix = date.strftime('%Y%m%d%b%H%M%S%f') 
    auth_token = str(datefix) + "-" + str(var_username) + "-" + str(uuid.uuid4())
    return auth_token

def long_token():
    date = timezone.now()
    datefix = date.strftime('%Y%m%d%b%H%M%S%f') 
    auth_token = str(datefix) + "-" + str(uuid.uuid4())
    return auth_token

def validate_password_strength(password):
    if len(password) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in password):
        raise serializers.ValidationError("Password must contain at least one digit.")
    if not any(char.isalpha() for char in password):
        raise serializers.ValidationError("Password must contain at least one letter.")
 
def get_authenticated_user(request):
        """Custom method to retrieve the user from JWT if session-based user is not valid."""
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return None

        token = auth.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            if user_id is None:
                return None
            print("user_id ::- " + str(user_id))
            return db_Profile.objects.get(id=user_id)
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired.")
            return None
        except jwt.InvalidTokenError:
            logger.warning("JWT token is invalid.")
            return None
        except db_Profile.DoesNotExist:
            logger.warning("User not found for the provided token.")
            return None


def send_mail_after_registration(email, code):
    subject = 'One Time Password'
    email_from = settings.EMAIL_HOST_USER  # From sender
    recipient_list = [email]

    obj_user = db_Profile.objects.filter(email = email).first()
    if not obj_user:
        print("Error: User not found for email:", email)
        return False   

    # name = f"{obj_user.db_fullname}"
    context = {'email': email, 'code': code, 'name': email}

    template_name = "SendEmail.html"
    convert_to_html_content = render_to_string(template_name, context)
    plain_message = strip_tags(convert_to_html_content)

    try:
        you_send_it = send_mail(
            subject=subject,
            message=plain_message,
            from_email=email_from,
            recipient_list=recipient_list,
            html_message=convert_to_html_content,
            fail_silently=False 
        )

        if you_send_it:
            print(f"Email successfully sent to {email}")
            return True
        else:
            print("Email failed to send")
            return False

    except smtplib.SMTPException as e:
        print(f"SMTP error occurred: {e}")
        logging.error(f"SMTP Error: {e}")
        return False

    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        logging.error(f"General Error: {e}")
        return False

