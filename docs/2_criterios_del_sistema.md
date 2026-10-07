# Criterios del sistema

## 1. Propósito

Este documento resume los criterios generales del sistema a desarrollar para la Academia de Tenis TM, tomando como base el funcionamiento actual de la organización (ver `1_organizacion.md`).

El objetivo es explicar, módulo por módulo, qué decisión se tomó sobre cómo el sistema va a resolver cada aspecto de la operatoria actual.

---

## 2. Alcance del sistema

El sistema será una única aplicación, con un solo backend y un único modelo de usuarios y roles, expuesta mediante dos interfaces separadas: la gestión interna para el personal (Administrador) y el portal público de autoservicio (Profesores,Público, Alumno, Reservas; ver 2.7). No son sistemas independientes: se separan por audiencia e interfaz, no por datos ni reglas de negocio.

La ocupación se organiza mediante turnos indivisibles de una hora. Cada turno identifica una cancha, una fecha y una hora de inicio; su fin se calcula sumando una hora. Un Evento vincula los turnos utilizados y concentra el estado, observaciones y auditoría de una Reserva, una Clase o un Bloqueo. Una clase utiliza exactamente un turno; reservas y bloqueos pueden utilizar varios.

Cancha, fecha, horario y duración se obtienen de los turnos. El estado se almacena únicamente en Evento: Programado ocupa sus turnos, Anulado los libera y Finalizado conserva su ocupación histórica. Los vínculos permanecen para consultar la historia. Un turno puede existir sin actividad asociada; su existencia no significa que esté ocupado.

Las clases y reservas previamente agendadas deberán respetarse. El sistema impedirá que dos eventos no Anulados ocupen el mismo turno. Las operaciones bloquean los turnos involucrados dentro de una transacción y comprueban la ocupación compartida antes de confirmar. Ninguna actividad podrá desplazar automáticamente a otra.

Cada sede tendrá su propio horario de funcionamiento, definido por día de la semana y con hasta dos franjas horarias por día (por ejemplo, de 8 a 12 y de 16 a 22). El inicio y el fin de cada franja deberán ser en punto y, si se configuran dos franjas, deberá haber al menos una hora sin funcionamiento entre ellas. Un día sin franjas configuradas significa que esa sede no funciona ese día. Toda reserva debe quedar contenida en una única franja habilitada, tanto desde el portal como desde la administración. Las clases mantienen una advertencia confirmable para el administrador cuando se generan o crean fuera de ese horario.

### 2.0 Límites temporales y calendario operativo

La historia operativa administrada por el sistema comienza el **1 de agosto de 2026**. Ninguna clase, reserva, bloqueo, contratación de plan o pase, fecha de alta, feriado ni ingreso puede registrarse antes de esa fecha. Esta fecha mínima es absoluta: no avanza con el tiempo, para permitir cargas y correcciones históricas desde el inicio de operaciones. Una eventual importación de historia anterior deberá resolverse mediante un proceso específico, no relajando las validaciones de la operación cotidiana.

Las clases y bloqueos pueden ubicarse desde el inicio de operaciones hasta un año calendario después de la fecha local actual. La agenda diaria y semanal usa ese intervalo. La administración puede registrar clases y bloqueos históricos para reconstruir la actividad. Una reserva nueva o reprogramada debe comenzar en un horario futuro y su fecha debe estar entre hoy y catorce días después, inclusive; no hay excepciones administrativas. Las consultas conservan el acceso a la historia.

La generación o regeneración de clases acepta rangos dentro de ese mismo intervalo y de **hasta 62 días corridos inclusive** por ejecución. Las consultas de actividad de clases y uso de pases aceptan rangos de **hasta 366 días corridos inclusive**. Un período mayor se consulta por tramos.

Las contrataciones de planes y pases pueden registrarse desde agosto de 2026 hasta el mes calendario siguiente al actual. Guardan el mes cubierto como una fecha del primer día; inicio y fin se calculan y siempre cubren meses completos. Una contratación histórica cuyo mes terminó nace Vencida. Una contratación de un mes futuro puede estar Activa, pero su cobertura corresponde a ese mes.

La fecha y hora de un ingreso representa el momento real en que se recibió el dinero: puede abarcar desde el 1 de agosto de 2026 a las 00:00 hasta el momento local actual, pero nunca ser futura. Puede ser anterior al inicio del período contratado o de la reserva asociada porque se admiten pagos anticipados.

