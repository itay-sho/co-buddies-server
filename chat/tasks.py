from asgiref.sync import async_to_sync
from channels.generic.websocket import SyncConsumer
from chat.match_maker import MatchMaker


class MatchmakingTask(SyncConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matcher = MatchMaker(self.match_request_found)

    def request_match(self, message):
        self.matcher.add_to_pool(message['channel_name'], message['user_id'])

    def cancel_match_request(self, message):
        self.matcher.remove_from_pool(message['channel_name'])

    def match_request_found(self, channel_name1, channel_name2, conversation_id):
        payload = {'type': 'receive_match', 'conversation_id': conversation_id}
        async_to_sync(self.channel_layer.send)(
            channel_name1,
            payload
        )
        async_to_sync(self.channel_layer.send)(
            channel_name2,
            payload
        )
        print(f'We found a match! {channel_name1} with {channel_name2} conversation id: {conversation_id}')
