from django.contrib import admin
from .models import (PlayerBid , Game, GameRound, PlayerResult,  
                     FootballGame, FootballRound, FootBallResult,
                      ConnectDotGame, ConnectDotRound, ConnectDotResult, 
                      GuessNumberGame,
                       Dice_Game, Dice_GameRound, Dice_PlayerBid, Dice_PlayerResult,
                        ColorGame, ColorGameRound, ColorPlayerBid, ColorPlayerResult,
                        RocketGame , RocketGameRound , RocketPlayerBid , RocketPlayerResult , 
                        SpinWheelRound ) 
  
admin.site.register(Game) 
admin.site.register(GameRound)
admin.site.register(PlayerBid)  
admin.site.register(PlayerResult) 

admin.site.register(FootballGame) 
admin.site.register(FootballRound) 
admin.site.register(FootBallResult) 

admin.site.register(ConnectDotGame) 
admin.site.register(ConnectDotRound) 
admin.site.register(ConnectDotResult) 

admin.site.register(GuessNumberGame) 

admin.site.register(SpinWheelRound)

admin.site.register(Dice_Game) 
admin.site.register(Dice_GameRound)
admin.site.register(Dice_PlayerBid)  
admin.site.register(Dice_PlayerResult)

admin.site.register(ColorGame)
admin.site.register(ColorGameRound) 
admin.site.register(ColorPlayerBid)
admin.site.register(ColorPlayerResult)
  
admin.site.register(RocketGame)
admin.site.register(RocketGameRound) 
admin.site.register(RocketPlayerBid)
admin.site.register(RocketPlayerResult)
  