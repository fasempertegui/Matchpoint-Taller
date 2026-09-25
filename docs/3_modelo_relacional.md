# Modelo relacional para PostgreSQL

## 1. Propósito

Este documento transforma las decisiones de `1_organizacion.md` y `2_criterios_del_sistema.md` en una estructura relacional orientada a PostgreSQL 17: tablas de negocio, columnas, claves, restricciones e integridad transaccional. Incluye los detalles físicos que determina Django cuando forman parte del esquema y no define contratos de API.

---

## 2. Convenciones generales

### 2.1 Nombres e identificadores

- Tablas y columnas utilizarán `snake_case` y nombres en plural para tablas.
- Las claves primarias simples serán `bigint GENERATED ALWAYS AS IDENTITY`.
- Las tablas de relación utilizarán claves primarias compuestas cuando corresponda.
- Las claves foráneas terminarán en `_id`.

### 2.2 Fechas, horas e importes

- Fechas civiles: `date`.
- Horas operativas: `time without time zone`.
- Auditoría: `timestamptz`.
- Importes: `numeric(12,2)` no negativo para precios y positivo para movimientos.
- La zona horaria funcional será `America/Argentina/Buenos_Aires`.

### 2.3 Valores fijos y auditoría

Los estados, modalidades, superficies, tipos de pase y medios de pago se validan mediante las opciones definidas en Django antes de guardar. Los roles se almacenan en un catálogo fijo `roles`, referenciado mediante una clave foránea desde `usuarios_roles`. Las tablas mutables tienen `creado_en` y `actualizado_en`; Django mantiene automáticamente la segunda marca al guardar cada registro.

### 2.4 Contraseñas

Se utiliza el hash predeterminado de Django: PBKDF2 con SHA-256 (`pbkdf2_sha256`). Django genera y verifica el hash, incluyendo el salt y el número de iteraciones, mediante su sistema de autenticación. La base nunca almacena la contraseña en texto plano.

El campo físico es `usuarios.password`, de tipo `varchar(128)`. La recuperación utiliza el mecanismo nativo de Django, sin una tabla de tokens (ver 4.25).

### 2.5 Columnas `Nullable` y `Unique`

En las tablas de la sección 4, ambas columnas solo muestran `Sí` cuando aplica; se dejan vacías en caso contrario. `Unique` marca reglas de unicidad sobre una sola columna, incluidas las que comparan su valor normalizado, distintas de la clave primaria (que ya implica unicidad y se identifica en `Clave`). Las restricciones de unicidad que abarcan más de una columna se describen en el texto debajo de cada tabla.

---

## 3. Extensiones de PostgreSQL

Se habilitará `btree_gist` para aplicar una restricción de exclusión que impida eventos superpuestos en una misma cancha.

---

## 4. Tablas

### 4.1 `usuarios`

Representa a toda persona gestionada por la academia —alumno, profesor, administrador o simplemente alguien que reserva una cancha—, siempre con credenciales propias.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `password` | `varchar(128)` | | | `pbkdf2_sha256$...` |
| | `last_login` | `timestamptz` | Sí | | `2026-03-18 09:30:00-03` |
| | `is_superuser` | `boolean` | | | `false` |
| | `username` | `varchar(150)` | | Sí | `gomezm` |
| | `first_name` | `varchar(150)` | | | `Martina` |
| | `last_name` | `varchar(150)` | | | `Gómez` |
| | `email` | `varchar(254)` | | Sí | `martina.gomez@gmail.com` |
| | `is_staff` | `boolean` | | | `false` |
| | `is_active` | `boolean` | | | `true` |
| | `fecha_baja` | `timestamptz` | Sí | | `2026-03-20 18:45:00-03` |
| | `debe_cambiar_contrasena` | `boolean` | | | `true` |
| | `date_joined` | `timestamptz` | | | `2026-03-01 10:15:00-03` |
| | `fecha_nacimiento` | `date` | Sí | | `1998-04-12` |
| | `celular_contacto` | `varchar(30)` | | | `+54 387 555-1234` |
| | `observaciones` | `text` | | | `Celular es de la madre` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-01 10:15:00-03` |

`Usuario` hereda de `AbstractUser`; por eso `password`, `last_login`, `is_superuser`, `username`, `first_name`, `last_name`, `is_staff`, `is_active` y `date_joined` son columnas físicas de `usuarios`. `date_joined` registra el alta, `actualizado_en` la última modificación y `fecha_baja` el momento de la inactivación. Una cuenta activa conserva `fecha_baja = NULL`. `observaciones` admite una cadena vacía, pero no `NULL`.

PostgreSQL garantiza la unicidad de `email` y `username` sin distinguir mayúsculas de minúsculas mediante restricciones funcionales sobre `LOWER(email)` y `LOWER(username)`. Los formularios comprueban la disponibilidad del email antes de guardar. En el alta administrativa y el autorregistro, el sistema genera `username` combinando el apellido normalizado con la inicial del nombre y agrega un sufijo numérico desde `1` cuando la combinación ya existe. El nombre generado se muestra sin permitir su edición y se confirma al guardar. `celular_contacto` no es único. `is_active` determina si la cuenta puede autenticarse. `is_superuser` vale `true` para las cuentas con el rol Administrador y permite que el sistema de permisos de Django les conceda acceso total. `is_staff` permanece en `false`, garantizado por la restricción `usuarios_is_staff_false`, porque la aplicación no expone la interfaz administrativa técnica de Django.

`debe_cambiar_contrasena` indica que la contraseña vigente fue establecida por otra persona durante el alta administrativa, la creación mediante `crear_administrador` o un restablecimiento, y es provisoria. Mientras vale `true`, la sesión queda restringida al cambio o recuperación de contraseña y al cierre de sesión. El sistema guarda el hash de la contraseña elegida por la persona y cambia la marca a `false` en la misma transacción. El restablecimiento administrativo solo puede aplicarse a otro usuario; para la cuenta propia se utiliza el cambio de contraseña o la recuperación.

Los atributos heredados `groups` y `user_permissions` son relaciones muchos a muchos, no columnas de `usuarios`. Django las almacena en las tablas intermedias `usuarios_groups` y `usuarios_user_permissions`; sirven para sus permisos de autenticación y son independientes de los roles funcionales de `roles` y `usuarios_roles`.

Al inactivar una cuenta, la aplicación establece `is_active = false` y registra `fecha_baja` con el momento actual. Al reactivarla, establece `is_active = true` y limpia `fecha_baja`. La operación bloquea las filas de los administradores activos dentro de la misma transacción y se rechaza si el actor intenta desactivar su propia cuenta o si la cuenta objetivo es el único administrador activo. Así, las solicitudes concurrentes no pueden dejar al sistema sin administradores.

Relaciones:

- Un usuario puede tener uno o varios roles asignados.
- Un rol asignado pertenece a exactamente un usuario.
- Un usuario puede tener cero, una o varias membresías de usuario.
- Una membresía de usuario pertenece a exactamente un usuario.
- Un usuario puede organizar cero, una o varias reservas.
- Una reserva pertenece a exactamente un usuario organizador.
- Un usuario puede ser invitado en cero, una o varias reservas.
- Un invitado de reserva es exactamente un usuario.
- Un usuario puede estar asignado a cero, una o varias clases como alumno.
- Una asignación de alumno pertenece a exactamente un usuario.
- Un usuario puede estar asignado a cero, una o varias clases como profesor.
- Una asignación de profesor pertenece a exactamente un usuario.
- Un usuario puede estar previsto en cero, uno o varios turnos de planilla como alumno.
- Una previsión de alumno pertenece a exactamente un usuario.
- Un usuario puede estar previsto en cero, uno o varios turnos de planilla como profesor.
- Una previsión de profesor pertenece a exactamente un usuario.
- Un usuario puede tener cero, uno o varios registros de asistencia.
- Un registro de asistencia pertenece a exactamente un usuario.
- Un usuario puede tener cero, uno o varios intentos de pago con MercadoPago.
- Un intento de pago con MercadoPago pertenece a exactamente un usuario.

### 4.2 `roles` y `usuarios_roles`

#### Catálogo `roles`

Catálogo fijo cargado por migración, sin altas, modificaciones ni bajas desde la aplicación.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `5` |
| | `codigo` | `varchar(20)` | | Sí | `publico` |
| | `nombre` | `varchar(50)` | | | `Público` |

Contiene Administrador (`administrador`), Profesor (`profesor`), Alumno (`alumno`), Reservas (`reservas`) y Público (`publico`). El código permite identificar el rol en las reglas de negocio sin depender de un número de fila. La integridad referencial depende de la clave foránea a `roles.id`, no de un enum.

#### Asignaciones `usuarios_roles`

Representa que un usuario tiene asignado uno de los roles del catálogo cerrado del sistema.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `12` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `rol_id` | `bigint` | | | `2` |
| FK | `asignado_por_id` | `bigint` | Sí | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-03-01 10:15:00-03` |

