from django.core.exceptions import FieldDoesNotExist

from clases.models import Asistencia, ClaseAlumno
from reservas.models import Evento, ReservaInvitado

from .models import LogAuditoria


ACCIONES_DIRECTAS = {
    LogAuditoria.Accion.CAMBIO_CONTRASENA: "Cambio de contraseña",
    "restablecimiento_contrasena": "Restablecimiento de contraseña",
    LogAuditoria.Accion.ACTUALIZACION_HASH: "Actualización de hash",
}

ESTADOS_ACTIVACION = {
    "usuarios": ("is_active", True, False, "cuenta"),
    "sedes": ("estado", "activa", "inactiva", "sede"),
    "canchas": ("estado", "activa", "inactiva", "cancha"),
    "membresias": ("estado", "activo", "inactivo", "membresía"),
    "planes": ("estado", "activo", "inactivo", "plan"),
}

ELIMINACIONES_POR_TABLA = {
    "usuarios_roles": "Quita de rol",
    "clases_profesores": "Retiro de profesor de clase",
    "clases_alumnos": "Retiro de alumno de clase",
    "turnos_planilla_profesores": "Retiro de profesor de planilla",
    "turnos_planilla_alumnos": "Retiro de alumno de planilla",
    "reservas_invitados": "Retiro de invitación de reserva",
}

CAMPOS_CONCRETOS = {
    ("usuarios", "email"): "Cambio de correo",
    ("usuarios", "username"): "Cambio de nombre de usuario",
    ("usuarios", "celular_contacto"): "Cambio de celular de contacto",
    ("usuarios", "fecha_nacimiento"): "Cambio de fecha de nacimiento",
    ("usuarios", "observaciones"): "Actualización de observaciones de usuario",
    ("sedes", "nombre"): "Cambio de nombre de sede",
    ("sedes", "direccion"): "Cambio de dirección de sede",
    ("sedes", "localidad_codigo"): "Cambio de localidad de sede",
    ("sedes", "calle"): "Cambio de calle de sede",
    ("sedes", "altura"): "Cambio de altura de sede",
    ("sedes", "cpa"): "Cambio de CPA de sede",
    ("sedes", "calle_georef_id"): "Actualización de referencia de calle de sede",
    ("sedes", "tiene_estacionamiento"): "Actualización de estacionamiento de sede",
    ("sedes", "tiene_sanitarios"): "Actualización de sanitarios de sede",
    ("sedes", "tiene_vestuarios"): "Actualización de vestuarios de sede",
    ("sedes", "tiene_wifi"): "Actualización de Wi-Fi de sede",
    ("sedes", "tiene_buffet"): "Actualización de buffet de sede",
    ("sedes", "telefono_contacto_1"): "Cambio de teléfono principal de sede",
    ("sedes", "telefono_contacto_2"): "Cambio de teléfono adicional de sede",
    ("sedes", "precio_reserva_vigente"): "Actualización de precio de sede",
    ("sedes", "observaciones"): "Actualización de observaciones de sede",
    ("canchas", "nombre"): "Cambio de nombre de cancha",
    ("canchas", "superficie"): "Cambio de superficie de cancha",
    ("canchas", "observaciones"): "Actualización de observaciones de cancha",
    ("planes", "nombre"): "Cambio de nombre de plan",
    ("planes", "descripcion"): "Actualización de descripción de plan",
    ("planes", "precio_vigente"): "Actualización de precio de plan",
    ("membresias", "nombre"): "Cambio de nombre de membresía",
    ("membresias", "descripcion"): "Actualización de descripción de membresía",
    ("membresias", "precio_vigente"): "Actualización de precio de membresía",
    ("membresias", "precio_invitado_vigente"): "Actualización de precio de invitado",
    ("bloqueos", "motivo"): "Cambio de motivo de bloqueo",
    ("feriados", "fecha"): "Cambio de fecha de feriado",
    ("feriados", "descripcion"): "Actualización de descripción de feriado",
    ("turnos_planilla", "observaciones"): "Actualización de observaciones de planilla",
    ("clases_alumnos", "observaciones"): "Actualización de observaciones de alumno",
    ("asistencias", "observaciones"): "Actualización de observaciones de asistencia",
    ("planes_usuarios", "observaciones"): "Actualización de observaciones de contratación de plan",
    ("membresias_usuarios", "observaciones"): "Actualización de observaciones de contratación de membresía",
}

