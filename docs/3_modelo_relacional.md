# Modelo relacional para PostgreSQL

## 1. Propósito

Este documento describe cómo se representan los datos de Academia TM en PostgreSQL 17: tablas, atributos, claves, dominios, restricciones, datos derivados y dependencias referenciales. Incluye los campos físicos aportados por Django y las decisiones de normalización del modelo.

Las reglas de negocio, permisos, validaciones de operaciones, confirmaciones y procesos automáticos se definen en `2_criterios_del_sistema.md`.

---

## 2. Convenciones generales

### 2.1 Nombres e identificadores

- Tablas y columnas utilizan `snake_case`; los nombres de tablas están en plural.
- Las claves primarias simples son `bigint GENERATED ALWAYS AS IDENTITY`.
- Las tablas de relación utilizan claves primarias compuestas cuando corresponde.
- Las claves foráneas terminan en `_id`.

### 2.2 Fechas, horas e importes

- Fechas civiles: `date`.
- Horas operativas: `time without time zone`.
- Auditoría: `timestamptz`.
- Importes: `numeric(12,2)`, no negativos para precios y positivos para movimientos.
- La interpretación local de fechas y horas utiliza `America/Argentina/Buenos_Aires`.

### 2.3 Dominios y auditoría

Los estados, modalidades, superficies, tipos de pase y medios de pago tienen dominios cerrados, indicados en las tablas y representados mediante opciones de Django. Los roles tienen su propio catálogo, referenciado por clave foránea.

Las tablas de actividades concentran `creado_en` y `actualizado_en` en `eventos`. Las entidades mutables y las asignaciones con estado conservan sus propias marcas; `actualizado_en` registra automáticamente la última modificación del registro. Los vínculos inmutables no requieren una fecha de modificación. Las referencias a responsables de registro, anulación y finalización son datos de auditoría separados de las asignaciones de participantes.

### 2.4 Credenciales

`usuarios.password` contiene el hash generado por Django, con algoritmo PBKDF2 con SHA-256 (`pbkdf2_sha256`), salt y número de iteraciones. La base no almacena contraseñas en texto plano. La recuperación no necesita una tabla de tokens; su representación se explica en 4.25.

### 2.5 Columnas `Nullable` y `Unique`

En las tablas, ambas columnas muestran `Sí` cuando aplica y quedan vacías en caso contrario. `Unique` identifica unicidad sobre una sola columna, incluidas comparaciones normalizadas; no repite la unicidad implícita de una clave primaria. Las claves y restricciones compuestas se describen junto a cada tabla.

---

## 3. Organización del modelo

La ocupación se representa mediante `turnos`, `eventos` y tres especializaciones excluyentes: `reservas`, `clases` y `bloqueos`. El turno contiene la ubicación temporal y física; el evento contiene el tipo, estado y auditoría; la especialización contiene sus atributos particulares. Cada entidad tiene un identificador propio.

La programación semanal se representa con `turnos_planilla` y sus asignaciones. Las clases concretas tienen asignaciones y asistencia propias, por lo que su historia no depende del contenido vigente de la planilla. Los roles de cuenta y las funciones de una persona dentro de una clase son datos distintos.

Planes y pases se modelan como catálogos independientes, con tablas separadas de contrataciones. Los ingresos referencian operaciones concretas y no productos del catálogo. Los precios aplicados se conservan en las contrataciones y reservas; los importes cobrados pertenecen a `ingresos`.

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
| | `first_name` | `varchar(150)` | | | `Martina` |
| | `last_name` | `varchar(150)` | | | `Gómez` |
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

`email` y `username` tienen unicidad sin distinción de mayúsculas mediante restricciones funcionales sobre `LOWER(email)` y `LOWER(username)`. `celular_contacto` no es único y contiene la representación internacional E.164. Las columnas heredadas de nombre y apellido admiten 150 caracteres. `observaciones` admite cadena vacía, sin `NULL`.

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

El nombre tiene unicidad parcial entre filas con `estado = 'activo'`. Las contrataciones se almacenan en `planes_usuarios`; esta tabla no contiene alumnos, asignaciones ni cobros.

### 4.6 `pases`