Los feriados pueden registrarse desde el inicio de operaciones hasta cinco años calendario después de la fecha local actual. Registrar o quitar un feriado pasado no modifica retroactivamente las clases que ya fueron generadas.

La fecha de nacimiento es obligatoria y debe estar comprendida entre la fecha local actual menos 120 años y la fecha local actual. No se establece una edad mínima para ser usuario.

Todos estos límites se validan en el servidor y se exponen además en los controles HTML como ayuda de carga. Las comparaciones con el día o momento actual usan la zona `America/Argentina/Buenos_Aires`. Los servicios que escriben datos vuelven a validar las reglas aunque la interfaz ya lo haya hecho, para que no puedan evitarse manipulando formularios o URLs.

### 2.1 Gestión de clases

El sistema incluirá la gestión de clases de la academia.

La gestión incluirá:

- Armado y edición continua de la planilla semanal (semana tipo) por sede: una única planilla viva por sede, sin conservar versiones históricas por período. Cada celda define, para un día y horario, los alumnos asignados.
- Generación de clases concretas para un período seleccionado, a partir del estado actual de la planilla en ese momento.
- Eliminación manual de clases generadas que aún no tengan actividad efectiva (sin asistencia registrada ni completar), para los casos puntuales donde no corresponda regenerar todo el período.
- Consulta diaria y semanal de clases existentes.
- Creación, edición y cancelación de clases individuales, generadas por la planilla o creadas manualmente.
- Asignación de profesores y alumnos.
- Finalización individual de clases por la administración o por alguno de sus profesores asignados.
- Registro de asistencia, como parte de completar la clase.

Las clases generadas existirán como instancias individuales, marcadas con un indicador de origen (`es_generada`) que distingue si provienen de la planilla o fueron creadas manualmente. No se conservará una referencia a una planilla histórica: la clase concreta ya contiene por sí sola todo lo necesario para la historia operativa (día, horario, cancha, alumnos, profesor).

No existirá una reprogramación de clases como operación propia: una clase puede editarse, incluso cambiar de cancha, pero nunca de día ni de horario. Si hace falta mover una clase a otro día u horario, se cancela y se crea una nueva, sin ninguna vinculación entre ambas — a diferencia de una reserva, que sí queda vinculada a la que reemplaza.

Generar las clases de un período es una acción irreversible desde el sistema: no existe una operación de deshacer. Antes de ejecutarla, el sistema mostrará al menos dos confirmaciones explícitas advirtiendo que el proceso no puede deshacerse y que, si hace falta quitar clases generadas, deberá hacerse manualmente.

Modificar la planilla y volver a generar clases para un período ya generado elimina y recrea únicamente las clases de ese período cuyo evento sigue Programado y que fueron generadas por la planilla (`es_generada = true`), sin actividad efectiva. Conserva las clases con evento Finalizado o Anulado y las creadas manualmente. La regeneración elimina los vínculos de las clases reemplazadas, pero conserva los turnos concretos.

La asistencia se registrará como parte de completar la clase: una clase debe completarse para registrar la asistencia efectiva de sus alumnos.

La generación y la creación individual de clases también respetan el horario de funcionamiento de la sede (ver introducción de esta sección); como toda gestión de clases es responsabilidad del administrador, quedar fuera de ese horario solo genera una advertencia, nunca un bloqueo.

Cancelar una clase, al ser siempre una operación de administrador, sigue la misma clasificación de motivo que cancelar una reserva administrativamente (ver 2.2): clima adverso, torneo, mantenimiento u otro. Los primeros tres bloquean automáticamente el turno; "otro" lo deja disponible.

### 2.2 Gestión de reservas

El sistema incluirá la gestión interna de reservas de cancha.

Una sede o cancha no puede desactivarse mientras tenga reservas en estado Programada, aunque su horario ya haya terminado. Para la sede se consideran todas sus canchas. Las reservas futuras deben anularse según sus reglas; las demás sólo pueden finalizarse después del último turno, automáticamente o mediante la acción administrativa de emergencia. Las reservas Anuladas o Finalizadas no impiden la desactivación y sus registros se conservan. La reactivación se permite aunque haya reservas Programadas y no cambia el estado individual de las canchas ni las reservas existentes.

El control y el cambio de estado se confirman en una transacción coordinada con la creación de reservas, bloqueando primero la sede y luego la cancha cuando corresponde. Las solicitudes establecen un estado concreto; repetirlas no invierte la acción. Modificar los datos de la sede o cancha no puede sobrescribir su estado.