ETIQUETAS_CAMPO = {
    "creado_en": "fecha de creación",
    "actualizado_en": "fecha de actualización",
    "anulado_por_id": "responsable de anulación",
    "first_name": "nombre",
    "last_name": "apellido",
    "username": "nombre de usuario",
    "email": "correo",
    "email_pendiente": "correo pendiente",
    "is_active": "estado de cuenta",
    "last_login": "último acceso",
    "fecha_baja": "fecha de baja",
    "celular_contacto": "celular de contacto",
    "fecha_nacimiento": "fecha de nacimiento",
    "debe_cambiar_contrasena": "cambio obligatorio de contraseña",
    "correo_verificado_en": "verificación de correo",
    "verificacion_solicitada_en": "solicitud de verificación",
    "cambio_email_solicitado_en": "solicitud de cambio de correo",
    "direccion": "dirección",
    "localidad_codigo": "localidad",
    "calle": "calle",
    "altura": "altura",
    "cpa": "CPA",
    "calle_georef_id": "identificador de calle en Georef",
    "tiene_estacionamiento": "estacionamiento",
    "tiene_sanitarios": "sanitarios",
    "tiene_vestuarios": "vestuarios",
    "tiene_wifi": "Wi-Fi",
    "tiene_buffet": "buffet",
    "telefono_contacto_1": "teléfono principal",
    "telefono_contacto_2": "teléfono adicional",
    "precio_reserva_vigente": "precio por turno",
    "precio_vigente": "precio vigente",
    "precio_invitado_vigente": "precio por invitado",
    "horas_organizador": "horas como organizador",
    "horas_invitado": "horas como invitado",
    "hora_inicio_1": "inicio de primera franja",
    "hora_fin_1": "fin de primera franja",
    "hora_inicio_2": "inicio de segunda franja",
    "hora_fin_2": "fin de segunda franja",
    "turno_id": "turno",
    "cancha_id": "cancha",
    "respuesta_continuidad": "respuesta de continuidad",
    "resultado_uso": "resultado de reserva",
}

CAMPOS_DIRECCION_SEDE = frozenset({
    "direccion",
    "localidad_codigo",
    "calle",
    "altura",
    "cpa",
    "calle_georef_id",
})
CAMPOS_SERVICIOS_SEDE = frozenset({
    "tiene_estacionamiento",
    "tiene_sanitarios",
    "tiene_vestuarios",
    "tiene_wifi",
    "tiene_buffet",
})
CAMPOS_TELEFONOS_SEDE = frozenset({"telefono_contacto_1", "telefono_contacto_2"})
CAMPOS_HORARIO_SEDE = frozenset({"hora_inicio_1", "hora_fin_1", "hora_inicio_2", "hora_fin_2"})
CAMPOS_ANTICIPACION = frozenset({"anticipacion_clases_minutos", "anticipacion_reservas_minutos"})
CAMPOS_CONTINUIDAD = frozenset({
    "dia_apertura_continuidad",
    "dia_recordatorio_continuidad",
    "dia_cierre_continuidad",
    "hora_continuidad",
})
CAMPOS_HORAS_MEMBRESIA = frozenset({"horas_organizador", "horas_invitado"})


def _tipo_evento(actuales, objeto):
    tipo = actuales.get("tipo") or getattr(objeto, "tipo", None)
    if tipo in (Evento.Tipo.RESERVA, Evento.Tipo.CLASE, Evento.Tipo.BLOQUEO):
        return tipo
    return "evento"


def _clasificar_anulacion(registro, objeto, entidad):
    tabla = registro.tabla
    actuales = registro.valores_actuales

    if tabla == "eventos":
        return f"Anulación de {_tipo_evento(actuales, objeto)}"
    if tabla == "reservas":
        por_organizador = actuales.get("anulada_por_organizador")
        if por_organizador is True:
            return "Anulación de reserva por organizador"
        if por_organizador is False:
            return "Anulación de reserva por administración"
        return "Anulación de reserva"
    return f"Anulación de {entidad}"


def _clasificar_modificacion_usuario(registro, campos, anteriores, actuales, _objeto):
    if (
        registro.origen == LogAuditoria.Origen.APLICACION
        and registro.usuario_id == registro.clave_registro.get("id")
        and campos == {"last_login"}
        and actuales.get("last_login") is not None
    ):
        return "Inicio de sesión"

    if anteriores.get("correo_verificado_en") is None and actuales.get("correo_verificado_en") is not None:
        return "Confirmación de correo"

    if "email" in campos and anteriores.get("email_pendiente") and actuales.get("email_pendiente") == "":
        return "Confirmación de cambio de correo"

    if not anteriores.get("email_pendiente") and actuales.get("email_pendiente"):
        return "Solicitud de cambio de correo"

    if anteriores.get("email_pendiente") and actuales.get("email_pendiente") == "" and "email" not in campos:
        return "Cancelación de cambio de correo"

    if campos <= {"verificacion_solicitada_en", "revision_correo"} and "verificacion_solicitada_en" in campos:
        return "Solicitud de verificación de correo"

    if campos == {"debe_cambiar_contrasena"}:
        return (
            "Exigencia de cambio de contraseña"
            if actuales.get("debe_cambiar_contrasena")
            else "Liberación de cambio obligatorio de contraseña"
        )

    if campos == {"first_name"}:
        return "Cambio de nombre"
    if campos == {"last_name"}:
        return "Cambio de apellido"
    if campos == {"first_name", "last_name"}:
        return "Actualización de nombre y apellido"

    return None


