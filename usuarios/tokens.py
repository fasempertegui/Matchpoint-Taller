from datetime import timezone as utc

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.http import base36_to_int


class TokenRecuperacion(PasswordResetTokenGenerator):
    def __init__(self, *, emitido_en=None):
        super().__init__()
        self.emitido_en = emitido_en

    def _now(self):
        instante = self.emitido_en or timezone.now()
        return instante.astimezone(utc.utc).replace(tzinfo=None)

    def check_token(self, user, token):
        if user is None or not user.esta_habilitado or not super().check_token(user, token):
            return False
        segundos = self._num_seconds(self._now()) - base36_to_int(token.split('-')[0])
        return 0 <= segundos < settings.PASSWORD_RESET_TIMEOUT


def huella_recuperacion(usuario):
    datos = f"{usuario.pk}:{usuario.password}:{usuario.last_login}:{usuario.email}"
    return salted_hmac("usuarios.solicitud_recuperacion", datos).hexdigest()
