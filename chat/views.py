from rest_auth.registration.views import RegisterView
from allauth.account import app_settings as allauth_settings


class CustomerRegisterView(RegisterView):
    def get_response_data(self, user):
        if allauth_settings.EMAIL_VERIFICATION == allauth_settings.EmailVerificationMethod.MANDATORY:
            return {"detail": _("Verification e-mail sent.")}

        return {
            'key': user.auth_token.key,
            'id': user.chat_user.id
        }
