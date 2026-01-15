# app/backends.py
from django.contrib.auth.backends import ModelBackend
from AccountApp.models import db_Profile, Player, Transaction

class PhoneBackend(ModelBackend):
    def authenticate(self, request, db_phone_number=None, email=None, username=None, password=None, **kwargs):
        try:
            if db_phone_number is not None:
                user = db_Profile.objects.get(db_phone_number=db_phone_number)
            elif username is not None:
                user = db_Profile.objects.get(username=username)
            else:
                user = db_Profile.objects.get(email=email)
            if user.check_password(password):
                return user
        except db_Profile.DoesNotExist:
            return None