def _clasificar_modificacion_evento(_registro, campos, anteriores, actuales, objeto):
    tipo = _tipo_evento(actuales, objeto)
    if anteriores.get("estado") == Evento.Estado.PROGRAMADO and actuales.get("estado") == Evento.Estado.FINALIZADO:
        return f"Finalización de {tipo}"
    if campos == {"turno_id"}:
        return f"Cambio de turno de {tipo}"
    if campos == {"observaciones"}:
        return f"Actualización de observaciones de {tipo}"
    return None


def _clasificar_modificacion_clase(_registro, campos, anteriores, actuales, _objeto):
    if anteriores.get("finalizado_por_id") is None and actuales.get("finalizado_por_id") is not None:
        return "Finalización de clase"
    return None


def _clasificar_modificacion_reserva(_registro, campos, anteriores, actuales, _objeto):
    if "resultado_uso" in campos or "resultado_corregido_en" in campos:
        if anteriores.get("resultado_uso") == "sin_registrar" and actuales.get("resultado_uso") in ("realizada", "no_realizada"):
            return "Registro de resultado de reserva"
        if actuales.get("resultado_corregido_en") is not None or (
            anteriores.get("resultado_uso") in ("realizada", "no_realizada")
            and actuales.get("resultado_uso") in ("realizada", "no_realizada")
        ):
            return "Corrección de resultado de reserva"
        return "Actualización de resultado de reserva"
    return None


def _clasificar_modificacion_invitado(_registro, campos, _anteriores, actuales, _objeto):
    if "respuesta" in campos:
        respuestas = {
            ReservaInvitado.Respuesta.AFIRMATIVA: "Aceptación de invitación",
            ReservaInvitado.Respuesta.NEGATIVA: "Rechazo de invitación",
        }
        return respuestas.get(actuales.get("respuesta"), "Respuesta a invitación")
    return None


def _clasificar_modificacion_clase_alumno(_registro, campos, _anteriores, actuales, _objeto):
    if "respuesta" in campos:
        respuestas = {
            ClaseAlumno.Respuesta.NO_ASISTIRA: "Aviso de no asistencia",
            ClaseAlumno.Respuesta.ASISTIRA: "Confirmación de asistencia",
        }
        return respuestas.get(actuales.get("respuesta"), "Respuesta de asistencia a clase")
    return None


def _clasificar_modificacion_asistencia(_registro, campos, anteriores, actuales, _objeto):
    if "estado" in campos:
        if anteriores.get("estado") == Asistencia.Estado.SIN_REGISTRAR and actuales.get("estado") in (
            Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE,
        ):
            return "Registro de asistencia"
        return "Actualización de asistencia"
    return None


def _clasificar_modificacion_sesion_caja(_registro, _campos, anteriores, actuales, _objeto):
    if anteriores.get("estado") == "abierta" and actuales.get("estado") == "cerrada":
        return "Cierre de sesión de caja"
    return None


def _clasificar_modificacion_contratacion(registro, campos, anteriores, actuales, _objeto):
    entidad = "contratación de plan" if registro.tabla == "planes_usuarios" else "contratación de membresía"
    if anteriores.get("estado") == "activo" and actuales.get("estado") == "vencido":
        return f"Vencimiento de {entidad}"
    if "respuesta_continuidad" in campos:
        return f"Respuesta de continuidad de {entidad}"
    return None


def _clasificar_modificacion_sede(_registro, campos, _anteriores, _actuales, _objeto):
    if len(campos) > 1 and campos <= CAMPOS_DIRECCION_SEDE:
        return "Actualización de dirección de sede"
    if len(campos) > 1 and campos <= CAMPOS_SERVICIOS_SEDE:
        return "Actualización de servicios de sede"
    if len(campos) > 1 and campos <= CAMPOS_TELEFONOS_SEDE:
        return "Actualización de teléfonos de contacto de sede"
    return None