La restricción única `(usuario_id, rol_id)` impide repetir una asignación. `rol_id` referencia `roles.id`: no acepta roles inexistentes y Django protege contra el borrado de roles referenciados. Público y Reservas se asignan automáticamente en la misma transacción del alta. Público no puede retirarse; Reservas, Profesor y Alumno se gestionan según las condiciones de FL-07. Alumno también puede otorgarse automáticamente (ver sección 6).

Para eliminar una asignación de `usuarios_roles`, se aplican estas reglas entre tablas:

- **Público:** se rechaza siempre su retiro.
- **Reservas:** se rechaza si existe una fila de `reservas` cuyo `usuario_id` sea el titular y cuyo evento relacionado tenga `estado = 'programado'`.
- **Alumno:** se rechaza si existe una fila de `membresias_usuarios` del titular con `estado = 'activa'`, tanto si corresponde a un plan como a un pase.
- **Profesor:** se rechaza si existe una fila de `clases_profesores` del usuario con `estado = 'activo'`, vinculada a una clase cuyo evento tenga `estado = 'programado'`.

La comprobación y el retiro forman una única operación transaccional, coordinada con las operaciones que crean o reactivan esas relaciones para impedir que una escritura concurrente invalide la comprobación. Un rechazo conserva la asignación y no modifica las reservas, membresías ni clases. El retiro permitido conserva sus registros históricos y no elimina ninguna fila del catálogo `roles`.

Administrador es un rol funcional almacenado en `usuarios_roles`, igual que los demás roles del catálogo. Una cuenta activa con esa asignación mantiene `is_superuser = true`, por lo que Django le concede todos los permisos; los usuarios sin el rol conservan el comportamiento normal de permisos individuales y por grupos. El comando `crear_administrador` crea la cuenta con contraseña provisoria, activa `debe_cambiar_contrasena` e `is_superuser`, y registra su asignación en una sola transacción. La aplicación no permite otorgar ni retirar Administrador desde sus pantallas.

Los roles funcionales expresan la forma en que cada persona participa en el negocio. Los permisos técnicos de Django expresan qué operaciones puede ejecutar una cuenta sobre los modelos y se almacenan en las tablas de autenticación. No existe una relación `roles_permisos`: Administrador obtiene todos los permisos mediante `is_superuser`, mientras que Profesor, Alumno, Reservas y Público habilitan sus funciones mediante comprobaciones del rol correspondiente.

En el DER, `roles` se relaciona uno a muchos con `usuarios_roles`, y `usuarios` también se relaciona uno a muchos con `usuarios_roles`. Cada asignación referencia al usuario y al rol mediante sus claves foráneas.

Relaciones:

- Un rol asignado pertenece a exactamente un usuario.
- Un usuario puede tener uno o varios roles asignados.

### 4.3 `sedes`

Representa una sede física donde opera la academia.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `nombre` | `varchar(120)` | | Sí | `Sociedad Española` |
| | `direccion` | `varchar(250)` | | | `Av. Sarmiento 320` |
| | `observaciones` | `text` | Sí | | `Ingreso por calle lateral` |
| | `estado` | `varchar(10)` | | | `activa` (o `inactiva`) |
| | `creado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |

PostgreSQL garantiza la unicidad de `nombre` sin distinguir mayúsculas de minúsculas mediante una restricción funcional sobre `LOWER(nombre)`; por ejemplo, no permite registrar `CENTRO` cuando ya existe `Centro`. El formulario aplica la misma comparación para informar el conflicto antes de guardar.

Relaciones:

- Una sede puede tener cero, una o varias canchas.
- Una cancha pertenece a exactamente una sede.
- Una sede puede tener cero a siete horarios de funcionamiento, uno por día de la semana.
- Un horario de funcionamiento pertenece a exactamente una sede.

### 4.4 `canchas`

Representa una cancha disponible dentro de una sede.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| FK | `sede_id` | `bigint` | | | `1` |
| | `nombre` | `varchar(120)` | | | `Cancha 1` |
| | `superficie` | `varchar(30)` | | | `cemento` (o `polvo_ladrillo`) |
| | `observaciones` | `text` | Sí | | `Con luminaria` |
| | `estado` | `varchar(10)` | | | `activa` (o `inactiva`) |
| | `creado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |

PostgreSQL garantiza la unicidad de la combinación `sede_id, LOWER(nombre)`, por lo que no admite nombres equivalentes sin distinguir mayúsculas de minúsculas dentro de una misma sede. El formulario aplica la misma comparación para informar el conflicto antes de guardar. Dos sedes diferentes sí pueden tener canchas con el mismo nombre. La sede se obtiene siempre a través de la cancha; no se duplica en otras tablas.

Relaciones:

- Una cancha pertenece a exactamente una sede.
- Una sede puede tener cero, una o varias canchas.
- Una cancha puede tener cero, uno o varios turnos de planilla.
- Un turno de planilla pertenece a exactamente una cancha.
- Una cancha puede tener cero, uno o varios eventos.
- Un evento pertenece a exactamente una cancha.

### 4.5 `membresias`

Representa una membresía mensual ofrecida por la academia: un plan de clases o un pase de cancha. Cada fila es la cabecera comercial (nombre y precio); el detalle específico vive en `planes` o `pases`.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `12` |
| | `nombre` | `varchar(150)` | | | `Grupal 3 veces por semana` |
| | `descripcion` | `text` | | | `Clases grupales de una hora, lunes/miércoles/viernes` |
| | `precio_vigente` | `numeric(12,2)` | | | `45000.00` |
| | `estado` | `varchar(10)` | | | `activa` (o `inactiva`) |
| | `creado_en` | `timestamptz` | | | `2026-01-10 12:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-01-10 12:00:00-03` |

