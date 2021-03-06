import asyncio
from django.db import models
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.db import IntegrityError
from django.db import transaction
import time


# Create your models here.
class ChatUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_user', unique=True, null=False)
    name = models.TextField(max_length=50, default='')
    age = models.IntegerField(null=True)
    reason_to_isolation = models.TextField(max_length=300, default='')

    @staticmethod
    def create_chat_user(user, name=None, age=None, reason_to_isolation=None):
        return ChatUser.objects.create(name=name, user_id=user.id, age=age, reason_to_isolation=reason_to_isolation)

    def __str__(self):
        return self.user.username


class Conversation(models.Model):
    attendees = models.ManyToManyField(ChatUser, 'conversations')
    is_open = models.BooleanField(default=True)

    @staticmethod
    def create_conversation(attendees_id):
        with transaction.atomic():
            conversation = Conversation.objects.create()
            conversation.attendees.add(*attendees_id)
            conversation.save()

        return conversation

    async def close_conversation(self):
        self.is_open = False
        return await database_sync_to_async(self.save)()

    def __str__(self):
        return 'Conversation of: ' + ', '.join([f'{chat_user.user.first_name} {chat_user.user.last_name}' for chat_user in self.attendees.all()])


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(ChatUser, on_delete=models.CASCADE, related_name='messages')
    text = models.TextField(max_length=500)
    time = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def validate_message_creation(author_id, conversation_id):
        conversation = Conversation.objects.filter(id=conversation_id, attendees__in=[author_id], is_open=True)

        # didn't find any matching conversation
        if len(conversation) == 0:
            raise Conversation.DoesNotExist()

        return True

    @staticmethod
    def create_message(author_id, conversation_id, text):
        return Message.objects.create(
            author_id=author_id,
            conversation_id=conversation_id,
            text=text
        )
