# Criterios del sistema

## 1. Propósito

Este documento resume los criterios generales del sistema a desarrollar para la Academia de Tenis TM, tomando como base el funcionamiento actual de la organización (ver `1_organizacion.md`).

El objetivo es explicar, módulo por módulo, qué decisión se tomó sobre cómo el sistema va a resolver cada aspecto de la operatoria actual.

---

## 2. Alcance del sistema

El sistema será una única aplicación, con un solo backend y un único modelo de usuarios y roles, expuesta mediante dos interfaces separadas: la gestión interna para el personal (Administrador) y el portal público de autoservicio (Profesores,Público, Alumno, Reservas; ver 2.7). No son sistemas independientes: se separan por audiencia e interfaz, no por datos ni reglas de negocio.

Las clases y reservas previamente agendadas deberán respetarse. El sistema impedirá superposiciones de cancha, fecha y horario y ninguna actividad podrá desplazar automáticamente a otra.

Cada sede tendrá su propio horario de funcionamiento, definido por día de la semana y con hasta dos franjas horarias por día (por ejemplo, de 8 a 12 y de 16 a 22); un día sin franjas configuradas significa que esa sede no funciona ese día. Este horario rige tanto para clases como para reservas, pero con distinta exigencia según quién actúa: una reserva autogestionada por un usuario desde el portal deberá quedar contenida por completo dentro de una franja habilitada, sin excepción; cuando la gestiona el administrador, sea una clase o una reserva, quedar fuera de ese horario no bloquea la operación, el sistema advierte que está fuera del horario de funcionamiento de la sede y exige una confirmación explícita antes de continuar.

### 2.0 Límites temporales y calendario operativo

La historia operativa administrada por el sistema comienza el **1 de agosto de 2026**. Ninguna clase, reserva, bloqueo, membresía de usuario, fecha de alta, feriado ni ingreso puede registrarse antes de esa fecha. Esta fecha mínima es absoluta: no avanza con el tiempo, para permitir cargas y correcciones históricas desde el inicio de operaciones. Una eventual importación de historia anterior deberá resolverse mediante un proceso específico, no relajando las validaciones de la operación cotidiana.

Las clases, reservas y bloqueos —incluidas sus reprogramaciones— pueden ubicarse desde el inicio de operaciones hasta un año calendario después de la fecha local actual. La agenda diaria y semanal usa el mismo intervalo y deja de ofrecer navegación y acciones cuando alcanza alguno de sus extremos. La posibilidad administrativa de crear eventos pasados es deliberada: permite reconstruir la actividad desde el inicio de operaciones. Para las reservas se mantiene, dentro de ese límite absoluto, la advertencia confirmable cuando superan los catorce días de anticipación.

La generación o regeneración de clases acepta rangos dentro de ese mismo intervalo y de **hasta 62 días corridos inclusive** por ejecución. Las consultas de actividad de clases y uso de pases aceptan rangos de **hasta 366 días corridos inclusive**. Un período mayor se consulta por tramos.

Las membresías de usuarios pueden registrarse desde agosto de 2026 hasta el mes calendario siguiente al actual. Siempre cubren meses completos. Si se registra históricamente una membresía cuyo mes ya finalizó, nace en estado **Vencida**; no queda transitoriamente Activa a la espera de la tarea periódica.

La fecha y hora de un ingreso representa el momento real en que se recibió el dinero: puede abarcar desde el 1 de agosto de 2026 a las 00:00 hasta el momento local actual, pero nunca ser futura. Puede ser anterior al inicio de la membresía o de la reserva asociada porque se admiten pagos anticipados.

Los feriados pueden registrarse desde el inicio de operaciones hasta cinco años calendario después de la fecha local actual. Registrar o quitar un feriado pasado no modifica retroactivamente las clases que ya fueron generadas.

La fecha de nacimiento es opcional y debe estar comprendida entre la fecha local actual menos 120 años y la fecha local actual. No se establece una edad mínima para ser usuario.

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

Modificar la planilla y volver a generar clases para un período ya generado eliminará y recreará únicamente las clases de ese período que estén en estado programada y hayan sido generadas por la planilla (`es_generada = true`). Las clases completadas, canceladas o creadas manualmente no se tocan.