`nombre` es único entre membresías activas. Cada fila tendrá exactamente un subtipo (`planes` o `pases`).

Relaciones:

- Una membresía se completa con exactamente un plan o un pase.
- Un plan completa exactamente una membresía.
- Un pase completa exactamente una membresía.
- Una membresía puede estar asociada a cero, una o varias membresías de usuarios.
- Una membresía de usuario pertenece a exactamente una membresía.
- Una membresía puede estar asociada a cero, uno o varios intentos de pago con MercadoPago.
- Un intento de pago con MercadoPago referencia exactamente una membresía del catálogo.

### 4.6 `planes`

Representa la configuración propia de una membresía de plan de clases. Cada combinación de modalidad, frecuencia y duración es una membresía distinta en el catálogo.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `membresia_id` | `bigint` | | | `12` |
| | `modalidad` | `varchar(15)` | | | `grupal` (o `individual`) |
| | `frecuencia_semanal` | `smallint` | | | `3` (entre 1 y 7) |
| | `cantidad_clases_por_encuentro` | `smallint` | | | `1` (o `2`) |

Relaciones:

- Un plan completa exactamente una membresía.
- Una membresía se completa, cuando corresponde, con exactamente un plan.

### 4.7 `pases`

Representa la configuración propia de una membresía de pase de cancha. El pase libre y el pase de fin de semana son dos filas distintas y autónomas del catálogo: el día habilitado es una propiedad fija de cada variante (`tipo`), no un campo configurable aparte.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `membresia_id` | `bigint` | | | `18` |
| | `tipo` | `varchar(15)` | | | `libre` (o `fin_de_semana`) |
| | `limite_horas_diarias` | `smallint` | | | `2` |
| | `precio_invitado_vigente` | `numeric(12,2)` | | | `1500.00` |

`tipo = fin_de_semana` habilita únicamente sábados y domingos; `tipo = libre` habilita todos los días. Esta correspondencia es fija en el sistema, no editable por fila.

Relaciones:

- Un pase completa exactamente una membresía.
- Una membresía se completa, cuando corresponde, con exactamente un pase.

### 4.8 `membresias_usuarios`

Representa que un usuario adquirió una membresía para un mes calendario, con el precio que pagó en ese momento.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `301` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `membresia_id` | `bigint` | | | `12` |
| | `fecha_alta` | `date` | | | `2026-03-01` |
| | `fecha_inicio` | `date` | | | `2026-03-01` |
| | `fecha_fin` | `date` | | | `2026-03-31` |
| | `precio_aplicado` | `numeric(12,2)` | | | `42750.00` |
| FK | `registrada_por_id` | `bigint` | Sí | | `4` |
| | `observaciones` | `text` | Sí | | `Pagó con descuento por adelantado` |
| | `estado` | `varchar(12)` | | | `activa` (o `cancelada`, `vencida`) |
| | `aviso_vencimiento_enviado` | `boolean` | | | `false` |
| | `creado_en` | `timestamptz` | | | `2026-03-01 11:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-01 11:00:00-03` |

`registrada_por_id` queda nulo cuando la fila se creó automáticamente por la confirmación de pago de MercadoPago. `fecha_inicio` es el primer día del mes y `fecha_fin` su último día. El alta bloquea la fila del usuario durante la comprobación de exclusividad y la inserción, por lo que dos altas concurrentes del mismo titular se evalúan de forma serial.

Relaciones:

- Una membresía de usuario pertenece a exactamente un usuario.
- Un usuario puede tener cero, una o varias membresías de usuario.
- Una membresía de usuario pertenece a exactamente una membresía.
- Una membresía puede estar asociada a cero, una o varias membresías de usuarios.
- Una membresía de usuario puede recibir cero, uno o varios ingresos.
- Un ingreso tiene como origen, como máximo, una membresía de usuario.
- Una membresía de usuario de tipo pase puede estar aplicada en cero, una o varias reservas.
- Una reserva con pase utiliza exactamente una membresía de usuario de tipo pase.
- Una membresía de usuario de tipo pase puede estar aplicada a cero, uno o varios invitados de reserva.
- Un invitado de reserva puede tener, como máximo, una membresía de usuario de tipo pase.

### 4.9 `precios_reservas_cancha`

Representa una configuración de precio vigente para una reserva normal, según su duración.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `duracion_horas` | `smallint` | | | `1` |
| | `precio_vigente` | `numeric(12,2)` | | | `8000.00` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `creado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |

Habrá una sola configuración activa por duración. Su estructura no cambia después de ser utilizada.

Relaciones:

- Un precio de reserva puede estar aplicado en cero, una o varias reservas.
- Una reserva normal utiliza, como máximo, un precio de reserva.

### 4.10 `feriados`

Representa una fecha sin dictado de clases, válida por igual para todas las sedes. La usa la generación de clases para omitir esa fecha en los turnos de la planilla que coincidan.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1` |
| | `fecha` | `date` | | Sí | `2026-05-25` |
| | `descripcion` | `varchar(150)` | | | `Feriado nacional` |
| | `creado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |

`fecha` es única: no existe un feriado por sede, rige siempre para todas.

Sin relaciones con otras tablas de negocio; la generación de clases (**7.2**) la consulta directamente por fecha.

### 4.11 `turnos_planilla`

Representa una celda ocupada en la planilla semanal viva de una cancha: un día de la semana y un horario en el que la academia quiere generar clases. No hay una planilla por período: es una única planilla por cancha que se edita en el tiempo. Un turno solo existe mientras forma parte de la planilla; quitarlo lo elimina.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `55` |
| FK | `cancha_id` | `bigint` | | | `1` |
| | `dia_semana` | `smallint` | | | `3` (1 = lunes … 7 = domingo) |
| | `hora_inicio` | `time` | | | `18:00` |
| | `modalidad` | `varchar(15)` | Sí | | `grupal` (o `individual`) |
| | `observaciones` | `text` | Sí | | `Cancha techada en invierno` |
| | `creado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |

La combinación `cancha_id, dia_semana, hora_inicio` es única. La sede se obtiene a través de la cancha.

Relaciones:

- Un turno de planilla pertenece a exactamente una cancha.
- Una cancha puede tener cero, uno o varios turnos de planilla.
- Un turno de planilla puede tener uno o varios profesores previstos.
- Una previsión de profesor pertenece a exactamente un turno de planilla.
- Un turno de planilla puede tener cero, uno o varios usuarios previstos.
- Una previsión de usuario pertenece a exactamente un turno de planilla.
- Un turno de planilla puede haber originado cero, una o varias clases.
- Una clase puede provenir, como máximo, de un turno de planilla.

### 4.12 `turnos_planilla_profesores`

Representa qué profesores están previstos para un turno de la planilla.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `turno_planilla_id` | `bigint` | | | `55` |
| PK, FK | `profesor_id` | `bigint` | | | `4` |
| | `creado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |

`profesor_id` debe pertenecer a un usuario con rol profesor activo.

Relaciones:

- Una previsión de profesor pertenece a exactamente un turno de planilla.
- Un turno de planilla puede tener uno o varios profesores previstos.
- Una previsión de profesor es exactamente un usuario.
- Un usuario puede estar previsto en cero, uno o varios turnos de planilla como profesor.

### 4.13 `turnos_planilla_usuarios`

Representa qué alumnos están previstos para un turno de la planilla.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `turno_planilla_id` | `bigint` | | | `55` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `creado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |

Relaciones:

- Una previsión de usuario pertenece a exactamente un turno de planilla.
- Un turno de planilla puede tener cero, uno o varios usuarios previstos.
- Una previsión de usuario es exactamente un usuario.
- Un usuario puede estar previsto en cero, uno o varios turnos de planilla como alumno.

### 4.14 `eventos`

Representa una utilización concreta y exclusiva de una cancha, en un día y horario determinados: es la tabla base común a clases, reservas y bloqueos.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `900` |
| | `tipo` | `varchar(10)` | | | `clase` (o `reserva`, `bloqueo`) |
| FK | `cancha_id` | `bigint` | | | `1` |
| | `fecha` | `date` | | | `2026-03-04` |
| | `hora_inicio` | `time` | | | `18:00` |
| | `hora_fin` | `time` | | | `19:00` |
| FK | `registrado_por_id` | `bigint` | | | `4` |
| | `motivo_cancelacion` | `text` | Sí | | `Cancha en mantenimiento` |
| | `cancelada_por_usuario` | `boolean` | Sí | | `false` |
| FK | `cancelado_por_id` | `bigint` | Sí | | `4` |
| | `cancelado_en` | `timestamptz` | Sí | | `2026-03-03 09:00:00-03` |
| FK | `completado_por_id` | `bigint` | Sí | | `6` |
| | `completado_en` | `timestamptz` | Sí | | `2026-03-04 19:05:00-03` |
| | `estado` | `varchar(12)` | | | `programado` (o `cancelado`, `completado`) |
| | `creado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-02-20 15:00:00-03` |

`cancelada_por_usuario` solo se completa al cancelar una reserva; queda vacío para clases, bloqueos y para eventos programados o completados. La exclusión GiST sobre `[fecha + hora_inicio, fecha + hora_fin)` impide superposiciones entre eventos no cancelados de una misma cancha — un bloqueo ocupa el turno exactamente igual que una clase o una reserva. `registrado_por_id`, `cancelado_por_id` y `completado_por_id` son referencias de auditoría a `usuarios`, no relaciones de negocio. Toda operación que edita o cambia el estado de un evento bloquea esta fila hasta confirmar la transacción, de modo que cancelación, finalización, cobro y edición no decidan sobre estados obsoletos. `hora_inicio` siempre cae en punto (minutos y segundos en cero); junto con la duración exacta de clases y horas enteras de reservas, garantiza que `hora_fin` también caiga en punto (un bloqueo no tiene esa restricción de duración, solo la de `hora_inicio` en punto). Todo evento comienza y finaliza dentro de la misma fecha: un intervalo que atravesaría la medianoche se rechaza.

Relaciones:

- Un evento pertenece a exactamente una cancha.
- Una cancha puede tener cero, uno o varios eventos.
- Un evento corresponde a exactamente una clase, a exactamente una reserva o a exactamente un bloqueo.
- Una clase pertenece a exactamente un evento.
- Una reserva pertenece a exactamente un evento.
- Un bloqueo pertenece a exactamente un evento.

### 4.15 `clases`

Representa una clase concreta, dictada o a dictarse, de exactamente una hora de duración.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `700` |
| FK | `evento_id` | `bigint` | | Sí | `900` |
| FK | `turno_planilla_id` | `bigint` | Sí | | `55` |
| | `es_generada` | `boolean` | | | `true` |
| | `modalidad` | `varchar(15)` | Sí | | `grupal` (o `individual`) |
| | `observaciones` | `text` | Sí | | `Recupera Martina, faltó el lunes` |
| | `creado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |

`evento_id` es único: el evento debe ser de tipo `clase` y durar exactamente una hora. `es_generada` distingue si la clase se creó por la planilla (`true`) o directamente por un administrador (`false`); la usa la regeneración de un período para saber qué clases puede eliminar y recrear. `turno_planilla_id` queda vacío tanto en clases creadas manualmente como en clases cuyo turno de origen ya fue eliminado de la planilla.

Relaciones:

- Una clase pertenece a exactamente un evento.
- Un evento corresponde, cuando es de tipo clase, a exactamente una clase.
- Una clase puede provenir, como máximo, de un turno de planilla.
- Un turno de planilla puede haber originado cero, una o varias clases.
- Una clase puede tener uno o varios profesores asignados.
- Una asignación de profesor pertenece a exactamente una clase.
- Una clase puede tener cero, uno o varios usuarios asignados como alumnos.
- Una asignación de alumno pertenece a exactamente una clase.
- Una clase puede tener cero, uno o varios registros de asistencia.
- Un registro de asistencia pertenece a exactamente una clase.

### 4.16 `clases_profesores`

Representa qué profesores dictan una clase concreta. Permite cubrir una clase con más de uno.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `profesor_id` | `bigint` | | | `4` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `creado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |

Toda clase debe tener al menos un profesor activo al finalizar la transacción.

Relaciones:

- Una asignación de profesor pertenece a exactamente una clase.
- Una clase puede tener uno o varios profesores asignados.
- Una asignación de profesor es exactamente un usuario.
- Un usuario puede estar asignado a cero, una o varias clases como profesor.

### 4.17 `clases_usuarios`

Representa la asignación prevista de un usuario a una clase concreta, como alumno.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `observaciones` | `text` | Sí | | `Se suma solo por marzo` |
| | `estado` | `varchar(10)` | | | `activo` (o `inactivo`) |
| | `recordatorio_enviado` | `boolean` | | | `false` |
| | `creado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-02-25 10:00:00-03` |

Representa asignación prevista, no asistencia efectiva. `recordatorio_enviado` es por asignación, no por clase, porque el recordatorio se envía a cada alumno individualmente: así un envío fallido o un alumno agregado después no dependen del resto de la clase. Vuelve a `false` si esta asignación pasa de `inactivo` a `activo`.

Relaciones:

- Una asignación de alumno pertenece a exactamente una clase.
- Una clase puede tener cero, uno o varios usuarios asignados.
- Una asignación de alumno es exactamente un usuario.
- Un usuario puede estar asignado a cero, una o varias clases como alumno.

### 4.18 `asistencias`

Representa la asistencia efectiva de un usuario a una clase concreta. Solo puede registrarse o modificarse en estado `presente` o `ausente` cuando el evento de la clase ya está completado.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `clase_id` | `bigint` | | | `700` |
| PK, FK | `usuario_id` | `bigint` | | | `1` |
| | `estado` | `varchar(15)` | | | `presente` (o `ausente`, `sin_registrar`) |
| FK | `registrada_por_id` | `bigint` | Sí | | `6` |
| | `observaciones` | `text` | Sí | | `Llegó sobre la hora` |
| | `registrada_en` | `timestamptz` | Sí | | `2026-03-04 19:04:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-04 19:04:00-03` |

`registrada_en` es obligatorio para `presente` o `ausente`. Admite usuarios no asignados previamente a la clase. `registrada_por_id` es una referencia de auditoría a `usuarios`, no una relación de negocio.

Relaciones:

- Un registro de asistencia pertenece a exactamente una clase.
- Una clase puede tener cero, uno o varios registros de asistencia.
- Un registro de asistencia pertenece a exactamente un usuario.
- Un usuario puede tener cero, uno o varios registros de asistencia.

### 4.19 `reservas`

