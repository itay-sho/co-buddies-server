from django.contrib import admin
from .models import ChatUser, Conversation, Message

# Register your models here.
admin.site.register(ChatUser)
admin.site.register(Conversation)
admin.site.register(Message)
