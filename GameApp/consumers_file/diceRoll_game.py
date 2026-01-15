#consumers.py 
from channels.db import database_sync_to_async 
from django.db.models import Sum, F, Q  
from GameApp import models
from GameApp.models import  Dice_Game, Dice_GameRound, Dice_PlayerBid, Dice_PlayerResult 
from AccountApp.models import db_Profile, Player, Transaction
from django.utils import timezone
from datetime import timedelta 
from asgiref.sync import sync_to_async  
import asyncio, json, random 
from channels.generic.websocket import AsyncWebsocketConsumer 
from django.db import IntegrityError, transaction  
 

class DiceRollGameConsumer(AsyncWebsocketConsumer): 
    _active_connections = set()
    ROUND_DURATION = 20
    RESULT_DURATION = 8
    GAME_GROUP = "live_dice_game"

    _timer_task = None
    _timer_lock = asyncio.Lock()
    _active_consumer = None  
       
    async def connect(self):
        await self.accept()
        self._active_connections.add(self)
        self.connected = True
        
        if not await self.authenticate_user():
            return

        await self.channel_layer.group_add(self.GAME_GROUP, self.channel_name)
        await self.initialize_game()
        await self.send_initial_state()
        await self.ensure_timer_running()
        asyncio.create_task(self.websocket_heartbeat())

    async def authenticate_user(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close(code=4001)
            return False
        
        try:
            self.player = await database_sync_to_async(Player.objects.get)(user=self.user)
            return True
        except Player.DoesNotExist:
            await self.close(code=4002)
            return False

    async def safe_send(self, message):
        if self in self._active_connections:
            try:
                await self.send(text_data=json.dumps(message))
            except Exception as e:
                print(f"Failed to send message: {e}")
                await self.close()

    async def websocket_heartbeat(self):
        while self.connected:
            try:
                await self.safe_send({'type': 'heartbeat'})
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Heartbeat failed: {e}")
                break
 
    async def disconnect(self, close_code):
        try:
            if self in self._active_connections:
                self._active_connections.remove(self)
                
            if self._active_consumer == self.channel_name:
                self._active_consumer = None
                
            await self.channel_layer.group_discard(self.GAME_GROUP, self.channel_name)
            
            if self._timer_task:
                self._timer_task.cancel()
        except Exception as e:
            print(f"Error during disconnect: {e}")
        finally:
            self.connected = False

    async def initialize_game(self):
        self.game = await self.get_or_create_game()
        self.current_round = await self.get_active_round(self.game)
        
        if not self.current_round:
            self.current_round = await self.create_new_round()
            await self.broadcast_new_round()

    @database_sync_to_async
    def get_or_create_game(self):
        return Dice_Game.objects.get_or_create(name="Live Dice Battle")[0]
    
    @database_sync_to_async
    def get_global_game(self):
        return Dice_Game.objects.get_or_create(name="Live Dice Battle")[0]

    @database_sync_to_async
    def get_active_round(self, game):
        return Dice_GameRound.objects.filter(
            game=game,
            status__in=[
                Dice_GameRound.RoundStatus_dice.ACTIVE,
                Dice_GameRound.RoundStatus_dice.RESULTS
            ]
        ).first()
    
    @database_sync_to_async
    def create_new_round(self):
        with transaction.atomic():  
            existing_round = Dice_GameRound.objects.filter(
                game=self.game,
                status=Dice_GameRound.RoundStatus_dice.ACTIVE
            ).first()
            if existing_round:
                existing_round.status = Dice_GameRound.RoundStatus_dice.COMPLETED
                existing_round.save()
             
            jackpot_numbers = random.sample(range(2, 13), 2)
            exact_jackpot_numbers = random.sample(range(2, 13), 2)
            new_round = Dice_GameRound.objects.create(
                game=self.game,
                status=Dice_GameRound.RoundStatus_dice.ACTIVE,
                start_time=timezone.now(),
                result_start=None,  # EXPLICITLY SET TO None
                multiplyer_number={"number1": jackpot_numbers[0], "number2": jackpot_numbers[1]},
                exact_number_on_multiplyer={"number1": exact_jackpot_numbers[0], "number2": exact_jackpot_numbers[1]}
            )
            
            self.game.current_round = new_round
            self.game.current_bid = {"DOWN": 0, "MIDDLE": 0, "UP": 0, "EXACT": {}}
            self.game.save()
            
            return new_round
    
    async def ensure_timer_running(self):
        async with self._timer_lock:
            if self._timer_task and not self._timer_task.done():
                return
                 
            self._timer_task = asyncio.create_task(self.global_timer_loop())

    async def global_timer_loop(self): 
        while True:
            try: 
                game = await self.get_global_game()  # Directly call the async method
                active_round = await self.get_active_round(game)  # Directly call the async method
                
                if not active_round:
                    await asyncio.sleep(1)
                    continue
                
                now = timezone.now()
                status = active_round.status
                
                if status == Dice_GameRound.RoundStatus_dice.ACTIVE:
                    elapsed = (now - active_round.start_time).total_seconds()
                    remaining = max(0, self.ROUND_DURATION - int(elapsed))
                    
                    await self.broadcast_timer(remaining, 'bidding')
                    
                    if remaining <= 0:
                        await self.process_bidding_end()
                
                elif status == Dice_GameRound.RoundStatus_dice.RESULTS: 
                    if not active_round.result_start:
                        active_round.result_start = now
                        await database_sync_to_async(active_round.save)()
                    
                    elapsed = (now - active_round.result_start).total_seconds()
                    remaining = max(0, self.RESULT_DURATION - int(elapsed))
                    
                    await self.broadcast_timer(remaining, 'results')
                    
                    if remaining < 1: # and status == Dice_GameRound.RoundStatus_dice.COMPLETED:  # Buffer period
                        await self.start_new_round()
                
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Global timer error: {e}")
                await asyncio.sleep(1)
                
    @database_sync_to_async
    def update_game_timer(self, remaining):
        self.game.timer = remaining
        self.game.save()
        
    async def refresh_game_state(self):
        self.current_round = await database_sync_to_async(
            Dice_GameRound.objects.get
        )(id=self.current_round.id) 
    
    async def process_bidding_end(self):  
        dice1, dice2 = random.randint(1, 6), random.randint(1, 6)
        total = dice1 + dice2  
        await self.save_dice_results(dice1, dice2, total)
          
        player_results = await self.process_results(dice1, dice2, total) 
        
        await self.update_round_status(
            Dice_GameRound.RoundStatus_dice.RESULTS,
            result_start=timezone.now()
        )
         
        winning_side = self.get_winning_side(total)
        await self.broadcast_results(dice1, dice2, total, winning_side, player_results)

    @database_sync_to_async
    def save_dice_results(self, dice1, dice2, total):
        self.current_round.dice1 = dice1
        self.current_round.dice2 = dice2
        self.current_round.total = total
        self.current_round.save()
         
    async def process_results(self, dice1, dice2, total): 
        winning_side = self.get_winning_side(total, True) 
        player_results = await database_sync_to_async(self.calculate_and_save_results)(total, winning_side)
        return player_results
         
    @transaction.atomic
    def calculate_and_save_results(self, total, winning_side):
        with transaction.atomic():
            player_results = []
            bids = Dice_PlayerBid.objects.filter(round=self.current_round)
            
            for bid in bids:
                total_return, result_type = self.calculate_winnings(bid, total, winning_side)
                total_bet = bid.amount_bet_side + bid.amount_bet_exact
                net_profit = total_return + total_bet 
                player = bid.player   
                is_loss = result_type.lower() == "lose" 

                if is_loss:
                    result = Dice_PlayerResult.objects.create(
                        player=player,  
                        round=self.current_round,
                        amount_bet_side=bid.amount_bet_side,
                        amount_bet_exact=bid.amount_bet_exact,
                        amount_won_loss=total_bet,  
                        result_type=result_type
                    )
                    
                else:
                    result = Dice_PlayerResult.objects.create(
                        player=player,
                        round=self.current_round,
                        amount_bet_side=bid.amount_bet_side,
                        amount_bet_exact=bid.amount_bet_exact,
                        amount_won_loss=net_profit, 
                        result_type=result_type
                    )
                   
                    player.coins += net_profit
                    player.save()

                player_results.append({
                    'fullname': player.user.db_fullname,
                    'auth_token': player.user.auth_token,
                    'amount_bet_side': bid.amount_bet_side,
                    'amount_bet_exact': bid.amount_bet_exact,
                    'result_type': result_type, 
                    'amount_won_loss': total_bet if is_loss else net_profit, 
                    'won': not is_loss  
                })
                
            return player_results
       
    async def send_balance_update(self): 
        await database_sync_to_async(self.player.refresh_from_db)()
        await self.send(json.dumps({
            'type': 'balance_update',
            'balance': self.player.coins
        }))

    
    def calculate_winnings(self, bid, total, winning_side): 
        total_return = 0
        result_types = []
        developer_fee = 0.90
        jackpots = list(self.current_round.exact_number_on_multiplyer.values())

        win_flag = False 
        
        if bid.side and bid.side == winning_side: 
            total_return += bid.amount_bet_side * developer_fee
            result_types.append('win')
            win_flag = True

        if bid.exact_number:
            if bid.exact_number in jackpots:
                if bid.exact_number == self.current_round.exact_number_on_multiplyer['number1']:
                    multiplier_val = self.current_round.multiplyer_number['number1']
                else:
                    multiplier_val = self.current_round.multiplyer_number['number2']

                total_return += ((bid.amount_bet_exact * multiplier_val) * developer_fee)
                result_types.append('win')
                win_flag = True

            elif bid.exact_number == total:
                total_return += bid.amount_bet_exact * developer_fee
                result_types.append('win')
                win_flag = True

        # Only append 'lose' if nothing was won
        if not win_flag:
            result_types.append('lose')

        return total_return, ", ".join(result_types)

    def get_winning_side(self, total, for_db=False):
        if 2 <= total <= 6:
            return 'DOWN' if for_db else 'down'
        if total == 7:
            return 'MIDDLE' if for_db else 'middle'
        if 8 <= total <= 12:
            return 'UP' if for_db else 'up'
        return None

    def update_player_balance(self, player, amount):  
        player.coins += amount
        player.save()
  
    async def start_new_round(self):
        await self.update_round_status(Dice_GameRound.RoundStatus_dice.COMPLETED)
        if self.current_round.status == Dice_GameRound.RoundStatus_dice.COMPLETED:
            self.current_round = await self.create_new_round()
        await self.broadcast_new_round() 
    
    @database_sync_to_async
    def update_round_status(self, status, **kwargs):
        self.current_round.status = status
        for key, value in kwargs.items():
            setattr(self.current_round, key, value)
        self.current_round.save()

    async def receive(self, text_data): 
        if self.user.is_anonymous:
            await self.send_error("Authentication required")
            return 
        try:
            data = json.loads(text_data)
            if data['action'] == 'place_bid':
                await self.handle_place_bid(data)
            elif data['action'] == 'get_state':
                await self.send_initial_state()
            else:
                await self.send_error("Invalid action")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error("Server error")
  
    async def handle_place_bid(self, data):
        try: 
            if not await self.validate_bid_data(data):
                return

            success = await self.process_bid(data)
            if not success:
                return

            await self.send_balance_update()
            await self.broadcast_bid_update()

        except Exception as e:
            await self.send_error(str(e))
    
    async def broadcast_bid_update(self):
        totals = await self.get_bid_totals()
        user_bets = await self.get_user_bets()
        participants = await self.get_participants()
        
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'bids.update',
            'totals': totals,
            'user_bets': user_bets,
            'participants': participants,
            'multiplier_info': {
                'exact_jackpots': self.current_round.exact_number_on_multiplyer,
                'multipliers': self.current_round.multiplyer_number
            }
        })
         
    @database_sync_to_async
    def get_user_bets(self):
        if not self.current_round:
            return {
                'side_bets': {'DOWN': 0, 'MIDDLE': 0, 'UP': 0},
                'exact_bets': {}
            }
        
        try:
            bid = Dice_PlayerBid.objects.get(
                round=self.current_round,
                player=self.player
            )
            side_bets = {
                'DOWN': bid.amount_bet_side if bid.side == 'DOWN' else 0,
                'MIDDLE': bid.amount_bet_side if bid.side == 'MIDDLE' else 0,
                'UP': bid.amount_bet_side if bid.side == 'UP' else 0
            }
            
            exact_bets = {}
            if bid.exact_number:
                exact_bets[str(bid.exact_number)] = bid.amount_bet_exact
                
            return {
                'side_bets': side_bets,
                'exact_bets': exact_bets
            }
            
        except Dice_PlayerBid.DoesNotExist:
            return {
                'side_bets': {'DOWN': 0, 'MIDDLE': 0, 'UP': 0},
                'exact_bets': {}
            }
      
    @database_sync_to_async
    def get_participants(self):
        if not self.current_round:
            return []
        
        participants = []
        bids = Dice_PlayerBid.objects.filter(
            round=self.current_round
        ).exclude(
            Q(side__isnull=True) & Q(exact_number__isnull=True)
        ).select_related('player__user')
        
        for bid in bids:
            auth_token = bid.player.user.auth_token
            fullname = bid.player.user.db_fullname
            is_current_user = (bid.player == self.player)
            
            if bid.side:
                participants.append({
                    'type': 'side',
                    'auth_token': auth_token,
                    'fullname': fullname,
                    'position': bid.side,
                    'amount': bid.amount_bet_side,
                    'is_current_user': is_current_user
                })
                
            if bid.exact_number:
                participants.append({
                    'type': 'exact',
                    'auth_token': auth_token,
                    'fullname': fullname,
                    'position': bid.exact_number,
                    'amount': bid.amount_bet_exact,
                    'is_current_user': is_current_user
                })
        
        return participants
    
    @database_sync_to_async
    def create_bid(self, side, amount, exact_number):
        try:
            with transaction.atomic():
                player = Player.objects.select_for_update().get(id=self.player.id)
                current_round = Dice_GameRound.objects.select_for_update().get(id=self.current_round.id)

                amount_side = amount if side is not None else 0
                amount_exact = amount if exact_number is not None else 0
                total_deduction = amount_side + amount_exact

                if player.coins < total_deduction:
                    raise ValueError("Insufficient balance")
 
                bid, created = Dice_PlayerBid.objects.select_for_update().get_or_create(
                    player=player,
                    round=current_round
                )

                if created:
                    bid.amount_bet_side = 0
                    bid.amount_bet_exact = 0


                if side is not None:
                    bid.side = side
                    bid.amount_bet_side += amount_side

                if exact_number is not None:
                    bid.exact_number = exact_number
                    bid.amount_bet_exact += amount_exact

                bid.save()
                
                player.coins -= total_deduction
                player.save()
                

                return True
        except Exception as e:
            print(f"Bid creation error: {str(e)}")
            raise e
 
    async def process_bid(self, data): 
        return await self.create_bid(
            data.get('side'),
            data.get('amount'),
            data.get('exact_number')
        )
    
    @database_sync_to_async
    def validate_bid_data(self, data):
        if not data.get('side') and not data.get('exact_number'):
            raise ValueError("Select a valid betting option")
        required_fields = ['amount', 'side', 'exact_number']
        if not all(field in data for field in required_fields):
            raise ValueError("Missing required fields")
        
        if not isinstance(data['amount'], int) or data['amount'] <= 0:
            raise ValueError("Invalid bid amount")
            
        if data['side'] not in ['DOWN', 'MIDDLE', 'UP'] and not data['exact_number']:
            raise ValueError("Select a valid betting option")
            
        return True

    @database_sync_to_async
    def determine_current_phase(self):
        if not self.current_round:
            return 'waiting'
            
        return self.current_round.status.lower()

    def get_current_bets(self):
        return list(Dice_PlayerBid.objects.filter(
            round=self.current_round
        ).values('side', 'exact_number', 'amount_bet_side', 'amount_bet_exact', 'player__user__username'))
  
    @database_sync_to_async
    def get_bid_totals(self):
        totals = {'DOWN': 0, 'MIDDLE': 0, 'UP': 0, 'EXACT': {}}
         
        side_totals = Dice_PlayerBid.objects.filter(
            round=self.current_round
        ).exclude(side__isnull=True).values('side').annotate(
            total=Sum('amount_bet_side')
        )
        
        for item in side_totals:
            totals[item['side']] = item['total']
            
            
        exact_bets = Dice_PlayerBid.objects.filter(
            round=self.current_round
        ).exclude(exact_number__isnull=True).values('exact_number').annotate(
            total=Sum('amount_bet_exact')
        )
        
        for bet in exact_bets:
            totals['EXACT'][str(bet['exact_number'])] = bet['total']
        
        return totals

    async def broadcast_timer(self, remaining, phase):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'timer_update',
            'timer': remaining,
            'phase': phase,
            'multiplier_info': {
                'exact_jackpots': self.current_round.exact_number_on_multiplyer,
                'multipliers': self.current_round.multiplyer_number
            }
        }) 

    async def broadcast_bids_update(self):
        totals = await database_sync_to_async(self.get_bid_totals)()
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'bids.update',
            'totals': totals
        })
    
    async def broadcast_results(self, dice1, dice2, total, winning_side, player_results):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'results',
            'dice1': dice1,
            'dice2': dice2,
            'total': total,
            'winning_side': winning_side,
            'player_results': player_results,
            'multiplier_info': {
                'exact_jackpots': self.current_round.exact_number_on_multiplyer,
                'multipliers': self.current_round.multiplyer_number
            }
        })

    async def broadcast_new_round(self):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'round.start'
        })
   
    async def send_initial_state(self):
        if not self.current_round:
            await self.initialize_game()
            return

        await self.refresh_game_state()
        totals = await self.get_bid_totals()
        user_bets = await self.get_user_bets()
        participants = await self.get_participants()
                
        now = timezone.now()
        if self.current_round.status == Dice_GameRound.RoundStatus_dice.ACTIVE:
            elapsed = (now - self.current_round.start_time).total_seconds()
            remaining = max(0, self.ROUND_DURATION - int(elapsed))
            phase = 'bidding'
        else:  
            if self.current_round.result_start:
                elapsed = (now - self.current_round.result_start).total_seconds()
                remaining = max(0, self.RESULT_DURATION - int(elapsed))
            else:
                remaining = self.RESULT_DURATION
            phase = 'results'
        
        print(f"Sending initial state: {totals=}, {len(participants)=}, {phase=}")
        
        await self.send(json.dumps({
            'type': 'initial_state',
            'round_id': self.current_round.id,
            'bids': {
                'totals': totals,
                'user_bets': user_bets,
                'participants': participants
            },
            'timer': {
                'remaining': remaining,
                'phase': phase
            },
            'current_user': self.user.db_fullname,
            'auth_token': self.user.auth_token,
            'multiplier_info': {
                'exact_jackpots': self.current_round.exact_number_on_multiplyer,
                'multipliers': self.current_round.multiplyer_number
            }
        }))
        
    @database_sync_to_async
    def get_remaining_time(self):
        if not self.current_round:
            return 0
            
        now = timezone.now()
        
        if self.current_round.status == Dice_GameRound.RoundStatus_dice.ACTIVE:
            elapsed = (now - self.current_round.start_time).total_seconds()
            return max(0, self.ROUND_DURATION - int(elapsed))
        elif self.current_round.status == Dice_GameRound.RoundStatus_dice.RESULTS:
            elapsed = (now - self.current_round.result_start).total_seconds()
            return max(0, self.RESULT_DURATION - int(elapsed))
        return 0

    async def send_error(self, message):
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))
     
    async def timer_update(self, event):
        await self.send(text_data=json.dumps(event))
  
    async def bids_update(self, event): 
        await self.send(text_data=json.dumps({
            'type': 'bids_update',
            'totals': event['totals'],
            'user_bets': event['user_bets'],
            'participants': event['participants'],
            'multiplier_info': event['multiplier_info']  # ADD THIS LINE
        }))

    async def results(self, event):
        await self.send(text_data=json.dumps(event))

    async def round_start(self, event):
        await self.send_initial_state()
 