El administrador podrá consultar, buscar, crear y cancelar reservas de usuarios ya registrados. La finalización es automática al terminar el último turno, mediante la tarea horaria de Celery. El administrador también podrá finalizar manualmente una reserva Programada cuyo último turno terminó, como acción de emergencia sin depender de Celery ni Redis. Ambas opciones registran el estado y el momento de procesamiento, sin responsable de finalización. La disponibilidad se consulta como una vista completa del día elegido para una cancha (dentro de una sede): se ve de un vistazo qué bloques están ocupados y cuáles libres dentro del horario de funcionamiento, y se opera directamente sobre un espacio disponible para reservar o dar de alta una clase, sin necesitar una consulta puntual del tipo "¿está libre tal cancha a tal hora?". Un usuario también podrá consultar esa misma disponibilidad, consultar sus propias reservas y crear y cancelar sus propias reservas desde el portal (ver 2.7), sin intervención del administrador.

Para crear una reserva, el organizador debe estar activo y tener el rol Reservas o Administrador. La selección administrativa sólo ofrece usuarios que cumplen esas condiciones y el sistema las verifica nuevamente al confirmar. Si el organizador no tiene ninguno de esos roles, el administrador debe asignarle Reservas antes de reservar para él. Registrar una reserva no asigna roles automáticamente. Esta condición permite que el organizador acceda a sus reservas desde su cuenta.

Toda reserva utiliza turnos consecutivos de una misma cancha y fecha, dentro de una única franja de funcionamiento de su sede. La duración se obtiene de la cantidad de turnos seleccionados, sin ingresar una duración independiente.

La fecha elegida debe estar entre hoy y catorce días después y el inicio del primer turno debe ser futuro. Estas condiciones se aplican al portal, a la administración y a las reprogramaciones, y se vuelven a comprobar al confirmar.

Una reserva se registra con un único evento y uno o varios vínculos en `eventos_turnos`. Se confirma, anula o finaliza completa. Podrá ser normal, con precio determinado por su sede y cantidad de turnos, o utilizar una contratación de pase vigente del organizador.

Toda cancelación de reserva exigirá un motivo de al menos 25 caracteres, sin contar los espacios al principio y al final. Este mínimo se informa en el formulario y se valida en el servidor al confirmar. Un administrador solo puede cancelar la reserva de un usuario por una causa ajena al organizador —clima adverso, torneo, mantenimiento u otro imprevisto—: si el organizador quiere cancelar su propia reserva, debe hacerlo él mismo desde el portal (autoservicio). Para este sistema, que cada usuario tenga y use su propia cuenta para gestionar sus reservas no es una comodidad opcional: es un requisito, precisamente para que esta distinción tenga sentido.

Sólo se puede cancelar una reserva Programada. El usuario con rol Reservas puede cancelar únicamente las propias con al menos una hora de antelación al inicio del primer turno, incluido el límite exacto de una hora. El administrador puede cancelar la reserva de cualquier organizador hasta antes de su inicio. Una reserva iniciada, cancelada o completada no puede cancelarse. El sistema verifica estos límites con la fecha y hora completas dentro de la transacción y conserva quién realizó la operación, el motivo y el momento.

Cuando cancela un administrador, además del motivo en texto libre, deberá clasificarlo en uno de cuatro tipos: clima adverso, torneo, mantenimiento u otro. De esa clasificación depende si el turno queda disponible o no: clima adverso, torneo y mantenimiento son causas que impiden usar la cancha durante ese turno, así que el sistema lo bloquea automáticamente en el mismo momento de cancelar, con el mismo motivo, para que nadie más pueda ocuparlo mientras la causa siga vigente; otro imprevisto no bloquea nada, el turno queda disponible de inmediato, igual que cuando cancela el propio organizador. Este bloqueo automático es, en todo lo demás, la misma operación que bloquear directamente un turno hoy libre (ver más abajo): ambos caminos producen el mismo tipo de registro, solo cambia si nace de una cancelación o de una acción directa sobre un turno vacío.

