import hashlib
import json
from datetime import date, datetime, time

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from clases.servicios import bloquear_usuarios_clase
from common.disponibilidad import validar_disponibilidad
from common.respuestas import aplicar_respuesta
from instalaciones.models import Cancha, Sede
from membresias.models import Membresia, MembresiaUsuario
from usuarios.models import Rol

from .disponibilidad import consultar_disponibilidad, validar_fecha_reserva
from .models import Evento, Reserva, ReservaInvitado, Turno
from .servicios import exigir_acceso_reservas, validar_turno_seleccionado


def inicio_reserva(reserva):
    turno = reserva.evento.turno
    return timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))


def _huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()


def _firmar(actor, accion, datos, huella):
    return signing.dumps({"actor": actor.pk, "accion": accion, "datos": datos, "huella": huella}, salt="reservas.comercial", compress=True)


def _leer(actor, token, accion):
    try:
        datos = signing.loads(token, salt="reservas.comercial", max_age=900)
        if datos["actor"] != actor.pk or datos["accion"] != accion:
            raise signing.BadSignature
        return datos
    except (signing.BadSignature, KeyError, TypeError):
        raise ValidationError("La revisión venció o no es válida. Revisá nuevamente antes de confirmar.") from None


def _validar_persona(usuario):
    if usuario is None or not usuario.is_active or not usuario.puede_reservar:
        raise ValidationError("Cada organizador e invitado debe tener cuenta activa y rol Reservas o Administrador.")


def coberturas(usuarios_ids, fecha, *, bloquear=False):
    consulta = MembresiaUsuario.objects.filter(
        usuario_id__in=usuarios_ids, mes_cubierto=fecha.replace(day=1), estado=MembresiaUsuario.Estado.ACTIVO,
    ).order_by("pk")
    if bloquear:
        consulta = consulta.select_for_update(of=("self",))
    contratos = list(consulta.select_related("membresia"))
    if bloquear:
        productos = {p.pk: p for p in Membresia.objects.select_for_update().filter(pk__in={c.membresia_id for c in contratos}).order_by("pk")}
        for contrato in contratos:
            contrato.membresia = productos[contrato.membresia_id]
    return {contrato.usuario_id: contrato for contrato in contratos if contrato.vigente_en(fecha)}


def usos_del_mes(usuario_id, mes):
    return Reserva.objects.filter(
        organizador_id=usuario_id, computa_hora_membresia=True,
        evento__turno__fecha__year=mes.year, evento__turno__fecha__month=mes.month,
    )


def _condicion(reserva, usuario_id, contratos):
    contrato = contratos.get(usuario_id) if reserva.es_con_membresia else None
    return ("socio", contrato) if contrato else ("no_socio" if reserva.es_con_membresia else "reserva_normal", None)