La asistencia se registrará como parte de completar la clase: una clase debe completarse para registrar la asistencia efectiva de sus alumnos.

La generación y la creación individual de clases también respetan el horario de funcionamiento de la sede (ver introducción de esta sección); como toda gestión de clases es responsabilidad del administrador, quedar fuera de ese horario solo genera una advertencia, nunca un bloqueo.

Cancelar una clase, al ser siempre una operación de administrador, sigue la misma clasificación de motivo que cancelar una reserva administrativamente (ver 2.2): clima adverso, torneo, mantenimiento u otro. Los primeros tres bloquean automáticamente el turno; "otro" lo deja disponible.

### 2.2 Gestión de reservas

El sistema incluirá la gestión interna de reservas de cancha.

El administrador podrá gestionar reservas de cualquier usuario ya registrado: consulta y búsqueda de reservas existentes, creación, cancelación y finalización. La disponibilidad se consulta como una vista completa del día elegido para una cancha (dentro de una sede): se ve de un vistazo qué bloques están ocupados y cuáles libres dentro del horario de funcionamiento, y se opera directamente sobre un espacio disponible para reservar o dar de alta una clase, sin necesitar una consulta puntual del tipo "¿está libre tal cancha a tal hora?". Un usuario también podrá consultar esa misma disponibilidad, consultar sus propias reservas y crear y cancelar sus propias reservas desde el portal (ver 2.7), sin intervención del administrador.

Toda reserva respeta el horario de funcionamiento de su sede (ver introducción de esta sección), con la misma distinción entre autoservicio y administrador allí descripta.

El sistema también limitará con cuánta anticipación puede crearse una reserva: como máximo, catorce días corridos desde la fecha en que se crea. Para una reserva autogestionada desde el portal esa fecha límite es inflexible; para el administrador es, otra vez, solo una advertencia con confirmación explícita, no un bloqueo.

Una reserva será un evento continuo e indivisible de una o más horas. Podrá ser normal, con precio determinado por su duración, o utilizar una membresía de pase vigente del organizador.

Toda cancelación de reserva exigirá un motivo. Un administrador solo puede cancelar la reserva de un usuario por una causa ajena al organizador —clima adverso, torneo, mantenimiento u otro imprevisto—: si el organizador quiere cancelar su propia reserva, debe hacerlo él mismo desde el portal (autoservicio). Para este sistema, que cada usuario tenga y use su propia cuenta para gestionar sus reservas no es una comodidad opcional: es un requisito, precisamente para que esta distinción tenga sentido.

Cuando cancela un administrador, además del motivo en texto libre, deberá clasificarlo en uno de cuatro tipos: clima adverso, torneo, mantenimiento u otro. De esa clasificación depende si el turno queda disponible o no: clima adverso, torneo y mantenimiento son causas que impiden usar la cancha durante ese turno, así que el sistema lo bloquea automáticamente en el mismo momento de cancelar, con el mismo motivo, para que nadie más pueda ocuparlo mientras la causa siga vigente; otro imprevisto no bloquea nada, el turno queda disponible de inmediato, igual que cuando cancela el propio organizador. Este bloqueo automático es, en todo lo demás, la misma operación que bloquear directamente un turno hoy libre (ver más abajo): ambos caminos producen el mismo tipo de registro, solo cambia si nace de una cancelación o de una acción directa sobre un turno vacío.

El sistema también permitirá bloquear directamente uno o varios turnos que hoy están libres, sin que exista una reserva o una clase que cancelar — por ejemplo, una cancha que se rompe, o una previsión de lluvia para todo un fin de semana. Un bloqueo se identifica con el mismo motivo tipado que una cancelación administrativa bloqueante (clima adverso, torneo o mantenimiento; nunca "otro", porque no tendría sentido bloquear un turno libre sin una causa que lo justifique) y ocupa la cancha exactamente igual que una clase o una reserva: mientras esté vigente, nadie puede reservar ni dar de alta una clase sobre ese turno. Cuando el bloqueo abarca varios turnos a la vez, el administrador podrá indicarlos todos en una sola operación en lugar de repetirla turno por turno; si alguno de esos turnos ya tiene una reserva o una clase programada, cancelarla y reemplazarla por el bloqueo es parte de la misma operación, con el mismo motivo. Liberar un bloqueo, individual o en lote, deja el turno disponible de nuevo y sigue el mismo criterio que cancelar cualquier otro evento: requiere un motivo y queda registrado quién lo liberó y cuándo.