El sistema también permitirá bloquear directamente uno o varios turnos que hoy están libres, sin que exista una reserva o una clase que cancelar — por ejemplo, una cancha que se rompe, o una previsión de lluvia para todo un fin de semana. Un bloqueo se identifica con el mismo motivo tipado que una cancelación administrativa bloqueante (clima adverso, torneo o mantenimiento; nunca "otro", porque no tendría sentido bloquear un turno libre sin una causa que lo justifique) y ocupa la cancha exactamente igual que una clase o una reserva: mientras esté vigente, nadie puede reservar ni dar de alta una clase sobre ese turno. Cuando el bloqueo abarca varios turnos a la vez, el administrador podrá indicarlos todos en una sola operación en lugar de repetirla turno por turno; si alguno de esos turnos ya tiene una reserva o una clase programada, cancelarla y reemplazarla por el bloqueo es parte de la misma operación, con el mismo motivo. Un bloqueo puede agrupar varios turnos y su estado pertenece al evento. Liberarlo cambia el evento a Anulado, requiere un motivo y registra quién lo liberó y cuándo. La liberación individual actúa sobre un bloqueo completo; la operación en lote permite liberar varios bloqueos completos. La liberación parcial de turnos de un mismo bloqueo queda pendiente de definición funcional. Los eventos anulados que originaron un bloqueo se conservan vinculados mediante `bloqueos_origenes`.

La posibilidad de reprogramar depende de quién cancela: un usuario con rol Reservas puede cancelar su propia reserva, pero esa cancelación nunca ofrece reprogramación. El administrador, en cambio, siempre puede ofrecer reprogramarla en el momento —cancela la original y registra una nueva para el día y horario acordados, sujeta a disponibilidad—, ya que por definición está cancelando por una causa ajena al organizador. Si no se reprograma, no se crea ningún otro registro: resolver el dinero ya cobrado queda fuera del sistema, a cargo de la administración caso por caso (ver `1_organizacion.md`, 5.2). Ninguna cancelación, se reprograme o no, genera una devolución dentro del sistema.

Los ingresos originales de una reserva cancelada permanecerán cobrados, para conservar el movimiento real de dinero. Una reserva cancelada no podrá recibir nuevos ingresos.

En una reserva normal no se registrarán invitados. En una reserva con pase se registrará la cantidad total de invitados y se identificarán aquellos que ya existan como usuarios. Los pases vigentes aplicados a invitados identificados quedarán registrados y cada invitado sin pase generará el precio adicional vigente copiado al crear la reserva.

Al crear cualquier reserva, el sistema buscará automáticamente si el organizador tiene una contratación de pase vigente que cubra la fecha elegida —es decir, una contratación cuyo mes cubierto incluya esa fecha— y, de existir, preguntará si desea utilizarla; si el organizador no quiere usarla, o no tiene ninguna vigente para esa fecha, la reserva sigue por el camino normal. Como el pase es válido solo para su mes calendario y una reserva puede crearse con hasta dos semanas de anticipación, es posible reservar para el mes siguiente sin que el pase del mes actual lo cubra: en ese caso la reserva cae en el camino normal, no es un error.

Cada pase (libre o de fin de semana, ver `1_organizacion.md` 3.2) se considerará ilimitado en cantidad de reservas durante su vigencia, pero limitado a una cantidad de horas por día calendario configurada en cada pase (inicialmente dos), sin importar si el uso proviene de reservas como organizador o como invitado; el pase de fin de semana además solo podrá usarse sábados y domingos. Al elegir usar el pase, el sistema validará primero si el día está habilitado para ese pase y luego calculará las horas ya usadas ese día; si el día no está habilitado, se rechaza sin llegar a revisar las horas; si el día está habilitado pero no queda ninguna hora disponible, también se impide continuar con pase. Si le queda alguna hora, la duración de la reserva no podrá superar las horas disponibles. Cualquier usuario existente puede identificarse como invitado, tenga o no pase: el sistema revisa si su propio pase tiene el día habilitado y horas disponibles suficientes para la duración elegida; si no, se lo cuenta como invitado sin pase y genera el adicional correspondiente, sin impedir el resto de la reserva.

Una reserva no se reprogramará ni cambiará de turno directamente. Si debe modificarse su fecha, horario o cancha, se cancelará la reserva original y se registrará una nueva.

Crear una reserva será siempre un recorrido guiado único, sin abandonar el proceso ni volver a ingresar datos ya conocidos, que resuelve en un mismo flujo si corresponde precio normal o pase. Cuando la gestiona el administrador, el recorrido empieza buscando y seleccionando al organizador entre los usuarios ya existentes, y permite además registrar opcionalmente el ingreso recibido; el organizador deberá existir previamente como usuario, este recorrido no incluye el alta de uno nuevo. Cuando la gestiona un usuario con rol Reservas para sí mismo desde el portal, el organizador es siempre el propio usuario y no hay registro de ingreso: el pago se resuelve en la sede.

