import json
from collections import defaultdict

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import CompositePrimaryKey, prefetch_related_objects
from django.urls import reverse
from django.utils.dateparse import parse_date

from agenda.servicios import enlace_agenda
from bloqueos.models import Bloqueo
from caja.models import SesionCaja
from clases.models import (
    Asistencia, Clase, ClaseAlumno, ClaseProfesor, Feriado, TurnoPlanilla,
    TurnoPlanillaAlumno, TurnoPlanillaProfesor,
)
from instalaciones.models import Cancha, Sede, SedeHorario
from membresias.models import Membresia, MembresiaUsuario, Plan, PlanUsuario
from reservas.models import Evento, Reserva, ReservaInvitado, Turno
from usuarios.models import Rol, Usuario, UsuarioRol

from .models import LogAuditoria


TIPOS_REGISTRO = {
    "sesiones_caja": (SesionCaja, "Sesión de caja", ("responsable",), "caja:sesion_detalle"),
    "usuarios": (Usuario, "Usuario", (), "usuarios:usuario_detalle"),
    "roles": (Rol, "Rol", (), None),
    "usuarios_roles": (UsuarioRol, "Rol de usuario", ("usuario", "rol"), None),
    "sedes": (Sede, "Sede", (), "instalaciones:sede_detalle"),
    "canchas": (Cancha, "Cancha", ("sede",), None),
    "sedes_horarios": (SedeHorario, "Horario de sede", ("sede",), None),
    "turnos": (Turno, "Turno", ("cancha__sede",), None),
    "eventos": (Evento, "Evento", ("clase", "reserva", "bloqueo"), None),
    "reservas_invitados": (ReservaInvitado, "Invitación de reserva", ("reserva", "usuario"), None),
    "reservas": (Reserva, "Reserva", (), "reservas:reserva_detalle"),
    "bloqueos": (Bloqueo, "Bloqueo", (), "agenda:bloqueo_detalle"),
    "feriados": (Feriado, "Feriado", (), "clases:feriado_detalle"),
    "turnos_planilla": (TurnoPlanilla, "Turno de planilla", (), "clases:planilla_detalle"),
    "turnos_planilla_profesores": (
        TurnoPlanillaProfesor, "Profesor de planilla", ("turno_planilla", "profesor"), None,
    ),
    "turnos_planilla_alumnos": (
        TurnoPlanillaAlumno, "Alumno de planilla", ("turno_planilla", "usuario"), None,
    ),
    "clases": (Clase, "Clase", (), "clases:clase_detalle"),
    "clases_profesores": (
        ClaseProfesor, "Profesor de clase", ("clase", "profesor"), None,
    ),
    "clases_alumnos": (
        ClaseAlumno, "Alumno de clase", ("clase", "usuario"), None,
    ),
    "asistencias": (
        Asistencia, "Asistencia", ("clase", "usuario"), None,
    ),
    "membresias": (Membresia, "Membresía de socio", (), "membresias:membresia_detalle"),
    "planes": (Plan, "Plan", (), "membresias:plan_detalle"),
    "membresias_usuarios": (MembresiaUsuario, "Contratación de membresía", ("usuario",), "membresias:contratacion_membresia_detalle"),
    "planes_usuarios": (PlanUsuario, "Contratación de plan", ("usuario",), "membresias:contratacion_plan_detalle"),
}


ESTADOS_ACTIVACION = {
    "usuarios": ("is_active", True, False),
    "sedes": ("estado", "activa", "inactiva"),
    "canchas": ("estado", "activa", "inactiva"),
    "membresias": ("estado", "activo", "inactivo"),
    "planes": ("estado", "activo", "inactivo"),
}


def _relacion(objeto, nombre):
    try:
        relacionado = getattr(objeto, nombre)
    except ObjectDoesNotExist:
        relacionado = None
    if relacionado is not None:
        return str(relacionado)
    campo = objeto._meta.get_field(nombre)
    etiqueta = TIPOS_REGISTRO[campo.related_model._meta.db_table][1]
    return f"{etiqueta} #{getattr(objeto, campo.attname)}"


