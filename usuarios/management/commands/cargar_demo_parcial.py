"""Importa un escenario histórico y vigente de demostración sobre la base inicial del proyecto."""

from calendar import monthrange
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import repeat
import os
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
from caja.models import AjusteImporte, MovimientoFondo, SesionCaja
from clases.models import Asistencia, Clase, ClaseAlumno, ClaseProfesor, Feriado
from common.fechas import FECHA_INICIO_OPERACIONES
from comunicaciones.configuracion import obtener_configuracion
from instalaciones.horarios import horarios_efectivos
from instalaciones.models import Cancha
from membresias.continuidad import ventana_continuidad
from membresias.fechas import mes_siguiente
from membresias.models import Membresia, MembresiaUsuario, Plan, PlanUsuario, RespuestaContinuidad
from reservas.models import Evento, Reserva, ReservaInvitado, Turno
from usuarios.forms import validar_celular_ar
from usuarios.models import Rol, Usuario, UsuarioRol


NOMBRES = (
    "Lucía Fabricio Yuliana Luciana Gustavo Tiziana Mateo Camila Nicolás Valentina "
    "Santiago Julieta Tomás Sofía Benjamín Martina Joaquín Catalina Lautaro Emilia "
    "Agustín Paula Ignacio Delfina Facundo Florencia Bruno Victoria Gonzalo Abril "
    "Ramiro Rocío Franco Malena Andrés"
).split()
APELLIDOS = (
    "Herrera Acosta Aguirre Alarcón Álvarez Arias Ávila Barrios Benítez Blanco Bustos "
    "Cabrera Cáceres Campos Cárdenas Carrizo Castro Chávez Córdoba Correa Costa Cruz "
    "Delgado Díaz Domínguez Duarte Escobar Espinoza Farías Fernández Ferreyra Figueroa "
    "Flores Franco Fuentes García Giménez Godoy Gómez González Gutiérrez Guzmán Ibáñez "
    "Juárez Lagos Leiva Ledesma López Luna Maidana Maldonado Mansilla Márquez Martínez "
    "Medina Méndez Miranda Molina Montero Morales Moreno Muñoz Navarro Núñez Ojeda "
    "Oliva Olivera Ortiz Páez Palacios Paredes Paz Peralta Pereyra Pérez Ponce Quiroga "
    "Ramírez Ramos Reyes Ríos Rivas Robles Rojas Romero Ruiz Salazar Sánchez Sosa Torres"
).split()
HORAS = range(19, 11, -1)
DIAS_PLAN = {1: (0,), 2: (1, 3), 3: (0, 2, 4), 5: (0, 1, 2, 3, 4)}
MOTIVOS_ANULACION_CONTRATO = (
    "Cambio de disponibilidad horaria del titular",
    "Lesión informada antes de iniciar las actividades",
    "Viaje laboral confirmado para el mes",
    "Reorganización personal de agenda",
)
MOTIVOS_ANULACION_CLASE = (
    "Profesor ausente por motivo personal",
    "Reprogramación docente informada por la sede",
)
MOTIVOS_ANULACION_RESERVA = (
    "Cancelación solicitada por el organizador",
    "Cambio de planes del grupo de jugadores",
    "Inconveniente de último momento del organizador",
)
MODELOS_IMPORTADOS = (
    Feriado, Plan, Membresia, Usuario, UsuarioRol, PlanUsuario, MembresiaUsuario,
    Turno, Evento, Bloqueo, Clase, ClaseProfesor, ClaseAlumno, Asistencia,
    Reserva, ReservaInvitado, SesionCaja, MovimientoFondo, AjusteImporte,
)
CAMPOS_AUTO = {
    modelo: (
        tuple(c.name for c in modelo._meta.fields if getattr(c, "auto_now_add", False)),
        tuple(c.name for c in modelo._meta.fields if getattr(c, "auto_now", False)),
    )
    for modelo in MODELOS_IMPORTADOS
}
REFERENCIAS_FK = {
    modelo: tuple(
        c.name for c in modelo._meta.fields
        if isinstance(c, ForeignKey) and c.db_constraint and not c.get_limit_choices_to()
    )
    for modelo in MODELOS_IMPORTADOS
}


def instante(fecha, hora=8, minuto=0):
    return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))


def normalizar(texto):
    return "".join(
        letra for letra in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(letra)
    )


def ultimo_dia_mes(mes):
    return mes.replace(day=monthrange(mes.year, mes.month)[1])


@contextmanager
def fechas_explicitas(modelos):
    """Permite fijar creado_en y actualizado_en en bulk_create sin generar UPDATEs ni auditoría espuria."""
    estado_original = []
    for modelo in modelos:
        for campo in modelo._meta.fields:
            auto_add = getattr(campo, "auto_now_add", False)
            auto_now = getattr(campo, "auto_now", False)
            if auto_add or auto_now:
                estado_original.append((campo, auto_add, auto_now))
                campo.auto_now_add = False
                campo.auto_now = False
    try:
        yield
    finally:
        for campo, auto_add, auto_now in estado_original:
            campo.auto_now_add = auto_add
            campo.auto_now = auto_now


def preparar(objeto, creado, actualizado=None):
    modelo = type(objeto)
    campos_add, campos_now = CAMPOS_AUTO[modelo]
    for nombre in campos_add:
        setattr(objeto, nombre, creado)
    for nombre in campos_now:
        setattr(objeto, nombre, actualizado or creado)
    objeto.clean_fields(exclude=REFERENCIAS_FK[modelo])
    return objeto


def insertar_lote(modelo, objetos, *, batch_size=1000):
    if not objetos:
        return []
    return modelo.objects.bulk_create(objetos, batch_size=batch_size)


