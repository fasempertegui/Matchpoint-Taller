# Modelo relacional para PostgreSQL

## 1. Propósito

Este documento describe cómo se representan los datos de Academia TM en PostgreSQL 17: tablas, atributos, claves, dominios, restricciones, datos derivados y dependencias referenciales. Incluye los campos físicos aportados por Django y las decisiones de normalización del modelo.

Las reglas de negocio, permisos, validaciones de operaciones, confirmaciones y procesos automáticos se definen en `2_criterios_del_sistema.md`.

---

## 2. Convenciones generales

### 2.1 Nombres e identificadores

- Tablas y columnas utilizan `snake_case`; los nombres de tablas están en plural.
- Las claves primarias simples son `bigint GENERATED ALWAYS AS IDENTITY`, salvo `envios_email`, que identifica cada aviso mediante `uuid`.
- Las tablas de relación utilizan claves primarias compuestas cuando corresponde.
- Las claves foráneas terminan en `_id`.

### 2.2 Fechas, horas e importes

- Fechas civiles: `date`.
- Horas operativas: `time without time zone`.
- Auditoría: `timestamptz`.
- Importes: `numeric(12,2)`, no negativos para precios y positivos para movimientos.
- Calendario, cortes y presentación utilizan `America/Argentina/Salta`. Los instantes se almacenan con zona horaria y se comparan usando el reloj del servidor.

### 2.3 Dominios y auditoría

Los estados, modalidades, superficies y medios de pago tienen dominios cerrados, indicados en las tablas y representados mediante opciones de Django. Los roles tienen su propio catálogo, referenciado por clave foránea.

Las tablas de actividades concentran `creado_en` y `actualizado_en` en `eventos`. Las entidades mutables y las asignaciones con estado conservan sus propias marcas; `actualizado_en` registra automáticamente la última modificación del registro. Los vínculos inmutables no requieren una fecha de modificación. Las referencias a responsables de registro, anulación y finalización son datos de auditoría separados de las asignaciones de participantes.

### 2.4 Credenciales

`usuarios.password` contiene el hash generado por Django, con algoritmo PBKDF2 con SHA-256 (`pbkdf2_sha256`), salt y número de iteraciones. La base no almacena contraseñas en texto plano. La recuperación no necesita una tabla de tokens; su representación se explica en 4.25.

### 2.5 Columnas `Nullable` y `Unique`

En las tablas, ambas columnas muestran `Sí` cuando aplica y quedan vacías en caso contrario. `Unique` identifica unicidad sobre una sola columna, incluidas comparaciones normalizadas; no repite la unicidad implícita de una clave primaria. Las claves y restricciones compuestas se describen junto a cada tabla.

---

## 3. Organización del modelo

La ocupación se representa mediante `turnos`, `eventos` y tres especializaciones excluyentes: `reservas`, `clases` y `bloqueos`. El turno contiene la ubicación temporal y física; el evento contiene el tipo, estado y auditoría; la especialización contiene sus atributos particulares. Cada entidad tiene un identificador propio.

La programación semanal se representa con `turnos_planilla` y sus asignaciones. Las clases concretas tienen asignaciones y asistencia propias, por lo que su historia no depende del contenido vigente de la planilla. Los roles de cuenta y las funciones de una persona dentro de una clase son datos distintos.

Planes y membresías se modelan como catálogos independientes, con tablas separadas de contrataciones. Las contrataciones de membresía conservan cupos independientes de organizador e invitado; `ajustes_horas_membresia` registra otorgamientos, descuentos y reversiones por rol. Los precios aplicados se conservan en las contrataciones y reservas; la única fuente monetaria es `movimientos_fondos`. Sus movimientos Ingreso y Egreso de categoría Devoluciones pueden referenciar una contratación concreta o reserva, o conservar solo el concepto. `sesiones_caja` agrupa movimientos y controla el efectivo. Los medios son efectivo, transferencia, tarjeta y QR y la fecha monetaria es la de registro del servidor.

Se admiten pagos parciales mediante varios movimientos Ingreso por origen. La situación financiera se deriva de ingresos y devoluciones Vigentes y del importe acordado, sin almacenar saldos ni estados de pago mutables. Indica Diferencia por cubrir, Cubierto o Excedente por resolver en operaciones no Anuladas y muestra diferencias negativas para revisión administrativa. Los pagos se registran manualmente.

El alta propia y administrativa utiliza las mismas tablas de contratación. La renovación registra otra contratación del mismo producto para el mes siguiente al de referencia, sin una entidad adicional de intención o solicitud. El seguimiento de plantilla consulta las contrataciones por titular y mes sin almacenar un estado de renovación o pago.

El historial transversal de cambios se conserva en `log_auditoria`, separado de los campos propios de creación, modificación y transición de cada entidad.

## 4. Tablas y representación de datos

### 4.1 `usuarios`

Representa a las personas gestionadas por la academia y sus credenciales, datos personales y estado de cuenta.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `password` | `varchar(128)` | | | `pbkdf2_sha256$...` |
| | `last_login` | `timestamptz` | Sí | | `2026-10-12 09:30:00-03` |
| | `is_superuser` | `boolean` | | | `false` |
| | `username` | `varchar(150)` | | Sí | `gomezm` |
| | `first_name` | `varchar(100)` | | | `Martina` |
| | `last_name` | `varchar(100)` | | | `Gómez` |
| | `email` | `varchar(254)` | | Sí | `martina.gomez@gmail.com` |
| | `is_staff` | `boolean` | | | `false` |
| | `is_active` | `boolean` | | | `true` |
| | `fecha_baja` | `timestamptz` | Sí | | `NULL` |
| | `debe_cambiar_contrasena` | `boolean` | | | `true` |
| | `date_joined` | `timestamptz` | | | `2026-10-01 10:15:00-03` |
| | `fecha_nacimiento` | `date` | | | `1998-04-12` |
| | `celular_contacto` | `varchar(30)` | | | `+5493875551234` |
| | `observaciones` | `text` | | | `Celular es de la madre` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 10:15:00-03` |

`Usuario` hereda de `AbstractUser`: `password`, `last_login`, `is_superuser`, `username`, `first_name`, `last_name`, `is_staff`, `is_active` y `date_joined` son columnas físicas de esta tabla. Los atributos heredados `groups` y `user_permissions` son relaciones muchos a muchos almacenadas en `usuarios_groups` y `usuarios_user_permissions`, no columnas de `usuarios`.

`date_joined` identifica el momento de alta; `actualizado_en`, la última modificación; `last_login`, el último acceso. `fecha_baja` es nula para una cuenta activa y contiene el momento de inactivación para una cuenta inactiva. `debe_cambiar_contrasena` representa la condición de contraseña provisoria.

`email` y `username` tienen unicidad sin distinción de mayúsculas mediante restricciones funcionales sobre `LOWER(email)` y `LOWER(username)`. `celular_contacto` no es único y contiene la representación internacional E.164. Las columnas de nombre y apellido admiten hasta 100 caracteres cada una. `observaciones` admite cadena vacía, sin `NULL`.

`is_superuser` es la representación técnica de los permisos de Administrador; el rol funcional se almacena en `usuarios_roles`. `is_staff` permanece en `false`, garantizado por `usuarios_is_staff_false`.

### 4.2 `roles` y `usuarios_roles`

#### Catálogo `roles`

Catálogo fijo de roles, con registros iniciales cargados por migración.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `5` |
| | `codigo` | `varchar(20)` | | Sí | `publico` |
| | `nombre` | `varchar(50)` | | | `Público` |

Contiene Administrador (`administrador`), Profesor (`profesor`), Alumno (`alumno`), Reservas (`reservas`) y Público (`publico`). `codigo` es único y permite identificar cada rol sin depender de su número de fila. La clave foránea al catálogo aporta integridad referencial sin utilizar un enum.

#### Asignaciones `usuarios_roles`

Representa la asociación entre un usuario y un rol del catálogo.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `12` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `rol_id` | `bigint` | | | `2` |
| FK | `asignado_por_id` | `bigint` | Sí | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:15:00-03` |

