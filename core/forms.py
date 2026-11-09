from django import forms
from django.contrib.auth import get_user_model

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
