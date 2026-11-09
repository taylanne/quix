import json
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import TurmaForm
from .models import Fase, Liberacao, PerfilUsuario, Tentativa, Turma

User = get_user_model()


@override_settings(QUIX_DEVELOPER_EMAILS=("mentora@example.org", "aluna@example.org"))
class TurmaTestCase(TestCase):
    def criar_usuario(self, email, tipo=PerfilUsuario.Tipo.ALUNA, **kwargs):
        user = User.objects.create_user(
            username=email, email=email, password=None, **kwargs
        )
        user.perfil.tipo = tipo
        user.perfil.save(update_fields=["tipo"])
        return user

    def setUp(self):
        self.mentora = self.criar_usuario(
            "mentora@example.org", PerfilUsuario.Tipo.MENTORA, is_staff=True
        )
        self.client.force_login(self.mentora)
        self.fase1 = Fase.objects.create(numero=1, nome="Primeiros passos")
        self.fase2 = Fase.objects.create(numero=2, nome="Interface de usuário")
        self.turma = Turma.objects.create(nome="Turma A")
        self.hoje = timezone.localdate()
        self.amanha = self.hoje + timedelta(days=1)

    def teorico(self, fase):
        return fase.quizzes.get(tipo="teorico")

    def pratico(self, fase):
        return fase.quizzes.get(tipo="pratico")

    def aluna(self, email="ana@example.org", **kwargs):
        return self.criar_usuario(email, first_name="Ana", last_name="Souza", **kwargs)


class RegrasDeLiberacaoTests(TurmaTestCase):
    """Critérios de aceite e regras de negócio, direto nos models."""

    def test_quiz_liberado_para_amanha_nao_aparece_hoje(self):
        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=quiz, data=self.amanha)

        self.assertNotIn(quiz, self.turma.quizzes_liberados())
        self.assertNotIn(self.fase1, self.turma.fases_liberadas())
        # No dia seguinte ele aparece
        self.assertIn(quiz, self.turma.quizzes_liberados(hoje=self.amanha))
        self.assertIn(self.fase1, self.turma.fases_liberadas(hoje=self.amanha))

    def test_quiz_liberado_hoje_ou_antes_aparece(self):
        hoje, ontem = self.teorico(self.fase1), self.teorico(self.fase2)
        Liberacao.objects.create(turma=self.turma, quiz=hoje, data=self.hoje)
        Liberacao.objects.create(turma=self.turma, quiz=ontem, data=self.hoje - timedelta(days=1))

        self.assertCountEqual(self.turma.quizzes_liberados(), [hoje, ontem])

    def test_teorico_e_pratico_da_mesma_fase_em_dias_diferentes(self):
        teorico, pratico = self.teorico(self.fase1), self.pratico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=teorico, data=self.hoje)
        Liberacao.objects.create(turma=self.turma, quiz=pratico, data=self.amanha)

        self.assertEqual(list(self.turma.quizzes_liberados()), [teorico])
        # A fase aparece quando pelo menos um dos quizzes foi liberado
        self.assertEqual(list(self.turma.fases_liberadas()), [self.fase1])
        self.assertCountEqual(
            self.turma.quizzes_liberados(hoje=self.amanha), [teorico, pratico]
        )

    def test_quiz_pode_ser_liberado_para_varias_turmas_com_datas_proprias(self):
        outra = Turma.objects.create(nome="Turma B")
        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=quiz, data=self.hoje)
        Liberacao.objects.create(turma=outra, quiz=quiz, data=self.amanha)

        self.assertIn(quiz, self.turma.quizzes_liberados())
        self.assertNotIn(quiz, outra.quizzes_liberados())

    def test_liberacao_de_uma_turma_nao_vaza_para_outra(self):
        outra = Turma.objects.create(nome="Turma B")
        Liberacao.objects.create(turma=self.turma, quiz=self.teorico(self.fase1), data=self.hoje)

        self.assertFalse(outra.quizzes_liberados().exists())
        self.assertFalse(outra.fases_liberadas().exists())

    def test_data_de_liberacao_vale_no_horario_de_sao_paulo(self):
        self.assertEqual(timezone.get_current_timezone_name(), "America/Sao_Paulo")
        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=quiz, data=date(2026, 11, 10))

        # 01:00 UTC do dia 10 ainda é 22:00 do dia 9 em São Paulo
        antes = datetime(2026, 11, 10, 1, 0, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=antes):
            self.assertNotIn(quiz, self.turma.quizzes_liberados())
        # 04:00 UTC do dia 10 já é 01:00 do dia 10 em São Paulo
        depois = datetime(2026, 11, 10, 4, 0, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=depois):
            self.assertIn(quiz, self.turma.quizzes_liberados())

    def test_cada_quiz_so_pode_ser_liberado_uma_vez_por_turma(self):
        from django.db import IntegrityError, transaction

        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=quiz, data=self.hoje)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Liberacao.objects.create(turma=self.turma, quiz=quiz, data=self.amanha)

    def test_nome_da_turma_e_unico_sem_diferenciar_maiusculas(self):
        form = TurmaForm({"nome": "  turma a "})
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe uma turma com este nome.", form.errors["nome"])

    def test_remover_turma_deixa_alunas_sem_turma_e_preserva_tentativas(self):
        aluna = self.aluna()
        aluna.perfil.turma = self.turma
        aluna.perfil.save()
        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=self.turma, quiz=quiz, data=self.hoje)
        tentativa = Tentativa.objects.create(aluna=aluna, quiz=quiz, acertos=1, total=2)

        self.turma.delete()

        aluna.perfil.refresh_from_db()
        self.assertIsNone(aluna.perfil.turma)
        self.assertFalse(Liberacao.objects.exists())
        self.assertTrue(Tentativa.objects.filter(pk=tentativa.pk).exists())


