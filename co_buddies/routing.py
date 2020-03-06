import asyncio
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from chat.middewares import QueryAuthMiddleware
from channels.security.websocket import AllowedHostsOriginValidator

from chat.consumers import ChatConsumer

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
        )
})