Representa una reserva normal o con pase, continua e indivisible.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `1200` |
| FK | `evento_id` | `bigint` | | Sí | `901` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `precio_reserva_id` | `bigint` | Sí | | `1` |
| FK | `membresia_pase_id` | `bigint` | Sí | | `301` |
| | `cantidad_invitados` | `integer` | Sí | | `3` |
| | `precio_invitado_aplicado` | `numeric(12,2)` | Sí | | `1500.00` |
| | `precio_aplicado` | `numeric(12,2)` | | | `8000.00` |
| FK | `reprogramada_desde_id` | `bigint` | Sí | Sí | `1180` |
| | `observaciones` | `text` | Sí | | `Cliente pidió cancha techada` |
| | `creado_en` | `timestamptz` | | | `2026-03-02 17:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-02 17:00:00-03` |

Exactamente uno de `precio_reserva_id` y `membresia_pase_id` está informado. `reprogramada_desde_id` se completa cuando esta reserva nace de reprogramar otra cancelada por un motivo ajeno al organizador (ver `2_criterios_del_sistema.md`, 2.2); es único cuando está informado, para que una reserva cancelada no se reprograme dos veces. El organizador, la modalidad, el intervalo y la cancha son inmutables; para cambiarlos se cancela la reserva y se crea otra.

Relaciones:

- Una reserva pertenece a exactamente un evento.
- Un evento corresponde, cuando es de tipo reserva, a exactamente una reserva.
- Una reserva pertenece a exactamente un usuario organizador.
- Un usuario puede organizar cero, una o varias reservas.
- Una reserva normal utiliza, como máximo, un precio de reserva.
- Un precio de reserva puede estar aplicado en cero, una o varias reservas.
- Una reserva con pase utiliza, como máximo, una membresía de usuario de tipo pase.
- Una membresía de usuario de tipo pase puede estar aplicada en cero, una o varias reservas.
- Una reserva puede tener cero, uno o varios invitados identificados.
- Un invitado identificado pertenece a exactamente una reserva.
- Una reserva puede provenir, como máximo, de otra reserva que reprograma.
- Una reserva puede haber sido reprogramada, como máximo, por otra reserva.
- Una reserva puede recibir cero, uno o varios ingresos.
- Un ingreso tiene como origen, como máximo, una reserva.

### 4.20 `reservas_invitados`

Representa a un invitado de una reserva con pase que ya existe como usuario.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `reserva_id` | `bigint` | | | `1200` |
| PK, FK | `usuario_id` | `bigint` | | | `9` |
| FK | `membresia_pase_id` | `bigint` | Sí | | `340` |
| | `creado_en` | `timestamptz` | | | `2026-03-02 17:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-02 17:00:00-03` |

Solo admite reservas con pase. El organizador no puede repetirse como invitado. `membresia_pase_id` vacío indica que el invitado no tiene pase aplicable ese día. La cantidad de filas no supera `reservas.cantidad_invitados`.

Relaciones:

- Un invitado identificado pertenece a exactamente una reserva.
- Una reserva puede tener cero, uno o varios invitados identificados.
- Un invitado identificado es exactamente un usuario.
- Un usuario puede ser invitado en cero, una o varias reservas.
- Un invitado identificado puede tener, como máximo, una membresía de usuario de tipo pase.
- Una membresía de usuario de tipo pase puede estar aplicada a cero, uno o varios invitados de reserva.

### 4.21 `ingresos`

Representa dinero efectivamente recibido por la academia.

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `5000` |
| | `pagado_en` | `timestamptz` | | | `2026-03-02 17:10:00-03` |
| | `monto` | `numeric(12,2)` | | | `8000.00` |
| | `medio_pago` | `varchar(20)` | | | `efectivo` (o `transferencia`, `debito`, `credito`, `qr`, `mercadopago`) |
| FK | `registrado_por_id` | `bigint` | Sí | | `4` |
| FK | `membresia_usuario_id` | `bigint` | Sí | | `301` |
| FK | `reserva_id` | `bigint` | Sí | | `1200` |
| | `concepto_otro` | `text` | Sí | | `Venta de pelotas` |
| | `observaciones` | `text` | Sí | | `Pagó en dos partes` |
| | `estado` | `varchar(10)` | | | `cobrado` (o `anulado`) |
| FK | `anulado_por_id` | `bigint` | Sí | | `4` |
| | `anulado_en` | `timestamptz` | Sí | | `2026-03-03 09:00:00-03` |
| | `motivo_anulacion` | `text` | Sí | | `Cargado dos veces por error` |
| | `creado_en` | `timestamptz` | | | `2026-03-02 17:10:00-03` |

Exactamente una de `membresia_usuario_id`, `reserva_id` y `concepto_otro` está informada. `registrado_por_id` y `anulado_por_id` son siempre un usuario administrador, salvo cuando la fila la generó automáticamente la confirmación de pago de MercadoPago (quedan nulos); son referencias de auditoría, no relaciones de negocio. Este módulo, incluida la anulación, es exclusivo del rol Administrador. Los ingresos registrados no se editan ni se eliminan, solo se anulan.

Relaciones:

- Un ingreso tiene como origen, como máximo, una membresía de usuario.
- Una membresía de usuario puede recibir cero, uno o varios ingresos.
- Un ingreso tiene como origen, como máximo, una reserva.
- Una reserva puede recibir cero, uno o varios ingresos.

### 4.22 `sedes_horarios`

Representa el horario de funcionamiento de una sede: por día de la semana, hasta dos franjas horarias en las que la sede opera. Rige tanto para clases como para reservas, aunque con distinta exigencia: bloqueante para una reserva autogestionada desde el portal, solo advertencia para el administrador (ver `2_criterios_del_sistema.md`, 2).

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK, FK | `sede_id` | `bigint` | | | `1` |
| PK | `dia_semana` | `smallint` | | | `3` (1 = lunes … 7 = domingo) |
| | `hora_inicio_1` | `time` | | | `08:00` |
| | `hora_fin_1` | `time` | | | `12:00` |
| | `hora_inicio_2` | `time` | Sí | | `16:00` |
| | `hora_fin_2` | `time` | Sí | | `22:00` |
| | `creado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-01-05 09:00:00-03` |

`hora_inicio_2` y `hora_fin_2` están ambas presentes o ambas vacías. Un día de la semana sin fila para la sede indica que esa sede no funciona ese día. `hora_fin_1` es siempre posterior a `hora_inicio_1`; cuando existe la segunda franja, `hora_inicio_2` es igual o posterior a `hora_fin_1`, y `hora_fin_2` es posterior a `hora_inicio_2`.

Relaciones:

- Un horario de funcionamiento pertenece a exactamente una sede.
- Una sede puede tener cero a siete horarios de funcionamiento, uno por día de la semana.

### 4.23 `pagos_mercadopago`

Representa un intento de pago online a través de MercadoPago, independiente de `ingresos`. `estado` cubre los tres resultados que este sistema procesa para decidir si activa la membresía —**pendiente**, **aprobado** y **rechazado**— y se protege con la misma restricción `CHECK` que el resto de los estados del sistema (ver 2.3). Ancla además la idempotencia real del webhook (ver `4_flujos_del_sistema.md`, FL-22 y 4.4). La moneda no se almacena por fila: el sistema opera en un único mercado y valida siempre contra ARS, igual que el resto de los importes del modelo, ninguno de los cuales guarda moneda propia.