Representa la definición comercial de un pase mensual de cancha.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `18` |
| | `nombre` | `varchar(150)` | | | `Pase libre` |
| | `descripcion` | `text` | | | `Acceso todos los días` |
| | `tipo` | `varchar(15)` | | | `libre` (o `fin_de_semana`) |
| | `limite_horas_diarias` | `smallint` | | | `2` |
| | `precio_vigente` | `numeric(12,2)` | | | `35000.00` |
| | `precio_invitado_vigente` | `numeric(12,2)` | | | `1500.00` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |

`tipo` admite `libre` o `fin_de_semana`; no existe una tabla adicional de días por pase. `limite_horas_diarias` es positivo y los precios son no negativos. `descripcion` admite cadena vacía.

El nombre tiene unicidad parcial entre pases Activos, independiente de los nombres de planes. El saldo de horas no es un atributo almacenado del catálogo ni de sus contrataciones.

### 4.7 `planes_usuarios`

Representa una contratación concreta de un plan por un usuario para un mes calendario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `301` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `plan_id` | `bigint` | | | `12` |
| | `mes_cubierto` | `date` | | | `2026-10-01` |
| | `fecha_alta` | `date` | | | `2026-10-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `42750.00` |
| FK | `registrado_por_id` | `bigint` | Sí | | `4` |
| | `observaciones` | `text` | | | `Importe acordado con descuento` |
| | `estado` | `varchar(10)` | | | `activo` (o `anulado`, `vencido`) |
| | `aviso_vencimiento_enviado` | `boolean` | | | `false` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |

`usuario_id` y `plan_id` son referencias obligatorias. `mes_cubierto` contiene el primer día del mes; el inicio y fin de cobertura se derivan de ese valor. `fecha_alta` representa la fecha efectiva y `creado_en` el momento de carga, que pueden ser distintos.

`precio_aplicado` conserva el importe mensual acordado, separado del dinero cobrado. No es una referencia al precio vigente del catálogo. Una restricción única parcial sobre `(usuario_id, mes_cubierto)` para estados `activo` o `vencido` preserva la exclusividad del mes y admite conservar filas Anuladas.

`registrado_por_id` referencia al responsable de una carga manual y queda nulo en altas automáticas por MercadoPago. Los campos de anulación están informados sólo en estado `anulado`: responsable y momento no nulos y motivo no vacío. En los demás estados quedan nulos o vacíos, según su tipo. `observaciones` y `motivo_anulacion` admiten cadena vacía, sin `NULL`.

`aviso_vencimiento_enviado` conserva la marca de envío de esa contratación. No se duplican en esta tabla asignaciones, asistencia ni importes cobrados.

### 4.8 `pases_usuarios`

Representa una contratación concreta de un pase por un usuario para un mes calendario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `340` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `pase_id` | `bigint` | | | `18` |
| | `mes_cubierto` | `date` | | | `2026-10-01` |
| | `fecha_alta` | `date` | | | `2026-10-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `35000.00` |
| FK | `registrado_por_id` | `bigint` | Sí | | `4` |
| | `observaciones` | `text` | | | `Pase contratado en sede` |
| | `estado` | `varchar(10)` | | | `activo` (o `anulado`, `vencido`) |
| | `aviso_vencimiento_enviado` | `boolean` | | | `false` |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 11:00:00-03` |

Utiliza la misma representación de mes cubierto, fecha efectiva, importe aplicado, auditoría y estados que 4.7, con referencia obligatoria a `pases.id`. Tiene su propia restricción única parcial sobre `(usuario_id, mes_cubierto)` entre Activos o Vencidos; no comparte esa restricción con `planes_usuarios`.

La cobertura aplicada queda referenciada desde `reservas.pase_usuario_id` o `reservas_invitados.pase_usuario_id`. El uso diario se deriva de esas referencias y de los eventos de reservas no Anulados, sin almacenar un saldo de horas ni una tabla de consumos separada.

### 4.9 Precios vigentes e importes aplicados

Los valores vigentes se almacenan en los catálogos o la sede. Sus copias aplicadas pertenecen a las contrataciones y reservas correspondientes.

| Precio vigente | Importe conservado |
|---|---|
| `planes.precio_vigente` | `planes_usuarios.precio_aplicado` |
| `pases.precio_vigente` | `pases_usuarios.precio_aplicado` |
| `sedes.precio_reserva_vigente` | `reservas.precio_por_turno_aplicado` |
| `pases.precio_invitado_vigente` | `reservas.precio_invitado_aplicado` |

El modelo no tiene una tabla de historial de precios. La historia comercial se representa mediante los importes aplicados, mientras que los movimientos de dinero utilizan `ingresos`.

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
| | `modalidad` | `varchar(15)` | Sí | | `grupal` (o `individual`) |
| | `observaciones` | `text` | Sí | | `Cancha techada en invierno` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 15:00:00-03` |

