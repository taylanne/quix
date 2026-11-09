from datetime import date, datetime

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Quiz, Turma
from .turmas import alunas_ativas

User = get_user_model()


class AlunaForm(forms.Form):
    nome = forms.CharField(max_length=150, label="Nome")
    email = forms.EmailField(label="E-mail")

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().casefold()
        users = User.objects.filter(email__iexact=email)
        if self.usuario:
            users = users.exclude(pk=self.usuario.pk)
        if users.exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email


class LocalLoginForm(forms.Form):
    email = forms.EmailField(label="E-mail")
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput,
    )


_CAMPO = "mt-1 block w-full rounded-lg border px-3 py-2"


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["nome"]
        labels = {"nome": "Nome da turma"}
        widgets = {"nome": forms.TextInput(attrs={"class": _CAMPO})}

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        outras = Turma.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if outras.exists():
            # Erro no campo (e não "geral") para aparecer junto do campo na tela
            raise ValidationError("Já existe uma turma com este nome.", code="unique")
        return nome


class DataField(forms.DateField):
    """DateField que também aceita o que vier de JSON sem quebrar: número, lista
    etc. viram erro de validação em vez de exceção."""

    def to_python(self, value):
        if value not in self.empty_values and not isinstance(value, (str, date, datetime)):
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        return super().to_python(value)


class DataLiberacaoForm(forms.Form):
    data = DataField(
        label="Data de liberação",
        widget=forms.DateInput(attrs={"type": "date", "class": _CAMPO}, format="%Y-%m-%d"),
    )


class LiberacaoForm(DataLiberacaoForm):
    quiz = forms.ModelChoiceField(queryset=Quiz.objects.all(), label="Quiz")


class AdicionarAlunasForm(forms.Form):
    alunas = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),  # definido no __init__
        label="Alunas",
        error_messages={"required": "Escolha pelo menos uma aluna."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Quem já está na turma é ignorada pelo serviço, então reenviar não dá erro
        self.fields["alunas"].queryset = alunas_ativas().select_related("perfil__turma")
