import asyncio
from django.db import models
from django.contrib.auth.models import User
from channels.db import database_sync_to_async


# Create your models here.
class ChatUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_user', unique=True, null=False)
    birth_date = models.DateField(null=True)
    reason_to_isolation = models.TextField(max_length=300)

    def __str__(self):
        return self.user.username


class Conversation(models.Model):
    attendees = models.ManyToManyField(ChatUser, 'conversations')
    is_open = models.BooleanField(default=True)


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
            raise Message.DoesNotExist()

        return True

    @staticmethod
    async def create_message_async(author_id, conversation_id, text):
        return await database_sync_to_async(Message.objects.create)(
            author_id=author_id,
            conversation_id=conversation_id,
            text=text
        )
