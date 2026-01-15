from django.urls import path 
from GameApp.consumers_file.card_game import CardGameConsumer 
from GameApp.consumers_file.colorTrading_game import ColorTradeGameConsumer
from GameApp.consumers_file.crashRocket_game import RocketGameConsumer
from GameApp.consumers_file.diceRoll_game import DiceRollGameConsumer
from GameApp.consumers_file.guessNumber_game import GuessNumberConsumer
from GameApp.consumers_file.football_game import FootBallBitConsumer, FootBallPlayLandConsumer
from GameApp.consumers_file.connectdots_game import ConnectDotBitConsumer, ConnectDotPlayConsumer
from GameApp.consumers_file.spinWheel import SpinWheelConsumer 

websocket_urlpatterns = [
    path("ws/card_game/<room_name>/", CardGameConsumer.as_asgi()), 
    path("ws/guess_number_game/<room_name>/", GuessNumberConsumer.as_asgi()), 
    path("ws/dice_game/<room_name>/", DiceRollGameConsumer.as_asgi()), 
    path("ws/colorTrade_game/<room_name>/", ColorTradeGameConsumer.as_asgi()), 
    path("ws/crashRocket_game/<room_name>/", RocketGameConsumer.as_asgi()), 
    path("ws/spinWheel_game/<room_name>/", SpinWheelConsumer.as_asgi()), 

    path("ws/football_bitLand/<room_name>/", FootBallBitConsumer.as_asgi()), 
    path("ws/football_playLand/<room_name>/<game_id>/", FootBallPlayLandConsumer.as_asgi()), 

    path("ws/connect_dots_bit/<room_name>/", ConnectDotBitConsumer.as_asgi()), 
    path("ws/connect_dots_play/<room_name>/<game_id>/", ConnectDotPlayConsumer.as_asgi()),  
]


'''  
 
'''