La posibilidad de reprogramar depende de quién cancela: un usuario con rol Reservas puede cancelar su propia reserva, pero esa cancelación nunca ofrece reprogramación. El administrador, en cambio, siempre puede ofrecer reprogramarla en el momento —cancela la original y registra una nueva para el día y horario acordados, sujeta a disponibilidad—, ya que por definición está cancelando por una causa ajena al organizador. Si no se reprograma, no se crea ningún otro registro: resolver el dinero ya cobrado queda fuera del sistema, a cargo de la administración caso por caso (ver `1_organizacion.md`, 5.2). Ninguna cancelación, se reprograme o no, genera una devolución dentro del sistema.

Los ingresos originales de una reserva cancelada permanecerán cobrados, para conservar el movimiento real de dinero. Una reserva cancelada no podrá recibir nuevos ingresos.

En una reserva normal no se registrarán invitados. En una reserva con pase se registrará la cantidad total de invitados y se identificarán aquellos que ya existan como usuarios. Los pases vigentes aplicados a invitados identificados quedarán registrados y cada invitado sin pase generará el precio adicional vigente copiado al crear la reserva.

Al crear cualquier reserva, el sistema buscará automáticamente si el organizador tiene una membresía de pase vigente que cubra la fecha elegida —es decir, una membresía cuyo mes calendario incluya esa fecha— y, de existir, preguntará si desea utilizarla; si el organizador no quiere usarla, o no tiene ninguna vigente para esa fecha, la reserva sigue por el camino normal. Como el pase es válido solo para su mes calendario y una reserva puede crearse con hasta dos semanas de anticipación, es posible reservar para el mes siguiente sin que el pase del mes actual lo cubra: en ese caso la reserva cae en el camino normal, no es un error.

Cada pase (libre o de fin de semana, ver `1_organizacion.md` 3.2) se considerará ilimitado en cantidad de reservas durante su vigencia, pero limitado a una cantidad de horas por día calendario configurada en cada pase (inicialmente dos), sin importar si el uso proviene de reservas como organizador o como invitado; el pase de fin de semana además solo podrá usarse sábados y domingos. Al elegir usar el pase, el sistema validará primero si el día está habilitado para ese pase y luego calculará las horas ya usadas ese día; si el día no está habilitado, se rechaza sin llegar a revisar las horas; si el día está habilitado pero no queda ninguna hora disponible, también se impide continuar con pase. Si le queda alguna hora, la duración de la reserva no podrá superar las horas disponibles. Cualquier usuario existente puede identificarse como invitado, tenga o no pase: el sistema revisa si su propio pase tiene el día habilitado y horas disponibles suficientes para la duración elegida; si no, se lo cuenta como invitado sin pase y genera el adicional correspondiente, sin impedir el resto de la reserva.

Una reserva no se reprogramará ni cambiará de turno directamente. Si debe modificarse su fecha, horario o cancha, se cancelará la reserva original y se registrará una nueva.

Crear una reserva será siempre un recorrido guiado único, sin abandonar el proceso ni volver a ingresar datos ya conocidos, que resuelve en un mismo flujo si corresponde precio normal o pase. Cuando la gestiona el administrador, el recorrido empieza buscando y seleccionando al organizador entre los usuarios ya existentes, y permite además registrar opcionalmente el ingreso recibido; el organizador deberá existir previamente como usuario, este recorrido no incluye el alta de uno nuevo. Cuando la gestiona un usuario con rol Reservas para sí mismo desde el portal, el organizador es siempre el propio usuario y no hay registro de ingreso: el pago se resuelve en la sede.

### 2.3 Usuarios y roles

El sistema no distinguirá entre clientes y usuarios del sistema: toda persona que interactúa con el sistema, incluidas las que hoy se gestionan como clientes, es un **usuario**. Lo que cada usuario puede hacer lo determinan los roles que tiene asignados, no una categoría separada de "cliente".