`usuario_id` referencia `usuarios.id` y `rol_id` referencia `roles.id`. La restricción única `(usuario_id, rol_id)` impide duplicar la misma asignación. `asignado_por_id` referencia al responsable de una asignación administrativa y admite `NULL` para asignaciones automáticas.

Los permisos técnicos de Django se almacenan en sus tablas de autenticación. El modelo no incorpora una tabla `roles_permisos`.

### 4.3 `sedes`

Representa una sede física de la academia.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `nombre` | `varchar(120)` | | Sí | `Sociedad Española` |
| | `direccion` | `varchar(250)` | | | `Av. Sarmiento 320` |
| | `precio_reserva_vigente` | `numeric(12,2)` | Sí | | `30000.00` |
| | `observaciones` | `text` | Sí | | `Ingreso por calle lateral` |
| | `estado` | `varchar(10)` | | | `activa` (o `inactiva`) |
| | `creado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |

La unicidad de `nombre` se aplica mediante `LOWER(nombre)`. `precio_reserva_vigente` es nullable y, cuando está informado, debe ser positivo. La tarifa pertenece a la sede y no se repite en cada cancha. Los horarios utilizan su tabla dependiente `sedes_horarios`.

### 4.4 `canchas`

Representa una cancha perteneciente a una sede.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| FK | `sede_id` | `bigint` | | | `1` |
| | `nombre` | `varchar(120)` | | | `Cancha 1` |
| | `superficie` | `varchar(30)` | | | `cemento` (o `polvo_ladrillo`) |
| | `observaciones` | `text` | Sí | | `Con luminaria` |
| | `estado` | `varchar(10)` | | | `activa` (o `inactiva`) |
| | `creado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |

`sede_id` es obligatorio. La combinación `sede_id, LOWER(nombre)` es única: dos sedes pueden tener canchas con el mismo nombre. `superficie` admite `cemento` o `polvo_ladrillo`. La sede de un evento se obtiene a través de su turno y cancha, sin duplicarla en el evento ni en sus especializaciones.

### 4.5 `planes`

Representa la definición comercial de un plan mensual de clases.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `12` |
| | `nombre` | `varchar(150)` | | | `Grupal dos encuentros semanales` |
| | `descripcion` | `text` | | | `Dos clases de una hora por encuentro` |
| | `modalidad` | `varchar(15)` | | | `grupal` (o `individual`) |
| | `frecuencia_semanal` | `smallint` | | | `2` |
| | `cantidad_clases_por_encuentro` | `smallint` | | | `2` |
| | `precio_vigente` | `numeric(12,2)` | | | `45000.00` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |

`modalidad` admite `individual` o `grupal`; `frecuencia_semanal`, valores de uno a siete; `cantidad_clases_por_encuentro`, uno o dos. Cada clase concreta se representa por separado en `clases`. `precio_vigente` es no negativo y `descripcion` admite cadena vacía, sin `NULL`.

El nombre tiene unicidad parcial sin distinguir mayúsculas y minúsculas mediante `LOWER(nombre)` entre filas con `estado = 'activo'`. Las contrataciones se almacenan en `planes_usuarios`; esta tabla no contiene alumnos, asignaciones ni cobros.

### 4.6 `membresias`

Representa un producto del catálogo de socios.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `18` |
| | `nombre` | `varchar(150)` | | | `Socio 10 horas` |
| | `descripcion` | `text` | | | `Uso mensual de canchas` |
| | `horas_organizador` | `smallint` | | | `10` |
| | `horas_invitado` | `smallint` | | | `10` |
| | `precio_vigente` | `numeric(12,2)` | | | `40000.00` |
| | `precio_invitado_vigente` | `numeric(12,2)` | | | `12500.00` |
| | `estado` | `varchar(10)` | | | `activo` |
| | `creado_en` | `timestamptz` | | | `2026-11-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-11-01 10:00:00-03` |

Las horas son positivas y los precios no negativos, con restricciones de base de datos. El nombre tiene unicidad parcial entre Activas mediante `LOWER(nombre)`, independiente de planes. Descripción admite cadena vacía. Las horas no se modifican cuando existe cualquier contratación histórica; el servicio transaccional coordina edición y contratación. El catálogo no almacena saldo ni variantes por día.

### 4.7 `planes_usuarios`

Representa una contratación concreta de un plan por un usuario para un mes calendario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `301` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `plan_id` | `bigint` | | | `12` |
| | `mes_cubierto` | `date` | | | `2026-10-01` |
| | `fecha_alta` | `date` | | | `2026-10-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `45000.00` |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `observaciones` | `text` | | | `Horario coordinado con administración` |
| | `estado` | `varchar(10)` | | | `activo` (o `anulado`, `vencido`) |
| | `aviso_vencimiento_enviado` | `boolean` | | | `false` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |

`usuario_id` y `plan_id` son referencias obligatorias. `mes_cubierto` contiene el primer día del mes; el inicio y fin de cobertura se derivan de ese valor. `fecha_alta` representa la fecha efectiva, entre el inicio de operaciones y hoy, independiente del mes cubierto. `creado_en` conserva el momento de carga; ambas fechas pueden ser distintas.

`precio_aplicado` conserva el precio mensual vigente copiado al confirmar, no negativo y separado del dinero cobrado. No se edita ni recalcula por la fecha de pago o aumentos de catálogo. El servicio bloquea el producto y revalida el importe revisado; el usuario no lo introduce. El concepto de los ingresos explica pagos parciales o excepciones sin alterar ese precio. Una restricción única parcial sobre `(usuario_id, mes_cubierto)` para estados `activo` o `vencido` preserva la exclusividad del mes y admite conservar filas Anuladas.

`registrado_por_id` referencia obligatoriamente al actor real: el titular en una renovación propia autorizada o el administrador que registra el alta. La titularidad y el permiso se validan en el servicio, conservando la incompatibilidad con Profesor. Los campos de anulación están informados sólo en estado `anulado`: responsable y momento no nulos y motivo no vacío. En los demás estados quedan nulos o vacíos, según su tipo. `observaciones` y `motivo_anulacion` admiten cadena vacía, sin `NULL`.

El portal asigna `fecha_alta` con la fecha local del servidor; administración puede informar la fecha efectiva permitida. El mes siguiente se habilita desde el día 25 para ambos actores. El servicio valida límites y, al renovar por el portal, una contratación no Anulada del mismo producto en el mes inmediatamente anterior al solicitado. No hace falta almacenar un estado de aprobación ni una copia de la contratación de referencia.

`aviso_vencimiento_enviado` conserva la marca de envío de esa contratación. No se duplican en esta tabla asignaciones, asistencia ni importes cobrados.

### 4.8 `membresias_usuarios`

Representa una contratación concreta de membresía por un usuario para un mes calendario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `340` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `membresia_id` | `bigint` | | | `18` |
| | `mes_cubierto` | `date` | | | `2026-10-01` |
| | `fecha_alta` | `date` | | | `2026-10-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `40000.00` |
| | `horas_organizador_aplicadas` | `smallint` | | | `10` |
| | `horas_invitado_aplicadas` | `smallint` | | | `10` |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `observaciones` | `text` | | | `Membresía contratada en sede` |
| | `estado` | `varchar(10)` | | | `activo` (o `anulado`, `vencido`) |
| | `aviso_vencimiento_enviado` | `boolean` | | | `false` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |

