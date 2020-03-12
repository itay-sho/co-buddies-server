import asyncio
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import jsonschema
from .tasks import ConversationManagerTask
from .enums import ErrorEnum
from .conversation_user_dictionary import ConversationUserDictionary


base_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'request_type': {'type': 'string', 'enum': ['send_message', 'receive_message', 'error', 'request_match', 'unrequest_match', 'receive_match', 'disconnect', 'authenticate', 'set_pn_token']},
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
        'author_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
        'time': {'type': 'number', 'minimum': 0},
    },
    'required': ['text', 'conversation_id', 'author_id', 'time'],
    'additionalProperties': False
}

request_match_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {},
    'additionalProperties': False
}

unrequest_match_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'user_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
    },
    'required': ['user_id'],
    'additionalProperties': False
}

set_pn_token_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'token': {'type': 'string', 'maxLength': 300},
    },
    'required': ['token'],
    'additionalProperties': False
}

receive_match_schema = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'conversation_id': {'type': 'number', 'minimum': 1, 'multipleOf': 1.0},
        'attendees': {
            'type': 'object',
            "patternProperties": {
                "^[0-9]+$": {'type': 'string', 'maxLength': 100}
            },
            'additionalProperties': False
        },
    },
    'required': ['conversation_id', 'attendees'],
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
    '$schema': 'http://json-schema.org/drauft-07/schema#',
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
    'unrequest_match': unrequest_match_schema,
    'receive_match': receive_match_schema,
    'disconnect': disconnect_schema,
    'authenticate': authenticate_schema,
    'set_pn_token': set_pn_token_schema
}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    AUTHENTICATE_TIMEOUT_SECONDS = 3
    INACTIVENESS_TIMEOUT_SECONDS = 180

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._conversation_id = None
        self._chat_user_id = None
        self._seq = 0
        self._is_authenticated = False
        self._new_message_flag = True
        self._has_push_notifications = False

        self._authenticate_timeout_task = asyncio.create_task(self.send_disconnection_due_to_authentication_timeout())
        self._in_active_timeout = asyncio.create_task(self.send_disconnection_due_to_inactiveness())

    async def send_disconnection_due_to_authentication_timeout(self):
        await asyncio.sleep(ChatConsumer.AUTHENTICATE_TIMEOUT_SECONDS)
        await self.send_error_message(ErrorEnum.AUTHENTICATION_TIMEOUT, error_message='disconnecting due to authentication timeout')
        await self.close()

    async def send_disconnection_due_to_inactiveness(self):
        while self.did_got_new_message():
            await asyncio.sleep(ChatConsumer.INACTIVENESS_TIMEOUT_SECONDS)

        await self.send_error_message(ErrorEnum.INACTIVENESS_TIMEOUT, error_message='disconnecting due inactiveness')
        await self.close()

    def did_got_new_message(self):
        did_got_new_message = self._new_message_flag
        if did_got_new_message:
            self._new_message_flag = False

        return did_got_new_message

    def get_next_seq(self):
        self._seq += 1
        return self._seq

    async def update_conversation_id(self, value):
        if self._conversation_id != value:
            if self._conversation_id is not None:
                await self.channel_layer.group_discard(
                    ConversationManagerTask.get_conversation_channel(self._conversation_id),
                    self.channel_name
                )

            self._conversation_id = value
            await self.channel_layer.send(
                'conversation-manager-task',
                {
                    'type': 'join_conversation',
                    'user_id': self._chat_user_id,
                    'conversation_id': self._conversation_id
                }
            )
            await self.channel_layer.group_add(ConversationManagerTask.get_conversation_channel(self._conversation_id), self.channel_name)

    async def connect(self):
        await self.accept()

    async def receive_json(self, content, **kwargs):
        try:
            self._new_message_flag = True
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
        attendees = json.loads(content['attendees'])

        await self.update_conversation_id(conversation_id)
        await self.send_receive_match(conversation_id, attendees)

    async def disconnect(self, close_code):
        if self._is_authenticated:
            group = ConversationManagerTask.get_conversation_channel(self._conversation_id)
            # sending disconnection to other user BEFORE closing all the sockets & configurations
            await self.send_disconnect_message()

            await self.channel_layer.send(
                'matchmaking-task',
                {'type': 'unrequest_match', 'user_id': self._chat_user_id}
            )
            await self.channel_layer.send(
                'conversation-manager-task',
                {'type': 'user_disconnect', 'user_id': self._chat_user_id}
            )
            if self._has_push_notifications:
                await self.channel_layer.send(
                    'pn-task',
                    {'type': 'remove_pn_listener', 'channel_name': self.channel_name}
                )
            await self.channel_layer.group_discard(group, self.channel_name)

    @classmethod
    def validate_content(cls, content):
        jsonschema.validate(content, base_schema)
        payload_schema = payload_dict[content['request_type']]

        jsonschema.validate(content['payload'], payload_schema)

    async def pn_channel_removed(self, content):
        self._has_push_notifications = False

    async def process__send_message(self, content):
        payload = content['payload']
        if self._conversation_id is None:
            await self.send_error_message(ErrorEnum.CONVERSATION_NOT_INITIALIZED, "conversation has not initialized yet")
            return

        await self.channel_layer.send(
            'db-operations-task',
            {
                'type': 'create_message',
                'channel_name': self.channel_name,
                'text': payload['text'],
                'conversation_id': self._conversation_id,
                'author_id': self._chat_user_id,
                'seq': content['seq'],
            }
        )

    async def process__set_pn_token(self, content):
        payload = content['payload']
        await self.channel_layer.send(
            'pn-task',
            {
                'type': 'add_pn_listener',
                'channel_name': self.channel_name,
                'token': payload['token']
            }
        )
        self._has_push_notifications = True

    async def create_message_response(self, content):
        error_payload = content['error']
        error_code = error_payload['payload']['error_code']

        if error_code == ErrorEnum.OK.value:
            message_payload = content['message']
            content = {
                'request_type': 'receive_message',
                # TODO: this is a bug: using one chat sequence number to other.
                'seq': self.get_next_seq(),
                'payload': {
                    'text': message_payload['text'],
                    'conversation_id': message_payload['conversation_id'],
                    'author_id': message_payload['author_id'],
                    'time': message_payload['time']
                }
            }

            # broadcasting the message
            await self.send_to_group(content)
        else:
            # fallback
            await self.send_error_message(
                ErrorEnum(error_payload['payload']['error_code']),
                error_payload['payload']['error_message']
            )
            await self.close()

    async def process__authenticate(self, content):
        await self.channel_layer.send(
            'db-operations-task',
            {
                'type': 'authenticate',
                'channel_name': self.channel_name,
                'seq': content['seq'],
                'access_token': content['payload']['access_token'],
            }
        )

    async def authenticate_response(self, content):
        error_payload = content['error']
        error_code = error_payload['payload']['error_code']

        if error_code == ErrorEnum.OK.value:
            # login success
            self._authenticate_timeout_task.cancel()
            self._chat_user_id = content['chat_user_id']
            self._is_authenticated = True
            await self.send_error_message(response_to=error_payload['response_to'])
        else:
            # login has failed
            await self.send_error_message(
                ErrorEnum(error_payload['payload']['error_code']),
                error_payload['payload']['error_message']
            )
            await self.close()

    async def send_to_group(self, content):
        await self.channel_layer.send(
            'conversation-manager-task',
            {
                'type': 'broadcast_message_to_conversation',
                'user_id': self._chat_user_id,
                'message': content
            }
        )

    async def chat_message(self, content):
        if content['content']['request_type'] == 'receive_message' and self._has_push_notifications:
            await self.channel_layer.send(
                'pn-task',
                {
                    'type': 'send_pn_message',
                    'channel_name': self.channel_name,
                    'title': 'הודעה חדשה',
                    'body': f'{content["content"]["payload"]["text"]}'
                }
            )

        await self.send_json(content['content'])

    async def chat_conversation_closed(self, content):
        await self.channel_layer.group_discard(
            ConversationManagerTask.get_conversation_channel(self._conversation_id),
            self.channel_name
        )

    async def process__default(self, content):
        await self.send_error_message(
            error_code=ErrorEnum.UNIMPLEMENTED,
            error_message='This action is not implemented by the server',
            response_to=content['seq']
        )

    async def process__request_match(self, content):
        await self.channel_layer.send(
            'matchmaking-task',
            {'type': 'request_match', 'channel_name': self.channel_name, 'user_id': self._chat_user_id}
        )
        await self.send_error_message(response_to=content['seq'])

        await self.request_lobby_attendees_list()

    async def request_lobby_attendees_list(self):
        await self.channel_layer.send(
            'conversation-manager-task',
            {'type': 'request_lobby_attendees_list', 'channel_name': self.channel_name}
        )

    async def response_lobby_attendees_list(self, content):
        attendees = json.loads(content['attendees'])
        # moving to lobby until response is given
        await self.move_to_lobby(attendees)

    async def move_to_lobby(self, attendees):
        await self.update_conversation_id(ConversationUserDictionary.LOBBY_CONVERSATION_ID)
        await self.send_receive_match(ConversationUserDictionary.LOBBY_CONVERSATION_ID, attendees)

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

    async def send_receive_match(self, conversation_id, attendees):
        content = {
            'request_type': 'receive_match',
            'seq': self.get_next_seq(),
            'payload': {
                'conversation_id': conversation_id,
                'attendees': attendees
            }
        }

        await self.send_json(content)

    async def send_disconnect_message(self):
        content = {
            'request_type': 'disconnect',
            # TODO: this is a bug: using one chat sequence number to other.
            'seq': self.get_next_seq(),
            'payload': {
                'user_id': self._chat_user_id
            }
        }

        await self.send_to_group(content)