Los roles se almacenan en la tabla fija `roles`; `usuarios_roles.rol_id` los referencia mediante una clave foránea. No se crean, renombran ni eliminan roles desde la aplicación. Sus registros iniciales se cargan mediante una migración; no se usa un enum para garantizar la integridad referencial.

Los roles serán:

- **Administrador**: acceso total al sistema. Se representa mediante una asignación en `usuarios_roles`; la marca técnica `is_superuser` permite que Django le conceda todos los permisos. Se crea con el comando `crear_administrador` ejecutado por el desarrollador y opera desde la interfaz de Academia TM. Ningún administrador puede asignar ni quitar este rol desde la aplicación.
- **Profesor**: gestiona sus propias clases asignadas. Lo asigna un administrador, al crear el usuario o mediante la gestión de roles. Solo puede quitarse si el usuario no tiene clases programadas como profesor.
- **Público**: permite consultar el catálogo de la academia, suscribirse a planes o pases y consultar el perfil propio. Corresponde a una cuenta registrada y autenticada, no a un visitante anónimo. Se asigna automáticamente al crear la cuenta y no puede quitarse desde la aplicación.
- **Reservas**: permite crear, cancelar y consultar reservas propias. Todo usuario lo recibe automáticamente desde su alta, se autoregistre o lo registre la administración. Un administrador puede quitarlo únicamente si el usuario no tiene reservas programadas. El catálogo, la suscripción y el perfil corresponden al rol Público.
- **Alumno**: permite ver historial y membresía e historial de clases. Se obtiene por cualquiera de estas vías: automáticamente al activarse el primer plan del usuario, presencial o mediante el portal, con independencia de si el ingreso ya fue registrado (un pase de cancha no otorga este rol: es solo acceso a cancha, no inscripción a clases); o asignado directamente por un administrador, al crear el usuario o mediante la gestión de roles, igual que el rol Profesor. No se pierde automáticamente cuando la membresía vence ni por ninguna otra causa: no existe un proceso que retire roles, salvo que un administrador lo quite explícitamente.

Todo usuario recibe Público y Reservas en la misma transacción del alta y puede acumular, además, varios de los demás roles a la vez; por ejemplo, Alumno.

Las cuentas creadas por otra persona reciben una contraseña provisoria y quedan marcadas con `debe_cambiar_contrasena = true`. Esta regla comprende tanto el alta desde la aplicación como la creación de un administrador mediante `crear_administrador`. La persona puede autenticarse con esas credenciales, pero solo puede cambiar la contraseña, recuperarla o cerrar sesión hasta establecer una propia. El cambio correcto y la recuperación mediante el enlace enviado por email guardan el nuevo hash y desactivan la marca en la misma transacción. El restablecimiento administrativo genera otra contraseña provisoria y vuelve a activar la misma obligación; ningún administrador puede restablecer su propia contraseña.

A fines prácticos, un usuario con rol Alumno se considera vigente en un período determinado cuando tiene actividad de clases en ese período, por ejemplo un plan activo. Esto es informativo, para reportes y consultas; no equivale al estado de la cuenta ni condiciona ninguna otra regla del sistema.

La administración podrá asignar o quitar Profesor y Alumno, y volver a otorgar o quitar Reservas después del alta. Público no puede retirarse y Administrador se gestiona mediante `crear_administrador`, fuera de las pantallas de la aplicación.

El retiro de roles debe respetar las siguientes condiciones:

| Rol | Condición para quitarlo |
|---|---|
| Público | No se puede quitar. |
| Reservas | El usuario no tiene reservas propias en estado Programado. |
| Alumno | El usuario no tiene ninguna membresía en estado Activa, sea un plan o un pase. |
| Profesor | El usuario no tiene asignaciones activas como profesor en clases cuyo evento esté Programado. |

Si existe una relación que impide el retiro, se rechaza la operación y se conserva el rol. No se cancelan reservas, membresías ni clases automáticamente para permitir quitarlo. Los registros históricos se conservan; las reservas y clases canceladas o completadas y las membresías vencidas o canceladas no bloquean por sí solas el retiro. Las comprobaciones se basan en el estado registrado, no solo en que una fecha haya pasado.

