import json
from collections import defaultdict

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import CompositePrimaryKey, prefetch_related_objects
from django.urls import reverse

from agenda.servicios import enlace_agenda
from bloqueos.models import Bloqueo
from clases.models import (
    Asistencia, Clase, ClaseAlumno, ClaseProfesor, Feriado, TurnoPlanilla,
    TurnoPlanillaAlumno, TurnoPlanillaProfesor,
)
from instalaciones.models import Cancha, Sede, SedeHorario
from membresias.models import Pase, PaseUsuario, Plan, PlanUsuario
from reservas.models import Evento, Reserva, Turno
from usuarios.models import Rol, Usuario, UsuarioRol

from .models import LogAuditoria


TIPOS_REGISTRO = {
    "usuarios": (Usuario, "Usuario", ()),
    "roles": (Rol, "Rol", ()),
    "usuarios_roles": (UsuarioRol, "Rol de usuario", ("usuario", "rol")),
    "sedes": (Sede, "Sede", ()),
    "canchas": (Cancha, "Cancha", ("sede",)),
    "sedes_horarios": (SedeHorario, "Horario de sede", ("sede",)),
    "turnos": (Turno, "Turno", ("cancha__sede",)),
    "eventos": (Evento, "Evento", ("clase", "reserva", "bloqueo")),
    "reservas": (Reserva, "Reserva", ()),
    "bloqueos": (Bloqueo, "Bloqueo", ()),
    "feriados": (Feriado, "Feriado", ()),
    "turnos_planilla": (TurnoPlanilla, "Turno de planilla", ()),
    "turnos_planilla_profesores": (
        TurnoPlanillaProfesor, "Profesor de planilla", ("turno_planilla", "profesor"),
    ),
    "turnos_planilla_alumnos": (
        TurnoPlanillaAlumno, "Alumno de planilla", ("turno_planilla", "usuario"),
    ),
    "clases": (Clase, "Clase", ()),
    "clases_profesores": (
        ClaseProfesor, "Profesor de clase", ("clase", "profesor"),
    ),
    "clases_alumnos": (
        ClaseAlumno, "Alumno de clase", ("clase", "usuario"),
    ),
    "asistencias": (
        Asistencia, "Asistencia", ("clase", "usuario"),
    ),
    "planes": (Plan, "Plan", ()),
    "pases": (Pase, "Pase de cancha", ()),
    "planes_usuarios": (PlanUsuario, "Contratación de plan", ("usuario",)),
    "pases_usuarios": (PaseUsuario, "Contratación de pase", ("usuario",)),
}


RUTAS_DETALLE = {
    Usuario: "usuarios:usuario_detalle",
    Sede: "instalaciones:sede_detalle",
    Reserva: "reservas:reserva_detalle",
    Bloqueo: "agenda:bloqueo_detalle",
    Clase: "clases:clase_detalle",
    TurnoPlanilla: "clases:planilla_detalle",
    Feriado: "clases:feriado_detalle",
    Plan: "membresias:plan_detalle",
    Pase: "membresias:pase_detalle",
    PlanUsuario: "membresias:contratacion_plan_detalle",
    PaseUsuario: "membresias:contratacion_pase_detalle",
}


ESTADOS_ACTIVACION = {
    "usuarios": ("is_active", True, False),
    "sedes": ("estado", "activa", "inactiva"),
    "canchas": ("estado", "activa", "inactiva"),
    "planes": ("estado", "activo", "inactivo"),
    "pases": ("estado", "activo", "inactivo"),
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
    if isinstance(objeto, (Usuario, Rol, Sede, Plan, Pase)):
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
    if isinstance(objeto, (Reserva, Bloqueo)):
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
    if isinstance(objeto, (PlanUsuario, PaseUsuario)):
        return f"{_relacion(objeto, 'usuario')} · {objeto.mes_cubierto:%m/%Y}"


def _url_registro(objeto):
    ruta = RUTAS_DETALLE.get(type(objeto))
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
        objetos = {}
        urls = {}
        if configuracion:
            modelo, etiqueta, relaciones = configuracion
            claves = [
                tuple(registro.clave_registro[campo] for campo in modelo._meta.pk.field_names)
                if isinstance(modelo._meta.pk, CompositePrimaryKey) else registro.clave_registro["id"]
                for registro in grupo
            ]
            existentes = {objeto.pk: objeto for objeto in modelo.objects.filter(pk__in=claves)}
            for registro, clave in zip(grupo, claves):
                if clave not in existentes and registro.accion != "eliminacion":
                    continue
                datos = {}
                if clave in existentes:
                    datos.update({
                        campo.attname: getattr(existentes[clave], campo.attname)
                        for campo in modelo._meta.concrete_fields
                    })
                # Las diferencias aportan la identidad de esa entrada; los demás campos se completan con el registro vigente.
                datos.update(registro.valores_anteriores)
                datos.update(registro.valores_actuales)
                datos.update(registro.clave_registro)
                objetos[registro.pk] = modelo(**{
                    campo.attname: campo.to_python(datos[campo.attname])
                    for campo in modelo._meta.concrete_fields
                    if campo.attname in datos
                })
            prefetch_related_objects(list(objetos.values()) + list(existentes.values()), *relaciones)
            for registro, clave in zip(grupo, claves):
                if clave in existentes and registro.accion != LogAuditoria.Accion.ELIMINACION:
                    urls[registro.pk] = _url_registro(existentes[clave])
        else:
            modelo, etiqueta = None, tabla.replace("_", " ").capitalize()

        for registro in grupo:
            clave = _clave_legible(registro.clave_registro, modelo)
            objeto = objetos.get(registro.pk)
            filas[registro.pk] = {
                "registro": registro,
                "accion": _accion_visible(registro),
                "tipo": etiqueta,
                "referencia": (_referencia_breve(objeto) or clave) if objeto is not None else clave,
                "url": urls.get(registro.pk),
                "clave": json.dumps(registro.clave_registro, ensure_ascii=False),
                "anteriores": json.dumps(registro.valores_anteriores, ensure_ascii=False, indent=2),
                "actuales": json.dumps(registro.valores_actuales, ensure_ascii=False, indent=2),
            }

    return [filas[registro.pk] for registro in registros]
