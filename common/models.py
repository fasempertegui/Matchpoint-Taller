from django.conf import settings
from django.db import models
from django.utils import timezone


class RespuestaActividad(models.Model):
    class Respuesta(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        AFIRMATIVA = "afirmativa", "Afirmativa"
        NEGATIVA = "negativa", "Negativa"

    respuesta = models.CharField(max_length=10, choices=Respuesta.choices, default=Respuesta.PENDIENTE)
    respuesta_inicial = models.CharField(max_length=10, choices=Respuesta.choices, null=True, blank=True)
    respondido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    respondido_en = models.DateTimeField(null=True, blank=True)
    respuesta_modificada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    respuesta_modificada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(respuesta="pendiente", respuesta_inicial__isnull=True, respondido_por__isnull=True, respondido_en__isnull=True,
                             respuesta_modificada_por__isnull=True, respuesta_modificada_en__isnull=True)
                    | (models.Q(respuesta__in=("afirmativa", "negativa"), respuesta_inicial__in=("afirmativa", "negativa"), respuesta_inicial__isnull=False,
                                respondido_por=models.F("usuario"), respondido_por__isnull=False, respondido_en__isnull=False)
                       & ((models.Q(respuesta=models.F("respuesta_inicial"), respuesta_modificada_por__isnull=True,
                                    respuesta_modificada_en__isnull=True))
                          | (models.Q(respuesta_modificada_por=models.F("usuario"), respuesta_modificada_por__isnull=False, respuesta_modificada_en__isnull=False)
                             & ~models.Q(respuesta=models.F("respuesta_inicial")))))
                ), name="%(app_label)s_%(class)s_respuesta_coherente",
            ),
        ]

    @property
    def respuesta_inicial_texto(self):
        return dict(self.Respuesta.choices).get(self.respuesta_inicial, "")

    def respuesta_visible(self, inicio):
        if self.respuesta == self.Respuesta.PENDIENTE and timezone.now() >= inicio:
            return "Sin respuesta"
        return self.get_respuesta_display()
