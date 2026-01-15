from rest_framework import serializers
from GameApp.models import Game, GameRound, PlayerBid, PlayerResult, Transaction
from AccountApp.models import db_Profile, Player, Transaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = db_Profile
        fields = ['id', 'auth_token' , 'username', 'email', 'db_fullname', 'db_phone_number', 'db_country_address', 'db_photo']

class PlayerBidSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerBid
        fields = ['id', 'side', 'amount', 'created_at']

class GameRoundSerializer(serializers.ModelSerializer):
    bids = PlayerBidSerializer(many=True, read_only=True)

    class Meta:
        model = GameRound
        fields = ['id', 'card', 'created_at', 'bids']

class PlayerSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Player
        fields = ['id', 'user', 'coins']

class GameSerializer(serializers.ModelSerializer):
    current_round = GameRoundSerializer()

    class Meta:
        model = Game
        fields = ['id', 'name', 'current_round']

class PlayerResultSerializer(serializers.ModelSerializer):
    round = GameRoundSerializer(read_only=True)

    class Meta:
        model = PlayerResult
        fields = ['round'  , 'amount_bet', 'amount_won_loss', 'result_type', 'created_at']

