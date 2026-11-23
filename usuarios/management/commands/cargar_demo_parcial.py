"""Importa un escenario histórico de demostración sobre la base inicial del proyecto."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import repeat
from pathlib import Path
import random
import unicodedata
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import ForeignKey
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from bloqueos.models import Bloqueo
from caja.finanzas import resumen_financiero
from caja.models import AjusteImporte, MovimientoFondo, SesionCaja
from caja.servicios import efectivo_esperado
from clases.models import Asistencia, Clase, ClaseAlumno, ClaseProfesor, Feriado
from common.fechas import FECHA_INICIO_OPERACIONES
from instalaciones.horarios import horarios_efectivos
from instalaciones.models import Cancha
from membresias.fechas import mes_siguiente
from membresias.models import Membresia, MembresiaUsuario, Plan, PlanUsuario
from reservas.models import Evento, Reserva, ReservaInvitado, Turno
from usuarios.forms import validar_celular_ar
from usuarios.models import Rol, Usuario, UsuarioRol


MARCA = ""
NOMBRES = "Lucía Fabricio Yuliana Luciana Gustavo Tiziana Mateo Camila Nicolás Valentina Santiago Julieta Tomás Sofía Benjamín Martina Joaquín Catalina Lautaro Emilia Agustín Paula Ignacio Delfina Facundo Florencia Bruno Victoria Gonzalo Abril Ramiro Rocío Franco Malena Andrés".split()
APELLIDOS = "Herrera Acosta Aguirre Alarcón Álvarez Arias Ávila Barrios Benítez Blanco Bustos Cabrera Cáceres Campos Cárdenas Carrizo Castro Chávez Córdoba Correa Costa Cruz Delgado Díaz Domínguez Duarte Escobar Espinoza Farías Fernández Ferreyra Figueroa Flores Franco Fuentes García Giménez Godoy Gómez González Gutiérrez Guzmán Ibáñez Juárez Lagos Leiva Ledesma López Luna Maidana Maldonado Mansilla Márquez Martínez Medina Méndez Miranda Molina Montero Morales Moreno Muñoz Navarro Núñez Ojeda Oliva Olivera Ortiz Páez Palacios Paredes Paz Peralta Pereyra Pérez Ponce Quiroga Ramírez Ramos Reyes Ríos Rivas Robles Rojas Romero Ruiz Salazar Sánchez Sosa Torres".split()
HORAS = range(15, 7, -1)
DIAS_PLAN = {1: (0,), 2: (1, 3), 3: (0, 2, 4), 5: (0, 1, 2, 3, 4)}


def instante(fecha, hora=7, minuto=0):
    return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))


def normalizar(texto):
    return "".join(letra for letra in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(letra))


def insertar(objeto, creado, actualizado=None):
    # PostgreSQL comprueba referencias, unicidad y restricciones dentro de la transacción.
    referencias = [
        campo.name
        for campo in objeto._meta.fields
        if isinstance(campo, ForeignKey) and campo.db_constraint and not campo.get_limit_choices_to()
    ]
    objeto.full_clean(exclude=referencias, validate_unique=False, validate_constraints=False)
    if isinstance(objeto, Evento):
        # La importación conserva eventos históricos; el alta interactiva exige inicio futuro.
        Evento.objects.bulk_create([objeto])
    else:
        objeto.save()
    fechas = {}
    for campo in objeto._meta.fields:
        if getattr(campo, "auto_now_add", False):
            fechas[campo.name] = creado
        elif getattr(campo, "auto_now", False):
            fechas[campo.name] = actualizado or creado
    if fechas:
        type(objeto).objects.filter(pk=objeto.pk).update(**fechas)
        for nombre, valor in fechas.items():
            setattr(objeto, nombre, valor)
    return objeto


class Command(BaseCommand):
    help = "Importa usuarios, oferta, contrataciones, caja y agenda de demostración desde agosto de 2026."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, default=20261115)
        parser.add_argument("--salida", type=Path, default=Path("output/semilla"))
        parser.add_argument("--omitir-si-hay-datos", action="store_true",
                            help="Conserva una base con datos y omite la importación sin interrumpir el arranque.")

    def handle(self, *args, **opciones):
        self.azar = random.Random(opciones["semilla"])
        self.hoy = timezone.localdate()
        self.mes_actual = self.hoy.replace(day=1)
        if self.mes_actual <= FECHA_INICIO_OPERACIONES:
            raise CommandError("Se necesita al menos un mes anterior dentro del calendario operativo.")
        self.meses = []
        mes = FECHA_INICIO_OPERACIONES
        while mes <= self.mes_actual:
            self.meses.append(mes)
            mes = mes_siguiente(mes)
        self.pagos = defaultdict(list)
        self.ocupacion = set()
        self.personas_ocupadas = defaultdict(set)
        self.usos_organizador = Counter()
        self.usos_invitado = Counter()
        self.reservas_diarias = Counter()
        self.cantidades = Counter()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734021, 2)")
                cursor.execute("LOCK TABLE usuarios, planes, membresias, eventos, planes_usuarios, membresias_usuarios, sesiones_caja IN SHARE ROW EXCLUSIVE MODE")
            if (Usuario.objects.count() != 1 or Plan.objects.exists() or Evento.objects.exists()
                    or PlanUsuario.objects.exists() or MembresiaUsuario.objects.exists() or SesionCaja.objects.exists()
                    or Feriado.objects.exists() or Membresia.objects.count() != 1):
                if opciones["omitir_si_hay_datos"]:
                    self.stdout.write("Demostración omitida: la base contiene datos. Se conservan sin modificaciones.")
                    return
                raise CommandError("La carga requiere la base inicial con un solo administrador y sin operaciones. No borra ni duplica datos.")
            self.admin = Usuario.objects.get(roles__rol__codigo=Rol.ADMINISTRADOR)
            self.canchas = list(Cancha.objects.select_related("sede").order_by("pk"))
            if len(self.canchas) != 4 or len({c.sede_id for c in self.canchas}) != 2:
                raise CommandError("La demostración requiere las dos sedes iniciales con dos canchas cada una.")
            with contexto_auditoria(self.admin):
                self.crear_feriados()
                self.crear_oferta()
                self.crear_personas()
                self.crear_contrataciones()
                self.crear_agenda()
                self.crear_caja()
                self.crear_escenarios_caja()
            # Las referencias de la importación deben resolverse antes de confirmar el lote.
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        opciones["salida"].mkdir(parents=True, exist_ok=True)
        resumen = self.resumen(opciones["semilla"])
        (opciones["salida"] / "resumen.txt").write_text(resumen, encoding="utf-8")
        (opciones["salida"] / "usuarios.txt").write_text(
            "Nombre | Usuario | Email | Celular | Perfil\n" + "\n".join(
                f"{u.get_full_name()} | {u.username} | {u.email} | {u.celular_contacto} | {'Profesor' if i < 6 else 'Participante'}"
                for i, u in enumerate(self.usuarios)
            ) + "\n", encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(resumen))

    def crear_feriados(self):
        for fecha, descripcion in (
            (date(2026, 8, 17), "Paso a la Inmortalidad del General José de San Martín"),
            (date(2026, 10, 12), "Día del Respeto a la Diversidad Cultural"),
        ):
            if fecha <= self.hoy:
                insertar(Feriado(fecha=fecha, descripcion=descripcion), instante(FECHA_INICIO_OPERACIONES))
        self.feriados = set(Feriado.objects.values_list("fecha", flat=True))

    def crear_oferta(self):
        creado = instante(FECHA_INICIO_OPERACIONES - timedelta(days=1))
        self.planes = []
        for modalidad in ("grupal", "individual"):
            for numero, frecuencia in enumerate((1, 2, 3, 5), 1):
                self.planes.append(insertar(Plan(
                    nombre=f"Plan {modalidad} #{numero}", modalidad=modalidad,
                    frecuencia_semanal=frecuencia, cantidad_clases_por_encuentro=1,
                    precio_vigente=Decimal(200000 if numero == 4 else 50000 * frecuencia),
                    descripcion=f"{frecuencia} días por semana, un encuentro de una hora por día."
                    + (" Tarifa mensual de cinco días con descuento: $200.000." if numero == 4 else ""),
                ), creado))
        base = Membresia.objects.get(nombre="Socio 10 horas")
        if (base.horas_organizador, base.horas_invitado) != (10, 10):
            raise CommandError("La membresía inicial debe tener diez horas por rol.")
        self.membresias = [base, insertar(Membresia(
            nombre="Socio 15 horas", horas_organizador=15, horas_invitado=15,
            precio_vigente=Decimal(60000), precio_invitado_vigente=base.precio_invitado_vigente,
            descripcion="Quince horas mensuales como organizador y quince como invitado. Cupos independientes.",
        ), creado)]

    def crear_personas(self):
        self.usuarios = []
        roles = {r.codigo: r for r in Rol.objects.all()}
        creado = instante(FECHA_INICIO_OPERACIONES - timedelta(days=1), 8)
        apellidos = APELLIDOS[:90]
        with ThreadPoolExecutor(max_workers=4) as ejecutor:
            contrasenas = list(ejecutor.map(make_password, repeat("ulisesbatata", len(apellidos))))
        for indice, (apellido, contrasena) in enumerate(zip(apellidos, contrasenas)):
            nombre = NOMBRES[indice % len(NOMBRES)]
            correo = f"{normalizar(apellido)}{normalizar(nombre[0])}@gmail.com"
            usuario = insertar(Usuario(
                username=correo.removesuffix("@gmail.com"), email=correo,
                first_name=nombre, last_name=apellido, fecha_nacimiento=date(2000, 1, 1),
                celular_contacto=validar_celular_ar(f"387500{indice + 1:04d}"),
                password=contrasena, date_joined=creado,
                correo_verificado_en=creado, verificacion_solicitada_en=creado,
                observaciones=MARCA,
            ), creado)
            for codigo in (Rol.PUBLICO, Rol.RESERVAS) + ((Rol.PROFESOR,) if indice < 6 else ()):
                insertar(UsuarioRol(usuario=usuario, rol=roles[codigo], asignado_por=self.admin), creado)
            self.usuarios.append(usuario)
        self.profesores = self.usuarios[:6]
        self.alumnos = self.usuarios[6:]
        self.indices = {u.pk: i for i, u in enumerate(self.alumnos)}

    def crear_contrataciones(self):
        self.contratos = {}
        self.planes_por_mes = defaultdict(list)
        for indice, usuario in enumerate(self.alumnos[:76]):
            anteriores = self.meses[:-1]
            seleccion = [m for m in anteriores if self.azar.random() < (0.85 if indice < 35 else 0.55)]
            if indice < 63:
                seleccion.append(self.mes_actual)
            elif not seleccion:
                seleccion = [self.azar.choice(anteriores)]
            es_membresia = indice % 4 == 0
            for mes in seleccion:
                producto = self.membresias[(indice // 4 + mes.month) % 2] if es_membresia else self.planes[(indice + mes.month // 2) % 8]
                datos = dict(usuario=usuario, mes_cubierto=mes, fecha_alta=mes,
                             precio_aplicado=producto.precio_vigente, registrado_por=self.admin,
                             observaciones=MARCA, estado="activo" if mes == self.mes_actual else "vencido")
                if es_membresia:
                    contrato = MembresiaUsuario(membresia=producto, horas_organizador_aplicadas=producto.horas_organizador,
                                               horas_invitado_aplicadas=producto.horas_invitado, **datos)
                    tipo = "membresia"
                else:
                    contrato = PlanUsuario(plan=producto, **datos)
                    tipo = "plan"
                insertar(contrato, instante(mes))
                self.contratos[(usuario.pk, mes)] = contrato
                self.cantidades[f"contrataciones_{tipo}"] += 1
                if not es_membresia:
                    self.planes_por_mes[mes].append(contrato)
                    if not usuario.tiene_rol(Rol.ALUMNO):
                        insertar(UsuarioRol(usuario=usuario, rol=Rol.objects.get(codigo=Rol.ALUMNO), asignado_por=self.admin), instante(mes))
                fecha_pago = mes + timedelta(days=1 + indice % 6)
                importe = contrato.precio_aplicado
                parcial = indice % 9 == 0
                self.agendar_pago(fecha_pago, importe * (Decimal("0.60") if parcial else Decimal(1)), tipo, contrato,
                                  concepto="Pago parcial de suscripción" if parcial else "Pago total de suscripción")
                if parcial:
                    self.cantidades["suscripciones_pago_parcial"] += 1
                elif indice % 10 == 0:
                    # Dos recibos completan el mismo importe sin duplicar el cobro.
                    self.pagos[fecha_pago][-1]["monto"] = importe / 2
                    self.agendar_pago(fecha_pago + timedelta(days=5), importe / 2, tipo, contrato, concepto="Saldo de suscripción")

    def agendar_pago(self, fecha, monto, tipo, origen, *, concepto, devolucion=False):
        if monto <= 0 or fecha > self.hoy:
            return
        self.pagos[fecha].append(dict(monto=monto.quantize(Decimal("0.01")), tipo=tipo, origen=origen,
                                      concepto=concepto, devolucion=devolucion))

    def evento(self, cancha, fecha, hora, tipo, *, anulado=False, motivo=""):
        hora_inicio = time(hora)
        if not self.horarios[cancha.sede_id][fecha].contiene(hora_inicio, time(hora + 1)):
            raise CommandError(f"El turno del {fecha} a las {hora_inicio:%H:%M} está fuera del horario de {cancha.sede}.")
        clave = (fecha, hora, cancha.pk)
        if clave in self.ocupacion:
            raise CommandError(f"Turno repetido en la carga: {clave}.")
        inicio = instante(fecha, hora)
        fin = inicio + timedelta(hours=1)
        if fin > timezone.now():
            raise CommandError("La importación no admite actividades futuras ni en curso.")
        turno = self.turnos.get(clave)
        if turno is None:
            turno = insertar(Turno(cancha=cancha, fecha=fecha, hora_inicio=hora_inicio), instante(fecha))
            self.turnos[clave] = turno
        datos = dict(turno=turno, tipo=tipo, registrado_por=self.admin, observaciones=MARCA,
                     estado="anulado" if anulado else "finalizado")
        if anulado:
            datos.update(anulado_por=self.admin, anulado_en=inicio - timedelta(minutes=30), motivo_anulacion=motivo)
        else:
            datos["finalizado_en"] = fin
            self.ocupacion.add(clave)
        return insertar(Evento(**datos), instante(fecha, 7, 15), fin if not anulado else datos["anulado_en"])

    def crear_bloqueos(self, fecha):
        indice_mes = self.meses.index(fecha.replace(day=1))
        clima = fecha.weekday() == 5 and 7 <= fecha.day <= 13
        for cancha in self.canchas:
            horas = (13, 14, 15) if clima else ()
            for hora in horas:
                evento = self.evento(cancha, fecha, hora, "bloqueo")
                insertar(Bloqueo(evento=evento, motivo="clima_adverso"), evento.creado_en)
                self.cantidades["bloqueos"] += 1
        if fecha.day == 22:
            cancha = self.canchas[indice_mes % 4]
            for hora in (8, 9):
                evento = self.evento(cancha, fecha, hora, "bloqueo")
                insertar(Bloqueo(evento=evento, motivo="mantenimiento"), evento.creado_en)
                self.cantidades["bloqueos"] += 1

    def buscar_turno(self, fecha, personas, *, preferencia=0):
        for hora in HORAS:
            if not personas.isdisjoint(self.personas_ocupadas[(fecha, hora)]):
                continue
            for desplazamiento in range(4):
                cancha = self.canchas[(preferencia + desplazamiento) % 4]
                if (fecha, hora, cancha.pk) not in self.ocupacion:
                    return cancha, hora
        return None

    def crear_clases(self, fecha):
        if fecha in self.feriados or fecha.weekday() >= 5:
            return
        grupos = defaultdict(list)
        for contrato in self.planes_por_mes[fecha.replace(day=1)]:
            if fecha.weekday() in DIAS_PLAN[contrato.plan.frecuencia_semanal]:
                grupos[contrato.plan_id].append(contrato)
        numero_grupo = 0
        for contratos in grupos.values():
            tamano = 4 if contratos[0].plan.modalidad == "grupal" else 1
            for inicio in range(0, len(contratos), tamano):
                participantes = [c.usuario for c in contratos[inicio:inicio + tamano]]
                profesor = self.profesores[numero_grupo % 6]
                personas = {u.pk for u in participantes} | {profesor.pk}
                turno = self.buscar_turno(fecha, personas, preferencia=numero_grupo % 4)
                numero_grupo += 1
                if turno is None:
                    raise CommandError(f"No hay capacidad para las clases del {fecha}.")
                cancha, hora = turno
                anulado = self.azar.random() < 0.035
                evento = self.evento(cancha, fecha, hora, "clase", anulado=anulado, motivo="Profesor ausente por motivo personal")
                clase = insertar(Clase(evento=evento, finalizado_por=None if anulado else profesor), evento.creado_en)
                insertar(ClaseProfesor(clase=clase, profesor=profesor), evento.creado_en)
                for alumno in participantes:
                    insertar(ClaseAlumno(clase=clase, usuario=alumno), evento.creado_en)
                    if not anulado:
                        probabilidad = min(0.94, 0.68 + 0.06 * self.meses.index(fecha.replace(day=1)))
                        sin_carga = self.azar.random() < 0.035
                        estado = "sin_registrar" if sin_carga else "presente" if self.azar.random() < probabilidad else "ausente"
                        insertar(Asistencia(clase=clase, usuario=alumno, estado=estado,
                                            registrada_por=None if sin_carga else profesor,
                                            registrada_en=None if sin_carga else evento.finalizado_en + timedelta(minutes=5)),
                                 evento.finalizado_en + timedelta(minutes=5))
                if not anulado:
                    self.personas_ocupadas[(fecha, hora)].update(personas)
                self.cantidades["clases_anuladas" if anulado else "clases_finalizadas"] += 1

    def crear_reservas(self, fecha):
        mes = fecha.replace(day=1)
        cantidad = 3 + self.meses.index(mes) + (2 if fecha.weekday() >= 5 else 0)
        for numero in range(cantidad):
            candidatos = self.alumnos.copy()
            self.azar.shuffle(candidatos)
            disponibles = [u for u in candidatos if self.reservas_diarias[(fecha, u.pk)] < 2]
            usuario = disponibles[0]
            turno = self.buscar_turno(fecha, {usuario.pk}, preferencia=(numero + fecha.day) % 4)
            if turno is None:
                continue
            cancha, hora = turno
            contrato = self.contratos.get((usuario.pk, mes))
            socio = isinstance(contrato, MembresiaUsuario) and self.usos_organizador[(usuario.pk, mes)] < contrato.horas_organizador_aplicadas
            con_membresia = socio and self.azar.random() < 0.85
            anulado = self.azar.random() < 0.065
            evento = self.evento(cancha, fecha, hora, "reserva", anulado=anulado, motivo="Cancelación solicitada por el organizador")
            if anulado:
                evento.anulado_por = usuario
                Evento.objects.filter(pk=evento.pk).update(anulado_por=usuario)
            reserva = insertar(Reserva(
                evento=evento, organizador=usuario, membresia_usuario=contrato if con_membresia else None,
                precio_por_turno_aplicado=None if con_membresia else cancha.sede.precio_reserva_vigente,
                precio_invitado_aplicado=contrato.membresia.precio_invitado_vigente if con_membresia else None,
                computa_hora_membresia=bool(con_membresia), anulada_por_organizador=True if anulado else None,
                resultado_uso=("no_realizada" if self.azar.random() < 0.08 else "realizada") if con_membresia and not anulado else "sin_registrar",
                resultado_registrado_por=self.admin if con_membresia and not anulado else None,
                resultado_registrado_en=evento.finalizado_en + timedelta(minutes=10) if con_membresia and not anulado else None,
            ), evento.creado_en, evento.finalizado_en or evento.anulado_en)
            self.reservas_diarias[(fecha, usuario.pk)] += 1
            if con_membresia:
                # La cancelación del organizador a treinta minutos consume su hora.
                self.usos_organizador[(usuario.pk, mes)] += 1
            personas = {usuario.pk}
            invitados = [u for u in candidatos if u.pk != usuario.pk and u.pk not in self.personas_ocupadas[(fecha, hora)]]
            for invitado in invitados[:self.azar.choice((1, 1, 2, 3))]:
                respuesta = self.azar.choices(("afirmativa", "negativa", "pendiente"), (85, 10, 5))[0]
                cobertura = self.contratos.get((invitado.pk, mes))
                condicion, aplicada = "sin_aplicar", None
                if respuesta == "afirmativa":
                    personas.add(invitado.pk)
                    if not con_membresia:
                        condicion = "reserva_normal"
                    elif isinstance(cobertura, MembresiaUsuario):
                        aplicada = cobertura
                        condicion = "socio" if self.usos_invitado[(invitado.pk, mes)] < cobertura.horas_invitado_aplicadas else "cupo_agotado"
                        if condicion == "socio" and not anulado:
                            self.usos_invitado[(invitado.pk, mes)] += 1
                    else:
                        condicion = "no_socio"
                insertar(ReservaInvitado(reserva=reserva, usuario=invitado, respuesta=respuesta,
                                        condicion_aplicada=condicion, membresia_usuario=aplicada,
                                        respondido_por=invitado if respuesta != "pendiente" else None,
                                        respondido_en=instante(fecha, 7, 25) if respuesta != "pendiente" else None),
                         evento.creado_en, instante(fecha, 7, 25))
            if not anulado:
                self.personas_ocupadas[(fecha, hora)].update(personas)
            importe = reserva.total
            indice = self.indices[usuario.pk]
            parcial = indice % 9 == 0 and not anulado
            cobro = importe * (Decimal("0.60") if parcial else Decimal(1))
            self.agendar_pago(fecha, cobro, "reserva", reserva, concepto="Pago parcial de reserva" if parcial else "Pago de reserva")
            if anulado:
                self.agendar_pago(fecha, cobro, "reserva", reserva, concepto="Devolución por cancelación de reserva", devolucion=True)
            self.cantidades["reservas_anuladas" if anulado else "reservas_finalizadas"] += 1

    def crear_agenda(self):
        fechas = [
            FECHA_INICIO_OPERACIONES + timedelta(days=dia)
            for dia in range((self.hoy - FECHA_INICIO_OPERACIONES).days)
        ]
        sedes = {cancha.sede_id: cancha.sede for cancha in self.canchas}
        self.horarios = {sede_id: horarios_efectivos(sede, fechas) for sede_id, sede in sedes.items()}
        self.turnos = {
            (turno.fecha, turno.hora_inicio.hour, turno.cancha_id): turno
            for turno in Turno.objects.filter(
                cancha__in=self.canchas, fecha__gte=FECHA_INICIO_OPERACIONES, fecha__lt=self.hoy,
            ).order_by()
        }
        # La agenda parte sin eventos; la ocupación se registra al generar cada actividad.
        for fecha in fechas:
            self.crear_bloqueos(fecha)
            self.crear_clases(fecha)
            self.crear_reservas(fecha)
            if fecha.day in (1, 15):
                self.stdout.write(f"Agenda importada hasta {fecha:%d/%m/%Y}…", ending="\n")

    def crear_caja(self):
        for fecha, pagos in sorted(self.pagos.items()):
            sesion = insertar(SesionCaja(responsable=self.admin, efectivo_inicial=Decimal(50000)), instante(fecha))
            for numero, pago in enumerate(pagos):
                origen, tipo = pago["origen"], pago["tipo"]
                devolucion = pago["devolucion"]
                medio = self.azar.choices(("efectivo", "transferencia", "qr", "tarjeta"), (25, 35, 30, 10))[0]
                # Una devolución usa transferencia para no consumir efectivo de otra operación.
                if devolucion:
                    medio = "transferencia"
                campo = {"plan": "plan_usuario", "membresia": "membresia_usuario", "reserva": "reserva"}[tipo]
                if tipo == "reserva":
                    creado = instante(fecha, 7, 27) if not devolucion else origen.evento.anulado_en + timedelta(minutes=5)
                else:
                    creado = instante(fecha, 9, numero % 60)
                insertar(MovimientoFondo(
                    operacion_id=uuid4(), sesion=sesion, clase="egreso" if devolucion else "ingreso",
                    concepto=f"{pago['concepto']} · {MARCA}", monto=pago["monto"], medio_pago=medio,
                    referencia="" if medio == "efectivo" else f"DEMO-{fecha:%Y%m%d}-{numero + 1:04d}",
                    categoria_ingreso="" if devolucion else {"plan": "planes", "membresia": "membresias", "reserva": "reservas"}[tipo],
                    categoria_egreso="devoluciones" if devolucion else "", registrado_por=self.admin,
                    destinatario=origen.organizador.get_full_name() if devolucion else "", **{campo: origen},
                ), creado)
                self.cantidades["devoluciones" if devolucion else "pagos"] += 1
            esperado = efectivo_esperado(sesion)
            if esperado > 50000:
                insertar(MovimientoFondo(
                    operacion_id=uuid4(), sesion=sesion, clase="retiro", concepto="Retiro de efectivo al cierre de caja",
                    monto=esperado - Decimal(50000), medio_pago="efectivo", registrado_por=self.admin,
                ), instante(fecha, 23, 10))
            sesion.estado = "cerrada"
            sesion.cerrada_en = instante(fecha, 23, 30)
            if sesion.cerrada_en > timezone.now():
                sesion.cerrada_en = timezone.now()
            sesion.efectivo_esperado = efectivo_esperado(sesion)
            sesion.efectivo_contado = sesion.efectivo_esperado
            sesion.diferencia = Decimal(0)
            sesion.full_clean()
            sesion.save(update_fields=("estado", "cerrada_en", "efectivo_esperado", "efectivo_contado", "diferencia"))
            self.cantidades["cajas_cerradas"] += 1

    def crear_escenarios_caja(self):
        contratos = []
        for contrato in self.contratos.values():
            if contrato.mes_cubierto != self.mes_actual or not isinstance(contrato, PlanUsuario):
                continue
            resumen = resumen_financiero("plan", contrato)
            if resumen["maximo_ingreso"] > 0 and resumen["neto_recibido"] >= Decimal("5000.00"):
                contratos.append(contrato)
                if len(contratos) == 4:
                    break
        if len(contratos) < 4:
            return
        sesion = SesionCaja.objects.create(responsable=self.admin, efectivo_inicial=Decimal("50000.00"))
        for contrato, importe_nuevo, motivo in (
            (contratos[0], resumen_financiero("plan", contratos[0])["neto_recibido"] - Decimal("5000.00"), "Reducción del importe acordado"),
            (contratos[1], contratos[1].importe_acordado + Decimal("10000.00"), "Ampliación del importe acordado"),
        ):
            AjusteImporte.objects.create(
                operacion_id=uuid4(), plan_usuario=contrato, importe_anterior=contrato.importe_acordado,
                importe_nuevo=importe_nuevo,
                motivo=f"{motivo} · {MARCA}", registrado_por=self.admin,
            )
            self.cantidades["ajustes_importe"] += 1
        for numero, contrato in enumerate(contratos[2:], 1):
            MovimientoFondo.objects.create(
                operacion_id=uuid4(), sesion=sesion, clase="ingreso", concepto=f"Pago recibido con excedente · {MARCA}",
                monto=resumen_financiero("plan", contrato)["maximo_ingreso"] + Decimal("5000.00"),
                medio_pago="transferencia", referencia=f"DEMO-EXCEDENTE-{numero}",
                categoria_ingreso="planes", plan_usuario=contrato, registrado_por=self.admin,
                motivo_excedente="El cliente transfirió un importe mayor al saldo pendiente.",
            )
            self.cantidades["cobros_con_excedente"] += 1
            if numero == 2:
                maximo = resumen_financiero("plan", contrato)["maximo_devolucion"]
                MovimientoFondo.objects.create(
                    operacion_id=uuid4(), sesion=sesion, clase="egreso", categoria_egreso="devoluciones",
                    concepto=f"Devolución del excedente recibido · {MARCA}", monto=maximo, medio_pago="transferencia",
                    referencia=f"DEMO-DEVOLUCION-EXCEDENTE-{numero}", plan_usuario=contrato, registrado_por=self.admin,
                )
                self.cantidades["devoluciones"] += 1
        sesion.estado = "cerrada"
        sesion.cerrada_en = timezone.now()
        sesion.efectivo_esperado = efectivo_esperado(sesion)
        sesion.efectivo_contado = sesion.efectivo_esperado
        sesion.diferencia = Decimal("0.00")
        sesion.full_clean()
        sesion.save(update_fields=("estado", "cerrada_en", "efectivo_esperado", "efectivo_contado", "diferencia"))
        self.cantidades["cajas_cerradas"] += 1

    def resumen(self, semilla):
        return (
            f"{MARCA}\nSemilla: {semilla}\nPeríodo: {FECHA_INICIO_OPERACIONES} a {self.hoy}\n"
            "Usuarios nuevos: 90 (6 profesores y 84 participantes), además del administrador inicial.\n"
            "63 participantes con suscripción activa; 13 sólo con anteriores; 8 sin contrataciones.\n"
            "Planes: 8. Membresías: 2. Contrataciones sin meses futuros.\n"
            "Cumpleaños de los usuarios nuevos: 01/01/2000. Contraseña: ulisesbatata.\n"
            "El administrador inicial conserva sus datos y contraseña.\n"
            + "\n".join(f"{nombre}: {cantidad}" for nombre, cantidad in sorted(self.cantidades.items()))
            + "\nLa importación no crea ni envía correos. Las fechas de auditoría corresponden al momento de importación.\n"
        )