Un usuario no puede tener dos intentos en estado `pendiente` para la misma `membresia_id` y `mes_cubierto`: una restricción de unicidad parcial sobre `(usuario_id, membresia_id, mes_cubierto) WHERE estado = 'pendiente'` lo impide. Esto evita que un doble clic, dos pestañas o dos dispositivos generen dos preferencias de pago simultáneas y pagables para la misma membresía y mes (ver `4_flujos_del_sistema.md`, FL-22).

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `501` |
| FK | `usuario_id` | `bigint` | | | `1` |
| FK | `membresia_id` | `bigint` | | | `12` |
| | `mes_cubierto` | `date` | | | `2026-03-01` |
| | `precio_aplicado` | `numeric(12,2)` | | | `42750.00` |
| | `referencia_externa` | `uuid` | | Sí | `b3f1...` |
| | `preference_id` | `varchar(120)` | | Sí | `123456789-abcd...` |
| | `payment_id` | `varchar(120)` | Sí | Sí | `987654321` |
| | `estado` | `varchar(20)` | | | `pendiente` (o `aprobado`, `rechazado`) |
| FK | `membresia_usuario_id` | `bigint` | Sí | | `301` |
| FK | `ingreso_id` | `bigint` | Sí | | `5000` |
| | `creado_en` | `timestamptz` | | | `2026-03-01 10:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-01 10:05:00-03` |

`referencia_externa` se genera en la aplicación antes de crear la preferencia en MercadoPago y se envía como `external_reference`: es la clave de correlación disponible desde el primer momento, antes de que exista un `payment_id`. La fila solo se crea después de que MercadoPago confirma la preferencia, por eso `preference_id` nunca queda vacío y es único (una preferencia no se comparte entre intentos); si esa llamada falla, no se persiste ningún intento. `payment_id` se completa recién al recibir el webhook y es único cuando está presente: ancla el descarte de notificaciones repetidas. `mes_cubierto` es siempre el primer día del mes que se está pagando, igual que `membresias_usuarios.fecha_inicio` (ver 4.8). `membresia_usuario_id` e `ingreso_id` están siempre ambos presentes o ambos ausentes, y solo pueden estar presentes cuando `estado = 'aprobado'`: un intento `aprobado` sin estas referencias señala que quedó pendiente de resolución manual (ver 7.10), localizable mediante `4_flujos_del_sistema.md`, FL-62.

Relaciones:

- Un intento de pago con MercadoPago pertenece a exactamente un usuario.
- Un usuario puede tener cero, uno o varios intentos de pago con MercadoPago.
- Un intento de pago con MercadoPago referencia exactamente una membresía del catálogo.
- Una membresía puede estar asociada a cero, uno o varios intentos de pago con MercadoPago.
- Un intento de pago con MercadoPago genera, como máximo, una membresía de usuario.
- Un intento de pago con MercadoPago genera, como máximo, un ingreso.

### 4.24 `bloqueos`

Representa un bloqueo administrativo de un turno: mismo patrón de subtipo exclusivo de `eventos` que `clases`/`reservas` (4.15/4.19), pero sin usuario ni actividad asociada — ocupa la cancha sin ser ni una clase ni una reserva. Nace de dos caminos: bloquear directamente un turno hoy libre (lluvia, mantenimiento, torneo — ver `4_flujos_del_sistema.md`, FL-63/FL-64), o quedar creado automáticamente cuando un administrador cancela una reserva o una clase por uno de esos mismos motivos (ver 2.2, "Toda cancelación administrativa...").

| Clave | Columna | Tipo de dato | Nullable | Unique | Ejemplo |
|---|---|---|---|---|---|
| PK | `id` | `bigint` identity | | | `40` |
| FK | `evento_id` | `bigint` | | Sí | `950` |
| | `motivo` | `varchar(20)` | | | `clima_adverso` (o `torneo`, `mantenimiento`) |
| | `observaciones` | `text` | Sí | | `Cancha 3 anegada, se seca en dos días` |
| FK | `evento_origen_id` | `bigint` | Sí | Sí | `900` |
| | `creado_en` | `timestamptz` | | | `2026-03-03 09:00:00-03` |
| | `actualizado_en` | `timestamptz` | | | `2026-03-03 09:00:00-03` |

`motivo` nunca incluye `otro`: a diferencia del motivo de cancelación de una reserva o clase (texto libre, ver 4.14 y 4.19), un bloqueo por definición existe solo para uno de los tres motivos que impiden liberar el turno — si el motivo administrativo es "otro imprevisto", el turno se libera y no queda ningún bloqueo (ver 2.2). `evento_origen_id` referencia al evento cancelado que dio origen al bloqueo, cuando nace de cancelar una reserva o clase existente; queda vacío cuando el bloqueo se creó directamente sobre un turno libre. `evento_id` es único: el evento debe ser de tipo `bloqueo`. Un bloqueo se libera de la misma forma que se cancela una clase o una reserva: pasa a `estado = 'cancelado'` en su evento y el turno vuelve a quedar disponible.

Relaciones:

- Un bloqueo pertenece a exactamente un evento.
- Un evento corresponde, cuando es de tipo bloqueo, a exactamente un bloqueo.
- Un bloqueo referencia, como máximo, un evento de origen (la reserva o clase cancelada que lo generó).
- Un evento puede haber originado, como máximo, un bloqueo.

### 4.25 Recuperación de contraseña con Django

Se utiliza `PasswordResetTokenGenerator` junto con las vistas y formularios de recuperación de Django (FL-46).

El enlace contiene el identificador codificado del usuario y un token autenticado mediante HMAC, calculado con la clave secreta del proyecto, datos de la cuenta y una marca temporal. No se almacena una fila por solicitud. Su vigencia se limita a una hora mediante `PASSWORD_RESET_TIMEOUT = 3600`.

Al completar la recuperación cambia el hash de la contraseña, por lo que el enlace utilizado y los demás enlaces anteriores quedan invalidados. Cambiar el email o registrar un nuevo inicio de sesión también puede invalidarlos. Solicitar otro enlace no modifica por sí solo la cuenta ni invalida los anteriores.

---

## 5. Claves foráneas y eliminación

- Usuarios, sedes, canchas, membresías, precios y orígenes comerciales con historia utilizarán `ON DELETE RESTRICT`.
- Los subtipos de membresías (`planes`, `pases`) utilizarán `ON DELETE CASCADE` desde su fila base en `membresias`.
- `usuarios_roles` utilizará cascada desde `usuarios`.
- `usuarios_roles.rol_id` referencia `roles.id`; la integridad referencial impide borrar un rol que tenga asignaciones.
- Las asignaciones de un turno de planilla (`turnos_planilla_profesores`, `turnos_planilla_usuarios`) utilizarán cascada desde `turnos_planilla`.
- `sedes_horarios` utilizará cascada desde `sedes`.
- `clases.turno_planilla_id` utilizará `ON DELETE SET NULL`: eliminar un turno de la planilla no elimina las clases que ya generó, solo desvincula su origen.
- Eliminar un evento eliminará su clase o reserva únicamente dentro de operaciones expresamente autorizadas (regeneración de clases sin historia, ver 7.3).
- Clases, reservas, membresías de usuarios e ingresos con historia no se eliminarán como mecanismo operativo habitual.
- `pagos_mercadopago` utilizará `ON DELETE RESTRICT` desde `usuarios` y `membresias`: es historia de intentos de pago y no se elimina como mecanismo operativo habitual.
- `bloqueos.evento_origen_id` utilizará `ON DELETE SET NULL`: es solo trazabilidad hacia el evento cancelado que originó el bloqueo, no una relación de negocio que deba impedir su eliminación.