La combinación `cancha_id, dia_semana, hora_inicio` es única. `dia_semana` utiliza valores de uno a siete y `hora_inicio` contiene una hora en punto. La sede se obtiene de la cancha.

No existe una entidad de planilla por mes ni una tabla de versiones: las asignaciones previstas utilizan `turnos_planilla_profesores` y `turnos_planilla_alumnos`. La referencia opcional de una clase a esta celda indica procedencia, no una copia histórica de la programación.

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

Cada evento tiene exactamente una especialización en `reservas`, `clases` o `bloqueos`, coherente con `tipo`. Los `evento_id` de esas tablas son únicos. Cancha, fecha y hora pertenecen a `turnos` y no se duplican en el evento ni en sus especializaciones.

La coherencia de estado y auditoría es:

- `programado`: sin responsable, momento o motivo de anulación ni momento de finalización.
- `anulado`: con responsable, momento y motivo de anulación; sin momento de finalización.
- `finalizado`: con momento de finalización y sin datos de anulación; sólo corresponde a reservas y clases.

`observaciones` y `motivo_anulacion` admiten cadena vacía, sin `NULL`. Las referencias a usuarios identifican responsables de registro y anulación. La responsabilidad de finalización manual de una clase se representa en `clases.finalizado_por_id`; no hay una columna equivalente para reservas.

### 4.15 `clases`

Contiene la especialización de un evento de tipo clase.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `700` |
| FK | `evento_id` | `bigint` | | Sí | `1200` |
| FK | `turno_planilla_id` | `bigint` | Sí | | `55` |
| | `es_generada` | `boolean` | | | `true` |
| | `modalidad` | `varchar(15)` | Sí | | `grupal` (o `individual`) |
| FK | `finalizado_por_id` | `bigint` | Sí | | `NULL` |

`evento_id` es único y referencia un evento de tipo `clase`. Estado, ubicación, observaciones y marcas de auditoría comunes se obtienen de ese evento y su turno. Profesores, participantes y asistencia se representan en tablas dependientes.

`es_generada` distingue el origen en la planilla. `turno_planilla_id` es opcional: es nulo para clases manuales o cuando se elimina la celda de origen. El indicador de origen conserva su valor aunque esa referencia quede nula. Las asignaciones de la clase concreta conservan su propia información.

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
| | `recordatorio_enviado` | `boolean` | | | `false` |
| | `creado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-02 10:00:00-03` |

La clave primaria compuesta `(clase_id, usuario_id)` impide repetir una asignación. `usuario_id` referencia a la persona directamente, sin depender de su rol de cuenta ni de una contratación. Se mantiene separada de `clases_profesores` y de la asistencia efectiva.

`estado` representa la vigencia de la asignación. `recordatorio_enviado` es una marca por participante y clase, no por clase completa; permite representar envíos independientes. `observaciones` y las fechas de auditoría pertenecen al vínculo.

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
| FK | `pase_usuario_id` | `bigint` | Sí | | `340` |
| | `cantidad_invitados` | `integer` | Sí | | `3` |
| | `precio_invitado_aplicado` | `numeric(12,2)` | Sí | | `1500.00` |
| FK | `reprogramada_desde_id` | `bigint` | Sí | Sí | `1180` |
| | `anulada_por_organizador` | `boolean` | Sí | | `NULL` |

`evento_id` es único y referencia un evento de tipo `reserva`. `organizador_id` referencia al responsable de la reserva, separado del responsable del registro en `eventos.registrado_por_id`. No hay una entidad beneficiario ni un registro de presencia del organizador. El número de reserva se deriva de `id`; la fecha de registro pertenece al evento.

Exactamente uno de `precio_por_turno_aplicado` y `pase_usuario_id` está informado:

- Normal: precio por turno positivo aplicado; `pase_usuario_id`, cantidad de invitados y precio adicional nulos.
- Con pase: referencia a `pases_usuarios`, cantidad total de invitados no negativa y precio adicional unitario no negativo; `precio_por_turno_aplicado` nulo.

