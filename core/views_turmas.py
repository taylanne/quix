from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import mentor_required
from .forms import AdicionarAlunasForm, DataLiberacaoForm, LiberacaoForm, TurmaForm
from .models import Turma
from .turmas import (
    LiberacaoJaExiste,
    adicionar_alunas,
    alterar_data_liberacao,
    alunas_da_turma,
    alunas_disponiveis,
    cronograma,
    liberar_quiz,
    remover_aluna_da_turma,
    retirar_liberacao,
    turmas_com_totais,
)


def _primeiro_erro(form):
    for erros in form.errors.values():
        return erros[0]
    return "Dados inválidos."


@mentor_required
def admin_turmas(request):
    form = TurmaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        turma = form.save()
        messages.success(request, "Turma criada. Agora adicione as alunas.")
        return redirect("admin_turma_detalhe", turma_id=turma.pk)
    return render(
        request,
        "core/admin/turmas.html",
        {"form": form, "turmas": turmas_com_totais()},
    )


@mentor_required
def editar_turma(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    form = TurmaForm(request.POST or None, instance=turma)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Turma atualizada.")
        return redirect("admin_turma_detalhe", turma_id=turma.pk)
    return render(request, "core/admin/editar_turma.html", {"form": form, "turma": turma})


@mentor_required
@require_POST
def remover_turma(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    turma.delete()
    messages.success(request, "Turma removida. As alunas dela ficaram sem turma.")
    return redirect("admin_turmas")


@mentor_required
def admin_turma_detalhe(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    return render(
        request,
        "core/admin/turma_detalhe.html",
        {
            "turma": turma,
            "alunas": alunas_da_turma(turma),
            "candidatas": alunas_disponiveis(turma),
            "cronograma": cronograma(turma),
            "hoje": timezone.localdate(),
        },
    )


@mentor_required
@require_POST
def turma_adicionar_alunas(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    form = AdicionarAlunasForm(request.POST)
    if not form.is_valid():
        messages.error(request, _primeiro_erro(form))
    else:
        alteradas = adicionar_alunas(turma, form.cleaned_data["alunas"])
        movidas = [(a, ant) for a, ant in alteradas if ant is not None]
        messages.success(request, f"{len(alteradas)} aluna(s) na turma.")
        for aluna, anterior in movidas:
            messages.info(
                request,
                f"{aluna.get_full_name() or aluna.email} saiu da turma {anterior.nome}.",
            )
    return redirect("admin_turma_detalhe", turma_id=turma.pk)


@mentor_required
@require_POST
def turma_remover_aluna(request, turma_id, aluna_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    if remover_aluna_da_turma(turma, aluna_id):
        messages.success(request, "Aluna removida da turma.")
    else:
        messages.error(request, "Essa aluna não está nesta turma.")
    return redirect("admin_turma_detalhe", turma_id=turma.pk)


@mentor_required
@require_POST
def turma_liberar_quiz(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    form = LiberacaoForm(request.POST)
    if not form.is_valid():
        messages.error(request, _primeiro_erro(form))
    else:
        try:
            liberar_quiz(turma, form.cleaned_data["quiz"], form.cleaned_data["data"])
            messages.success(request, "Quiz liberado para a turma.")
        except LiberacaoJaExiste:
            messages.error(request, "Esse quiz já está liberado para a turma.")
    return redirect("admin_turma_detalhe", turma_id=turma.pk)


@mentor_required
@require_POST
def turma_alterar_liberacao(request, turma_id, quiz_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    form = DataLiberacaoForm(request.POST)
    if not form.is_valid():
        messages.error(request, _primeiro_erro(form))
    elif alterar_data_liberacao(turma, quiz_id, form.cleaned_data["data"]) is None:
        messages.error(request, "Esse quiz não está liberado para a turma.")
    else:
        messages.success(request, "Data de liberação alterada.")
    return redirect("admin_turma_detalhe", turma_id=turma.pk)


@mentor_required
@require_POST
def turma_retirar_liberacao(request, turma_id, quiz_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    if retirar_liberacao(turma, quiz_id):
        messages.success(request, "Quiz retirado da turma.")
    else:
        messages.error(request, "Esse quiz não está liberado para a turma.")
    return redirect("admin_turma_detalhe", turma_id=turma.pk)
