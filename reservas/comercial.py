from common.validaciones import validar_motivo

import hashlib
import json
from datetime import date, datetime, time

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from comunicaciones.actividades import avisar_reserva
from comunicaciones.retiradas import avisar_retirada_invitacion
from clases.servicios import bloquear_usuarios_clase
from common.disponibilidad import validar_disponibilidad, validar_limite_reservas_organizadas
from common.fechas import validar_inicio_evento
from instalaciones.models import Cancha, Sede
from membresias.models import Membresia, MembresiaUsuario
from usuarios.models import Rol

from .disponibilidad import consultar_disponibilidad, validar_fecha_reserva
from .horas import horas_disponibles_invitado, saldo_horas_contratacion
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
    if usuario is None or not usuario.esta_habilitado or not usuario.puede_reservar:
        raise ValidationError("Cada organizador e invitado debe tener cuenta activa, correo verificado y rol Reservas o Administrador.")


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


def _condicion(reserva, usuario_id, contratos):
    if not reserva.es_con_membresia:
        return "reserva_normal", None
    contrato = contratos.get(usuario_id)
    if contrato is None:
        return "no_socio", None
    if horas_disponibles_invitado(contrato) == 0:
        return "cupo_agotado", contrato
    return "socio", contrato


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
    validar_disponibilidad({organizador_id}, fecha, hora)
    validar_limite_reservas_organizadas(organizador_id)
    contratos = coberturas({organizador_id}, fecha, bloquear=True) if modalidad == "membresia" else {}
    contrato = contratos.get(organizador_id) if modalidad == "membresia" else None
    if modalidad == "membresia" and contrato is None:
        raise ValidationError("El organizador necesita una membresía Activa que cubra la fecha del turno.")
    saldo_organizador = saldo_horas_contratacion(contrato, "organizador") if contrato else None
    if contrato and saldo_organizador["disponibles"] == 0:
        raise ValidationError("El organizador no tiene horas disponibles para ese mes.")
    reserva = Reserva(
        organizador=usuarios[organizador_id], membresia_usuario=contrato,
        precio_por_turno_aplicado=disponibilidad["precio_por_turno"] if contrato is None else None,
        precio_invitado_aplicado=contrato.membresia.precio_invitado_vigente if contrato else None,
        computa_hora_membresia=contrato is not None,
    )
    invitados = [ReservaInvitado(reserva=reserva, usuario=usuarios[pk]) for pk in sorted(invitados_ids)]
    total = reserva.precio_por_turno_aplicado if contrato is None else 0
    huella = _huella({
        "datos": datos, "turno": turno.pk, "tarifa": reserva.precio_por_turno_aplicado,
        "cuentas": [[u.pk, u.is_active, u.correo_verificado_en, u.debe_cambiar_contrasena, u.actualizado_en, sorted(v.rol.codigo for v in u.roles.all())] for u in usuarios.values()],
        "contratos": [[c.pk, c.estado, c.actualizado_en, c.membresia.actualizado_en] for c in contratos.values()],
        "saldo_organizador": saldo_organizador,
        "invitados": [[i.usuario_id, i.condicion_aplicada, i.membresia_usuario_id] for i in invitados],
        "total": total,
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
    validar_fecha_reserva(revision["turno"].fecha)
    validar_inicio_evento(revision["turno"].fecha, revision["turno"].hora_inicio)
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
            avisar_reserva(reserva, "invitacion", invitado=invitado)
        avisar_reserva(reserva, "reserva_creada")
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
        "invitados": [[i.usuario_id, str(i.identidad), i.respuesta, i.actualizado_en, i.membresia_usuario_id, i.condicion_aplicada] for i in invitados],
    })


@transaction.atomic
def gestionar_invitados(actor, reserva_id, invitados_ids, *, confirmacion=None):
    invitados_ids = set(invitados_ids)
    actor, administrador, reserva, relaciones, usuarios = bloquear_reserva_personas(actor, reserva_id, invitados_ids)
    _validar_edicion(actor, administrador, reserva)
    if reserva.organizador_id in invitados_ids:
        raise ValidationError("El organizador no puede aparecer como invitado.")
    anteriores = {i.usuario_id: i for i in relaciones}
    nuevos = invitados_ids - anteriores.keys()
    quitados = anteriores.keys() - invitados_ids
    for pk in sorted(nuevos):
        _validar_persona(usuarios.get(pk))
    datos = {"reserva": reserva.pk, "invitados": sorted(invitados_ids)}
    huella = instantanea_reserva(reserva, relaciones)
    total = reserva.precio_por_turno_aplicado if not reserva.es_con_membresia else reserva.precio_invitado_aplicado * sum(
        i.participacion_computable and i.genera_adicional for i in relaciones if i.usuario_id in invitados_ids
    )
    if confirmacion is None:
        cambios = [(str(usuarios[pk]), "agregar", "sin_aplicar") for pk in sorted(nuevos)]
        cambios += [(str(anteriores[pk].usuario), "quitar", anteriores[pk].condicion_aplicada) for pk in sorted(quitados)]
        return {"reserva": reserva, "total": total, "cambios": cambios,
                "confirmacion": _firmar(actor, "invitados", datos, huella)}
    firmado = _leer(actor, confirmacion, "invitados")
    if firmado["datos"] != datos or firmado["huella"] != huella:
        raise ValidationError("Los invitados o sus condiciones cambiaron. Revisá nuevamente.")
    _validar_edicion(actor, administrador, reserva)
    with contexto_auditoria(actor):
        for pk in sorted(quitados):
            avisar_retirada_invitacion(reserva, anteriores[pk])
            anteriores[pk].delete()
        for pk in sorted(nuevos):
            relacion = ReservaInvitado(reserva=reserva, usuario=usuarios[pk])
            relacion.full_clean()
            relacion.save()
            avisar_reserva(reserva, "invitacion", invitado=relacion)
        _validar_edicion(actor, administrador, reserva)
    return reserva