### 2.3 Usuarios y roles

El sistema no distinguirá entre clientes y usuarios del sistema: toda persona que interactúa con el sistema, incluidas las que hoy se gestionan como clientes, es un **usuario**. Lo que cada usuario puede hacer lo determinan los roles que tiene asignados, no una categoría separada de "cliente".

Los roles se almacenan en la tabla fija `roles`; `usuarios_roles.rol_id` los referencia mediante una clave foránea. No se crean, renombran ni eliminan roles desde la aplicación. Sus registros iniciales se cargan mediante una migración; no se usa un enum para garantizar la integridad referencial.

Los roles serán:

- **Administrador**: acceso total al sistema. Es un rol exclusivo: una cuenta administrativa sólo tiene esta asignación en `usuarios_roles`, sin Público, Reservas, Profesor ni Alumno. La marca técnica `is_superuser` permite que Django le conceda todos los permisos. Se crea con el comando `crear_administrador` ejecutado por el desarrollador y opera desde la interfaz de Academia TM. Ningún administrador puede asignar ni quitar este rol desde la aplicación.
- **Profesor**: gestiona sus propias clases asignadas. Lo asigna un administrador, al crear el usuario o mediante la gestión de roles. Solo puede quitarse si el usuario no tiene clases programadas como profesor.
- **Público**: permite consultar el catálogo de la academia, suscribirse a planes o pases y consultar el perfil propio. Corresponde a una cuenta registrada y autenticada, no a un visitante anónimo. Se asigna automáticamente al crear una cuenta no administrativa y no puede quitarse desde la aplicación.
- **Reservas**: permite crear, cancelar y consultar reservas propias. Toda cuenta no administrativa lo recibe automáticamente desde su alta, se autoregistre o la registre la administración. Un administrador puede quitarlo únicamente si el usuario no tiene reservas programadas. El catálogo, la suscripción y el perfil corresponden al rol Público.
- **Alumno**: permite consultar sus clases asignadas y su historial de asistencia. Una cuenta no administrativa lo obtiene al registrar una contratación Activa de plan, presencial o mediante el portal, si no lo tiene; el alta administrativa no exige que se haya registrado un ingreso. Un pase no otorga este rol. También puede asignarlo un administrador al crear la cuenta o mediante la gestión de roles. No se retira automáticamente al vencer una contratación; sólo un administrador puede quitarlo respetando las condiciones del retiro.

Las cuentas no administrativas reciben Público y Reservas en la misma transacción del alta y pueden acumular Profesor o Alumno. Las cuentas administrativas reciben únicamente Administrador, que habilita el acceso total sin roles adicionales. Las asignaciones automáticas también respetan esta exclusividad.

La edición de una cuenta se limita a estas operaciones:

| Operación | Quién puede realizarla |
|---|---|
| Consultar el perfil propio | El usuario autenticado. |
| Cambiar la contraseña propia | El titular de la cuenta, incluido un administrador. |
| Modificar el correo | El Administrador, desde la gestión de usuarios. |
| Restablecer una contraseña | El Administrador, únicamente para otra cuenta. |

El nombre, apellido, nombre de usuario, celular, fecha de nacimiento y observaciones se registran durante el alta y no se editan desde la aplicación. El estado de la cuenta y las asignaciones de roles se administran mediante sus operaciones específicas; no forman parte de la edición del perfil. El usuario no puede modificar su correo desde el portal ni cambiar la contraseña de otra persona. La modificación del correo, el cambio de contraseña y el restablecimiento actualizan automáticamente la fecha de última modificación.

Las cuentas creadas por otra persona reciben una contraseña provisoria y quedan marcadas con `debe_cambiar_contrasena = true`. Esta regla comprende tanto el alta desde la aplicación como la creación de un administrador mediante `crear_administrador`. La persona puede autenticarse con esas credenciales, pero solo puede cambiar la contraseña, recuperarla o cerrar sesión hasta establecer una propia. El cambio correcto y la recuperación mediante el enlace enviado por email guardan el nuevo hash y desactivan la marca en la misma transacción. El restablecimiento administrativo genera otra contraseña provisoria y vuelve a activar la misma obligación; ningún administrador puede restablecer su propia contraseña.

