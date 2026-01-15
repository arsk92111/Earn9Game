#consumers.py 
from channels.db import database_sync_to_async  
from GameApp.models import  GuessNumberGame
from AccountApp.models import db_Profile, Player, Transaction
from django.utils import timezone
from datetime import timedelta 
from asgiref.sync import sync_to_async  
import asyncio, json, random 
from channels.generic.websocket import AsyncWebsocketConsumer  
from django.views.decorators.csrf import csrf_exempt 


def default_player_detail_guess(player_token=None):
    return {
        "player_id": player_token if player_token else None,
        'status': 'bedding',
        'bet_amount': 0,
        'game_result': "lose",
        'winning_amount': 0,
        'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
        'ended_at': '',
        'time_remaings': 100,
        'attempt_remaining': 10,
        'target_number': random.randint(0, 1000),
        'your_guesses': []  
    }

class GuessNumberConsumer(AsyncWebsocketConsumer):
    round_duration = 100
    result_duration = 3
    current_phase = 'bedding'
    game_group = "guessNumber" 

    _timer_task = None
    _timer_lock = asyncio.Lock()
    game_ended = False  # Track if game has ended
  
    async def connect(self):
        try:
            await self.accept() 
            if not await self.authenticate_user():
                return  
            
            self.user_group = f"guessNumber_{self.user.id}"
            await self.channel_layer.group_add(
                self.user_group, 
                self.channel_name
            )
             
            self.game = await self.get_or_create_game()
            await self.send_initial_state()
 
            game_state = self.game.player_game_detail
            if game_state['status'] == 'active' and game_state['time_remaings'] > 0:
                await self.start_timer(game_state['time_remaings'])

        except Exception as e:
            await self.handle_connection_error(e)
    
    @database_sync_to_async
    def get_or_create_game(self): 
        active_game = GuessNumberGame.objects.filter(
            player_auth=self.player.user,
            player_game_detail__status__in=['bedding', 'active']
        ).order_by('-created_at').first()
        
        if active_game:
            return active_game
             
        profile = self.player.user
        return GuessNumberGame.objects.create(
            player_auth=profile,
            player_game_detail=default_player_detail_guess(player_token = profile.auth_token ),
            player_channel=self.channel_name
        )

    async def send_initial_state(self):
        state = self.game.player_game_detail
        await self.send(json.dumps({
            'type': 'game_state',
            'state': {
                'status': state['status'],
                'bet_amount': state['bet_amount'],
                'time_remaining': state['time_remaings'],
                'attempts_left': state['attempt_remaining'],
                'guesses': state['your_guesses'],
                'target_number': state['target_number'] if state['status'] != 'active' else None, 
                'game_result': state.get('game_result'),
                'winning_amount': state.get('winning_amount')
            }
        }))

    async def handle_connection_error(self, error): 
        print(f"Connection error: {str(error)}")
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
            self.player = await sync_to_async(Player.objects.get)(user=self.user)
            return True
        except Player.DoesNotExist:
            await self.handle_connection_error("Player record missing")
            return False
          
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'place_bid':
                await self.handle_bid(data['amount'])
            elif action == 'submit_guess':
                await self.handle_guess(data['guess'])
            elif action == 'get_state':
                await self.send_initial_state()
                
        except Exception as e:
            await self.send_error(f"Invalid request: {str(e)}")

    async def handle_bid(self, amount):
        game_state = self.game.player_game_detail
         
        if game_state['status'] != 'bedding':
            await self.send_error("Bidding not allowed in current phase")
            return
             
        if not await self.deduct_balance(amount):
            await self.send_error("Insufficient balance")
            return
             
        game_state['status'] = 'active'
        game_state['bet_amount'] = amount
        game_state['started_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
        self.game_ended = False  # Reset game ended flag
        
        await self.save_game_state(game_state)
        await self.start_timer(self.round_duration)
         
        await self.channel_layer.group_send(
            self.user_group,
            {
                'type': 'game_update',
                'state': {
                    'status': 'active',
                    'bet_amount': amount,
                    'time_remaining': self.round_duration
                }
            }
        )

    @database_sync_to_async
    def deduct_balance(self, amount):
        if self.player.coins < amount:
            return False
        self.player.coins -= amount
        self.player.save()
        return True

    async def start_timer(self, initial_time):
        async with self._timer_lock:
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                
            self._timer_task = asyncio.create_task(self.run_timer(initial_time))

    async def run_timer(self, initial_time):
        time_left = initial_time
        game_state = self.game.player_game_detail
        
        while time_left > 0 and not self.game_ended:
            await asyncio.sleep(1)
            
            if self.game_ended or game_state['status'] != 'active':
                break
                
            time_left -= 1
            game_state['time_remaings'] = time_left 
             
            await self.save_game_state(game_state) 
            
            await self.channel_layer.group_send(
                self.user_group,
                {
                    'type': 'timer_update',
                    'time_remaining': time_left
                }
            )
            if game_state['time_remaings'] <= 0 and (game_state['status'] == 'active' or game_state['status'] == 'result'):
                await self.end_game_send(False, game_state)

    async def handle_guess(self, guess):
        try:
            guess = int(guess)
        except ValueError:
            await self.send_error("Invalid number format")
            return
        
        game_state = self.game.player_game_detail
        
        if game_state['status'] != 'active' or self.game_ended: 
            await self.send_error("Game not active")
            return
         
        game_state['your_guesses'].append(guess)
        game_state['attempt_remaining'] -= 1
        
        target = game_state['target_number'] 
        if game_state['time_remaings'] < 1:
            await self.end_game(False, game_state['time_remaings'])
            return  
        elif guess == target:
            await self.end_game(True, game_state['time_remaings'])
            return 
        elif game_state['attempt_remaining'] < 1:
            await self.end_game(False, game_state['time_remaings'])
            return  
        else:
            if guess < target:
                result_msg = "Too low! Guess higher."
                image_type = "low" 
            else:
                result_msg = "Too high! Guess lower."
                image_type = "high"
            
        await self.handle_guess_send(result_msg, game_state, image_type)
    
    async def handle_guess_send(self, result_msg, game_state, image_type): 
        await self.save_game_state(game_state) 
        await self.channel_layer.group_send(
            self.user_group,
            {
                'type': 'guess_result',
                'result': result_msg,
                'image_type': image_type,
                'state': {
                    'attempts_left': game_state['attempt_remaining'],
                    'guesses': game_state['your_guesses']
                }
            }
        )

    async def end_game(self, is_winner, remain_time): 
        if self.game_ended:
            return 
        self.game_ended = True  
        async with self._timer_lock:
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
        
        game_state = self.game.player_game_detail
        game_state['status'] = 'result'
        game_state['ended_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
        game_state['game_result'] = 'win' if is_winner else 'lose'
        
        if remain_time < 1:  
            await self.end_game_send(False, game_state) 
        elif is_winner: 
            await self.end_game_send(is_winner, game_state)
        else:
            await self.end_game_send(False, game_state)
             
        await self.end_game_send(is_winner, game_state) 

        await asyncio.sleep(2)
        game_state['status'] = 'expired'
        await self.save_game_state(game_state)   
        await self.send_initial_state()
        
        if is_winner:
            await self.add_winnings(game_state['winning_amount'])

    async def end_game_send(self, is_winner, game_state): 
        if is_winner: 
            winnings = int(game_state['bet_amount'] * 1.5)
            game_state['winning_amount'] = winnings  
            image_type = "win"
        else:
            game_state['ended_at'] = timezone.now().strftime("%d/%m/%YT%H:%M:%S")
            game_state['status'] = 'expired'
            image_type = "lose" 

        await self.save_game_state(game_state) 
        await self.channel_layer.group_send(
            self.user_group,
            {
                'type': 'game_result',
                'result': 'win' if is_winner else 'lose',
                'winnings': game_state['winning_amount'],
                'lossing_amount': game_state['bet_amount'],
                'target_number': game_state['target_number'],
                'image_type': image_type  
            }
        )

    @database_sync_to_async
    def add_winnings(self, amount):
        self.player.coins += amount
        self.player.save()

    @database_sync_to_async
    def save_game_state(self, state):
        self.game.player_game_detail = state
        self.game.save()

    async def game_update(self, event):
        await self.send(json.dumps(event))

    async def timer_update(self, event):
        await self.send(json.dumps({
            'type': 'timer',
            'time_remaining': event['time_remaining']
        }))

    async def guess_result(self, event):
        await self.send(json.dumps(event))

    async def game_result(self, event):
        await self.send(json.dumps(event))

    async def send_error(self, message):
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))

    async def disconnect(self, close_code):
        async with self._timer_lock:
            if self._timer_task:
                self._timer_task.cancel()
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )

    @database_sync_to_async
    def finalize_game(self):
        if hasattr(self, 'game') and not self.game_ended:
            game_state = self.game.player_game_detail
            if game_state['status'] == 'active':
                game_state['status'] = 'expired'
                self.game.player_game_detail = game_state
                self.game.save()

 