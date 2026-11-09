from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models.signals import post_save
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import PerfilUsuario


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        tipo = (
            PerfilUsuario.Tipo.MENTORA
            if instance.is_staff or instance.is_superuser
            else PerfilUsuario.Tipo.ALUNA
        )
        PerfilUsuario.objects.create(usuario=instance, tipo=tipo)


@receiver(post_migrate)
def create_local_demo_account(sender, **kwargs):
    if sender.name != "core" or not settings.QUIX_LOCAL_PASSWORD_LOGIN:
        return

    database = kwargs.get("using", "default")
    if connections[database].vendor != "sqlite":
        return

    User = get_user_model()
    email = settings.QUIX_LOCAL_DEMO_EMAIL.strip().casefold()
    if not email or not settings.QUIX_LOCAL_DEMO_PASSWORD:
        raise ImproperlyConfigured("As credenciais da conta local de demonstração estão vazias.")

    if User.objects.using(database).filter(email__iexact=email).exists():
        return

    username = email
    suffix = 2
    while User.objects.using(database).filter(username__iexact=username).exists():
        username = f"{email}-{suffix}"
        suffix += 1

    User.objects.db_manager(database).create_superuser(
        username=username,
        email=email,
        password=settings.QUIX_LOCAL_DEMO_PASSWORD,
        first_name="Jessica",
    )