---

## 6. Reglas y validaciones de integridad

El sistema aplica, como mínimo:

1. Actualización automática de `actualizado_en`.
2. Exactamente un subtipo por `membresias` (plan o pase) y exclusión entre ambos.
3. Inmutabilidad estructural de membresías y precios ya utilizados.
4. Validación del mes calendario y estados de `membresias_usuarios`, incluida la exclusividad por titular y mes: no más de un plan vigente, ni más de un pase vigente (cualquiera sea su variante); sí puede combinar un plan con un pase.
5. Vencimiento idempotente de membresías de usuarios.
6. Unicidad de `turnos_planilla` por cancha, día de la semana y hora.
7. Exactamente un subtipo por `eventos` y coherencia con `eventos.tipo`.
8. Duración exacta de una hora para eventos de clase y horas enteras para reservas; `hora_inicio` con minutos y segundos en cero.
9. Sede y cancha activas al crear o mover eventos.
10. Al menos un profesor activo por clase.
11. Protección de clases y reservas terminales (canceladas o completadas) y autorización para completarlas.
12. Exclusividad entre precio normal y membresía de pase en reservas.
13. Coherencia entre duración de reserva normal y `precios_reservas_cancha`.
14. Vigencia, titularidad, día habilitado según el tipo de pase (`pases.tipo`) y horas diarias disponibles del pase del organizador al crear o modificar una reserva con pase; el día se valida antes que las horas.
15. Coherencia de invitados, cantidad declarada, membresías de pase aplicadas, día habilitado y horas diarias disponibles de cada invitado identificado con pase.
16. Congelamiento de reservas e invitados al cancelar o completar el evento.
17. Exactamente un origen por ingreso.
18. Registro obligatorio de motivo al cancelar una reserva.
19. Inmutabilidad de ingresos salvo su anulación.
20. Bloqueo de registro o modificación de una asistencia en estado `presente` o `ausente` mientras el evento de la clase no esté `completado`.
21. Bloqueo de superposición horaria de un mismo profesor entre actividades no canceladas, sin importar la cancha.
22. Un usuario activo autorizado (administrador, o el propio organizador en una reserva de autoservicio) registrará usuario y momento al cancelar un evento, con la misma exigencia que ya aplica a su finalización.
23. Alta automática de Público y Reservas en `usuarios_roles` para todo usuario nuevo, en la misma transacción que lo crea. Público no puede retirarse; Reservas solo puede retirarse si el usuario no tiene reservas programadas. Cada asignación referencia una fila del catálogo `roles`.
24. Alta automática del rol `alumno` en `usuarios_roles` para el usuario titular al registrarse su primer plan (subtipo `planes`) en estado `activa`, si aún no lo posee; un pase no lo otorga (además de la asignación manual por un administrador, ver FL-07).
25. Auto-completado idempotente de eventos `programado` cuya `hora_fin` ya pasó.
26. Aviso idempotente de vencimiento próximo de membresías, con marca de envío para no repetirlo.
27. Recordatorio idempotente de la próxima clase asignada, con marca de envío por asignación alumno–clase para no repetirlo, reseteada al reactivar la asignación.
28. Al regenerar las clases de un período, eliminar y recrear únicamente las clases en estado `programada` con `es_generada = true`; las clases `completada`, `cancelada` o con `es_generada = false` no se tocan.
29. En `pagos_mercadopago`: `mes_cubierto` es siempre el primer día de un mes; `membresia_usuario_id` e `ingreso_id` están ambos presentes o ambos ausentes, y solo pueden estar presentes cuando `estado = 'aprobado'`; a lo sumo un intento `pendiente` por `usuario_id`, `membresia_id` y `mes_cubierto` (unicidad parcial).
30. Retiro condicionado de roles: no se permite retirar Alumno mientras el usuario tenga una membresía activa, ni Profesor mientras tenga una asignación activa como profesor en una clase programada. Junto con el ítem 23, estas restricciones se verifican en la misma operación que elimina la asignación (ver 4.2 y FL-07).
31. Contraseña provisoria obligatoria: el alta administrativa realizada desde la aplicación, la creación mediante `crear_administrador` y el restablecimiento administrativo de una contraseña activan `usuarios.debe_cambiar_contrasena`; mientras permanezca activa, el usuario solo puede cambiar o recuperar su contraseña o cerrar sesión. El nuevo hash y la desactivación de la marca se guardan en la misma transacción (ver FL-68 y FL-69).
32. Estado y fecha de baja coherentes: una cuenta inactiva registra el momento de su baja y una cuenta activa conserva `fecha_baja = NULL` (ver FL-05).

Las reglas que deben observar varias filas se ejecutan dentro de operaciones transaccionales. Cuando existe riesgo de concurrencia, el backend bloquea las filas involucradas antes de validar y guardar.

La superposición horaria de una persona se comprueba en el backend sobre todos sus modos de participación: profesor o alumno de una clase, organizador o invitado identificado de una reserva. Las operaciones que crean clases o reservas y la generación desde la planilla bloquean las filas de los usuarios involucrados en orden de identificador antes de consultar y escribir. Para un profesor la superposición rechaza la operación; para los demás participantes produce una advertencia confirmable. La garantía supone que las escrituras operativas pasan por estos servicios; no reemplaza la exclusión GiST que protege la ocupación de cada cancha en la base.

El horario de funcionamiento de la sede (`sedes_horarios`) tampoco se valida mediante una restricción de base de datos, porque su exigencia depende de quién actúa: para una reserva de autoservicio es bloqueante, y para cualquier actividad gestionada por el administrador (clase o reserva) es solo una advertencia que este puede confirmar. Ambos casos quedan a cargo del backend, que conoce el actor de la operación.

El máximo de catorce días corridos de anticipación para crear una reserva sigue el mismo esquema: bloqueante para una reserva de autoservicio, solo una advertencia con confirmación para el administrador. Tampoco es una restricción de base de datos, por la misma razón.

El límite diario de horas de un pase (ítem 14) depende de una suma agregada sobre reservas existentes, no de una condición evaluable con un `CHECK`. La transacción que crea o modifica una reserva con pase deberá bloquear, con `SELECT ... FOR UPDATE` sobre `membresias_usuarios`, la fila de cada membresía de pase involucrada antes de calcular las horas ya usadas ese día: la del organizador y la de cada invitado identificado cuyo propio pase se esté evaluando para cubrirlo. Esto serializa intentos concurrentes sobre un mismo pase, sea como organizador o como invitado, y evita que dos reservas simultáneas lo superen sin verse entre sí. Cuando una misma transacción deba bloquear más de una membresía de pase, lo hará en un orden estable (por `id` ascendente) para evitar interbloqueos con otra transacción que bloquee las mismas filas en orden distinto.

---

## 7. Operaciones transaccionales críticas

### 7.1 Alta de una membresía

Creará la fila base y exactamente un subtipo en una transacción.

### 7.2 Generación de clases para un período

