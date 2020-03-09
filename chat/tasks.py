from asgiref.sync import async_to_sync
from channels.generic.websocket import SyncConsumer
from chat.match_maker import MatchMaker
from chat.models import Message, Conversation
from chat.consumers import ErrorEnum
import json
import time


class DBOperationsTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seq = 0

    def get_next_seq(self):
        self._seq += 1
        return self._seq

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
            return_content = {
                'type': 'create_message_response',
                'error': {
                    'request_type': 'error',
                    'seq': self.get_next_seq(),
                    'payload': {
                        'error_code': error_code.value,
                        'error_message': error_message,
                        'response_to': response_to
                    }
                }
            }

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
