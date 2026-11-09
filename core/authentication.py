from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import id_token


def verify_google_credential(credential):
    try:
        return id_token.verify_oauth2_token(
            credential,
            Request(),
            audience=settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except ValueError:
        return None