def _contexto_creacion(actor, datos):
    try:
        fecha = date.fromisoformat(datos["fecha"])
        hora = time(int(datos["hora"]))
        invitados_ids = {int(pk) for pk in datos["invitados"]}
        organizador_id = int(datos["organizador"])
        cancha_inicial = Cancha.objects.get(pk=int(datos["cancha"]))
        modalidad = datos["modalidad"]
        observaciones = datos["observaciones"].strip()
    except (KeyError, TypeError, ValueError, Cancha.DoesNotExist):
        raise ValidationError("Revisá los datos del turno y las personas seleccionadas.") from None
    if modalidad not in ("normal", "membresia") or organizador_id in invitados_ids or len(invitados_ids) != len(datos["invitados"]):
        raise ValidationError("Elegí una modalidad válida y personas sin duplicados ni el organizador entre invitados.")
    usuarios = bloquear_usuarios_clase(invitados_ids | {actor.pk, organizador_id})
    actor = usuarios.get(actor.pk)
    if actor is None:
        raise PermissionDenied
    administrador = exigir_acceso_reservas(actor)
    if not administrador and actor.pk != organizador_id:
        raise PermissionDenied
    for pk in invitados_ids | {organizador_id}:
        _validar_persona(usuarios.get(pk))
    validar_fecha_reserva(fecha)
    disponibilidad = consultar_disponibilidad(cancha_inicial, fecha, requiere_tarifa=modalidad == "normal")
    turno_inicial = next((t for t in disponibilidad["turnos"] if t.hora_inicio == hora), None)
    if turno_inicial is None:
        raise ValidationError("El turno ya no está disponible o está fuera de horario.")
    turno = Turno.objects.select_for_update().select_related("cancha__sede").get(pk=turno_inicial.pk)
    validar_turno_seleccionado(disponibilidad, turno.pk)
    if Evento.objects.filter(turno=turno).exclude(estado=Evento.Estado.ANULADO).exists():
        raise ValidationError("El turno está ocupado. Seleccioná otro en Agenda.")
    if timezone.make_aware(datetime.combine(fecha, hora)) <= timezone.now():
        raise ValidationError("El turno ya comenzó.")
    validar_disponibilidad(invitados_ids | {organizador_id}, fecha, hora, controlar_cupo=True)
    contratos = coberturas(invitados_ids | {organizador_id}, fecha, bloquear=True)
    contrato = contratos.get(organizador_id) if modalidad == "membresia" else None
    if modalidad == "membresia" and contrato is None:
        raise ValidationError("El organizador necesita una membresía Activa que cubra la fecha del turno.")
    usados = usos_del_mes(organizador_id, fecha).count() if contrato else 0
    if contrato and usados >= contrato.membresia.horas_mensuales:
        raise ValidationError("El organizador no tiene horas disponibles para ese mes.")
    reserva = Reserva(
        organizador=usuarios[organizador_id], membresia_usuario=contrato,
        precio_por_turno_aplicado=disponibilidad["precio_por_turno"] if contrato is None else None,
        precio_invitado_aplicado=contrato.membresia.precio_invitado_vigente if contrato else None,
        computa_hora_membresia=contrato is not None,
    )
    invitados = [ReservaInvitado(reserva=reserva, usuario=usuarios[pk]) for pk in sorted(invitados_ids)]
    for invitado in invitados:
        invitado.condicion_aplicada, invitado.membresia_usuario = _condicion(reserva, invitado.usuario_id, contratos)
    total = reserva.precio_por_turno_aplicado if contrato is None else reserva.precio_invitado_aplicado * sum(i.condicion_aplicada == "no_socio" for i in invitados)
    huella = _huella({
        "datos": datos, "turno": turno.pk, "tarifa": reserva.precio_por_turno_aplicado,
        "cuentas": [[u.pk, u.is_active, u.debe_cambiar_contrasena, u.actualizado_en, sorted(v.rol.codigo for v in u.roles.all())] for u in usuarios.values()],
        "contratos": [[c.pk, c.estado, c.actualizado_en, c.membresia.actualizado_en] for c in contratos.values()],
        "usados": usados, "total": total,
    })
    return {"actor": actor, "reserva": reserva, "invitados": invitados, "turno": turno, "total": total, "observaciones": observaciones, "huella": huella}


@transaction.atomic
def preparar_reserva(actor, datos):
    revision = _contexto_creacion(actor, datos)
    revision["confirmacion"] = _firmar(actor, "crear", datos, revision["huella"])
    return revision


@transaction.atomic
def confirmar_reserva(actor, token, *, coordenadas=None):
    firmado = _leer(actor, token, "crear")
    if coordenadas is not None and any(str(firmado["datos"].get(campo)) != str(valor) for campo, valor in coordenadas.items()):
        raise ValidationError("El turno seleccionado cambió. Revisá nuevamente la reserva.")
    revision = _contexto_creacion(actor, firmado["datos"])
    if revision["huella"] != firmado["huella"]:
        raise ValidationError("Las condiciones cambiaron. Revisá nuevamente el resumen de la reserva.")
    with contexto_auditoria(revision["actor"]):
        evento = Evento.objects.create(turno=revision["turno"], tipo=Evento.Tipo.RESERVA, registrado_por=revision["actor"], observaciones=revision["observaciones"])
        reserva = revision["reserva"]
        reserva.evento = evento
        reserva.full_clean()
        reserva.save()
        for invitado in revision["invitados"]:
            invitado.reserva = reserva
            invitado.full_clean()
            invitado.save()
    return reserva


def bloquear_reserva_personas(actor, reserva_id, extras=()):
    inicial = Reserva.objects.select_related("evento__turno__cancha").get(pk=reserva_id)
    invitados_ids = set(inicial.invitados.values_list("usuario_id", flat=True))
    usuarios = bloquear_usuarios_clase(invitados_ids | {actor.pk, inicial.organizador_id} | set(extras))
    actor = usuarios.get(actor.pk)
    if actor is None:
        raise PermissionDenied
    administrador = exigir_acceso_reservas(actor)
    sede = Sede.objects.select_for_update().get(pk=inicial.evento.turno.cancha.sede_id)
    Cancha.objects.select_for_update().get(pk=inicial.evento.turno.cancha_id, sede=sede)
    turno = Turno.objects.select_for_update().get(pk=inicial.evento.turno_id)
    evento = Evento.objects.select_for_update().get(pk=inicial.evento_id)
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    reserva.evento = evento
    reserva.evento.turno = turno
    relaciones = list(reserva.invitados.select_for_update(of=("self",)).select_related("usuario").order_by("usuario_id"))
    if {i.usuario_id for i in relaciones} != invitados_ids or reserva.organizador_id != inicial.organizador_id:
        raise ValidationError("El grupo cambió. Revisá nuevamente la reserva.")
    return actor, administrador, reserva, relaciones, usuarios


