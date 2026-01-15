# models.py 
import datetime, random
from django.utils import timezone  
from django.db import models
from django.conf import settings
from AccountApp.models import db_Profile, Player, Transaction
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField  # or models.JSONField in Django 3.1+
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.db.models import JSONField
from datetime import datetime

User = get_user_model()

 
# ******************************  Card Game **************************
class GameManager(models.Manager):
    def current_game(self):
        return self.get_or_create(name="Live Card Battle")[0]
 
class Game(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    current_round = models.ForeignKey('GameRound', null=True, blank=True, on_delete=models.SET_NULL, related_name='current_game_round')
    current_bid = models.JSONField(default=dict, blank=True)
    timer = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return str(self.id) + " | " +  self.name
 
class GameRound(models.Model): 
    class RoundStatus(models.TextChoices):
        WAITING = 'WAIT', 'Waiting'
        ACTIVE = 'ACTIVE', 'Active'
        RESULTS = 'RESULTS', 'Showing Results'
        COMPLETED = 'DONE', 'Completed'

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rounds')
    card = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=RoundStatus.choices, default=RoundStatus.WAITING)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    timer = models.IntegerField(default=0)
    result_duration = models.PositiveIntegerField(default=3)
    result_start = models.DateTimeField(null=True)
    
    def __str__(self): 
            return str(self.id) + " | " + self.game.name
    
    def save(self, *args, **kwargs): 
        if self.status != self.RoundStatus.ACTIVE and self.end_time is None:
            self.end_time = timezone.now()
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.status == self.RoundStatus.COMPLETED and not self.end_time:
            self.end_time = timezone.now()
        super().save(*args, **kwargs)
  
class PlayerBid(models.Model):
    class BidSide(models.TextChoices):
        NUMBER = 'NUM', 'Number'
        PICTURE = 'PIC', 'Picture'
    class Meta:
        indexes = [
            models.Index(fields=['round', 'side']),
            models.Index(fields=['player', 'round']),
        ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='bids')
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name='bids')
    amount = models.PositiveIntegerField()
    side = models.CharField(max_length=3, choices=BidSide.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)

    class Meta:
        unique_together = ('player', 'round')
 
class PlayerResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE)
    amount_bet = models.IntegerField()
    amount_won_loss = models.IntegerField() 
    result_type = models.CharField(max_length=20) # win/lose
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email + " | " + self.round.game.name
        return (self.player.user.db_phone_number or str(self.player.user.id)) + " | " + self.round.game.name
 
# ******************************   FootBall Game **************************
def default_player_detail(player_token=None):
    return {
        "player_id": player_token if player_token else None,
        'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
        'ended_at': '',
        'score': 0,
        'is_turn_done': False,
        'keeper_state': 'standing',
        'vertical': 0.0,
        'horizontal': 0.0,
        'power': 0.0,
        'ball_x': 0.00,
        'ball_y': 0.00, 
        'is_goalMe': False
    }

class FootballGame(models.Model):
    player_a = models.ForeignKey(db_Profile, related_name='games_as_a', on_delete=models.CASCADE)
    player_a_bet_amount = models.PositiveIntegerField()
    player_b = models.ForeignKey(db_Profile, related_name='games_as_b', on_delete=models.CASCADE, null=True, blank=True) 
    player_b_bet_amount = models.PositiveIntegerField(null=True, blank=True) 

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('active', 'Active'),
        ('expired', 'Expired')
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='waiting') 
    player_a_channel = models.CharField(max_length=255, blank=True)
    player_b_channel = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return str(self.id) 
 
class FootballRound(models.Model):
    game = models.ForeignKey(FootballGame, on_delete=models.CASCADE, related_name='rounds')
    round_status = models.CharField(max_length=50, choices=[ 
        ('PLAYER_A_TURN', 'Player A Turn'),
        ('PLAYER_B_TURN', 'Player B Turn'),
        ('RESULT', 'Result'),
        ('EXPIRED', 'Expired')
    ])  

    player_a_detail = JSONField(max_length=100000, default=default_player_detail)
    player_b_detail = JSONField(max_length=100000, default=default_player_detail)  
    timer_remaining = models.PositiveIntegerField(default=25)
    current_player = models.ForeignKey(db_Profile, on_delete=models.CASCADE)  
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return  str(self.id)  
     
class FootBallResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(FootballRound, on_delete=models.CASCADE) 
    amount_won_loss = models.IntegerField() # amount won or lose
    result_type = models.CharField(max_length=20) # type win/lose/draw_(winner/loss) , draw_winner both player score = {1, 1} w, draw_loss both player with score = {0, 0}
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email 
        return (self.player.user.db_phone_number or str(self.player.id)) 