Utiliza la misma representación de mes cubierto, fecha efectiva, importe aplicado, auditoría y estados que 4.7, con referencia obligatoria a `membresias.id`. El responsable de registro puede ser el titular que contrata para sí mismo o el administrador, sin exigir Alumno. Tiene su propia restricción única parcial sobre `(usuario_id, mes_cubierto)` entre Activos o Vencidos; no comparte esa restricción con `planes_usuarios`.

El precio aplicado es no negativo y se conserva independiente del catálogo. La contratación conserva el precio mensual vigente completo al confirmar, sin prorrateo ni importe negociado. La cobertura se evalúa por estado y mes para la fecha del turno. Las referencias de organizador e invitado socio pertenecen a reservas e invitados. Ambos cupos aplicados son positivos y se copian del producto al confirmar; no se modifican por cambios posteriores del catálogo. El saldo de cada rol se deriva del cupo conservado, ajustes y usos del titular y mes, incluidos los vinculados a contrataciones Anuladas. Las reservas normales no computan horas de ningún rol. La anulación se rechaza si existe aplicación en una reserva Programada como organizador o invitado socio Aceptado. Las invitaciones Pendientes o Rechazadas no bloquean.

### 4.9 Precios vigentes e importes aplicados

Los valores vigentes se almacenan en los catálogos o la sede. Sus copias aplicadas pertenecen a las contrataciones y reservas correspondientes.

| Precio vigente | Importe conservado |
|---|---|
| `planes.precio_vigente` | `planes_usuarios.precio_aplicado` |
| `membresias.precio_vigente` | `membresias_usuarios.precio_aplicado` |
| `sedes.precio_reserva_vigente` | `reservas.precio_por_turno_aplicado` |
| `membresias.precio_invitado_vigente` | `reservas.precio_invitado_aplicado` |

El modelo no tiene una tabla de historial de precios. La historia comercial se representa mediante los importes aplicados, mientras que los movimientos de dinero utilizan exclusivamente `movimientos_fondos`. La consulta vigente compara neto recibido e importe acordado y el registro del cobro es separado del alta comercial.

### 4.10 `feriados`

Representa una fecha del calendario de feriados común a todas las sedes.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `fecha` | `date` | | Sí | `2026-10-12` |
| | `descripcion` | `varchar(150)` | | | `Feriado nacional` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |

`fecha` es única. No se almacena `sede_id` ni una relación individual con cada clase: la correspondencia se obtiene por la fecha del turno del evento. Los efectos de registrar o quitar una fecha se definen en los criterios del sistema, 2.1.

### 4.11 `turnos_planilla`

Representa una celda de la programación semanal vigente de una cancha.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `55` |
| FK | `cancha_id` | `bigint` | | | `1` |
| | `dia_semana` | `smallint` | | | `3` (1 = lunes … 7 = domingo) |
| | `hora_inicio` | `time` | | | `18:00` |
| | `observaciones` | `text` | Sí | | `Cancha techada en invierno` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |

La combinación `cancha_id, dia_semana, hora_inicio` es única. `dia_semana` utiliza valores de uno a siete y `hora_inicio` contiene una hora en punto. La sede se obtiene de la cancha.

No existe una entidad de planilla por mes ni una tabla de versiones: las asignaciones previstas utilizan `turnos_planilla_profesores` y `turnos_planilla_alumnos`. Las clases concretas no referencian esta celda; `clases.es_generada` identifica si se generaron desde la planilla y cada clase conserva sus propias asignaciones.

### 4.12 `turnos_planilla_profesores`

Representa los profesores previstos para dictar una celda de la programación semanal.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `turno_planilla_id` | `bigint` | | | `55` |
| PK, FK | `profesor_id` | `bigint` | | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |

La clave primaria compuesta `(turno_planilla_id, profesor_id)` impide repetir el vínculo. Ambas columnas son claves foráneas: a `turnos_planilla.id` y `usuarios.id`, respectivamente. No contiene un estado ni historial de modificaciones del vínculo.

### 4.13 `turnos_planilla_alumnos`

Representa los usuarios previstos para asistir como participantes a una celda de la programación semanal.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `turno_planilla_id` | `bigint` | | | `55` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |

La clave primaria compuesta `(turno_planilla_id, usuario_id)` impide repetir el vínculo. `usuario_id` referencia directamente a `usuarios`, no a una asignación de rol ni a una contratación. La participación prevista queda separada del rol Alumno y de la asistencia efectiva.

### 4.14 Turnos y eventos

#### 4.14.1 `turnos`

Representa las coordenadas de una hora de cancha: cancha, fecha y hora de inicio.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `900` |
| FK | `cancha_id` | `bigint` | | | `1` |
| | `fecha` | `date` | | | `2026-10-06` |
| | `hora_inicio` | `time` | | | `18:00` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |

La combinación `cancha_id, fecha, hora_inicio` es única. La hora tiene minutos, segundos y fracciones en cero, con inicio entre 00:00 y 22:00 inclusive. El fin se deriva sumando una hora y no se almacena. La sede se obtiene de la cancha.

El turno no contiene estado de ocupación. Su existencia puede corresponder a un espacio libre o a la historia de varios eventos; la ocupación se determina mediante `eventos`.

#### 4.14.2 `eventos`

Representa los atributos comunes de una reserva, clase o bloqueo, separados de sus datos específicos.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1200` |
| FK | `turno_id` | `bigint` | | | `900` |
| | `tipo` | `varchar(10)` | | | `clase` (o `reserva`, `bloqueo`) |
| | `estado` | `varchar(10)` | | | `finalizado` (o `programado`, `anulado`) |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `observaciones` | `text` | | | `Solicitó cancha techada` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-06 19:00:00-03` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `finalizado_en` | `timestamptz` | Sí | | `2026-10-06 19:00:00-03` |

`turno_id` es obligatorio y tiene un índice para consultar la historia del turno. Una restricción única parcial sobre `turno_id`, con condición `estado <> 'anulado'`, permite un máximo de un evento Programado o Finalizado por turno y múltiples eventos Anulados históricos. Los eventos conservan identificadores independientes aunque referencien el mismo turno.

La creación de cualquier evento exige que la fecha y hora de inicio de su turno sea estrictamente posterior al momento actual del servidor. La validación incluye las altas individuales y masivas; las actualizaciones de eventos existentes conservan la gestión de su historia.

Cada evento tiene exactamente una especialización en `reservas`, `clases` o `bloqueos`, coherente con `tipo`. Los `evento_id` de esas tablas son únicos. Cancha, fecha y hora pertenecen a `turnos` y no se duplican en el evento ni en sus especializaciones.

La coherencia de estado y auditoría es:

- `programado`: sin responsable, momento o motivo de anulación ni momento de finalización.
- `anulado`: con responsable, momento y motivo de anulación; sin momento de finalización.
- `finalizado`: con momento de finalización y sin datos de anulación; corresponde a reservas, clases y bloqueos.

