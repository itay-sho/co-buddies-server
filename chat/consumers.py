import asyncio
import enum

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.authtoken.models import Token
import jsonschema
from chat.models import Conversation, Message
import time
import threading
from django.contrib.auth.models import User

base_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'request_type': {'type': 'string', 'enum': ['send_message', 'receive_message', 'error', 'request_match', 'receive_match', 'disconnect', 'authenticate']},
        'payload': {'type': 'object'},
        'seq': {'type': 'number', 'minimum': 1,  'multipleOf': 1.0},
    },
    'required': ['request_type', 'payload', 'seq'],
    'additionalProperties': False
}

send_message_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'text': {'type': 'string', 'maxLength': 500},
    },
    'required': ['text'],
    'additionalProperties': False
}

error_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'error_code': {'type': 'number', 'minimum': 0,  'multipleOf': 1.0},
        'error_message': {'type': 'string', 'maxLength': 500},
        'response_to': {'type': 'number', 'minimum': 1,  'multipleOf': 1.0},
    },
    'required': ['error_code', 'error_message'],
    'additionalProperties': False
}

receive_message_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'text': {'type': 'string', 'maxLength': 500},
        'conversation_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
        'author_name': {'type': 'string', 'maxLength': 100},
        'time': {'type': 'number', 'minimum': 0},
    },
    'required': ['text', 'conversation_id', 'author_name', 'time'],
    'additionalProperties': False
}

request_match_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {},
    'additionalProperties': False
}

receive_match_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'conversation_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
    },
    'required': ['conversation_id'],
    'additionalProperties': False
}

disconnect_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'user_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
    },
    'required': ['user_id'],
    'additionalProperties': False
}

authenticate_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'access_token': {'type': 'string', 'maxLength': 100},
    },
    'required': ['access_token'],
    'additionalProperties': False
}

payload_dict = {
    'send_message': send_message_schema,
    'receive_message': receive_message_schema,
    'error': error_schema,
    'request_match': request_match_schema,
    'receive_match': receive_match_schema,
    'disconnect': disconnect_schema,
    'authenticate': authenticate_schema
}


