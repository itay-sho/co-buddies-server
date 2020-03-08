from asgiref.sync import async_to_sync
from channels.generic.websocket import SyncConsumer
from chat.match_maker import MatchMaker
import json


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