# ******************************   Dots Connect  **************************
def default_player_detail_dot(player_token=None):
    return {
        "player_id": player_token if player_token else None,
        'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"),
        'ended_at': '',
        'score': 0,
        'is_turn_done': False, 
        'btn_clicked': [] # there will come which button are clicked [1,42,14,25 , so on..]
    }

class ConnectDotGame(models.Model):
    player_a = models.ForeignKey(db_Profile, related_name='dot_games_as_a', on_delete=models.CASCADE)
    player_a_bet_amount = models.PositiveIntegerField()
    player_b = models.ForeignKey(db_Profile, related_name='dot_games_as_b', on_delete=models.CASCADE, null=True, blank=True) 
    player_b_bet_amount = models.PositiveIntegerField(null=True, blank=True) 

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('active', 'Active'),
        ('expired', 'Expired')
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='waiting') 
    player_a_channel = models.CharField(max_length=255, blank=True)
    player_b_channel = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return str(self.id) 

class ConnectDotRound(models.Model):
    game = models.ForeignKey(ConnectDotGame, on_delete=models.CASCADE, related_name='rounds')
    round_status = models.CharField(max_length=50, choices=[ 
        ('PLAYER_A_TURN', 'Player A Turn'),
        ('PLAYER_B_TURN', 'Player B Turn'),
        ('RESULT', 'Result'),
        ('EXPIRED', 'Expired')
    ])  

    player_a_detail = JSONField(max_length=100000, default=default_player_detail_dot)
    player_b_detail = JSONField(max_length=100000, default=default_player_detail_dot)  
    timer_remaining = models.PositiveIntegerField(default=150) # 150 seconds 
    turn_time_remaining = models.PositiveIntegerField(default=5)
    current_player = models.ForeignKey(db_Profile, on_delete=models.CASCADE)  
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return  str(self.id)  
     
class ConnectDotResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(ConnectDotRound, on_delete=models.CASCADE) 
    amount_won_loss = models.IntegerField() # amount won or lose
    result_type = models.CharField(max_length=20) # type win/lose/draw_(winner/loss) , draw_winner both player score = {1, 1} w, draw_loss both player with score = {0, 0}
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email 
        return (self.player.user.db_phone_number or str(self.player.id)) 

# ******************************   Guess Number  **************************

def default_player_detail_guess(player_token=None):
    return {
        "player_id": player_token if player_token else None,
        'status': 'bedding', #bedding, Active, Result , Expired
        'bet_amount': 0,  
        'game_result': "lose", # win/ lose
        'winning_amount' : 0, #(bet_amount + 50% of bet_amount)
        'started_at': timezone.now().strftime("%d/%m/%YT%H:%M:%S"), # this is start_time
        'ended_at': '', # + 100 seconds , this is end_time
        'time_remaings': 100,   # game result win for 1 , lose for 0
        'attempt_remaining': 10, # total attempt are 10 , # this is attempt used
        'target_number ': 0, # [0-1000]
        'your_guesses': []  
    }
  
