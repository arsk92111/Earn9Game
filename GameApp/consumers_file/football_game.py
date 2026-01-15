#consumers.py  
from channels.db import database_sync_to_async  
from GameApp.models import FootballGame, FootballRound, FootBallResult, default_player_detail 
from AccountApp.models import db_Profile, Player, Transaction
from asgiref.sync import sync_to_async  
import asyncio, json, time, datetime , logging 
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import  IntegrityError  
from datetime import timedelta 
from django.db.models import Q  
from django.utils import timezone as django_timezone
from datetime import datetime as dt, timezone 
from django.utils import timezone  
from datetime import datetime, timedelta, timezone as dt_timezone
logger = logging.getLogger(__name__)  


class FootBallBitConsumer(AsyncJsonWebsocketConsumer):   
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
            game = FootballGame.objects.get(id=game_id) 
            if game.status == 'waiting' and not game.player_b:  
                self.player.coins += amount
                self.player.save()
                game.delete()
                return True
            return False
        except FootballGame.DoesNotExist:
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
            return FootballGame.objects.get(id=game_id)
        except FootballGame.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_game(self, game_id): 
        FootballGame.objects.filter(id=game_id).delete()
 
    
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
            game = FootballGame.objects.get(id=game_id)
            if game.status == 'waiting' and not game.player_b: 
                self.player.coins += game.player_a_bet_amount
                self.player.save()
                game.delete()
                return True
            return False
        except FootballGame.DoesNotExist:
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
        FootballGame.objects.filter(
            player_a_bet_amount=amount,
            created_at__lte=expired,
            player_b__isnull=True
        ).delete()


    @database_sync_to_async
    def find_existing_game(self, amount):
        min_amount = max(0, amount - 300)  # Prevent negative amounts
        max_amount = amount + 300
        
        return FootballGame.objects.filter(
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
        return FootballGame.objects.filter(
            player_a=player,
            id=self.game.id
        ).values_list('channel_name', flat=True).first()

    @database_sync_to_async
    def create_new_game(self, amount):
        return FootballGame.objects.create(
            player_a=self.db_profile,
            player_a_bet_amount=amount,
            player_a_channel=self.channel_name,
            status='waiting'
        )
  
    @database_sync_to_async
    def get_pending_game(self):
        return FootballGame.objects.filter(
            Q(player_a=self.db_profile) |
            Q(player_b=self.db_profile),
            status='waiting',
            created_at__gte=timezone.now()-timedelta(minutes=3)
        ).first()

    @database_sync_to_async
    def finalize_game(self, game_id): 
        game = FootballGame.objects.get(id=game_id)
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


class FootBallPlayLandConsumer(AsyncJsonWebsocketConsumer): 
    round_duration = 25
    result_duration = 5  
    game_group = "football_session"

    _timer_task = None
    _timer_lock = asyncio.Lock() 

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        await self.accept() 

        if not await self.authenticate_user():
            await self.close(code=4001)
            return

        try:
            self.game = await self.get_game()
            if not await self.is_player_in_game():
                await self.close(code=4001)
                return
        except FootballGame.DoesNotExist:
            await self.close(code=4004)
            return

        self.game_group_name = f"game_{self.game_id}"
        await self.channel_layer.group_add(
            self.game_group_name,
            self.channel_name
        )
 
        current_round = await self.get_current_round()
        if current_round:
            await self.schedule_timer_task(current_round)
        if not current_round:
            current_round = await self.create_new_round()
            if not current_round:
                await self.close(code=4004)
                return

        if not current_round or not await self.get_current_player(current_round):
            await self.close(code=4005)
            return

        await self.send_json({
            'type': 'initial_state',
            'timer': await self.calculate_remaining_time(current_round),
            'current_turn': await self.get_current_player(current_round),
            'scores': {  
                    'round_status' : current_round.round_status,
                    'a': await self.get_player_a_score(current_round), 
                    'a_power': current_round.player_a_detail.get('power', 0.0),
                    'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                    'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                    'player_a_auth_token': await self.get_current_player_data_a(current_round), 

                    'b': await self.get_player_b_score(current_round),  
                    'b_power': current_round.player_b_detail.get('power', 0.0),
                    'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                    'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                    'player_b_auth_token': await self.get_current_player_data_b(current_round)
            },
            'keeper_state': current_round.player_a_detail.get('keeper_state', 'standing')
        })
          
    async def receive_json(self, content):
        action = content.get('action')
        if action == 'get_state':
            current_round = await self.get_current_round()
            if current_round:
                await self.send_json({
                    'type': 'initial_state',
                    'timer': await self.calculate_remaining_time(current_round),
                    'current_turn': await self.get_current_player(current_round),
                    'scores': {
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
                    },
                    'keeper_state': current_round.player_a_detail.get('keeper_state', 'standing')
                })
        if action == 'kick':
            await self.handle_kick(content) 
        elif action == 'sync':
            await self.send_game_state() 
     
    async def authenticate_user(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            return False
        try:
            self.db_profile = await sync_to_async(db_Profile.objects.get)(auth_token=self.user.auth_token)
            return True
        except db_Profile.DoesNotExist:
            return False

    @database_sync_to_async
    def get_game(self):
        return FootballGame.objects.select_related('player_a', 'player_b').get(id=self.game_id)

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
        
    async def send_game_state(self, current_round):
        await self.send_json({
            'type': 'game_state',
            'scores': { 
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
            },
            'current_turn': 'A' if current_round.round_status == 'PLAYER_A_TURN' else 'B'
        })

    async def send_current_state(self):
        current_round = await self.get_current_round()
        if not current_round:
            return

        state = {  
            'type': 'game_state',  
            'current_player_id': await self.get_current_player(current_round),
            'scores': {
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
            },
            'timer_remaining': await self.calculate_remaining_time(current_round),
        }
        await self.send_json(state)

    @database_sync_to_async
    def get_player_a_score(self, current_round):
        return current_round.player_a_detail.get('score', 0)

    @database_sync_to_async 
    def get_player_b_score(self, current_round):
        return current_round.player_b_detail.get('score', 0)
     
    @database_sync_to_async
    def get_player_a(self):
        return self.game.player_a

    @database_sync_to_async
    def get_player_b(self):
        return self.game.player_b

    @database_sync_to_async
    def get_current_round(self):
        try:
            return FootballRound.objects.filter(game=self.game).latest('created_at')
        except FootballRound.DoesNotExist:
            return None

    async def calculate_remaining_time(self, current_round):
        try:
            if current_round.round_status in ['PLAYER_A_TURN', 'PLAYER_B_TURN']:
                detail = current_round.player_a_detail if current_round.round_status == 'PLAYER_A_TURN' else current_round.player_b_detail
                started_at_str = detail.get('started_at')
                if not started_at_str:
                    return self.round_duration
                
                started_at = datetime.strptime(started_at_str, "%d/%m/%YT%H:%M:%S") 
                now = timezone.now()
                elapsed = (now - started_at).total_seconds()
                remaining = max(0, self.round_duration - elapsed)
                return int(remaining)
            else:
                return 0
        except Exception as e:
            print(f"Time calculation error: {str(e)}")
            return self.round_duration
                
    async def send_game_state(self):
        current_round = await self.get_current_round()
        if not current_round:
            return

        try:
            timer_value = await self.calculate_remaining_time(current_round) 
            timer_value = int(timer_value)
        except (ValueError, TypeError):
            timer_value = 25 
            
        state = {
            'type': 'game_state',
            'scores': { 
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
            },
            'current_turn': await self.get_current_player_id(current_round),
            'timer': timer_value,
            'keeper_state': current_round.player_a_detail.get('keeper_state', 'standing')
        }
        await self.send_json(state)

    async def handle_kick(self, content):
        try:
            current_round = await self.get_current_round()
            if not current_round:
                await self.send_json({'type': 'error', 'message': 'Game round not ready'})
                return

            current_player = await self.get_current_player(current_round)
            if current_player != self.db_profile.auth_token:
                await self.send_json({'type': 'error', 'message': "It's not your turn"})
                return

            try:
                vertical = float(content.get('vertical', 0))
                horizontal = float(content.get('horizontal', 0))
                power = float(content.get('power', 0))
                goalMe =  content.get('goalMe', False)  
                et = 440 - ((0.8 + vertical) / 1.8 * power * 440 + 0.3 * power * (abs(0.5 - horizontal) / 0.5) * 440)
                el = 405 + power * (horizontal - 0.5) * 810

            except (KeyError, ValueError, TypeError):
                await self.send_json({
                    'type': 'error',
                    'message': 'Invalid kick parameters: must be numbers'
                })
                return

            kick_data = {
                'vertical': vertical,
                'horizontal': horizontal,
                'power': power,
                'ball_x': el, 
                'ball_y': et,  
                'is_turn_done': True,
                'is_goalMe': goalMe
            }

            if await self.is_db_profile_player_a():
                current_round.player_a_detail.update(kick_data)
            else:
                current_round.player_b_detail.update(kick_data)

            await self.save_kick_data(current_round)
            await self.process_kick_result(current_round) 
            await self.broadcast_update()
            async with self._timer_lock:
                if self._timer_task:
                    self._timer_task.cancel()
                    self._timer_task = None
                
        except Exception as e:
            print(f"Error handling kick: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': 'Internal server error'
            })
            
    @database_sync_to_async
    def is_db_profile_player_a(self):
        return self.db_profile == self.game.player_a
    
    @database_sync_to_async
    def is_db_profile_player_b(self):
        return self.db_profile == self.game.player_b
    
    @database_sync_to_async
    def create_new_round(self):
        try:
            game = FootballGame.objects.select_related('player_a', 'player_b').get(id=self.game.id)
            new_round = FootballRound.objects.create(
                game=game,
                round_status='PLAYER_A_TURN',
                current_player=game.player_a
            )
            
            new_round.player_a_detail = default_player_detail(game.player_a.auth_token)
            new_round.player_a_detail['started_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
            
            if game.player_b:
                new_round.player_b_detail = default_player_detail(game.player_b.auth_token)
                new_round.player_b_detail['started_at'] = '' 
            else:
                new_round.player_b_detail = default_player_detail()
            
            new_round.save()
            return new_round
        except Exception as e:
            print(f"Round creation failed: {str(e)}")
            return None

    async def handle_expired_turn(self, current_round):
        try:
            if current_round.round_status == 'PLAYER_A_TURN': 
                current_round.player_a_detail['ended_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
                current_round.round_status = 'PLAYER_B_TURN'
                current_round.current_player = self.game.player_b
                current_round.player_b_detail['started_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
                await self.schedule_timer_task(current_round)
                
            elif current_round.round_status == 'PLAYER_B_TURN':
                current_round.player_b_detail['ended_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
                current_round.round_status = 'RESULT' 
                
            await database_sync_to_async(current_round.save)()
            await self.broadcast_update() 

            if current_round.round_status == 'RESULT':
                result_data = await self.create_result(current_round) 
                await self.channel_layer.group_send(
                    self.game_group_name,
                    {
                        'type': 'game.result',
                        'result': {
                            'result_type': result_data['result_type'], 
                            'scores': result_data['scores'],
                            'bits': result_data['bits']
                        }
                    }
                )
                await self.broadcast_update()
                
        except Exception as e:
            print(f"Error handling expired turn: {str(e)}")
            raise e
        
    @database_sync_to_async
    def save_kick_data(self, current_round): 
        current_round.save(update_fields=['player_a_detail', 'player_b_detail'])
 
    @database_sync_to_async
    def get_current_player_id(self, current_round):
        return current_round.current_player.auth_token if current_round.current_player else None

    @database_sync_to_async
    def is_player_a(self, current_round):
        return current_round.current_player == current_round.game.player_a
 
    async def schedule_timer_task(self, current_round):
        async with self._timer_lock:
            if self._timer_task:
                self._timer_task.cancel()
            
            remaining = await self.calculate_remaining_time(current_round)
            if remaining > 0:
                self._timer_task = asyncio.create_task(
                    self.handle_timer_expiration(current_round, remaining)
                )

    async def handle_timer_expiration(self, current_round, delay):
        try:
            await asyncio.sleep(delay)
            await self.handle_expired_turn(current_round)
        except asyncio.CancelledError:
            pass
        finally:
            async with self._timer_lock:
                self._timer_task = None
    
    async def process_kick_result(self, current_round):
        try:     
            is_goal = await self.calculate_goal(current_round) 
            game = await database_sync_to_async(lambda: self.game)() 
            
            if await self.is_db_profile_player_a():
                current_round.player_a_detail['score'] = 1 if is_goal else 0
                player_detail = current_round.player_a_detail
                opponent_detail = current_round.player_b_detail
            else: 
                current_round.player_b_detail['score'] = 1 if is_goal else 0
                player_detail = current_round.player_b_detail
                opponent_detail = current_round.player_a_detail
             
            current_time = timezone.now()
            player_detail['ended_at'] = current_time.strftime("%d/%m/%YT%H:%M:%S")
            
            opponent_start = current_time + timedelta(seconds=1)
            opponent_detail['started_at'] = opponent_start.strftime("%d/%m/%YT%H:%M:%S")
                    
            if current_round.round_status == 'PLAYER_A_TURN':
                if game.player_b:
                    next_status = 'PLAYER_B_TURN'
                    new_player = await self.get_player_b()
                    current_round.player_b_detail.update({
                        'is_turn_done': False,
                        'vertical': 0.0,
                        'horizontal': 0.0,
                        'power': 0.00
                    })
                else:
                    next_status = 'RESULT'
                    new_player = current_round.current_player  # Keep existing player
            else:
                next_status = 'RESULT'
                new_player = current_round.current_player 
            
            
            await self.switch_turns(current_round) 
            await self.schedule_timer_task(current_round)

            await database_sync_to_async(setattr)(current_round, 'current_player', new_player)
            try:
                await database_sync_to_async(current_round.save)()
            except IntegrityError as e: 
                await self.send_json({
                    'type': 'error',
                    'message': 'Game state corrupted - please start new game'
                })
                return
                
            if next_status == 'RESULT':
                result_data = await self.create_result(current_round) 
                await self.channel_layer.group_send(
                    self.game_group_name,
                    {
                        'type': 'game.result',
                        'result': {
                            'result_type': result_data['result_type'], 
                            'scores': result_data['scores'],
                            'bits': result_data['bits']
                        }
                    }
                )

            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game.update',
                    'scores': {
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
                    },
                    'current_turn': await self.get_current_player_id(current_round),
                    'round_status': current_round.round_status,
                    'timer': await self.calculate_remaining_time(current_round),
                    'ended_at': player_detail['ended_at'],
                    'next_start': opponent_detail['started_at']
                }
            )
            
        except Exception as e:
            print(f"Error processing kick result: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to process kick result'
            })

    @database_sync_to_async
    def calculate_goal(self, current_round):
        game = current_round.game
        current_player = current_round.current_player
        is_player_a = (current_player == game.player_a)

        if is_player_a:
            kicker_detail = current_round.player_a_detail 
        else:
            kicker_detail = current_round.player_b_detail 
        goalME = kicker_detail.get('is_goalMe', False)  
         
        return goalME 


    async def switch_turns(self, current_round):
        player_a = await self.get_player_a()
        player_b = await self.get_player_b()
        
        if current_round.current_player == player_a and player_b: 
            current_round.round_status = 'PLAYER_B_TURN'
            current_round.current_player = player_b
            current_round.player_b_detail['started_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
            current_round.player_b_detail['ended_at'] = '' 
            
            async with self._timer_lock:
                if self._timer_task:
                    self._timer_task.cancel()
                self._timer_task = asyncio.create_task(
                    self.handle_timer_expiration(current_round, self.round_duration))
                
            await database_sync_to_async(current_round.save)()
            await self.schedule_timer_task(current_round)
        else: 
            current_round.round_status = 'RESULT'
            await self.finalize_round(current_round) 

    async def broadcast_update(self):
        current_round = await self.get_current_round()
        if not current_round:
            return

        await self.channel_layer.group_send(
            f"game_{self.game_id}",
            {
                'type': 'game.update',  
                'scores': {
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
                },
                'current_turn': await self.get_current_player_id(current_round),
                'timer': self.round_duration
            }
        )

    async def get_current_player_data_a(self, current_round):  
        obj_pass = await sync_to_async(
            lambda: FootballRound.objects.select_related('game__player_a')
            .filter(current_player=current_round.current_player)
            .first()
        )()
        
        if obj_pass and obj_pass.game and obj_pass.game.player_a:
            return obj_pass.game.player_a.auth_token
        return "Unknown Player"  # Fallback value
    
    async def get_current_player_data_b(self, current_round):  
        obj_pass = await sync_to_async(
            lambda: FootballRound.objects.select_related('game__player_b')
            .filter(current_player=current_round.current_player)
            .first()
        )()
        
        if obj_pass and obj_pass.game and obj_pass.game.player_b:
            return obj_pass.game.player_b.auth_token
        return "Unknown Player"  

    @database_sync_to_async 
    def get_current_player_object(self, current_round):
        return {
            'id': current_round.current_player.auth_token,
            'auth_token': current_round.current_player.user.auth_token
        }
     
    async def handle_player_action(self, content):
        vertical = content.get('vertical')
        horizontal = content.get('horizontal')
        power = content.get('power')

        current_round = await self.get_current_round()
        if not current_round or not await self.get_current_player_object(current_round):
            await self.send_json({'type': 'error', 'message': 'Invalid action'})
            return
        
        is_player_a = await database_sync_to_async(
            lambda: current_round.current_player == self.game.player_a
        )()
    
        player_detail = 'player_a_detail' if is_player_a else 'player_b_detail'
        detail = getattr(current_round, player_detail) 
        started_at = dt.strptime(detail['started_at'], "%d/%m/%YT%H:%M:%S") 

        if (timezone.now() - started_at).total_seconds() > self.round_duration:
            await self.handle_expired_turn(current_round)
            return
        
        detail.update({
            'vertical': vertical,
            'horizontal': horizontal,
            'power': power,
            'ended_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
            'is_turn_done': True,
        })
        await self.save_player_details(current_round, player_detail, detail)
        
        is_goal = await self.calculate_goal(current_round)
        if is_goal: 
            if is_player_a:
                current_round.player_a_detail['score'] = current_round.player_a_detail.get('score', 0) 
            else:
                current_round.player_b_detail['score'] = current_round.player_b_detail.get('score', 0) 
            await database_sync_to_async(current_round.save)(update_fields=['player_a_detail', 'player_b_detail'])

        if current_round.round_status == 'PLAYER_A_TURN':
            await self.switch_to_player_b(current_round)
        else:
            await self.finalize_round(current_round)

        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game.update', 
                'scores': { 
                        'round_status' : current_round.round_status,
                        'a': await self.get_player_a_score(current_round), 
                        'a_power': current_round.player_a_detail.get('power', 0.0),
                        'a_horizontal': current_round.player_a_detail.get('horizontal', 0.0),
                        'a_vertical': current_round.player_a_detail.get('vertical', 0.0),
                        'player_a_auth_token': await self.get_current_player_data_a(current_round),

                        'b': await self.get_player_b_score(current_round),  
                        'b_power': current_round.player_b_detail.get('power', 0.0),
                        'b_horizontal': current_round.player_b_detail.get('horizontal', 0.0),
                        'b_vertical': current_round.player_b_detail.get('vertical', 0.0), 
                        'player_b_auth_token': await self.get_current_player_data_b(current_round)
                },
                'current_player_auth_token': current_round.current_player.auth_token,
            }
        )

    @database_sync_to_async
    def save_player_details(self, current_round, field, details):
        setattr(current_round, field, details)
        current_round.save()

    async def switch_to_player_b(self, current_round):
        current_round.round_status = 'PLAYER_B_TURN'
        current_round.current_player = self.game.player_b
        current_round.player_b_detail['started_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
        await database_sync_to_async(current_round.save)()

    async def finalize_round(self, current_round): 
        async with self._timer_lock:
            if self._timer_task:
                self._timer_task.cancel()
                self._timer_task = None
        if current_round.round_status != 'RESULT':
            current_round.round_status = 'RESULT'
        await database_sync_to_async(current_round.save)()   
    
    @database_sync_to_async 
    def Player_obj(self, player): 
        obj_player = Player.objects.filter(user = player).first()
        return obj_player
    
    @database_sync_to_async 
    def create_result(self, current_round): 
        if FootBallResult.objects.filter(round=current_round).exists():
            return {'result_type': {}, 'scores': {}, 'bits': {}}
            
        total_a = current_round.player_a_detail.get('score', 0)
        total_b = current_round.player_b_detail.get('score', 0)
        amount_A =  self.game.player_a_bet_amount
        amount_B =  self.game.player_b_bet_amount
        total_amount = 0
        
        winner_a = winner_b = loser_a = loser_b = None
        winner_draw_a = winner_draw_b = None
        loss_draw_a = loss_draw_b = None

        if total_a == 1 and total_b == 0:
            winner_a = Player.objects.filter(user = self.game.player_a).first()  
            loser_b = Player.objects.filter(user = self.game.player_b).first()  
            total_amount = self.amount_A_Winner_Calculate(amount_A, amount_B)
        elif total_b == 1 and total_a == 0:
            winner_b = Player.objects.filter(user = self.game.player_b).first() 
            loser_a = Player.objects.filter(user = self.game.player_a).first() 
            total_amount = self.amount_B_Winner_Calculate(amount_A, amount_B)
        elif  total_b == 1 and total_a == 1:
            winner_draw_a = Player.objects.filter(user = self.game.player_a).first() 
            winner_draw_b = Player.objects.filter(user = self.game.player_b).first() 
        else:
            loss_draw_a = Player.objects.filter(user = self.game.player_a).first() 
            loss_draw_b = Player.objects.filter(user = self.game.player_b).first()  
            
        if winner_a:
            FootBallResult.objects.create(
                player=winner_a, round=current_round,
                amount_won_loss = total_amount, result_type='win'
            ) 
            FootBallResult.objects.create(
                player=loser_b, round=current_round,
                amount_won_loss = self.game.player_b_bet_amount, result_type='loss'
            )
            winner_a.coins += total_amount
            winner_a.save() 
        elif winner_b:
            FootBallResult.objects.create(
                player=winner_b, round=current_round,
                amount_won_loss = total_amount, result_type='win'
            ) 
            FootBallResult.objects.create(
                player=loser_a, round=current_round,
                amount_won_loss = amount_A, result_type='loss'
            )
            winner_b.coins +=  total_amount
            winner_b.save()
        elif winner_draw_a and winner_draw_b:
            FootBallResult.objects.create(
                player=winner_draw_a, round=current_round,
                amount_won_loss = amount_A, result_type='win_draw'
            ) 
            
            FootBallResult.objects.create(
                player=winner_draw_b, round=current_round,
                amount_won_loss = amount_B, result_type='win_draw'
            )
            winner_draw_a.coins += amount_A
            winner_draw_b.coins += amount_B
            winner_draw_a.save()
            winner_draw_b.save()
        else:
            FootBallResult.objects.create(
                player=loss_draw_a, round=current_round,
                amount_won_loss = amount_A, result_type='loss_draw'
            ) 
            
            FootBallResult.objects.create(
                player=loss_draw_b, round=current_round,
                amount_won_loss = amount_B, result_type='loss_draw'
            ) 


        self.GameExpired(current_round)
        if winner_a:
            return {
                'result_type': {'winner_a' :  self.get_player_auth_token(winner_a) if winner_a else None ,   
                    'loser_b' : self.get_player_auth_token(loser_b) if loser_b else None, 'prize': total_amount }, 
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            } 
        elif winner_b:
            return {
                'result_type': {'loser_a' : self.get_player_auth_token(loser_a)  if loser_a else None,
                    'winner_b' : self.get_player_auth_token(winner_b) if winner_b else None , 'prize': total_amount }, 
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            } 
        elif winner_draw_a and winner_draw_b:
            return {
                'result_type': {'win_draw_a': self.get_player_auth_token(winner_draw_a) if winner_draw_a else None, 
                                'win_draw_b': self.get_player_auth_token(winner_draw_b) if winner_draw_b else None
                                }, 
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            } 
        else:
            return {
                'result_type': {'loss_draw_a': self.get_player_auth_token(loss_draw_a) if loss_draw_a else None, 
                                'loss_draw_b': self.get_player_auth_token(loss_draw_b) if loss_draw_b else None}, 
                'scores': {'player_a': total_a, 'player_b': total_b},
                'bits': {'player_a_bit': amount_A, 'player_b_bit': amount_B}
            } 
        
    def amount_A_Winner_Calculate(self, amount_A, amount_B):
        if amount_A > amount_B:
            total_amount = (amount_B * 0.90) + amount_A
        else:
            total_amount = (amount_A * 0.90) + amount_A
        return total_amount
    def amount_B_Winner_Calculate(self, amount_A, amount_B):
        if amount_B > amount_A:
            total_amount = (amount_A * 0.90) + amount_B
        else:
            total_amount = (amount_B * 0.90) + amount_B
        return total_amount

    def get_player_auth_token(self, player):
        return player.user.auth_token if player else None
 
    def GameExpired(self, round_instance):
        if round_instance:
            FootballGame.objects.filter(id=round_instance.game.id).update(status='expired')
            return True
        return False
    
    async def game_update(self, event): 
        current_round = await self.get_current_round()
        event['timer'] = await self.calculate_remaining_time(current_round)
        
        event['current_turn'] = str(event['current_turn']) 
        await self.send_json(event)
 
    @database_sync_to_async
    def validate_round(self, round_obj): 
        if not round_obj:
            return False
        return all([
            round_obj.current_player,
            round_obj.round_status,
            'started_at' in round_obj.player_a_detail
        ])
    
    async def game_result(self, event): 
        await self.send_json({
            'type': 'game.result',
            'result': event['result']
        })

