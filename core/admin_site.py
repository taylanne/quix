from django.contrib.admin import AdminSite
from django.shortcuts import redirect

from .access import is_developer, is_mentor


class QuiXAdminSite(AdminSite):
    def has_permission(self, request):
        user = request.user
        return (
            user.is_active
            and user.is_staff
            and is_developer(user)
            and is_mentor(user)
        )

    def login(self, request, extra_context=None):
        return redirect("login")


site = QuiXAdminSite(name="admin")