El autorregistro no activa esa obligación: la persona elige y confirma su propia contraseña durante el alta. Tanto el cambio voluntario como el obligatorio exigen la contraseña vigente, la nueva contraseña y su confirmación. La nueva debe superar los validadores de Django y ser diferente de la vigente. Una validación fallida conserva el hash y la obligación pendiente; cerrar sesión tampoco desactiva esa obligación. Al cambiar la contraseña se conserva la sesión actual y las demás sesiones dejan de ser válidas al volver a utilizarse.

A fines prácticos, un usuario con rol Alumno se considera vigente en un período determinado cuando tiene actividad de clases en ese período, por ejemplo un plan activo. Esto es informativo, para reportes y consultas; no equivale al estado de la cuenta ni condiciona ninguna otra regla del sistema.

La administración podrá asignar o quitar Profesor y Alumno, y volver a otorgar o quitar Reservas después del alta, únicamente a cuentas no administrativas. Los perfiles de administradores no ofrecen la modificación de roles y el servidor rechaza cualquier intento de asignarles otros. Público no puede retirarse y Administrador se gestiona mediante `crear_administrador`, fuera de las pantallas de la aplicación.

El retiro de roles debe respetar las siguientes condiciones:

| Rol | Condición para quitarlo |
|---|---|
| Público | No se puede quitar. |
| Reservas | El usuario no tiene reservas propias en estado Programado. |
| Alumno | El usuario no tiene contrataciones de planes en estado Activo. Un pase no impide retirar Alumno. |
| Profesor | El usuario no tiene asignaciones activas como profesor en clases cuyo evento esté Programado. |

Si existe una relación que impide el retiro, se rechaza la operación y se conserva el rol. No se cancelan reservas, contrataciones ni clases automáticamente para permitir quitarlo. Los registros históricos se conservan; las reservas y clases canceladas o completadas y las contrataciones Vencidas o Anuladas no bloquean por sí solas el retiro. Las comprobaciones se basan en el estado registrado, no solo en que una fecha haya pasado.

La condición funcional de Administrador depende de una asignación del rol `administrador` en `usuarios_roles`. El comando de gestión `crear_administrador` es la única vía de alta y mantiene `is_superuser = true` como representación técnica de sus permisos; esa marca no constituye otro rol ni se gestiona por separado. El rol no se otorga ni se retira desde las pantallas. El estado activo o inactivo de esas cuentas se gestiona con las mismas reglas de cambio de estado que el resto de los usuarios.

Una persona con permiso para cambiar estados no puede desactivar su propia cuenta. Un administrador activo solo puede ser desactivado cuando permanece al menos otro administrador activo. Estas condiciones se validan al confirmar la operación y los cambios concurrentes se serializan para impedir que dos desactivaciones dejen al sistema sin administradores.

La inactivación registra automáticamente la fecha y hora de baja de la cuenta. La reactivación elimina esa marca, de modo que una cuenta activa no conserva una fecha de baja vigente. Ambas operaciones actualizan también la fecha de última modificación.

La aplicación no expone la interfaz administrativa técnica de Django; toda operación cotidiana se realiza desde las pantallas de Academia TM.

### 2.4 Planes, pases, contrataciones y precios

Los catálogos de planes y pases son independientes. Cada producto guarda nombre, descripción, precio vigente, estado y su configuración específica.

- `planes` define modalidad individual o grupal, frecuencia de uno a siete encuentros semanales y una o dos clases consecutivas de una hora por encuentro.
- `pases` define variante Libre o Fin de semana, límite diario de horas y adicional vigente por invitado sin cobertura. Libre habilita todos los días; Fin de semana sólo sábados y domingos.

Cada combinación de plan y cada variante de pase es un producto completo de su catálogo. Nombre, descripción y precios pueden actualizarse; la configuración estructural se conserva cuando tiene contrataciones históricas. Un producto inactivo no admite contrataciones nuevas y no altera las existentes.

`planes_usuarios` y `pases_usuarios` registran las contrataciones por separado. Cada fila referencia obligatoriamente al usuario y a su producto, conserva el mes cubierto, fecha efectiva de alta, precio aplicado, responsable del registro, observaciones y estado Activo, Anulado o Vencido. Un alta automática por MercadoPago no tiene administrador responsable.