La condición funcional de Administrador depende de una asignación del rol `administrador` en `usuarios_roles`. El comando de gestión `crear_administrador` es la única vía de alta y mantiene `is_superuser = true` como representación técnica de sus permisos; esa marca no constituye otro rol ni se gestiona por separado. El rol no se otorga ni se retira desde las pantallas. El estado activo o inactivo de esas cuentas se gestiona con las mismas reglas de cambio de estado que el resto de los usuarios.

Una persona con permiso para cambiar estados no puede desactivar su propia cuenta. Un administrador activo solo puede ser desactivado cuando permanece al menos otro administrador activo. Estas condiciones se validan al confirmar la operación y los cambios concurrentes se serializan para impedir que dos desactivaciones dejen al sistema sin administradores.

La inactivación registra automáticamente la fecha y hora de baja de la cuenta. La reactivación elimina esa marca, de modo que una cuenta activa no conserva una fecha de baja vigente. Ambas operaciones actualizan también la fecha de última modificación.

La aplicación no expone la interfaz administrativa técnica de Django; toda operación cotidiana se realiza desde las pantallas de Academia TM.

### 2.4 Membresías, reservas y precios

El sistema distinguirá entre membresías mensuales y reservas de cancha.

Las membresías contemplarán:

- Planes grupales e individuales de entre uno y siete encuentros por semana, con encuentros de una o dos clases consecutivas de una hora.
- Pases de cancha mensuales: **pase libre** y **pase de fin de semana** (ver `1_organizacion.md`, 3.2). Cada variante es una membresía propia y distinta en el catálogo, con su propio precio — igual que cada combinación de plan es una membresía distinta. No hay una única entidad "pase" con un campo que module el día habilitado: el día habilitado (todos los días, o solo sábado y domingo) es una propiedad fija de cada membresía de pase.

`membresias_usuarios` vinculará un usuario con una membresía durante un mes calendario y conservará el precio aplicado en ese momento. Las clases no serán originadas por planes; la asignación y la asistencia serán las relaciones del usuario con cada clase.

Las reservas de cancha normales, en cambio, se pagarán por uso según su duración, mediante una configuración de precio (`precios_reservas_cancha`) independiente de las membresías.

Esos precios de reserva se gestionarán por separado de las membresías. Cada reserva copiará el precio aplicado para conservar su historia. El dinero efectivamente cobrado se registrará por separado como ingreso.

El sistema no controlará automáticamente la cantidad de clases, frecuencia ni cumplimiento de un plan mensual. Las reservas cubiertas por un pase seguirán registrándose como reservas concretas.

Las reservas normales se vincularán con su configuración de precio y las reservas con pase con la membresía vigente utilizada por su organizador.

Una tarea periódica ejecutada mediante Celery vencerá automáticamente las membresías de usuarios activas cuando haya finalizado su período. Otra tarea periódica completará automáticamente las clases y reservas cuyo horario ya finalizó y que nadie completó manualmente; no reemplaza la finalización manual, que sigue disponible.

El sistema calculará automáticamente el descuento o recargo por fecha de pago (ver `1_organizacion.md`, 3.1) únicamente al procesar un cobro online de un **plan** a través del portal (ver 2.7), ya que en ese flujo no hay un administrador interviniendo para decidirlo. Un pase se cobra siempre a su `precio_vigente` de catálogo, sin ese ajuste: la regla es propia de los planes. Para los pagos registrados manualmente en sede, la aplicación de esa regla sigue a cargo de la administración; el sistema no la calcula por sí solo en ese caso.

### 2.5 Ingresos

El sistema registrará el dinero recibido por la academia. Cada ingreso tendrá exactamente uno de estos orígenes: membresía de usuario, reserva u otro concepto. Las membresías y reservas podrán recibir pagos parciales mediante varios ingresos. La administración podrá consultar y buscar los ingresos registrados, filtrando por origen, usuario, período o estado.

