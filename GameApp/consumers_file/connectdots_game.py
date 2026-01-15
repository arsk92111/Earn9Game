#consumers.py  
from channels.db import database_sync_to_async  
from GameApp.models import ConnectDotResult, ConnectDotRound, ConnectDotGame 
from AccountApp.models import db_Profile ,Player, Transaction
import asyncio, json, time, datetime , logging 
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import  IntegrityError  
from datetime import timedelta 
from django.db.models import Q  
from django.utils import timezone as django_timezone
from datetime import datetime as dt, timezone 
from django.utils import timezone  
from datetime import datetime, timedelta, timezone as dt_timezone 
from django.db import transaction
logger = logging.getLogger(__name__)  

class ConnectDotBitConsumer(AsyncJsonWebsocketConsumer):  
    room_name = "bid_room"
    
    async def connect(self):
        try:
            await self.accept() 
            if not await self.authenticate_user():
                return  
            
            await self.channel_layer.group_add(
                self.room_name, 
                self.channel_name
            )

        except Exception as e:
            await self.handle_connection_error(e)
 
    async def handle_connection_error(self, error):  
        try: 
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Failed to initialize game connection'
            }))
        except Exception as send_error:
            print(f"Error sending failure message: {send_error}")
        finally: 
            await self.close(code=4001)
        
    async def authenticate_user(self): 
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.handle_connection_error("Anonymous access denied")
            return False
        
        try:
            self.db_profile = await self.get_db_profile()
            self.player = await self.get_player()
            return True
        except Player.DoesNotExist:
            await self.handle_connection_error("Player record missing")
            return False

    @database_sync_to_async
    def get_db_profile(self):
        try:
            return db_Profile.objects.get(auth_token=self.user.auth_token)
        except db_Profile.DoesNotExist: 
            return False

    @database_sync_to_async
    def get_player(self):
        return Player.objects.get(user=self.db_profile)
    
    async def receive_json(self, content):
        action = content.get('action')
        if action == 'confirm_bet':
            await self.handle_confirm_bet(content)
        elif action == 'reconnect':
            await self.handle_reconnect()

    async def handle_confirm_bet(self, content):
        amount = content['amount']
        if not await self.check_balance(amount):
            return

        await self.deduct_balance(amount)
        
        existing_game = await self.find_existing_game(amount)
        if existing_game:
            await self.pair_players(existing_game, amount)
        else:
            game = await self.create_new_game(amount)
            asyncio.create_task(
                self.check_game_expiration(game.id, amount)
            ) 
            await self.channel_layer.group_add(
                f"game_{game.id}",
                self.channel_name
            )
            await self.send_json({
                'type': 'waiting', 
                'game_id': game.id
            })
              
    async def check_game_expiration(self, game_id, amount): 
        await asyncio.sleep(180)  # 3 minutes
        
        expired = await self.handle_expired_game_safe(game_id, amount)
        if expired:
            await self.notify_game_expired(game_id)

    async def handle_expired_game_safe(self, game_id, amount): 
        return await self._handle_expired_game(game_id, amount)
    
    @database_sync_to_async
    def _handle_expired_game(self, game_id, amount): 
        try:
            game = ConnectDotGame.objects.get(id=game_id) 
            if game.status == 'waiting' and not game.player_b:  
                self.player.coins += amount
                self.player.save()
                game.delete()
                return True
            return False
        except ConnectDotGame.DoesNotExist:
            return False

    async def notify_game_expired(self, game_id): 
        await self.channel_layer.group_send(
            f"game_{game_id}",
            {
                'type': 'game.expired',
                'message': 'Game expired. Amount refunded.'
            }
        ) 
        await self.channel_layer.group_discard(
            f"game_{game_id}",
            self.channel_name
        ) 

    async def game_expired(self, event): 
        await self.send_json({
            'type': 'game_expired',
            'message': event['message']
        })
        await self.close(code=4003)


    @database_sync_to_async
    def refund_player(self, player_id, amount): 
        player = Player.objects.get(id=player_id)
        player.coins += amount
        player.save()

    @database_sync_to_async
    def get_game_by_id(self, game_id): 
        try:
            return ConnectDotGame.objects.get(id=game_id)
        except ConnectDotGame.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_game(self, game_id): 
        ConnectDotGame.objects.filter(id=game_id).delete()
 
    
    async def handle_reconnect(self):
        game = await self.get_pending_game()
        if game:
            # Check expiration first
            if game.created_at < timezone.now() - timedelta(minutes=3):
                await self.refund_expired_game_safe(game.id)
                await self.send_json({
                    'type': 'session_expired',
                    'message': 'Game expired. Amount refunded.'
                })
                return
            
            # Re-add to game group and send waiting status
            await self.add_to_game_group(game.id)
            await self.send_json({
                'type': 'waiting', 
                'game_id': game.id
            })
        else:
            # No pending game found
            await self.send_json({'type': 'session_clear'})
    

    async def handle_reconnect_expiration(self, game): 
        if game.created_at < timezone.now() - timedelta(minutes=3): 
            await self.refund_expired_game_safe(game.id)
            await self.send_json({
                'type': 'session_expired',
                'message': 'Game expired. Amount refunded.'
            })
            return True
        return False
    
    @database_sync_to_async
    def refund_expired_game_safe(self, game_id): 
        try:
            game = ConnectDotGame.objects.get(id=game_id)
            if game.status == 'waiting' and not game.player_b: 
                self.player.coins += game.player_a_bet_amount
                self.player.save()
                game.delete()
                return True
            return False
        except ConnectDotGame.DoesNotExist:
            return False

    @database_sync_to_async
    def check_balance(self, amount):
        return self.player.coins >= amount

    @database_sync_to_async
    def deduct_balance(self, amount):
        self.player.coins -= amount
        self.player.save()
    
    @database_sync_to_async
    def refund_balance(self, amount):
        self.player.coins += amount
        self.player.save()

    @database_sync_to_async
    def cleanup_expired_games(self, amount):
        expired = timezone.now() - timedelta(minutes=3)
        self.refund_balance(amount)
        ConnectDotGame.objects.filter(
            player_a_bet_amount=amount,
            created_at__lte=expired,
            player_b__isnull=True
        ).delete()
 
    @database_sync_to_async
    def find_existing_game(self, amount):
        min_amount = max(0, amount - 300)  # Prevent negative amounts
        max_amount = amount + 300
        
        return ConnectDotGame.objects.filter(
            player_a_bet_amount__range=(min_amount, max_amount),  # Range filter
            player_b__isnull=True,
            created_at__gte=timezone.now()-timedelta(minutes=3)
        ).exclude(player_a=self.db_profile).order_by('created_at').first()
 
    async def pair_players(self, game, amount): 
        await self.update_game_details(game, amount)
        await self.channel_layer.group_add(
            f"game_{game.id}",
            game.player_a_channel
        )
        await self.channel_layer.group_add(
            f"game_{game.id}",
            self.channel_name
        )
        await self.channel_layer.group_send(
            f"game_{game.id}",
            {'type': 'game.start', 'game_id': str(game.id), 'redirect': True}
        )

    @database_sync_to_async
    def update_game_details(self, game, amount):
        """Sync method for database operations"""
        game.player_b = self.db_profile
        game.player_b_bet_amount = amount
        game.player_b_channel = self.channel_name
        game.status = 'active'
        game.save(update_fields=[
            'player_b', 'player_b_bet_amount',
            'player_b_channel', 'status'
        ])
 
    @database_sync_to_async
    def get_player_channel(self, player):
        return ConnectDotGame.objects.filter(
            player_a=player,
            id=self.game.id
        ).values_list('channel_name', flat=True).first()

    @database_sync_to_async
    def create_new_game(self, amount):
        return ConnectDotGame.objects.create(
            player_a=self.db_profile,
            player_a_bet_amount=amount,
            player_a_channel=self.channel_name,
            status='waiting'
        )
  
    @database_sync_to_async
    def get_pending_game(self):
        return ConnectDotGame.objects.filter(
            Q(player_a=self.db_profile) |
            Q(player_b=self.db_profile),
            status='waiting',
            created_at__gte=timezone.now()-timedelta(minutes=3)
        ).first()

    @database_sync_to_async
    def finalize_game(self, game_id): 
        game = ConnectDotGame.objects.get(id=game_id)
        game.status = 'active'
        game.save(update_fields=['status'])

    async def game_start(self, event):
        if event.get('redirect'): 
            await self.finalize_game(event['game_id'])
            await self.send_json({
                'type': 'redirect',
                'game_id': event['game_id']
            })
            await self.close()
    
    async def add_to_game_group(self, game_id):
        await self.channel_layer.group_add(
            f"game_{game_id}",
            self.channel_name
        )


