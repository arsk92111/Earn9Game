# consumers.py
import json, random, asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from GameApp.models import SpinWheelRound
from AccountApp.models import db_Profile, Player, Transaction

class SpinWheelConsumer(AsyncWebsocketConsumer):
    ACTIVE_ROUND = None
    TIMER_TASK = None
    ROUND_DURATION = 10 

    @staticmethod
    def weighted_choice(choices):
        values, weights = zip(*choices)
        return random.choices(values, weights=weights, k=1)[0]

    BOX_PRIZES = {
        "Gold": lambda: SpinWheelConsumer.weighted_choice([
            (random.randint(250, 275), 60),
            (random.randint(276, 300), 22),
            (random.randint(301, 350), 10),
            (random.randint(351, 400), 5),
            (random.randint(401, 450), 2),
            (random.randint(451, 500), 1),
        ]),

        "Platinum": lambda: SpinWheelConsumer.weighted_choice([
            (random.randint(400, 425), 60),
            (random.randint(426, 450), 22),
            (random.randint(451, 500), 11),
            (random.randint(501, 525), 6),
            (random.randint(536, 550), 2),
            (random.randint(551, 600), 1),
        ]),

        "Diamond": lambda: SpinWheelConsumer.weighted_choice([
            (random.randint(600, 625), 75),
            (random.randint(626, 650), 13),
            (random.randint(651, 700), 6),
            (random.randint(701, 725), 3),
            (random.randint(736, 750), 2),
            (random.randint(751, 800), 1),
        ]),

        "Mystery": lambda: SpinWheelConsumer.weighted_choice([
            (0, 25),
            (1, 25),
            (10, 12),
            (20, 8),
            (50, 7),
            (70, 6),
            (100, 5),
            (150, 4),
            (200, 3),
            (300, 2),
            (500, 1),
            (750, 1),
            (850, 0.5),
            (1000, 0.5),
        ])
    }
    
    async def connect(self):
        await self.accept()
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.player = await self.get_player()
        if not self.player:
            await self.close(code=4002)
            return

        # Check for existing active round
        self.ACTIVE_ROUND = await self.get_active_round()
        await self.send_initial_state()


    # @staticmethod
    # def weighted_prize_choice():
    #     choices = [
    #         ("0", 4),
    #         ("50", 4),
    #         ("100", 1),
    #         ("250", 5),
    #         ("Gold", 5),
    #         ("Platinum", 5),
    #         ("Diamond", 5),
    #         ("Mystery", 75),
    #     ]
    #     values, weights = zip(*choices)
    #     return random.choices(values, weights=weights, k=1)[0]

    @staticmethod
    def weighted_prize_choice():
        choices = [
            ("0", 50),
            ("50", 25),
            ("100", 13),
            ("250", 6),
            ("Gold", 3),
            ("Platinum", 1),
            ("Diamond", 0.5),
            ("Mystery", 1.5),
        ]
        values, weights = zip(*choices)
        return random.choices(values, weights=weights, k=1)[0]

    @database_sync_to_async
    def get_active_round(self):
        try:
            return SpinWheelRound.objects.get(
                player=self.player,
                status__in=["ACTIVE", "SPIN", "RESULT"]
            )
        except SpinWheelRound.DoesNotExist:
            return None
 
    @database_sync_to_async
    def get_player(self):
        try:
            return Player.objects.get(user=self.user)
        except Player.DoesNotExist:
            return None
 
    async def send_initial_state(self):
        if self.ACTIVE_ROUND:
            await self.send(json.dumps({
                'type': 'round_update',
                'status': self.ACTIVE_ROUND.status,
                'timer': self.ACTIVE_ROUND.timer,
                'prize': self.ACTIVE_ROUND.game_randomly_prize
            }))
            
            # If we're in the middle of a round, restart the timer
            if self.ACTIVE_ROUND.status in ["ACTIVE", "SPIN", "RESULT"]:
                await self.start_round_timer()
        else:
            await self.send(json.dumps({
                'type': 'status',
                'message': 'READY'
            }))
        
        # Always send history
        await self.send_history()
 
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'spin':
            if self.ACTIVE_ROUND:
                # await self.send_error("Round already active")
                return

            if not await self.deduct_coins(100):
                await self.send_error("Insufficient balance")
                return

            self.ACTIVE_ROUND = await self.create_round()
            # Immediately set status to SPIN
            await self.update_round_status("SPIN")
            await self.send(json.dumps({
                'type': 'round_update',
                'status': "SPIN",  # Send SPIN status immediately
                'timer': self.ROUND_DURATION,
                'prize': ''
            }))
            await self.start_round_timer()
 
    @database_sync_to_async
    def update_round_status(self, status):
        if self.ACTIVE_ROUND:
            self.ACTIVE_ROUND.status = status
            self.ACTIVE_ROUND.save(update_fields=['status'])
 
    @database_sync_to_async
    def deduct_coins(self, amount):
        if self.player.coins < amount:
            return False
        self.player.coins -= amount
        self.player.save()
        return True

    @database_sync_to_async
    def create_round(self):
        return SpinWheelRound.objects.create(
            player=self.player,
            status="ACTIVE",
            amount_bet=100,
            timer=self.ROUND_DURATION,
            game_randomly_prize=''
        )
 
    async def start_round_timer(self):
        if self.TIMER_TASK and not self.TIMER_TASK.done():
            self.TIMER_TASK.cancel()
            
        self.TIMER_TASK = asyncio.create_task(self.run_round_timer())
 
    async def run_round_timer(self):
        try:
            # Start from current timer value
            timer = self.ROUND_DURATION
            if self.ACTIVE_ROUND:
                timer = self.ACTIVE_ROUND.timer
            
            while timer >= 0 and self.ACTIVE_ROUND:  # Add active round check
                # Update timer in database
                await self.update_timer(timer)
                
                # Send update to client
                await self.send(json.dumps({
                    'type': 'round_update',
                    'status': self.ACTIVE_ROUND.status,
                    'timer': timer,
                    'prize': self.ACTIVE_ROUND.game_randomly_prize
                }))
                
                # Handle game events
                if timer == 5:
                    await self.determine_prize()
                    # Check if round was completed by determine_prize
                    if not self.ACTIVE_ROUND:
                        break
                    
                if timer == 0:
                    if self.ACTIVE_ROUND and self.ACTIVE_ROUND.status == "RESULT":
                        await self.finalize_round()
                    break
                    
                await asyncio.sleep(1)
                timer -= 1
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Timer error: {str(e)}")
        finally:
            self.TIMER_TASK = None
 
    @database_sync_to_async
    def update_timer(self, timer):
        if self.ACTIVE_ROUND:
            self.ACTIVE_ROUND.timer = timer
            self.ACTIVE_ROUND.save(update_fields=['timer'])
 
    async def determine_prize(self):
        if not self.ACTIVE_ROUND:
            return
            
        prize = self.weighted_prize_choice()  # Use weighted selection

        await self.update_round_prize(prize) 
        if prize in ["0", "50", "100", "250"]:
            coins = int(prize)
            await self.award_coins(coins)
            await self.complete_round(coins, None)
            await self.send_prize_result(prize, coins)
        else:  
            await self.update_round_status("RESULT")
            await self.send_box_reveal(prize)
   
    async def send_history(self):
        history = await self.get_spin_history()
        await self.send(json.dumps({
            'type': 'spin_history',
            'history': history
        }))

    @database_sync_to_async
    def get_spin_history(self):
        if not self.player:
            return []
            
        history = SpinWheelRound.objects.filter(
            player=self.player,
            status="COMPLETED"
        ).order_by('-created_at')[:10]
        
        results = []
        for item in history:
            if item.prize_coins:
                results.append({
                    'prize': f"{item.prize_coins} Coins",
                    'coins': int(item.prize_coins),
                    'time': item.created_at.strftime("%H:%M:%S")
                })
            elif item.prize_in_side_box:
                results.append({
                    'prize': f"{item.game_randomly_prize} Box",
                    'coins': int(item.prize_in_side_box),
                    'time': item.created_at.strftime("%H:%M:%S")
                })
        return results
    
    @database_sync_to_async
    def update_round_prize(self, prize):
        if self.ACTIVE_ROUND:
            self.ACTIVE_ROUND.game_randomly_prize = prize
            self.ACTIVE_ROUND.save(update_fields=['game_randomly_prize'])
    
    async def finalize_round(self):
        if self.ACTIVE_ROUND and self.ACTIVE_ROUND.status == "RESULT":
            box_type = self.ACTIVE_ROUND.game_randomly_prize
            prize_coins = self.BOX_PRIZES[box_type]()
            await self.award_coins(prize_coins)
            await self.complete_round(prize_coins, box_type)
            await self.send_box_opened(box_type, prize_coins)
 
    @database_sync_to_async
    def award_coins(self, amount):
        if self.player:
            self.player.coins += amount
            self.player.save()
 
    @database_sync_to_async
    def complete_round(self, prize_coins, is_box):
        if self.ACTIVE_ROUND:
            self.ACTIVE_ROUND.status = "COMPLETED"
            
            if is_box:
                self.ACTIVE_ROUND.prize_in_side_box = str(prize_coins)
            else:
                self.ACTIVE_ROUND.prize_coins = str(prize_coins)
                
            self.ACTIVE_ROUND.save()
            self.ACTIVE_ROUND = None

    async def send_prize_result(self, prize, coins):
        await self.send(json.dumps({
            'type': 'prize_result',
            'prize': prize,
            'coins': coins
        }))

    async def send_box_reveal(self, box_type):
        await self.send(json.dumps({
            'type': 'box_reveal',
            'box_type': box_type
        }))

    async def send_box_opened(self, box_type, coins):
        await self.send(json.dumps({
            'type': 'box_opened',
            'box_type': box_type,
            'coins': coins
        }))

    async def send_error(self, message):
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))

    async def disconnect(self, close_code):
        if self.TIMER_TASK:
            self.TIMER_TASK.cancel()
            try:
                await self.TIMER_TASK
            except asyncio.CancelledError:
                pass


