from django.conf import settings

from .models import PerfilUsuario


def get_or_create_profile(user):
    tipo = (
        PerfilUsuario.Tipo.MENTORA
        if user.is_staff or user.is_superuser
        else PerfilUsuario.Tipo.ALUNA
    )
    return PerfilUsuario.objects.get_or_create(
        usuario=user,
        defaults={"tipo": tipo},
    )


def is_developer(user):
    allowed_emails = getattr(settings, "QUIX_DEVELOPER_EMAILS", ())
    return user.is_authenticated and user.email.casefold() in allowed_emails


def is_mentor(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return PerfilUsuario.objects.filter(
        usuario=user,
        tipo=PerfilUsuario.Tipo.MENTORA,
    ).exists()