El total no se almacena. En una reserva normal se deriva del precio por turno aplicado; con pase se deriva del precio adicional aplicado y de la cantidad de invitados sin cobertura, incluidos los no identificados. Los invitados identificados se representan en `reservas_invitados`.

`reprogramada_desde_id` es una referencia opcional y única a otra fila de `reservas`; representa una cadena de reemplazos con un máximo de un sucesor por reserva. La reserva de origen tiene evento Anulado administrativamente.

`anulada_por_organizador` es nulo mientras el evento no esté Anulado; vale `true` para la anulación del organizador y `false` para la administrativa. Los demás datos de anulación pertenecen al evento.

### 4.20 `reservas_invitados`

Representa usuarios identificados como invitados de una reserva con pase y su cobertura aplicada.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `reserva_id` | `bigint` | | | `1200` |
| PK, FK | `usuario_id` | `bigint` | | | `9` |
| FK | `pase_usuario_id` | `bigint` | Sí | | `340` |
| | `creado_en` | `timestamptz` | | | `2026-10-02 17:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-02 17:00:00-03` |

La clave primaria compuesta `(reserva_id, usuario_id)` impide repetir al invitado dentro de una reserva. `pase_usuario_id` referencia la contratación concreta del invitado y es nulo cuando no hay cobertura aplicada. La tabla no contiene invitados anónimos: su cantidad se deriva de `reservas.cantidad_invitados` y del número de filas identificadas.

La coherencia del vínculo exige una reserva con pase, un usuario distinto del organizador y una cantidad de filas no superior a la cantidad total declarada. Una contratación aplicada pertenece al usuario de la fila. Las reglas temporales, de coincidencias y cobertura se definen en criterios, 2.2 y 2.4.

### 4.21 `ingresos`

Representa un movimiento de dinero recibido con un único origen comercial.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `5000` |
| | `pagado_en` | `timestamptz` | | | `2026-10-02 17:10:00-03` |
| | `monto` | `numeric(12,2)` | | | `35000.00` |
| | `medio_pago` | `varchar(20)` | | | `efectivo` (o `transferencia`, `debito`, `credito`, `qr`, `mercadopago`) |
| FK | `registrado_por_id` | `bigint` | Sí | | `4` |
| FK | `plan_usuario_id` | `bigint` | Sí | | `301` |
| FK | `pase_usuario_id` | `bigint` | Sí | | `NULL` |
| FK | `reserva_id` | `bigint` | Sí | | `NULL` |
| | `concepto_otro` | `text` | Sí | | `NULL` |
| | `observaciones` | `text` | | | `Pago parcial` |
| | `estado` | `varchar(10)` | | | `cobrado` (o `anulado`) |
| FK | `anulado_por_id` | `bigint` | Sí | | `NULL` |
| | `anulado_en` | `timestamptz` | Sí | | `NULL` |
| | `motivo_anulacion` | `text` | | | `''` |
| | `creado_en` | `timestamptz` | | | `2026-10-02 17:10:00-03` |

Exactamente uno de `plan_usuario_id`, `pase_usuario_id`, `reserva_id` y `concepto_otro` está informado. Las referencias apuntan a contrataciones concretas o a una reserva, no a los productos del catálogo. `concepto_otro` informado contiene texto no vacío. `monto` es positivo.

`pagado_en` representa el momento del cobro; `creado_en`, el momento de carga. `registrado_por_id` es nulo para ingresos automáticos por MercadoPago. Los datos de anulación están informados sólo con `estado = 'anulado'`; responsable y momento son no nulos y el motivo no está vacío. En estado `cobrado` esos campos quedan nulos o vacíos según su tipo.

El total cobrado, pendiente, excedente y estado de pago son valores derivados, no columnas: se obtienen del total aplicado del origen y de sus ingresos Cobrado. `observaciones` conserva las aclaraciones del movimiento, incluido el motivo de excedente cuando corresponde.

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

### 4.23 `pagos_mercadopago`