`observaciones` y `motivo_anulacion` admiten cadena vacía, sin `NULL`. Las referencias a usuarios identifican responsables de registro y anulación. La responsabilidad de finalización manual de una clase se representa en `clases.finalizado_por_id`; no hay una columna equivalente para reservas.

### 4.15 `clases`

Contiene la especialización de un evento de tipo clase.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `700` |
| FK | `evento_id` | `bigint` | | Sí | `1200` |
| | `es_generada` | `boolean` | | | `true` |
| FK | `finalizado_por_id` | `bigint` | Sí | | `NULL` |

`evento_id` es único y referencia un evento de tipo `clase`. Estado, ubicación, observaciones y marcas de auditoría comunes se obtienen de ese evento y su turno. Profesores, participantes y asistencia se representan en tablas dependientes.

`es_generada` distingue las clases generadas desde la planilla de las creadas manualmente. La clase concreta no referencia una celda de planilla y conserva sus propios datos y asignaciones.

`finalizado_por_id` contiene al responsable de una finalización manual. Es nulo antes de finalizar, en clases Anuladas y cuando la finalización es automática. Si está informado, el evento relacionado tiene estado `finalizado`.

### 4.16 `clases_profesores`

Representa la asignación de una persona para dictar una clase concreta.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `profesor_id` | `bigint` | | | `4` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `creado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |

La clave primaria compuesta `(clase_id, profesor_id)` impide repetir una asignación. `profesor_id` referencia `usuarios.id`. El estado `activo` o `inactivo` pertenece al vínculo y es distinto del estado de la cuenta y del evento de la clase. Las marcas de creación y modificación corresponden a esa asignación.

### 4.17 `clases_alumnos`

Representa la asignación prevista de una persona para asistir a una clase concreta como participante.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `observaciones` | `text` | Sí | | `Se suma sólo por octubre` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `respuesta` | `varchar(11)` | | | `asistira` |
| FK | `respondido_por_id` | `bigint` | Sí | | `NULL` |
| | `respondido_en` | `timestamptz` | Sí | | `NULL` |
| | `recordatorio_enviado` | `boolean` | | | `false` |
| | `creado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |

La clave primaria compuesta `(clase_id, usuario_id)` impide repetir una asignación. `usuario_id` referencia a la persona directamente, sin depender de su rol de cuenta ni de una contratación. Se mantiene separada de `clases_profesores` y de la asistencia efectiva.

`estado` representa la vigencia de la asignación. `recordatorio_enviado` es una marca por participante y clase, no por clase completa; permite representar envíos independientes. `observaciones` y las fechas de auditoría pertenecen al vínculo.

`respuesta` admite `asistira` (Asistirá, valor por defecto) y `no_asistira` (No asistirá). `respondido_por_id` y `respondido_en` conservan titular y momento de la decisión. Ambos pueden estar vacíos sólo en Asistirá; cuando están informados, el responsable coincide con `usuario_id`. El servicio permite únicamente registrar No asistirá, con titular habilitado, asignación activa, clase Programada e inicio futuro. Repetir el aviso no genera cambios. No permite volver a Asistirá. Asistirá ocupa disponibilidad personal; No asistirá no la ocupa. La auditoría conserva la historia y reactivar mantiene el aviso. La asistencia real, los profesores y la plantilla permanecen separados.

### 4.18 `asistencias`

Representa el registro de asistencia efectiva de una persona a una clase.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `estado` | `varchar(15)` | | | `presente` (o `ausente`, `sin_registrar`) |
| FK | `registrada_por_id` | `bigint` | Sí | | `6` |
| | `observaciones` | `text` | Sí | | `Llegó sobre la hora` |
| | `registrada_en` | `timestamptz` | Sí | | `2026-10-07 19:04:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-07 19:04:00-03` |

La clave primaria compuesta `(clase_id, usuario_id)` impide repetir el registro. Las claves foráneas apuntan directamente a `clases` y `usuarios`; no existe una referencia obligatoria a `clases_alumnos`, por lo que puede representarse asistencia sin asignación previa.

`estado` admite `presente`, `ausente` y `sin_registrar`. `registrada_en` es obligatorio para los dos primeros. `registrada_por_id` identifica al responsable de la carga y no una función dentro de la clase. `actualizado_en` distingue el momento de modificación del registro. Las condiciones de carga y corrección se definen en criterios, 2.1.

### 4.19 `reservas`

Contiene los atributos comerciales de un evento de tipo reserva.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1200` |
| FK | `evento_id` | `bigint` | | Sí | `1300` |
| FK | `organizador_id` | `bigint` | | | `1` |
| | `precio_por_turno_aplicado` | `numeric(12,2)` | Sí | | `NULL` |
| FK | `membresia_usuario_id` | `bigint` | Sí | | `340` |
| | `precio_invitado_aplicado` | `numeric(12,2)` | Sí | | `12500.00` |
| | `computa_hora_membresia` | `boolean` | | | `true` |
| | `resultado_uso` | `varchar(15)` | | | `sin_registrar` |
| FK | `resultado_registrado_por_id` | `bigint` | Sí | | `NULL` |
| | `resultado_registrado_en` | `timestamptz` | Sí | | `NULL` |
| | `resultado_original` | `varchar(15)` | Sí | | `NULL` |
| FK | `resultado_corregido_por_id` | `bigint` | Sí | | `NULL` |
| | `resultado_corregido_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_correccion_resultado` | `text` | | | `''` |
| | `anulada_por_organizador` | `boolean` | Sí | | `NULL` |

El evento único es de tipo reserva. El organizador es distinto del responsable de registro del evento. Número y turno se obtienen del identificador y del evento. No hay beneficiario ni asistencia individual de reservas.

Las restricciones de modalidad exigen exactamente una alternativa:

- Normal: precio por turno positivo, membresía y adicional nulos y cómputo de hora falso.
- Con membresía: contratación del organizador y adicional unitario no negativo obligatorios, precio por turno nulo. Nunca se computa una hora sin contratación aplicada.

La reserva con membresía nace con cómputo verdadero; Programada compromete la hora y Finalizada la consume. La anulación propia conserva el cómputo con dos horas o menos y lo quita con más de dos; la administrativa siempre lo quita. La hora pertenece al mes del turno. El cómputo es un resultado comercial de la reserva, no un saldo mutable. Se cuentan usos de todas las contrataciones del titular y mes, incluidas Anuladas, y los ajustes netos por rol. La cancelación libera siempre las horas comprometidas de invitados.

El total no se almacena: normal utiliza su tarifa; con membresía multiplica el adicional unitario por las participaciones computables sin beneficio, tanto no socios como socios con cupo agotado. La aceptación aplica la condición comercial; al comenzar el turno se conserva su efecto sin recalcular usos o importes históricos. La cantidad de participantes se deriva de esas relaciones; no existe cantidad total declarada. En normal los invitados son opcionales y no alteran la tarifa.

Resultado admite `sin_registrar`, `realizada` o `no_realizada`. Sin registrar exige datos iniciales nulos y ausencia de corrección. Registrar después de Finalizado exige responsable y momento. La única corrección exige un resultado distinto, original conservado, responsable, momento y motivo no vacío; los campos de corrección se informan juntos. El servicio bloquea la reserva e impide una segunda corrección. El resultado no modifica horas ni invitados.


`anulada_por_organizador` es nulo mientras el evento no esté Anulado; verdadero para cancelación propia y falso para administrativa. Motivo, actor y momento de anulación pertenecen al evento.

### 4.20 `reservas_invitados`

Representa una invitación existente. Quitar al invitado elimina la relación y conserva su historia mediante auditoría.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `reserva_id` | `bigint` | | | `1200` |
| PK, FK | `usuario_id` | `bigint` | | | `9` |
| FK | `membresia_usuario_id` | `bigint` | Sí | | `NULL` |
| | `condicion_aplicada` | `varchar(20)` | | | `sin_aplicar` |
| | `respuesta` | `varchar(10)` | | | `pendiente` |
| FK | `respondido_por_id` | `bigint` | Sí | | `NULL` |
| | `respondido_en` | `timestamptz` | Sí | | `NULL` |
| | `creado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |

La clave compuesta impide duplicados y el usuario es distinto del organizador. No hay estado de retiro. Volver a invitar después de eliminar crea una invitación Pendiente. Las revisiones de respuesta identifican al titular y las fechas de creación y modificación de la invitación; una solicitud anterior a su eliminación no modifica una relación creada nuevamente.

Respuesta admite `pendiente`, `afirmativa` y `negativa`, presentadas como Pendiente, Aceptada y Rechazada. Pendiente exige responsable y momento nulos; Aceptada o Rechazada exige ambos informados y responsable igual a `usuario_id`. Estos campos conservan la última decisión; la auditoría conserva todas. Los servicios permiten cambios sin límite antes del inicio, no permiten volver a Pendiente y comprueban titularidad, acceso y estado Programado. Repetir la decisión no modifica los datos.

Condición admite `sin_aplicar`, `socio`, `no_socio`, `cupo_agotado` o `reserva_normal`. Sin aplicar es el valor inicial y no tiene contratación aplicada. Aceptar una reserva normal aplica `reserva_normal`, sin membresía, horas ni adicional. En membresía se evalúa cobertura y horas al aceptar: `socio` exige contratación con cobertura y horas de invitado disponibles; `cupo_agotado` conserva la contratación cuya cobertura existe pero no tiene saldo; `no_socio` no tiene contratación. Los dos últimos generan el adicional unitario conservado en la reserva. Rechazar antes del inicio libera la aplicación y vuelve a sin aplicar, sin borrar la historia de auditoría.

La disponibilidad personal depende exclusivamente de la respuesta Aceptada y es un requisito independiente del beneficio comercial. Horas, total y cantidad computable derivan de la condición efectivamente aplicada y la respuesta. La condición comercial de un turno comenzado se conserva sin recalcular importes o consumos. La anulación del evento excluye los usos de invitado; no borra sus referencias.

Actualizar socios evalúa sólo Aceptadas con adicional antes del inicio. Exige cobertura y horas de invitado disponibles, conserva precio unitario, respuestas y cobros y registra el cambio en auditoría. Los bloqueos comunes coordinan aceptación, eliminación, clases, reservas, ajustes y anulaciones de contrataciones.

### 4.21 `sesiones_caja`

Representa una sesión de la única caja de la academia. El administrador que abre es su responsable fijo y quien la cierra. No existe una tabla de cajas ni reasignación.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `15` |
| | `estado` | `varchar(10)` | | | `abierta` (o `cerrada`) |
| FK | `responsable_id` | `bigint` | | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-10-29 08:00:00-03` |
| | `efectivo_inicial` | `numeric(12,2)` | | | `20000.00` |
| | `motivo_apertura` | `text` | | | `Retiro personal entre sesiones` |
| | `cerrada_en` | `timestamptz` | Sí | | `NULL` |
| | `efectivo_esperado` | `numeric(12,2)` | Sí | | `NULL` |
| | `efectivo_contado` | `numeric(12,2)` | Sí | | `NULL` |
| | `diferencia` | `numeric(12,2)` | Sí | | `NULL` |
| | `motivo_diferencia` | `text` | | | `''` |

Un índice único parcial sobre `estado`, con condición `estado = 'abierta'`, permite como máximo una sesión abierta. El número legible `C-000015` se deriva del identificador.

`efectivo_inicial` y `efectivo_contado` son no negativos. `motivo_apertura` es obligatorio cuando el inicial difiere del último contado; si coincide o es la primera apertura queda vacío. No crea un movimiento automático. Las fechas las fija el servidor. En Abierta los campos de cierre son nulos y el motivo de diferencia está vacío; en Cerrada están informados, `cerrada_en >= creado_en` y la diferencia es contado menos esperado. Si la diferencia no es cero, el motivo es obligatorio.

El efectivo esperado de una sesión abierta se calcula con sus movimientos Vigentes: `efectivo_inicial + ingresos en efectivo + aportes − egresos en efectivo − retiros`. Los medios digitales no intervienen. Los egresos en efectivo de categoría devoluciones cuentan como salidas. Al cerrar se guardan esperado, contado y diferencia; una diferencia positiva indica sobrante y una negativa, faltante. Una diferencia no genera un movimiento. Los totales por clase y medio se consultan desde los movimientos; no se almacena una fotografía JSON.

`responsable_id` referencia `usuarios.id`, conserva al administrador que abre y no se modifica. La apertura y las cargas requieren usuario autenticado, activo, con rol Administrador y sin cambio obligatorio de contraseña. Solo el responsable opera y cierra su sesión; otros administradores pueden consultar. El servicio impide modificar, borrar o reabrir una sesión Cerrada y agregarle movimientos. Puede haber varias sesiones sucesivas por día y una sesión puede atravesar medianoche; no existe cierre automático.

La apertura usa transacción y el índice único parcial. Registro, anulación y cierre bloquean la sesión con `select_for_update` dentro de `transaction.atomic`. La anulación de un movimiento de otra sesión bloquea también la sesión de origen. El estado se revalida al confirmar para que una carga concurrente con cierre se incluya o se rechace. La tabla participa de la auditoría transversal de modificaciones y anulaciones. La inmutabilidad se valida en servicios, sin triggers adicionales de protección de esta tabla en PostgreSQL.

### 4.22 `sedes_horarios`

Representa las franjas semanales de funcionamiento de una sede.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `sede_id` | `bigint` | | | `1` |
| PK | `dia_semana` | `smallint` | | | `3` (1 = lunes … 7 = domingo) |
| | `hora_inicio_1` | `time` | | | `08:00` |
| | `hora_fin_1` | `time` | | | `12:00` |
| | `hora_inicio_2` | `time` | Sí | | `16:00` |
| | `hora_fin_2` | `time` | Sí | | `22:00` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 09:00:00-03` |

La clave primaria compuesta `(sede_id, dia_semana)` permite una fila por sede y día de la semana. `dia_semana` toma valores de uno a siete. La primera franja es obligatoria y la segunda se representa mediante dos columnas opcionales que están ambas presentes o ambas nulas.

Los cuatro horarios tienen minutos, segundos y fracciones en cero. Cada fin es posterior a su inicio; una segunda franja comienza al menos una hora después del fin de la primera. Las restricciones de base de datos controlan la coherencia de las parejas y su separación. La ausencia de una fila representa un día sin funcionamiento.

### 4.23 `movimientos_fondos`

