from asgiref.sync import async_to_sync
from channels.generic.websocket import SyncConsumer
from chat.match_maker import MatchMaker
from chat.models import Message, Conversation, ChatUser
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from channels.layers import get_channel_layer
import json
import time
import firebase_admin
from firebase_admin import messaging
from .enums import ErrorEnum
from .conversation_user_dictionary import ConversationUserDictionary


class ConversationManagerTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._conversation_user_dictionary = ConversationUserDictionary()
        self.channel_layer = get_channel_layer()

    @classmethod
    def get_conversation_channel(cls, conversation_id):
        return f'conversation_{conversation_id}'

    def _create_lobby_attendees_dict(self):
        lobby_attendees_ids = self._conversation_user_dictionary.get_conversation_attendees(ConversationUserDictionary.LOBBY_CONVERSATION_ID)
        if len(lobby_attendees_ids) > 0:
            return {
                attendee.id: attendee.name
                for attendee in
                ChatUser.objects.only('id', 'name').filter(id__in=lobby_attendees_ids)
            }
        return {}

    def request_lobby_attendees_list(self, content):
        channel_name = content['channel_name']
        attendees_dict = self._create_lobby_attendees_dict()

        async_to_sync(self.channel_layer.send)(
            channel_name,
            {
                'type': 'response_lobby_attendees_list',
                'attendees': json.dumps(attendees_dict)
            }
        )

    def user_disconnect(self, content):
        user_id = content['user_id']
        closed_conversation_id = self._conversation_user_dictionary.user_disconnect(user_id)
        if closed_conversation_id is not None:
            self._close_conversation(closed_conversation_id)

    def leave_conversation(self, content):
        user_id = content['user_id']
        conversation_id = content['conversation_id']
        closed_conversation_id = self._conversation_user_dictionary.remove_user_from_conversation(
            user_id,
            conversation_id
        )

        if closed_conversation_id is not None:
            self._close_conversation(closed_conversation_id)

    def _close_conversation(self, conversation_id):
        conversation = Conversation.objects.get(id=conversation_id)
        conversation.is_open = False
        conversation.save()

        async_to_sync(self.channel_layer.group_send)(
            self.get_conversation_channel(conversation_id),
            {
                'type': 'chat.conversation_closed'
            }
        )

    def join_conversation(self, content):
        user_id = content['user_id']
        conversation_id = content['conversation_id']
        self._conversation_user_dictionary.leave_any_previous_conversations_and_join(user_id, conversation_id)

    def broadcast_message_to_conversation(self, content):
        conversation_id = self._conversation_user_dictionary.get_user_conversation(content['user_id'])

        if conversation_id is not None:
            message = content['message']
            async_to_sync(self.channel_layer.group_send)(
                self.get_conversation_channel(conversation_id),
                {
                    'type': 'chat.message',
                    'content': message
                }
            )


class PushNotificationsTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._channel_name_to_token_dict = {}
        firebase_admin.initialize_app()

    def add_pn_listener(self, content):
        channel_name = content['channel_name']
        token = content['token']

        self._channel_name_to_token_dict[channel_name] = token

    def remove_pn_listener(self, content):
        channel_name = content['channel_name']
        if channel_name in self._channel_name_to_token_dict:
            del self._channel_name_to_token_dict[channel_name]

    def send_pn_message(self, content):
        channel_name = content['channel_name']
        title = content['title']
        body = content['body']
        has_error_occurred = True
        try:
            message = messaging.Message(
                data={
                    'title': title,
                    'body': body,
                    'url': 'https://co-buddies.co.il/'
                },
                token=self._channel_name_to_token_dict[channel_name],
            )
            messaging.send(message)

            # everything succeeded, changing error to false
            has_error_occurred = False
        except messaging.UnregisteredError:
            if channel_name in self._channel_name_to_token_dict:
                del self._channel_name_to_token_dict[channel_name]
        finally:
            if has_error_occurred:
                async_to_sync(self.channel_layer.send)(channel_name, {'type': 'pn_channel_removed'})
                print('removing the pn channel')


class DBOperationsTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seq = 0

    def get_next_seq(self):
        self._seq += 1
        return self._seq

    def authenticate(self, content):
        channel_name = content['channel_name']
        access_token = content['access_token']
        response_to = content['seq']

        # initialized to success values, any exception caught should change that
        error_code = ErrorEnum.OK
        error_message = ''
        user = None

        try:
            token = Token.objects.get(key=access_token)
            user = User.objects.get(id=token.user_id)

            if not user.is_active:
                error_code = ErrorEnum.AUTH_FAIL_USER_INACTIVE
                error_message = 'Select user inactive'

        except Token.DoesNotExist:
            error_code = ErrorEnum.AUTH_FAIL_INVALID_TOKEN
            error_message = 'Invalid access token'

        finally:
            return_content = self._create_base_return_content('authenticate_response', error_code, error_message, response_to)
            if user is not None:
                return_content['chat_user_id'] = user.chat_user.id
                return_content['chat_user_name'] = user.chat_user.name

            async_to_sync(self.channel_layer.send)(
                channel_name,
                return_content
            )

    def create_message(self, content):
        channel_name = content['channel_name']
        text = content['text']
        author_id = content['author_id']
        conversation_id = content['conversation_id']
        response_to = content['seq']

        # initialized to success values, any exception caught should change that
        error_code = ErrorEnum.OK
        error_message = ''
        message = None

        try:
            # validate if the user is allowed to do this operation
            message = Message.create_message(
                author_id=author_id,
                conversation_id=conversation_id,
                text=text
            )

        except Conversation.DoesNotExist:
            # failed
            error_code = ErrorEnum.CONVERSATION_CLOSED
            error_message = 'Conversation has closed'

        finally:
            return_content = self._create_base_return_content('create_message_response', error_code, error_message, response_to)

            if message is not None:
                return_content['message'] = {
                    'text': message.text,
                    'conversation_id': message.conversation_id,
                    'author_id': author_id,
                    'time': time.mktime(message.time.timetuple())
                }

            async_to_sync(self.channel_layer.send)(
                channel_name,
                return_content
            )

    def _create_base_return_content(self, message_type, error_code, error_message, response_to=None):
        error_message = {
            'type': message_type,
            'error': {
                'request_type': 'error',
                'seq': self.get_next_seq(),
                'payload': {
                    'error_code': error_code.value,
                    'error_message': error_message
                }
            }
        }

        if response_to is not None:
            error_message['error']['response_to'] = response_to

        return error_message


class MatchmakingTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matcher = MatchMaker(self.match_request_found)

    def request_match(self, message):
        # removing old user channel if there is
        prev_user_channel = self.matcher.get_user_channel(message['user_id'])
        if prev_user_channel is not None:
            async_to_sync(self.channel_layer.send)(
                prev_user_channel,
                {'type': 'disconnect'}
            )
            self.matcher.remove_from_pool_if_exist(message['user_id'])

        # adding new channel
        self.matcher.add_to_pool(message['user_id'], message['channel_name'])

    def unrequest_match(self, message):
        print('unrequesting match')
        self.matcher.remove_from_pool_if_exist(message['user_id'])

    def match_request_found(self, channel_name1, channel_name2, conversation_id, attendees):
        payload = {'type': 'receive_match', 'conversation_id': conversation_id, 'attendees': json.dumps(attendees)}
        async_to_sync(self.channel_layer.send)(
            channel_name1,
            payload
        )
        async_to_sync(self.channel_layer.send)(
            channel_name2,
            payload
        )
        print(f'We found a match! {channel_name1} with {channel_name2} conversation id: {conversation_id}')
