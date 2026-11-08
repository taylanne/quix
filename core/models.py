from django.conf import settings
from django.db import models


class Fase(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"Fase {self.numero}: {self.nome}"

    def save(self, *args, **kwargs):
        nova = self._state.adding
        super().save(*args, **kwargs)
        if nova:
            # Toda fase nasce com um quiz teórico e um prático, vazios
            Quiz.objects.create(fase=self, tipo=Quiz.Tipo.TEORICO)
            Quiz.objects.create(fase=self, tipo=Quiz.Tipo.PRATICO)


class Quiz(models.Model):
    class Tipo(models.TextChoices):
        TEORICO = "teorico", "Teórico"
        PRATICO = "pratico", "Prático"

    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name="quizzes")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)

    class Meta:
        ordering = ["fase__numero", "-tipo"]
        verbose_name_plural = "quizzes"
        constraints = [
            models.UniqueConstraint(fields=["fase", "tipo"], name="um_quiz_de_cada_tipo_por_fase"),
        ]

    def __str__(self):
        return f"{self.fase} - {self.get_tipo_display()}"


class Pergunta(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="perguntas")
    enunciado = models.TextField()
    imagem = models.ImageField(upload_to="perguntas/", blank=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["quiz", "ordem", "id"]

    def __str__(self):
        return self.enunciado[:50]


class Alternativa(models.Model):
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name="alternativas")
    texto = models.CharField(max_length=255)
    correta = models.BooleanField(default=False)

    def __str__(self):
        return self.texto


class Tentativa(models.Model):
    aluna = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tentativas")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="tentativas")
    acertos = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    oficial = models.BooleanField(default=False, editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self):
        return f"{self.aluna} - {self.quiz} ({self.acertos}/{self.total})"

    def save(self, *args, **kwargs):
        if self._state.adding:
            # Só a primeira tentativa da aluna neste quiz vale como nota oficial
            ja_tentou = Tentativa.objects.filter(aluna=self.aluna, quiz=self.quiz).exists()
            self.oficial = not ja_tentou
        super().save(*args, **kwargs)


class Resposta(models.Model):
    tentativa = models.ForeignKey(Tentativa, on_delete=models.CASCADE, related_name="respostas")
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE)
    alternativa = models.ForeignKey(Alternativa, on_delete=models.CASCADE)

    @property
    def correta(self):
        return self.alternativa.correta