def _referencia_breve(objeto):
    if isinstance(objeto, (Usuario, Rol, Sede, Plan, Membresia)):
        return str(objeto)
    if isinstance(objeto, UsuarioRol):
        return f"{_relacion(objeto, 'usuario')} · {_relacion(objeto, 'rol')}"
    if isinstance(objeto, Cancha):
        return f"{objeto.nombre} · {_relacion(objeto, 'sede')}"
    if isinstance(objeto, SedeHorario):
        return f"{_relacion(objeto, 'sede')} · {objeto.get_dia_semana_display()}"
    if isinstance(objeto, Evento):
        try:
            actividad = getattr(objeto, objeto.tipo)
        except ObjectDoesNotExist:
            return f"{objeto.get_tipo_display()} · Evento #{objeto.pk}"
        return _referencia_breve(actividad)
    if isinstance(objeto, ReservaInvitado):
        return f"{objeto.reserva.numero} · {_relacion(objeto, 'usuario')}"
    if isinstance(objeto, (Reserva, Bloqueo, SesionCaja)):
        return objeto.numero
    if isinstance(objeto, Clase):
        return f"Clase #{objeto.pk}"
    if isinstance(objeto, Turno):
        return f"Turno #{objeto.pk}"
    if isinstance(objeto, TurnoPlanilla):
        return f"Turno de planilla #{objeto.pk}"
    if isinstance(objeto, Feriado):
        return f"{objeto.fecha:%d/%m/%Y}"
    if isinstance(objeto, (TurnoPlanillaProfesor, TurnoPlanillaAlumno)):
        persona = "profesor" if isinstance(objeto, TurnoPlanillaProfesor) else "usuario"
        return f"{_relacion(objeto, persona)} · Turno de planilla #{objeto.turno_planilla_id}"
    if isinstance(objeto, (ClaseProfesor, ClaseAlumno, Asistencia)):
        persona = "profesor" if isinstance(objeto, ClaseProfesor) else "usuario"
        return f"{_relacion(objeto, persona)} · Clase #{objeto.clase_id}"
    if isinstance(objeto, (PlanUsuario, MembresiaUsuario)):
        return f"{_relacion(objeto, 'usuario')} · {objeto.mes_cubierto:%m/%Y}"


def _url_registro(objeto):
    ruta = TIPOS_REGISTRO[objeto._meta.db_table][3]
    if ruta:
        return reverse(ruta, kwargs={"pk": objeto.pk})
    try:
        if isinstance(objeto, Evento):
            return _url_registro(getattr(objeto, objeto.tipo))
        if isinstance(objeto, (Cancha, SedeHorario)):
            seccion = "canchas" if isinstance(objeto, Cancha) else "horarios"
            return _url_registro(objeto.sede) + f"#{seccion}"
        if isinstance(objeto, UsuarioRol):
            return _url_registro(objeto.usuario) + "#roles"
        if isinstance(objeto, (TurnoPlanillaProfesor, TurnoPlanillaAlumno)):
            return _url_registro(objeto.turno_planilla)
        if isinstance(objeto, (ClaseProfesor, ClaseAlumno, Asistencia)):
            return _url_registro(objeto.clase)
        if isinstance(objeto, ReservaInvitado):
            return _url_registro(objeto.reserva)
        if isinstance(objeto, Turno):
            return enlace_agenda(objeto.cancha.sede, objeto.fecha, objeto.cancha, objeto.hora_inicio.hour)
    except ObjectDoesNotExist:
        return None


def _clave_legible(clave, modelo=None):
    partes = []
    for nombre, valor in clave.items():
        if nombre == "id":
            etiqueta = "ID"
        elif nombre == "dia_semana":
            etiqueta = "Día"
            valor = dict(SedeHorario.DiaSemana.choices).get(valor, valor)
        elif modelo is not None:
            campo = modelo._meta.get_field(nombre.removesuffix("_id"))
            etiqueta = str(campo.verbose_name).capitalize()
            valor = dict(campo.choices).get(valor, valor) if campo.choices else valor
        else:
            etiqueta = nombre.replace("_", " ").capitalize()
        partes.append(f"{etiqueta}: {valor}")
    return " · ".join(partes)


def _accion_visible(registro):
    if registro.accion != LogAuditoria.Accion.MODIFICACION:
        return registro.get_accion_display()

    anteriores = registro.valores_anteriores
    actuales = registro.valores_actuales
    campos = registro.valores_anteriores.keys() | registro.valores_actuales.keys()
    if (
        registro.tabla == "usuarios"
        and registro.origen == LogAuditoria.Origen.APLICACION
        and registro.usuario_id == registro.clave_registro.get("id")
        and campos - {"actualizado_en"} == {"last_login"}
        and registro.valores_actuales.get("last_login") is not None
    ):
        return "Inicio de sesión"

    if (
        registro.tabla == "eventos"
        and anteriores.get("estado") == Evento.Estado.PROGRAMADO
        and actuales.get("estado") == Evento.Estado.FINALIZADO
    ):
        return "Finalización"

    configuracion = ESTADOS_ACTIVACION.get(registro.tabla)
    if configuracion:
        campo, activo, inactivo = configuracion
        if anteriores.get(campo) == inactivo and actuales.get(campo) == activo:
            return "Activación"
        if anteriores.get(campo) == activo and actuales.get(campo) == inactivo:
            return "Desactivación"

    return registro.get_accion_display()