def _validar_edicion(actor, administrador, reserva):
    if not administrador and actor.pk != reserva.organizador_id:
        raise PermissionDenied
    if reserva.evento.estado != Evento.Estado.PROGRAMADO or timezone.now() >= inicio_reserva(reserva):
        raise ValidationError("Sólo se puede gestionar una reserva Programada antes del inicio.")


def instantanea_reserva(reserva, invitados):
    return _huella({
        "reserva": [reserva.pk, reserva.evento.estado, reserva.evento.actualizado_en, reserva.membresia_usuario_id, reserva.precio_invitado_aplicado],
        "invitados": [[i.usuario_id, i.estado, i.respuesta, i.actualizado_en, i.membresia_usuario_id, i.condicion_aplicada] for i in invitados],
    })


@transaction.atomic
def gestionar_invitados(actor, reserva_id, invitados_ids, *, confirmacion=None):
    invitados_ids = set(invitados_ids)
    actor, administrador, reserva, relaciones, usuarios = bloquear_reserva_personas(actor, reserva_id, invitados_ids)
    _validar_edicion(actor, administrador, reserva)
    if reserva.organizador_id in invitados_ids:
        raise ValidationError("El organizador no puede aparecer como invitado.")
    anteriores = {i.usuario_id: i for i in relaciones}
    nuevos = {pk for pk in invitados_ids if pk not in anteriores or anteriores[pk].estado == "retirado"}
    if any(i.respuesta == "negativa" for i in relaciones if i.usuario_id in invitados_ids):
        raise ValidationError("Una invitación Rechazada no se retira ni se vuelve a enviar.")
    contratos = coberturas(nuevos, reserva.evento.turno.fecha, bloquear=True)
    propuestas = []
    for pk in sorted(nuevos):
        _validar_persona(usuarios.get(pk))
        validar_disponibilidad({pk}, reserva.evento.turno.fecha, reserva.evento.turno.hora_inicio, reserva_id=reserva.pk, controlar_cupo=True)
        relacion = anteriores.get(pk) or ReservaInvitado(reserva=reserva, usuario=usuarios[pk])
        condicion, contrato = _condicion(reserva, pk, contratos)
        propuestas.append((relacion, "vigente", condicion, contrato))
    for relacion in relaciones:
        if relacion.estado == "vigente" and relacion.respuesta != "negativa" and relacion.usuario_id not in invitados_ids:
            propuestas.append((relacion, "retirado", relacion.condicion_aplicada, relacion.membresia_usuario))
    datos = {"reserva": reserva.pk, "invitados": sorted(invitados_ids)}
    huella = _huella([instantanea_reserva(reserva, relaciones), [[i.usuario_id, estado, condicion, c.pk if c else None, c.actualizado_en if c else None] for i, estado, condicion, c in propuestas]])
    total = reserva.total
    if reserva.es_con_membresia:
        estados = {i.usuario_id: (i.estado, i.condicion_aplicada, i.respuesta) for i in relaciones}
        for i, estado, condicion, _ in propuestas:
            estados[i.usuario_id] = (estado, condicion, i.respuesta)
        total = reserva.precio_invitado_aplicado * sum(estado == "vigente" and condicion == "no_socio" and respuesta != "negativa" for estado, condicion, respuesta in estados.values())
    if confirmacion is None:
        return {"reserva": reserva, "total": total, "cambios": [(str(i.usuario), estado, condicion) for i, estado, condicion, _ in propuestas], "confirmacion": _firmar(actor, "invitados", datos, huella)}
    firmado = _leer(actor, confirmacion, "invitados")
    if firmado["datos"] != datos or firmado["huella"] != huella:
        raise ValidationError("Los invitados o sus condiciones cambiaron. Revisá nuevamente.")
    _validar_edicion(actor, administrador, reserva)
    with contexto_auditoria(actor):
        for relacion, estado, condicion, contrato in propuestas:
            relacion.estado, relacion.condicion_aplicada, relacion.membresia_usuario = estado, condicion, contrato
            relacion.retirado_por = actor if estado == "retirado" else None
            relacion.retirado_en = timezone.now() if estado == "retirado" else None
            relacion.full_clean()
            relacion.save()
    return reserva