Representa un intento de pago online y sus resultados persistidos.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `501` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `plan_id` | `bigint` | Sí | | `12` |
| FK | `pase_id` | `bigint` | Sí | | `NULL` |
| | `mes_cubierto` | `date` | | | `2026-10-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `42750.00` |
| | `referencia_externa` | `uuid` | | Sí | `b3f1...` |
| | `preference_id` | `varchar(120)` | | Sí | `123456789-abcd...` |
| | `payment_id` | `varchar(120)` | Sí | Sí | `987654321` |
| | `estado` | `varchar(20)` | | | `aprobado` (o `pendiente`, `rechazado`) |
| FK | `plan_usuario_id` | `bigint` | Sí | | `301` |
| FK | `pase_usuario_id` | `bigint` | Sí | | `NULL` |
| FK | `ingreso_id` | `bigint` | Sí | | `5000` |
| | `creado_en` | `timestamptz` | | | `2026-10-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-10-01 10:05:00-03` |

Exactamente uno de `plan_id` y `pase_id` está informado. `mes_cubierto` es el primer día del mes y `precio_aplicado` conserva el importe del intento. `referencia_externa` es un UUID propio del sistema; `preference_id` identifica el checkout y `payment_id`, nullable, el pago comunicado por la plataforma. Los tres identificadores tienen unicidad individual.

Dos restricciones únicas parciales evitan duplicar intentos Pendientes para el mismo usuario, producto y mes: una sobre `(usuario_id, plan_id, mes_cubierto)` con plan informado y otra sobre `(usuario_id, pase_id, mes_cubierto)` con pase informado.

Los resultados se representan mediante `plan_usuario_id`, `pase_usuario_id` e `ingreso_id`. Antes de aplicar una aprobación, las tres referencias son nulas. Una aprobación aplicada tiene exactamente una contratación, coherente con producto, usuario y mes del intento, y un ingreso relacionado. Un intento Aprobado sin resultados representa una aplicación pendiente de resolución administrativa; Pendiente o Rechazado no tiene resultados. El procesamiento se define en criterios, 2.4.1.

### 4.24 `bloqueos`

Representa un bloqueo de un turno y su vínculo opcional con la actividad anulada que originó su creación.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `40` |
| FK | `evento_id` | `bigint` | | Sí | `1400` |
| | `motivo` | `varchar(20)` | | | `clima_adverso` (o `torneo`, `mantenimiento`) |
| FK | `evento_origen_id` | `bigint` | Sí | Sí | `1300` |

`evento_id` es único y referencia un evento de tipo `bloqueo`. El turno, estado, observaciones y auditoría pertenecen al evento. `motivo` admite `clima_adverso`, `torneo` y `mantenimiento`. La especialización no agrega un estado ni una ubicación propios; su evento admite `programado` y `anulado`, sin `finalizado`.

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

La función `registrar_auditoria` recibe los nombres de los componentes de la PK mediante los argumentos del trigger. Cada tabla de negocio tiene un trigger de fila `AFTER UPDATE OR DELETE`. La función usa `OLD` y `NEW`, descarta cambios sin diferencias funcionales, excluye secretos e inserta el historial dentro de la misma transacción. El actor, origen, UUID y acción específica se leen de configuración local; sin contexto se registra origen SQL y la base genera el UUID de la transacción. Un trigger independiente rechaza modificación, eliminación y vaciado de `log_auditoria`. Las reglas de contexto y consulta se definen en criterios, 2.14.

---

## 5. Dependencias referenciales y eliminación

- Las referencias a usuarios, sedes, canchas, productos y contrataciones protegen los registros que tienen datos dependientes. Cada contratación referencia obligatoriamente a su usuario y producto.
- `usuarios_roles` utiliza cascada desde `usuarios`; `rol_id` protege el registro del catálogo mientras tenga asignaciones.
- `turnos_planilla_profesores` y `turnos_planilla_alumnos` utilizan cascada desde `turnos_planilla`.
- `sedes_horarios.sede_id` protege la sede mientras tenga horarios registrados.
- `clases.turno_planilla_id` utiliza `ON DELETE SET NULL`: la eliminación de una celda de planilla no elimina las clases concretas ni su indicador de origen.
- `eventos.turno_id` protege al turno. Las especializaciones `reservas`, `clases` y `bloqueos` protegen su evento.
- `bloqueos.evento_origen_id` protege al evento de origen mientras exista la referencia de trazabilidad.
- `log_auditoria.usuario_id` protege la cuenta del actor; el historial no admite modificación ni eliminación.
- Los intentos de MercadoPago protegen las referencias a usuario, producto, contrataciones e ingreso resultantes.

La eliminación coordinada de los datos de una clase generada y la conservación de historia se definen en criterios, 2.1 y 2.12. Los turnos no dependen de la vida de una única actividad: su identidad puede ser compartida por eventos históricos.