class GuessNumberGame(models.Model):
    player_auth = models.ForeignKey(db_Profile, related_name='guess_games_as', on_delete=models.CASCADE) 
    player_game_detail = JSONField(max_length=100000, default=default_player_detail_guess) 
    player_channel = models.CharField(max_length=255, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return str(self.id) 

# ******************************   Dice Roll ************************** 
 
class DiceGameManager(models.Manager):
    def current_game(self):
        return self.get_or_create(name="Live Dice Battle")[0]
 
class Dice_Game(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    current_round = models.ForeignKey('Dice_GameRound', null=True, blank=True, on_delete=models.SET_NULL, related_name='current_game_round_dice')
    current_bid = models.JSONField(default=dict, blank=True, max_length=10000)
    timer = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return str(self.id) + " | " +  self.name
    
    def save(self, *args, **kwargs):
        if not self.current_bid: 
            self.current_bid = {"DOW": 0, "MID": 0, "UP": 0, "EXACT": {}}
        super().save(*args, **kwargs)

class Dice_GameRound(models.Model): 
    class RoundStatus_dice(models.TextChoices):
        WAITING = 'WAIT', 'Waiting'
        ACTIVE = 'ACTIVE', 'Active'
        RESULTS = 'RESULTS', 'Showing Results'
        COMPLETED = 'DONE', 'Completed'

    game = models.ForeignKey(Dice_Game, on_delete=models.CASCADE, related_name='rounds_dice')
    status = models.CharField(max_length=10, choices=RoundStatus_dice.choices, default=RoundStatus_dice.WAITING)
    start_time = models.DateTimeField(default=timezone.now)
    result_start = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
     
    dice1 = models.PositiveIntegerField(null=True)
    dice2 = models.PositiveIntegerField(null=True)
    total = models.PositiveIntegerField(null=True)
     
    multiplyer_number = models.JSONField(default=dict)
    exact_number_on_multiplyer = models.JSONField(default=dict)
    
    def __str__(self): 
        return f"{self.id} | {self.game.name}" 
    
    def save(self, *args, **kwargs): 
        if not self.multiplyer_number:
            jackpot_numbers = random.sample(range(2, 13), 2)
            self.multiplyer_number = {"number1": jackpot_numbers[0], "number2": jackpot_numbers[1]}
        
        if not self.exact_number_on_multiplyer:
            exact_jackpot_numbers = random.sample(range(2, 13), 2)
            self.exact_number_on_multiplyer = {
                "number1": exact_jackpot_numbers[0],
                "number2": exact_jackpot_numbers[1]
            }
         
        if self.status == self.RoundStatus_dice.COMPLETED and not self.end_time:
            self.end_time = timezone.now()
        
        super().save(*args, **kwargs)

class Dice_PlayerBid(models.Model):
    class BidSide_dice(models.TextChoices):
        DOWN = 'DOWN', 'Down'
        MIDDLE = 'MIDDLE', 'Middle'
        UP = 'UP', 'Up'  
 
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='bids_dice')
    round = models.ForeignKey(Dice_GameRound, on_delete=models.CASCADE, related_name='bids_dice') 
    side = models.CharField(max_length=6, choices=BidSide_dice.choices, null=True, blank=True)
    amount_bet_side = models.PositiveIntegerField(null=True, blank=True)
    exact_number = models.PositiveIntegerField(null=True, blank=True)
    amount_bet_exact = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'round'],
                name='unique_player_round_bid_dice'
            )
        ]
 
class Dice_PlayerResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(Dice_GameRound, on_delete=models.CASCADE)
    amount_bet_side = models.IntegerField()
    amount_bet_exact = models.IntegerField()
    amount_won_loss = models.IntegerField() 
    result_type = models.CharField(max_length=50) # win/lose/win_exact
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email + " | " + self.round.game.name
        return (self.player.user.db_phone_number or str(self.player.user.id)) + " | " + self.round.game.name

# ******************************   Color Trading ************************** 

def default_player_detail_color(player_token=None):
    return {
        "player_id": player_token if player_token else None,

        'multiplyer_number_Color': 1, 
        'user_Select_Color': '', # Green , Voilet , Red
        'amount_Bet_Color': 0,

        'multiplyer_number_Color': 1,
        'user_Select_Size': '', # Small , Big
        'amount_Bet_Size': 0,

        'multiplyer_number_Color': 1,
        'user_Select_Exact_number': '', # [0-9]
        'amount_Bet_Exact_number': 0, 
    }

def generate_timestamp_id():
    return datetime.now().strftime('%Y%m%d%H%M%S')

class ColorGameManager(models.Manager):
    def current_game(self):
        return self.get_or_create(name="Live Color Trading")[0]
 
class ColorGame(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    current_round = models.ForeignKey('ColorGameRound', null=True, blank=True, on_delete=models.SET_NULL, related_name='current_game_round_color')
    current_bid_total = models.JSONField(default=dict, blank=True, max_length=10000)
    timer = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return str(self.id) + " | " +  self.name
    
    def save(self, *args, **kwargs):
        if not self.current_bid_total: 
            self.current_bid_total = {"COLOR": 0, "EXACT": 0, "SIZE": 0}
        super().save(*args, **kwargs)

class ColorGameRound(models.Model): 
    _game_id = models.CharField(max_length=14, default=generate_timestamp_id)
    class RoundStatus_color(models.TextChoices):
        WAITING = 'WAIT', 'Waiting'
        ACTIVE = 'ACTIVE', 'Active'
        PROCESSING = 'PROCESSING', 'Processing Results'  # New status
        RESULTS = 'RESULTS', 'Showing Results'
        COMPLETED = 'DONE', 'Completed'

    game = models.ForeignKey(ColorGame, on_delete=models.CASCADE, related_name='rounds_color')
    status = models.CharField(max_length=10, choices=RoundStatus_color.choices, default=RoundStatus_color.WAITING)
    start_time = models.DateTimeField(default=timezone.now)
    result_start = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True) 

    random_number = models.IntegerField(null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): 
        return f"{self.id} | {self._game_id} | {self.game.name}" 

