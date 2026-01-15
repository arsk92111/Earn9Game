from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

class Api_Response(APIView):
    @staticmethod
    def success_response(message, data=None, status_code=status.HTTP_200_OK):
        return Response(
            {
                "status": "success",
                "message": message,
                "data": data if data else {},
                "status_code": status_code
            },
            status=status_code
        )

    @staticmethod
    def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        # Ensure "errors" follows the desired format
        formatted_errors = errors if isinstance(errors, dict) else {"message": str(errors)}
        return Response(
            {
                "status": "error",
                "message": message,
                "errors": formatted_errors,
                "status_code": status_code
            },
            status=status_code
        )

class BaseSerializer(serializers.Serializer):
    def run_validation(self, data=...):
        try:
            return super().run_validation(data)
        except ValidationError as exc:
            errors = self.format_errors(exc.detail)
            raise ValidationError(errors)

    @staticmethod
    def format_errors(errors):
        formatted_errors = {"message": ""}  # Initialize with a single string
        for field, error_list in errors.items():
            if isinstance(error_list, list):
                formatted_errors["message"] = " ".join(error_list)  # Combine all errors into one string
            else:
                formatted_errors["message"] = error_list
        return formatted_errors
 