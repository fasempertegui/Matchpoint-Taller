from django.core.exceptions import ValidationError


def validar_motivo(motivo):
    if not isinstance(motivo, str) or len(motivo.strip()) < 5:
        raise ValidationError("El motivo debe tener al menos 5 caracteres.")
