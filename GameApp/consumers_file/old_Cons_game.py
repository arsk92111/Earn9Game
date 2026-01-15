#consumers.py 
from channels.db import database_sync_to_async  
from GameApp.models import Player , SpinWheelRound
from django.utils import timezone
from datetime import timedelta 
from asgiref.sync import sync_to_async  
import asyncio, json, random 
from channels.generic.websocket import AsyncWebsocketConsumer   

 
class SpinWheelConsumer(AsyncWebsocketConsumer):
    round_duration = 10 
    current_phase = 'bedding'
    game_name = "spinWheel" 

    _timer_task = None
    _timer_lock = asyncio.Lock() 
  
    async def connect(self):
        try:
            await self.accept() 
            if not await self.authenticate_user():
                return  
        
        except Exception as e:
            await self.handle_connection_error(e)
    
    async def handle_connection_error(self, error): 
        print(f"Connection error: {str(error)}")
        try: 
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Failed to initialize game connection'
            }))
        except Exception as send_error:
            print(f"Error sending failure message: {send_error}")
        finally: 
            await self.close(code=4001)

    async def authenticate_user(self): 
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.handle_connection_error("Anonymous access denied")
            return False
        
        try:
            self.player = await sync_to_async(Player.objects.get)(user=self.user)
            return True
        except Player.DoesNotExist:
            await self.handle_connection_error("Player record missing")
            return False
          