Representa ingresos, egresos, aportes y retiros registrados manualmente en una sesión abierta. Es la única fuente de cobros comerciales y no tiene un registro monetario paralelo.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `5000` |
| | `operacion_id` | `uuid` | | Sí | `b3f1…` |
| FK | `sesion_id` | `bigint` | | | `15` |
| | `clase` | `varchar(10)` | | | `ingreso` (o `egreso`, `aporte`, `retiro`) |
| | `concepto` | `text` | | | `Mensualidad de octubre` |
| | `monto` | `numeric(12,2)` | | | `35000.00` |
| | `medio_pago` | `varchar(15)` | | | `efectivo` (o `transferencia`, `tarjeta`, `qr`) |
| | `referencia` | `varchar(150)` | | | `''` |
| | `categoria_ingreso` | `varchar(20)` | | | `planes` |
| | `categoria_egreso` | `varchar(20)` | | | `''` |
| | `destinatario` | `varchar(150)` | | | `''` |
| FK | `plan_usuario_id` | `bigint` | Sí | | `301` |
| FK | `membresia_usuario_id` | `bigint` | Sí | | `NULL` |
| FK | `reserva_id` | `bigint` | Sí | | `NULL` |
| | `creado_en` | `timestamptz` | | | `2026-10-29 09:10:00-03` |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `estado` | `varchar(10)` | | | `vigente` (o `anulado`) |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |

`monto` es positivo y se calcula con Decimal, sin floats. `concepto` siempre contiene texto no vacío. Los medios no efectivos requieren `referencia`. Ingreso exige `categoria_ingreso`: `reservas`, `planes`, `membresias` u `otros`. Se determina por el tipo de origen: Reservas, Planes y Membresías requieren su vínculo correspondiente; sin vínculo, la categoría es Otros. Egreso exige `categoria_egreso`: `alquiler`, `servicios`, `profesores`, `insumos`, `mantenimiento`, `publicidad`, `otros` o `devoluciones`; `destinatario` es texto opcional. Cada categoría queda vacía fuera de su clase. El destinatario queda vacío fuera de Egreso. Aporte y Retiro solo admiten efectivo y no se contabilizan como cobros o gastos operativos.

Ingreso y Egreso de categoría `devoluciones` admiten referencias comerciales y como máximo una de las tres está informada. Una restricción de base de datos impide esos vínculos en otros egresos, aportes y retiros; un ingreso sin vínculo se identifica por su concepto obligatorio. `plan_usuario_id` referencia `planes_usuarios.id`, `membresia_usuario_id` referencia `membresias_usuarios.id` y `reserva_id` referencia `reservas.id`. No apuntan a productos del catálogo. Se admiten varios ingresos por origen, con comparación informativa del neto con el importe acordado. Las señas o adelantos opcionales de reservas confirmadas se representan mediante estos mismos ingresos vinculados, sin una tabla ni un estado de pago propios. El registro muestra el importe conservado de la contratación y sus ingresos Vigentes; el concepto explica pagos parciales o acuerdos excepcionales, sin representar descuentos ni alterar importes comerciales. El origen debe existir y estar confirmado; no admite nuevos ingresos si la contratación está Anulada o el evento de la reserva está Anulado. No se crea ni renueva un origen al registrar el cobro.

`sesion_id` referencia `sesiones_caja.id`; `registrado_por_id` y `anulado_por_id` referencian `usuarios.id`. Estas relaciones y los vínculos comerciales protegen a sus registros referenciados contra la eliminación. La reserva o contratación y su cobro se confirman como operaciones independientes: un error monetario no revierte el origen comercial.

Una devolución usa clase `egreso` y categoría `devoluciones`: representa dinero efectivamente reintegrado a un cliente, en cualquiera de los cuatro medios. Exige concepto, monto y referencia para no efectivo; el destinatario es opcional. No tiene FK a un ingreso particular. Su vínculo opcional utiliza las FK comerciales y el máximo vinculado es ingresos Vigentes menos devoluciones Vigentes de ese origen, recalculado bajo bloqueo común con ingresos y anulaciones. Un neto no positivo impide nuevas devoluciones vinculadas; el origen puede estar Anulado. Sin vínculo no tiene tope comercial y exige concepto. Compensaciones superiores se registran como otros egresos sin vínculo comercial. Los resúmenes la separan de los gastos operativos. No modifica automáticamente cobros, contratación ni reserva. Cancelar una operación comercial no genera un reintegro ni anula sus cobros; el reintegro se registra como un egreso independiente.

Las FK opcionales y fechas no informadas usan NULL; los textos opcionales usan cadena vacía. La creación pertenece a una sesión abierta y usa exclusivamente `creado_en`, asignado por el servidor, y el responsable de esa sesión. La fecha no es editable y no se almacena una fecha real de operación separada. Las fechas se interpretan en `America/Argentina/Salta` y los importes son pesos argentinos con dos decimales.

`operacion_id` tiene unicidad individual y se conserva para reintentos del mismo formulario. El servicio devuelve el registro existente si actor y contenido coinciden, y rechaza el UUID con otro actor o contenido. No se exige que coincida con el UUID de contexto de auditoría. Se indexan `(sesion_id, id)` y `creado_en`.

Los servicios validan dominios, importes, referencias y coherencia de campos dentro de la transacción y rechazan una salida de efectivo que supere lo disponible. Impiden editar datos originales o borrar movimientos. Ingresos y egresos, incluidas devoluciones, así como aportes y retiros, admiten anulación con motivo obligatorio: completa `estado = 'anulado'`, `anulado_por_id`, `anulado_en` y `motivo_anulacion`. En Vigente los datos de anulación son nulos o vacíos según su tipo. El actor es el responsable de la sesión abierta actual, aunque el movimiento pertenezca a una cerrada. Un Anulado no se reactiva ni vuelve a anularse.

Anular invalida la carga y no representa un reintegro. En sesión abierta recalcula el esperado y no puede dejarlo negativo; en sesión cerrada no modifica los resultados guardados. Corregir requiere una nueva carga independiente en la sesión actual; si corresponde a efectivo, tiene efecto ordinario y puede producir una diferencia explicada aunque no haya movimiento físico presente. No existe un vínculo entre el movimiento anulado y la nueva carga.

La consulta comercial presenta una única situación financiera por origen: importe acordado, cobros vigentes (suma de ingresos Vigentes), devoluciones vigentes (suma de devoluciones Vigentes) y neto recibido (ingresos menos devoluciones), sin reasignar movimientos ni almacenar saldos o estados de pago mutables. Una devolución reduce el neto sin modificar ingresos originales ni el importe acordado. Modificar ese importe requiere una operación autorizada y auditada. Compara ese neto con el importe acordado sólo en operaciones no Anuladas para indicar Diferencia por cubrir, Cubierto o Excedente por resolver. La diferencia por cubrir no implica por sí sola una deuda exigible. Las operaciones Anuladas muestran importes, movimientos y neto sin esos estados ni devolución automática. Anular un ingreso puede revelar neto negativo sin anular devoluciones; se conserva la validación de efectivo y se muestra la diferencia para revisión administrativa. El resumen histórico de una sesión cerrada incluye los movimientos con `anulado_en IS NULL OR anulado_en > cerrada_en`; los anulados antes o al cerrar no suman. Una anulación posterior no modifica los importes guardados del cierre. La comparación comercial no modifica los importes guardados del cierre.

La protección de datos originales y la inmutabilidad del cierre se validan en servicios; no hay triggers adicionales de inmutabilidad sobre las tablas de caja. El trigger común registra modificaciones y anulaciones dentro de la transacción y las altas conservan sus datos de creación sin agregar entradas al historial. Un error revierte la escritura y su auditoría. El registro de una escritura SQL no impide esa escritura. Las reglas operativas se detallan también en criterios, 2.5 y 2.12.

