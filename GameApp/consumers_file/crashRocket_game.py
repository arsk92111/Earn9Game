import asyncio, json, random
from django.db.models import Sum, F, Q
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db import IntegrityError, transaction 
from asgiref.sync import sync_to_async  
from AccountApp.models import db_Profile, Player, Transaction
from GameApp.models import RocketGame, RocketGameRound, RocketPlayerBid, RocketPlayerResult
 
class RocketGameConsumer(AsyncWebsocketConsumer):
    ROUND_DURATION = 25  
    RESULT_DURATION = 5 
    FLIGHT_SPEED = 0.1 
    GAME_GROUP = "live_rocket_game"
    
    _active_connections = set()
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
        # asyncio.create_task(self.websocket_heartbeat())

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
 
    async def websocket_heartbeat(self):
        while self.connected:
            try:
                await self.send(json.dumps({'type': 'heartbeat'}))
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

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            if action == "place_bet":
                await self.handle_place_bet(data)
            elif action == "change_guess":
                await self.handle_change_guess(data)
            elif action == "get_state":
                await self.send_initial_state()
            else:
                pass
                # await self.send_error("Invalid action")
        # except json.JSONDecodeError:
        #     await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error(str(e))

    async def initialize_game(self):
        self.game = await self.get_or_create_game()
        self.current_round = await self.get_active_round(self.game)
         
        if not self.current_round:
            self.current_round = await self.create_new_round()
            await self.broadcast_new_round()

    @database_sync_to_async
    def get_or_create_game(self):
        return RocketGame.objects.get_or_create(name="Live Rokcet Crash")[0]
    
    @database_sync_to_async
    def get_global_game(self):
        return RocketGame.objects.get_or_create(name="Live Rokcet Crash")[0]

    @database_sync_to_async
    def get_active_round(self, game):
        return RocketGameRound.objects.filter(
            game=game,
            status__in=[
                RocketGameRound.RoundStatus_Rocket.WAITING,
                RocketGameRound.RoundStatus_Rocket.FLY
            ]
        ).order_by('-start_time').first()  
    
    @database_sync_to_async
    def create_new_round(self):
        with transaction.atomic(): 
            RocketGameRound.objects.filter(
                game=self.game,
                status__in=[
                    RocketGameRound.RoundStatus_Rocket.WAITING,
                    RocketGameRound.RoundStatus_Rocket.FLY
                ]
            ).update(
                status=RocketGameRound.RoundStatus_Rocket.COMPLETED,
                end_time=timezone.now()
            )

            crash_point = self.random_number()
    
            default_state = {
                "current_multiplier": 0.01,
                "position_coordinate": {"x": 0, "y": 0}, 
            }

            new_round = RocketGameRound.objects.create(
                game=self.game,
                status=RocketGameRound.RoundStatus_Rocket.WAITING,
                start_time=timezone.now(),
                random_number_flee=crash_point,
                state_Rocket=default_state  
            )

            self.game.current_round = new_round
            self.game.current_bid = 0
            self.game.save()

            return new_round
    
    # def random_number(self):
    #         rand_num = round(random.uniform(0.01, 12.00), 2)
    #         return rand_num
    
    def random_number(self):
        ranges = [
            (0.01, 0.99),    # 64%
            (1.00, 2.00),    # 18%
            (2.01, 5.00),    # 9%
            (5.01, 8.00),    # 5%
            (8.01, 15.00),   # 2.5%
            (15.01, 20.00),  # 1%
            (20.01, 50.00),  # 0.4%
            (50.01, 100.00)  # 0.1%
        ]

        weights = [64, 18, 9, 5, 2.5, 1, 0.4, 0.1]  # Must sum to 100%
        
        selected_range = random.choices(ranges, weights = weights, k=1)[0]
        rand_num = round(random.uniform(selected_range[0], selected_range[1]), 2)
        return rand_num

    async def ensure_timer_running(self):
        async with self._timer_lock:
            if self._timer_task and not self._timer_task.done():
                return
                 
            self._timer_task = asyncio.create_task(self.global_timer_loop())

    async def global_timer_loop(self):
        while True:
            try:
                game = await self.get_global_game()
                active_round = await self.get_active_round(game)
                
                if not active_round:
                    await asyncio.sleep(1)
                    continue
                
                now = timezone.now()
                status = active_round.status
                
                if status == RocketGameRound.RoundStatus_Rocket.WAITING:
                    elapsed = (now - active_round.start_time).total_seconds()
                    remaining = max(0, self.ROUND_DURATION - int(elapsed))
                    
                    await self.broadcast_timer(remaining, 'waiting')
                    
                    if remaining <= 0: 
                        self.current_round = await self.get_round_by_id(active_round.id)
                        await self.start_flight_phase()
                
                elif status == RocketGameRound.RoundStatus_Rocket.FLY: 
                    await asyncio.sleep(0.1)
                    await self.broadcast_timer(0, 'fly')
                elif active_round.random_number_flee <= active_round.state_Rocket['current_multiplier']:
                    await self.start_new_round()
                
                elif status == RocketGameRound.RoundStatus_Rocket.COMPLETED:  
                    if active_round.end_time:
                        elapsed = (now - active_round.end_time).total_seconds()
                        remaining = max(0, self.RESULT_DURATION - int(elapsed))
                        
                        await self.broadcast_timer(remaining, 'results')
                        
                        if remaining <= 0:
                            await self.start_new_round()
                
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Global timer error: {e}")
                await asyncio.sleep(1)
                
    
    @database_sync_to_async
    def update_result_start(self, round_id, time): 
        with transaction.atomic():
            round_obj = RocketGameRound.objects.select_for_update().get(id=round_id)
            if not round_obj.result_start:
                round_obj.result_start = time
                round_obj.save()
    
    async def start_flight_phase(self): 
        round_id = self.current_round.id if self.current_round else None
          
        await database_sync_to_async(
            RocketGameRound.objects.filter(pk=round_id).update
        )(
            status=RocketGameRound.RoundStatus_Rocket.FLY
        )
         
        if round_id:
            self.current_round = await self.get_round_by_id(round_id)
         
        if self.current_round:
            asyncio.create_task(self.simulate_flight())
    
    @database_sync_to_async
    def get_round_by_id(self, round_id):
        return RocketGameRound.objects.get(id=round_id)
    
    async def simulate_flight(self):
        try: 
            current_state = await database_sync_to_async(
                lambda: RocketGameRound.objects.get(pk=self.current_round.pk).state_Rocket
            )()
             
            multiplier = float(current_state.get("current_multiplier", 0.01))
            crash_point = float(self.current_round.random_number_flee) 
            progress = 0.01 
               
            while multiplier <= crash_point:
                await asyncio.sleep(0.1)
                multiplier = round(multiplier + 0.01, 2) 
                progress += 0.8  
                position = {"x": round(progress, 2), "y": round(progress, 2)} 
                 
                await self.update_flight_state(multiplier, position) 
                await self.channel_layer.group_send(
                        self.GAME_GROUP,
                        {
                            "type": "game.update",
                            "event": "flight",
                            "multiplier": multiplier,
                            "position": position
                        }
                ) 

                await self.handle_falling_value(multiplier)  
            await self.handle_rocket_crash(crash_point)

        except Exception as e: 
            import traceback
            traceback.print_exc() 
    
    async def update_flight_state(self, multiplier, position):   
        current_state = await database_sync_to_async(
            lambda: RocketGameRound.objects.get(pk=self.current_round.pk).state_Rocket
        )()
         
        current_state['current_multiplier'] = multiplier
        current_state['position_coordinate'] = position
         
        await database_sync_to_async(
            lambda: RocketGameRound.objects.filter(pk=self.current_round.pk).update(
                state_Rocket=current_state
            )
        )()
          
        await self.channel_layer.group_send(
            self.GAME_GROUP,
            {
                "type": "game.update",
                "event": "flight",
                "multiplier": multiplier,
                "position": position
            }
        ) 

    @database_sync_to_async
    def get_current_state(self): 
        self.current_round.refresh_from_db()
        return self.current_round.state_Rocket
    
    async def check_player_wins(self, bid, current_multiplier):  
            await self.process_win(bid, current_multiplier) 
    
    
    async def handle_falling_value(self, multiplier):  
        bids = await database_sync_to_async(list)(
            RocketPlayerBid.objects.filter(round=self.current_round).select_related('player__user')
        ) 

        falling_players = []

        for bid in bids:
            cashout_multiplier = (
                bid.mind_Change_user_guess
                if bid.mind_Change_user_guess is not None
                else bid.actual_user_guess
            )

            guess_used = float(cashout_multiplier) 
            if guess_used and float(multiplier) == guess_used: 
                result_exists = await database_sync_to_async(RocketPlayerResult.objects.filter(
                    player=bid.player, round = self.current_round, amount_bet = bid.amount_bet
                ).exists)() 

                if not result_exists: 
                    await self.check_player_wins(bid, multiplier) 
                    falling_players.append({
                        "fullname": bid.player.user.db_fullname,
                        "guess_used": str(guess_used)
                    })

        await self.channel_layer.group_send(
            self.GAME_GROUP,
            {
                "type": "falling_values",
                "players": falling_players
            }
        )
 
    async def falling_values(self, event):
        await self.send(json.dumps({
            "type": "falling_values",
            "players": event["players"]  # list of { fullname, guess_used }
        }))
 
    async def process_win(self, bid, multiplier): 
        guess_used = (
            bid.mind_Change_user_guess
            if bid.mind_Change_user_guess is not None
            else bid.actual_user_guess
        )

        cashout_multiplier = float(guess_used)
        winnings = float(bid.amount_bet) + ((float(bid.amount_bet) * cashout_multiplier) * 0.90)

        auth_token = await self.get_user_auth_token(bid.player)

        created = await self.create_player_result(bid.player, "win", winnings)

        if created:
            await self.broadcast_player_cashout(auth_token, cashout_multiplier)
            await self.add_coins_to_player(bid.player, winnings)
  
    @database_sync_to_async
    def create_player_result(self, player, result_type, amount):
        result, created = RocketPlayerResult.objects.get_or_create(
            player=player,
            round=self.current_round,
            defaults={
                'amount_bet': amount,
                'result_type': result_type
            }
        )
        return created
 
    @database_sync_to_async
    def get_active_bids(self):
        return list(RocketPlayerBid.objects.filter(
            round=self.current_round,
            mind_Change_user_guess__isnull=False
        ).select_related('player__user'))  
    
    @database_sync_to_async
    def get_user_auth_token(self, player):
        return player.user.auth_token
    
    async def broadcast_player_cashout(self, player_token, multiplier):
        await self.channel_layer.group_send(
            self.GAME_GROUP,
            {
                "type": "player.cashout",
                "player_token": player_token,
                "multiplier": multiplier
            }
        )
 
    async def player_cashout(self, event):
        await self.send(json.dumps({
            "type": "player.cashout",
            "player_token": event["player_token"],
            "multiplier": event["multiplier"]
        }))
 
    @database_sync_to_async
    def add_coins_to_player(self, player, amount):
        with transaction.atomic():
            player = Player.objects.select_for_update().get(pk=player.pk)
            player.coins += amount
            player.save()

    async def handle_rocket_crash(self, crash_point): 
        now = timezone.now() 
        await database_sync_to_async(
            lambda: RocketGameRound.objects.filter(pk=self.current_round.pk).update(
                status=RocketGameRound.RoundStatus_Rocket.COMPLETED,
                end_time=now
            )
        )()
        
        await self.process_remaining_players(crash_point) 
        await self.channel_layer.group_send(
            self.GAME_GROUP,
            {
                "type": "game.update",
                "event": "crash",
                "crash_point": crash_point
            }
        )

    async def process_remaining_players(self, crash_point): 
        bids = await self.get_remaining_bids()
        
        for bid in bids: 
            guess_used = (
            bid.mind_Change_user_guess
            if bid.mind_Change_user_guess is not None
            else bid.actual_user_guess
            )

            win_condition = float(guess_used)
            if win_condition and float(win_condition) > crash_point:
                await self.create_player_result(
                    bid.player,
                    "lose",
                    bid.amount_bet
                )

    @database_sync_to_async
    def get_remaining_bids(self):
        return list(RocketPlayerBid.objects.filter(
            round=self.current_round,
            mind_Change_user_guess__isnull=True
        ).select_related('player'))
 
    async def start_new_round(self):
        self.current_round = await self.create_new_round()
        await self.broadcast_new_round() 

    async def send_initial_state(self): 
        await database_sync_to_async(self.current_round.refresh_from_db)()
        
        state_rocket = self.current_round.state_Rocket or {}
        state = {
            "type": "game.state",
            "phase": self.current_round.status.lower(),
            "timer": await self.get_remaining_time(),
            "multiplier": float(state_rocket.get("current_multiplier", 0.01)),
            "position": state_rocket.get("position_coordinate", {"x": 0, "y": 0}),
            "player_state": state_rocket.get(self.user.auth_token, {}),
            "crash_point": float(self.current_round.random_number_flee) if self.current_round.status == RocketGameRound.RoundStatus_Rocket.COMPLETED else None,
            "total_bet": self.game.current_bid
        }
        await self.send(json.dumps(state))

    @database_sync_to_async
    def get_remaining_time(self):
        if not self.current_round:
            return 0
            
        now = timezone.now() 
        if self.current_round.status == RocketGameRound.RoundStatus_Rocket.WAITING:
            elapsed = (now - self.current_round.start_time).total_seconds()
            return max(0, self.ROUND_DURATION - int(elapsed))
        elif self.current_round.status == RocketGameRound.RoundStatus_Rocket.COMPLETED:
            if self.current_round.end_time: 
                elapsed = (now - self.current_round.end_time).total_seconds()
                return max(0, self.RESULT_DURATION - int(elapsed))
        return 0

    async def handle_place_bet(self, data):
        amount = data.get("amount")
        guess = data.get("guess")
        
        if not amount or not guess:
            await self.send_error("Missing amount or guess")
            return
             
        success = await self.create_player_bid(amount, guess) 
        if success:   
            await self.update_total_bet(amount) 
            await self.broadcast_bid_update()
             
            await self.send(json.dumps({
                "type": "bet.confirmed",
                "amount": amount,
                "guess": guess
            }))
        else:
            await self.send_error("Failed to place bet")
     
    @database_sync_to_async
    def create_player_bid(self, amount, guess):
        try:
            with transaction.atomic(): 
                amount = float(amount)
                guess = float(guess)
                player = Player.objects.select_for_update().get(pk=self.player.pk)
                 
                if player.coins < amount:
                    return False
                    
                player.coins -= amount
                player.save()
                 
                bid, created = RocketPlayerBid.objects.update_or_create(
                    player=player,
                    round=self.current_round,
                    defaults={
                        "amount_bet": amount,
                        "actual_user_guess": guess,
                        "mind_Change_user_guess": None
                    }
                )
                 
                RocketGame.objects.filter(pk=self.game.pk).update(
                    current_bid=F('current_bid') + amount
                )
                 
                self.game.refresh_from_db()
                
                return True
        except Exception as e:
            print(f"Error creating bid: {str(e)}")
            return False
        
    @database_sync_to_async
    def update_total_bet(self, amount): 
        RocketGame.objects.filter(pk=self.game.pk).update(
            current_bid=F('current_bid') + amount
        )
        self.game.refresh_from_db()
   
    async def handle_change_guess(self, data):
        MindChangeGuess = data.get("MindChangeGuess") 
        prop_MindChangeGuess = float(MindChangeGuess) + 0.02
        bid = await database_sync_to_async(
            RocketPlayerBid.objects.get
        )(player=self.player, round=self.current_round)
 
        if (bid.actual_user_guess is not None and prop_MindChangeGuess is not None and bid.mind_Change_user_guess is None ):
            if (float(prop_MindChangeGuess) < float(bid.actual_user_guess)) : 
                bid.mind_Change_user_guess = prop_MindChangeGuess
                await database_sync_to_async(bid.save)()

                await self.send(json.dumps({
                    "type": "guess.updated",
                    "multiplier": prop_MindChangeGuess
                }))
            else:
                await self.send(json.dumps({
                    "type": "guess.rejected",
                    "message": "Mind change guess must be less than the original guess."
                }))
        else:
            await self.send(json.dumps({
                "type": "guess.rejected",
                "message": "Original guess or new guess is missing."
            }))
   
    async def broadcast_timer(self, remaining, phase):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'timer_update',
            'timer': remaining,
            'phase': phase
        })

    async def broadcast_new_round(self):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'round.start'
        })

    async def broadcast_bid_update(self):
        total_bet = await self.get_total_bet()
        participants = await self.get_participants()
        
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'bids.update',
            'total_bet': total_bet,
            'participants': participants
        })

    @database_sync_to_async
    def get_total_bet(self):
        return float(self.game.current_bid)

    @database_sync_to_async
    def get_participants(self):
        participants = []
        bids = RocketPlayerBid.objects.filter(
            round=self.current_round
        ).select_related('player__user')
        
        for bid in bids:
            auth_token = bid.player.user.auth_token
            fullname = bid.player.user.db_fullname
            is_current_user = (bid.player == self.player)
            
            participants.append({
                'auth_token': auth_token,
                'fullname': fullname,
                'amount': float(bid.amount_bet),
                'actual_guess': float(bid.actual_user_guess) if bid.actual_user_guess else None, 
                'mind_change_guess': float(bid.mind_Change_user_guess) if bid.mind_Change_user_guess else None,  # Add this
                'is_current_user': is_current_user
            })
        
        return participants
    
    async def game_update(self, event):
        await self.send(json.dumps({
            "type": "game.update",
            "event": event["event"],
            "multiplier": event.get("multiplier"),
            "position": event.get("position"),
            "crash_point": event.get("crash_point")
        }))
 
    async def timer_update(self, event):
        await self.send(json.dumps(event))

    async def round_start(self, event):
        await self.send_initial_state()

    async def bids_update(self, event):
        await self.send(json.dumps({
            'type': 'bids_update',
            'total_bet': event['total_bet'],
            'participants': event['participants']
        }))

    async def send_error(self, message):
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))

