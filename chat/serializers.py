from .models import ChatUser
import rest_auth.registration.serializers
from django.db import transaction
from rest_framework import serializers


class RegisterSerializer(rest_auth.registration.serializers.RegisterSerializer):
    reason_to_isolation = serializers.CharField(max_length=300, default='', required=False)
    age = serializers.IntegerField(required=False)

    def get_cleaned_data(self):
        cleaned_data = super().get_cleaned_data()
        cleaned_data.update(
            {
                'age': self.validated_data.get('age', None),
                'reason_to_isolation': self.validated_data.get('reason_to_isolation', ''),
            }
        )

        return cleaned_data

    def custom_signup(self, request, user):
        ChatUser.create_chat_user(
            user,
            age=self.cleaned_data['age'],
            reason_to_isolation=self.cleaned_data['reason_to_isolation']
        )

    def save(self, request):
        with transaction.atomic():
            return super().save(request)