### 4.24 `bloqueos`

Representa un bloqueo de un turno y su vínculo opcional con la actividad anulada que originó su creación.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `40` |
| FK | `evento_id` | `bigint` | | Sí | `1400` |
| | `motivo` | `varchar(20)` | | | `clima_adverso` (o `torneo`, `mantenimiento`) |
| FK | `evento_origen_id` | `bigint` | Sí | Sí | `1300` |

`evento_id` es único y referencia un evento de tipo `bloqueo`. El turno, estado, observaciones y auditoría pertenecen al evento. `motivo` admite `clima_adverso`, `torneo` y `mantenimiento`. La especialización no agrega un estado ni una ubicación propios; su evento admite `programado`, `anulado` y `finalizado`.

`evento_origen_id` referencia opcionalmente un evento de reserva o clase Anulado sobre el mismo turno que el bloqueo. Es único cuando está informado: un evento puede originar como máximo un bloqueo. Un bloqueo creado sobre un turno libre guarda `NULL`; varios bloqueos pueden no tener origen. La referencia protege al evento contra la eliminación física y se conserva aunque se anule el bloqueo.

### 4.25 Representación de la recuperación de contraseña

La recuperación utiliza el mecanismo nativo de Django, sin tabla de solicitudes ni tokens persistidos. El enlace contiene el identificador codificado del usuario y un token autenticado mediante HMAC, derivado de la clave secreta, datos de la cuenta y una marca temporal. Su validez depende de los datos existentes de `usuarios`, no de una fila de recuperación.

La vigencia y las condiciones de uso del enlace se definen en criterios, 2.3.

---

### 4.26 `log_auditoria`

Historial de modificaciones, anulaciones y eliminaciones permitidas capturado por triggers de PostgreSQL.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `450` |
| | `operacion_id` | `uuid` | | | `138adcdf-0ba0-4843-a43c-6e36819848e0` |
| | `tabla` | `varchar(63)` | | | `eventos` |
| | `clave_registro` | `jsonb` | | | `{"id": 1200}` |
| | `accion` | `varchar(32)` | | | `anulacion` |
| | `valores_anteriores` | `jsonb` | | | `{"estado": "programado"}` |
| | `valores_actuales` | `jsonb` | | | `{"estado": "anulado"}` |
| | `realizado_en` | `timestamptz` | | | `2026-10-06 15:00:00-03` |
| FK | `usuario_id` | `bigint` | Sí | | `4` |
| | `usuario_bd` | `varchar(63)` | | | `atm` |
| | `origen` | `varchar(10)` | | | `aplicacion` |

La base valida las acciones `modificacion`, `anulacion`, `eliminacion`, `cambio_contrasena`, `restablecimiento_contrasena` y `actualizacion_hash`. Los orígenes son `aplicacion`, `tarea` y `sql`. El origen de aplicación exige un usuario; los demás exigen una referencia nula. La FK a `usuarios` protege al actor contra la eliminación física. `usuario_bd` contiene `session_user`, sin sustituir la identidad del usuario de la aplicación.

La combinación de tabla y clave identifica al registro sin una FK polimórfica. Las claves compuestas guardan todos sus componentes: por ejemplo `{"sede_id": 2, "dia_semana": 3}`. Los valores anteriores y actuales contienen los campos modificados; en las eliminaciones permitidas se conserva el registro anterior completo y un objeto vacío como valor actual. Los triggers no generan entradas de alta. Los ejemplos de esta tabla muestran sólo un subconjunto ilustrativo de una anulación. Las contraseñas y hashes no se almacenan ni se representan mediante marcas artificiales. Las acciones de contraseña identifican el evento y conservan sólo cambios reales no sensibles; si no existen otras diferencias relevantes, ambos objetos son vacíos. `actualizado_en` no se incluye en las instantáneas de estos eventos; el momento de la operación se conserva en `realizado_en`.

`operacion_id` agrupa las entradas de una misma operación y no es único por fila ni constituye una cabecera de negocio. Existen índices por operación, por tabla y fecha descendente y por usuario y fecha descendente; la FK conserva además su índice propio.

La función `registrar_auditoria` recibe los nombres de los componentes de la PK mediante los argumentos del trigger. Cada tabla de negocio tiene un trigger de fila `AFTER UPDATE OR DELETE`, incluidas `sesiones_caja` y `movimientos_fondos`. El cierre es una modificación y la anulación de un movimiento se reconoce por su estado; no se agregan entradas de alta. La función usa `OLD` y `NEW`, descarta cambios sin diferencias funcionales, excluye secretos e inserta el historial dentro de la misma transacción. El actor, origen, UUID y acción específica se leen de configuración local; sin contexto se registra origen SQL y la base genera el UUID de la transacción. Un trigger independiente rechaza modificación, eliminación y vaciado de `log_auditoria`. Las reglas de contexto y consulta se definen en criterios, 2.14.

---

### 4.27 `intentos_auditoria`

Registro inmutable de los tres tipos de intentos rechazados definidos en criterios, 2.14. Lo inserta la aplicación después de salir de la transacción de negocio.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `18` |
| | `solicitud_id` | `uuid` | | Sí | `138adcdf-0ba0-4843-a43c-6e36819848e0` |
| | `realizado_en` | `timestamptz` | | | `2026-11-04 08:00:00-03` |
| FK | `usuario_id` | `bigint` | Sí | | `4` |
| | `tipo` | `varchar(32)` | | | `acceso_denegado` |
| | `motivo` | `varchar(40)` | | | `permisos_insuficientes` |
| | `identificador_ingresado` | `varchar(150)` | | | `mamanit` |
| | `vista` | `varchar(150)` | | | `usuarios:usuario_detalle` |
| | `metodo` | `varchar(7)` | | | `GET` |
| | `parametros_destino` | `jsonb` | | | `{"pk": 11}` |

Los tipos permitidos son `inicio_sesion_fallido`, `cambio_contrasena_rechazado` y `acceso_denegado`. Una restricción valida los motivos correspondientes: credenciales inválidas o cuenta inactiva para login; contraseña actual incorrecta para cambio de contraseña; permisos insuficientes o registro ajeno para acceso. El login fallido exige usuario nulo; el cambio de contraseña exige usuario identificado. El identificador ingresado se guarda sólo para login y es una entrada declarada, no una identidad autenticada; en otros tipos es una cadena vacía. La FK protege al actor de eliminación física. Los valores anteriores y actuales pertenecen a `log_auditoria`, no a esta tabla.

El UUID único evita duplicados de la misma solicitud. Hay un índice por usuario y fecha descendente; la FK conserva su índice propio. El identificador de fila se genera en PostgreSQL. Un trigger de sentencia rechaza modificación, eliminación y vaciado mediante la función común de protección del historial. Las inserciones no generan auditoría recursiva ni entradas de alta en `log_auditoria`.

---


### 4.28 `ajustes_horas_membresia`

