from django.urls import path

from core import api_turmas, views, views_turmas
from core.admin_site import site

urlpatterns = [
    path("django-admin/", site.urls),
    path("login", views.login_page, name="login"),
    path("api/auth/google", views.google_login, name="google_login"),
    path("api/auth/logout", views.logout_view, name="logout"),
    path("api/me", views.api_me, name="api_me"),
    path("api/turmas", api_turmas.turmas, name="api_turmas"),
    path("api/turmas/<int:turma_id>", api_turmas.turma_detalhe, name="api_turma"),
    path("api/turmas/<int:turma_id>/alunas", api_turmas.turma_alunas, name="api_turma_alunas"),
    path("api/turmas/<int:turma_id>/alunas/<int:aluna_id>", api_turmas.turma_aluna, name="api_turma_aluna"),
    path("api/turmas/<int:turma_id>/liberacoes", api_turmas.turma_liberacoes, name="api_turma_liberacoes"),
    path("api/turmas/<int:turma_id>/liberacoes/<int:quiz_id>", api_turmas.turma_liberacao, name="api_turma_liberacao"),
    path("perfil", views.profile, name="perfil"),
    path("aluna", views.aluna_dashboard, name="aluna_dashboard"),
    path("admin", views.admin_alunas, name="admin_home"),
    path("admin/alunas", views.admin_alunas, name="admin_alunas"),
    path("admin/alunas/<int:user_id>/editar", views.editar_aluna, name="editar_aluna"),
    path("admin/alunas/<int:user_id>/remover", views.remover_aluna, name="remover_aluna"),
    path("admin/turmas", views_turmas.admin_turmas, name="admin_turmas"),
    path("admin/turmas/<int:turma_id>", views_turmas.admin_turma_detalhe, name="admin_turma_detalhe"),
    path("admin/turmas/<int:turma_id>/editar", views_turmas.editar_turma, name="editar_turma"),
    path("admin/turmas/<int:turma_id>/remover", views_turmas.remover_turma, name="remover_turma"),
    path("admin/turmas/<int:turma_id>/alunas", views_turmas.turma_adicionar_alunas, name="turma_adicionar_alunas"),
    path("admin/turmas/<int:turma_id>/alunas/<int:aluna_id>/remover", views_turmas.turma_remover_aluna, name="turma_remover_aluna"),
    path("admin/turmas/<int:turma_id>/liberacoes", views_turmas.turma_liberar_quiz, name="turma_liberar_quiz"),
    path("admin/turmas/<int:turma_id>/liberacoes/<int:quiz_id>/alterar", views_turmas.turma_alterar_liberacao, name="turma_alterar_liberacao"),
    path("admin/turmas/<int:turma_id>/liberacoes/<int:quiz_id>/retirar", views_turmas.turma_retirar_liberacao, name="turma_retirar_liberacao"),
    path("", views.home, name="home"),
]
