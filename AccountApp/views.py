 
from rest_framework.decorators import api_view, permission_classes, authentication_classes 
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.hashers import make_password, check_password 
from django.shortcuts import redirect, render, get_object_or_404 
from rest_framework.authentication import SessionAuthentication 
from AccountApp.models import db_Profile, Player, Transaction  
from django.contrib.auth import authenticate, login, logout   
from Earn9Game.utils_file.api_response import Api_Response  
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken 
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator       
from django.contrib.auth.models import AnonymousUser 
from django.contrib.auth.models import User
from django.conf.urls.static import static
from rest_framework.views import APIView
from django.core.mail import send_mail    
from django.contrib import messages  
from django.template import loader 
from rest_framework import status   
from django.conf import settings   
from django.urls import reverse
  
from  Earn9Game.helper_func import ( anyNumber , DateTimeExpired , long_token , validate_password_strength , 
                                send_mail_after_registration, get_authenticated_user,  send_whatsapp_token )

from .serializers import ( RegisterSerializer, LoginSerializer, VerifySerializer, 
            RegenerateCodeSerializer , ChangePasswordSerializer, UserSerializer, ChangeProfileSerializer)
          
def register_page(request): 
    if not request.user.is_authenticated:
        template = loader.get_template('account/register.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('home_page') 

def login_page(request): 
    if not request.user.is_authenticated:
        template = loader.get_template('account/login.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request)) 
    
    else:
        return redirect('home_page') 

def verify_account_page(request):
    template = loader.get_template('account/verify_account.html') 
    context = { 
    }
    return HttpResponse(template.render(context, request)) 


def header(request):
    if not request.user.is_authenticated:
        template = loader.get_template('layout/account/header.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('home_page') 

def footer(request):
    if not request.user.is_authenticated:
        template = loader.get_template('layout/account/footer.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request)) 
    else:
        return redirect('home_page')


    ##############################     *******     << API's >>     *******        ##############################
    
@method_decorator(csrf_exempt, name='dispatch') 
class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save() 
            if user.db_phone_number:
                send_whatsapp_token(user.db_phone_number, user.code_pin) 
                pass
            else:
                send_mail_after_registration(user.email, user.code_pin)
            return Api_Response.success_response(
                "User registered successfully.", 
                data = UserSerializer(user).data )
        return Api_Response.error_response("Validation failed", errors=serializer.errors)

@method_decorator(csrf_exempt, name='dispatch') 
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            if user.is_verified == False:
                return Api_Response.error_response(
                "Your Account Not Verify, Please Verify your Account.",
                errors= {"auth_token": user.auth_token , "verify": False},
                status_code = 403
                )
            password = serializer.validated_data.get('password')   
            if user.email is not None:  
                authenticated_user = authenticate(request, email = user.email, password=password)
            else:  
                authenticated_user = authenticate(request, db_phone_number = user.db_phone_number, password=password)
            if authenticated_user is not None:
                refresh = RefreshToken.for_user(authenticated_user)
                login(request, authenticated_user)
                return Api_Response.success_response("Login successful", data={ 
                    "fullname": user.db_fullname, 
                    "auth_token": user.auth_token,
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                })
        return Api_Response.error_response("Authentication failed", errors=serializer.errors)


@method_decorator(csrf_exempt, name='dispatch')
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated]) 
@authentication_classes([JWTAuthentication]) 
class LogoutView(APIView):
    def post(self, request):
        print("\n ✅  logout start request.user.is_authenticated :",  request.user.is_authenticated)
        try:
            refresh_token = request.data.get('refresh_token')
            
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
              
            request.session.clear()
            request.session.flush()
            logout(request) 
            request.user = AnonymousUser()  

            return Api_Response.success_response(
                "Logout successful", 
                data={"detail": "Successfully logged out"}
            )

        except Exception as e:
            return Api_Response.error_response(
                "Logout failed",
                errors=str(e),
                status_code=400
            )

@method_decorator(csrf_exempt, name='dispatch') 
class VerifyView(APIView):  
    def post(self, request, authtoken):
        data = request.data
        data['authtoken'] = authtoken 

        serializer = VerifySerializer(data=data)
        if not serializer.is_valid():
            return Api_Response.error_response(
                "Validation error occurred.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = serializer.verify_user()
            return Api_Response.success_response(
                message="User verification successful.",
                data=response,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return Api_Response.error_response(
                "An unexpected error occurred during user verification.",
                errors={"details": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch') 
class Regenerate_codeView(APIView):
    def post(self, request, auth_token):
        data = request.data
        data['auth_token'] = auth_token

        serializer = RegenerateCodeSerializer(data = data)
        if not serializer.is_valid():
            return Api_Response.error_response(
                "Validation error occurred.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try: 
            user = serializer.regenerate_code_user() 
            if user.db_phone_number:
                send_whatsapp_token(user.db_phone_number, user.code_pin) 
                pass
            else:
                send_mail_after_registration(user.email, user.code_pin)
            return Api_Response.success_response(
                message="Code has been regenerated successfully.",
                data = UserSerializer(user).data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return Api_Response.error_response(
                "An unexpected error occurred during regenerate code.",
                errors={"details": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch') 
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, authtoken):
        user = request.user
        if not user:
            return Api_Response.error_response(
                "User not authenticated.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        obj_user = db_Profile.objects.filter(auth_token = authtoken).first()
        if obj_user is None:
            return Api_Response.error_response(
                "Email or Username not found.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not obj_user.is_verified: 
            return Api_Response.error_response(
                "Your account is not verified. Please verify your account.",
                errors={"auth_token": obj_user.auth_token if obj_user else None},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Api_Response.error_response(
                "Validation err0rs occured.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        old_password = serializer.validated_data['oldPassword']
        new_password1 = serializer.validated_data['newPassword1']

        if not check_password(old_password, obj_user.password):
            return Api_Response.error_response(
                "Your old password is incorrect.",
                errors = {"message" : "Your old password is incorrect." },
                status_code=status.HTTP_400_BAD_REQUEST
            ) 
        try:
            obj_user.set_password(new_password1)
            obj_user.save()
            return Api_Response.success_response(
                message="New password created successfully.",
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            # logger.error(f"Error changing password: {e}")
            return Api_Response.error_response(
                "An error occurred while changing the password.",
                errors={"details": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch') 
class ChangeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user 
        if not user:
            return Api_Response.error_response(
                "User not authenticated.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
 
        profile = db_Profile.objects.filter(db_phone_number=user).first()
        if profile is None:
            return Api_Response.error_response(
                "Profile not found.",  # Updated message
                status_code=status.HTTP_404_NOT_FOUND
            )
 
        serializer = ChangeProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Api_Response.error_response(
                "Validation errors occurred.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:   
            profile.db_fullname = serializer.validated_data['db_fullname']
            profile.save()  # Save the profile object

            return Api_Response.success_response(
                message="Profile updated successfully.",  # Updated message
                data = UserSerializer(user).data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e: 
            return Api_Response.error_response(
                "An error occurred while updating the profile.",
                errors={"details": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


 