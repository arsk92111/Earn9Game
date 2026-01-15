from requests import Response
from rest_framework.views import exception_handler

# utils.py
from decimal import Decimal

# def calculate_payouts(game):
#     winning_players = game.bids.filter(is_winner=True)
#     total_winning_bids = sum([bid.bid_amount for bid in winning_players])
#     total_pool = game.total_pool
    
#     payouts = []
#     for bid in winning_players:
#         share = (bid.bid_amount / total_winning_bids) * total_pool
#         developer_fee = share * Decimal('0.05')
#         player_share = share - developer_fee
        
#         payouts.append({
#             'player': bid.user.username,
#             'bid': bid.bid_amount,
#             'share': player_share,
#             'fee': developer_fee
#         })
    
#     return payouts

def custom_exception_handler(exc, context): 
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code == 401:  # Unauthorized errors
            if response.data.get('messages'):
                for message in response.data['messages']:
                    if message.get('message') == "Token is invalid or expired":
                        return Response(
                            {"message": "Token is invalid or expired"},
                            status=response.status_code
                        )
    return response

 