class ErrorEnum(enum.Enum):
    OK = 0
    UNAUTHENTICATED = 100
    CONVERSATION_CLOSED = enum.auto()
    SCHEMA_ERROR = enum.auto()
    UNIMPLEMENTED = enum.auto()
    CONVERSATION_NOT_INITIALIZED = enum.auto()
    TIMEOUT = enum.auto()
    UserInactive = enum.auto()
    InvalidToken = enum.auto()

    # KEEP LAST
    UNKNOWN_ERROR = enum.auto()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    AUTHENTICATE_TIMEOUT_SECONDS = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._conversation_id = None
        self._seq = 0
        self._is_authenticated = False
        self._authenticate_timeout_task = asyncio.create_task(self.send_disconnection_due_to_authentication_timeout())

    async def send_disconnection_due_to_authentication_timeout(self):
        await asyncio.sleep(ChatConsumer.AUTHENTICATE_TIMEOUT_SECONDS)
        await self.send_error_message(ErrorEnum.TIMEOUT, error_message='disconnecting due to timeout')
        await self.close()

    def get_channel_group(self):
        return f'conversation_{self._conversation_id}'

    def get_next_seq(self):
        self._seq += 1
        return self._seq

    async def update_conversation_id(self, value):
        # TODO: make this function blocking in order to avoid async bugs !

        if self._conversation_id != value:
            await self.channel_layer.group_discard(self.get_channel_group(), self.channel_name)
            self._conversation_id = value
            await self.channel_layer.group_add(self.get_channel_group(), self.channel_name)

    async def connect(self):
        await self.accept()

    async def receive_json(self, content, **kwargs):
        try:
            self.validate_content(content)

            if not self._is_authenticated and content['request_type'] != 'authenticate':
                await self.close()
                return

            try:
                # calling the specific payload process function
                await getattr(self, f'process__{content["request_type"]}')(content)
            except AttributeError:
                await self.process__default(content)

        except (jsonschema.exceptions.ValidationError, jsonschema.exceptions.FormatError):
            response_to = None
            if 'seq' in content:
                response_to = content['seq']

            await self.send_error_message(error_code=ErrorEnum.SCHEMA_ERROR, error_message='Invalid json schema', response_to=response_to)

    async def receive_match(self, content):
        conversation_id = content['conversation_id']
        await self.update_conversation_id(conversation_id)
        await self.send_receive_match(conversation_id)

    async def disconnect(self, close_code):
        if self._is_authenticated:
            group = self.get_channel_group()
            await self.channel_layer.group_discard(group, self.channel_name)
            await self.send_disconnect_message(group)

        await self.close()

    def validate_content(self, content):
        jsonschema.validate(content, base_schema)
        payload_schema = payload_dict[content['request_type']]

        jsonschema.validate(content['payload'], payload_schema)

    async def process__send_message(self, content):
        payload = content['payload']
        if self._conversation_id is None:
            await self.send_error_message(ErrorEnum.CONVERSATION_NOT_INITIALIZED, "conversation has not initialized yet")
            return

        # validate if the user is allowed to do this operation
        try:
            Message.validate_message_creation(author_id=self.scope['user'].chat_user.id, conversation_id=self._conversation_id)
            message = await Message.create_message_async(
                author_id=self.scope['user'].chat_user.id,
                conversation_id=self._conversation_id,
                text=payload['text']
            )

            content = {
                'request_type': 'receive_message',
                # TODO: this is a bug: using one chat sequence number to other.
                'seq': self.get_next_seq(),
                'payload': {
                    'text': message.text,
                    'conversation_id': message.conversation_id,
                    'author_name': f'{message.author.user.first_name} {message.author.user.last_name}',
                    'time': time.mktime(message.time.timetuple())
                }
            }

            # broadcasting the message
            await self.send_to_group(content)

        except Conversation.DoesNotExist:
            await self.send_error_message(ErrorEnum.CONVERSATION_CLOSED, 'Conversation has closed', content['seq'])

    async def process__authenticate(self, content):
        access_token = content['payload']['access_token']

        try:
            token = await database_sync_to_async(Token.objects.get)(key=access_token)
            user = await database_sync_to_async(User.objects.get)(id=token.user_id)

        except Token.DoesNotExist:
            await self.send_error_message(error_code=ErrorEnum.InvalidToken, error_message='Invalid access token', response_to=content['seq'])
            return

        if not user.is_active:
            await self.send_error_message(error_code=ErrorEnum.UserInactive, error_message='Select user inactive', response_to=content['seq'])
            return

        # Success
        self._authenticate_timeout_task.cancel()
        self.scope['user'] = user
        self._is_authenticated = True
        await self.send_error_message(response_to=content['seq'])

    async def send_to_group(self, content, group=None):
        if group is None:
            group = self.get_channel_group()

        await self.channel_layer.group_send(
            group,
            {
                'type': 'chat.message',
                'content': content
            }
        )

    async def chat_message(self, event):
        await self.send_json(event['content'])

    async def process__default(self, content):
        await self.send_error_message(
            error_code=ErrorEnum.UNIMPLEMENTED,
            error_message='This action is not implemented by the server',
            response_to=content['seq']
        )

    async def process__request_match(self, content):
        await self.channel_layer.send(
            'matchmaking-task',
            {'type': 'request_match', 'channel_name': self.channel_name, 'user_id': self.scope['user'].chat_user.id}
        )
        await self.send_error_message(response_to=content['seq'])

    async def send_json(self, content, close=False):
        self.validate_content(content)
        return await super().send_json(content, close)

    async def send_error_message(self, error_code=ErrorEnum.OK, error_message='', response_to=None):
        content = {
            'request_type': 'error',
            'seq': self.get_next_seq(),
            'payload': {
                'error_code': error_code.value,
                'error_message': error_message
            }
        }

        if response_to is not None:
            content['payload']['response_to'] = response_to

        await self.send_json(content)

    async def send_receive_match(self, conversation_id):
        content = {
            'request_type': 'receive_match',
            'seq': self.get_next_seq(),
            'payload': {
                'conversation_id': conversation_id
            }
        }

        await self.send_json(content)

    async def send_disconnect_message(self, group):
        content = {
            'request_type': 'disconnect',
            # TODO: this is a bug: using one chat sequence number to other.
            'seq': self.get_next_seq(),
            'payload': {
                'user_id': self.scope['user'].chat_user.id
            }
        }

        await self.send_to_group(content, group)
