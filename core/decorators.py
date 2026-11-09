from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse

from .access import is_developer, is_mentor


def developer_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("login"))
        if not is_developer(request.user):
            return HttpResponseForbidden("Acesso restrito à equipe de desenvolvimento.")
        return view(request, *args, **kwargs)

    return wrapped


def mentor_required(view):
    @wraps(view)
    @developer_required
    def wrapped(request, *args, **kwargs):
        if not is_mentor(request.user):
            return HttpResponseForbidden("Acesso restrito às mentoras.")
        return view(request, *args, **kwargs)

    return wrapped


def api_mentor_required(view):
    """Como mentor_required, mas responde JSON (401/403) em vez de redirecionar."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "authentication_required"}, status=401)
        if not is_developer(request.user):
            return JsonResponse({"error": "developer_access_required"}, status=403)
        if not is_mentor(request.user):
            return JsonResponse({"error": "mentor_required"}, status=403)
        return view(request, *args, **kwargs)

    return wrapped
