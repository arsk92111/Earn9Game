from requests import Response
from django.http import JsonResponse
from rest_framework.views import exception_handler
from rest_framework import status
from Earn9Game.utils_file.api_response import Api_Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None and response.status_code == 401: 
        return Api_Response.error_response(
                            message="User not found",
                            errors={ "message": "User not found"},
                            status_code=status.HTTP_400_BAD_REQUEST
                        )

    if response is not None:
        if response.status_code == 401:
            if response.data.get('messages'):
                for message in response.data['messages']:
                    if message.get('message') == "Token is invalid or expired":
                        return Api_Response.error_response(
                            message="Token is invalid or expired",
                            errors={ "token": "You'r Passing invalid Token"},
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
    return response
