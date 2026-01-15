from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager #, User 
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from datetime import datetime, time, date 
from rest_framework import serializers 
from django.dispatch import receiver 
from email.policy import default
from Earn9Game import settings
from django.db import models 
from random import choices 
from enum import auto
import django   


class db_Profile(AbstractBaseUser, PermissionsMixin):
    objects = UserManager()
    username = models.CharField(_("Username"), max_length=255, unique=True, blank=True, null=True)
    email = models.EmailField(_("Email"), max_length=255, unique=True, blank=True, null=True)
    db_phone_number = models.CharField(_("Phone Number"), max_length=20, unique=True, blank=True, null=True)

    db_fullname = models.CharField(_("Full Name"), max_length=255)  
    db_country_address = models.TextField(_("Country Address"), max_length=255, blank=True)   
    db_photo = models.CharField(_("Image"), max_length=25) 
 
    expired_time_start = models.DateTimeField(_("Expired Time Start"), default=django.utils.timezone.now)
    expired_time_end = models.DateTimeField(_("Expired Time End"), null=True, blank=True)  
    code_pin = models.CharField(_("Code Pin"), max_length=125, blank=True) 
    auth_token = models.CharField(_("Auth Token"), max_length=255) 

    is_staff = models.BooleanField(_("Is Staff"), default=False, null=False)
    is_verified = models.BooleanField(_("Is Verify"), default=False) 
    created_at = models.DateTimeField(_("Created At"), default=django.utils.timezone.now)
    # db_photo = models.ImageField(_("Profile Image"), upload_to="Profile/", width_field=None, height_field=None, max_length=500, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username'] 
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                name='unique_email',
                condition=~models.Q(email='')
            ),
            models.UniqueConstraint(
                fields=['db_phone_number'],
                name='unique_phone',
                condition=~models.Q(db_phone_number='')
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email)
        
        if not self.email and not self.db_phone_number:
            raise serializers.ValidationError(_('Either email or phone number must be provided.'))
 
    def get_full_name(self): 
        return self.db_fullname

    def __str__(self):
        if self.email:
            return self.email
        return self.db_phone_number or str(self.id)


class Player(models.Model):
    user = models.OneToOneField('db_Profile', on_delete=models.CASCADE, related_name='player')
    coins = models.PositiveIntegerField(default=0)
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user.email:
            return self.user.email
        return self.user.db_phone_number or str(self.user.id)

    def deduct_coins(self, amount):
        if self.coins >= amount:
            self.coins -= amount
            self.save()
            return True
        return False

    def add_coins(self, amount):
        self.coins += amount
        self.save()
        
    @receiver(post_save, sender=db_Profile)
    def create_player(sender, instance, created, **kwargs):
        if created:
            Player.objects.create(user=instance, coins=1000)

class Transaction(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)

