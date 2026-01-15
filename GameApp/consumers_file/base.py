from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs
from AccountApp.models import db_Profile 
from channels.db import database_sync_to_async

class BaseGameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_params = parse_qs(self.scope['query_string'].decode())
        token = query_params.get('token', [None])[0] 
        
        if not token:
            await self.close()
            return

        try:
            self.user = await database_sync_to_async(db_Profile.objects.get)(auth_token=token)
            self.scope['user'] = self.user  
        except db_Profile.DoesNotExist:
            await self.close()
 