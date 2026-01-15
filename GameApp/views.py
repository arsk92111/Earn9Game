from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view, permission_classes 
from django.shortcuts import redirect, render, get_object_or_404 
from rest_framework.authentication import TokenAuthentication   
from AccountApp.models import db_Profile ,Player, Transaction 
from rest_framework.decorators import authentication_classes
from django.contrib.auth import authenticate, login, logout
from Earn9Game.utils_file.api_response import Api_Response   
from django.http import HttpResponse, HttpResponseRedirect  
from django.contrib.auth.decorators import login_required 
from rest_framework_simplejwt.tokens import RefreshToken   
from rest_framework.permissions import IsAuthenticated 
from django.views.decorators.http import require_POST   
from django.views.decorators.csrf import csrf_exempt    
from django.utils.decorators import method_decorator 
from rest_framework.response import Response 
from django.contrib.auth.models import User  
from django.conf.urls.static import static  
from rest_framework.views import APIView 
from django.core.mail import send_mail
from django.http import JsonResponse 
import json, uuid, random, datetime 
from django.contrib import messages   
from django.template import loader  
from django.db import transaction 
from rest_framework import status  
from django.utils import timezone
from django.conf import settings 
from django.http import response     
from django.urls import reverse  
from django.db.models import Q 
from datetime import timedelta 
from datetime import datetime    
from random import shuffle        

from  Earn9Game.helper_func  import ( anyNumber , DateTimeExpired , long_token , validate_password_strength ,
                                    send_mail_after_registration, get_authenticated_user )
 
from GameApp.models import Game, PlayerResult , GameRound,  ConnectDotGame, FootballGame, Game, PlayerBid
from .serializers import GameRoundSerializer, PlayerBidSerializer, PlayerSerializer, GameSerializer, PlayerResultSerializer  
 