def preparar_filas(registros):
    por_tabla = defaultdict(list)
    filas = {}
    for registro in registros:
        por_tabla[registro.tabla].append(registro)

    for tabla, grupo in por_tabla.items():
        configuracion = TIPOS_REGISTRO.get(tabla)
        existentes = {}
        urls = {}
        if configuracion:
            modelo, etiqueta, relaciones, _ = configuracion
            claves = [
                tuple(registro.clave_registro[campo] for campo in modelo._meta.pk.field_names)
                if isinstance(modelo._meta.pk, CompositePrimaryKey) else registro.clave_registro["id"]
                for registro in grupo
            ]
            claves_vigentes = [
                clave for registro, clave in zip(grupo, claves)
                if registro.accion != LogAuditoria.Accion.ELIMINACION
            ]
            existentes = {objeto.pk: objeto for objeto in modelo.objects.filter(pk__in=claves_vigentes)}
            prefetch_related_objects(list(existentes.values()), *relaciones)
            objetos = {registro.pk: existentes.get(clave) for registro, clave in zip(grupo, claves)}
            for registro, clave in zip(grupo, claves):
                if clave in existentes and registro.accion != LogAuditoria.Accion.ELIMINACION:
                    urls[registro.pk] = _url_registro(existentes[clave])
        else:
            modelo, etiqueta = None, tabla.replace("_", " ").capitalize()
            objetos = {}

        for registro in grupo:
            clave = (
                f"{etiqueta} #{registro.clave_registro['id']}" if "id" in registro.clave_registro
                else _clave_legible(registro.clave_registro, modelo)
            )
            objeto = objetos.get(registro.pk)
            referencia = (_referencia_breve(objeto) or clave) if objeto is not None else clave
            if registro.accion == LogAuditoria.Accion.ELIMINACION:
                referencia = _referencia_eliminada(registro, clave)
            filas[registro.pk] = {
                "registro": registro,
                "accion": _accion_visible(registro),
                "tipo": etiqueta,
                "referencia": referencia,
                "url": urls.get(registro.pk),
                "clave": json.dumps(registro.clave_registro, ensure_ascii=False),
                "anteriores": json.dumps(registro.valores_anteriores, ensure_ascii=False, indent=2),
                "actuales": json.dumps(registro.valores_actuales, ensure_ascii=False, indent=2),
            }

    return [filas[registro.pk] for registro in registros]


def _referencia_eliminada(registro, clave):
    datos = registro.valores_anteriores
    if registro.tabla == "usuarios":
        nombre = " ".join(filter(None, (datos.get("first_name"), datos.get("last_name"))))
        return nombre or datos.get("username") or clave
    if registro.tabla in ("roles", "sedes", "canchas", "planes", "membresias"):
        return datos.get("nombre") or clave
    if registro.tabla == "usuarios_roles" and datos.get("usuario_id") and datos.get("rol_id"):
        return f"Usuario #{datos['usuario_id']} · Rol #{datos['rol_id']}"
    if registro.tabla == "feriados" and datos.get("fecha"):
        fecha = parse_date(datos["fecha"])
        return f"{fecha:%d/%m/%Y}" if fecha else clave
    if registro.tabla == "reservas":
        return f"R-{registro.clave_registro['id']:06d}"
    if registro.tabla == "bloqueos":
        return f"B-{registro.clave_registro['id']:06d}"
    return clave


def preparar_intentos(registros):
    modulos = {
        "usuarios": "Usuarios", "instalaciones": "Sedes y canchas", "clases": "Clases",
        "reservas": "Reservas", "agenda": "Agenda", "membresias": "Membresías", "caja": "Caja", "auditoria": "Auditoría",
    }
    filas = []
    for registro in registros:
        if registro.vista == "login":
            destino = f"Cuenta ingresada: {registro.identificador_ingresado}"
        elif registro.vista == "password_change":
            destino = "Contraseña de la cuenta"
        else:
            destino = modulos.get(registro.vista.split(":")[0], "Acceso al sistema")
            identificador = registro.parametros_destino.get("pk", registro.parametros_destino.get("usuario_id"))
            if identificador is not None:
                destino += f" · #{identificador}"
        filas.append({
            "registro": registro, "destino": destino,
            "parametros": json.dumps(registro.parametros_destino, ensure_ascii=False, indent=2),
        })
    return filas
