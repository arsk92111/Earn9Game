from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views import View 
from . import views  
from django.urls import path  
from .views import (CurrentRoundView, PlayerBalanceView, LeaderboardView,  
                    AllPlayersWithDetailsView, AuthenticatedPlayerDetailsView)


urlpatterns = [ 
    path('page/home/' , views.home_page, name='home_page'), 
    path('page/cardgame/', views.card_game_page, name='cardgame'),
    path('page/GuessNumber_page/', views.GuessNumber_page, name='GuessNumber_page'),
    path('page/diceRoll_game/', views.diceRoll_game_page, name='diceRoll_game'),
    path('page/crashRocket_game/', views.crashRocket_game_page, name='crashRocket_game'),
    path('page/spinWheel_game/', views.spinWheel_game_page, name='spinWheel_game'),
    
    path('page/colorTrade_game/', views.colorTrade_game_page, name='colorTrade_game'), 
    path('page/football_bit/', views.football_bit_page, name='football_bit'),
    path('page/football_playLand/<str:game_id>/', views.football_playLand_page, name='football_playLand'),

    path('page/connectDot_bit_page/', views.connectDot_bit_page, name='connectDot_bit_page'),
    path('page/connectDot_play_page/<str:game_id>/', views.connectDot_play_page, name='connectDot_play_page'),

    ##############################    *******    << API's >>     *******   spinWheel_game_page     ############################## 
    
    path('api/deduct_coins/', views.deduct_coins, name='deduct_coins'), 
    path('api/place_bid/', views.place_bid, name='place_bid'), 
    path('api/current_round/', CurrentRoundView.as_view(), name='current_round'),
    path('api/player_balance/', PlayerBalanceView.as_view(), name='player_balance'),
    path('api/leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('api/all_players/', AllPlayersWithDetailsView.as_view(), name='all_players'),
    path('api/my_profile/', AuthenticatedPlayerDetailsView.as_view(), name='my_profile'), 
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
 