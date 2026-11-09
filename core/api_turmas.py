from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .api import ApiError, api_endpoint, read_json_object, validation_error
from .forms import AdicionarAlunasForm, DataLiberacaoForm, LiberacaoForm, TurmaForm
from .models import Turma
from .turmas import (
    LiberacaoJaExiste,
    adicionar_alunas,
    alterar_data_liberacao,
    alunas_da_turma,
    cronograma,
    liberar_quiz,
    remover_aluna_da_turma,
    retirar_liberacao,
    turmas_com_totais,
)


# --- Serialização -----------------------------------------------------------

def _turma(turma):
    return {
        "id": turma.pk,
        "nome": turma.nome,
        "total_alunas": turma.total_alunas,
        "total_liberacoes": turma.total_liberacoes,
    }


def _turma_ref(turma):
    return None if turma is None else {"id": turma.pk, "nome": turma.nome}


def _aluna(user):
    return {"id": user.pk, "nome": user.get_full_name() or user.email, "email": user.email}


def _liberacao(liberacao, hoje):
    return {
        "quiz": liberacao.quiz_id,
        "data": liberacao.data.isoformat(),
        "liberada": liberacao.liberada(hoje),
    }


def _obter_turma(turma_id):
    try:
        return turmas_com_totais().get(pk=turma_id)
    except Turma.DoesNotExist:
        raise ApiError("not_found", status=404) from None


# --- Turmas -----------------------------------------------------------------

@api_endpoint("GET", "POST")
def turmas(request):
    if request.method == "GET":
        return JsonResponse({"turmas": [_turma(t) for t in turmas_com_totais()]})

    form = TurmaForm(read_json_object(request))
    if not form.is_valid():
        raise validation_error(form)
    turma = form.save()
    return JsonResponse(_turma(_obter_turma(turma.pk)), status=201)


@api_endpoint("GET", "PUT", "DELETE")
def turma_detalhe(request, turma_id):
    turma = _obter_turma(turma_id)

    if request.method == "GET":
        return JsonResponse(_turma(turma))

    if request.method == "DELETE":
        turma.delete()
        return HttpResponse(status=204)

    form = TurmaForm(read_json_object(request), instance=turma)
    if not form.is_valid():
        raise validation_error(form)
    form.save()
    return JsonResponse(_turma(_obter_turma(turma_id)))


# --- Alunas da turma ----------------------------------------------------------

@api_endpoint("GET", "POST")
def turma_alunas(request, turma_id):
    turma = _obter_turma(turma_id)

    if request.method == "GET":
        return JsonResponse({"alunas": [_aluna(a) for a in alunas_da_turma(turma)]})

    form = AdicionarAlunasForm(read_json_object(request))
    if not form.is_valid():
        raise validation_error(form)
    alteradas = adicionar_alunas(turma, form.cleaned_data["alunas"])
    return JsonResponse(
        {
            "adicionadas": [
                {**_aluna(aluna), "turma_anterior": _turma_ref(anterior)}
                for aluna, anterior in alteradas
            ]
        }
    )


@api_endpoint("DELETE")
def turma_aluna(request, turma_id, aluna_id):
    turma = _obter_turma(turma_id)
    if not remover_aluna_da_turma(turma, aluna_id):
        raise ApiError("not_found", status=404)
    return HttpResponse(status=204)


# --- Liberações -------------------------------------------------------------

def _cronograma_json(turma):
    hoje = timezone.localdate()
    return {
        "fases": [
            {
                "id": item["fase"].pk,
                "numero": item["fase"].numero,
                "nome": item["fase"].nome,
                "quizzes": [
                    {
                        "id": q["quiz"].pk,
                        "tipo": q["quiz"].tipo,
                        "liberacao": (
                            _liberacao(q["liberacao"], hoje) if q["liberacao"] else None
                        ),
                    }
                    for q in item["quizzes"]
                ],
            }
            for item in cronograma(turma, hoje)
        ]
    }


@api_endpoint("GET", "POST")
def turma_liberacoes(request, turma_id):
    turma = _obter_turma(turma_id)

    if request.method == "GET":
        return JsonResponse(_cronograma_json(turma))

    form = LiberacaoForm(read_json_object(request))
    if not form.is_valid():
        raise validation_error(form)
    try:
        liberacao = liberar_quiz(turma, form.cleaned_data["quiz"], form.cleaned_data["data"])
    except LiberacaoJaExiste:
        raise ApiError("already_released", status=409) from None
    return JsonResponse(_liberacao(liberacao, timezone.localdate()), status=201)


@api_endpoint("PUT", "DELETE")
def turma_liberacao(request, turma_id, quiz_id):
    turma = _obter_turma(turma_id)

    if request.method == "DELETE":
        if not retirar_liberacao(turma, quiz_id):
            raise ApiError("not_found", status=404)
        return HttpResponse(status=204)

    form = DataLiberacaoForm(read_json_object(request))
    if not form.is_valid():
        raise validation_error(form)
    liberacao = alterar_data_liberacao(turma, quiz_id, form.cleaned_data["data"])
    if liberacao is None:
        raise ApiError("not_found", status=404)
    return JsonResponse(_liberacao(liberacao, timezone.localdate()))