class ConnectDotPlayConsumer(AsyncJsonWebsocketConsumer):    
    GAME_DURATION = 120 
    TURN_DURATION = 5  
    
    result_duration = 5  
    game_group = "connectDot_session" 
    timer_task = None
    timer_tasks = {} 
    _timer_lock = asyncio.Lock() 

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.user = self.scope["user"]
        await self.accept() 

        if not await self.authenticate_user():
            await self.close(code=4001)
            return

        try:
            self.game = await self.get_game()
            self.db_profile = await self.get_db_profile()
            self.player = await self.get_player()
        except Exception as e:
            await self.close()
            return
        
        is_player_a = str(self.db_profile.auth_token) == str(self.game.player_a.auth_token)
        
        await self.send_json({
            'type': 'player_assignment',
            'is_player_a': is_player_a
        })


        try:
            self.game = await self.get_game()
            self.db_profile = await self.get_db_profile()
            self.player = await self.get_player()
        except Exception as e:
            await self.close()
            return
 
        self.game_group = f"game_{self.game_id}"
        await self.channel_layer.group_add(self.game_group, self.channel_name) 
        
        self.current_round = await self.get_current_round()
        if not self.current_round:
            self.current_round = await self.get_or_create_round()
            if not self.current_round:
                await self.close()
                return 
        
        if not self.current_round or not await self.get_current_player(self.current_round):
            await self.close(code=4005)
            return
        
        await self.send_initial_state() 
        if self.game_id not in ConnectDotPlayConsumer.timer_tasks:
            task = asyncio.create_task(self.game_timer())
            ConnectDotPlayConsumer.timer_tasks[self.game_id] = task
     
    async def player_assignment(self, event):
        await self.send_json({
            'type': 'player_assignment',
            'is_player_a': event['is_player_a']
        })

        
    async def game_timer(self):
        try:
            while True:
                current_round = await self.get_current_round()
                if not current_round or current_round.timer_remaining <= 0:
                    break
                    
                await asyncio.sleep(1)
                
                async with self._timer_lock:
                    current_round = await self.get_current_round()
                    if not current_round:
                        break
                    
                    await self.update_timers(current_round)
                    await self.broadcast_timer_update(current_round)
                    
                    if current_round.turn_time_remaining <= 0:
                        await self.handle_turn_timeout(current_round)
                    
                    if current_round.timer_remaining <= 0:
                        await self.end_game()
                        break
        finally:
            if self.game_id in ConnectDotPlayConsumer.timer_tasks:
                del ConnectDotPlayConsumer.timer_tasks[self.game_id]

    async def handle_turn_timeout(self, current_round): 
        await self.shift_turn(current_round)
        await self.broadcast_turn_shifted()


    async def handle_connection_error(self, error):  
        try: 
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Failed to initialize game connection'
            }))
        except Exception as send_error:
            print(f"Error sending failure message: {send_error}")
        finally: 
            await self.close(code=4001)
        
    async def authenticate_user(self): 
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.handle_connection_error("Anonymous access denied")
            return False
        
        try:
            self.db_profile = await self.get_db_profile()
            self.player = await self.get_player()
            return True
        except Player.DoesNotExist:
            await self.handle_connection_error("Player record missing")
            return False

    @database_sync_to_async
    def get_db_profile(self):
        try:
            return db_Profile.objects.get(auth_token=self.user.auth_token)
        except db_Profile.DoesNotExist: 
            return False

    @database_sync_to_async
    def get_player(self):
        try:
            return Player.objects.select_related('user').get(user=self.db_profile)
        except Player.DoesNotExist:
            return None
            
    @database_sync_to_async
    def get_game(self):
        return ConnectDotGame.objects.select_related('player_a', 'player_b').get(id=self.game_id)
    
    @database_sync_to_async
    def is_player_in_game(self):
        return self.game.player_a == self.db_profile or self.game.player_b == self.db_profile

    @database_sync_to_async
    def get_current_player(self, round_obj):
        try:
            if round_obj.current_player:
                return round_obj.current_player.auth_token
            return None   
        except AttributeError:
            return None
        
    @database_sync_to_async
    def get_or_create_round(self):
        try:
            return ConnectDotRound.objects.select_related('current_player').get(game_id=self.game_id)
        except ConnectDotRound.DoesNotExist:
            # Create new round with player details
            player_a_detail = {
                "player_id": str(self.game.player_a.auth_token)  if self.game.player_a else None,
                'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
                'ended_at': '',
                'score': 0,
                'is_turn_done': False,
                'btn_clicked': []
            }
            
            player_b_detail = {
                "player_id": str(self.game.player_b.auth_token) if self.game.player_b else None,
                'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
                'ended_at': '',
                'score': 0,
                'is_turn_done': False,
                'btn_clicked': []
            }
            
            current_round = ConnectDotRound.objects.create(
                game=self.game,
                round_status='PLAYER_A_TURN',
                player_a_detail=player_a_detail,
                player_b_detail=player_b_detail,
                current_player=self.game.player_a,
                timer_remaining=self.GAME_DURATION,
                turn_time_remaining=self.TURN_DURATION
            )
            return current_round

    async def send_initial_state(self):
        is_player_a = str(self.db_profile.auth_token) == str(self.game.player_a.auth_token)
        
        await self.send_json({
            'type': 'game_state',
            'grid_state': await self.get_grid_state(),
            'current_player': str(self.current_round.current_player.auth_token),
            'timer': self.current_round.timer_remaining,
            'turn_timer': self.current_round.turn_time_remaining,
            'player_color': 'green' if is_player_a else 'red',
            'is_player_a': is_player_a,
            'player_a_id': str(self.game.player_a.auth_token),  # Add explicit IDs
            'player_b_id': str(self.game.player_b.auth_token)
        })
   
    async def get_grid_state(self):
        grid = [0] * 49  # Changed from 42 to 49 (7x7)
        for btn in self.current_round.player_a_detail['btn_clicked']:
            if 0 < btn <= 49:  # Updated to 49
                grid[btn-1] = 1
        for btn in self.current_round.player_b_detail['btn_clicked']:
            if 0 < btn <= 49:  # Updated to 49
                grid[btn-1] = 2
        return grid
 
    async def broadcast_timer_update(self, current_round):
        await self.channel_layer.group_send(self.game_group, {
            'type': 'timer_update',
            'timer': current_round.timer_remaining,
            'turn_timer': current_round.turn_time_remaining
        })

    async def timer_update(self, event):
        await self.send_json({
            'type': 'timer_update',
            'timer': event['timer'],
            'turn_timer': event['turn_timer']
        })

    @database_sync_to_async 
    def get_current_round(self):
        try:
            return ConnectDotRound.objects.select_related('current_player').get(game_id=self.game_id)
        except ConnectDotRound.DoesNotExist:
            return None

    @database_sync_to_async
    def update_timers_sync(self, current_round): 
        current_round.timer_remaining = max(0, current_round.timer_remaining - 1)
        current_round.turn_time_remaining = max(0, current_round.turn_time_remaining - 1)
        current_round.save()

    async def update_timers(self, round):
        await self.update_timers_sync(round)

    async def shift_turn_sync(self, current_round):
        if current_round.round_status == 'PLAYER_A_TURN':
            current_round.round_status = 'PLAYER_B_TURN'
            current_round.current_player = self.game.player_b
            current_round.player_a_detail['is_turn_done'] = True
            current_round.player_b_detail['is_turn_done'] = False
        else:
            current_round.round_status = 'PLAYER_A_TURN'
            current_round.current_player = self.game.player_a
            current_round.player_b_detail['is_turn_done'] = True
            current_round.player_a_detail['is_turn_done'] = False
            
        current_round.turn_time_remaining = self.TURN_DURATION
        current_round.save()
        await self.broadcast_turn_shifted()
 
    @database_sync_to_async
    def shift_turn(self, current_round):
        if current_round.round_status == 'PLAYER_A_TURN':
            current_round.round_status = 'PLAYER_B_TURN'
            current_round.current_player = self.game.player_b
            current_round.player_a_detail['is_turn_done'] = True
            current_round.player_b_detail['is_turn_done'] = False
        else:
            current_round.round_status = 'PLAYER_A_TURN'
            current_round.current_player = self.game.player_a
            current_round.player_a_detail['is_turn_done'] = False
            current_round.player_b_detail['is_turn_done'] = True
        
        # Reset turn timer to full duration
        current_round.turn_time_remaining = self.TURN_DURATION
        current_round.save()

    async def end_game(self):
        current_round = await self.get_current_round()
        if not current_round:
            return 
        await self.mark_game_expired() 
        result_data = await self.create_result(current_round)
         
        await self.channel_layer.group_send(self.game_group, {
            'type': 'game.result',
            'result': result_data
        })

    @database_sync_to_async
    def mark_game_expired(self):
        self.game.status = 'expired'
        self.game.save()

    
    @database_sync_to_async
    def create_result(self, current_round): 
        if ConnectDotResult.objects.filter(round=current_round).exists():
            return {'result_type': {}, 'scores': {}, 'bits': {}}
         
        total_a = current_round.player_a_detail.get('score', 0)
        total_b = current_round.player_b_detail.get('score', 0)
        amount_A = self.game.player_a_bet_amount
        amount_B = self.game.player_b_bet_amount 
        winner_a = winner_b = loser_a = loser_b = None
        win_draw_a = win_draw_b = loss_draw_a = loss_draw_b = None
         
        if total_a > total_b:
            winner_a = Player.objects.filter(user=self.game.player_a).first()
            loser_b = Player.objects.filter(user=self.game.player_b).first()
            total_amount = self.amount_A_Winner_Calculate(amount_A, amount_B)
        elif total_b > total_a:
            winner_b = Player.objects.filter(user=self.game.player_b).first()
            loser_a = Player.objects.filter(user=self.game.player_a).first()
            total_amount = self.amount_B_Winner_Calculate(amount_A, amount_B)
        elif total_a == total_b and total_a > 0:
            win_draw_a = Player.objects.filter(user=self.game.player_a).first()
            win_draw_b = Player.objects.filter(user=self.game.player_b).first()
        else:
            loss_draw_a = Player.objects.filter(user=self.game.player_a).first()
            loss_draw_b = Player.objects.filter(user=self.game.player_b).first()
         
        if winner_a:
            self.create_result_record(winner_a, current_round, total_amount, 'win')
            self.create_result_record(loser_b, current_round, amount_B, 'loss')
        elif winner_b:
            self.create_result_record(winner_b, current_round, total_amount, 'win')
            self.create_result_record(loser_a, current_round, amount_A, 'loss')
        elif win_draw_a and win_draw_b:
            self.create_result_record(win_draw_a, current_round, amount_A, 'win_draw')
            self.create_result_record(win_draw_b, current_round, amount_B, 'win_draw')
        else:
            self.create_result_record(loss_draw_a, current_round, amount_A, 'loss_draw')
            self.create_result_record(loss_draw_b, current_round, amount_B, 'loss_draw')
        
        if winner_a:
            return {
                'result_type': {
                    'winner_a': self.get_player_auth_token(winner_a),
                    'loser_b': self.get_player_auth_token(loser_b),
                    'prize': total_amount
                },
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            }
        elif winner_b:
            return {
                'result_type': {
                    'loser_a': self.get_player_auth_token(loser_a),
                    'winner_b': self.get_player_auth_token(winner_b),
                    'prize': total_amount
                },
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            }
        elif win_draw_a and win_draw_b:
            return {
                'result_type': {
                    'win_draw_a': self.get_player_auth_token(win_draw_a),
                    'win_draw_b': self.get_player_auth_token(win_draw_b)
                },
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            }
        else:
            return {
                'result_type': {
                    'loss_draw_a': self.get_player_auth_token(loss_draw_a),
                    'loss_draw_b': self.get_player_auth_token(loss_draw_b)
                },
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            }

    def create_result_record(self, player, round, amount, result_type):
        ConnectDotResult.objects.create(
            player=player,
            round=round,
            amount_won_loss=amount,
            result_type=result_type
        )
        # Update player coins
        player.coins += amount
        player.save()

    def amount_A_Winner_Calculate(self, amount_A, amount_B):
        if amount_A > amount_B:
            return (amount_B * 0.90) + amount_A
        else:
            return (amount_A * 0.90) + amount_A

    def amount_B_Winner_Calculate(self, amount_A, amount_B):
        if amount_B > amount_A:
            return (amount_A * 0.90) + amount_B
        else:
            return (amount_B * 0.90) + amount_B

    def get_player_auth_token(self, player):
        return player.user.auth_token if player else None

    @database_sync_to_async
    def mark_game_expired(self):
        self.game.status = 'expired'
        self.game.save()

    async def game_result(self, event):
        await self.send_json({
            'type': 'game.result',
            'result': event['result']
        })

    async def receive_json(self, content):
        action = content.get('action')
        
        if action == 'make_move':
            await self.handle_move(content['button'])
        elif action == 'sync_state':
            await self.send_initial_state()

    
    async def handle_move(self, button):  
        self.current_round = await self.get_current_round()
        if not self.current_round:
            return
            
        if not await self.validate_move(button):
            return
            
        await self.save_move(button)
        
        if not await self.check_win_condition():
            async with self._timer_lock: 
                self.current_round = await self.get_current_round()
                if self.current_round:
                    await self.shift_turn(self.current_round)
                    await self.broadcast_turn_shifted()
                    
        await self.broadcast_move(button)
    
 
    @database_sync_to_async
    def save_move(self, button): 
        user_token = str(self.user.auth_token)
        player_a_token = str(self.game.player_a.auth_token)
        
        if user_token == player_a_token:
            self.current_round.player_a_detail['btn_clicked'].append(button)
        else:
            self.current_round.player_b_detail['btn_clicked'].append(button)
        self.current_round.save()

    async def check_win_condition(self):
        grid = await self.get_grid_state()
        user_token = str(self.user.auth_token)
        player_a_token = str(self.game.player_a.auth_token)
        player_mark = 1 if user_token == player_a_token else 2
        
        if await self.check_win(grid, player_mark):
            await self.update_score(self.user)
            await self.declare_winner(self.user)
            return True
        return False

    @database_sync_to_async
    def update_score(self, player):
        if player.id == self.game.player_a.id:
            self.current_round.player_a_detail['score'] += 1
        else:
            self.current_round.player_b_detail['score'] += 1
        self.current_round.save()

    async def check_win(self, grid, player): 
        grid_2d = [grid[i*7:(i+1)*7] for i in range(7)]  # Changed from 6 to 7 rows
        return (await self.check_horizontal(grid_2d, player) or
            (await self.check_vertical(grid_2d, player)) or
            (await self.check_diagonal(grid_2d, player)))

    async def check_horizontal(self, grid, player):
        for row in range(7):  # Updated to 7 rows
            for col in range(3):  # 7-5+1 = 3
                if all(grid[row][col+i] == player for i in range(5)):  # Changed from 4 to 5
                    return True
        return False

    async def check_vertical(self, grid, player):
        for row in range(3):  # 7-5+1 = 3
            for col in range(7):
                if all(grid[row+i][col] == player for i in range(5)):  # Changed from 4 to 5
                    return True
        return False

    async def check_diagonal(self, grid, player):  
        # Check diagonals (top-left to bottom-right)
        for row in range(3):  # 7-5+1 = 3
            for col in range(3):  # 7-5+1 = 3
                if all(grid[row+i][col+i] == player for i in range(5)):  # Changed from 4 to 5
                    return True
                    
        # Check diagonals (top-right to bottom-left)
        for row in range(3):  # 7-5+1 = 3
            for col in range(4, 7):  # Start from column 4 to 6
                if all(grid[row+i][col-i] == player for i in range(5)):  # Changed from 4 to 5
                    return True
        return False
 
    @database_sync_to_async
    def validate_move(self, button):  
        current_player_token = str(self.current_round.current_player.auth_token)
        user_token = str(self.user.auth_token)
        
        if current_player_token != user_token:
            print(f"Not player's turn: current={current_player_token}, user={user_token}")
            return False
        
        if not (1 <= button <= 49):  # Updated to 49
            return False
        # if not (1 <= button <= 42):
        #     return False
            
        all_moves = (
            self.current_round.player_a_detail['btn_clicked'] + 
            self.current_round.player_b_detail['btn_clicked']
        )
        return button not in all_moves

        
    async def declare_winner(self, winner): 
        await self.end_game()
    
    async def turn_shifted(self, event): 
        await self.send_json({
            'type': 'turn_shifted',
            'new_turn': event['new_turn'],
            'turn_timer': event['turn_timer']
        })

    async def broadcast_turn_shifted(self): 
        current_round = await self.get_current_round()
        if not current_round:
            return
            
        await self.channel_layer.group_send(self.game_group, {
            'type': 'turn_shifted',
            'new_turn': str(current_round.current_player.auth_token),
            'turn_timer': current_round.turn_time_remaining  # Current value, not initial duration
        })

    @database_sync_to_async
    def shift_turn_after_move(self): 
        self.current_round = ConnectDotRound.objects.get(id=self.current_round.id)
        
        if self.current_round.round_status == 'PLAYER_A_TURN':
            self.current_round.round_status = 'PLAYER_B_TURN'
            self.current_round.current_player = self.game.player_b
        else:
            self.current_round.round_status = 'PLAYER_A_TURN'
            self.current_round.current_player = self.game.player_a
        
        # Reset turn timer
        self.current_round.turn_time_remaining = self.TURN_DURATION
        
        # Update player status
        if self.current_round.round_status == 'PLAYER_A_TURN':
            self.current_round.player_a_detail['is_turn_done'] = False
            self.current_round.player_b_detail['is_turn_done'] = True
        else:
            self.current_round.player_a_detail['is_turn_done'] = True
            self.current_round.player_b_detail['is_turn_done'] = False
            
        self.current_round.save()

     
    async def broadcast_move(self, button): 
        is_player_a = self.user.id == self.game.player_a.id
        await self.channel_layer.group_send(self.game_group, {
            'type': 'move_made',
            'player_id': str(self.db_profile.auth_token),  # Use auth_token for identification
            'is_player_a': is_player_a,  # Add player identification
            'button': button,
            'new_turn': str(self.current_round.current_player.auth_token),
            'turn_timer': self.current_round.turn_time_remaining
        })


    async def move_made(self, event):
        await self.send_json({
            'type': 'move_made',
            'player_id': event['player_id'],  # Changed from 'player'
            'is_player_a': event['is_player_a'],
            'button': event['button'],
            'new_turn': event['new_turn'],
            'turn_timer': event['turn_timer']
        })

        