@login_required(login_url='login_page')
def home_page(request):
    if request.user.is_authenticated:
        template = loader.get_template('Earn9/home.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('login_page')

@login_required(login_url='login_page')
def card_game_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        template = loader.get_template('Earn9/card_game.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request))  

@login_required(login_url='login_page')
def GuessNumber_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        template = loader.get_template('Earn9/guess_Number_page.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request))  

@login_required(login_url='login_page')
def colorTrade_game_page(request):
    if request.user.is_authenticated:
        obj_player = Player.objects.filter(user =  request.user).first()
        print("obj_player :", obj_player.user.auth_token)
        template = loader.get_template('Earn9/colorTrade_game.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('login_page')


@login_required(login_url='login_page')
def crashRocket_game_page(request):
    if request.user.is_authenticated:
        obj_player = Player.objects.filter(user =  request.user).first()
        print("obj_player :", obj_player.user.auth_token)
        template = loader.get_template('Earn9/crashRocket_game.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('login_page')


@login_required(login_url='login_page')
def spinWheel_game_page(request):
    if request.user.is_authenticated:
        obj_player = Player.objects.filter(user =  request.user).first()
        print("obj_player :", obj_player.user.auth_token)
        template = loader.get_template('Earn9/spinWheel_game.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request)) 
         
    else:
        return redirect('login_page')


@login_required(login_url='login_page')
def football_bit_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        user_profile = request.user
        create_me = timezone.now() - timedelta(minutes=2)
        game = FootballGame.objects.filter( Q(player_a=user_profile) | Q(player_b=user_profile),
            status="active", created_at__gte = create_me).first()
        if game:
            return redirect('football_playLand', game_id=game.id)
        template = loader.get_template('Earn9/football_bit_page.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request))  

@login_required(login_url='login_page')
def football_playLand_page(request, game_id):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        user_profile = request.user
        if game_id is not None:
            try:
                game = FootballGame.objects.get(id = game_id)
                if( game.player_a == user_profile or game.player_b == user_profile) and game.status == "active":
                    template = loader.get_template('Earn9/football_playLand_page.html') 
                    context = {
                        "player": request.user
                    }
                    return HttpResponse(template.render(context, request))
                else:
                    return redirect('football_bit')
            except FootballGame.DoesNotExist:
                return redirect('football_bit')
        else:
            return redirect('football_bit')

@login_required(login_url='login_page')
def connectDot_bit_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        user_profile = request.user
        create_me = timezone.now() - timedelta(minutes=3)
        game = ConnectDotGame.objects.filter( Q(player_a=user_profile) | Q(player_b=user_profile),
            status="active", created_at__gte = create_me).first()
        if game:
            return redirect('connectDot_play_page', game_id=game.id)
        
        template = loader.get_template('Earn9/connectDot_bit_page.html') 
        context = { 
        }
        return HttpResponse(template.render(context, request))  


@login_required(login_url='login_page')
def connectDot_play_page(request, game_id):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        user_profile = request.user
        if game_id is not None:
            try:
                game = ConnectDotGame.objects.get(id = game_id)
                if( game.player_a == user_profile or game.player_b == user_profile) and game.status == "active":
                    template = loader.get_template('Earn9/connectDot_play_page.html') 
                    context = {
                        "player": request.user,
                        "game": game
                    }
                    return HttpResponse(template.render(context, request))
                else:
                    return redirect('connectDot_bit_page')
            except ConnectDotGame.DoesNotExist:
                return redirect('connectDot_bit_page')
        else:
            return redirect('connectDot_bit_page')

@login_required(login_url='login_page')
def diceRoll_game_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    else:
        obj_player = Player.objects.filter(user =  request.user).first()
        print("obj_player :", obj_player.user.auth_token)
        template = loader.get_template('Earn9/dice_roll_game.html') 
        context = { 
            'obj_player' : obj_player
        }
        return HttpResponse(template.render(context, request))  

##############################     *******     << API's >>     *******        ##############################

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
def deduct_coins(request):
    try:
        player = request.user.player
        amount = request.data.get('amount')
        
        if player.coins < amount:
            return Response({"error": "Insufficient balance"}, status=400)
            
        player.coins -= amount
        player.save()
        
        return Response({
            "new_balance": player.coins,
            "transaction_id": uuid.uuid4()
        })
        
    except Exception as e:
        return Response({"error": str(e)}, status=500)
     
def is_picture(card):
    return card[0] in ['J', 'Q', 'K', 'A']

def card_image_path(card):
    return f"/static/cards/{card}.png"
  
def get_deck():
    suits = ['hearts', 'diamonds', 'clubs', 'spades']
    # values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
    values = ['2', '4', '6', '8', '10', 'jack', 'queen', 'king', 'ace']
    return [f"{value}_of_{suit}" for suit in suits for value in values]

@transaction.atomic 
def calculate_winners(round_obj):
    if round_obj.status != GameRound.RoundStatus.ACTIVE:
        return [], 'None'
    
    if PlayerResult.objects.filter(round=round_obj).exists():
        print("⚠️ Already processed round.")
        return [], 'None'

    card_value = round_obj.card.split('_')[0].lower()
    is_picture = card_value in ['jack', 'queen', 'king', 'ace']
    win_side = 'PIC' if is_picture else 'NUM'

    bids = PlayerBid.objects.filter(round=round_obj).select_related('player')
    total_pool = sum(b.amount for b in bids)
    winners = bids.filter(side=win_side)

    results = []
    existing_users = set()
    # processed_bids = set()

    if winners.exists(): 
        developer_fee = round(total_pool * 0.10)
        prize_pool = total_pool - developer_fee
 
        max_payouts = []
        total_desired_payout = 0
        for w in winners:
            max_win = round(w.amount * 1.95)
            max_payouts.append((w, max_win))
            total_desired_payout += max_win
 
        if total_desired_payout <= prize_pool:
            scaling_factor = 1.0
        else:
            scaling_factor = prize_pool / total_desired_payout
 
        for bid, max_win in max_payouts:
            try:
                actual_payout = round(max_win * scaling_factor)
                actual_payout += bid.amount
                
                with transaction.atomic():
                    bid.player.coins += actual_payout
                    bid.player.save() 

                    PlayerResult.objects.update_or_create(
                        player=bid.player,
                        round=round_obj,
                        result_type = "WIN",
                        defaults={
                            'amount_won_loss': actual_payout,
                            'amount_bet': bid.amount
                        }
                    ) 
                    
                username = bid.player.user.username or bid.player.user.db_phone_number or bid.player.user.email or str(bid.player.user.id)
                results.append({
                    "username": username,
                    "side": 'Picture' if bid.side == 'PIC' else 'Number',
                    "amount": bid.amount,
                    "won": True,
                    "payout": actual_payout
                })
                existing_users.add(username)

            except Exception as e:
                print(f"Error processing winner {bid.player}: {str(e)}")
 
    all_bids = PlayerBid.objects.filter(round=round_obj)
    for bid in all_bids:
        username = bid.player.user.username or bid.player.user.db_phone_number or bid.player.user.email or str(bid.player.user.id)
        if username not in existing_users: 
            with transaction.atomic():
                PlayerResult.objects.update_or_create(
                        player=bid.player,
                        round=round_obj,
                        result_type = "LOSS",
                        defaults={
                            'amount_won_loss': bid.amount,
                            'amount_bet': bid.amount
                        }
                )
            # processed_bids.add(bid.id)

            results.append({
                "username": username,
                "side": 'Picture' if bid.side == 'PIC' else 'Number',
                "amount": bid.amount,
                "won": False,
                "payout": 0
            })
            existing_users.add(username)

    round_obj.status = GameRound.RoundStatus.COMPLETED
    round_obj.save()

    sorted_results = sorted(
        results,
        key=lambda x: (-x['payout'], x['username'])
    )

    return sorted_results, 'Picture' if win_side == 'PIC' else 'Number'

class AuthenticatedPlayerDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            player = Player.objects.select_related('user').get(user=request.user)
            player_data = PlayerSerializer(player).data

            bids = player.bids.select_related('round').order_by('-created_at')
            results = player.playerresult_set.select_related('round').order_by('-created_at')

            player_data['bids'] = PlayerBidSerializer(bids, many=True).data
            player_data['results'] = PlayerResultSerializer(results, many=True).data

            return Api_Response.success_response("Authenticated player data fetched.", player_data)
        except Player.DoesNotExist:
            return Api_Response.error_response("Authenticated player not found.")
        except Exception as e:
            return Api_Response.error_response("Something went wrong.", str(e))

class CurrentRoundView(APIView):
    def get(self, request):
        try:
            game = Game.objects.select_related('current_round').order_by('-updated_at').first()
            if not game:
                return Api_Response.error_response("No game found.")
            serialized = GameSerializer(game)
            return Api_Response.success_response("Current round fetched successfully.", serialized.data)
        except Exception as e:
            return Api_Response.error_response("Failed to fetch current round.", str(e))

class PlayerBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            player = Player.objects.get(user=request.user)
            return Api_Response.success_response("Player balance fetched.", {"coins": player.coins})
        except Player.DoesNotExist:
            return Api_Response.error_response("Player not found.")
 
class LeaderboardView(APIView):
    def get(self, request):
        try:
            players = Player.objects.select_related('user').order_by('-coins')[:10]
            serialized = PlayerSerializer(players, many=True)
            return Api_Response.success_response("Leaderboard retrieved successfully.", serialized.data)
        except Exception as e:
            return Api_Response.error_response("Failed to fetch leaderboard.", str(e))

class AllPlayersWithDetailsView(APIView):
    def get(self, request):
        try:
            players = Player.objects.select_related('user').prefetch_related(
                'bids__round',
                'playerresult_set__round',
            )
            data = []
            for player in players:
                player_data = PlayerSerializer(player).data
                player_data['bids'] = PlayerBidSerializer(player.bids.all(), many=True).data
                player_data['results'] = PlayerResultSerializer(player.playerresult_set.all(), many=True).data
                data.append(player_data)

            return Api_Response.success_response("All player data fetched.", data)
        except Exception as e:
            return Api_Response.error_response("Error fetching player details.", str(e))

class CurrentCardView(APIView):
    def get(self, request):
        try:
            game = Game.objects.select_related('current_round').first()
            if not game or not game.current_round:
                return Api_Response.error_response("No active round")
            
            serializer = GameRoundSerializer(game.current_round)
            return Api_Response.success_response(
                "Current card details fetched", 
                {
                    **serializer.data,
                    'image_url': f"/static/cards/{serializer.data['card']}.png",
                    'formatted_name': serializer.data['card'].replace('_', ' ').title()
                }
            )
        except Exception as e:
            return Api_Response.error_response(str(e))

class RoundResultsView(APIView):
    def get(self, request, round_id):
        try:
            round_obj = GameRound.objects.get(id=round_id)
            results, _ = calculate_winners(round_obj)
            return Api_Response.success_response("Round results", results)
        except Exception as e:
            return Api_Response.error_response(str(e))
 

 
@transaction.atomic  
@csrf_exempt
@require_POST
def place_bid(request):
    try:
        data = json.loads(request.body)
        user = request.user
        round_id = data.get('round_id')
        
        if not user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
            
        if not round_id:
            return JsonResponse({'error': 'Missing round_id'}, status=400)
            
        try:
            round_obj = GameRound.objects.get(id=round_id, status=GameRound.RoundStatus.ACTIVE)
            player = Player.objects.get(user=user)
        except GameRound.DoesNotExist:
            return JsonResponse({'error': 'Invalid round'}, status=400)
        except Player.DoesNotExist:
            return JsonResponse({'error': 'Player not found'}, status=400)

        # Rest of bid logic...
        return JsonResponse({'success': True, 'coins': player.coins})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

 