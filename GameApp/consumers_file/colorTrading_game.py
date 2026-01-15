#consumers.py 
from channels.db import database_sync_to_async 
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta 
import asyncio, json, random 
from asgiref.sync import sync_to_async   
from channels.generic.websocket import AsyncWebsocketConsumer 
from django.db import IntegrityError, transaction  
from GameApp.models import  ColorGame, ColorGameRound, ColorPlayerBid, ColorPlayerResult 
from AccountApp.models import db_Profile ,Player, Transaction
 

class ColorTradeGameConsumer(AsyncWebsocketConsumer):
    ROUND_DURATION = 50
    RESULT_DURATION = 10
    GAME_GROUP = "live_colorTrade_game"
    
    _timer_task = None
    _timer_lock = asyncio.Lock()
    _active_timer = False
    
    async def connect(self):
        await self.accept()
        if not await self.authenticate_user():
            return
            
        await self.channel_layer.group_add(self.GAME_GROUP, self.channel_name)
        await self.initialize_game()
        await self.ensure_timer_running()
        await self.send_initial_state()
        
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

    
    async def initialize_game(self):
        self.game = await self.get_or_create_game()
        self.current_round = await self.get_active_round()
        
        if not self.current_round:
            self.current_round = await self.create_new_round()

    @database_sync_to_async
    def get_or_create_game(self):
        try:
            return ColorGame.objects.get_or_create(name="Live Color Trading")[0]
        except Exception as e:
            print(f"Error getting/creating game: {e}") 
            return ColorGame.objects.create(name="Live Color Trading")
     
    @database_sync_to_async
    def get_active_round(self):
        return ColorGameRound.objects.filter(
            game=self.game,
            status__in=[
                ColorGameRound.RoundStatus_color.ACTIVE,
                ColorGameRound.RoundStatus_color.RESULTS
            ]
        ).first()
    
    
    @database_sync_to_async
    def create_new_round(self):
        with transaction.atomic():  
            existing_round = ColorGameRound.objects.filter(
                game=self.game,
                status=ColorGameRound.RoundStatus_color.WAITING
            ).first()
            
            if existing_round:
                return existing_round
                
            new_round = ColorGameRound.objects.create(
                game=self.game,
                status=ColorGameRound.RoundStatus_color.WAITING
            )
             
            self.game.current_round = new_round
            self.game.current_bid_total = {"COLOR": 0, "EXACT": 0, "SIZE": 0}
            self.game.save()
            
            return new_round  
    
    async def ensure_timer_running(self):
        async with self._timer_lock: 
            if self._active_timer:
                return
                
            if self._timer_task and not self._timer_task.done():
                return
                
            self._active_timer = True
            self._timer_task = asyncio.create_task(self.global_timer_loop())
    
    async def global_timer_loop(self): 
        try:
            while True:
                await self.refresh_game_state()
                
                now = timezone.now()
                status = self.current_round.status
                
                if status == ColorGameRound.RoundStatus_color.WAITING:  
                    await self.update_round_status(
                        ColorGameRound.RoundStatus_color.ACTIVE,
                        start_time=now
                    )
                  
                    await self.update_game_timer(self.ROUND_DURATION)
                    await self.broadcast_new_round()
                    
                elif status == ColorGameRound.RoundStatus_color.ACTIVE: 
                    elapsed = (now - self.current_round.start_time).total_seconds()
                    remaining = max(0, self.ROUND_DURATION - int(elapsed))
                     
                    await self.update_game_timer(remaining)
                    await self.broadcast_timer(remaining, 'bidding')
                    
                    if remaining <= 0: 
                        await self.process_bidding_end()
                
                elif status == ColorGameRound.RoundStatus_color.RESULTS: 
                    elapsed = (now - self.current_round.result_start).total_seconds()
                    remaining = max(0, self.RESULT_DURATION - int(elapsed))
                     
                    await self.update_game_timer(remaining)
                    await self.broadcast_timer(remaining, 'results')
                    
                    if remaining <= 0: 
                        await self.complete_round()
                        self.current_round = await self.create_new_round()
                        await self.broadcast_new_round()
                
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Timer error: {e}")
        finally: 
            async with self._timer_lock:
                self._active_timer = False
 
    @database_sync_to_async
    def refresh_game_state(self):
        self.game.refresh_from_db()
        self.current_round.refresh_from_db()
    
    @database_sync_to_async
    def update_round_status(self, status, **kwargs):
        self.current_round.status = status
        for key, value in kwargs.items():
            setattr(self.current_round, key, value)
        self.current_round.save()
    
    @database_sync_to_async
    def update_game_timer(self, timer):
        self.game.timer = timer
        self.game.save()
    
    async def process_bidding_end(self): 
        await self.update_round_status(
            ColorGameRound.RoundStatus_color.RESULTS,
            result_start=timezone.now()
        )
        
        random_num = random.randint(0, 9)
        await self.save_random_number(random_num)
        
        player_results = await self.calculate_results(random_num)
        await self.broadcast_results(random_num, player_results)
        
    @database_sync_to_async
    def save_random_number(self, number): 
        self.current_round.random_number = number
        self.current_round.save()
    
    @database_sync_to_async
    def calculate_results(self, random_number): 
        if ColorPlayerResult.objects.filter(round=self.current_round).exists():
            return []
        return self._calculate_results(random_number)
    
    def _calculate_results(self, random_number):
        if ColorPlayerResult.objects.filter(round=self.current_round).exists():
            return [] 
        player_results = []
        bids = ColorPlayerBid.objects.filter(round=self.current_round)
         
        winning_color = self.get_color_from_number(random_number)
        winning_size = "Small" if random_number < 5 else "Big"
        
        for bid in bids:
            player_detail = bid.player_detail
            win_amount = 0 
            developer_fee_exact = 0.90
            developer_fee_color = 0.70
            developer_fee_size = 0.40
            ColorBet = player_detail['amount_Bet_Color']
            SizeBet = player_detail['amount_Bet_Size']
            ExactBet = player_detail['amount_Bet_Exact_number']
            MultiColor = player_detail['multiplyer_number_Color']
            MultiSize = player_detail['multiplyer_number_Size']
            MultiExact = player_detail['multiplyer_number_Exact_number']

            is_color_win = player_detail['user_Select_Color'] == winning_color
            is_size_win = player_detail['user_Select_Size'] == winning_size
            is_exact_win = str(player_detail['user_Select_Exact_number']) == str(random_number)
            
            if is_color_win and ColorBet > 0:
                win_amount += self.calculate_win(ColorBet, MultiColor, developer_fee_color)

            if is_size_win and SizeBet > 0:
                win_amount += self.calculate_win(SizeBet, MultiSize, developer_fee_size)

            if is_exact_win and ExactBet > 0:
                win_amount += self.calculate_win(ExactBet, MultiExact, developer_fee_exact)
            
            total_bet = ( ColorBet +  SizeBet +  ExactBet )
            is_win = win_amount > 0

            print("\n\n is_winis_winis_win :", is_win)

            ColorPlayerResult.objects.create(
                player=bid.player,
                round=self.current_round,
                amount_bet_Color=ColorBet,
                amount_bet_Size=SizeBet,
                amount_bet_Exact_Number=ExactBet,
                amount_won_loss=win_amount if is_win else total_bet,
                result_type = "WIN" if is_win else "LOSE"
            )
 
            if is_win:
                bid.player.coins = F('coins') + win_amount
                bid.player.save()

            player_results.append({
                'player': str(bid.player.user.auth_token),
                'result_type': "WIN" if is_win else "LOSE",
                'net_amount': win_amount if is_win else total_bet 
            })
        return player_results
    
    def calculate_win(self, bet_amount, multiplier, fee):
        if multiplier == 1:
            return (bet_amount * 2 * fee) + bet_amount
        return (bet_amount * multiplier * fee) + bet_amount

    def get_color_from_number(self, number):
        color_map = {
            0: "Violet",
            1: "Green",
            2: "Red",
            3: "Green",
            4: "Red",
            5: "Violet",
            6: "Red",
            7: "Green",
            8: "Red",
            9: "Green"
        }
        return color_map.get(number, "Unknown")
    
    async def complete_round(self):
        await self.update_round_status(
            ColorGameRound.RoundStatus_color.COMPLETED,
            end_time=timezone.now()
        )
     
    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['action'] == 'place_bet':
            await self.handle_place_bet(data)
     
    async def handle_place_bet(self, data):
        success = await self.process_bet(
            data['bet_type'],
            data['selection'],
            data['amount'],
            data['multiplier']
        )
        
        if success: 
            bid_details = await self.get_user_bid_details()
            await self.send(json.dumps({
                'type': 'bet_success',
                'bid_details': bid_details  # Send back updated bid details
            }))
            await self.broadcast_bid_update()
        else:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Failed to place bet. Check your balance.'
            }))
        
    @database_sync_to_async
    def process_bet(self, bet_type, selection, amount, multiplier):
        try:
            with transaction.atomic(): 
                bid, created = ColorPlayerBid.objects.get_or_create(
                    player=self.player,
                    round=self.current_round,
                    defaults={'player_detail': self.default_player_detail()}
                )
                
                player_detail = bid.player_detail
                total_bet = 0
                 
                if bet_type == 'COLOR':
                    player_detail['user_Select_Color'] = selection
                    player_detail['amount_Bet_Color'] = amount * multiplier
                    player_detail['multiplyer_number_Color'] = multiplier
                    total_bet = amount * multiplier
                elif bet_type == 'SIZE':
                    player_detail['user_Select_Size'] = selection
                    player_detail['amount_Bet_Size'] = amount * multiplier
                    player_detail['multiplyer_number_Size'] = multiplier
                    total_bet = amount * multiplier
                elif bet_type == 'EXACT':
                    player_detail['user_Select_Exact_number'] = selection
                    player_detail['amount_Bet_Exact_number'] = amount * multiplier
                    player_detail['multiplyer_number_Exact_number'] = multiplier
                    total_bet = amount * multiplier
                
                if self.player.coins < total_bet:
                    return False
                
                self.player.coins -= total_bet
                self.player.save()
                
                bid.player_detail = player_detail
                bid.save()
                 
                self.game.current_bid_total[bet_type] += amount
                self.game.save()
                
                return True
        except Exception as e:
            print(f"Bet error: {e}")
            return False

    def default_player_detail(self):
        return {
            "player_id": self.player.user.auth_token,
            'multiplyer_number_Color': 1, 
            'user_Select_Color': '',
            'amount_Bet_Color': 0,
            'multiplyer_number_Size': 1,
            'user_Select_Size': '',
            'amount_Bet_Size': 0,
            'multiplyer_number_Exact_number': 1,
            'user_Select_Exact_number': '',
            'amount_Bet_Exact_number': 0, 
        }
     
    async def broadcast_timer(self, remaining, phase):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'timer_update',
            'timer': remaining,
            'phase': phase
        })
    
    async def broadcast_new_round(self):
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'round_start',
            'round_id': self.current_round._game_id  # Send _game_id instead of id
        })
        
    async def broadcast_bid_update(self):
        totals = await database_sync_to_async(
            lambda: self.game.current_bid_total
        )()
        
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'type': 'bid_update',
            'totals': totals
        })
    
    async def broadcast_results(self, random_number, player_results):
        color = self.get_color_from_number(random_number)
        size = "Small" if random_number < 5 else "Big"
        
        # Get the latest history including this result
        history = await self.get_history_data()
        
        await self.channel_layer.group_send(self.GAME_GROUP, {
            'round_id': self.current_round._game_id, 
            'type': 'results',
            'random_number': random_number,
            'winning_color': color,
            'winning_size': size,
            'player_results': player_results,
            'history': history  # Include updated history
        })

    @database_sync_to_async
    def get_user_bid_details(self):
        try:
            bid = ColorPlayerBid.objects.get(
                player=self.player,
                round=self.current_round
            )
            return bid.player_detail
        except ColorPlayerBid.DoesNotExist:
            return None

    async def send_initial_state(self):
        history = await self.get_history_data()
        user_bid = await self.get_user_bid_details()
        
        await self.send(json.dumps({
            'type': 'initial_state',
            'timer': self.game.timer,
            'phase': self.current_round.status.lower(),
            'totals': self.game.current_bid_total,
            'round_id': self.current_round._game_id,
            'history': history,
            'user_bid': user_bid  # Include user's current bid details
        }))
    
    @database_sync_to_async
    def get_history_data(self):
        completed_rounds = ColorGameRound.objects.filter(
            status=ColorGameRound.RoundStatus_color.COMPLETED
        ).order_by('-id')[:10]
        
        return [{
            'game_id': round._game_id,
            'number': round.random_number,
            'size': "Small" if round.random_number < 5 else "Big",
            'color': self.get_color_from_number(round.random_number)
        } for round in completed_rounds]
     
    async def timer_update(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def round_start(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def bid_update(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def results(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GAME_GROUP, self.channel_name)