class PaginasDeTurmasTests(TurmaTestCase):
    def test_aluna_nao_acessa_paginas_de_turmas(self):
        self.client.force_login(self.aluna("aluna@example.org"))
        for nome, args in [
            ("admin_turmas", []),
            ("admin_turma_detalhe", [self.turma.pk]),
            ("editar_turma", [self.turma.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        resposta = self.client.post(reverse("remover_turma", args=[self.turma.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Turma.objects.filter(pk=self.turma.pk).exists())

    def test_visitante_e_enviado_para_o_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("admin_turmas"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta["Location"])

    def test_mentora_cria_turma_e_cai_no_detalhe(self):
        resposta = self.client.post(reverse("admin_turmas"), {"nome": "Turma B"})
        turma = Turma.objects.get(nome="Turma B")
        self.assertRedirects(resposta, reverse("admin_turma_detalhe", args=[turma.pk]))

    def test_nome_duplicado_mostra_erro(self):
        resposta = self.client.post(reverse("admin_turmas"), {"nome": "turma a"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma turma com este nome.")
        self.assertEqual(Turma.objects.count(), 1)

    def test_lista_mostra_totais(self):
        aluna = self.aluna()
        aluna.perfil.turma = self.turma
        aluna.perfil.save()
        Liberacao.objects.create(turma=self.turma, quiz=self.teorico(self.fase1), data=self.hoje)

        resposta = self.client.get(reverse("admin_turmas"))

        turma = resposta.context["turmas"].get(pk=self.turma.pk)
        self.assertEqual((turma.total_alunas, turma.total_liberacoes), (1, 1))

    def test_mentora_edita_e_remove_turma(self):
        resposta = self.client.post(reverse("editar_turma", args=[self.turma.pk]), {"nome": "Turma Z"})
        self.assertRedirects(resposta, reverse("admin_turma_detalhe", args=[self.turma.pk]))
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.nome, "Turma Z")

        # Remover só aceita POST
        self.assertEqual(self.client.get(reverse("remover_turma", args=[self.turma.pk])).status_code, 405)
        resposta = self.client.post(reverse("remover_turma", args=[self.turma.pk]))
        self.assertRedirects(resposta, reverse("admin_turmas"))
        self.assertFalse(Turma.objects.exists())

    def test_mentora_monta_turma_adicionando_e_removendo_alunas(self):
        ana, bia = self.aluna("ana@example.org"), self.aluna("bia@example.org")

        self.client.post(reverse("turma_adicionar_alunas", args=[self.turma.pk]), {"alunas": [ana.pk, bia.pk]})
        detalhe = self.client.get(reverse("admin_turma_detalhe", args=[self.turma.pk]))
        self.assertCountEqual(detalhe.context["alunas"], [ana, bia])
        self.assertContains(detalhe, "ana@example.org")

        self.client.post(reverse("turma_remover_aluna", args=[self.turma.pk, ana.pk]))
        ana.perfil.refresh_from_db()
        self.assertIsNone(ana.perfil.turma)
        bia.perfil.refresh_from_db()
        self.assertEqual(bia.perfil.turma, self.turma)

    def test_adicionar_sem_escolher_aluna_mostra_erro(self):
        resposta = self.client.post(
            reverse("turma_adicionar_alunas", args=[self.turma.pk]), follow=True
        )
        self.assertContains(resposta, "Escolha pelo menos uma aluna.")

    def test_aluna_que_ja_esta_em_outra_turma_e_movida(self):
        outra = Turma.objects.create(nome="Turma B")
        ana = self.aluna()
        ana.perfil.turma = outra
        ana.perfil.save()

        resposta = self.client.post(
            reverse("turma_adicionar_alunas", args=[self.turma.pk]),
            {"alunas": [ana.pk]},
            follow=True,
        )

        ana.perfil.refresh_from_db()
        self.assertEqual(ana.perfil.turma, self.turma)
        self.assertContains(resposta, "saiu da turma Turma B")

    def test_cronograma_mostra_todas_as_fases_com_os_dois_quizzes(self):
        resposta = self.client.get(reverse("admin_turma_detalhe", args=[self.turma.pk]))
        cronograma = resposta.context["cronograma"]
        self.assertEqual([i["fase"] for i in cronograma], [self.fase1, self.fase2])
        for item in cronograma:
            self.assertEqual(
                [q["quiz"].tipo for q in item["quizzes"]], ["teorico", "pratico"]
            )
            self.assertTrue(all(q["liberacao"] is None for q in item["quizzes"]))

    def test_mentora_libera_altera_e_retira_quiz(self):
        quiz = self.teorico(self.fase1)

        self.client.post(
            reverse("turma_liberar_quiz", args=[self.turma.pk]),
            {"quiz": quiz.pk, "data": self.amanha.isoformat()},
        )
        self.assertEqual(Liberacao.objects.get(turma=self.turma, quiz=quiz).data, self.amanha)

        self.client.post(
            reverse("turma_alterar_liberacao", args=[self.turma.pk, quiz.pk]),
            {"data": self.hoje.isoformat()},
        )
        self.assertEqual(Liberacao.objects.get(turma=self.turma, quiz=quiz).data, self.hoje)

        self.client.post(reverse("turma_retirar_liberacao", args=[self.turma.pk, quiz.pk]))
        self.assertFalse(Liberacao.objects.exists())

    def test_aceita_data_no_formato_brasileiro(self):
        quiz = self.teorico(self.fase1)
        self.client.post(
            reverse("turma_liberar_quiz", args=[self.turma.pk]),
            {"quiz": quiz.pk, "data": "15/03/2027"},
        )
        self.assertEqual(Liberacao.objects.get().data, date(2027, 3, 15))

    def test_liberar_de_novo_ou_com_data_invalida_mostra_erro(self):
        quiz = self.teorico(self.fase1)
        url = reverse("turma_liberar_quiz", args=[self.turma.pk])
        self.client.post(url, {"quiz": quiz.pk, "data": self.hoje.isoformat()})

        repetido = self.client.post(url, {"quiz": quiz.pk, "data": self.amanha.isoformat()}, follow=True)
        self.assertContains(repetido, "Esse quiz já está liberado para a turma.")
        invalido = self.client.post(url, {"quiz": quiz.pk, "data": "ontem"}, follow=True)
        self.assertContains(invalido, "Informe uma data válida.")
        self.assertEqual(Liberacao.objects.count(), 1)

    def test_alterar_ou_retirar_quiz_nao_liberado_mostra_erro(self):
        quiz = self.teorico(self.fase1)
        alterar = self.client.post(
            reverse("turma_alterar_liberacao", args=[self.turma.pk, quiz.pk]),
            {"data": self.hoje.isoformat()},
            follow=True,
        )
        self.assertContains(alterar, "Esse quiz não está liberado para a turma.")
        retirar = self.client.post(
            reverse("turma_retirar_liberacao", args=[self.turma.pk, quiz.pk]), follow=True
        )
        self.assertContains(retirar, "Esse quiz não está liberado para a turma.")

    def test_detalhe_diferencia_liberado_de_agendado(self):
        Liberacao.objects.create(turma=self.turma, quiz=self.teorico(self.fase1), data=self.hoje)
        Liberacao.objects.create(turma=self.turma, quiz=self.pratico(self.fase1), data=self.amanha)

        resposta = self.client.get(reverse("admin_turma_detalhe", args=[self.turma.pk]))

        self.assertContains(resposta, f"Liberado desde {self.hoje:%d/%m/%Y}")
        self.assertContains(resposta, f"Agendado para {self.amanha:%d/%m/%Y}")

    def test_turma_inexistente_da_404(self):
        self.assertEqual(self.client.get(reverse("admin_turma_detalhe", args=[999])).status_code, 404)


class ApiTurmasTests(TurmaTestCase):
    def api(self, metodo, url, dados=None):
        corpo = {} if dados is None else {"data": json.dumps(dados), "content_type": "application/json"}
        return getattr(self.client, metodo)(url, **corpo)

    def url(self, nome, *args):
        return reverse(nome, args=args)

    # Acesso

    def test_exige_login_e_perfil_de_mentora(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url("api_turmas")).status_code, 401)

        self.client.force_login(self.aluna("aluna@example.org"))
        resposta = self.client.get(self.url("api_turmas"))
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()["error"], "mentor_required")
        self.assertEqual(self.api("post", self.url("api_turmas"), {"nome": "X"}).status_code, 403)
        self.assertEqual(self.client.delete(self.url("api_turma", self.turma.pk)).status_code, 403)
        self.assertTrue(Turma.objects.filter(pk=self.turma.pk).exists())

    def test_metodo_nao_permitido(self):
        resposta = self.client.delete(self.url("api_turmas"))
        self.assertEqual(resposta.status_code, 405)
        self.assertEqual(resposta["Allow"], "GET, POST")

    def test_escrita_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.mentora)
        resposta = client.post(
            self.url("api_turmas"), json.dumps({"nome": "X"}), content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Turma.objects.count(), 1)

    # Turmas

    def test_listar_criar_detalhar_editar_e_remover_turma(self):
        resposta = self.client.get(self.url("api_turmas"))
        self.assertEqual(resposta.json(), {"turmas": [{"id": self.turma.pk, "nome": "Turma A", "total_alunas": 0, "total_liberacoes": 0}]})

        criada = self.api("post", self.url("api_turmas"), {"nome": "Turma B"})
        self.assertEqual(criada.status_code, 201)
        pk = criada.json()["id"]
        self.assertEqual(criada.json()["nome"], "Turma B")

        self.assertEqual(self.client.get(self.url("api_turma", pk)).json()["nome"], "Turma B")

        editada = self.api("put", self.url("api_turma", pk), {"nome": "Turma C"})
        self.assertEqual((editada.status_code, editada.json()["nome"]), (200, "Turma C"))

        removida = self.client.delete(self.url("api_turma", pk))
        self.assertEqual(removida.status_code, 204)
        self.assertEqual(self.client.get(self.url("api_turma", pk)).status_code, 404)

    def test_criar_turma_com_dados_invalidos(self):
        for dados in ({}, {"nome": ""}, {"nome": "turma a"}, {"nome": " Turma A "}):
            resposta = self.api("post", self.url("api_turmas"), dados)
            self.assertEqual(resposta.status_code, 400, dados)
            self.assertEqual(resposta.json()["error"], "validation_error")
            self.assertIn("nome", resposta.json()["details"])
        self.assertEqual(Turma.objects.count(), 1)

    def test_nome_com_tipo_estranho_nao_derruba_a_api(self):
        for nome in (123, ["a"], {"a": 1}, None, True):
            resposta = self.api("post", self.url("api_turmas"), {"nome": nome})
            self.assertIn(resposta.status_code, (201, 400), nome)  # nunca 500

    def test_corpo_que_nao_e_json_da_400(self):
        resposta = self.client.post(self.url("api_turmas"), "isso nao e json", content_type="application/json")
        self.assertEqual((resposta.status_code, resposta.json()["error"]), (400, "invalid_json"))
        resposta = self.api("post", self.url("api_turmas"), ["lista"])
        self.assertEqual(resposta.json()["error"], "invalid_json")

    def test_editar_turma_com_o_proprio_nome_e_permitido(self):
        resposta = self.api("put", self.url("api_turma", self.turma.pk), {"nome": "Turma A"})
        self.assertEqual(resposta.status_code, 200)

    # Alunas da turma

    def test_adicionar_listar_e_remover_alunas(self):
        ana, bia = self.aluna("ana@example.org"), self.aluna("bia@example.org")
        url = self.url("api_turma_alunas", self.turma.pk)

        resposta = self.api("post", url, {"alunas": [ana.pk, bia.pk]})
        self.assertEqual(resposta.status_code, 200)
        self.assertCountEqual([a["id"] for a in resposta.json()["adicionadas"]], [ana.pk, bia.pk])
        self.assertTrue(all(a["turma_anterior"] is None for a in resposta.json()["adicionadas"]))

        listadas = self.client.get(url).json()["alunas"]
        self.assertEqual([a["email"] for a in listadas], ["ana@example.org", "bia@example.org"])
        self.assertEqual(self.client.get(self.url("api_turma", self.turma.pk)).json()["total_alunas"], 2)

        self.assertEqual(self.client.delete(self.url("api_turma_aluna", self.turma.pk, ana.pk)).status_code, 204)
        self.assertEqual([a["id"] for a in self.client.get(url).json()["alunas"]], [bia.pk])

    def test_adicionar_aluna_de_outra_turma_move_e_informa_a_turma_anterior(self):
        outra = Turma.objects.create(nome="Turma B")
        ana = self.aluna()
        ana.perfil.turma = outra
        ana.perfil.save()

        resposta = self.api("post", self.url("api_turma_alunas", self.turma.pk), {"alunas": [ana.pk]})

        self.assertEqual(
            resposta.json()["adicionadas"][0]["turma_anterior"], {"id": outra.pk, "nome": "Turma B"}
        )
        self.assertEqual(self.client.get(self.url("api_turma_alunas", outra.pk)).json()["alunas"], [])

    def test_adicionar_aluna_que_ja_esta_na_turma_e_idempotente(self):
        ana = self.aluna()
        url = self.url("api_turma_alunas", self.turma.pk)
        self.api("post", url, {"alunas": [ana.pk]})

        resposta = self.api("post", url, {"alunas": [ana.pk]})

        self.assertEqual((resposta.status_code, resposta.json()["adicionadas"]), (200, []))

    def test_so_alunas_ativas_entram_na_turma(self):
        inativa = self.aluna("inativa@example.org", is_active=False)
        url = self.url("api_turma_alunas", self.turma.pk)

        for dados in ({"alunas": [inativa.pk]}, {"alunas": [self.mentora.pk]}, {"alunas": [9999]}, {"alunas": []}, {"alunas": "1"}, {"alunas": [[1]]}, {"alunas": [{"id": 1}]}, {"alunas": ["abc"]}, {}):
            resposta = self.api("post", url, dados)
            self.assertEqual(resposta.status_code, 400, dados)
        self.assertFalse(PerfilUsuario.objects.filter(turma=self.turma).exists())

    def test_remover_aluna_que_nao_esta_na_turma_da_404(self):
        ana = self.aluna()
        self.assertEqual(self.client.delete(self.url("api_turma_aluna", self.turma.pk, ana.pk)).status_code, 404)

    def test_rotas_de_turma_inexistente_dao_404(self):
        for nome, args, metodo in [
            ("api_turma", [999], "get"),
            ("api_turma_alunas", [999], "get"),
            ("api_turma_aluna", [999, 1], "delete"),
            ("api_turma_liberacoes", [999], "get"),
            ("api_turma_liberacao", [999, 1], "delete"),
        ]:
            self.assertEqual(getattr(self.client, metodo)(self.url(nome, *args)).status_code, 404, nome)

    # Liberações

    def test_cronograma_vem_organizado_por_fase(self):
        Liberacao.objects.create(turma=self.turma, quiz=self.teorico(self.fase1), data=self.hoje)
        Liberacao.objects.create(turma=self.turma, quiz=self.pratico(self.fase1), data=self.amanha)

        fases = self.client.get(self.url("api_turma_liberacoes", self.turma.pk)).json()["fases"]

        self.assertEqual([f["numero"] for f in fases], [1, 2])
        teorico, pratico = fases[0]["quizzes"]
        self.assertEqual((teorico["tipo"], pratico["tipo"]), ("teorico", "pratico"))
        self.assertEqual(teorico["liberacao"], {"quiz": teorico["id"], "data": self.hoje.isoformat(), "liberada": True})
        self.assertEqual(pratico["liberacao"], {"quiz": pratico["id"], "data": self.amanha.isoformat(), "liberada": False})
        # A fase 2 aparece, com os quizzes ainda não liberados
        self.assertEqual([q["liberacao"] for q in fases[1]["quizzes"]], [None, None])

    def test_liberar_alterar_e_retirar_quiz(self):
        quiz = self.teorico(self.fase1)
        url = self.url("api_turma_liberacoes", self.turma.pk)

        criada = self.api("post", url, {"quiz": quiz.pk, "data": self.amanha.isoformat()})
        self.assertEqual(criada.status_code, 201)
        self.assertEqual(criada.json(), {"quiz": quiz.pk, "data": self.amanha.isoformat(), "liberada": False})

        alterar = self.api("put", self.url("api_turma_liberacao", self.turma.pk, quiz.pk), {"data": self.hoje.isoformat()})
        self.assertEqual(alterar.status_code, 200)
        self.assertEqual(alterar.json(), {"quiz": quiz.pk, "data": self.hoje.isoformat(), "liberada": True})
        self.assertEqual(Liberacao.objects.get().data, self.hoje)

        retirar = self.client.delete(self.url("api_turma_liberacao", self.turma.pk, quiz.pk))
        self.assertEqual(retirar.status_code, 204)
        self.assertFalse(Liberacao.objects.exists())

    def test_teorico_e_pratico_da_mesma_fase_em_dias_diferentes_pela_api(self):
        url = self.url("api_turma_liberacoes", self.turma.pk)
        self.api("post", url, {"quiz": self.teorico(self.fase1).pk, "data": self.hoje.isoformat()})
        self.api("post", url, {"quiz": self.pratico(self.fase1).pk, "data": self.amanha.isoformat()})

        self.assertEqual(
            list(self.turma.quizzes_liberados()), [self.teorico(self.fase1)]
        )

    def test_liberar_quiz_ja_liberado_da_409(self):
        quiz = self.teorico(self.fase1)
        url = self.url("api_turma_liberacoes", self.turma.pk)
        self.api("post", url, {"quiz": quiz.pk, "data": self.hoje.isoformat()})

        resposta = self.api("post", url, {"quiz": quiz.pk, "data": self.amanha.isoformat()})

        self.assertEqual((resposta.status_code, resposta.json()["error"]), (409, "already_released"))
        self.assertEqual(Liberacao.objects.get().data, self.hoje)

    def test_liberar_com_dados_invalidos_da_400(self):
        quiz = self.teorico(self.fase1)
        url = self.url("api_turma_liberacoes", self.turma.pk)
        for dados in (
            {},
            {"quiz": quiz.pk},
            {"data": self.hoje.isoformat()},
            {"quiz": quiz.pk, "data": "2026-13-45"},
            {"quiz": quiz.pk, "data": 20261109},
            {"quiz": quiz.pk, "data": [self.hoje.isoformat()]},
            {"quiz": quiz.pk, "data": {"dia": 9}},
            {"quiz": [quiz.pk], "data": self.hoje.isoformat()},
            {"quiz": {"id": quiz.pk}, "data": self.hoje.isoformat()},
            {"quiz": 9999, "data": self.hoje.isoformat()},
        ):
            self.assertEqual(self.api("post", url, dados).status_code, 400, dados)
        self.assertFalse(Liberacao.objects.exists())

        resposta = self.api("put", self.url("api_turma_liberacao", self.turma.pk, quiz.pk), {"data": "x"})
        self.assertEqual(resposta.status_code, 400)

    def test_alterar_e_retirar_quiz_nao_liberado_da_404(self):
        quiz = self.teorico(self.fase1)
        url = self.url("api_turma_liberacao", self.turma.pk, quiz.pk)
        self.assertEqual(self.api("put", url, {"data": self.hoje.isoformat()}).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_liberacao_nao_afeta_outra_turma(self):
        outra = Turma.objects.create(nome="Turma B")
        quiz = self.teorico(self.fase1)
        Liberacao.objects.create(turma=outra, quiz=quiz, data=self.hoje)

        url = self.url("api_turma_liberacao", self.turma.pk, quiz.pk)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Liberacao.objects.filter(turma=outra, quiz=quiz).exists())
