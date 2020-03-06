import asyncio
import enum

from channels.generic.websocket import AsyncJsonWebsocketConsumer
import jsonschema
from chat.models import Message
import time

base_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'request_type': {'type': 'string', 'enum': ['send_message', 'receive_message', 'error']},
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
        'conversation_id': {'type': 'number', 'minimum': 1,  'multipleOf': 1.0}
    },
    'required': ['text', 'conversation_id'],
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

payload_dict = {
    'send_message': send_message_schema,
    'receive_message': receive_message_schema,
    'error': error_schema
}


class ErrorEnum(enum.Enum):
    OK = 0
    UNAUTHENTICATED = 100
    FORBIDDEN_ACTION = enum.auto()
    SCHEMA_ERROR = enum.auto()
    UNIMPLEMENTED = enum.auto()

    # KEEP LAST
    UNKNOWN_ERROR = enum.auto()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._authenticated = False
        self._conversation_id = None
        self._seq = 0
        # self.channel_name = ''.join([random.choice(string.ascii_letters + string.digits) for i in range(15)])

    def get_channel_group(self):
        return f'conversation_{self._conversation_id}'

    def get_set_seq(self):
        self._seq += 1
        return self._seq

    async def update_conversation_id(self, value):
        # TODO: make this function blocking in order to avoid async bugs !

        if self._conversation_id != value:
            await self.channel_layer.group_discard(self.get_channel_group(), self.channel_name)
            self._conversation_id = value
            await self.channel_layer.group_add(self.get_channel_group(), self.channel_name)

    def set_authenticated(self):
        self._authenticated = True

    async def connect(self):
        if self.scope['user'] is None:
            await self.close()

        await self.accept()

    async def receive_json(self, content, **kwargs):
        try:
            self.validate_content(content)

            # calling the specific payload process function
            await getattr(self, f'process__{content["request_type"]}')(content)

        except (jsonschema.exceptions.ValidationError, jsonschema.exceptions.FormatError):
            response_to = None
            if 'seq' in content:
                response_to = content['seq']

            await self.send_error_message(error_code=ErrorEnum.SCHEMA_ERROR, error_message='Invalid json schema', response_to=response_to)

    async def disconnect(self, close_code):
        # Called when the socket closes
        await self.channel_layer.group_discard(self.get_channel_group(), self.channel_name)
        self.self._conversation_id
        await self.close()

    def validate_content(self, content):
        jsonschema.validate(content, base_schema)
        payload_schema = payload_dict[content['request_type']]

        jsonschema.validate(content['payload'], payload_schema)

    async def process__send_message(self, content):
        payload = content['payload']
        await self.update_conversation_id(payload['conversation_id'])

        # validate if the user is allowed to do this operation
        try:
            Message.validate_message_creation(author_id=self.scope['user'].id, conversation_id=payload['conversation_id'])
            message = await Message.create_message_async(
                author_id=self.scope['user'].id,
                conversation_id=payload['conversation_id'],
                text=payload['text']
            )

            # sending success to the user
            await self.send_error_message(ErrorEnum.OK, 'Message received and will be broadcasted', content['seq'])

            # broadcasting the message
            await self.broadcast_message(message)

        except Message.DoesNotExist:
            await self.send_error_message(ErrorEnum.FORBIDDEN_ACTION, 'attempted operation was forbidden', content['seq'])

    async def broadcast_message(self, message):
        content = {
            'request_type': 'receive_message',
            'seq': self.get_set_seq(),
            'payload': {
                'text': message.text,
                'conversation_id': message.conversation_id,
                'author_name': f'{message.author.user.first_name} {message.author.user.last_name}',
                'time':  time.mktime(message.time.timetuple())
            }
        }

        await self.channel_layer.group_send(
            self.get_channel_group(),
            {
                'type': 'chat.message',
                'content': content
            }
        )

    async def chat_message(self, event):
        await self.send_json(event['content'])

    async def process__receive_message(self, content):
        await self.send_error_message(
            error_code=ErrorEnum.UNIMPLEMENTED,
            error_message='This action is not implemented by the server',
            response_to=content['seq']
        )

    async def process__error(self, content):
        await self.send_error_message(
            error_code=ErrorEnum.UNIMPLEMENTED,
            error_message='This action is not implemented by the server',
            response_to=content['seq']
        )

    async def send_json(self, content, close=False):
        self.validate_content(content)
        return await super().send_json(content, close)

    async def send_error_message(self, error_code=ErrorEnum.OK, error_message='', response_to=None):
        content = {
            'request_type': 'error',
            'seq': self.get_set_seq(),
            'payload': {
                'error_code': error_code.value,
                'error_message': error_message
            }
        }

        if response_to is not None:
            content['payload']['response_to'] = response_to

        await self.send_json(content)
