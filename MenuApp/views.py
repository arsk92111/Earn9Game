
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.shortcuts import redirect, render, get_object_or_404 
from AccountApp.models import db_Profile, Player, Transaction 
from django.contrib.auth.models import User , AnonymousUser  
from django.http import HttpResponse, HttpResponseRedirect  
from Earn9Game.utils_file.api_response import Api_Response
from django.contrib.auth.decorators import login_required      
from rest_framework.permissions import IsAuthenticated  
from rest_framework.views import APIView 
from django.contrib import messages 
from django.template import loader 
from rest_framework import status 
from django.conf import settings  
from django.urls import reverse       
 

@login_required(login_url='login_page')
def wallet_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        obj_player = Player.objects.filter(user =  request.user).first() 
        template = loader.get_template('menu/wallet_page.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request))  

@login_required(login_url='login_page')
def settings_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        obj_player = Player.objects.filter(user =  request.user).first() 
        template = loader.get_template('menu/settings.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request))  

##############################     *******     << API's >>     *******        ##############################

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Transaction
from .easypaisa import initiate_deposit, initiate_withdrawal
import uuid

@login_required
def deposit_funds(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        account_number = request.POST.get('account_number')
        
        # Create transaction record
        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='deposit',
            account_number=account_number
        )
        
        # Initiate Easypaisa deposit
        response = initiate_deposit(
            amount=amount,
            account_number=account_number,
            order_id=str(transaction.id))
        
        if response.get('status') == 'SUCCESS':
            transaction.easypaisa_id = response['transaction_id']
            transaction.status = 'completed'
            transaction.save()
            # Add funds to user's game balance here
            return render(request, 'success.html')
        else:
            transaction.status = 'failed'
            transaction.save()
            return render(request, 'error.html', {'error': response['message']})
    
    return render(request, 'deposit.html')

@login_required
def withdraw_funds(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        account_number = request.POST.get('account_number')
         
        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='withdraw',
            account_number=account_number
        )
        
        response = initiate_withdrawal(
            amount=amount,
            account_number=account_number,
            order_id=str(transaction.id))
        
        if response.get('status') == 'SUCCESS':
            transaction.easypaisa_id = response['transaction_id']
            transaction.status = 'completed'
            transaction.save()
      
            return render(request, 'success.html')
        else:
            transaction.status = 'failed'
            transaction.save()
            return render(request, 'error.html', {'error': response['message']})
    
    return render(request, 'withdraw.html')
