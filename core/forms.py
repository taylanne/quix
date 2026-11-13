from django import forms
from django.contrib.auth import get_user_model
from .models import Fase
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


ESTILO_CAMPO = "w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-700"


class FaseForm(forms.ModelForm):
    class Meta:
        model = Fase
        fields = ["numero", "nome", "descricao"]
        labels = {"numero": "Número", "nome": "Nome", "descricao": "Descrição"}
        widgets = {
            "numero": forms.NumberInput(attrs={"class": ESTILO_CAMPO}),
            "nome": forms.TextInput(attrs={"class": ESTILO_CAMPO}),
            "descricao": forms.Textarea(attrs={"class": ESTILO_CAMPO, "rows": 3}),
        }