Un usuario puede tener un plan y un pase para el mismo mes, pero no dos contrataciones no Anuladas del mismo tipo. Los Vencidos también protegen la exclusividad histórica de su mes. Anular conserva la fila y permite registrar un reemplazo. Renovar para otro mes crea una contratación nueva; usuario, producto, mes e importe aplicado no se editan en un registro existente.

Una anulación administrativa exige motivo y conserva administrador y momento. No modifica automáticamente ingresos, clases, reservas ni coberturas aplicadas. El vencimiento periódico procesa por separado las contrataciones Activas de ambas tablas cuyo mes terminó. El aviso por email conserva su marca de envío en cada contratación.

Registrar una contratación Activa de plan otorga Alumno si falta ese rol y el titular no es administrador; un pase no lo otorga. El titular puede consultar sus propias contrataciones de ambos tipos y el acceso a un pase no exige Alumno. Las clases se organizan mediante asignaciones y asistencia; contratar un plan no genera clases ni asigna horarios automáticamente. La frecuencia contratada se administra según la organización de la academia, sin un control automático de cumplimiento del plan.

Los precios siguen el mismo criterio en los tres productos:

| Valor vigente | Importe conservado |
|---|---|
| Precio mensual en `planes` | `planes_usuarios.precio_aplicado` |
| Precio mensual en `pases` | `pases_usuarios.precio_aplicado` |
| Tarifa por turno en `sedes.precio_reserva_vigente` | `reservas.precio_por_turno_aplicado` |
| Adicional de invitado en `pases` | `reservas.precio_invitado_aplicado` |

Actualizar modifica el valor vigente para operaciones nuevas. Los registros existentes conservan su importe acordado. El sistema consulta esos importes para su historia comercial; no conserva un historial independiente de cambios de precio del catálogo o de la sede.

El Administrador configura un único precio positivo por turno de una hora en cada sede, común a todas sus canchas. El valor puede estar vacío mientras no se configure; sin tarifa no se confirma una reserva normal. La configuración y el registro se coordinan bloqueando la sede dentro de la transacción. Un importe igual al vigente no genera cambios.

Al registrar una reserva normal, el servidor valida y copia el precio vigente de la sede. Si cambió mientras se seleccionaban los turnos, muestra el nuevo total y exige confirmar nuevamente. El total se calcula con cantidad de turnos por precio unitario aplicado, sin almacenar otra copia del total.

La contratación mensual guarda el importe acordado, separado del dinero cobrado. En el alta administrativa se propone el precio vigente y puede establecerse el importe final correspondiente a un ajuste. En el portal, el precio queda congelado en el intento de pago: la aprobación copia ese importe en la contratación, sin recalcular con el catálogo.

El descuento o recargo por fecha de pago de los planes sigue la política de `1_organizacion.md`, sección 3.1. El portal lo calcula al iniciar el pago; un pase utiliza su precio vigente sin ese ajuste. La administración resuelve los ajustes de los cobros presenciales y conserva el importe acordado en la contratación.

Una reserva con pase referencia la contratación concreta del organizador en `pases_usuarios`; los invitados cubiertos referencian sus propias contrataciones. Se valida titularidad, mes, estado Activo, día habilitado y horas disponibles. El consumo diario cuenta los turnos de reservas no Anuladas, como organizador o invitado, sin almacenar un saldo.

Celery finaliza cada hora los eventos de clases y reservas Programados cuyo último turno terminó, conservando `eventos.finalizado_en`. Las reservas mantienen la acción administrativa de emergencia, sin responsable de finalización. Las clases registran responsable sólo si se finalizan manualmente. Los bloqueos se liberan mediante anulación y quedan fuera de la tarea.

Estado, observaciones y auditoría de clases, reservas y bloqueos pertenecen a `eventos`. Los datos de participantes, asistencia, contrataciones e ingresos conservan su auditoría específica.

### 2.5 Ingresos

El sistema registrará el dinero recibido por la academia. Cada ingreso tiene exactamente uno de estos orígenes: plan contratado, pase contratado, reserva u otro concepto. Referencia la contratación concreta en `planes_usuarios` o `pases_usuarios`, no el producto del catálogo. Las contrataciones y reservas pueden recibir pagos parciales mediante varios ingresos. La administración podrá consultar y buscar los ingresos registrados, filtrando por origen, usuario, período o estado.