@transaction.atomic
def responder_invitacion(actor, reserva_id, respuesta):
    actor, _, reserva, relaciones, _ = bloquear_reserva_personas(actor, reserva_id)
    relacion = next((i for i in relaciones if i.usuario_id == actor.pk), None)
    if relacion is None:
        raise PermissionDenied
    if relacion.estado != "vigente" or reserva.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("La invitación no admite respuestas en su estado actual.")
    cambio = aplicar_respuesta(relacion, actor, respuesta, inicio_reserva(reserva))
    if not cambio:
        return relacion
    if respuesta == "afirmativa":
        _validar_persona(actor)
        validar_disponibilidad({actor.pk}, reserva.evento.turno.fecha, reserva.evento.turno.hora_inicio, reserva_id=reserva.pk, controlar_cupo=True)
        contratos = coberturas({actor.pk}, reserva.evento.turno.fecha, bloquear=True)
        relacion.condicion_aplicada, relacion.membresia_usuario = _condicion(reserva, actor.pk, contratos)
    if timezone.now() >= inicio_reserva(reserva):
        raise ValidationError("La reserva alcanzó su inicio. No se modificó la respuesta.")
    with contexto_auditoria(actor):
        relacion.full_clean()
        relacion.save()
    return relacion


@transaction.atomic
def actualizar_socios(actor, reserva_id, *, confirmacion=None):
    actor, administrador, reserva, relaciones, _ = bloquear_reserva_personas(actor, reserva_id)
    _validar_edicion(actor, administrador, reserva)
    if not reserva.es_con_membresia:
        raise ValidationError("Actualizar socios sólo corresponde a reservas con membresía.")
    candidatos = [i for i in relaciones if i.estado == "vigente" and i.respuesta != "negativa" and i.condicion_aplicada == "no_socio"]
    contratos = coberturas({i.usuario_id for i in candidatos}, reserva.evento.turno.fecha, bloquear=True)
    cambios = [(i, contratos[i.usuario_id]) for i in candidatos if i.usuario_id in contratos]
    huella = _huella([instantanea_reserva(reserva, relaciones), [(i.usuario_id, c.pk, c.actualizado_en) for i, c in cambios]])
    total = reserva.total - reserva.precio_invitado_aplicado * len(cambios)
    if confirmacion is None:
        return {"reserva": reserva, "cambios": [str(i.usuario) for i, _ in cambios], "total": total, "confirmacion": _firmar(actor, "socios", {"reserva": reserva_id}, huella)}
    firmado = _leer(actor, confirmacion, "socios")
    if firmado["datos"] != {"reserva": reserva_id} or firmado["huella"] != huella:
        raise ValidationError("Las membresías o los invitados cambiaron. Revisá nuevamente.")
    _validar_edicion(actor, administrador, reserva)
    with contexto_auditoria(actor):
        for invitado, contrato in cambios:
            invitado.condicion_aplicada = "socio"
            invitado.membresia_usuario = contrato
            invitado.full_clean()
            invitado.save()
    return reserva


@transaction.atomic
def registrar_resultado(actor, reserva_id, resultado, motivo="", *, version):
    actor, administrador, reserva, relaciones, _ = bloquear_reserva_personas(actor, reserva_id)
    if not administrador:
        raise PermissionDenied
    if not reserva.es_con_membresia or reserva.evento.estado != Evento.Estado.FINALIZADO:
        raise ValidationError("El resultado sólo se registra en reservas con membresía Finalizadas.")
    try:
        datos = signing.loads(version, salt="reservas.resultado")
    except (signing.BadSignature, TypeError):
        raise ValidationError("Revisá el resultado antes de confirmar.") from None
    if datos != _datos_resultado(actor, reserva):
        raise ValidationError("El resultado cambió. Revisá nuevamente.")
    if resultado not in ("realizada", "no_realizada") or resultado == reserva.resultado_uso:
        raise ValidationError("Elegí un resultado distinto y válido.")
    if reserva.resultado_corregido_en is not None:
        raise ValidationError("El resultado ya utilizó su única corrección.")
    if reserva.resultado_uso == "sin_registrar":
        reserva.resultado_registrado_por, reserva.resultado_registrado_en = actor, timezone.now()
    else:
        if not motivo.strip():
            raise ValidationError("Indicá el motivo de la corrección.")
        reserva.resultado_original = reserva.resultado_uso
        reserva.resultado_corregido_por, reserva.resultado_corregido_en = actor, timezone.now()
        reserva.motivo_correccion_resultado = motivo.strip()
    reserva.resultado_uso = resultado
    with contexto_auditoria(actor):
        reserva.full_clean()
        reserva.save()
    return reserva


def _datos_resultado(actor, reserva):
    return {"actor": actor.pk, "reserva": reserva.pk, "resultado": reserva.resultado_uso, "corregido": str(reserva.resultado_corregido_en), "registrado": str(reserva.resultado_registrado_en)}


def version_resultado(actor, reserva):
    return signing.dumps(_datos_resultado(actor, reserva), salt="reservas.resultado")
