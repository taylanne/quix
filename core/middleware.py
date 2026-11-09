from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect


class DeveloperAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        allowed_emails = getattr(settings, "QUIX_DEVELOPER_EMAILS", ())
        if user.is_authenticated and user.email.casefold() not in allowed_emails:
            logout(request)
            if request.path == "/login":
                return self.get_response(request)
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "developer_access_required"}, status=403)
            return redirect("login")
        return self.get_response(request)