def _clasificar_modificacion_horario_sede(_registro, campos, _anteriores, _actuales, _objeto):
    if campos <= CAMPOS_HORARIO_SEDE:
        return "Actualización de horario de sede"
    return None


def _clasificar_modificacion_notificaciones(_registro, campos, _anteriores, _actuales, _objeto):
    if campos <= CAMPOS_ANTICIPACION:
        return "Actualización de anticipación de recordatorios"
    if campos <= CAMPOS_CONTINUIDAD:
        return "Actualización de calendario de continuidad"
    return "Actualización de reglas de notificación"


def _clasificar_modificacion_membresia(_registro, campos, _anteriores, _actuales, _objeto):
    if campos <= CAMPOS_HORAS_MEMBRESIA:
        return "Actualización de horas de membresía"
    return None


REGLAS_MODIFICACION = {
    "usuarios": _clasificar_modificacion_usuario,
    "eventos": _clasificar_modificacion_evento,
    "clases": _clasificar_modificacion_clase,
    "reservas": _clasificar_modificacion_reserva,
    "reservas_invitados": _clasificar_modificacion_invitado,
    "clases_alumnos": _clasificar_modificacion_clase_alumno,
    "asistencias": _clasificar_modificacion_asistencia,
    "sesiones_caja": _clasificar_modificacion_sesion_caja,
    "planes_usuarios": _clasificar_modificacion_contratacion,
    "membresias_usuarios": _clasificar_modificacion_contratacion,
    "sedes": _clasificar_modificacion_sede,
    "sedes_horarios": _clasificar_modificacion_horario_sede,
    "configuracion_notificaciones": _clasificar_modificacion_notificaciones,
    "membresias": _clasificar_modificacion_membresia,
}


def _etiqueta_campo(nombre, modelo=None):
    if nombre in ETIQUETAS_CAMPO:
        return ETIQUETAS_CAMPO[nombre]
    if modelo is not None:
        base = nombre.removesuffix("_id")
        try:
            campo = modelo._meta.get_field(base)
            return str(campo.verbose_name).lower()
        except FieldDoesNotExist:
            pass
    return nombre.removesuffix("_id").replace("_", " ")


def _formatear_lista_campos(etiquetas):
    if len(etiquetas) == 1:
        return etiquetas[0]
    if len(etiquetas) <= 3:
        return f"{', '.join(etiquetas[:-1])} y {etiquetas[-1]}"
    restantes = len(etiquetas) - 3
    return f"{', '.join(etiquetas[:3])} y {restantes} más"


def _respaldo_campos(entidad, campos, modelo):
    if not campos:
        return f"Cambio en {entidad} sin campos identificados"
    etiquetas = [_etiqueta_campo(nombre, modelo) for nombre in sorted(campos)]
    if len(etiquetas) == 1:
        return f"Cambio de {etiquetas[0]} en {entidad}"
    return f"Actualización de {_formatear_lista_campos(etiquetas)} en {entidad}"


def clasificar_accion(registro, *, entidad, objeto, modelo):
    if registro.accion in ACCIONES_DIRECTAS:
        return ACCIONES_DIRECTAS[registro.accion]

    if registro.accion == LogAuditoria.Accion.ELIMINACION:
        return ELIMINACIONES_POR_TABLA.get(registro.tabla, f"Eliminación de {entidad}")

    if registro.accion == LogAuditoria.Accion.ANULACION:
        return _clasificar_anulacion(registro, objeto, entidad)

    if registro.accion != LogAuditoria.Accion.MODIFICACION:
        return registro.get_accion_display()

    anteriores = registro.valores_anteriores or {}
    actuales = registro.valores_actuales or {}
    campos_brutos = anteriores.keys() | actuales.keys()
    campos = campos_brutos - {"actualizado_en"} or campos_brutos

    config_activacion = ESTADOS_ACTIVACION.get(registro.tabla)
    if config_activacion:
        campo, activo, inactivo, entidad = config_activacion
        if anteriores.get(campo) == inactivo and actuales.get(campo) == activo:
            return f"Activación de {entidad}"
        if anteriores.get(campo) == activo and actuales.get(campo) == inactivo:
            return f"Desactivación de {entidad}"

    regla = REGLAS_MODIFICACION.get(registro.tabla)
    if regla:
        etiqueta = regla(registro, campos, anteriores, actuales, objeto)
        if etiqueta:
            return etiqueta

    if len(campos) == 1:
        unico = next(iter(campos))
        etiqueta = CAMPOS_CONCRETOS.get((registro.tabla, unico))
        if etiqueta:
            return etiqueta

    return _respaldo_campos(entidad, campos, modelo)