Dado un rango de fechas y una sede, recorrerá los `turnos_planilla` vigentes de las canchas de esa sede y, para cada fecha del período que coincida con el día de la semana del turno, no sea feriado (ver `feriados`) y no choque con un evento ya existente en esa cancha y horario, creará un evento de una hora y su clase con `es_generada = true`. Las fechas puntuales en conflicto se omiten y se informan; no interrumpen el resto de la generación. Las fechas fuera del horario de funcionamiento de la sede (`sedes_horarios`) no se omiten, solo se listan como advertencia en la vista previa: las dos confirmaciones explícitas descriptas en `2_criterios_del_sistema.md` (2) ya cubren esa advertencia. La operación no admite deshacer automático.

### 7.3 Regeneración de clases para un período

Al modificar la planilla y volver a generar un período ya generado, eliminará primero, en la misma transacción, las clases de ese período en estado `programada` con `es_generada = true` junto con sus eventos, y luego repetirá el procedimiento de 7.2. No toca clases `completada`, `cancelada` ni creadas manualmente (`es_generada = false`).

### 7.4 Reserva normal

Se ejecuta cuando el organizador no tiene una membresía de pase vigente para la fecha elegida, o no quiere usarla. Creará un evento continuo, copiará el precio aplicable, creará la reserva y registrará el ingreso opcional. Todo el intervalo deberá estar disponible. Tanto el horario de funcionamiento de la sede (`sedes_horarios`) como el máximo de catorce días de anticipación se rechazan sin excepción cuando organiza un usuario de autoservicio, y se advierten con confirmación explícita cuando gestiona el administrador.

### 7.5 Reserva con pase

Se ejecuta cuando el organizador tiene una membresía de pase vigente para la fecha elegida y decide usarla. Validará el horario de funcionamiento de la sede y el máximo de anticipación (igual que 7.4) y la membresía del organizador (vigencia, día habilitado según `pases.tipo`, horas disponibles), a los invitados identificados y sus pases; calculará el precio y creará evento, reserva, invitados e ingreso opcional en una transacción.

### 7.6 Cancelación de una reserva

Cancelará el evento completo con motivo obligatorio. Si cancela el propio organizador (autoservicio), `cancelada_por_usuario` queda fijo en verdadero y la operación termina ahí. Un administrador solo cancela por una causa ajena al organizador (clima, fuerza mayor, mantenimiento u otro imprevisto) — si el organizador quiere cancelar su propia reserva, lo hace él mismo por autoservicio —, así que `cancelada_por_usuario` queda fijo en falso y, a continuación, podrá encadenar 7.7 en la misma operación. No modificará los ingresos ni membresías originales.

### 7.7 Reprogramación de una reserva

Exclusiva de reservas canceladas por el administrador (nunca de una cancelada por el propio organizador vía autoservicio) y aún no reprogramadas. Crea una nueva reserva para el turno acordado —siguiendo el procedimiento de 7.4 o 7.5 según corresponda— vinculada mediante `reprogramada_desde_id` a la cancelada. Si no se reprograma en el momento de cancelar, no se crea ningún otro registro: resolver el dinero ya cobrado queda fuera del sistema. Puede ejecutarse inmediatamente después de 7.6 o más tarde, sobre una reserva ya cancelada.

### 7.8 Registro de un ingreso

Creará una sola fila de `ingresos` con exactamente una columna de origen informada. Exclusivo del rol Administrador.

### 7.9 Registro de un usuario

La operación centralizada de creación guardará la fila de `usuarios` con sus credenciales y, en la misma transacción, dos filas de `usuarios_roles`, con referencias a Público y Reservas. Si cualquiera de las tres escrituras falla, el alta completa se revierte. Aplica tanto si la propia persona se registra desde el portal como si la administración crea la cuenta.

### 7.10 Confirmación de pago de MercadoPago (webhook)

Al recibir el webhook, validará primero su firma (`x-signature`, `x-request-id`, `data.id` y la clave secreta configurada); si no coincide, descarta sin consultar nada. Consultará el pago en la API de MercadoPago (no confía en el payload recibido) y localizará el intento en `pagos_mercadopago` por `external_reference`; si no encuentra ninguno (evento ajeno a Academia TM en la misma cuenta, o referencia inexistente), descarta la notificación sin crear ni modificar nada y responde igualmente `200`. Guardará `payment_id` y actualizará `estado` según lo consultado, aplicando el efecto correspondiente solo si todavía no fue aplicado (la idempotencia se ancla al efecto ya aplicado, no a si el `payment_id` ya es conocido: un mismo pago puede notificarse primero pendiente y luego, con el mismo `payment_id`, aprobado o rechazado):
- **Pendiente** (o cualquier estado que MercadoPago reporte fuera de los tres que este sistema procesa, por ejemplo `in_process` o `authorized`): solo si el intento todavía no llegó a un estado terminal (`aprobado` o `rechazado`), lo actualiza a `pendiente`; no activa nada, a la espera de una notificación posterior con un estado final. Si el intento ya es terminal, esta notificación se ignora sin modificarlo — un pago ya aprobado nunca retrocede a pendiente.
- **Rechazado:** si el intento no está ya en un estado terminal, lo marca `rechazado`; no activa nada.
- **Aprobado:** si el intento ya tiene `membresia_usuario_id` o `ingreso_id`, no repite la activación. Si no, valida monto y moneda contra `precio_aplicado`. Si el usuario sigue sin tener una membresía vigente incompatible para ese mes, en una única transacción crea la fila de `membresias_usuarios` (o la renueva) con el `precio_aplicado` ya calculado en `pagos_mercadopago` — no lo recalcula —, registra el ingreso con `medio_pago = 'mercadopago'` vinculado a esa membresía, otorga el rol `alumno` al usuario si todavía no lo tiene, y guarda en el intento sus referencias a la membresía de usuario y al ingreso creados. `membresias_usuarios.registrada_por_id` e `ingresos.registrado_por_id` quedarán nulos. Si el conflicto de exclusividad se detecta recién en este paso, el intento queda `aprobado` sin esas referencias: el dinero fue cobrado pero la activación queda pendiente de resolución manual. Si la operación falla, no quedará ninguna membresía activada a medias. Responderá `200`/`201` dentro de los 22 segundos que MercadoPago espera antes de reintentar.

### 7.11 Auto-completado de clases y reservas vencidas

Función idempotente, análoga a `vencer_membresias_usuarios()`, ejecutada por Celery Beat cada hora en punto. Localizará los `eventos` en estado `programado` cuyo `fecha + hora_fin` sea menor o igual al momento de ejecución, los marcará `completado` con `completado_por_id` nulo, y no modificará asistencias.

### 7.12 Aviso de vencimiento próximo de una membresía

Tarea diaria idempotente. Localizará `membresias_usuarios` en estado `activa` con `fecha_fin` dentro de los próximos 3 días y `aviso_vencimiento_enviado = false`. Enviará el email y marcará `aviso_vencimiento_enviado = true` en la misma operación por fila.

### 7.13 Recordatorio de la próxima clase asignada

Tarea diaria idempotente. Localizará asignaciones `clases_usuarios` en estado `activo` de clases cuyo evento esté `programado` con `fecha` igual a la de mañana y `recordatorio_enviado = false`. Enviará el email a cada alumno por su propia asignación y marcará `recordatorio_enviado = true` en la misma operación por fila, de forma independiente por alumno.
