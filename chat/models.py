from django.db import models
from django.contrib.auth.models import User


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