Registra movimientos administrativos de horas de una contratación concreta.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| FK | `membresia_usuario_id` | `bigint` | | | `340` |
| | `tipo_horas` | `varchar(15)` | | | `organizador` |
| | `operacion` | `varchar(10)` | | | `otorgar` |
| | `cantidad` | `smallint` | | | `2` |
| | `motivo` | `text` | | | `Premio del torneo` |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-11-08 10:00:00-03` |
| FK | `reversion_de_id` | `bigint` | Sí | Sí | `NULL` |

Las FK protegen contratación, administrador y ajuste original contra eliminación. `tipo_horas` admite organizador o invitado; `operacion`, otorgar o quitar; `cantidad` es entera positiva y el motivo no vacío. Otorgar suma y quitar resta. Se indexan contratación, tipo y fecha. Los registros no se editan ni borran.

Una reversión es otro movimiento de igual cantidad y operación inversa, misma contratación y rol, con referencia única al original, motivo propio y administrador responsable. No puede apuntarse a sí misma ni revertir una reversión; el servicio valida coherencia bajo bloqueo y la unicidad impide dobles reversiones. Ambos registros permanecen en la suma y el historial. El movimiento y su reversión conservan motivo, responsable y fecha como evidencia administrativa. Un trigger impide UPDATE, DELETE y TRUNCATE de estos movimientos; no se edita un saldo ni se borra el original. La tabla declara el trigger común de auditoría y las altas conservan sus datos de creación sin agregar entradas a log_auditoria, según criterios 2.14.

El servicio sólo admite ajustes y reversiones para contrataciones Activas del período vigente o programadas para un período futuro. Bloquea titular y contratación en el orden común con reservas e invitaciones. Recalcula por rol `cupo + otorgadas − descontadas − comprometidas − consumidas` y rechaza descuentos o reversiones que dejen disponibilidad negativa. No modifica participaciones existentes ni genera penalizaciones pendientes, cambios de precio o movimientos monetarios. Los cupos aplicados y los movimientos explican la disponibilidad sin almacenar saldo mutable.


### 4.29 `envios_email`

Registro persistente de emails preparados por las operaciones. Redis transporta tareas y no es la fuente del seguimiento. La operación y su aviso se guardan en la misma transacción. La tabla no registra lectura ni sirve como bandeja del usuario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Descripción |
|---|---|---|---|---|---|
| PK | `id` | `uuid` | | | Identidad del envío. |
| | `clave` | `varchar(250)` | | Sí | Hecho efectivo y destinatario, sin secretos. |
| | `tipo` | `varchar(32)` | | | Tipo funcional de email. |
| | `destinatario` | `varchar(254)` | | | Dirección capturada para ese recorrido. |
| | `datos` | `jsonb` | | | Contenido mínimo, referencias de vigencia y preparación del enlace. |
| | `estado` | `varchar(12)` | | | pendiente, en_proceso, enviado, fallido o descartado. |
| | `creado_en` | `timestamptz` | | | Creación junto con la operación. |
| | `proximo_intento_en` | `timestamptz` | | | Instante desde el que puede reclamarse. |
| | `intentos` | `smallint` | | | De cero a cuatro. |
| | `ultimo_intento_en` | `timestamptz` | Sí | | Última reclamación para entrega. |
| | `enlace_emitido_en` | `timestamptz` | Sí | | Primera emisión, conservada durante reintentos. |
| | `reserva_token` | `uuid` | Sí | | Identidad privada de la reserva de procesamiento. |
| | `reservado_hasta` | `timestamptz` | Sí | | Fin de la reserva de cinco minutos. |
| | `aceptado_en` | `timestamptz` | Sí | | Confirmación de aceptación por el proveedor. |
| | `error_resumido` | `varchar(200)` | | | Resultado técnico sin texto sensible del proveedor. |

`envio_estado_valido` restringe los cinco estados y `envio_intentos_validos` limita a cuatro intentos. `envio_reserva_coherente` exige identificador y fecha de reserva únicamente En proceso. `envio_aceptacion_coherente` exige fecha de aceptación únicamente Enviado. La clave única evita duplicar registros por llamadas concurrentes. Índices por estado/próximo intento y estado/fin de reserva permiten recuperar pendientes y procesamientos interrumpidos.

`datos` contiene tres bloques acotados: `mensaje`, con párrafos, pares etiqueta/valor, acciones internas y apartados; `vigencia`, con referencias de cuenta, actividad, participación, solicitud y vencimiento aplicables; y `enlace`, cuando se prepara una confirmación firmada. No se almacenan contraseñas, tokens ni URLs completas de acceso. El token se construye con la identidad del aviso y su emisión persistida. La recuperación de contraseña utiliza sus mecanismos nativos de Django en el flujo de cuenta.

Las referencias técnicas de `datos` no son FK y no conceden acceso: la entrega vuelve a consultar los registros actuales. Así se conserva la evidencia mínima de una retirada aunque su vínculo ya no exista, sin impedir la limpieza de una cuenta inicial. La identidad de una participación incluye su creación para distinguir borrado y nueva asignación con la misma clave compuesta. El registro de envío es la fuente técnica de entrega; la auditoría de la operación conserva sus propias reglas y no copia cuerpos, enlaces o errores sensibles de emails.

Las transiciones de entrega bloquean el registro sólo mientras se reclama o se confirma el resultado. El proveedor se invoca fuera de la transacción. El identificador de reserva impide que un trabajador interrumpido confirme sobre otra reserva. Vencer una reserva cuenta como interrupción y aplica el siguiente plazo de fallo. Los reintentos son 5, 15 y 60 minutos desde cada fallo; un enlace vence a los quince minutos de su emisión sin extenderse al reintentar. Enviado no representa confirmación de lectura o recepción final y admite el límite de duplicación por aceptación remota sin confirmación local.


## 5. Dependencias referenciales y eliminación

- Las referencias a usuarios, sedes, canchas, productos y contrataciones protegen los registros que tienen datos dependientes. Cada contratación referencia obligatoriamente a su usuario y producto.
- `usuarios_roles` utiliza cascada desde `usuarios`; `rol_id` protege el registro del catálogo mientras tenga asignaciones.
- `turnos_planilla_profesores` y `turnos_planilla_alumnos` utilizan cascada desde `turnos_planilla`.
- `sedes_horarios.sede_id` protege la sede mientras tenga horarios registrados.
- Las clases concretas son independientes de las celdas de planilla. Eliminar una celda no modifica las clases ni su indicador de origen.
- `eventos.turno_id` protege al turno. Las especializaciones `reservas`, `clases` y `bloqueos` protegen su evento.
- Las relaciones de invitados protegen reserva, usuario y contratación aplicada; quitar un invitado elimina la relación y conserva su historia en auditoría, mientras que rechazar conserva la relación con su respuesta. Las respuestas de alumnos conservan su identidad al reactivar.
- `bloqueos.evento_origen_id` protege al evento de origen mientras exista la referencia de trazabilidad.
- `log_auditoria.usuario_id` protege la cuenta del actor; el historial no admite modificación ni eliminación.
- `intentos_auditoria.usuario_id` protege la cuenta del actor autenticado; el historial de intentos tampoco admite modificación, eliminación ni vaciado.
- Las sesiones de caja protegen al responsable y los movimientos protegen su sesión, responsables y orígenes comerciales. No se ofrecen eliminaciones físicas. Los vínculos comerciales apuntan a las contrataciones concretas o a la reserva. La protección de historia se valida en servicios y ambas tablas participan de la auditoría transversal; no hay triggers adicionales de inmutabilidad sobre caja.

Las clases manuales y generadas no admiten eliminación física desde la aplicación. La anulación conserva la clase, su evento y sus asignaciones conforme a criterios, 2.1 y 2.12. Los turnos pueden ser compartidos por eventos históricos.
