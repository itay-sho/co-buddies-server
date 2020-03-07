from django.contrib.auth.models import User
import django.db
from channels.middleware import BaseMiddleware
from django.db import close_old_connections


class QueryAuthMiddleware:
    """
    Custom middleware (insecure) that takes user IDs from the query string.
    """

    def __init__(self, inner):
        # Store the ASGI application we were passed
        self.inner = inner

    def __call__(self, scope):
        # Close old database connections to prevent usage of timed out connections
        close_old_connections()

        # Look up user from query string (you should also do things like
        # checking if it is a valid user ID, or if scope["user"] is already
        # populated).
        user = User.objects.get(id=int(scope["query_string"]))

        scope['user'] = user

        # Return the inner application directly and let it run everything else
        return self.inner(dict(scope, user=user))