Cada membresía de usuario y reserva mostrará un resumen de cobro calculado: total aplicado, suma de ingresos en estado `cobrado`, pendiente y excedente. Se usarán los precios históricos de la operación; en reservas con pase se agregarán los adicionales por invitados sin cobertura, incluidos los no identificados. Los ingresos anulados no sumarán y el resumen se actualizará al anular un ingreso o cambiar la cobertura de invitados. El estado de pago (sin pagos, pago parcial, completo, con excedente o sin cargo) será independiente del estado operativo de la membresía o reserva. En operaciones canceladas se mostrarán diferencias históricas, sin convertirlas automáticamente en deuda, devolución o crédito transferible a una reprogramación.

Si un ingreso manual, incluido el primero o el registrado al crear una reserva, lleva el cobro acumulado por encima del total aplicado, el sistema mostrará los importes y exigirá confirmación explícita y un motivo, conservado en las observaciones del ingreso. No se guardará el ingreso —ni la reserva nueva asociada— hasta confirmar. La confirmación será válida durante 30 minutos para el origen, monto, total y cobrado revisados; si cambian, se pedirá nuevamente. Registro y anulación de ingresos se serializarán por operación para que cobros simultáneos se validen sobre el saldo actualizado. Los ingresos de otros conceptos no tendrán esta comparación porque no poseen un total pactado asociado.

Los ingresos de otros conceptos conservarán una descripción obligatoria. Una vez registrados, los ingresos no podrán editarse ni eliminarse; solo podrán anularse, por ejemplo ante un error de carga. Este módulo, y la posibilidad de anular ingresos, quedará reservado exclusivamente al rol Administrador.

El sistema no incluirá, en esta etapa, un módulo de egresos generales de la academia: esa contabilidad seguirá llevándose fuera del sistema.

### 2.6 Notificaciones

El sistema enviará notificaciones automáticas por email en los siguientes casos: confirmación de alta de cuenta, recuperación de contraseña, confirmación de suscripción a una membresía o pase (pago aprobado por MercadoPago), confirmación de una reserva propia, invitación a una reserva con pase, cancelación de una reserva o clase que afecta al usuario, reprogramación de una reserva cancelada por un motivo ajeno al cliente, vencimiento próximo de una membresía, recordatorio de la próxima clase asignada y asignación de un profesor a una clase o turno programado.

Las notificaciones se enviarán únicamente por email; no habrá una bandeja de notificaciones dentro del sistema. Las comunicaciones no cubiertas por estos casos seguirán realizándose por fuera del sistema.

### 2.7 Portal de usuarios

El sistema tendrá un único portal de acceso externo, para cualquier persona que se registre como usuario, separado de la interfaz de gestión interna (ver intro de la sección 2).

El catálogo de planes, pases y precios vigentes solo podrá consultarse estando registrado y autenticado con el rol Público: es el equivalente, dentro del sistema, a tener que preguntar en la sede antes de conocer los precios.

Un usuario con rol Reservas podrá consultar, crear y cancelar sus propias reservas de cancha desde el portal, normales o con pase, con las mismas reglas que la gestión interna (ver 2.2); se asigna automáticamente junto con Público. En una reserva con pase, podrá elegir como invitados a otros usuarios ya registrados, sin que se les exija tener pase; cada invitado identificado recibe una notificación de la invitación.

Un usuario autenticado con rol Público podrá suscribirse a un plan o a un pase pagando online a través de MercadoPago; activar el primer plan le otorga el rol Alumno, pero contratar un pase no lo otorga. Un usuario con rol Alumno podrá consultar, en modo de solo lectura, su membresía vigente, su historial de membresías, su historial de clases con asistencia y sus próximas clases asignadas.

El rol Público permite consultar el perfil propio, de solo lectura desde el portal: los cambios de datos de contacto (email, celular) y demás datos seguirá gestionándolos la administración. En la etapa administrativa se reutiliza el detalle del usuario conectado; las pantallas del portal, incluido su catálogo y suscripciones, siguen pendientes.

Las reservas creadas desde el portal se pagarán en la sede, igual que las gestionadas internamente; el portal no integrará un cobro online para reservas.

Quedan fuera del portal en esta etapa: elegir el turno semanal de un plan (lo sigue asignando la administración), solicitar recuperaciones de clase, y notificaciones dentro del sistema más allá del email.
