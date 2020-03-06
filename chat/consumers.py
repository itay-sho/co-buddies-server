import asyncio
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import json

class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._authenticated = False

    def set_authenticated(self):
        self._authenticated = True

    async def connect(self):
        # Called on connection.
        # To accept the connection call:
        await self.accept()

    async def receive_json(self, content):
        if await self.validate_authenticated(content):
            await self.send_json(content)
        # Called with either text_data or bytes_data for each frame
        # You can call:

    async def disconnect(self, close_code):
        # Called when the socket closes
        pass

    async def validate_authenticated(self, content):
        if self._authenticated:
            return True

        if 'authenticated' in content and content['authenticated'] == 'true':
            self._authenticated = True
            return True

        await self.send_json(json.dumps({'error': 1, 'text': 'unauthenticated!'}))
        return False
