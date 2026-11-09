from django.urls import path

from core import views
from core.admin_site import site

urlpatterns = [
    path("django-admin/", site.urls),
    path("login", views.login_page, name="login"),
    path("api/auth/google", views.google_login, name="google_login"),
    path("api/auth/logout", views.logout_view, name="logout"),
    path("api/me", views.api_me, name="api_me"),
    path("perfil", views.profile, name="perfil"),
    path("aluna", views.aluna_dashboard, name="aluna_dashboard"),
    path("admin", views.admin_alunas, name="admin_home"),
    path("admin/alunas", views.admin_alunas, name="admin_alunas"),
    path("admin/alunas/<int:user_id>/editar", views.editar_aluna, name="editar_aluna"),
    path("admin/alunas/<int:user_id>/remover", views.remover_aluna, name="remover_aluna"),
    path("", views.home, name="home"),
]
