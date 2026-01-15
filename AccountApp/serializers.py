from AccountApp.models import db_Profile, Player, Transaction
from Earn9Game.utils_file.api_response import BaseSerializer 
from django.contrib.auth.hashers import make_password
from rest_framework import serializers  
from django.utils import timezone
import re, random

from Earn9Game.helper_func import (anyNumber , DateTimeExpired, generate_random_name , long_token , validate_password_strength 
                                , send_mail_after_registration, get_authenticated_user) # send_whatsapp_token
 
class RegisterSerializer(BaseSerializer):
    email = serializers.EmailField(required=False)
    username = serializers.EmailField(required=False)
    db_phone_number = serializers.CharField(max_length=20, required=False)
    password = serializers.CharField(write_only=True)

    db_fullname = serializers.CharField(max_length=255, required=False) 
    db_country_address = serializers.CharField(write_only=True, required=False)   
    db_photo = serializers.CharField(write_only=True, required=False)  
    auth_token = serializers.CharField(write_only=True, required=False) 
    code_pin = serializers.CharField(write_only=True, required=False) 
    country_code =  serializers.CharField(write_only=True, required=False) 
    expired_time_end = serializers.DateTimeField(write_only=True, required=False) 
    
    def validate_password(self, value):
        if not value:
            raise serializers.ValidationError("Password is required.")

        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
 
        if not re.search(r'[A-Za-z]', value):
            raise serializers.ValidationError("Password must contain at least one letter.")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def validate(self, attrs):
        email = attrs.get("email")
        db_phone_number = attrs.get("db_phone_number") 
        country_code = attrs.get("country_code") 
        password = attrs.get("password") 

        if not email and not db_phone_number:
            raise serializers.ValidationError("Either email or phone number is required.") 
        if email and db_Profile.objects.filter(email = email).exists():
            raise serializers.ValidationError("Email already exists.") 
        
        country_code = attrs.get("country_code") 
        if db_phone_number: 
            if db_phone_number.startswith('+'): 
                if country_code:
                    raise serializers.ValidationError(
                        "Don't provide country_code if phone number includes international prefix."
                    )
                full_number = db_phone_number
            else: 
                if not country_code:
                    raise serializers.ValidationError(
                        "country_code is required for phone numbers without international prefix."
                    )
                 
                country_code = country_code if country_code.startswith('+') else f'+{country_code}'
                 
                local_number = db_phone_number.lstrip('0')
                full_number = f'{country_code}{local_number}'
 
            if db_Profile.objects.filter(db_phone_number=full_number).exists():
                raise serializers.ValidationError("Phone number already exists.")
             
            attrs['db_phone_number'] = full_number
        attrs['username'] = email
 
        attrs.pop('country_code', None) 
        if attrs.get("email") and db_Profile.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError("Email already exists.")

        validate_password_strength(attrs["password"])
        return attrs

    def create(self, validated_data): 
        if not validated_data.get("db_fullname"):
            validated_data["db_fullname"] = generate_random_name()
            
        if not validated_data.get("db_photo"):
            avatar_number = random.randint(0, 70)
            validated_data["db_photo"] = avatar_number

        otp_code = anyNumber()
        validated_data["auth_token"] = long_token() 
        expiry_time_str = DateTimeExpired()  
        validated_data["expired_time_end"] = expiry_time_str
        validated_data["code_pin"] = otp_code  
        validated_data["password"] = make_password(validated_data["password"])
        return db_Profile.objects.create(**validated_data)

class LoginSerializer(BaseSerializer):
    email = serializers.EmailField(required=False)
    db_phone_number = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("db_phone_number")
        password = attrs.get("password")

        if not email and not phone:
            raise serializers.ValidationError("Email or phone number is required.")

        try:
            if email:
                user = db_Profile.objects.get(email = email)
            else:
                user = db_Profile.objects.get(db_phone_number=phone)
        except db_Profile.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        from django.contrib.auth.hashers import check_password
        if not check_password(password, user.password):
            raise serializers.ValidationError("Your Password is wrong.")

        attrs["user"] = user
        return attrs


class VerifySerializer(BaseSerializer):
    authtoken = serializers.CharField(max_length=255, required=True)
    pin_code = serializers.CharField(max_length=6, required=True) 

    def validate(self, data):
        token = data.get('authtoken')
        pin_code = data.get('pin_code')
        current_time = timezone.now()

        user = db_Profile.objects.filter(auth_token=token).first() 

        if not user:
            raise serializers.ValidationError({"message": "Email / Username is not found."})
        if user.is_verified:
            raise serializers.ValidationError({"message": "Email is already verified."})
        if not user or user.expired_time_end <= current_time:
            raise serializers.ValidationError({"message": "OTP Code time has expired. Please create a new OTP Code."})
        if user.code_pin != pin_code:
            raise serializers.ValidationError({"message": "Please enter a valid OTP Code."})
        return data
    
    def verify_user(self):
        validated_data = self.validated_data
        token = validated_data.get('authtoken') 
        user = db_Profile.objects.filter(auth_token=token).first() 
        if user.is_verified == True:  
            raise serializers.ValidationError({"message": "Your account has been already verified."})
        else:
            user.is_verified = True 
            user.save()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = db_Profile
        fields = ['id', 'email', 'db_phone_number', 'auth_token']
        
class RegenerateCodeSerializer(BaseSerializer):
    auth_token = serializers.CharField(max_length=255, required=True)

    def validate(self, data):
        token = data.get('auth_token') 

        user = db_Profile.objects.filter(auth_token = token).first() 

        if not user:
            raise serializers.ValidationError({"message": "Email / Username is not found."})
        if user.is_verified:
            raise serializers.ValidationError({"message": "Your account has been already verified."})
        return data

    def regenerate_code_user(self):
        validated_data = self.validated_data
        token = validated_data.get('auth_token') 
        user = db_Profile.objects.filter(auth_token=token).first() 

        otp_code = anyNumber()
        expiry_time_str = DateTimeExpired()
        new_token  = long_token()  

        user.auth_token = new_token
        user.expired_time_end = expiry_time_str
        user.code_pin = otp_code
        user.save()
        
        return user


class ChangePasswordSerializer(BaseSerializer):
    oldPassword = serializers.CharField(required=True, max_length=128)
    newPassword1 = serializers.CharField(required=True, max_length=128)
    newPassword2 = serializers.CharField(required=True, max_length=128)

    def validate_newPassword(self, value):
        if not value:
            raise serializers.ValidationError("Password is required.")

        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")

        if not re.search(r'[A-Za-z]', value):
            raise serializers.ValidationError("Password must contain at least one letter.")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def validate(self, attrs):
        if attrs['newPassword1'] != attrs['newPassword2']:
            raise serializers.ValidationError("New Password and Confirm Password did not match.")
        return attrs


class ChangeProfileSerializer(BaseSerializer):
    db_fullname = serializers.CharField(max_length=255, required=True)
  

