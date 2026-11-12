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

def consultar_resultados_mentora(fase_id=None, quiz_id=None, aluna_id=None):
    """Retorna as tentativas oficiais (1ª tentativa) filtradas para a mentora."""
    qs = (
        Tentativa.objects.filter(oficial=True)
        .select_related("aluna", "quiz", "quiz__fase")
        .order_by("quiz__fase__numero", "-quiz__tipo", "aluna__first_name", "aluna__email")
    )

    if fase_id:
        qs = qs.filter(quiz__fase_id=fase_id)
    if quiz_id:
        qs = qs.filter(quiz_id=quiz_id)
    if aluna_id:
        qs = qs.filter(aluna_id=aluna_id)

    # Conta total de tentativas (oficial + treinos) por par (aluna, quiz)
    contagens = {
        (row["aluna_id"], row["quiz_id"]): row["qtd"]
        for row in Tentativa.objects.values("aluna_id", "quiz_id").annotate(qtd=Count("id"))
    }

    resultados = []
    for t in qs:
        nota_percentual = round((t.acertos / t.total) * 100) if t.total > 0 else 0
        resultados.append(
            {
                "id": t.id,
                "aluna_id": t.aluna_id,
                "aluna_nome": t.aluna.get_full_name() or t.aluna.email,
                "aluna_email": t.aluna.email,
                "fase_id": t.quiz.fase_id,
                "fase_numero": t.quiz.fase.numero,
                "fase_nome": t.quiz.fase.nome,
                "quiz_id": t.quiz_id,
                "quiz_tipo": t.quiz.tipo,
                "quiz_tipo_label": t.quiz.get_tipo_display(),
                "acertos": t.acertos,
                "total": t.total,
                "nota_percentual": nota_percentual,
                "tentativas_total": contagens.get((t.aluna_id, t.quiz_id), 1),
                "criada_em": t.criada_em,
            }
        )

    return resultados