#consumers.py 
from channels.db import database_sync_to_async 
from django.db.models import Sum
from GameApp.models import Game, PlayerBid, GameRound 
from AccountApp.models import db_Profile ,Player, Transaction
from django.utils import timezone
from datetime import timedelta 
from asgiref.sync import sync_to_async 
from GameApp.views import calculate_winners, get_deck
import asyncio, json, random 
from channels.generic.websocket import AsyncWebsocketConsumer 
from django.db import IntegrityError, transaction 
from django.views.decorators.csrf import csrf_exempt 
 

class CardGameConsumer(AsyncWebsocketConsumer):
    round_duration = 30
    result_duration = 3
    countdown_duration = 3
    current_phase = 'bidding'
    game_group = "live_card_game"

    _timer_task = None
    _timer_lock = asyncio.Lock()
  
    async def connect(self):
        try:
            await self.accept() 
            if not await self.authenticate_user():
                return  
            
            await self.initialize_core_components() 
            await self.run_phase_timer() 
            await self.send_initial_state() 
            await self.channel_layer.group_add(
                self.game_group, 
                self.channel_name
            )

        except Exception as e:
            await self.handle_connection_error(e)
 
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
         
    async def initialize_core_components(self):
        self.game = await self.get_or_create_game()
        self.player = await self.get_player()

    async def initialize_game_state(self):
        if not await self.ensure_active_round():
            raise Exception("Game state initialization failed")

    async def join_group(self):
        await self.channel_layer.group_add(
            self.game_group, 
            self.channel_name
        )
    
    @database_sync_to_async
    def get_or_create_game(self):
        return Game.objects.get_or_create(name="Live Card Game")[0]

    async def get_current_round(self): 
        round = await sync_to_async(
            GameRound.objects.filter(
                game=self.game,
                status=GameRound.RoundStatus.ACTIVE
            ).first
        )()
        
        if not round:
            print("No active round found, creating new one")
            await self.create_new_round()
            return await sync_to_async(
                GameRound.objects.filter(
                    game=self.game,
                    status=GameRound.RoundStatus.ACTIVE
                ).first
            )()
            
        return round

    @database_sync_to_async
    def get_player(self):
        try:
            return Player.objects.get(user=self.user)
        except Player.DoesNotExist: 
            return Player.objects.create(user=self.user, coins=0)
    
    @database_sync_to_async
    def get_player(self):
        return Player.objects.get(user=self.user)
    
    async def ensure_active_round(self): 
        self.current_round = await self.get_current_round()
        if not self.current_round:
            return await self.create_new_round()
        return True
    
    def get_logged_in_username(self):
        if self.user and self.user.is_authenticated:
            return self.user.username or self.user.db_phone_number or self.user.email
        return "Anonymous"
    
    async def send_initial_state(self): 
        try: 
            if not hasattr(self, 'current_round') or not self.current_round:
                self.current_round = await self.get_current_round()
                
            if not self.current_round:
                raise ValueError("Failed to initialize game round")

            remaining = await self.get_remaining_time()
            phase = await self.determine_current_phase(remaining)
            
            await self.send(json.dumps({
                'type': 'initial_state',
                'round_id': self.current_round.id, 
                'current_user': self.get_logged_in_username(),
                'bids': {
                    'totals': {
                        'Number': self.game.current_bid.get('NUM', 0),
                        'Picture': self.game.current_bid.get('PIC', 0)
                    },
                    'user_bets': await self.get_user_bets(),
                    'participants': await self.get_participants()
                },
                'timer': {
                    'remaining': remaining,
                    'phase': phase
                }
            }))
            
        except Exception as e:
            print(f"Initial state error: {str(e)}")
            await self.send_error("Game initialization failed")
            await self.handle_connection_error(e)
 
    async def _timer_loop(self):
        while True:
            try:
                self.game = await sync_to_async(Game.objects.first)()
                
                if not self.game:
                    self.game = await self.get_or_create_game()

                round = await self.get_current_round()
                if not round:
                    await self.create_new_round()
                    await asyncio.sleep(0.1)  # Allow DB write
                    continue

                remaining = await self.get_remaining_time()
                phase = await self.determine_current_phase(remaining)
 
                if remaining <= 0:
                    if phase == 'bidding': 
                        await self.start_results_phase(round)
                    elif phase == 'results': 
                        await self.complete_round(round)
                    elif phase == 'countdown': 
                        await self.create_new_round()
 
                await self.channel_layer.group_send(
                    self.game_group,
                    {
                        'type': 'timer.update',
                        'remaining': remaining,
                        'phase': phase
                    }
                )

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Timer error: {str(e)}")
                await asyncio.sleep(5)

    async def run_phase_timer(self): 
        async with self._timer_lock:
            if self._timer_task and not self._timer_task.done():
                return

            self._timer_task = asyncio.create_task(self._timer_loop())
     
    async def receive(self, text_data): 
        if self.user.is_anonymous:
            await self.send_error("Authentication required")
            return 
        try:
            data = json.loads(text_data)
            if data['action'] == 'place_bid':
                await self.handle_bid(data)
            elif data['action'] == 'get_initial_state':
                await self.send_initial_state()
            else:
                await self.send_error("Invalid action")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error("Server error")
 
    async def validate_bid(self, data):
        required = ['amount', 'side', 'round_id']
        if any(field not in data for field in required):
            raise ValueError("Missing fields")
 
    @database_sync_to_async
    def update_round_timer(self, round_obj, remaining):
        round_obj.timer = remaining
        round_obj.save()
 
    async def create_new_round(self): 
        try:
            async with self._timer_lock: 
                current_round = await sync_to_async(
                    GameRound.objects.filter(
                        game=self.game,
                        status=GameRound.RoundStatus.ACTIVE
                    ).first
                )()
                 
                if current_round: 
                    self.current_round = current_round
                    return

 
                card = random.choice(get_deck())
                self.current_round = await sync_to_async(GameRound.objects.create)(
                    game=self.game,
                    card=card,
                    status=GameRound.RoundStatus.ACTIVE,
                    start_time=timezone.now()
                    )
                
                self.game.current_round = self.current_round
                self.game.current_bid = {'NUM': 0, 'PIC': 0}
                await sync_to_async(self.game.refresh_from_db)()

        except Exception as e:
            print(f"Round creation failed: {str(e)}")
            await self.handle_connection_error(e)


    async def determine_current_phase(self, remaining):
        try:
            round = await self.get_current_round()
            if not round:
                return 'waiting'
                
            if round.status == GameRound.RoundStatus.ACTIVE:
                return 'bidding'
            elif round.status == GameRound.RoundStatus.RESULTS:
                return 'results'
            elif round.status == GameRound.RoundStatus.COMPLETED:
                return 'countdown'
                
            return 'waiting'
        except Exception as e:
            print(f"Phase determination error: {str(e)}")
            return 'error'

    def handle(self, *args, **options):
        stale_rounds = GameRound.objects.filter(
            status=GameRound.RoundStatus.ACTIVE,
            start_time__lt=timezone.now() - timedelta(minutes=5)
        )
        for round in stale_rounds:
            calculate_winners(round)
            round.status = GameRound.RoundStatus.COMPLETED
            round.save()
    
    async def handle_bid(self, data):
        try:
            if not await self.validate_bid_data(data):
                return

            success = await self.process_bid(data)
            if not success:
                return

            await self.send_balance_update()
            await self.broadcast_bid_update() 

        except Exception as e:
            await self.handle_bid_error(e)
     
    @database_sync_to_async
    def validate_bid_data(self, data):
        required_fields = ['amount', 'side', 'round_id']
        if any(field not in data for field in required_fields):
            raise ValueError("Missing required bid fields")
            
        if data['side'].lower() not in ['number', 'picture']:
            raise ValueError("Invalid side selection")
        
        if not isinstance(data['amount'], int) or data['amount'] < 1:
            raise ValueError("Invalid bid amount")
            
        return True
    
    @database_sync_to_async
    def process_bid(self, data):
        with transaction.atomic():
            player = Player.objects.select_for_update().get(user=self.user)
            round = GameRound.objects.get(id=data['round_id']) 
            if player.coins < data['amount']:
                raise ValueError("Insufficient funds")
                
            internal_side = 'PIC' if data['side'].lower() == 'picture' else 'NUM'
             
            bid, created = PlayerBid.objects.get_or_create(
                player=player,
                round=round,
                side=internal_side,
                defaults={'amount': data['amount']}
            )
            
            if not created:
                bid.amount += data['amount']
                bid.save()
                 
            self.game.current_bid[internal_side] = self.game.current_bid.get(internal_side, 0) + data['amount']
            self.game.save()
             
            player.coins -= data['amount']
            player.save()
            return True
    
    async def broadcast_bid_update(self):
        print(self.user)
        await self.channel_layer.group_send(
            self.game_group,
            {
                'type': 'bids.update',
                'totals': {
                    'Number': self.game.current_bid.get('NUM', 0),
                    'Picture': self.game.current_bid.get('PIC', 0)
                },
                'user_bets': await self.get_user_bets(), 
                'participants': await self.get_participants(),  
            }
        )
      
    @database_sync_to_async
    def get_participants(self):
        current_round = GameRound.objects.filter(
            game=self.game,
            status=GameRound.RoundStatus.ACTIVE
        ).first()
        
        if not current_round:
            return []

        participants = [] 
        bids = PlayerBid.objects.filter(round=current_round).select_related('player__user')
         
        user_totals = {}
        for bid in bids:
            user_display = self.get_user_display(bid.player.user)
            side = 'Number' if bid.side == 'NUM' else 'Picture'
            key = f"{user_display}-{side}"
            
            if key not in user_totals:
                user_totals[key] = {
                    'user': user_display,
                    'side': side,
                    'amount': 0
                }
            user_totals[key]['amount'] += bid.amount
        
        return list(user_totals.values())
       
    def get_user_display(self, user): 
        if user.username:
            return user.username
        if user.db_phone_number:
            return user.db_phone_number
        if user.email:
            return user.email.split('@')[0]
        return f"User-{user.id}"


    async def send_balance_update(self):
        await self.send(json.dumps({
            'type': 'balance_update',
            'balance': self.player.coins
        }))

    async def handle_bid_error(self, error):
        await self.send(json.dumps({
            'type': 'error',
            'message': str(error)
        }))
        await sync_to_async(self.player.refresh_from_db)()
        await self.send_balance_update()


    async def send_timer_update(self, remaining, phase):
        await self.channel_layer.group_send(
            self.game_group,
            {
                'type': 'timer_update',
                'remaining': remaining,
                'phase': phase
            }
        )
        
    @database_sync_to_async
    def save_phase_state(self):
        self.game.timer_state = {
            'phase': self.current_phase,
            'timestamp': timezone.now().isoformat()
        }
        self.game.save()
    
    async def get_remaining_time(self):
        round = await self.get_current_round()
        if not round:
            return 0
        
        now = timezone.now()
        
        if round.status == GameRound.RoundStatus.ACTIVE:
            elapsed = (now - round.start_time).total_seconds()
            return max(0, self.round_duration - int(elapsed))
        elif round.status == GameRound.RoundStatus.RESULTS: 
            return self.result_duration
        elif round.status == GameRound.RoundStatus.COMPLETED:
            elapsed = (now - round.end_time).total_seconds()
            return max(0, self.countdown_duration - int(elapsed))
        return 0
    
    async def transition_to_next_phase(self, current_phase):
        if current_phase == 'bidding':
            await self.process_round_results()
            await self.start_countdown()
        elif current_phase == 'results':
            await self.start_new_round()
            

    async def start_results_phase(self, round): 
        current_status = await sync_to_async(lambda: round.status)()
        if current_status != GameRound.RoundStatus.ACTIVE:
            return
        results, win_side = await sync_to_async(calculate_winners)(round)
         
        round.status = GameRound.RoundStatus.RESULTS
        round.end_time = timezone.now()
        await sync_to_async(round.save)()
         
        await self.channel_layer.group_send(
            self.game_group,
            {
                'type': 'results',
                'results': results,
                'winning_side': win_side,
                'card': round.card
            }
        )
         
        await self.channel_layer.group_send(
            self.game_group,
            {
                'type': 'timer.update',
                'remaining': self.result_duration,
                'phase': 'results'
            }
        )

    async def complete_round(self, round):
        """Mark round as completed"""
        round.status = GameRound.RoundStatus.COMPLETED
        await sync_to_async(round.save)()
 
    @database_sync_to_async
    def get_current_bids(self):
        return {
            'totals': self.game.current_bid,
            'participants': {
                bid.player.user.username: bid.amount
                for bid in PlayerBid.objects.select_related('player__user')
                    .filter(round=self.current_round)
            },
            'user_bets': dict(
                PlayerBid.objects.filter(player=self.player, round=self.current_round)
                    .values_list('side', 'amount')
            )
        }
    
    @csrf_exempt
    @transaction.atomic  
    @database_sync_to_async
    def create_bid(self, amount, side):
        with transaction.atomic():
            try: 
                internal_side = 'PIC' if side.lower() == 'picture' else 'NUM'
                 
                bid = PlayerBid.objects.create(
                    player=self.player,
                    round=self.current_round,
                    amount=amount,
                    side=internal_side
                )
                 
                self.game.current_bid[internal_side] = self.game.current_bid.get(internal_side, 0) + amount
                self.game.save()
                 
                self.player.coins -= amount
                self.player.save()
                
                return True

            except IntegrityError:
                raise ValueError("You already placed a bid this round")
        

    async def results(self, event):
        await self.send(json.dumps({
            'type': 'results',
            'participants': event['results'],
            'winning_side': event['winning_side'],
            'card': event['card']
        }))
  
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group, self.channel_name)
    
    async def get_initial_state(self):
        try: 
            self.game = await sync_to_async(Game.objects.first)()
            if not self.game:
                self.game = await sync_to_async(Game.objects.create)(name="Live Card Game")
                
            self.current_round = await sync_to_async(
                GameRound.objects.filter(game=self.game)
                .order_by('-start_time')
                .first
            )()
            
            if not self.current_round or self.current_round.status != GameRound.RoundStatus.ACTIVE:
                await self.create_new_round()
                 
            await self.send_initial_state()
            
        except Exception as e:
            print(f"Initialization error: {str(e)}")
 
    @database_sync_to_async
    def update_totals(self, side, amount):
        self.game.current_bid[side] = self.game.current_bid.get(side, 0) + amount
        self.game.save()

    async def send_updates(self):
        await self.channel_layer.group_send(self.game_group, {
            'type': 'bids.update',
            'totals': self.game.current_bid,
            'user_bets': await self.get_user_bets()
        })
    
    @database_sync_to_async
    def get_user_bets(self):
        current_round = GameRound.objects.filter(
            game=self.game,
            status=GameRound.RoundStatus.ACTIVE
        ).first()
        
        if not current_round:
            return {'Number': 0, 'Picture': 0}

        return {
            'Number': PlayerBid.objects.filter(
                player=self.player,
                round=current_round,
                side='NUM'
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'Picture': PlayerBid.objects.filter(
                player=self.player,
                round=current_round,
                side='PIC'
            ).aggregate(Sum('amount'))['amount__sum'] or 0
        }
  
 
    # ---------------- Game Initialization ---------------- #
    async def initialize_game(self):
        if await self.should_create_new_round(self.current_round):
            await self.create_new_round()
        else:
            await self.send_initial_round_data(self.current_round)
            await self.start_round_timer(self.current_round)
 

    async def start_round_timer(self, round_obj):
        remaining = await self.get_remaining_time()
        await self.run_phase_timer(remaining, "bidding", round_obj)
      
    async def bids_update(self, event): 
        converted_totals = {
            'Number': event['totals'].get('NUM', 0),
            'Picture': event['totals'].get('PIC', 0)
        }
        await self.send(json.dumps({
            'type': 'bids_update',
            'totals': converted_totals,
            'user_bets': event['user_bets'],
            'participants': event['participants']
        }))

    async def process_round_results(self, round_obj):
        try:
            results, win_side = await sync_to_async(calculate_winners)(round_obj)
            win_side = 'Picture' if win_side == 'PIC' else 'Number'
            
            await self.channel_layer.group_send(
                self.game_group,
                {
                    'type': 'results',
                    'participants': results,
                    'winning_side': win_side,
                    'card': self.current_round.card
                }
            )
            await self.create_new_round()

        except Exception as e:
            print(f"Result processing error: {str(e)}")

    @database_sync_to_async
    def get_current_bids(self):
        bids = PlayerBid.objects.filter(round=self.current_round).select_related('player__user')
        participants = {bid.player.user.username: bid.amount for bid in bids}
        return {
            'totals': self.game.current_bid,
            'participants': participants,
            'user_bets': dict(bids.values_list('side', 'amount'))
        }
 
    # ---------------- Bidding ---------------- #
 
    @database_sync_to_async
    def get_active_game(self):
        try:
            return Game.objects.filter(is_active=True).latest('id')
        except Game.DoesNotExist:
            return None

    @database_sync_to_async
    def get_player_from_user(self, user):
        return Player.objects.get(user=user)
 

    @database_sync_to_async
    def should_create_new_round(self, round_obj):
        if not round_obj:
            return True
        return round_obj.status != GameRound.RoundStatus.ACTIVE

    @database_sync_to_async
    def create_new_round_db(self):
        card = random.choice(get_deck())['name']
        return GameRound.objects.create(
            game=self.game,
            card=card,
            status=GameRound.RoundStatus.ACTIVE,
            start_time=timezone.now()
        )

    @database_sync_to_async
    def update_game_current_round(self, round_obj):
        self.game.current_round = round_obj
        self.game.save()

    @database_sync_to_async
    def end_previous_round(self):
        if self.current_round:
            self.current_round.status = GameRound.RoundStatus.COMPLETED
            self.current_round.end_time = timezone.now()
            self.current_round.save()
 
    @sync_to_async
    def deduct_player_coins(self, amount):
        self.player.coins -= amount
        self.player.save()

    @sync_to_async
    def save_bid_to_db(self, amount, card_type):
        return PlayerBid.objects.create(
            player=self.player,
            game=self.game,
            card_type=card_type,
            bid_amount=amount
        )

    @sync_to_async
    def update_current_bid(self, card_type, amount):
        if not self.game.current_bid:
            self.game.current_bid = {}
        self.game.current_bid[card_type] = self.game.current_bid.get(card_type, 0) + amount
        self.game.save()

    # ---------------- Messaging ---------------- #
    async def send_game_update(self, message):
        await self.send(text_data=json.dumps({
            'type': 'game_update',
            'message': message
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
 
    async def send_results(self, results, win_side, card):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "round.results",
                "results": results,
                "winning_side": win_side,
                "card": card
            }
        )

    async def send_initial_round_data(self, round_obj):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "round.start",
                "card": round_obj.card,
                "start_time": round_obj.start_time.isoformat()
            }
        )
 
    async def game_update(self, event):
        await self.send_game_update(event['message'])
    
    async def timer_update(self, event):
        await self.send(json.dumps({
            'type': 'timer_update',
            'remaining': event['remaining'],
            'phase': event['phase']
        }))
 

    async def round_results(self, event):
        await self.send(text_data=json.dumps({
            "type": "results",
            "results": event["results"],
            "winning_side": event["winning_side"],
            "card": event["card"]
        }))

    async def round_start(self, event):
        await self.send(text_data=json.dumps({
            "type": "round_start",
            "card": event["card"],
            "start_time": event["start_time"]
        }))


  