def version_invitacion(actor, invitacion):
    return signing.dumps({"actor": actor.pk, "reserva": invitacion.reserva_id,
                          "identidad": str(invitacion.identidad), "actualizada": invitacion.actualizado_en.isoformat()},
                         salt="reservas.invitacion", compress=True)


def _contexto_respuesta(actor, reserva_id, respuesta, version):
    actor, _, reserva, relaciones, _ = bloquear_reserva_personas(actor, reserva_id)
    relacion = next((i for i in relaciones if i.usuario_id == actor.pk), None)
    if relacion is None:
        raise PermissionDenied
    try:
        anterior = signing.loads(version, salt="reservas.invitacion", max_age=900)
        actual = signing.loads(version_invitacion(actor, relacion), salt="reservas.invitacion")
        if anterior != actual:
            raise signing.BadSignature
    except (signing.BadSignature, TypeError):
        raise ValidationError("La invitación cambió. Volvé a abrir su detalle.") from None
    if reserva.evento.estado != Evento.Estado.PROGRAMADO or timezone.now() >= inicio_reserva(reserva):
        raise ValidationError("Sólo podés responder antes del inicio de una reserva Programada.")
    if respuesta not in (ReservaInvitado.Respuesta.AFIRMATIVA, ReservaInvitado.Respuesta.NEGATIVA):
        raise ValidationError("Elegí Aceptar o Rechazar.")
    condicion, contrato = relacion.condicion_aplicada, relacion.membresia_usuario
    if relacion.respuesta != respuesta:
        condicion, contrato = "sin_aplicar", None
        if respuesta == ReservaInvitado.Respuesta.AFIRMATIVA:
            _validar_persona(actor)
            turno = reserva.evento.turno
            validar_disponibilidad({actor.pk}, turno.fecha, turno.hora_inicio, reserva_id=reserva.pk)
            contratos = coberturas({actor.pk}, turno.fecha, bloquear=True) if reserva.es_con_membresia else {}
            condicion, contrato = _condicion(reserva, actor.pk, contratos)
    datos = {"reserva": reserva.pk, "respuesta": respuesta, "version": version}
    huella = _huella([instantanea_reserva(reserva, relaciones), condicion, contrato.pk if contrato else None,
                     contrato.actualizado_en if contrato else None])
    return actor, reserva, relacion, condicion, contrato, datos, huella


@transaction.atomic
def preparar_respuesta_invitacion(actor, reserva_id, respuesta, *, version):
    actor, reserva, relacion, condicion, contrato, datos, huella = _contexto_respuesta(actor, reserva_id, respuesta, version)
    return {"reserva": reserva, "invitacion": relacion, "respuesta": respuesta, "condicion": condicion,
            "adicional": reserva.precio_invitado_aplicado if condicion in ("no_socio", "cupo_agotado") else None,
            "version": version, "confirmacion": _firmar(actor, "respuesta", datos, huella)}


@transaction.atomic
def responder_invitacion(actor, reserva_id, respuesta, *, version, confirmacion):
    actor, reserva, relacion, condicion, contrato, datos, huella = _contexto_respuesta(actor, reserva_id, respuesta, version)
    firmado = _leer(actor, confirmacion, "respuesta")
    if firmado["datos"] != datos or firmado["huella"] != huella:
        raise ValidationError("La disponibilidad o la condición comercial cambió. Revisá nuevamente antes de confirmar.")
    if relacion.respuesta == respuesta:
        return relacion
    relacion.respuesta, relacion.condicion_aplicada, relacion.membresia_usuario = respuesta, condicion, contrato
    relacion.respondido_por, relacion.respondido_en = actor, timezone.now()
    with contexto_auditoria(actor):
        relacion.full_clean()
        if timezone.now() >= inicio_reserva(reserva):
            raise ValidationError("La reserva alcanzó su inicio. No se modificó la respuesta.")
        relacion.save()
        avisar_reserva(reserva, "respuesta_invitacion", respuesta=relacion)
    return relacion


@transaction.atomic
def actualizar_socios(actor, reserva_id, *, confirmacion=None):
    actor, administrador, reserva, relaciones, _ = bloquear_reserva_personas(actor, reserva_id)
    _validar_edicion(actor, administrador, reserva)
    if not reserva.es_con_membresia:
        raise ValidationError("Actualizar socios sólo corresponde a reservas con membresía.")
    candidatos = [i for i in relaciones if i.respuesta == "afirmativa" and i.genera_adicional]
    contratos = coberturas({i.usuario_id for i in candidatos}, reserva.evento.turno.fecha, bloquear=True)
    cambios = [(i, contratos[i.usuario_id]) for i in candidatos
               if i.usuario_id in contratos and horas_disponibles_invitado(contratos[i.usuario_id]) > 0]
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
        validar_motivo(motivo)
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
