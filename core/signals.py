from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from core.security import issue_security_session


@receiver(user_logged_in)
def set_login_security_session(sender, request, user, **kwargs):
    issue_security_session(request)
