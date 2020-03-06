import asyncio
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import json
import jsonschema

base_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'request_type': {'type': 'string', 'enum': ['send_message', 'receive_message', 'error']},
        'payload': {'type': 'object'},
    },
    'required': ['request_type', 'payload'],
    'additionalProperties': False
}

send_message_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'text': {'type': 'string', 'maxLength': 500},
        'conversation_id': {'type': 'number', 'minimum': 0,  'multipleOf': 1.0}
    },
    'required': ['text', 'conversation_id'],
    'additionalProperties': False
}

receive_message_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'error_code': {'type': 'number', 'minimum': 0,  'multipleOf': 1.0},
        'error_message': {'type': 'string', 'maxLength': 500},
    },
    'required': ['error_code', 'error_message'],
    'additionalProperties': False
}

error_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'text': {'type': 'string', 'maxLength': 500},
        'conversation_id': {'type': 'number', 'minimum': 0, 'multipleOf': 1.0},
        'author_name': {'type': 'string', 'maxLength': 100},
        'time': {'type': 'int', 'minimum': 0},
    },
    'required': ['text', 'conversation_id', 'author_name', 'time'],
    'additionalProperties': False
}

payload_schemas = {
    'send_message': send_message_schema,
    'receive_message': receive_message_schema,
    'error': error_schema
}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._authenticated = False

    def set_authenticated(self):
        self._authenticated = True

    async def connect(self):
        if self.scope['user'] is None:
            await self.close()

        await self.accept()

    async def receive_json(self, content):
        await self.send_json(content)

    async def disconnect(self, close_code):
        # Called when the socket closes
        pass

    def process_request(self, content):
        json