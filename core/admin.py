from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .admin_site import site
from .models import (
    Alternativa,
    Fase,
    Liberacao,
    PerfilUsuario,
    Pergunta,
    Quiz,
    Resposta,
    Tentativa,
    Turma,
)

User = get_user_model()


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    extra = 0


class QuiXUserAdmin(UserAdmin):
    inlines = [PerfilUsuarioInline]

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model is PerfilUsuario:
            user = form.instance
            user.is_staff = (
                user.is_superuser
                or user.perfil.tipo == PerfilUsuario.Tipo.MENTORA
            )
            user.save(update_fields=["is_staff"])


site.register(User, QuiXUserAdmin)


class QuizInline(admin.TabularInline):  # quizzes dentro da pág da fase, em tabela
    model = Quiz  # qual model a tabela mostra
    max_num = 0  # n deixa add quiz novo, já nascem c/ a fase
    can_delete = False  # tira o "apagar" de cada linha
    show_change_link = True  # link "alterar" p/ abrir o quiz
    readonly_fields = ["tipo"]  # tipo só p/ ver, n dá p/ trocar


@admin.register(Fase, site=site)  # registra a fase no admin
class FaseAdmin(admin.ModelAdmin):
    list_display = ["numero", "nome"]  # colunas da lista de fases
    inlines = [QuizInline]  # mostra os quizzes dentro da fase


class PerguntaInline(admin.StackedInline):  # perguntas dentro da pág do quiz, em blocos
    model = Pergunta
    extra = 0  # sem blocos vazios, p/ pág n ficar enorme
    show_change_link = True  # link p/ abrir a pergunta e editar as alternativas


@admin.register(Quiz, site=site)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["__str__", "tipo"]  # __str__ = "Fase 3: ... - Teórico"
    list_filter = ["tipo"]  # filtro na lateral: teórico ou prático
    inlines = [PerguntaInline]  # mostra as perguntas dentro do quiz


class AlternativaInline(admin.TabularInline):  # alternativas dentro da pág da pergunta
    model = Alternativa
    extra = 4  # já abre c/ 4 linhas vazias p/ preencher


@admin.register(Pergunta, site=site)
class PerguntaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "quiz", "ordem"]  # colunas: enunciado, quiz e ordem
    list_filter = ["quiz"]  # filtra perguntas por quiz
    inlines = [AlternativaInline]  # mostra as alternativas dentro da pergunta


class RespostaInline(admin.TabularInline):  # respostas da aluna dentro da tentativa
    model = Resposta
    extra = 0  # sem linhas vazias, qm cria resposta é a aluna


@admin.register(Tentativa, site=site)
class TentativaAdmin(admin.ModelAdmin):
    list_display = ["aluna", "quiz", "acertos", "total", "oficial", "criada_em"]  # colunas da lista
    list_filter = ["oficial", "quiz"]  # filtra por oficial/treino e por quiz
    inlines = [RespostaInline]  # mostra o q a aluna marcou em cada pergunta


class LiberacaoInline(admin.TabularInline):  # cronograma de liberação dentro da pág da turma
    model = Liberacao
    extra = 0


@admin.register(Turma, site=site)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ["nome", "criada_em"]
    search_fields = ["nome"]
    inlines = [LiberacaoInline]