class Command(BaseCommand):
    help = "Importa usuarios, oferta, contrataciones, agenda (histórica y futura vigente) y caja de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, default=20261125)
        parser.add_argument("--salida", type=Path, default=Path("output/semilla"))
        parser.add_argument(
            "--omitir-si-hay-datos",
            action="store_true",
            help="Conserva una base con datos y omite la importación sin interrumpir el arranque.",
        )

    def handle(self, *args, **opciones):
        self.azar = random.Random(opciones["semilla"])
        self.ahora = timezone.localtime()
        self.hoy = self.ahora.date()
        self.mes_actual = self.hoy.replace(day=1)
        if self.mes_actual <= FECHA_INICIO_OPERACIONES:
            raise CommandError("Se necesita al menos un mes anterior dentro del calendario operativo.")
        self.fin_mes_actual = ultimo_dia_mes(self.mes_actual)
        self.ultimo_dia_caja = self.hoy - timedelta(days=1)
        self.hasta_reservas = min(self.fin_mes_actual, self.hoy + timedelta(days=3))

        self.meses = []
        mes = FECHA_INICIO_OPERACIONES
        while mes <= self.mes_actual:
            self.meses.append(mes)
            mes = mes_siguiente(mes)

        self.pagos = defaultdict(list)
        self.egresos_operativos = defaultdict(list)
        self.ingresos_otros = defaultdict(list)
        self.ajustes_pendientes = []
        self.ocupacion = set()
        self.personas_ocupadas = defaultdict(set)
        self.usos_organizador = Counter()
        self.usos_invitado = Counter()
        self.reservas_diarias = Counter()
        self.reservas_programadas_organizador = Counter()
        self.cantidades = Counter()

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734021, 2)")
                cursor.execute(
                    "LOCK TABLE usuarios, planes, membresias, eventos, "
                    "planes_usuarios, membresias_usuarios, sesiones_caja IN SHARE ROW EXCLUSIVE MODE"
                )
            if (
                Usuario.objects.count() != 1
                or Plan.objects.exists()
                or Evento.objects.exists()
                or PlanUsuario.objects.exists()
                or MembresiaUsuario.objects.exists()
                or SesionCaja.objects.exists()
                or Feriado.objects.exists()
                or Membresia.objects.count() != 1
            ):
                if opciones["omitir_si_hay_datos"]:
                    self.stdout.write("Demostración omitida: la base contiene datos. Se conservan sin modificaciones.")
                    return
                raise CommandError(
                    "La carga requiere la base inicial con un solo administrador y sin operaciones. "
                    "No borra ni duplica datos."
                )

            self.admin = Usuario.objects.get(roles__rol__codigo=Rol.ADMINISTRADOR)
            self.canchas = list(Cancha.objects.select_related("sede").order_by("pk"))
            if len(self.canchas) != 4 or len({c.sede_id for c in self.canchas}) != 2:
                raise CommandError("La demostración requiere las dos sedes iniciales con dos canchas cada una.")

            with contexto_auditoria(self.admin), fechas_explicitas(MODELOS_IMPORTADOS):
                self.crear_feriados()
                self.crear_oferta()
                self.crear_personas()
                self.crear_contrataciones()
                self.crear_agenda()
                self.programar_movimientos_operativos()
                self.crear_caja()

            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        opciones["salida"].mkdir(parents=True, exist_ok=True)
        resumen = self.resumen(opciones["semilla"])
        (opciones["salida"] / "resumen.txt").write_text(resumen, encoding="utf-8")
        (opciones["salida"] / "usuarios.txt").write_text(
            "Nombre | Usuario | Email | Celular | Perfil\n"
            + "\n".join(
                f"{u.get_full_name()} | {u.username} | {u.email} | {u.celular_contacto} | "
                f"{self._etiqueta_perfil(i, u)}"
                for i, u in enumerate(self.usuarios)
            )
            + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(resumen))

    def _etiqueta_perfil(self, indice, usuario):
        if indice < 6:
            return "Profesor"
        if usuario.pk in self.socios_ids_por_mes[self.mes_actual]:
            return "Socio activo"
        if usuario.pk in self.alumnos_ids_por_mes[self.mes_actual]:
            return "Alumno activo"
        return "Participante"

    def _momento_pasado_hoy(self, hora=9, minuto=0):
        objetivo = instante(self.hoy, hora, minuto)
        limite = self.ahora - timedelta(minutes=15)
        if objetivo <= limite:
            return objetivo
        inicio_dia = instante(self.hoy, 0, 5)
        return max(inicio_dia, limite)

    def crear_feriados(self):
        feriados = []
        creado = instante(FECHA_INICIO_OPERACIONES)
        for fecha, descripcion in (
            (date(2026, 8, 17), "Paso a la Inmortalidad del General José de San Martín"),
            (date(2026, 10, 12), "Día del Respeto a la Diversidad Cultural"),
        ):
            if fecha <= self.fin_mes_actual:
                feriados.append(preparar(Feriado(fecha=fecha, descripcion=descripcion), creado))
        insertar_lote(Feriado, feriados)
        self.feriados = {f.fecha for f in feriados}

    def crear_oferta(self):
        creado = instante(FECHA_INICIO_OPERACIONES - timedelta(days=1))
        planes = []
        for modalidad in ("grupal", "individual"):
            for numero, frecuencia in enumerate((1, 2, 3, 5), 1):
                planes.append(
                    preparar(
                        Plan(
                            nombre=f"Plan {modalidad} #{numero}",
                            modalidad=modalidad,
                            frecuencia_semanal=frecuencia,
                            cantidad_clases_por_encuentro=1,
                            precio_vigente=Decimal(200000 if numero == 4 else 50000 * frecuencia),
                            descripcion=(
                                f"{frecuencia} días por semana, un encuentro de una hora por día."
                                + (" Tarifa mensual de cinco días con descuento: $200.000." if numero == 4 else "")
                            ),
                        ),
                        creado,
                    )
                )
        self.planes = insertar_lote(Plan, planes)
        base = Membresia.objects.get(nombre="Socio 10 horas")
        if (base.horas_organizador, base.horas_invitado) != (10, 10):
            raise CommandError("La membresía inicial debe tener diez horas por rol.")
        ampliada = insertar_lote(
            Membresia,
            [
                preparar(
                    Membresia(
                        nombre="Socio 15 horas",
                        horas_organizador=15,
                        horas_invitado=15,
                        precio_vigente=Decimal(60000),
                        precio_invitado_vigente=base.precio_invitado_vigente,
                        descripcion=(
                            "Quince horas mensuales como organizador y quince como invitado. "
                            "Cupos independientes."
                        ),
                    ),
                    creado,
                )
            ],
        )[0]
        self.membresias = [base, ampliada]

    def crear_personas(self):
        self.roles = {r.codigo: r for r in Rol.objects.all()}
        base_creado = instante(FECHA_INICIO_OPERACIONES - timedelta(days=1), 8)
        apellidos = APELLIDOS[:90]
        workers = min(8, max(2, os.cpu_count() or 4))
        with ThreadPoolExecutor(max_workers=workers) as ejecutor:
            contrasenas = list(ejecutor.map(make_password, repeat("ulisesbatata", len(apellidos))))

        usuarios = []
        fechas_alta_usuario = []
        for indice, (apellido, contrasena) in enumerate(zip(apellidos, contrasenas)):
            nombre = NOMBRES[indice % len(NOMBRES)]
            correo = f"{normalizar(apellido)}{normalizar(nombre[0])}@gmail.com"
            if indice < 78:
                # 6 profesores + 72 participantes con historial desde el inicio de operaciones.
                creado = base_creado
            elif indice < 82:
                # 4 socios que se incorporaron a fines del mes anterior para el mes actual.
                dias_antes = 4 - (indice - 78)
                fecha_alta = max(FECHA_INICIO_OPERACIONES, self.mes_actual - timedelta(days=dias_antes))
                creado = instante(fecha_alta, 10 + (indice % 5), 15)
            elif indice < 89:
                # 7 usuarios públicos/reservas registrados gradualmente en el último mes.
                desplazamiento = max(1, 24 - (indice - 82) * 3)
                fecha_alta = max(FECHA_INICIO_OPERACIONES, self.hoy - timedelta(days=desplazamiento))
                creado = instante(fecha_alta, 9 + (indice % 6), 20)
            else:
                # 1 usuario registrado hoy para reflejar actividad reciente en el panel.
                creado = self._momento_pasado_hoy(9, 30)

            fechas_alta_usuario.append(creado)
            usuarios.append(
                preparar(
                    Usuario(
                        username=correo.removesuffix("@gmail.com"),
                        email=correo,
                        first_name=nombre,
                        last_name=apellido,
                        fecha_nacimiento=date(2000, 1, 1),
                        celular_contacto=validar_celular_ar(f"387500{indice + 1:04d}"),
                        password=contrasena,
                        date_joined=creado,
                        correo_verificado_en=creado,
                        verificacion_solicitada_en=creado,
                        observaciones="",
                    ),
                    creado,
                )
            )

        self.usuarios = insertar_lote(Usuario, usuarios)
        roles_lote = []
        for indice, (usuario, creado) in enumerate(zip(self.usuarios, fechas_alta_usuario)):
            codigos = (Rol.PUBLICO, Rol.RESERVAS) + ((Rol.PROFESOR,) if indice < 6 else ())
            for codigo in codigos:
                roles_lote.append(
                    preparar(
                        UsuarioRol(usuario=usuario, rol=self.roles[codigo], asignado_por=self.admin),
                        creado,
                    )
                )
        insertar_lote(UsuarioRol, roles_lote)

        self.profesores = self.usuarios[:6]
        self.alumnos = self.usuarios[6:]  # 84 participantes: [0..55] planes, [56..75] socios, [76..83] sin contrato
        self.pool_planes_usuarios = self.alumnos[:56]
        self.pool_socios_usuarios = self.alumnos[56:76]
        self.pool_sin_contrato = self.alumnos[76:]
        self.fecha_ingreso_usuario = {u.pk: u.date_joined.date() for u in self.usuarios}

    def _plan_para_usuario(self, indice_usuario, indice_mes):
        # 70 % grupales y 30 % individuales para reflejar la demanda real y equilibrar la ocupación diaria.
        pesos = (0, 0, 1, 1, 2, 2, 2, 3, 3, 4, 5, 6, 7)
        base = pesos[indice_usuario % len(pesos)]
        # Pequeña rotación de frecuencia en algunos alumnos entre meses.
        if indice_usuario % 11 == 0 and indice_mes > 0:
            if base < 4:
                base = (base + 1) % 4
            else:
                base = 4 + ((base - 4 + 1) % 4)
        return self.planes[base]

    def _seleccion_mensual(self, pool, cantidad, indice_mes, *, elegibles_desde=None):
        candidatos = [
            u for u in pool
            if elegibles_desde is None or self.fecha_ingreso_usuario[u.pk] <= elegibles_desde
        ]
        # Mantiene alta continuidad (~85 %) de un mes al siguiente y rota un porcentaje pequeño.
        nucleo = int(cantidad * 0.80)
        seleccion = list(candidatos[:nucleo])
        restantes = list(candidatos[nucleo:])
        rotador = random.Random(202600 + indice_mes * 37 + len(pool))
        rotador.shuffle(restantes)
        seleccion.extend(restantes[: max(0, cantidad - len(seleccion))])
        return seleccion

    def crear_contrataciones(self):
        self.planes_activos_por_mes = defaultdict(list)
        self.socios_activos_por_mes = defaultdict(list)
        self.alumnos_ids_por_mes = defaultdict(set)
        self.socios_ids_por_mes = defaultdict(set)
        self.membresia_por_usuario_mes = {}
        self.plan_por_usuario_mes = {}

        total_meses = len(self.meses)
        objetivo_planes = []
        objetivo_socios = []
        for i in range(total_meses):
            progreso = i / max(1, total_meses - 1)
            objetivo_planes.append(round(42 + 8 * progreso))  # 42 -> 45 -> 47 -> 50
            objetivo_socios.append(round(14 + 4 * progreso))  # 14 -> 15 -> 17 -> 18

        seleccion_planes_mes = {}
        seleccion_socios_mes = {}
        for i, mes in enumerate(self.meses):
            seleccion_planes_mes[mes] = self._seleccion_mensual(
                self.pool_planes_usuarios, objetivo_planes[i], i, elegibles_desde=mes,
            )
            seleccion_socios_mes[mes] = self._seleccion_mensual(
                self.pool_socios_usuarios, objetivo_socios[i], i, elegibles_desde=mes,
            )

        configuracion = obtener_configuracion()
        planes_lote = []
        membresias_lote = []
        primer_mes_alumno = {}
        planes_cancelados_info = []
        membresias_canceladas_info = []

        for i, mes in enumerate(self.meses):
            es_actual = mes == self.mes_actual
            estado_vigente = PlanUsuario.Estado.ACTIVO if es_actual else PlanUsuario.Estado.VENCIDO
            mes_prox = self.meses[i + 1] if i + 1 < total_meses else None
            apertura_enc, _ = ventana_continuidad(mes, configuracion)

            # 1) Planes vigentes del mes.
            activos_planes = seleccion_planes_mes[mes]
            ids_activos_prox = {u.pk for u in seleccion_planes_mes[mes_prox]} if mes_prox else set()
            for pos, usuario in enumerate(activos_planes):
                idx_u = self.pool_planes_usuarios.index(usuario)
                plan = self._plan_para_usuario(idx_u, i)
                fecha_alta = mes + timedelta(days=min(pos % 3, 2))
                creado = instante(fecha_alta, 8 + (pos % 4), (pos * 7) % 60)
                respuesta, respondida_en = self._respuesta_continuidad(
                    mes, es_actual, pos, usuario.pk in ids_activos_prox, apertura_enc,
                )
                contrato = preparar(
                    PlanUsuario(
                        usuario=usuario,
                        plan=plan,
                        mes_cubierto=mes,
                        fecha_alta=fecha_alta,
                        precio_aplicado=plan.precio_vigente,
                        registrado_por=self.admin,
                        observaciones="",
                        estado=estado_vigente,
                        respuesta_continuidad=respuesta,
                        continuidad_respondida_en=respondida_en,
                    ),
                    creado,
                    respondida_en or creado,
                )
                planes_lote.append((contrato, False, pos))
                primer_mes_alumno.setdefault(usuario.pk, creado)

            # 2) Planes anulados (1 por mes histórico, 2 en el mes actual) con devolución total.
            no_activos_planes = [
                u for u in self.pool_planes_usuarios
                if u not in activos_planes and self.fecha_ingreso_usuario[u.pk] <= mes
            ]
            cant_anulados_plan = 2 if es_actual else 1
            for k, usuario in enumerate(no_activos_planes[:cant_anulados_plan]):
                idx_u = self.pool_planes_usuarios.index(usuario)
                plan = self._plan_para_usuario(idx_u, i)
                fecha_alta = mes + timedelta(days=1 + k)
                fecha_anul = min(self.ultimo_dia_caja, fecha_alta + timedelta(days=3 + k))
                creado = instante(fecha_alta, 9, 15 + k * 10)
                anulado_en = instante(fecha_anul, 11, 20 + k * 10)
                contrato = preparar(
                    PlanUsuario(
                        usuario=usuario,
                        plan=plan,
                        mes_cubierto=mes,
                        fecha_alta=fecha_alta,
                        precio_aplicado=plan.precio_vigente,
                        registrado_por=self.admin,
                        observaciones="",
                        estado=PlanUsuario.Estado.ANULADO,
                        anulado_por=self.admin,
                        anulado_en=anulado_en,
                        motivo_anulacion=MOTIVOS_ANULACION_CONTRATO[(i + k) % len(MOTIVOS_ANULACION_CONTRATO)],
                    ),
                    creado,
                    anulado_en,
                )
                planes_lote.append((contrato, True, k))
                planes_cancelados_info.append((contrato, fecha_alta, fecha_anul))

            # 3) Membresías vigentes del mes.
            activos_socios = seleccion_socios_mes[mes]
            ids_socios_prox = {u.pk for u in seleccion_socios_mes[mes_prox]} if mes_prox else set()
            for pos, usuario in enumerate(activos_socios):
                idx_u = self.pool_socios_usuarios.index(usuario)
                membresia = self.membresias[(idx_u + i // 2) % 2]
                fecha_alta = mes + timedelta(days=min(pos % 3, 2))
                creado = instante(fecha_alta, 9 + (pos % 4), (pos * 11) % 60)
                respuesta, respondida_en = self._respuesta_continuidad(
                    mes, es_actual, pos, usuario.pk in ids_socios_prox, apertura_enc,
                )
                contrato = preparar(
                    MembresiaUsuario(
                        usuario=usuario,
                        membresia=membresia,
                        mes_cubierto=mes,
                        fecha_alta=fecha_alta,
                        precio_aplicado=membresia.precio_vigente,
                        horas_organizador_aplicadas=membresia.horas_organizador,
                        horas_invitado_aplicadas=membresia.horas_invitado,
                        registrado_por=self.admin,
                        observaciones="",
                        estado=estado_vigente,
                        respuesta_continuidad=respuesta,
                        continuidad_respondida_en=respondida_en,
                    ),
                    creado,
                    respondida_en or creado,
                )
                membresias_lote.append((contrato, False, pos))

            # 4) Membresías anuladas (en meses pares y en el mes actual) con devolución total.
            no_activos_socios = [
                u for u in self.pool_socios_usuarios
                if u not in activos_socios and self.fecha_ingreso_usuario[u.pk] <= mes
            ]
            if (es_actual or i % 2 == 0) and no_activos_socios:
                usuario = no_activos_socios[0]
                membresia = self.membresias[i % 2]
                fecha_alta = mes + timedelta(days=2)
                fecha_anul = min(self.ultimo_dia_caja, fecha_alta + timedelta(days=4))
                creado = instante(fecha_alta, 10, 10)
                anulado_en = instante(fecha_anul, 12, 5)
                contrato = preparar(
                    MembresiaUsuario(
                        usuario=usuario,
                        membresia=membresia,
                        mes_cubierto=mes,
                        fecha_alta=fecha_alta,
                        precio_aplicado=membresia.precio_vigente,
                        horas_organizador_aplicadas=membresia.horas_organizador,
                        horas_invitado_aplicadas=membresia.horas_invitado,
                        registrado_por=self.admin,
                        observaciones="",
                        estado=MembresiaUsuario.Estado.ANULADO,
                        anulado_por=self.admin,
                        anulado_en=anulado_en,
                        motivo_anulacion=MOTIVOS_ANULACION_CONTRATO[(i + 2) % len(MOTIVOS_ANULACION_CONTRATO)],
                    ),
                    creado,
                    anulado_en,
                )
                membresias_lote.append((contrato, True, 0))
                membresias_canceladas_info.append((contrato, fecha_alta, fecha_anul))

        insertar_lote(PlanUsuario, [item[0] for item in planes_lote])
        insertar_lote(MembresiaUsuario, [item[0] for item in membresias_lote])

        # Asigna rol Alumno a todos los usuarios que contrataron al menos un plan vigente.
        roles_alumno = [
            preparar(
                UsuarioRol(usuario_id=uid, rol=self.roles[Rol.ALUMNO], asignado_por=self.admin),
                creado,
            )
            for uid, creado in sorted(primer_mes_alumno.items())
        ]
        insertar_lote(UsuarioRol, roles_alumno)

        # Indexa pools activos mes a mes y agenda sus pagos y devoluciones.
        for contrato, anulado, pos in planes_lote:
            if anulado:
                self.cantidades["contrataciones_plan_anuladas"] += 1
                continue
            self.planes_activos_por_mes[contrato.mes_cubierto].append(contrato)
            self.alumnos_ids_por_mes[contrato.mes_cubierto].add(contrato.usuario_id)
            self.plan_por_usuario_mes[(contrato.usuario_id, contrato.mes_cubierto)] = contrato
            self.cantidades["contrataciones_plan"] += 1
            self._agendar_cobro_contratacion("plan", contrato, pos)

        for contrato, anulado, pos in membresias_lote:
            if anulado:
                self.cantidades["contrataciones_membresia_anuladas"] += 1
                continue
            self.socios_activos_por_mes[contrato.mes_cubierto].append(contrato)
            self.socios_ids_por_mes[contrato.mes_cubierto].add(contrato.usuario_id)
            self.membresia_por_usuario_mes[(contrato.usuario_id, contrato.mes_cubierto)] = contrato
            self.cantidades["contrataciones_membresia"] += 1
            self._agendar_cobro_contratacion("membresia", contrato, pos)

        # Cobros originales y devoluciones totales de contrataciones anuladas.
        for tipo, listado in (("plan", planes_cancelados_info), ("membresia", membresias_canceladas_info)):
            etiqueta = "plan" if tipo == "plan" else "membresía"
            for contrato, fecha_alta, fecha_anul in listado:
                self.agendar_pago(
                    fecha_alta,
                    contrato.precio_aplicado,
                    tipo,
                    contrato,
                    concepto=f"Pago total de {etiqueta}",
                )
                self.agendar_pago(
                    fecha_anul,
                    contrato.precio_aplicado,
                    tipo,
                    contrato,
                    concepto=f"Devolución total por anulación de {etiqueta}",
                    devolucion=True,
                )

    def _respuesta_continuidad(self, mes, es_actual, pos, continua_prox, apertura):
        if es_actual:
            # Deja la mayoría pendiente para mostrar la encuesta abierta en el portal.
            if pos % 7 != 0:
                return "", None
            momento = self._momento_pasado_hoy(9, 15 + (pos % 40))
            if momento < apertura:
                return "", None
            respuesta = self.azar.choices(
                (
                    RespuestaContinuidad.CONTINUAR,
                    RespuestaContinuidad.CAMBIAR,
                    RespuestaContinuidad.INDECISO,
                ),
                (70, 20, 10),
            )[0]
            return respuesta, momento

        if pos % 4 == 3:
            return "", None
        dia_resp = min(ultimo_dia_mes(mes).day, 26 + (pos % 3))
        momento = instante(mes.replace(day=dia_resp), 10 + (pos % 8), (pos * 13) % 60)
        if continua_prox:
            respuesta = RespuestaContinuidad.CAMBIAR if pos % 9 == 0 else RespuestaContinuidad.CONTINUAR
        else:
            respuesta = RespuestaContinuidad.NO_CONTINUAR if pos % 2 == 0 else RespuestaContinuidad.INDECISO
        return respuesta, momento

    def _agendar_cobro_contratacion(self, tipo, contrato, pos):
        etiqueta = "plan" if tipo == "plan" else "membresía"
        mes = contrato.mes_cubierto
        es_actual = mes == self.mes_actual
        importe = contrato.precio_aplicado
        fecha_pago = min(self.ultimo_dia_caja, contrato.fecha_alta + timedelta(days=pos % 4))

        if not es_actual:
            # Meses históricos: 100 % cubiertos (1 pago o 2 cuotas que suman el total exacto).
            if pos % 7 == 0:
                mitad = (importe / 2).quantize(Decimal("0.01"))
                saldo = importe - mitad
                fecha_saldo = min(self.ultimo_dia_caja, fecha_pago + timedelta(days=7))
                self.agendar_pago(fecha_pago, mitad, tipo, contrato, concepto=f"Primera cuota de {etiqueta}")
                self.agendar_pago(fecha_saldo, saldo, tipo, contrato, concepto=f"Saldo final de {etiqueta}")
            else:
                self.agendar_pago(fecha_pago, importe, tipo, contrato, concepto=f"Pago total de {etiqueta}")
            return

        # Mes actual (noviembre): gran mayoría cubiertos; solo pocos casos especiales para demostración.
        if tipo == "plan" and pos in (46, 47, 48):
            parcial = (importe * Decimal("0.60")).quantize(Decimal("0.01"))
            self.agendar_pago(fecha_pago, parcial, tipo, contrato, concepto=f"Pago parcial de {etiqueta}")
            self.cantidades["suscripciones_pago_parcial"] += 1
            return

        if tipo == "membresia" and pos == 17:
            parcial = (importe * Decimal("0.60")).quantize(Decimal("0.01"))
            self.agendar_pago(fecha_pago, parcial, tipo, contrato, concepto=f"Pago parcial de {etiqueta}")
            self.cantidades["suscripciones_pago_parcial"] += 1
            return

        if tipo == "plan" and pos == 45 and importe >= Decimal("50000.00"):
            # Un único ajuste de importe por bonificación, luego cubierto por completo.
            nuevo_importe = importe - Decimal("10000.00")
            fecha_ajuste = min(self.ultimo_dia_caja, mes + timedelta(days=5))
            self.ajustes_pendientes.append(
                preparar(
                    AjusteImporte(
                        operacion_id=uuid4(),
                        plan_usuario=contrato,
                        importe_anterior=importe,
                        importe_nuevo=nuevo_importe,
                        motivo="Bonificación por incorporación con el mes iniciado",
                        registrado_por=self.admin,
                    ),
                    instante(fecha_ajuste, 10, 0),
                )
            )
            self.agendar_pago(fecha_ajuste, nuevo_importe, tipo, contrato, concepto=f"Pago total de {etiqueta}")
            self.cantidades["ajustes_importe"] += 1
            return

        if tipo == "plan" and pos == 44:
            # Un único caso de excedente ya devuelto para mostrar el flujo completo sin ensuciar pendientes.
            excedente = Decimal("5000.00")
            fecha_dev = min(self.ultimo_dia_caja, fecha_pago + timedelta(days=2))
            self.agendar_pago(
                fecha_pago,
                importe + excedente,
                tipo,
                contrato,
                concepto=f"Pago de {etiqueta} con excedente",
                motivo_excedente="El titular transfirió un monto superior al saldo vigente.",
                medio_forzado="transferencia",
            )
            self.agendar_pago(
                fecha_dev,
                excedente,
                tipo,
                contrato,
                concepto=f"Devolución de excedente de {etiqueta}",
                devolucion=True,
            )
            self.cantidades["cobros_con_excedente"] += 1
            return

        if pos % 8 == 0:
            mitad = (importe / 2).quantize(Decimal("0.01"))
            saldo = importe - mitad
            fecha_saldo = min(self.ultimo_dia_caja, fecha_pago + timedelta(days=7))
            self.agendar_pago(fecha_pago, mitad, tipo, contrato, concepto=f"Primera cuota de {etiqueta}")
            self.agendar_pago(fecha_saldo, saldo, tipo, contrato, concepto=f"Saldo final de {etiqueta}")
        else:
            self.agendar_pago(fecha_pago, importe, tipo, contrato, concepto=f"Pago total de {etiqueta}")

    def agendar_pago(
        self,
        fecha,
        monto,
        tipo,
        origen,
        *,
        concepto,
        devolucion=False,
        motivo_excedente="",
        medio_forzado=None,
        hora_exacta=None,
    ):
        monto = Decimal(monto).quantize(Decimal("0.01"))
        if monto <= 0 or fecha > self.ultimo_dia_caja:
            return
        self.pagos[fecha].append(
            dict(
                monto=monto,
                tipo=tipo,
                origen=origen,
                concepto=concepto,
                devolucion=devolucion,
                motivo_excedente=motivo_excedente,
                medio_forzado=medio_forzado,
                hora_exacta=hora_exacta,
            )
        )

    def obtener_turno(self, cancha, fecha, hora):
        clave = (fecha, hora, cancha.pk)
        turno = self.turnos.get(clave)
        if turno is None:
            creado = min(instante(fecha, 7, 0), self.ahora - timedelta(minutes=30))
            turno = preparar(Turno(cancha=cancha, fecha=fecha, hora_inicio=time(hora)), creado)
            self.turnos[clave] = turno
            self.turnos_nuevos.append(turno)
        return turno

    def preparar_evento(
        self,
        cancha,
        fecha,
        hora,
        tipo,
        *,
        estado,
        creado,
        anulado_por=None,
        anulado_en=None,
        motivo="",
    ):
        hora_inicio = time(hora)
        if not self.horarios[cancha.sede_id][fecha].contiene(hora_inicio, time(hora + 1)):
            raise CommandError(
                f"El turno del {fecha} a las {hora_inicio:%H:%M} está fuera del horario de {cancha.sede}."
            )
        clave = (fecha, hora, cancha.pk)
        if estado != Evento.Estado.ANULADO and clave in self.ocupacion:
            raise CommandError(f"Turno repetido en la carga: {clave}.")
        turno = self.obtener_turno(cancha, fecha, hora)
        inicio = instante(fecha, hora)
        fin = inicio + timedelta(hours=1)

        datos = dict(
            turno=turno,
            tipo=tipo,
            registrado_por=self.admin,
            observaciones="",
            estado=estado,
        )
        if estado == Evento.Estado.ANULADO:
            anulado_en = anulado_en or (inicio - timedelta(hours=2))
            datos.update(
                anulado_por=anulado_por or self.admin,
                anulado_en=anulado_en,
                motivo_anulacion=motivo,
            )
            actualizado = anulado_en
        elif estado == Evento.Estado.FINALIZADO:
            datos["finalizado_en"] = fin
            self.ocupacion.add(clave)
            actualizado = fin
        else:
            self.ocupacion.add(clave)
            actualizado = creado

        evento = preparar(Evento(**datos), creado, actualizado)
        self.eventos_lote.append(evento)
        return evento

    def buscar_turno(self, fecha, personas, *, preferencia=0):
        for hora in HORAS:
            if not personas.isdisjoint(self.personas_ocupadas[(fecha, hora)]):
                continue
            for desplazamiento in range(4):
                cancha = self.canchas[(preferencia + desplazamiento) % 4]
                if (fecha, hora, cancha.pk) not in self.ocupacion:
                    return cancha, hora
        return None

    def planificar_bloqueos(self, fecha):
        if fecha >= self.hoy:
            return
        indice_mes = self.meses.index(fecha.replace(day=1))
        clima = fecha.weekday() == 5 and 7 <= fecha.day <= 13
        if clima:
            for cancha in self.canchas:
                for hora in (17, 18, 19):
                    creado = instante(fecha, 7, 30)
                    evento = self.preparar_evento(
                        cancha, fecha, hora, Evento.Tipo.BLOQUEO,
                        estado=Evento.Estado.FINALIZADO, creado=creado,
                    )
                    self.bloqueos_pendientes.append((evento, Bloqueo.Motivo.CLIMA_ADVERSO))
                    self.cantidades["bloqueos"] += 1
        if fecha.day == 22:
            cancha = self.canchas[indice_mes % 4]
            for hora in (12, 13):
                creado = instante(fecha, 7, 30)
                evento = self.preparar_evento(
                    cancha, fecha, hora, Evento.Tipo.BLOQUEO,
                    estado=Evento.Estado.FINALIZADO, creado=creado,
                )
                self.bloqueos_pendientes.append((evento, Bloqueo.Motivo.MANTENIMIENTO))
                self.cantidades["bloqueos"] += 1

    def planificar_clases(self, fecha):
        if fecha in self.feriados or fecha.weekday() >= 5:
            return
        mes = fecha.replace(day=1)
        grupos = defaultdict(list)
        # Pool estricto del mes: solo usuarios con plan vigente (no anulado) en ese mes.
        for contrato in self.planes_activos_por_mes[mes]:
            if fecha.weekday() in DIAS_PLAN[contrato.plan.frecuencia_semanal]:
                grupos[contrato.plan_id].append(contrato)

        numero_grupo = 0
        for contratos in grupos.values():
            tamano = 4 if contratos[0].plan.modalidad == Plan.Modalidad.GRUPAL else 1
            for inicio_idx in range(0, len(contratos), tamano):
                participantes = [c.usuario for c in contratos[inicio_idx : inicio_idx + tamano]]
                profesor = self.profesores[numero_grupo % len(self.profesores)]
                personas = {u.pk for u in participantes} | {profesor.pk}
                turno = self.buscar_turno(fecha, personas, preferencia=numero_grupo % 4)
                numero_grupo += 1
                if turno is None:
                    raise CommandError(f"No hay capacidad para las clases del {fecha}.")
                cancha, hora = turno
                inicio_dt = instante(fecha, hora)
                fin_dt = inicio_dt + timedelta(hours=1)
                es_pasada = fin_dt <= self.ahora

                anulado = es_pasada and self.azar.random() < 0.022
                if anulado:
                    estado = Evento.Estado.ANULADO
                    creado = min(instante(mes, 8, 0), inicio_dt - timedelta(hours=4))
                    anulado_en = inicio_dt - timedelta(hours=2)
                    motivo = self.azar.choice(MOTIVOS_ANULACION_CLASE)
                elif es_pasada:
                    estado = Evento.Estado.FINALIZADO
                    creado = min(instante(mes, 8, 0), inicio_dt - timedelta(hours=2))
                    anulado_en = None
                    motivo = ""
                else:
                    estado = Evento.Estado.PROGRAMADO
                    creado = min(instante(mes, 8, 0), self.ahora - timedelta(hours=1))
                    anulado_en = None
                    motivo = ""

                evento = self.preparar_evento(
                    cancha,
                    fecha,
                    hora,
                    Evento.Tipo.CLASE,
                    estado=estado,
                    creado=creado,
                    anulado_en=anulado_en,
                    motivo=motivo,
                )

                alumnos_info = []
                personas_ocupantes = {profesor.pk}
                clase_sin_asistencia = (
                    estado == Evento.Estado.FINALIZADO
                    and fecha >= self.hoy - timedelta(days=2)
                    and self.cantidades["clases_sin_asistencia"] < 4
                    and self.azar.random() < 0.12
                )
                if clase_sin_asistencia:
                    self.cantidades["clases_sin_asistencia"] += 1

                for alumno in participantes:
                    aviso_ausencia = (
                        estado == Evento.Estado.PROGRAMADO
                        and inicio_dt > self.ahora
                        and self.azar.random() < 0.05
                    )
                    if not aviso_ausencia:
                        personas_ocupantes.add(alumno.pk)

                    asistencia_estado = None
                    if estado == Evento.Estado.FINALIZADO:
                        if clase_sin_asistencia:
                            asistencia_estado = Asistencia.Estado.SIN_REGISTRAR
                        else:
                            prob = min(0.92, 0.80 + 0.03 * self.meses.index(mes))
                            asistencia_estado = (
                                Asistencia.Estado.PRESENTE
                                if self.azar.random() < prob
                                else Asistencia.Estado.AUSENTE
                            )
                    alumnos_info.append((alumno, aviso_ausencia, asistencia_estado))

                if estado != Evento.Estado.ANULADO:
                    self.personas_ocupadas[(fecha, hora)].update(personas_ocupantes)

                self.clases_pendientes.append((evento, profesor, alumnos_info))
                self.cantidades[f"clases_{estado}"] += 1

    def planificar_reservas(self, fecha):
        # Respeta el horizonte máximo de 3 días de anticipación para reservas.
        if fecha > self.hasta_reservas:
            return
        mes = fecha.replace(day=1)
        socios_mes = self.socios_activos_por_mes[mes]
        es_finde = fecha.weekday() >= 5
        if fecha > self.hoy:
            cantidad_objetivo = 8 if es_finde else 6
        else:
            cantidad_objetivo = (8 if es_finde else 4) + (1 if mes == self.mes_actual else 0)

        elegibles_normales = [
            u for u in self.alumnos
            if self.fecha_ingreso_usuario[u.pk] <= fecha
            and u.pk not in self.socios_ids_por_mes[mes]
        ]
        elegibles_invitados = [
            u for u in self.alumnos if self.fecha_ingreso_usuario[u.pk] <= fecha
        ]

        for numero in range(cantidad_objetivo):
            # Alterna reservas de socios (~55 %) y reservas normales (~45 %).
            preferir_socio = (numero % 11) in (0, 2, 4, 6, 8, 10)
            organizador = None
            contrato_org = None
            con_membresia = False

            # Determina primero un turno disponible aproximado buscando candidato válido.
            if preferir_socio and socios_mes:
                candidatos_socios = [
                    c for c in socios_mes
                    if self.usos_organizador[(c.usuario_id, mes)] < c.horas_organizador_aplicadas
                    and self.reservas_diarias[(fecha, c.usuario_id)] < 2
                ]
                self.azar.shuffle(candidatos_socios)
                for contrato in candidatos_socios:
                    turno = self._buscar_turno_reserva(fecha, contrato.usuario_id, numero)
                    if turno is not None:
                        cancha, hora, es_pasada = turno
                        if not es_pasada and self.reservas_programadas_organizador[contrato.usuario_id] >= 2:
                            continue
                        organizador = contrato.usuario
                        contrato_org = contrato
                        con_membresia = True
                        break

            if organizador is None:
                candidatos_normales = [
                    u for u in elegibles_normales
                    if self.reservas_diarias[(fecha, u.pk)] < 2
                ]
                self.azar.shuffle(candidatos_normales)
                for candidato in candidatos_normales:
                    turno = self._buscar_turno_reserva(fecha, candidato.pk, numero)
                    if turno is not None:
                        cancha, hora, es_pasada = turno
                        if not es_pasada and self.reservas_programadas_organizador[candidato.pk] >= 2:
                            continue
                        organizador = candidato
                        break

            if organizador is None:
                continue

            inicio_dt = instante(fecha, hora)
            fin_dt = inicio_dt + timedelta(hours=1)
            es_pasada = fin_dt <= self.ahora

            anulado = es_pasada and fecha <= self.ultimo_dia_caja and self.azar.random() < 0.035
            if anulado:
                estado = Evento.Estado.ANULADO
                cancelacion_tardia = self.azar.random() < 0.30
                anulado_en = inicio_dt - timedelta(minutes=30 if cancelacion_tardia else 240)
                creado = min(instante(fecha, 7, 15), anulado_en - timedelta(minutes=30))
                motivo = self.azar.choice(MOTIVOS_ANULACION_RESERVA)
                anulado_por = organizador
                computa_hora = con_membresia and cancelacion_tardia
            elif es_pasada:
                estado = Evento.Estado.FINALIZADO
                if fecha == self.hoy:
                    # Reservas de hoy se crearon ayer para poder tener cobro coherente previo o quedar pendientes.
                    creado = instante(self.ultimo_dia_caja, 11 + (numero % 6), 15)
                else:
                    creado = instante(fecha, 7, 15)
                anulado_en = None
                motivo = ""
                anulado_por = None
                computa_hora = con_membresia
            else:
                estado = Evento.Estado.PROGRAMADO
                # Reservas futuras creadas respetando los 3 días de anticipación.
                puede_ayer = (fecha - self.ultimo_dia_caja).days <= 3
                creada_ayer = puede_ayer and (numero % 3 == 0)
                creado = (
                    instante(self.ultimo_dia_caja, 14 + (numero % 5), 20)
                    if creada_ayer
                    else self._momento_pasado_hoy(8 + (numero % 3), 10 + (numero * 7) % 45)
                )
                anulado_en = None
                motivo = ""
                anulado_por = None
                computa_hora = con_membresia

            evento = self.preparar_evento(
                cancha,
                fecha,
                hora,
                Evento.Tipo.RESERVA,
                estado=estado,
                creado=creado,
                anulado_por=anulado_por,
                anulado_en=anulado_en,
                motivo=motivo,
            )

            self.reservas_diarias[(fecha, organizador.pk)] += 1
            if estado == Evento.Estado.PROGRAMADO:
                self.reservas_programadas_organizador[organizador.pk] += 1
            if computa_hora:
                self.usos_organizador[(organizador.pk, mes)] += 1

            # Resultado de uso (solo en reservas finalizadas con membresía).
            resultado_uso = "sin_registrar"
            resultado_por = None
            resultado_en = None
            if con_membresia and estado == Evento.Estado.FINALIZADO:
                dejar_pendiente = (
                    fecha >= self.hoy - timedelta(days=1)
                    and self.cantidades["reservas_sin_resultado"] < 3
                )
                if dejar_pendiente:
                    self.cantidades["reservas_sin_resultado"] += 1
                else:
                    resultado_uso = "no_realizada" if self.azar.random() < 0.05 else "realizada"
                    resultado_por = self.admin
                    resultado_en = min(self.ahora - timedelta(minutes=5), fin_dt + timedelta(minutes=10))

            # Selección de invitados (mezcla de socios y no socios del mes).
            personas_ocupantes = {organizador.pk}
            pool_inv = [
                u for u in elegibles_invitados
                if u.pk != organizador.pk and u.pk not in self.personas_ocupadas[(fecha, hora)]
            ]
            if con_membresia:
                socios_disp = [u for u in pool_inv if u.pk in self.socios_ids_por_mes[mes]]
                no_socios_disp = [u for u in pool_inv if u.pk not in self.socios_ids_por_mes[mes]]
                self.azar.shuffle(socios_disp)
                self.azar.shuffle(no_socios_disp)
                cant_inv = self.azar.choice((1, 2, 2, 3))
                invitados_elegidos = []
                for idx_inv in range(cant_inv):
                    if idx_inv % 2 == 0 and socios_disp:
                        invitados_elegidos.append(socios_disp.pop())
                    elif no_socios_disp:
                        invitados_elegidos.append(no_socios_disp.pop())
                    elif socios_disp:
                        invitados_elegidos.append(socios_disp.pop())
            else:
                self.azar.shuffle(pool_inv)
                invitados_elegidos = pool_inv[: self.azar.choice((1, 2, 3))]

            invitados_info = []
            adicionales_count = 0
            for idx_inv, invitado in enumerate(invitados_elegidos):
                if estado == Evento.Estado.PROGRAMADO:
                    respuesta = self.azar.choices(
                        (
                            ReservaInvitado.Respuesta.AFIRMATIVA,
                            ReservaInvitado.Respuesta.PENDIENTE,
                            ReservaInvitado.Respuesta.NEGATIVA,
                        ),
                        (60, 32, 8),
                    )[0]
                else:
                    respuesta = self.azar.choices(
                        (
                            ReservaInvitado.Respuesta.AFIRMATIVA,
                            ReservaInvitado.Respuesta.NEGATIVA,
                            ReservaInvitado.Respuesta.PENDIENTE,
                        ),
                        (88, 9, 3),
                    )[0]

                condicion = "sin_aplicar"
                membresia_inv = None
                respondido_por = None
                respondido_en = None
                if respuesta != ReservaInvitado.Respuesta.PENDIENTE:
                    respondido_por = invitado
                    resp_dt = creado + timedelta(minutes=15 + idx_inv * 5)
                    limite_resp = min(inicio_dt - timedelta(minutes=5), self.ahora - timedelta(minutes=5))
                    respondido_en = min(resp_dt, limite_resp)
                    if respondido_en < creado:
                        respondido_en = creado

                if respuesta == ReservaInvitado.Respuesta.AFIRMATIVA:
                    personas_ocupantes.add(invitado.pk)
                    if not con_membresia:
                        condicion = "reserva_normal"
                    else:
                        cobertura = self.membresia_por_usuario_mes.get((invitado.pk, mes))
                        if cobertura is not None:
                            membresia_inv = cobertura
                            if self.usos_invitado[(invitado.pk, mes)] < cobertura.horas_invitado_aplicadas:
                                condicion = "socio"
                                if estado != Evento.Estado.ANULADO:
                                    self.usos_invitado[(invitado.pk, mes)] += 1
                            else:
                                condicion = "cupo_agotado"
                                adicionales_count += 1
                        else:
                            condicion = "no_socio"
                            adicionales_count += 1

                invitados_info.append((invitado, respuesta, condicion, membresia_inv, respondido_por, respondido_en))

            if estado != Evento.Estado.ANULADO:
                self.personas_ocupadas[(fecha, hora)].update(personas_ocupantes)

            precio_turno = None if con_membresia else cancha.sede.precio_reserva_vigente
            precio_invitado = contrato_org.membresia.precio_invitado_vigente if con_membresia else None
            total_reserva = (
                precio_turno if not con_membresia else precio_invitado * adicionales_count
            )

            self.reservas_pendientes.append(
                dict(
                    evento=evento,
                    organizador=organizador,
                    contrato=contrato_org if con_membresia else None,
                    precio_turno=precio_turno,
                    precio_invitado=precio_invitado,
                    computa_hora=computa_hora,
                    anulada_por_organizador=True if anulado else None,
                    resultado_uso=resultado_uso,
                    resultado_por=resultado_por,
                    resultado_en=resultado_en,
                    invitados=invitados_info,
                    fecha=fecha,
                    mes=mes,
                    total=total_reserva,
                    creado=creado,
                )
            )
            self.cantidades[f"reservas_{estado}"] += 1
            self.cantidades["reservas_membresia" if con_membresia else "reservas_normales"] += 1

    def _buscar_turno_reserva(self, fecha, usuario_id, preferencia):
        horas_orden = list(HORAS)
        if fecha >= self.hoy:
            # Distribuye las reservas de hoy y próximos días a lo largo de toda la jornada.
            desplazamiento = (preferencia + fecha.day) % len(horas_orden)
            horas_orden = horas_orden[desplazamiento:] + horas_orden[:desplazamiento]
        for hora in horas_orden:
            if usuario_id in self.personas_ocupadas[(fecha, hora)]:
                continue
            inicio_dt = instante(fecha, hora)
            fin_dt = inicio_dt + timedelta(hours=1)
            es_pasada = fin_dt <= self.ahora
            # Evita ubicar una reserva en el instante exacto ya iniciado sin finalizar si existe otra libre.
            if not es_pasada and inicio_dt <= self.ahora:
                continue
            for desp_cancha in range(4):
                cancha = self.canchas[(preferencia + desp_cancha) % 4]
                if (fecha, hora, cancha.pk) not in self.ocupacion:
                    return cancha, hora, es_pasada
        return None

    def crear_agenda(self):
        total_dias = (self.fin_mes_actual - FECHA_INICIO_OPERACIONES).days + 1
        fechas = [FECHA_INICIO_OPERACIONES + timedelta(days=dia) for dia in range(total_dias)]
        sedes = {cancha.sede_id: cancha.sede for cancha in self.canchas}
        self.horarios = {sede_id: horarios_efectivos(sede, fechas) for sede_id, sede in sedes.items()}
        self.turnos = {
            (t.fecha, t.hora_inicio.hour, t.cancha_id): t
            for t in Turno.objects.filter(
                cancha__in=self.canchas,
                fecha__gte=FECHA_INICIO_OPERACIONES,
                fecha__lte=self.fin_mes_actual,
            ).order_by()
        }
        self.turnos_nuevos = []
        self.eventos_lote = []
        self.bloqueos_pendientes = []
        self.clases_pendientes = []
        self.reservas_pendientes = []

        for fecha in fechas:
            self.planificar_bloqueos(fecha)
            self.planificar_clases(fecha)
            self.planificar_reservas(fecha)

        # Persistencia masiva ordenada por dependencias referenciales.
        insertar_lote(Turno, self.turnos_nuevos)
        for evento in self.eventos_lote:
            evento.turno_id = evento.turno.pk
        insertar_lote(Evento, self.eventos_lote)

        bloqueos = [
            preparar(Bloqueo(evento_id=evento.pk, motivo=motivo), evento.creado_en)
            for evento, motivo in self.bloqueos_pendientes
        ]
        insertar_lote(Bloqueo, bloqueos)

        clases = [
            preparar(
                Clase(
                    evento_id=evento.pk,
                    finalizado_por=profesor if evento.estado == Evento.Estado.FINALIZADO else None,
                ),
                evento.creado_en,
            )
            for evento, profesor, _ in self.clases_pendientes
        ]
        insertar_lote(Clase, clases)

        clases_profesores = []
        clases_alumnos = []
        asistencias = []
        for clase, (evento, profesor, alumnos_info) in zip(clases, self.clases_pendientes):
            clases_profesores.append(
                preparar(ClaseProfesor(clase_id=clase.pk, profesor_id=profesor.pk), evento.creado_en)
            )
            for alumno, aviso_ausencia, asistencia_estado in alumnos_info:
                if aviso_ausencia:
                    resp_en = self._momento_pasado_hoy(9, 0)
                    ca = ClaseAlumno(
                        clase_id=clase.pk,
                        usuario_id=alumno.pk,
                        respuesta=ClaseAlumno.Respuesta.NO_ASISTIRA,
                        respondido_por_id=alumno.pk,
                        respondido_en=resp_en,
                    )
                    clases_alumnos.append(preparar(ca, evento.creado_en, resp_en))
                else:
                    clases_alumnos.append(
                        preparar(ClaseAlumno(clase_id=clase.pk, usuario_id=alumno.pk), evento.creado_en)
                    )
                if asistencia_estado is not None:
                    sin_carga = asistencia_estado == Asistencia.Estado.SIN_REGISTRAR
                    reg_en = None if sin_carga else min(
                        self.ahora - timedelta(minutes=5), evento.finalizado_en + timedelta(minutes=5),
                    )
                    asistencias.append(
                        preparar(
                            Asistencia(
                                clase_id=clase.pk,
                                usuario_id=alumno.pk,
                                estado=asistencia_estado,
                                registrada_por_id=None if sin_carga else profesor.pk,
                                registrada_en=reg_en,
                            ),
                            reg_en or evento.finalizado_en,
                        )
                    )

        insertar_lote(ClaseProfesor, clases_profesores)
        insertar_lote(ClaseAlumno, clases_alumnos)
        insertar_lote(Asistencia, asistencias)

        reservas = []
        for item in self.reservas_pendientes:
            evento = item["evento"]
            reservas.append(
                preparar(
                    Reserva(
                        evento_id=evento.pk,
                        organizador_id=item["organizador"].pk,
                        membresia_usuario=item["contrato"],
                        precio_por_turno_aplicado=item["precio_turno"],
                        precio_invitado_aplicado=item["precio_invitado"],
                        computa_hora_membresia=item["computa_hora"],
                        anulada_por_organizador=item["anulada_por_organizador"],
                        resultado_uso=item["resultado_uso"],
                        resultado_registrado_por=item["resultado_por"],
                        resultado_registrado_en=item["resultado_en"],
                    ),
                    evento.creado_en,
                    evento.finalizado_en or evento.anulado_en or evento.creado_en,
                )
            )
        insertar_lote(Reserva, reservas)

        invitados_lote = []
        reservas_pendiente_nov = 0
        for reserva, item in zip(reservas, self.reservas_pendientes):
            evento = item["evento"]
            for invitado, respuesta, condicion, membresia_inv, resp_por, resp_en in item["invitados"]:
                invitados_lote.append(
                    preparar(
                        ReservaInvitado(
                            reserva_id=reserva.pk,
                            usuario_id=invitado.pk,
                            respuesta=respuesta,
                            condicion_aplicada=condicion,
                            membresia_usuario=membresia_inv,
                            respondido_por=resp_por,
                            respondido_en=resp_en,
                        ),
                        evento.creado_en,
                        resp_en or evento.creado_en,
                    )
                )

            total = item["total"]
            if total <= 0:
                continue

            fecha_turno = item["fecha"]
            creado_fecha = item["creado"].date()
            if evento.estado == Evento.Estado.ANULADO:
                fecha_cobro = min(self.ultimo_dia_caja, creado_fecha)
                fecha_dev = min(self.ultimo_dia_caja, evento.anulado_en.date())
                self.agendar_pago(
                    fecha_cobro, total, "reserva", reserva, concepto="Cobro de reserva",
                )
                self.agendar_pago(
                    fecha_dev,
                    total,
                    "reserva",
                    reserva,
                    concepto="Devolución total por cancelación de reserva",
                    devolucion=True,
                )
            elif fecha_turno <= self.ultimo_dia_caja:
                # Meses históricos 100 % cubiertos; en noviembre solo 2-3 reservas recientes quedan pendientes.
                dejar_pendiente = (
                    item["mes"] == self.mes_actual
                    and fecha_turno >= self.ultimo_dia_caja - timedelta(days=1)
                    and reservas_pendiente_nov < 3
                )
                if dejar_pendiente:
                    reservas_pendiente_nov += 1
                    continue
                self.agendar_pago(fecha_turno, total, "reserva", reserva, concepto="Cobro de reserva")
            elif creado_fecha <= self.ultimo_dia_caja:
                # Reservas de hoy/mañana creadas ayer: cobro adelantado en la caja de ayer.
                self.agendar_pago(
                    creado_fecha, total, "reserva", reserva, concepto="Cobro adelantado de reserva",
                )

        insertar_lote(ReservaInvitado, invitados_lote)

    def programar_movimientos_operativos(self):
        for mes in self.meses:
            es_actual = mes == self.mes_actual
            # Alquiler mensual de ambas sedes (día 5).
            for sede_nombre, destinatario, monto in (
                ("Sociedad Española", "Club Sociedad Española", Decimal("650000.00")),
                ("Sirio Libanesa", "Club Sirio Libanesa", Decimal("650000.00")),
            ):
                self._agendar_egreso(
                    mes.replace(day=5),
                    "alquiler",
                    f"Alquiler mensual sede {sede_nombre}",
                    monto,
                    destinatario,
                    medio="transferencia",
                )

            # Servicios básicos (días 10 a 12).
            for dia, concepto, destinatario, monto in (
                (10, "Servicio de energía eléctrica de sedes", "EDESA S.A.", Decimal("185000.00")),
                (11, "Servicio de agua corriente de sedes", "Aguas del Norte", Decimal("72000.00")),
                (12, "Servicio de internet y telefonía", "Personal Fibra", Decimal("64000.00")),
            ):
                self._agendar_egreso(mes.replace(day=dia), "servicios", concepto, monto, destinatario, medio="transferencia")

            # Insumos deportivos (días 8 y 18).
            self._agendar_egreso(
                mes.replace(day=8),
                "insumos",
                "Compra de cajones de pelotas de tenis y grips",
                Decimal("145000.00"),
                "Deportes Salta SRL",
                medio="transferencia",
            )
            self._agendar_egreso(
                mes.replace(day=18),
                "insumos",
                "Reposición de conos, flejes y botiquín",
                Decimal("32000.00"),
                "Deportes Salta SRL",
                medio="efectivo",
            )

            # Publicidad (día 15).
            self._agendar_egreso(
                mes.replace(day=15),
                "publicidad",
                "Campaña mensual en redes sociales",
                Decimal("115000.00"),
                "Meta Platforms",
                medio="tarjeta",
            )

            # Mantenimiento de canchas (día 22, alineado con el bloqueo de mantenimiento).
            self._agendar_egreso(
                mes.replace(day=22),
                "mantenimiento",
                "Acondicionamiento de polvo de ladrillo y líneas",
                Decimal("210000.00"),
                "Servicios Deportivos NOA",
                medio="transferencia",
            )

            # Honorarios docentes (día 28 en meses cerrados; adelanto quincenal el día 20 en noviembre).
            dia_docentes = 20 if es_actual else 28
            monto_docente = Decimal("170000.00") if es_actual else Decimal("340000.00")
            etiqueta_doc = "Adelanto de honorarios docentes" if es_actual else "Honorarios docentes mensuales"
            for profesor in self.profesores:
                self._agendar_egreso(
                    mes.replace(day=dia_docentes),
                    "profesores",
                    f"{etiqueta_doc} · {profesor.get_full_name()}",
                    monto_docente,
                    profesor.get_full_name(),
                    medio="transferencia",
                )

            # Ingresos menores varios (venta de tubos de pelotas / alquiler de raquetas).
            for dia, concepto, monto in (
                (6, "Venta de tubos de pelotas en recepción", Decimal("18000.00")),
                (14, "Alquiler de raquetas de demostración", Decimal("12000.00")),
                (21, "Venta de cubregrips y pelotas", Decimal("15000.00")),
            ):
                fecha_ing = mes.replace(day=dia)
                if fecha_ing <= self.ultimo_dia_caja:
                    self.ingresos_otros[fecha_ing].append(dict(concepto=concepto, monto=monto))

    def _agendar_egreso(self, fecha, categoria, concepto, monto, destinatario, *, medio):
        if fecha > self.ultimo_dia_caja:
            return
        self.egresos_operativos[fecha].append(
            dict(
                categoria=categoria,
                concepto=concepto,
                monto=monto.quantize(Decimal("0.01")),
                destinatario=destinatario,
                medio=medio,
            )
        )

    def crear_caja(self):
        # Registra ajustes de importe primero para mantener trazabilidad completa.
        insertar_lote(AjusteImporte, self.ajustes_pendientes)

        fechas_caja = sorted(
            {
                *self.pagos.keys(),
                *self.egresos_operativos.keys(),
                *self.ingresos_otros.keys(),
            }
        )
        fechas_caja = [f for f in fechas_caja if f <= self.ultimo_dia_caja]

        sesiones = []
        movimientos_lote = []
        efectivo_cierre_anterior = None

        for fecha in fechas_caja:
            apertura_dt = instante(fecha, 7, 30)
            cierre_dt = instante(fecha, 22, 0)

            if efectivo_cierre_anterior is None:
                efectivo_inicial = Decimal("50000.00")
                efectivo_anterior = None
                diferencia_apertura = None
            else:
                efectivo_anterior = efectivo_cierre_anterior
                efectivo_inicial = efectivo_anterior
                diferencia_apertura = Decimal("0.00")

            efectivo_actual = efectivo_inicial
            movs_dia = []
            secuencia = 0

            # 1) Ingresos y devoluciones vinculadas a contrataciones y reservas.
            for pago in self.pagos.get(fecha, ()):
                secuencia += 1
                origen = pago["origen"]
                tipo = pago["tipo"]
                devolucion = pago["devolucion"]
                if devolucion:
                    medio = "transferencia"
                elif pago["medio_forzado"]:
                    medio = pago["medio_forzado"]
                else:
                    medio = self.azar.choices(("efectivo", "transferencia", "qr", "tarjeta"), (22, 38, 28, 12))[0]

                campo = {"plan": "plan_usuario", "membresia": "membresia_usuario", "reserva": "reserva"}[tipo]
                titular = origen.organizador if tipo == "reserva" else origen.usuario
                creado = instante(fecha, 8 + ((secuencia * 3) % 11), (secuencia * 7) % 60)
                if devolucion and tipo == "reserva" and origen.evento.anulado_en is not None:
                    candidato = origen.evento.anulado_en + timedelta(minutes=10)
                    if apertura_dt < candidato < cierre_dt:
                        creado = candidato
                elif devolucion and tipo in ("plan", "membresia") and origen.anulado_en is not None:
                    candidato = origen.anulado_en + timedelta(minutes=10)
                    if apertura_dt < candidato < cierre_dt:
                        creado = candidato

                if medio == "efectivo":
                    efectivo_actual += -pago["monto"] if devolucion else pago["monto"]

                movs_dia.append(
                    preparar(
                        MovimientoFondo(
                            operacion_id=uuid4(),
                            clase="egreso" if devolucion else "ingreso",
                            concepto=pago["concepto"],
                            monto=pago["monto"],
                            medio_pago=medio,
                            referencia="" if medio == "efectivo" else f"OP-{fecha:%Y%m%d}-{secuencia:04d}",
                            categoria_ingreso="" if devolucion else {
                                "plan": "planes", "membresia": "membresias", "reserva": "reservas",
                            }[tipo],
                            categoria_egreso="devoluciones" if devolucion else "",
                            destinatario=titular.get_full_name() if devolucion else "",
                            motivo_excedente=pago["motivo_excedente"],
                            registrado_por=self.admin,
                            **{campo: origen},
                        ),
                        creado,
                    )
                )
                self.cantidades["devoluciones" if devolucion else "ingresos_vinculados"] += 1

            # 2) Ingresos varios (categoría Otros).
            for otro in self.ingresos_otros.get(fecha, ()):
                secuencia += 1
                efectivo_actual += otro["monto"]
                movs_dia.append(
                    preparar(
                        MovimientoFondo(
                            operacion_id=uuid4(),
                            clase="ingreso",
                            concepto=otro["concepto"],
                            monto=otro["monto"],
                            medio_pago="efectivo",
                            referencia="",
                            categoria_ingreso="otros",
                            categoria_egreso="",
                            destinatario="",
                            registrado_por=self.admin,
                        ),
                        instante(fecha, 15, (secuencia * 9) % 55),
                    )
                )
                self.cantidades["ingresos_otros"] += 1

            # 3) Egresos operativos.
            for egreso in self.egresos_operativos.get(fecha, ()):
                secuencia += 1
                medio = egreso["medio"]
                if medio == "efectivo":
                    # Solo paga gastos en efectivo si queda saldo cómodo en caja.
                    if efectivo_actual - egreso["monto"] >= Decimal("25000.00"):
                        efectivo_actual -= egreso["monto"]
                    else:
                        medio = "transferencia"
                movs_dia.append(
                    preparar(
                        MovimientoFondo(
                            operacion_id=uuid4(),
                            clase="egreso",
                            concepto=egreso["concepto"],
                            monto=egreso["monto"],
                            medio_pago=medio,
                            referencia="" if medio == "efectivo" else f"EGR-{fecha:%Y%m%d}-{secuencia:04d}",
                            categoria_ingreso="",
                            categoria_egreso=egreso["categoria"],
                            destinatario=egreso["destinatario"],
                            registrado_por=self.admin,
                        ),
                        instante(fecha, 17, (secuencia * 5) % 55),
                    )
                )
                self.cantidades["egresos_operativos"] += 1

            # 4) Retiro parcial de efectivo en múltiplos de $10.000 para mantener fondo de caja realista (~$50.000).
            if efectivo_actual >= Decimal("60000.00"):
                excedente_efectivo = ((efectivo_actual - Decimal("50000.00")) // Decimal("10000.00")) * Decimal("10000.00")
                if excedente_efectivo > 0:
                    efectivo_actual -= excedente_efectivo
                    movs_dia.append(
                        preparar(
                            MovimientoFondo(
                                operacion_id=uuid4(),
                                clase="retiro",
                                concepto="Retiro de efectivo al cierre de caja",
                                monto=excedente_efectivo,
                                medio_pago="efectivo",
                                referencia="",
                                categoria_ingreso="",
                                categoria_egreso="",
                                destinatario="",
                                registrado_por=self.admin,
                            ),
                            instante(fecha, 21, 30),
                        )
                    )
                    self.cantidades["retiros_efectivo"] += 1

            sesion = preparar(
                SesionCaja(
                    estado=SesionCaja.Estado.CERRADA,
                    responsable=self.admin,
                    efectivo_inicial=efectivo_inicial,
                    efectivo_anterior=efectivo_anterior,
                    diferencia_apertura=diferencia_apertura,
                    motivo_apertura="",
                    cerrada_en=cierre_dt,
                    efectivo_esperado=efectivo_actual,
                    efectivo_contado=efectivo_actual,
                    diferencia=Decimal("0.00"),
                    motivo_diferencia="",
                ),
                apertura_dt,
                cierre_dt,
            )
            sesiones.append((sesion, movs_dia))
            efectivo_cierre_anterior = efectivo_actual
            self.cantidades["cajas_cerradas"] += 1

        insertar_lote(SesionCaja, [s for s, _ in sesiones])
        for sesion, movs_dia in sesiones:
            for mov in movs_dia:
                mov.sesion_id = sesion.pk
                movimientos_lote.append(mov)
        insertar_lote(MovimientoFondo, movimientos_lote)

    def resumen(self, semilla):
        detalle_meses = "\n".join(
            f"  - {mes:%m/%Y}: {len(self.planes_activos_por_mes[mes])} planes activos/vencidos, "
            f"{len(self.socios_activos_por_mes[mes])} socios activos/vencidos"
            for mes in self.meses
        )
        return (
            f"Semilla: {semilla}\n"
            f"Período operativo: {FECHA_INICIO_OPERACIONES} a {self.fin_mes_actual}\n"
            f"Referencia hoy: {self.hoy} (reservas hasta {self.hasta_reservas}, caja cerrada hasta {self.ultimo_dia_caja})\n"
            "Usuarios nuevos: 90 (6 profesores y 84 participantes), además del administrador inicial.\n"
            "Planes: 8. Membresías: 2. Cumpleaños nuevos: 01/01/2000. Contraseña: ulisesbatata.\n"
            "Pools mensuales:\n"
            f"{detalle_meses}\n"
            + "\n".join(f"{nombre}: {cantidad}" for nombre, cantidad in sorted(self.cantidades.items()))
            + "\nLa importación no crea ni envía correos y deja la caja de hoy lista para abrir en vivo.\n"
        )