Cada contratación y reserva muestra un resumen de cobro calculado: total aplicado, suma de ingresos en estado `cobrado`, pendiente y excedente. Se usarán los precios históricos de la operación; en reservas con pase se agregarán los adicionales por invitados sin cobertura, incluidos los no identificados. Los ingresos anulados no sumarán y el resumen se actualizará al anular un ingreso o cambiar la cobertura de invitados. El estado de pago (sin pagos, pago parcial, completo, con excedente o sin cargo) será independiente del estado operativo de la contratación o reserva. En operaciones canceladas se mostrarán diferencias históricas, sin convertirlas automáticamente en deuda, devolución o crédito transferible a una reprogramación.

Si un ingreso manual, incluido el primero o el registrado al crear una reserva, lleva el cobro acumulado por encima del total aplicado, el sistema mostrará los importes y exigirá confirmación explícita y un motivo, conservado en las observaciones del ingreso. No se guardará el ingreso —ni la reserva nueva asociada— hasta confirmar. La confirmación será válida durante 30 minutos para el origen, monto, total y cobrado revisados; si cambian, se pedirá nuevamente. Registro y anulación de ingresos se serializarán por operación para que cobros simultáneos se validen sobre el saldo actualizado. Los ingresos de otros conceptos no tendrán esta comparación porque no poseen un total pactado asociado.

Los ingresos de otros conceptos conservarán una descripción obligatoria. Una vez registrados, los ingresos no podrán editarse ni eliminarse; solo podrán anularse, por ejemplo ante un error de carga. Este módulo, y la posibilidad de anular ingresos, quedará reservado exclusivamente al rol Administrador.

El sistema no incluirá, en esta etapa, un módulo de egresos generales de la academia: esa contabilidad seguirá llevándose fuera del sistema.

### 2.6 Notificaciones

El sistema enviará notificaciones automáticas por email en los siguientes casos: confirmación de alta de cuenta, recuperación de contraseña, confirmación de contratación de un plan o pase (pago aprobado por MercadoPago), confirmación de una reserva propia, invitación a una reserva con pase, cancelación de una reserva o clase que afecta al usuario, reprogramación de una reserva cancelada por un motivo ajeno al cliente, vencimiento próximo de una contratación, recordatorio de la próxima clase asignada y asignación de un profesor a una clase o turno programado.

Las notificaciones se enviarán únicamente por email; no habrá una bandeja de notificaciones dentro del sistema. Las comunicaciones no cubiertas por estos casos seguirán realizándose por fuera del sistema.

### 2.7 Portal de usuarios

El sistema tendrá un único portal de acceso externo, para cualquier persona que se registre como usuario, separado de la interfaz de gestión interna (ver intro de la sección 2).

El catálogo de planes, pases y tarifas vigentes sólo puede consultarse estando registrado y autenticado con el rol Público: es el equivalente, dentro del sistema, a tener que preguntar en la sede antes de conocer los precios.

Un usuario con rol Reservas podrá consultar, crear y cancelar sus propias reservas de cancha desde el portal, normales o con pase, con las mismas reglas que la gestión interna (ver 2.2); se asigna automáticamente junto con Público. En una reserva con pase, podrá elegir como invitados a otros usuarios ya registrados, sin que se les exija tener pase; cada invitado identificado recibe una notificación de la invitación.

Un usuario autenticado con rol Público podrá suscribirse a un plan o a un pase pagando online a través de MercadoPago; activar el primer plan le otorga el rol Alumno, pero contratar un pase no lo otorga. Un usuario con rol Alumno podrá consultar, en modo de solo lectura, su historial de clases con asistencia y sus próximas clases asignadas. Cualquier titular autenticado puede consultar sus propios planes y pases contratados, incluidos sus importes, período, cobros y usos, sin exigir Alumno para un pase.

El perfil propio permite consultar los datos personales y de la cuenta, los roles y el estado, y cambiar únicamente la contraseña propia mediante **Cambiar mi contraseña**. La modificación del correo se realiza exclusivamente por el Administrador mediante la gestión de usuarios; el resto de los datos personales no tiene edición desde la aplicación. La obligación de reemplazar una contraseña provisoria se cumple antes de acceder al perfil o a cualquier otra función del portal. El catálogo y las suscripciones forman parte de las funcionalidades del portal descriptas en esta sección.

Las reservas creadas desde el portal se pagarán en la sede, igual que las gestionadas internamente; el portal no integrará un cobro online para reservas.

Quedan fuera del portal en esta etapa: elegir el turno semanal de un plan (lo sigue asignando la administración), solicitar recuperaciones de clase, y notificaciones dentro del sistema más allá del email.
