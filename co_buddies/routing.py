import asyncio
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from chat.middewares import QueryAuthMiddleware
from channels.security.websocket import AllowedHostsOriginValidator

from chat.consumers import ChatConsumer
from chat.tasks import MatchmakingTask

websocket_urlpatterns = [
    re_path(r"^chat$", ChatConsumer),
]
application = ProtocolTypeRouter({
    # WebSocket chat handler
    "websocket":
        AllowedHostsOriginValidator(
            QueryAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        ),
    "channel":
        ChannelNameRouter({
            "matchmaking-task": MatchmakingTask,
        })
})
