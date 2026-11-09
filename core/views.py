import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from google.auth.exceptions import GoogleAuthError

from .access import get_or_create_profile, is_developer, is_mentor
from .authentication import verify_google_credential
from .decorators import developer_required, mentor_required
from .forms import AlunaForm, LocalLoginForm
from .models import PerfilUsuario

User = get_user_model()


def home(request):
    if request.user.is_authenticated:
        if not is_developer(request.user):
            return HttpResponseForbidden("Acesso restrito à equipe de desenvolvimento.")
        if is_mentor(request.user):
            return redirect("admin_alunas")
        return redirect("aluna_dashboard")
    return render(request, "home/index.html")


@ensure_csrf_cookie
def login_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = LocalLoginForm(request.POST or None)
    if request.method == "POST":
        if not settings.QUIX_LOCAL_PASSWORD_LOGIN:
            return HttpResponseForbidden("Login local disponível apenas em desenvolvimento.")
        if form.is_valid():
            email = form.cleaned_data["email"].casefold()
            matches = list(User.objects.filter(email__iexact=email).order_by("pk")[:2])
            user = None
            if len(matches) == 1 and matches[0].is_active:
                user = authenticate(
                    request,
                    username=matches[0].get_username(),
                    password=form.cleaned_data["password"],
                )
            if user is not None and is_developer(user):
                login(request, user)
                return redirect("admin_alunas" if is_mentor(user) else "aluna_dashboard")
            form.add_error(None, "E-mail ou senha inválidos.")

    return render(
        request,
        "auth/login.html",
        {
            "form": form,
            "google_client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "login_enabled": bool(
                settings.GOOGLE_OAUTH_CLIENT_ID and settings.QUIX_DEVELOPER_EMAILS
            ),
            "local_password_login_enabled": settings.QUIX_LOCAL_PASSWORD_LOGIN,
        },
    )


def _read_google_credential(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data.get("credential")
    return request.POST.get("credential")


@require_POST
def google_login(request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        return JsonResponse({"error": "google_login_not_configured"}, status=503)
    if not settings.QUIX_DEVELOPER_EMAILS:
        return JsonResponse({"error": "developer_access_not_configured"}, status=503)

    credential = _read_google_credential(request)
    if not isinstance(credential, str) or not credential:
        return JsonResponse({"error": "invalid_request"}, status=400)

    try:
        claims = verify_google_credential(credential)
    except GoogleAuthError:
        return JsonResponse({"error": "google_verification_unavailable"}, status=503)
    if not claims:
        return JsonResponse({"error": "invalid_google_credential"}, status=401)

    email = claims.get("email")
    if (
        not isinstance(email, str)
        or claims.get("email_verified") is not True
        or email.casefold() not in settings.QUIX_DEVELOPER_EMAILS
    ):
        return JsonResponse({"error": "developer_access_required"}, status=403)

    matches = list(User.objects.filter(email__iexact=email).order_by("pk")[:2])
    if len(matches) != 1 or not matches[0].is_active:
        return JsonResponse({"error": "account_not_registered"}, status=403)

    user = matches[0]
    perfil, _ = get_or_create_profile(user)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    redirect_url = (
        "/admin/alunas"
        if user.is_superuser or perfil.tipo == PerfilUsuario.Tipo.MENTORA
        else "/aluna"
    )
    return JsonResponse({"redirect_url": redirect_url})


@require_POST
def logout_view(request):
    logout(request)
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"success": True})
    return redirect("home")


def api_me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if not is_developer(request.user):
        return JsonResponse({"error": "developer_access_required"}, status=403)
    perfil, _ = get_or_create_profile(request.user)
    return JsonResponse(
        {
            "id": request.user.pk,
            "name": request.user.get_full_name() or request.user.email,
            "email": request.user.email,
            "role": perfil.tipo,
        }
    )


@developer_required
def profile(request):
    perfil, _ = get_or_create_profile(request.user)
    return render(request, "core/perfil.html", {"perfil": perfil})


@developer_required
def aluna_dashboard(request):
    if is_mentor(request.user):
        return redirect("admin_alunas")
    return render(request, "core/aluna.html")


def _alunas_ativas():
    return User.objects.filter(
        perfil__tipo=PerfilUsuario.Tipo.ALUNA,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )


def _username_for_email(email):
    base = slugify(email)[:130] or "aluna"
    username = base
    suffix = 2
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base}-{suffix}"
        suffix += 1
    return username


@mentor_required
def admin_alunas(request):
    form = AlunaForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            nome = form.cleaned_data["nome"].strip()
            nomes = nome.split(maxsplit=1)
            with transaction.atomic():
                user = User.objects.create_user(
                    username=_username_for_email(form.cleaned_data["email"]),
                    email=form.cleaned_data["email"],
                    first_name=nomes[0],
                    last_name=nomes[1] if len(nomes) > 1 else "",
                    password=None,
                )
                PerfilUsuario.objects.filter(usuario=user).update(
                    tipo=PerfilUsuario.Tipo.ALUNA
                )
            messages.success(request, "Aluna cadastrada com sucesso.")
            return redirect("admin_alunas")

    consulta = request.GET.get("q", "").strip()
    alunas = _alunas_ativas()
    if consulta:
        alunas = alunas.filter(
            Q(first_name__icontains=consulta)
            | Q(last_name__icontains=consulta)
            | Q(email__icontains=consulta)
        )
    return render(
        request,
        "core/admin/alunas.html",
        {"form": form, "alunas": alunas, "consulta": consulta},
    )


@mentor_required
def editar_aluna(request, user_id):
    aluna = get_object_or_404(_alunas_ativas(), pk=user_id)
    form = AlunaForm(
        request.POST or None,
        usuario=aluna,
        initial={
            "nome": aluna.get_full_name(),
            "email": aluna.email,
        },
    )
    if request.method == "POST" and form.is_valid():
        nome = form.cleaned_data["nome"].strip().split(maxsplit=1)
        aluna.first_name = nome[0]
        aluna.last_name = nome[1] if len(nome) > 1 else ""
        aluna.email = form.cleaned_data["email"]
        aluna.save(update_fields=["first_name", "last_name", "email"])
        messages.success(request, "Cadastro da aluna atualizado.")
        return redirect("admin_alunas")
    return render(
        request,
        "core/admin/editar_aluna.html",
        {"form": form, "aluna": aluna},
    )


@mentor_required
@require_POST
def remover_aluna(request, user_id):
    aluna = get_object_or_404(_alunas_ativas(), pk=user_id)
    aluna.is_active = False
    aluna.save(update_fields=["is_active"])
    messages.success(request, "Acesso da aluna removido.")
    return redirect("admin_alunas")
