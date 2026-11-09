"""Utilitários compartilhados pelas views da API JSON."""
import json
from functools import wraps

from django.http import JsonResponse

from .decorators import api_mentor_required


class ApiError(Exception):
    def __init__(self, error, status=400, **extra):
        super().__init__(error)
        self.status = status
        self.payload = {"error": error, **extra}


def api_endpoint(*methods):
    """Protege a view para mentoras, restringe os métodos HTTP e converte
    ApiError em resposta JSON."""

    def decorator(view):
        @wraps(view)
        @api_mentor_required
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                resposta = JsonResponse({"error": "method_not_allowed"}, status=405)
                resposta["Allow"] = ", ".join(methods)
                return resposta
            try:
                return view(request, *args, **kwargs)
            except ApiError as erro:
                return JsonResponse(erro.payload, status=erro.status)

        return wrapped

    return decorator


def read_json_object(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("invalid_json") from None
    if not isinstance(data, dict):
        raise ApiError("invalid_json")
    return data


def validation_error(form):
    details = {campo: [str(e) for e in erros] for campo, erros in form.errors.items()}
    return ApiError("validation_error", details=details)
