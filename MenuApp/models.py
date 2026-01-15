from django.db import models
# from django.contrib.auth.models import User
from AccountApp.models import db_Profile, Player, Transaction

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdrawal')
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    )
    
    userTransaction = models.ForeignKey(db_Profile, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    easypaisa_id = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    account_number = models.CharField(max_length=15)  

    
    def __str__(self):
        return str(self.id) + " | " +  str(self.userTransaction.db_phone_number) + " | " +  str(self.transaction_type)
 