class ColorPlayerBid(models.Model): 
    player = models.ForeignKey(Player, on_delete = models.CASCADE, related_name='bids_color')
    round = models.ForeignKey(ColorGameRound, on_delete = models.CASCADE, related_name='bids_color')   
    player_detail = JSONField(max_length=100000, default = default_player_detail_color)
    
    created_at = models.DateTimeField(auto_now_add = True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'round'],
                name='unique_player_round_bid_color'
            )
        ]

class ColorPlayerResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(ColorGameRound, on_delete=models.CASCADE)
    amount_bet_Color = models.IntegerField()
    amount_bet_Size = models.IntegerField()
    amount_bet_Exact_Number = models.IntegerField()
    amount_won_loss = models.IntegerField() 
    result_type = models.CharField(max_length=50) # win / lose
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email + " | " + self.round.game.name
        return (self.player.user.db_phone_number or str(self.player.user.id)) + " | " + self.round.game.name
 
# ******************************   Rocket Crash ************************** 

def detail_game_state_Rocket(player_token = None):
    return { 
        "current_multiplier" : 0.00,
        "position_coordinate": {"x": "", "y": ""}, 
    }

class RocketGameManager(models.Manager):
    def current_game(self):
        return self.get_or_create(name="Live Rocket Crash")[0]
 
class RocketGame(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    current_round = models.ForeignKey('RocketGameRound', null=True, blank=True, on_delete=models.SET_NULL, related_name='current_game_round_rocket')
    current_bid = models.IntegerField(null = True)
    timer = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    
    def __str__(self):
        return str(self.id) + " | " +  self.name 
 
class RocketGameRound(models.Model): 
    class RoundStatus_Rocket(models.TextChoices):
        WAITING = 'WAIT', 'Waiting'
        ACTIVE = 'ACTIVE', 'Active' 
        FLY = 'FLY', 'Fly'
        COMPLETED = 'DONE', 'Completed'

    game = models.ForeignKey(RocketGame, on_delete=models.CASCADE, related_name='rounds_rocket')
    status = models.CharField(max_length=10, choices=RoundStatus_Rocket.choices, default=RoundStatus_Rocket.WAITING)
    start_time = models.DateTimeField(default=timezone.now) 
    end_time = models.DateTimeField(null=True)  
    random_number_flee = models.DecimalField(decimal_places = 2, max_digits = 4 , null = True, blank = True) 
    state_Rocket = JSONField(max_length = 100000, default = detail_game_state_Rocket)

    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): 
        return f"{self.id} | {self.game.name}"  
    
class RocketPlayerBid(models.Model): 
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='bids_rocket')
    round = models.ForeignKey(RocketGameRound, on_delete=models.CASCADE, related_name='bids_rocket') 

    actual_user_guess = models.DecimalField(decimal_places = 2, max_digits = 4, null = True, blank = True)
    mind_Change_user_guess = models.DecimalField(decimal_places = 2, max_digits = 4, null = True, blank = True)
    amount_bet = models.DecimalField(decimal_places = 2, max_digits = 4, null = True, blank = True)
    created_at = models.DateTimeField(auto_now_add = True)
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'round'],
                name='unique_player_round_bid_rocket'
            )
        ]
 
class RocketPlayerResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    round = models.ForeignKey(RocketGameRound, on_delete=models.CASCADE)
    amount_bet = models.IntegerField() 
    result_type = models.CharField(max_length=50) # win/lose/win_exact
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['player', 'round'], name='unique_result_per_player_round')
        ]
    
    def __str__(self):
        if self.player.user.email:
            return self.player.user.email + " | " + self.round.game.name
        return (self.player.user.db_phone_number or str(self.player.user.id)) + " | " + self.round.game.name

# ******************************   Spin Wheel On ****************************** 

class SpinWheelRound(models.Model): 
    class RoundStatus_SpinWheel(models.TextChoices):
        WAITING = 'WAIT', 'Waiting'
        ACTIVE = 'ACTIVE', 'Active' 
        SPIN = 'SPIN', 'Spin'
        RESULT = 'RESULT' , 'Result'
        COMPLETED = 'DONE', 'Completed'

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='bids_SpinWheel')  
    status = models.CharField(max_length=10, choices=RoundStatus_SpinWheel.choices, default=RoundStatus_SpinWheel.WAITING)
    amount_bet = models.IntegerField(null = True, blank = True)
    timer = models.IntegerField(default=0) 
    game_randomly_prize = models.CharField(max_length=100) 
    prize_coins = models.CharField(max_length=100)
    prize_in_side_box = models.CharField(max_length=100) 
    created_at = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        if self.player.user.email:
            return self.player.user.email
        return self.player.user.db_phone_number or str(self.player.user.id)
 