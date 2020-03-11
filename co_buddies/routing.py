import asyncio
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from channels.security.websocket import AllowedHostsOriginValidator

from chat.consumers import ChatConsumer
from chat.tasks import *

websocket_urlpatterns = [
    re_path(r'^chat$', ChatConsumer),
]
application = ProtocolTypeRouter({
    # WebSocket chat handler
    'websocket':
        AllowedHostsOriginValidator(
            URLRouter(websocket_urlpatterns)
        ),
    'channel':
        ChannelNameRouter({
            'matchmaking-task': MatchmakingTask,
            'db-operations-task': DBOperationsTask,
            'pn-task': PushNotificationsTask,
            'conversation-manager-task': ConversationManagerTask
        })
})
