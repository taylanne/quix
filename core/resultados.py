from django.db.models import Count, Sum
from .models import Fase, Quiz, Tentativa


def resumo_desempenho_aluna(aluna):
    """Calcula pontuação oficial, total de quizzes respondidos e progresso geral."""
    tentativas_oficiais = Tentativa.objects.filter(aluna=aluna, oficial=True)

    agregados = tentativas_oficiais.aggregate(
        pontos_obtidos=Sum("acertos"),
        pontos_possiveis=Sum("total"),
    )
    pontos_obtidos = agregados["pontos_obtidos"] or 0
    pontos_possiveis = agregados["pontos_possiveis"] or 0

    quizzes_respondidos = tentativas_oficiais.count()
    total_quizzes = Quiz.objects.count()

    progresso_percentual = (
        round((quizzes_respondidos / total_quizzes) * 100)
        if total_quizzes > 0
        else 0
    )

    aproveitamento_percentual = (
        round((pontos_obtidos / pontos_possiveis) * 100)
        if pontos_possiveis > 0
        else 0
    )

    return {
        "pontos_obtidos": pontos_obtidos,
        "pontos_possiveis": pontos_possiveis,
        "quizzes_respondidos": quizzes_respondidos,
        "total_quizzes": total_quizzes,
        "progresso_percentual": progresso_percentual,
        "aproveitamento_percentual": aproveitamento_percentual,
    }


def historico_aluna(aluna):
    """Retorna a lista de quizzes já respondidos com a nota oficial e nº de tentativas."""
    tentativas_oficiais = (
        Tentativa.objects.filter(aluna=aluna, oficial=True)
        .select_related("quiz", "quiz__fase")
        .order_by("quiz__fase__numero", "-quiz__tipo")
    )

    # Conta quantas tentativas no total a aluna fez por quiz (oficial + treinos)
    contagem_por_quiz = dict(
        Tentativa.objects.filter(aluna=aluna)
        .values("quiz_id")
        .annotate(qtd=Count("id"))
        .values_list("quiz_id", "qtd")
    )

    itens = []
    for tentativa in tentativas_oficiais:
        nota_percentual = (
            round((tentativa.acertos / tentativa.total) * 100)
            if tentativa.total > 0
            else 0
        )
        itens.append(
            {
                "quiz": tentativa.quiz,
                "fase": tentativa.quiz.fase,
                "acertos": tentativa.acertos,
                "total": tentativa.total,
                "nota_percentual": nota_percentual,
                "data_oficial": tentativa.criada_em,
                "total_tentativas": contagem_por_quiz.get(tentativa.quiz_id, 1),
            }
        )
    return itens