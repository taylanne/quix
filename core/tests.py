import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from google.auth.exceptions import GoogleAuthError

from .models import Fase, PerfilUsuario, Tentativa

User = get_user_model()


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="google-client-id",
    QUIX_DEVELOPER_EMAILS=("dev@example.org", "mentor@example.org", "student@example.org"),
)
class AuthenticationTests(TestCase):
    def create_user(self, email, role=PerfilUsuario.Tipo.ALUNA, **kwargs):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="not-used-for-login",
            **kwargs,
        )
        user.perfil.tipo = role
        user.perfil.save(update_fields=["tipo"])
        return user

    @patch("core.views.verify_google_credential")
    def test_google_login_requires_verified_allowlisted_registered_user(self, verify):
        user = self.create_user("dev@example.org", first_name="Dev")
        verify.return_value = {
            "email": user.email,
            "email_verified": True,
            "sub": "google-user-id",
        }

        response = self.client.post(
            reverse("google_login"),
            data={"credential": "valid-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_url"], "/aluna")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @patch("core.views.verify_google_credential")
    def test_mentor_login_redirects_to_student_management(self, verify):
        user = self.create_user(
            "mentor@example.org",
            role=PerfilUsuario.Tipo.MENTORA,
        )
        verify.return_value = {"email": user.email, "email_verified": True}

        response = self.client.post(
            reverse("google_login"),
            data=json.dumps({"credential": "valid-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_url"], "/admin/alunas")

    @patch("core.views.verify_google_credential")
    def test_google_login_requires_csrf_protection(self, verify):
        self.create_user("dev@example.org")
        verify.return_value = {
            "email": "dev@example.org",
            "email_verified": True,
        }
        client = Client(enforce_csrf_checks=True)

        denied = client.post(
            reverse("google_login"),
            data=json.dumps({"credential": "valid-token"}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        client.get(reverse("login"))
        csrf_token = client.cookies["csrftoken"].value
        accepted = client.post(
            reverse("google_login"),
            data=json.dumps({"credential": "valid-token"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 200)

    @patch("core.views.verify_google_credential")
    def test_google_login_rejects_unverified_email(self, verify):
        self.create_user("dev@example.org")
        verify.return_value = {
            "email": "dev@example.org",
            "email_verified": False,
        }

        response = self.client.post(
            reverse("google_login"),
            data={"credential": "valid-token"},
        )

        self.assertEqual(response.status_code, 403)

    @patch("core.views.verify_google_credential")
    def test_google_login_rejects_email_outside_developer_allowlist(self, verify):
        verify.return_value = {
            "email": "outsider@example.org",
            "email_verified": True,
        }

        response = self.client.post(
            reverse("google_login"),
            data={"credential": "valid-token"},
        )

        self.assertEqual(response.status_code, 403)

    @patch("core.views.verify_google_credential")
    def test_google_login_rejects_unregistered_email(self, verify):
        verify.return_value = {
            "email": "dev@example.org",
            "email_verified": True,
        }

        response = self.client.post(
            reverse("google_login"),
            data={"credential": "valid-token"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "account_not_registered")

    @patch("core.views.verify_google_credential", return_value=None)
    def test_google_login_rejects_invalid_token(self, verify):
        response = self.client.post(
            reverse("google_login"),
            data={"credential": "invalid-token"},
        )

        self.assertEqual(response.status_code, 401)

    @override_settings(QUIX_DEVELOPER_EMAILS=())
    def test_google_login_is_disabled_without_developer_allowlist(self):
        response = self.client.post(
            reverse("google_login"),
            data={"credential": "token"},
        )

        self.assertEqual(response.status_code, 503)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_google_login_is_disabled_without_client_id(self):
        response = self.client.post(
            reverse("google_login"),
            data={"credential": "token"},
        )

        self.assertEqual(response.status_code, 503)

    @patch(
        "core.views.verify_google_credential",
        side_effect=GoogleAuthError("Google token verification is unavailable"),
    )
    def test_google_provider_errors_return_service_unavailable(self, verify):
        response = self.client.post(
            reverse("google_login"),
            data={"credential": "token"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"],
            "google_verification_unavailable",
        )

    def test_me_and_profile_require_a_signed_in_developer(self):
        user = self.create_user("dev@example.org", first_name="Dev")
        self.client.force_login(user)

        response = self.client.get(reverse("api_me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], user.email)
        self.assertEqual(response.json()["role"], PerfilUsuario.Tipo.ALUNA)
        self.assertEqual(self.client.get(reverse("perfil")).status_code, 200)

    def test_me_returns_unauthorized_json_without_a_session(self):
        response = self.client.get(reverse("api_me"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "authentication_required")

    def test_session_for_non_developer_is_blocked(self):
        user = self.create_user("outsider@example.org")
        self.client.force_login(user)

        response = self.client.get(reverse("perfil"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_ends_the_session(self):
        user = self.create_user("dev@example.org")
        self.client.force_login(user)

        response = self.client.post(
            reverse("logout"),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(
    QUIX_LOCAL_PASSWORD_LOGIN=True,
    QUIX_DEVELOPER_EMAILS=("jessica@teste.com.br",),
)
class LocalPasswordLoginTests(TestCase):
    def test_local_developer_can_sign_in_with_email_and_password(self):
        user = User.objects.get(email="jessica@teste.com.br")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("teste123@"))

        response = self.client.post(
            reverse("login"),
            {"email": "JESSICA@teste.com.br", "password": "teste123@"},
        )

        self.assertRedirects(response, reverse("admin_alunas"))
        self.assertEqual(self.client.get(reverse("admin_alunas")).status_code, 200)

    def test_local_sign_in_rejects_an_incorrect_password(self):
        response = self.client.post(
            reverse("login"),
            {"email": "jessica@teste.com.br", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail ou senha inválidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(QUIX_LOCAL_PASSWORD_LOGIN=False)
    def test_local_password_sign_in_is_disabled_outside_local_mode(self):
        response = self.client.post(
            reverse("login"),
            {"email": "jessica@teste.com.br", "password": "teste123@"},
        )

        self.assertEqual(response.status_code, 403)


@override_settings(QUIX_DEVELOPER_EMAILS=("mentor@example.org", "student@example.org"))
class StudentAdministrationTests(TestCase):
    def create_user(self, email, role, **kwargs):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="not-used-for-login",
            **kwargs,
        )
        user.perfil.tipo = role
        user.perfil.save(update_fields=["tipo"])
        return user

    def test_student_cannot_access_mentor_pages_or_django_admin(self):
        student = self.create_user("student@example.org", PerfilUsuario.Tipo.ALUNA)
        self.client.force_login(student)

        self.assertEqual(self.client.get(reverse("admin_alunas")).status_code, 403)
        self.assertEqual(self.client.get("/django-admin/").status_code, 302)

    def test_student_home_redirects_to_student_dashboard(self):
        student = self.create_user("student@example.org", PerfilUsuario.Tipo.ALUNA)
        self.client.force_login(student)

        self.assertRedirects(self.client.get(reverse("home")), reverse("aluna_dashboard"))
        self.assertEqual(self.client.get(reverse("aluna_dashboard")).status_code, 200)

    def test_mentor_can_access_django_admin(self):
        mentor = self.create_user(
            "mentor@example.org",
            PerfilUsuario.Tipo.MENTORA,
            is_staff=True,
        )
        self.client.force_login(mentor)

        self.assertEqual(self.client.get("/django-admin/").status_code, 200)

    def test_mentor_can_create_search_edit_and_remove_students(self):
        mentor = self.create_user(
            "mentor@example.org",
            PerfilUsuario.Tipo.MENTORA,
            is_staff=True,
        )
        self.client.force_login(mentor)

        response = self.client.post(
            reverse("admin_alunas"),
            {"nome": "Ana Souza", "email": "ana@example.org"},
        )
        self.assertRedirects(response, reverse("admin_alunas"))

        student = User.objects.get(email="ana@example.org")
        self.assertFalse(student.has_usable_password())
        self.assertEqual(student.perfil.tipo, PerfilUsuario.Tipo.ALUNA)
        self.assertEqual(
            self.client.get(reverse("admin_alunas"), {"q": "ana@example.org"}).status_code,
            200,
        )

        self.assertEqual(
            self.client.get(reverse("editar_aluna", args=[student.pk])).status_code,
            200,
        )
        response = self.client.post(
            reverse("editar_aluna", args=[student.pk]),
            {"nome": "Ana Lima", "email": "ana.lima@example.org"},
        )
        self.assertRedirects(response, reverse("admin_alunas"))
        student.refresh_from_db()
        self.assertEqual(student.get_full_name(), "Ana Lima")
        self.assertEqual(student.email, "ana.lima@example.org")

        fase = Fase.objects.create(numero=1, nome="Inicial")
        tentativa = Tentativa.objects.create(
            aluna=student,
            quiz=fase.quizzes.first(),
            acertos=1,
            total=1,
        )
        response = self.client.post(reverse("remover_aluna", args=[student.pk]))
        self.assertRedirects(response, reverse("admin_alunas"))
        student.refresh_from_db()
        self.assertFalse(student.is_active)
        self.assertTrue(Tentativa.objects.filter(pk=tentativa.pk).exists())
