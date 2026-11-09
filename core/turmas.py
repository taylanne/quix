"""Regras de negócio de turmas, alunas da turma e liberações de quiz.

Usado tanto pelas páginas da mentora quanto pela API, para que as duas sigam
exatamente as mesmas regras.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Fase, Liberacao, PerfilUsuario, Quiz, Turma

User = get_user_model()


class LiberacaoJaExiste(Exception):
    """O quiz já está liberado para a turma (use a alteração de data)."""


# --- Turmas ---------------------------------------------------------------

def turmas_com_totais():
    return Turma.objects.annotate(
        total_alunas=Count(
            "perfis",
            filter=Q(perfis__tipo=PerfilUsuario.Tipo.ALUNA, perfis__usuario__is_active=True),
            distinct=True,
        ),
        total_liberacoes=Count("liberacoes", distinct=True),
    )


# --- Alunas da turma --------------------------------------------------------

def alunas_ativas():
    return User.objects.filter(
        perfil__tipo=PerfilUsuario.Tipo.ALUNA,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )


def _ordenar(alunas):
    return alunas.order_by("first_name", "last_name", "email")


def alunas_da_turma(turma):
    return _ordenar(alunas_ativas().filter(perfil__turma=turma))


def alunas_disponiveis(turma):
    """Alunas que ainda não estão nesta turma (podem estar em outra ou em nenhuma)."""
    return _ordenar(
        alunas_ativas().exclude(perfil__turma=turma).select_related("perfil__turma")
    )


@transaction.atomic
def adicionar_alunas(turma, alunas):
    """Coloca as alunas na turma. Cada aluna só tem uma turma, então quem já está
    em outra é movida. Devolve [(aluna, turma_anterior_ou_None)] só de quem mudou."""
    alteradas = []
    for aluna in alunas:
        perfil = aluna.perfil
        if perfil.turma_id == turma.pk:
            continue
        anterior = perfil.turma
        perfil.turma = turma
        perfil.save(update_fields=["turma"])
        alteradas.append((aluna, anterior))
    return alteradas


def remover_aluna_da_turma(turma, aluna_id):
    """Tira a aluna da turma. Devolve False se ela não estava nesta turma."""
    return bool(
        PerfilUsuario.objects.filter(usuario_id=aluna_id, turma=turma).update(turma=None)
    )


# --- Liberações -------------------------------------------------------------

def cronograma(turma, hoje=None):
    """Cronograma da turma organizado por fase: toda fase aparece com seus dois
    quizzes (teórico primeiro), liberados ou não."""
    hoje = hoje or timezone.localdate()
    liberacoes = {l.quiz_id: l for l in turma.liberacoes.all()}
    fases = []
    for fase in Fase.objects.prefetch_related("quizzes"):
        quizzes = sorted(
            fase.quizzes.all(), key=lambda q: q.tipo != Quiz.Tipo.TEORICO
        )
        fases.append(
            {
                "fase": fase,
                "quizzes": [
                    {
                        "quiz": quiz,
                        "liberacao": liberacoes.get(quiz.pk),
                        "liberada": (
                            quiz.pk in liberacoes and liberacoes[quiz.pk].data <= hoje
                        ),
                    }
                    for quiz in quizzes
                ],
            }
        )
    return fases


def liberar_quiz(turma, quiz, data):
    try:
        with transaction.atomic():
            return Liberacao.objects.create(turma=turma, quiz=quiz, data=data)
    except IntegrityError:
        raise LiberacaoJaExiste from None


def alterar_data_liberacao(turma, quiz_id, data):
    """Muda a data da liberação. Devolve a liberação, ou None se o quiz não está liberado."""
    atualizadas = Liberacao.objects.filter(turma=turma, quiz_id=quiz_id).update(data=data)
    if not atualizadas:
        return None
    return Liberacao.objects.select_related("quiz").get(turma=turma, quiz_id=quiz_id)


def retirar_liberacao(turma, quiz_id):
    """Retira o quiz da turma. Devolve False se ele não estava liberado."""
    apagadas, _ = Liberacao.objects.filter(turma=turma, quiz_id=quiz_id).delete()
    return bool(apagadas)
