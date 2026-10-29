# Criterios del sistema

## 1. Propósito

Este documento resume los criterios generales del sistema a desarrollar para la Academia de Tenis TM, tomando como base el funcionamiento actual de la organización (ver `1_organizacion.md`).

El objetivo es definir qué hace el sistema y cómo resuelve cada operación: alcance, permisos, validaciones, interacción, auditoría y procesos automáticos. La representación de esos criterios mediante tablas, atributos, claves y restricciones se describe en `3_modelo_relacional.md`.

---

## 2. Alcance del sistema

El sistema será una única aplicación, con un solo backend y un único modelo de usuarios y roles, expuesta mediante dos interfaces separadas: la gestión interna para el personal (Administrador) y el portal público de autoservicio (Profesores,Público, Alumno, Reservas; ver 2.7). No son sistemas independientes: se separan por audiencia e interfaz, no por datos ni reglas de negocio.

La ocupación se organiza mediante turnos de una hora, con inicio en punto entre 00:00 y 22:00 inclusive y fin dentro de la misma fecha. Cada turno identifica una cancha, fecha y hora; esas coordenadas no se editan. Una reserva, clase o bloqueo ocupa un único turno y conserva estado, observaciones y auditoría de su actividad.

Una actividad Programada ocupa su turno, Anulada lo libera y Finalizada conserva su ocupación histórica. Un turno puede conservar varias actividades Anuladas, pero sólo una no Anulada. La existencia de un turno no significa que esté ocupado.

Las únicas transiciones son Programado a Anulado y Programado a Finalizado. Repetir una operación no sobrescribe su auditoría. Finalizar exige que el turno haya terminado; los bloqueos no pasan a Finalizado y conservan su condición horaria según 2.10. Las modificaciones de los datos específicos de una actividad actualizan también su fecha de última modificación.

Las clases y reservas previamente agendadas deberán respetarse. El sistema impedirá que dos eventos no Anulados ocupen el mismo turno. Ninguna actividad podrá desplazar automáticamente a otra. Las operaciones coordinan la ocupación según 2.12.

Cada sede tendrá su propio horario de funcionamiento, definido por día de la semana y con hasta dos franjas horarias por día (por ejemplo, de 8 a 12 y de 16 a 22). El inicio y el fin de cada franja deberán ser en punto y, si se configuran dos franjas, deberá haber al menos una hora sin funcionamiento entre ellas. Un día sin franjas configuradas significa que esa sede no funciona ese día. Toda reserva, clase o bloqueo debe quedar contenido íntegramente en una única franja habilitada. Esta condición rige para el portal, la administración, la planilla, la generación de clases y las operaciones masivas, sin excepciones confirmables. Un día sin franjas no admite nuevas actividades. Configurar o quitar franjas se rechaza si deja fuera una reserva, clase o bloqueo Programado cuyo turno aún no terminó. Los registros Anulados, Finalizados o con turno terminado se conservan como historia y no impiden actualizar el horario.

### 2.0 Límites temporales y calendario operativo

La historia operativa administrada por el sistema comienza el **1 de agosto de 2026**. Ninguna clase, reserva, bloqueo, contratación de plan o pase, fecha de alta, feriado ni ingreso puede registrarse antes de esa fecha. Esta fecha mínima es absoluta: no avanza con el tiempo, para permitir cargas y correcciones históricas desde el inicio de operaciones. Una eventual importación de historia anterior deberá resolverse mediante un proceso específico, no relajando las validaciones de la operación cotidiana.

Las clases pueden ubicarse desde el inicio de operaciones hasta un año calendario después de la fecha local actual. La agenda diaria y semanal usa ese intervalo y conserva el acceso a la historia. La administración puede registrar clases históricas para reconstruir la actividad. Los bloqueos sólo se crean sobre turnos con inicio futuro, hasta un año calendario después de la fecha local actual; no se registran bloqueos históricos. La anulación de reservas, clases o bloqueos exige que su turno no haya comenzado. Una reserva nueva o reprogramada debe comenzar en un horario futuro y su fecha debe estar entre hoy y catorce días después, inclusive; no hay excepciones administrativas. Las consultas conservan el acceso a la historia.

La generación o regeneración de clases acepta rangos dentro de ese mismo intervalo y de **hasta 62 días corridos inclusive** por ejecución. Las consultas de actividad de clases y uso de pases aceptan rangos de **hasta 366 días corridos inclusive**. Un período mayor se consulta por tramos.

Las contrataciones de planes y pases pueden registrarse desde agosto de 2026 hasta el mes calendario siguiente al actual. Guardan el mes cubierto como una fecha del primer día; inicio y fin se calculan y siempre cubren meses completos. Una contratación histórica cuyo mes terminó nace Vencida. Una contratación de un mes futuro puede estar Activa, pero su cobertura corresponde a ese mes.

Los movimientos de caja utilizan únicamente `creado_en`, asignado por el servidor al registrar. No se carga una fecha real histórica ni una fecha futura. Cada movimiento pertenece a la sesión abierta al momento de su registro; apertura, anulación y cierre también utilizan el momento del servidor.

Los feriados pueden registrarse desde el inicio de operaciones hasta cinco años calendario después de la fecha local actual. Registrar o quitar un feriado pasado no modifica retroactivamente las clases que ya fueron generadas.

La fecha de nacimiento es obligatoria y debe estar comprendida entre la fecha local actual menos 120 años y la fecha local actual. No se establece una edad mínima para ser usuario.

Todos estos límites se validan en el servidor y se exponen además en los controles HTML como ayuda de carga. Las comparaciones con el día o momento actual usan la zona `America/Argentina/Buenos_Aires`. Los servicios que escriben datos vuelven a validar las reglas aunque la interfaz ya lo haya hecho, para que no puedan evitarse manipulando formularios o URLs.

### 2.1 Gestión de clases

El sistema incluirá la gestión de clases de la academia.

La gestión incluirá:

- Armado y edición continua de la planilla semanal (semana tipo) por sede: una única planilla viva por sede, sin conservar versiones históricas por período. Cada celda define, para un día y horario, los alumnos asignados.
- Generación de clases concretas para un período seleccionado, a partir del estado actual de la planilla en ese momento.
- Eliminación manual de clases generadas cuyo evento siga Programado, para los casos puntuales donde no corresponda regenerar todo el período.
- Consulta diaria y semanal de clases existentes.
- Creación, edición y cancelación de clases individuales, generadas por la planilla o creadas manualmente.
- Asignación de profesores y alumnos.
- Finalización individual de clases por la administración o por alguno de sus profesores asignados.
- Registro y corrección de asistencia de clases Finalizadas.

Las clases generadas existirán como instancias individuales, con su origen identificado para distinguirlas de las creadas manualmente. No se conservará una referencia a una planilla histórica: la clase concreta ya contiene por sí sola todo lo necesario para la historia operativa (día, horario, cancha, alumnos, profesor).

No existirá una reprogramación de clases como operación propia: una clase Programada puede cambiar de cancha únicamente antes del inicio de su turno, pero nunca cambiar de día ni de horario. Si hace falta mover una clase a otro día u horario, se anula y se crea una nueva, sin ninguna vinculación entre ambas. Las reservas conservan su vinculación de reprogramación según 2.2.

Cambiar de cancha conserva fecha y hora, libera la ubicación original y exige disponibilidad y funcionamiento en el destino. Las clases Anuladas o Finalizadas conservan sus datos y asignaciones; el registro y corrección de asistencia de una clase Finalizada sigue las condiciones de esta sección.

Las clases y la planilla distinguen profesores que dictan la clase y participantes que asisten. Cada clase debe conservar al menos una asignación activa de profesor. Asignar o reactivar a un profesor exige una cuenta activa con rol Profesor; la creación o edición valida esas condiciones antes de guardar. Para los participantes, la selección muestra usuarios con rol Alumno por defecto y permite ampliar la búsqueda a cualquier usuario activo, incluidos profesores que asisten a una capacitación. Participar no exige ni otorga Alumno, no exige contratar un plan y no genera cargos: se admiten alumnos de prueba y participaciones acordadas fuera del sistema. Los planes conservan su alcance comercial definido en 2.4.

Una persona sólo puede tener una asignación activa a una clase no Anulada en la misma fecha y hora, independientemente de sede, cancha o función. Se comprueban conjuntamente profesores y participantes: no puede dictar una clase y asistir a otra simultánea, ni estar asignada a la misma clase en ambas funciones. La creación manual y las operaciones que agregan, reactivan o cambian asignaciones rechazan esos conflictos. Las asignaciones inactivas y las clases Anuladas no generan conflictos.

La coincidencia de una asignación a clase con una reserva no Anulada que la persona organiza o a la que está invitada de forma identificada genera una advertencia confirmable, sin bloquear. Se presenta tanto al crear una clase manual o agregar o reactivar una asignación como al crear una reserva o agregar un invitado, según 2.2. La generación y regeneración desde la planilla no presentan esta advertencia.

Superar seis participantes con asignación activa en una clase grupal genera una advertencia, sin impedir confirmar, cualquiera sea el rol de sus cuentas. La misma advertencia se presenta al editar la planilla y al revisar la generación de clases grupales con más de seis participantes previstos.

Generar las clases de un período es una acción irreversible desde el sistema: no existe una operación de deshacer. Antes de ejecutarla, el sistema mostrará al menos dos confirmaciones explícitas advirtiendo que el proceso no puede deshacerse y que, si hace falta quitar clases generadas, deberá hacerse manualmente.

Modificar la planilla y volver a generar clases para un período ya generado elimina y recrea únicamente las clases de ese período cuyo evento sigue Programado y que fueron generadas por la planilla. Conserva las clases con evento Finalizado o Anulado y las creadas manualmente. La regeneración elimina los eventos y datos de las clases que recrea, pero conserva los turnos concretos.

La vista previa de regeneración calcula ocupación y asignaciones excluyendo las clases que propone eliminar. Las clases conservadas siguen interviniendo en los conflictos. Eliminar una celda de planilla no elimina las clases concretas que originó ni modifica sus asignaciones o su indicador de origen.

La generación y regeneración omiten la clase candidata completa si el turno está ocupado o si cualquiera de sus profesores o participantes ya tiene una asignación activa a otra clase no Anulada de la misma fecha y hora. No eliminan participantes para generar una clase parcial ni abortan las demás candidatas por ese conflicto. También comparan las candidatas de la misma ejecución, en un orden estable por fecha, hora e identificadores de sede y cancha: la primera candidata válida se conserva y las posteriores en conflicto se omiten. También se omiten e informan las candidatas sobre instalaciones inactivas o cuyos usuarios previstos no cumplen las condiciones de asignación. La vista previa identifica cada clase omitida y el motivo. Antes de guardar se vuelve a validar el conjunto revisado; si cambia, se exige revisar la vista previa. Las coincidencias con reservas no son motivo de omisión ni generan advertencias en este proceso.

Registrar o corregir asistencia efectiva exige que el evento de la clase esté Finalizado. La finalización manual puede realizarse junto con la carga de asistencia en una misma operación. La finalización automática sólo cierra el evento por horario y no marca presentes ni ausentes.

Se admite registrar asistencia de usuarios no asignados previamente. El estado Sin registrar distingue la falta de carga de una ausencia efectiva; cada presente o ausente conserva responsable y momento de registro, junto con las modificaciones posteriores.

La creación individual, el cambio de cancha, la generación y la regeneración de clases exigen que cada turno quede íntegramente dentro de una franja de funcionamiento de la sede. Las fechas fuera de horario se omiten y se informan en la vista previa de generación; la creación individual y el cambio de cancha se rechazan. No existe confirmación administrativa que permita una excepción.

Anular una clase es una operación exclusiva del administrador y exige que su turno no haya comenzado. Exige un motivo en texto libre, conserva la historia de la clase y libera el turno que ocupaba. No crea un bloqueo.

Los feriados rigen para todas las sedes y se omiten al generar o regenerar clases desde la planilla. Se permite crear una clase manual en un feriado, respetando las demás reglas de funcionamiento y disponibilidad. Al registrar un feriado con fecha posterior a hoy, se muestra una vista previa de todas las clases Programadas de esa fecha y, al confirmar, se anulan con el motivo común «Clase anulada por registro de feriado». La anulación incluye las clases manuales existentes, conserva sus participantes y auditoría y libera sus turnos; no crea bloqueos ni modifica reservas. El registro del feriado y las anulaciones se confirman en una única transacción, coordinada con la generación y creación de clases. Una clase manual creada después del registro del feriado es una excepción explícita y permanece programada. Registrar un feriado de hoy o pasado no anula clases existentes. Quitar un feriado no reactiva clases Anuladas.

### 2.2 Gestión de reservas

El sistema incluirá la gestión interna de reservas de cancha.

El administrador podrá consultar, buscar, crear y cancelar reservas de usuarios ya registrados. La finalización es automática al terminar el turno, mediante la tarea horaria de Celery. El administrador también podrá finalizar manualmente una reserva Programada cuyo turno terminó, como acción de emergencia sin depender de Celery ni Redis. Ambas opciones registran el estado y el momento de procesamiento, sin responsable de finalización. La disponibilidad y la selección de turnos se centralizan en Agenda (2.8). El usuario consulta, crea y anula sus propias reservas desde el portal según 2.7.

Para crear una reserva, el organizador debe estar activo y tener el rol Reservas o Administrador. La selección administrativa sólo ofrece usuarios que cumplen esas condiciones y el sistema las verifica nuevamente al confirmar. Si el organizador no tiene ninguno de esos roles, el administrador debe asignarle Reservas antes de reservar para él. Registrar una reserva no asigna roles automáticamente. Esta condición permite que el organizador acceda a sus reservas desde su cuenta.

El organizador es el responsable de la reserva y no necesariamente quien utiliza físicamente la cancha. Desde el portal queda como organizador el usuario autenticado, aunque reserve para otras personas; no se selecciona otro organizador ni se registra un beneficiario separado. El administrador puede registrar una reserva para un organizador habilitado, conservando por separado quién realizó el registro. Un mismo usuario puede organizar varias reservas simultáneas en canchas diferentes.

Cada organizador puede tener como máximo cinco reservas cuyo evento tenga estado Programado, sumando todas las sedes, fechas y modalidades. Las invitaciones no consumen este cupo. El límite rige también cuando el administrador registra una reserva para ese organizador, y se aplica a cualquier organizador habilitado, incluidas cuentas administrativas. Se cuenta el estado almacenado: una reserva cuyo turno terminó sigue contando mientras permanezca Programada, aunque Celery se haya demorado o haya fallado. Sólo deja de contar al pasar a Anulada o Finalizada; no se descuenta por horario. La confirmación vuelve a comprobar el cupo según 2.12.

Un invitado identificado de una reserva con pase no puede organizar ni integrar como invitado otra reserva no Anulada de la misma fecha y hora, independientemente de sede, cancha o cobertura del pase. La comprobación es recíproca: agregar al invitado se rechaza si ya organiza o integra otra reserva simultánea, y crear una reserva se rechaza si el organizador ya es invitado de otra simultánea. Organizar varias reservas simultáneas sigue permitido dentro del cupo de cinco. Los invitados no identificados no permiten un control personal.

La coincidencia del organizador o de un invitado identificado con una clase no Anulada a la que esté asignado activamente, como profesor o participante, genera una advertencia confirmable y no bloquea la reserva. La advertencia se aplica al crear reservas y al agregar invitados; las operaciones manuales de clases aplican el control recíproco según 2.1. Las prohibiciones entre reservas y el cupo se validan antes de ofrecer continuar con advertencias. Se mantienen la ocupación exclusiva del turno y las condiciones de acceso, calendario, funcionamiento y precio o pase. La identificación de invitados determina cobertura, adicionales y consumo diario; no acredita presencia física ni sustituye las validaciones comerciales de 2.4.

Toda reserva utiliza un único turno de una hora contenido en una franja de funcionamiento de su sede. La creación permite seleccionar sólo un turno; no admite selección múltiple ni genera reservas agrupadas. Reservar dos horas exige registrar dos reservas independientes.

La fecha elegida debe estar entre hoy y catorce días después y el inicio del turno debe ser futuro. Estas condiciones se aplican al portal, a la administración y a las reprogramaciones, y se vuelven a comprobar al confirmar.

Una reserva podrá ser normal, con precio determinado por la tarifa por turno de su sede, o utilizar una contratación de pase vigente del organizador. Cada reserva tiene número con formato `R-000001`, comprobante, invitados cuando corresponda e ingresos propios.

Toda cancelación de reserva exigirá un motivo de al menos 25 caracteres, sin contar los espacios al principio y al final. Este mínimo se informa en el formulario y se valida en el servidor al confirmar. Un administrador solo puede cancelar la reserva de un usuario por una causa ajena al organizador —clima adverso, torneo, mantenimiento u otro imprevisto—: si el organizador quiere cancelar su propia reserva, debe hacerlo él mismo desde el portal (autoservicio). Para este sistema, que cada usuario tenga y use su propia cuenta para gestionar sus reservas no es una comodidad opcional: es un requisito, precisamente para que esta distinción tenga sentido.

Sólo se puede cancelar una reserva Programada. El usuario con rol Reservas puede cancelar únicamente las propias con al menos una hora de antelación al inicio del turno, incluido el límite exacto de una hora. El administrador puede cancelar la reserva de cualquier organizador hasta antes de su inicio. Una reserva iniciada, Anulada o Finalizada no puede anularse. El sistema verifica estos límites con la fecha y hora completas dentro de la transacción y conserva quién realizó la operación, el motivo y el momento.

Toda anulación de reserva libera el único turno que ocupaba, tanto si la realiza el organizador como el administrador. El motivo se registra en texto libre y no se clasifica. La cancelación no crea un bloqueo.

Los bloqueos y las acciones administrativas sobre varios eventos se definen en 2.10.

La posibilidad de reprogramar depende de quién cancela: un usuario con rol Reservas puede cancelar su propia reserva, pero esa cancelación nunca ofrece reprogramación. El administrador, en cambio, siempre puede ofrecer reprogramarla en el momento —cancela la original y registra una nueva para el día y horario acordados, sujeta a disponibilidad—, ya que por definición está cancelando por una causa ajena al organizador. La reprogramación puede realizarse al anular o más tarde, una sola vez para cada reserva de origen, y vincula la nueva con la original. La nueva cumple las reglas vigentes de una reserva normal o con pase. Cancelar o reprogramar no reintegra dinero ni anula cobros automáticamente. Si corresponde un reintegro, la administración registra un Egreso de categoría devoluciones, con las reglas de caja de 2.5, sin modificar automáticamente la reserva ni los cobros.

Los movimientos Ingreso de una reserva cancelada conservan su estado, para preservar la historia del dinero recibido. Una reserva cancelada no podrá recibir nuevos ingresos.

En una reserva normal no se registrarán invitados. En una reserva con pase se registrará la cantidad total de invitados y se podrán identificar usuarios activos con rol Reservas. Los pases vigentes aplicados a invitados identificados quedarán registrados y cada invitado sin cobertura generará el precio adicional vigente copiado al crear la reserva.

El organizador puede agregar o quitar invitados identificados de su propia reserva con pase mientras el evento siga Programado y falte al menos una hora para el inicio del turno, incluido el límite exacto de una hora. Cada usuario agregado debe estar activo y tener rol Reservas; no puede repetirse ni ser el organizador. La cantidad de invitados identificados no puede superar la cantidad total declarada. Agregar evalúa el pase del invitado según las reglas de cobertura; quitar libera el consumo que correspondía a ese invitado. Las coberturas de los invitados que permanecen no se recalculan automáticamente. El cambio muestra el nuevo total usando el precio adicional unitario conservado en la reserva, exige confirmación y conserva la consulta de cobros vigentes, sin calcular deuda ni modificar movimientos o generar devoluciones. El servidor vuelve a validar permiso, plazo, cantidad, conflictos entre reservas y cobertura dentro de la transacción. Al agregar un invitado comprueba también las coincidencias con clases y solicita la confirmación de la advertencia cuando corresponda.

Al crear cualquier reserva, el sistema buscará automáticamente si el organizador tiene una contratación de pase vigente que cubra la fecha elegida —es decir, una contratación cuyo mes cubierto incluya esa fecha— y, de existir, preguntará si desea utilizarla; si el organizador no quiere usarla, o no tiene ninguna vigente para esa fecha, la reserva sigue por el camino normal. Como el pase es válido solo para su mes calendario y una reserva puede crearse con hasta dos semanas de anticipación, es posible reservar para el mes siguiente sin que el pase del mes actual lo cubra: en ese caso la reserva cae en el camino normal, no es un error.

Cada pase (libre o de fin de semana, ver `1_organizacion.md` 3.2) se considerará ilimitado en cantidad de reservas durante su vigencia, pero limitado a una cantidad de horas por día calendario configurada en cada pase (inicialmente dos), sin importar si el uso proviene de reservas como organizador o como invitado; el pase de fin de semana además solo podrá usarse sábados y domingos. Al elegir usar el pase, el sistema validará primero si el día está habilitado para ese pase y luego calculará las horas ya usadas ese día; si el día no está habilitado, se rechaza sin llegar a revisar las horas; si el día está habilitado pero no queda ninguna hora disponible, también se impide continuar con pase. Cada reserva cubierta consume una hora y exige al menos una hora disponible. Cualquier usuario activo con rol Reservas puede identificarse como invitado, tenga o no pase: el sistema revisa si su propio pase tiene el día habilitado y al menos una hora disponible; si no, se lo cuenta como invitado sin pase y genera el adicional correspondiente, sin impedir el resto de la reserva.

Organizador, modalidad, importe o pase aplicado y turno de una reserva no se editan. Cambiar cancha, fecha u horario exige anular la original y registrar otra reserva. Las modificaciones de invitados admitidas en esta sección sólo se realizan mientras el evento siga Programado; una reserva Anulada o Finalizada conserva también sus invitados.

Crear una reserva será siempre un recorrido guiado único, sin abandonar el proceso ni volver a ingresar datos ya conocidos, que resuelve en un mismo flujo si corresponde precio normal o pase. El recorrido comienza seleccionando un turno libre en Agenda. Cuando la gestiona el administrador, continúa buscando y seleccionando al organizador entre los usuarios ya existentes, y confirma la reserva antes de registrar cualquier cobro como otra operación; el organizador deberá existir previamente como usuario, este recorrido no incluye el alta de uno nuevo. Cuando la gestiona un usuario con rol Reservas para sí mismo desde el portal, el organizador es siempre el propio usuario y no hay registro de ingreso: el pago se resuelve en la sede.

### 2.3 Usuarios y roles

El sistema no distinguirá entre clientes y usuarios del sistema: toda persona que interactúa con el sistema, incluidas las que hoy se gestionan como clientes, es un **usuario**. Lo que cada usuario puede hacer lo determinan los roles que tiene asignados, no una categoría separada de "cliente".

El alta exige nombre, apellido, correo, celular y fecha de nacimiento. Nombre y apellido admiten hasta 100 caracteres y no contienen números. El celular se valida como móvil argentino, puede pertenecer a un tercero y no debe ser único. Correo y nombre de usuario son únicos sin distinguir mayúsculas y minúsculas; los formularios comprueban la disponibilidad antes de guardar.

En el alta administrativa y el autorregistro, el nombre de usuario se genera con el apellido normalizado y la inicial del nombre. Si ya existe, se agrega un sufijo numérico desde 1. Se muestra sin permitir su edición y se confirma al guardar.

Los roles forman un catálogo fijo: no se crean, renombran ni eliminan desde la aplicación.

Los roles serán:

- **Administrador**: acceso total al sistema. Es un rol exclusivo: una cuenta administrativa sólo tiene esta asignación en `usuarios_roles`, sin Público, Reservas, Profesor ni Alumno. La marca técnica `is_superuser` permite que Django le conceda todos los permisos. Se crea con el comando `crear_administrador` ejecutado por el desarrollador y opera desde la interfaz de Academia TM. Ningún administrador puede asignar ni quitar este rol desde la aplicación.
- **Profesor**: gestiona las clases en las que está asignado para dictar y consulta las clases a las que asiste como participante. Lo asigna un administrador, al crear el usuario o mediante la gestión de roles. Sólo puede quitarse si el usuario no tiene clases Programadas como profesor. Participar en una capacitación no concede acciones de docencia sobre ella.
- **Público**: permite consultar el catálogo de la academia y el perfil propio. Las contrataciones se registran por la administración. Corresponde a una cuenta registrada y autenticada, no a un visitante anónimo. Se asigna automáticamente al crear una cuenta no administrativa y no puede quitarse desde la aplicación.
- **Reservas**: permite crear, cancelar y consultar reservas propias. Toda cuenta no administrativa lo recibe automáticamente desde su alta, se autoregistre o la registre la administración. Un administrador puede quitarlo únicamente si el usuario no tiene reservas programadas. El catálogo y el perfil corresponden al rol Público.
- **Alumno**: permite consultar sus clases asignadas y su historial de asistencia. Una cuenta no administrativa lo obtiene al registrar una contratación Activa de plan, mediante la administración, si no lo tiene; el alta administrativa no exige que se haya registrado un ingreso. Un pase no otorga este rol. También puede asignarlo un administrador al crear la cuenta o mediante la gestión de roles. No se retira automáticamente al vencer una contratación; sólo un administrador puede quitarlo respetando las condiciones del retiro.

El alta de una cuenta no administrativa, por autorregistro o por la administración, guarda Público y Reservas junto con el usuario y los roles adicionales autorizados de Profesor o Alumno. La operación se confirma completa o se revierte según 2.12. Las asignaciones administrativas y automáticas respetan la exclusividad del rol Administrador. Profesor y Alumno son incompatibles entre sí: la misma cuenta no puede tener ambos. Para cambiar de rol se retira primero el anterior, respetando sus condiciones de retiro. Asistir como participante a una clase o capacitación no requiere cambiar de rol.

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

Las contraseñas provisorias del alta y del restablecimiento se muestran una sola vez y no pueden consultarse después. La recuperación utiliza el enlace enviado por email mediante el mecanismo nativo de Django, con vigencia de una hora (`PASSWORD_RESET_TIMEOUT = 3600`). Al completar la recuperación, el enlace utilizado y los anteriores quedan invalidados por el cambio de contraseña. Cambiar el correo o registrar un nuevo inicio de sesión también puede invalidarlos. Solicitar otro enlace no cambia la cuenta ni invalida por sí solo los enlaces anteriores.

A fines prácticos, un usuario con rol Alumno se considera vigente en un período determinado cuando tiene actividad de clases en ese período, por ejemplo un plan activo. Esto es informativo, para reportes y consultas; no equivale al estado de la cuenta ni condiciona ninguna otra regla del sistema.

La administración podrá asignar o quitar Profesor y Alumno, y volver a otorgar o quitar Reservas después del alta, únicamente a cuentas no administrativas. El retiro respeta las condiciones siguientes. Los perfiles de administradores no ofrecen modificación de roles y el servidor rechaza cualquier intento de asignarles otros.

El retiro de roles debe respetar las siguientes condiciones:

| Rol | Condición para quitarlo |
|---|---|
| Público | No se puede quitar. |
| Reservas | El usuario no tiene reservas propias en estado Programado. |
| Alumno | El usuario no tiene contrataciones de planes en estado Activo. Un pase no impide retirar Alumno. |
| Profesor | El usuario no tiene asignaciones activas como profesor en clases cuyo evento esté Programado. |

Si existe una relación que impide el retiro, se rechaza la operación y se conserva el rol. No se cancelan reservas, contrataciones ni clases automáticamente para permitir quitarlo. Los registros históricos se conservan; las reservas y clases Anuladas o Finalizadas y las contrataciones Vencidas o Anuladas no bloquean por sí solas el retiro. Las comprobaciones se basan en el estado registrado, no solo en que una fecha haya pasado.

El estado activo o inactivo de las cuentas administrativas se gestiona con las mismas reglas de cambio de estado que el resto de los usuarios. `is_superuser` es la representación técnica de sus permisos, no otro rol ni una opción editable por separado.

Una persona con permiso para cambiar estados no puede desactivar su propia cuenta. Un administrador activo solo puede ser desactivado cuando permanece al menos otro administrador activo. Estas condiciones se validan al confirmar la operación y los cambios concurrentes se serializan para impedir que dos desactivaciones dejen al sistema sin administradores.

Una cuenta inactiva no puede autenticarse. La inactivación registra automáticamente la fecha y hora de baja de la cuenta. La reactivación elimina esa marca, de modo que una cuenta activa no conserva una fecha de baja vigente. Ambas operaciones actualizan también la fecha de última modificación.

La aplicación no expone la interfaz administrativa técnica de Django; toda operación cotidiana se realiza desde las pantallas de Academia TM.

### 2.4 Planes, pases, contrataciones y precios

Los catálogos de planes y pases son independientes. Cada producto guarda nombre, descripción, precio vigente, estado y su configuración específica.

- `planes` define modalidad individual o grupal, frecuencia de uno a siete encuentros semanales y una o dos clases consecutivas de una hora por encuentro.
- `pases` define variante Libre o Fin de semana, límite diario de horas y adicional vigente por invitado sin cobertura. Libre habilita todos los días; Fin de semana sólo sábados y domingos.

Cada combinación de plan y cada variante de pase es un producto completo de su catálogo. Nombre, descripción y precios pueden actualizarse; la configuración estructural se conserva cuando tiene contrataciones históricas. Un producto inactivo no admite contrataciones nuevas y no altera las existentes.

El nombre es único entre productos Activos de cada catálogo; planes y pases no comparten esa comparación. Los precios de catálogo pueden ser cero y no pueden ser negativos; el límite diario de un pase es positivo.

`planes_usuarios` y `pases_usuarios` registran las contrataciones por separado. Cada contratación identifica al usuario y al producto y conserva el mes cubierto, fecha efectiva de alta, precio aplicado, responsable del registro, observaciones y estado Activo, Anulado o Vencido. Las contrataciones se registran administrativamente con responsable obligatorio y cobro separado.

Un usuario puede tener un plan y un pase para el mismo mes, pero no dos contrataciones no Anuladas del mismo tipo. Los Vencidos también protegen la exclusividad histórica de su mes. Anular conserva la fila y permite registrar un reemplazo. Renovar para otro mes crea una contratación nueva; usuario, producto, mes e importe aplicado no se editan en un registro existente.

Sólo se anulan contrataciones Activas. La anulación administrativa exige motivo y conserva administrador y momento, sin modificar automáticamente cobros, clases, reservas ni coberturas aplicadas. Si corresponde reintegrar dinero, se registra un Egreso de categoría devoluciones según 2.5, separado de la anulación de la contratación. Un pase Anulado no admite nuevas aplicaciones, pero mantiene las coberturas registradas. El vencimiento se define en 2.13 y los avisos en 2.6.

Registrar una contratación Activa de plan otorga Alumno si falta ese rol y el titular no es administrador; un pase no lo otorga. Una cuenta con rol Profesor no puede contratar planes de clases mientras conserve ese rol. La incompatibilidad se valida al registrar la contratación administrativa. Contratar pases no tiene esta restricción. El titular puede consultar sus propias contrataciones de ambos tipos y el acceso a un pase no exige Alumno. Las clases se organizan mediante asignaciones y asistencia; contratar un plan no genera clases ni asigna horarios automáticamente. La frecuencia contratada se administra según la organización de la academia, sin un control automático de cumplimiento del plan.

Los precios vigentes se aplican a operaciones nuevas. Cada contratación o reserva conserva sus importes acordados; actualizar el catálogo o la tarifa de sede no modifica las operaciones existentes. La historia comercial se consulta a partir de esos importes, sin un historial independiente de cambios de precio.

El Administrador configura un único precio positivo por turno de una hora en cada sede, común a todas sus canchas. El valor puede estar vacío mientras no se configure; sin tarifa no se confirma una reserva normal. La configuración y el registro se coordinan bloqueando la sede dentro de la transacción. Un importe igual al vigente no genera cambios.

Al registrar una reserva normal, el servidor valida y copia el precio vigente de la sede. Si cambió mientras se seleccionaba el turno, muestra el nuevo total y exige confirmar nuevamente. El total de una reserva normal es el precio por turno aplicado, sin multiplicadores ni subtotales horarios.

La contratación mensual guarda el importe acordado, separado del dinero cobrado. En el alta administrativa se propone el precio vigente y puede establecerse el importe final correspondiente a un ajuste.

El descuento o recargo de los planes sigue la política de `1_organizacion.md`, sección 3.1. La administración resuelve los ajustes según la fecha del pago y conserva el importe acordado en la contratación. Un pase utiliza su precio vigente sin ese ajuste. La caja registra el cobro sin recalcular ese importe ni comparar automáticamente el acumulado con el precio aplicado.

Una reserva con pase referencia la contratación concreta del organizador en `pases_usuarios`; los invitados cubiertos referencian sus propias contrataciones. Se valida titularidad, mes, estado Activo, día habilitado y horas disponibles. El consumo diario suma una hora por reserva no Anulada cubierta, como organizador o invitado, contando cada reserva una sola vez por contratación. La cobertura se verifica con el mes y las demás condiciones, aunque una tarea de vencimiento todavía no haya actualizado el estado. No se almacena un saldo de horas.

### 2.5 Caja y movimientos

El sistema administra una única caja para toda la academia y como máximo una sesión abierta. `movimientos_fondos` es la fuente única de cobros y registra las clases Ingreso, Egreso, Aporte y Retiro. Los cobros se cargan manualmente; no hay pasarela ni confirmación automática de pagos. Se admiten pagos parciales mediante varios ingresos vinculados al mismo origen. El sistema no calcula deuda, pendiente, excedente ni estado de pago y no compara el cobro acumulado con el precio aplicado ni exige confirmación de sobrepago.

#### 2.5.1 Acceso y sesión

El acceso a caja exige usuario autenticado, activo, sin cambio obligatorio de contraseña y con rol Administrador. La marca `is_superuser` por sí sola no habilita ese acceso. El administrador que abre es el responsable fijo y quien registra movimientos y cierra la sesión. Otros administradores pueden consultar, pero no operar esa sesión. No hay reasignación. Anular un movimiento requiere ser responsable de la sesión abierta actual, incluso si pertenece a una sesión cerrada. Los permisos se verifican en vistas y se vuelven a comprobar en los servicios al confirmar.

La apertura declara efectivo inicial no negativo y usa el momento del servidor. El contado del último cierre es una referencia, no un importe trasladado automáticamente. Si el inicial difiere, se muestra un aviso y se exige explicación breve en `motivo_apertura`; si coincide o es la primera apertura, queda vacío. La diferencia entre sesiones no genera un movimiento. Puede haber varias sesiones sucesivas por día y una sesión puede atravesar medianoche. No hay cierre automático ni reapertura.

#### 2.5.2 Registro y medios

Cada movimiento pertenece a una sesión abierta y registra concepto obligatorio, monto positivo en pesos, medio, fecha del servidor, responsable y UUID único de operación. Los importes usan dos decimales y Decimal, sin floats. Los estados son Vigente y Anulado. La única fecha de carga es `creado_en`; no se ingresa una fecha real histórica ni futura. Apertura, anulación y cierre utilizan también el momento del servidor y la zona `America/Argentina/Buenos_Aires`.

Los medios son efectivo, transferencia, tarjeta y QR. Los no efectivos requieren referencia de texto y verificación manual del administrador: recepción para un ingreso, pago realizado para un egreso o aprobación de la operación con tarjeta. La referencia identifica la operación o el comprobante; no almacena credenciales ni datos completos de tarjeta. Registrar una tarjeta no confirma su acreditación bancaria. El módulo no administra saldos de cuentas personales ni liquidaciones de tarjetas.

Un Ingreso puede referenciar como máximo una contratación concreta de plan, una contratación concreta de pase o una reserva; el vínculo es opcional y el concepto siempre es obligatorio. No referencia productos del catálogo. No se registran nuevos ingresos vinculados a contrataciones Anuladas ni reservas con evento Anulado. La reserva o contratación se confirma y luego se registra el cobro en una operación separada; si falla la carga monetaria, el origen permanece confirmado. Registrar un cobro no crea ni renueva la contratación ni modifica el precio.

Un Egreso exige categoría, concepto, destinatario de texto, monto y medio. Las categorías son alquiler, servicios, profesores, insumos, mantenimiento, publicidad, comisiones, otros y devoluciones. No requiere crear usuarios para proveedores. Registrar pagos a profesores no calcula salarios ni honorarios. El registro comprende pagos realizados, no compromisos futuros, y no constituye contabilidad general.

Aporte y Retiro son únicamente efectivo, con concepto explicativo. No se cuentan como ingresos ni gastos operativos. Retirar efectivo para depositarlo no genera un ingreso por transferencia. Una salida en efectivo no puede superar el efectivo esperado disponible. Si hace falta aportar dinero, el aporte se registra como otra operación y luego se carga la salida.

#### 2.5.3 Devoluciones y anulaciones

Una devolución es dinero efectivamente reintegrado a un cliente y se registra como Egreso de categoría devoluciones, por efectivo, transferencia, tarjeta o QR. Exige concepto, destinatario, monto positivo y referencia si el medio no es efectivo. No tiene vínculo ni tope contra un ingreso. Se identifica por separado en los resúmenes y no se presenta como gasto operativo. No modifica automáticamente cobros, contratación ni reserva. Cancelar o reprogramar una reserva, o anular una contratación, no reintegra dinero ni anula cobros automáticamente: si corresponde devolver, la administración registra el egreso.

La anulación invalida una carga errónea, no entrega dinero. Ingresos y egresos, incluidas devoluciones, así como aportes y retiros, pueden anularse con motivo obligatorio, actor y momento del servidor. No se borran ni se editan sus datos originales. Un movimiento Anulado no se reactiva ni vuelve a anularse.

En una sesión abierta, la anulación recalcula el efectivo esperado y no puede dejarlo negativo. En una cerrada no modifica los importes guardados del cierre ni sus totales históricos. El hecho correcto se registra como nuevo movimiento independiente en la sesión actual, sin vínculo automático con la carga anulada. Si es efectivo tiene efecto ordinario aunque no haya movimiento físico actual: puede producir una diferencia explicada y el arqueo no representa exclusivamente movimientos físicos de esa sesión.

#### 2.5.4 Arqueo y cierre

`efectivo esperado = efectivo inicial + ingresos en efectivo + aportes − egresos en efectivo − retiros`

El cálculo de la sesión abierta usa solo movimientos Vigentes. Transferencia, tarjeta y QR figuran en los resúmenes, pero no alteran el efectivo esperado. Los egresos de categoría devoluciones en efectivo también son salidas para el arqueo.

El responsable declara efectivo contado no negativo y el servidor calcula `diferencia = contado − esperado`: positiva significa sobrante y negativa, faltante. Si no es cero se exige motivo. No se genera un movimiento automático por la diferencia. Al confirmar se recalcula el esperado y se guardan esperado, contado, diferencia, motivo y momento del servidor. Si el cálculo definitivo presenta diferencia sin explicación, se solicita revisar y completar. Cancelar el formulario conserva Abierta la sesión.

El servicio impide modificar, borrar o reabrir una sesión Cerrada y agregarle movimientos. El resumen histórico incluye los movimientos válidos al cerrar: sin anulación o con `anulado_en > cerrada_en`. Los anulados con `anulado_en <= cerrada_en` no suman. Las anulaciones posteriores son consultables sin modificar los importes guardados del cierre.

#### 2.5.5 Consultas, auditoría y consistencia

La consulta comercial de una contratación o reserva usa movimientos Ingreso vinculados en estado Vigente y excluye toda anulación, sin calcular deuda. Ese criterio es distinto del resumen histórico de una sesión cerrada. Los egresos por devoluciones se consultan como salidas y no alteran automáticamente la consulta comercial de cobros.

Caja ofrece resumen de sesión por clase y medio, historial por fecha de apertura y estado, y movimientos filtrados por fecha de registro, sesión, clase, medio y estado. El detalle muestra datos de creación, referencia, vínculo comercial y anulación cuando corresponde. Los datos se muestran primero; apertura, carga, anulación y cierre se revelan mediante disparadores explícitos. Las listas usan filas compactas y un menú por movimiento, sin formularios permanentes por fila. El estado vacío tiene un texto breve y una acción principal; solo se ofrecen acciones válidas para el estado y los permisos.

Registro, anulación y cierre usan `transaction.atomic` y `select_for_update` sobre la sesión. Anular un movimiento de otra sesión bloquea también esa sesión de origen. La apertura usa transacción e índice único parcial sobre estado Abierta; una colisión informa que existe una sesión abierta. Un registro concurrente con cierre se confirma dentro de la sesión abierta o se rechaza por sesión cerrada. Se validan campos, responsabilidad, estado, vínculo y disponibilidad dentro de la transacción; un error revierte la operación completa. Las escrituras usan POST y protección CSRF; las consultas no modifican datos.

El UUID de movimiento se conserva al reenviar el formulario. Un reintento con el mismo actor y contenido devuelve el registro existente; con otros datos se rechaza. Es distinto del UUID del contexto transaccional de auditoría y no se exige que coincidan.

Ambas tablas participan de la auditoría transversal de 2.14: el cierre es una modificación y la invalidación de un movimiento es una anulación. Las altas conservan sus campos de creación sin generar entradas de alta en el historial. La inmutabilidad de caja se garantiza en servicios; no hay triggers adicionales que impidan modificar sus tablas por SQL. Los triggers de auditoría registran esos cambios, pero no los impiden.

### 2.6 Notificaciones

El sistema enviará notificaciones automáticas por email en los siguientes casos: confirmación de alta de cuenta, recuperación de contraseña, confirmación de una reserva propia, invitación a una reserva con pase, cancelación de una reserva o clase que afecta al usuario, reprogramación de una reserva cancelada por un motivo ajeno al cliente, vencimiento próximo de una contratación, recordatorio de la próxima clase asignada y asignación de un profesor a una clase o turno programado.

Las notificaciones se enviarán únicamente por email; no habrá una bandeja de notificaciones dentro del sistema. Las comunicaciones no cubiertas por estos casos seguirán realizándose por fuera del sistema.

El aviso de vencimiento se evalúa diariamente para contrataciones Activas cuyo fin esté dentro de los próximos tres días. Cada contratación conserva una marca de envío para evitar repetir el aviso.

El recordatorio diario selecciona las clases Programadas de mañana y sus participantes con asignación activa, sin exigir Alumno. El envío y su marca se resuelven por participante y clase, sin depender de los demás. Reactivar una asignación restablece su marca de recordatorio a no enviado.

### 2.7 Portal de usuarios

El sistema tendrá un único portal de acceso externo, para cualquier persona que se registre como usuario, separado de la interfaz de gestión interna (ver intro de la sección 2).

El catálogo de planes, pases y tarifas vigentes sólo puede consultarse estando registrado y autenticado con el rol Público: es el equivalente, dentro del sistema, a tener que preguntar en la sede antes de conocer los precios.

Un usuario con rol Reservas podrá consultar, crear y cancelar sus propias reservas de cancha desde el portal, normales o con pase, con las mismas reglas que la gestión interna (ver 2.2); se asigna automáticamente junto con Público. El portal incluye la grilla de Agenda para consultar disponibilidad y elegir un turno libre desde el que iniciar la reserva. Agenda es la entrada única para las actividades. El panel de una reserva propia permite acceder a su detalle y comprobante, con las acciones propias autorizadas. La búsqueda de registros, incluidos los Anulados, se contempla dentro de Agenda y está pendiente de implementación. En una reserva con pase, podrá elegir como invitados a otros usuarios activos con rol Reservas, sin que se les exija tener pase, y modificar los invitados identificados según 2.2; cada invitado identificado recibe una notificación de la invitación.

Cualquier usuario autenticado puede consultar sus clases asignadas como participante y su historial de asistencia, aunque no tenga Alumno. El Administrador conserva el acceso total. Los profesores tienen acciones de docencia únicamente en las clases que están asignados a dictar; asistir como participante no agrega esas acciones. Cualquier titular autenticado puede consultar sus propios planes y pases contratados, incluidos sus importes, período, cobros vigentes desde movimientos y usos, sin exigir Alumno para un pase. La consulta propia de cobros no permite acceder a caja, informes globales ni movimientos de terceros y no muestra deuda calculada.

El perfil propio permite consultar los datos personales y de la cuenta, los roles y el estado, y cambiar únicamente la contraseña propia mediante **Cambiar mi contraseña**. La modificación del correo se realiza exclusivamente por el Administrador mediante la gestión de usuarios; el resto de los datos personales no tiene edición desde la aplicación. La obligación de reemplazar una contraseña provisoria se cumple antes de acceder al perfil o a cualquier otra función del portal. El portal ofrece catálogo y consulta de contrataciones propias; las altas comerciales y los cobros son administrativos.

Las reservas creadas desde el portal se pagarán en la sede, igual que las gestionadas internamente; el portal no integrará un cobro online para reservas.

Quedan fuera del portal en esta etapa: elegir el turno semanal de un plan (lo sigue asignando la administración), solicitar recuperaciones de clase, y notificaciones dentro del sistema más allá del email.

### 2.8 Agenda unificada

Agenda permite consultar disponibilidad, elegir turnos y ejecutar las acciones autorizadas. La administración accede a toda la ocupación; el portal ofrece la misma grilla para consultar disponibilidad y operar sobre reservas propias según los permisos. Los turnos ocupados por actividades ajenas se muestran como No disponible, sin tipo de actividad, identificadores, participantes, observaciones ni datos comerciales. Su panel sólo muestra sede, cancha, fecha y horario. Las acciones administrativas son exclusivas de la administración. La vista diaria muestra todas las canchas de una sede en columnas y las horas en filas; la semanal muestra una cancha con los días de lunes a domingo en columnas y las horas en filas. Se navega mediante sede, cancha cuando corresponde, fecha, período anterior o siguiente y Hoy. El cambio de sede limpia la selección de cancha y turno. Los límites del calendario no se amplían por cambiar de vista.

En el portal se ocultan las filas cuyo turno ya comenzó cuando ninguna cancha de esa fila contiene un evento propio. Las filas con eventos propios se conservan completas para consultar su detalle y comprobante, manteniendo la privacidad de las demás celdas. Las pausas iniciadas sin eventos propios también se ocultan. El corte se aplica al inicio del turno, con la zona horaria del sistema. La administración conserva la grilla completa. Un día pasado sin eventos propios muestra No tenés eventos en esta fecha; para hoy, sin eventos propios ni turnos pendientes de inicio, se informa esa condición.

La administración dispone además de una consulta rápida de disponibilidad: ingresa sede, fecha y hora de inicio, y puede indicar opcionalmente una cancha de esa sede. Sin cancha seleccionada se consultan todas sus canchas. El resultado identifica las canchas disponibles para el turno de una hora solicitado, sin exigir navegar por Agenda. Aplica los mismos horarios, estados de instalaciones, ocupación y límites de calendario que la consulta de Agenda, sin registrar turnos ni eventos. La consulta informa disponibilidad; la creación de una reserva comienza en Agenda y conserva su límite de catorce días.

En la vista administrativa cada celda distingue turno libre, reserva, clase o bloqueo. Seleccionarla muestra un panel con cancha, fecha, horario, participantes, estado e importes cuando corresponden y las acciones autorizadas para ese evento. En la vista diaria el panel acompaña a la grilla y se ubica debajo en pantallas pequeñas. Seleccionar un turno o cerrar el detalle actualiza sólo el panel y el resaltado, sin recargar la grilla ni desplazar la página. La consulta comprueba acceso y selección en el servidor. Ante un fallo conserva el detalle anterior y muestra un aviso; ante selecciones rápidas sólo aplica la última respuesta. La presentación e interacción de la vista semanal están pendientes de definición. Sobre un turno libre se puede crear una reserva, clase o bloqueo; sobre una reserva o clase, anular para liberar o anular y bloquear; sobre un bloqueo, anular para liberar. Cada acción conserva sus permisos, límites temporales y confirmaciones. La finalización administrativa de emergencia de una reserva vencida también está disponible desde su detalle en la agenda.

La consulta no registra eventos ni necesita una tarifa configurada. Los espacios libres se representan a partir del horario de funcionamiento, sin crear turnos persistidos por la mera consulta. Las actividades existentes fuera de las franjas actuales permanecen visibles. Una franja común sin actividad se representa como pausa; si un evento ocupa una hora de esa pausa, se muestra esa hora y su actividad. Los días o canchas sin horarios ni eventos tienen un estado vacío. Las instalaciones inactivas se incluyen para consulta histórica y no admiten nuevas actividades. Las horas fuera de las franjas no ofrecen creación de reservas, clases ni bloqueos.

El calendario puede consultarse desde el inicio de operaciones hasta un año después de la fecha local actual. La semana que cruza un límite mantiene sus siete columnas, pero las fechas fuera del intervalo no ofrecen acciones. Ver una fecha futura no habilita reservas fuera de los catorce días de anticipación. La hora actual se destaca únicamente en el margen de horarios con la indicación Ahora; no se dibuja una línea sobre los eventos. Los turnos iniciados se atenúan y conservan su detalle. Las comparaciones utilizan la zona horaria del sistema.

Los formularios de acción permanecen vinculados al turno seleccionado. La confirmación muestra el organizador, cancha, fecha, horario e importe de la reserva; una ocupación o precio que cambió exige revisión. Una anulación identifica la reserva confirmada y no puede aplicarse a otra actividad que haya ocupado el mismo turno entretanto. Cada operación reutiliza sus validaciones transaccionales y vuelve a comprobar el acceso.

La administración puede consultar toda la ocupación. El profesor consulta las clases que dicta y aquellas a las que está asignado como participante, con las acciones propias de cada función y sin datos personales o comerciales de reservas ajenas. El portal mantiene las consultas y acciones propias definidas en 2.7. La creación y consulta de reservas se inicia desde Agenda, tanto en la administración como en el portal, sin una sección independiente de Reservas o Mis reservas ni un formulario de alta separado. El panel de cada reserva ofrece acceso a su detalle y comprobante; se conservan los datos de auditoría y las acciones autorizadas sobre registros existentes. La búsqueda por criterios y el acceso a eventos Anulados que no ocupan una celda se contemplan dentro de Agenda y están pendientes de implementación. Los bloqueos se consultan y operan desde Agenda, sin una sección independiente de navegación.

Los turnos vacíos cuyo horario ya terminó se muestran sin enlace ni interacción. Los eventos finalizados conservan acceso a su detalle histórico.


### 2.9 Apariencia de la web

La aplicación web dispone de modo claro y modo oscuro en todas las pantallas, incluidos el acceso, el portal, las consultas, la agenda y sus paneles. La cabecera ofrece un botón que indica el modo al que se cambiará. La preferencia se conserva en el navegador, se aplica antes de mostrar el contenido y se comparte entre pestañas del mismo origen. Si no existe una elección guardada, se utiliza la preferencia del sistema y se siguen sus cambios. La elección no modifica datos ni permisos de la cuenta. Si el navegador impide guardar preferencias, el cambio sigue disponible en la página abierta.

Los colores se definen mediante variables semánticas comunes. La identidad violeta se utiliza en acciones, enlaces y selección; las superficies oscuras tienen un matiz violeta discreto y los textos mantienen contraste con sus fondos. No se invierte el color de imágenes ni se agregan bordes laterales a las tarjetas de actividades. Reservas y bloqueos se distinguen por fondo y etiqueta; la selección conserva ese fondo y utiliza un contorno violeta.

| Uso en modo oscuro | Color |
|---|---|
| Fondo general | `#121216` |
| Tarjetas y panel lateral | `#1C1C24` |
| Campos y superficies elevadas | `#252530` |
| Bordes y separadores | `#383845` |
| Texto principal | `#F2F0F7` |
| Texto secundario | `#B0ACBF` |
| Acción principal y selección | `#BE9AF2` |
| Hover de acción principal | `#CEB2FA` |
| Texto sobre acción principal | `#251334` |
| Realce violeta suave | `#2C213B` |
| Fondo de la cabecera | `#21182E` |
| Reservas: fondo / texto | `#233249` / `#D0E0FA` |
| Reservas: hover / marca de leyenda | `#2B3E59` / `#93B7E8` |
| Bloqueos: fondo / texto | `#382F25` / `#EBD2AE` |
| Bloqueos: hover / marca de leyenda | `#493B2D` / `#D7AC75` |

Los estados Programado utilizan violeta, los estados Activo y Finalizado conservan el acento verde, y los estados Inactivo y Anulado utilizan una paleta neutral. Los mensajes de error, advertencia e información tienen fondos atenuados y textos claros acordes con su intención. Los botones principales usan texto oscuro sobre violeta claro; los secundarios conservan el contorno y texto violeta. Los campos, selectores nativos, fechas, controles deshabilitados y focos se adaptan al tema activo.

El modo visual no cambia el tamaño ni la distribución funcional de las secciones. Los comprobantes se presentan con el tema activo en pantalla y utilizan fondo blanco y texto oscuro al imprimir o guardar como PDF mediante el navegador.


### 2.10 Bloqueos y acciones del día

#### 2.10.1 Bloqueos individuales

El Administrador podrá iniciar un bloqueo sobre un turno libre u ocupado por una reserva o clase Programada cuyo turno no haya comenzado. El motivo del bloqueo será clima adverso, torneo o mantenimiento. Su turno debe quedar íntegramente dentro de una franja de funcionamiento de la sede. La vista previa mostrará la actividad que deba anularse y el bloqueo que se creará. Primero se anula la actividad y se libera el turno; después se comprueba que esté libre y se registra un nuevo evento de bloqueo sobre ese mismo turno. Ambas acciones y su trazabilidad se guardan en una misma transacción. Anular una actividad por sí sola libera su turno y no crea un bloqueo.

Cada bloqueo ocupa un único turno y tiene estado y auditoría propios. Mientras esté vigente, impide registrar reservas, clases u otros bloqueos sobre ese turno. Liberarlo cambia su evento a Anulado, requiere un motivo y registra quién lo liberó y cuándo. Sólo se permite anular actividades y crear o liberar bloqueos antes del inicio del turno; los días pasados y los turnos iniciados quedan para consulta. Un bloqueo cuyo turno terminó conserva su estado registrado y se consulta como terminado por horario; no admite liberación ni finalización manual o automática. Los eventos de reserva o clase anulados para bloquear se conservan vinculados mediante `bloqueos.evento_origen_id`, opcional y único cuando está informado.

#### 2.10.2 Alcance de las acciones del día

Las operaciones administrativas masivas permiten anular y liberar eventos o anular y bloquear turnos de una fecha completa o desde una hora de corte inclusiva, sobre una o varias canchas seleccionadas de una sede. Para liberar se pueden excluir clases, reservas, bloqueos o cualquier combinación; para bloquear se pueden excluir clases o reservas, que conservan sus turnos ocupados. Bloquear incluye los turnos libres y conserva los bloqueos existentes, informados como ya cubiertos. Cada turno a bloquear origina su propio bloqueo, sin un evento agrupador ni un estado compartido.

En el día en curso sólo se incluyen turnos cuyo inicio sea posterior al momento de confirmar y sea igual o posterior al corte; a las 18:30 se puede operar desde las 19:00. A la hora exacta de inicio el turno ya se considera iniciado. Los turnos iniciados, los eventos Finalizados y los tipos excluidos se muestran como conservados y no impiden actuar sobre los demás. Los eventos Anulados se mantienen como historia y no se anulan nuevamente. Los cierres crean bloqueos únicamente sobre turnos contenidos en las franjas de funcionamiento. Las actividades existentes fuera de las franjas actuales se conservan y se informan; pueden anularse para liberar, pero no originar un bloqueo fuera de horario.

#### 2.10.3 Selección y revisión

La entrada Acciones del día está en la tarjeta del título de Agenda y abre el mismo panel lateral del detalle, conservando la grilla visible y la sede y fecha consultadas. La lista Canchas ofrece Todas las canchas de la sede o Seleccionar; esta última opción permite marcar una o varias canchas. Horario ofrece Día completo y los cortes Desde las HH:00 correspondientes a inicios habilitados aún futuros en la fecha consultada. Al elegir un inicio, Hasta permite indicar opcionalmente una hora de fin, entre las horas de finalización de turnos habilitados posteriores al inicio, incluida la hora de cierre; no ofrece horas dentro de las pausas. El límite de fin es exclusivo: de 08:00 a 10:00 comprende los turnos de 08:00 y 09:00. Sin fin indicado se incluye el resto del día. Primero se eligen canchas, alcance, exclusiones y motivos; después se revisan las cantidades y los listados desplegables de acciones y eventos sin cambios. Abrir, revisar, volver a editar y cerrar actualiza únicamente el panel y la selección, sin navegar a otra página ni desplazar la grilla. Seleccionar un turno reemplaza el contenido del panel por su detalle.

La vista previa diferencia las acciones, los eventos conservados y los bloqueos ya existentes.

#### 2.10.4 Confirmación

La confirmación efectiva utiliza un envío completo y actualiza la agenda. La confirmación queda vinculada al actor y a los datos revisados y vence a los quince minutos. Si cambia la ocupación, el alcance o la elegibilidad después de preparar la vista previa, se exige revisarla nuevamente. La confirmación aplica el lote completo con las garantías de 2.12.


### 2.11 Instalaciones

#### 2.11.1 Datos y horarios

Los nombres de sede son únicos sin distinguir mayúsculas y minúsculas. Los nombres de cancha tienen la misma condición dentro de su sede, pero pueden repetirse entre sedes. Los formularios informan los conflictos antes de guardar. Los horarios de funcionamiento y sus cambios respetan las reglas comunes del inicio de la sección 2.

#### 2.11.2 Activación y desactivación

Desactivar una sede comprende los eventos de todas sus canchas; desactivar una cancha comprende sólo sus eventos. La operación es administrativa y se rechaza si existe una reserva, clase o bloqueo no Anulado cuyo turno esté en curso. Un turno está en curso desde su inicio inclusive hasta su fin exclusivo.

Si no hay eventos en curso, se muestra una vista previa de todas las reservas, clases y bloqueos Programados con inicio futuro. Confirmar anula esos eventos y desactiva la instalación en una única transacción. Todos reciben el motivo común «Actividad anulada por desactivación de la sede» o «Actividad anulada por desactivación de la cancha», según el alcance. Cada evento conserva actor, momento, participantes, importes y relaciones históricas. Las reservas quedan anuladas administrativamente; no se registran bloqueos nuevos ni se modifican ingresos, devoluciones o contrataciones.

Los eventos Anulados y los turnos terminados no se anulan ni impiden desactivar. Las clases y reservas terminadas pendientes de finalización conservan su procesamiento normal. Los bloqueos terminados conservan su estado y ocupación histórica.

La operación coordina el bloqueo de sede, canchas, turnos y eventos con la creación, edición, anulación y finalización de actividades. Vuelve a validar acceso, ocupación y límites temporales al confirmar y antes de terminar. Si cambia el conjunto de eventos revisado o alguno de los turnos a anular alcanza su inicio, revierte toda la operación y exige revisar la vista previa. No permite una desactivación con anulaciones parciales.

Las solicitudes establecen un estado concreto; repetirlas no invierte la acción ni sobrescribe auditoría. Modificar los datos de una instalación no puede sobrescribir su estado. Reactivar no restaura eventos Anulados ni modifica el estado individual de las canchas de una sede.


### 2.12 Consistencia de las operaciones e historia

Las operaciones que escriben datos vuelven a comprobar acceso, estado y condiciones de negocio al confirmar, independientemente de las validaciones de la interfaz. Los cambios que forman una sola acción se guardan en una única transacción: un error revierte todos sus efectos. Si cambia la selección o una advertencia respecto de lo revisado, se solicita revisión antes de confirmar. Una operación repetida no duplica resultados ni sobrescribe auditoría.

La coordinación de escrituras concurrentes se aplica así:

- La asignación y el retiro de roles bloquean al usuario y se coordinan con la creación o reactivación de relaciones que condicionan esos cambios.
- La inactivación de usuarios bloquea a los administradores activos para impedir que dos solicitudes concurrentes dejen al sistema sin uno. Las condiciones de permiso y retiro se definen en 2.3.
- Las operaciones de clases, reservas e invitados y la generación o regeneración bloquean a los usuarios involucrados en orden de identificador antes de comprobar cupos y coincidencias.
- La configuración de tarifas y horarios, el cambio de estado de instalaciones y el registro de actividades se coordinan mediante la sede y sus canchas. Registrar o mover una actividad bloquea además los turnos involucrados y comprueba su ocupación compartida antes de escribir. Preparar un turno no crea un evento ni ocupa la cancha.
- Las operaciones con pase bloquean las contrataciones del organizador y de los invitados cuya cobertura se evalúa, en orden de identificador, antes de contar el consumo diario. La coordinación evita que dos reservas concurrentes utilicen las mismas horas disponibles sin verse entre sí.
- La contratación bloquea al usuario antes de comprobar la exclusividad del mes. La anulación bloquea la contratación antes de validar su estado.
- Registro, anulación de movimientos y cierre usan `transaction.atomic` y bloqueo de la sesión mediante `select_for_update`. La anulación de un movimiento histórico bloquea también su sesión de origen. La apertura utiliza el índice único parcial para resolver concurrencia. Los vínculos comerciales se validan por existencia y estado al confirmar. Las altas de reserva o contratación y sus cobros son operaciones separadas según 2.5.
- Anular o finalizar una actividad coordina el bloqueo de turno y evento con las demás operaciones sobre esa ocupación.

Las comprobaciones que dependen de varias filas se realizan en los servicios de escritura, dentro de esas transacciones. La base complementa esa coordinación con las claves y restricciones definidas en el modelo relacional.

La aplicación conserva la historia de usuarios, instalaciones, productos, contrataciones, actividades, sesiones de caja y movimientos. No utiliza la eliminación física de esos registros como una operación cotidiana. Las excepciones son quitar celdas de la planilla viva y eliminar clases generadas que siguen Programadas, mediante las operaciones de 2.1; se eliminan sus datos dependientes de forma coordinada y se conservan los turnos concretos.

### 2.13 Procesos automáticos de finalización y vencimiento

Celery Beat ejecuta la finalización de clases y reservas cada hora en punto de Buenos Aires. Selecciona eventos Programados cuyo turno terminó antes o en el momento de la ejecución. Para cada uno coordina turno y evento, vuelve a comprobar las condiciones y guarda Finalizado con el momento real de procesamiento. No modifica asistencias ni sobrescribe eventos Anulados o Finalizados. Los bloqueos quedan fuera de esta tarea.

La finalización automática de una clase no tiene responsable manual. Una finalización manual registra al administrador o profesor autorizado; las reservas no registran responsable de finalización, tampoco en la acción administrativa de emergencia. Cada ejecución recupera todas las clases y reservas pendientes, incluidas las que terminaron durante una interrupción de los servicios.

El vencimiento diario procesa las contrataciones Activas de planes y pases cuyo mes terminó, cambia su estado a Vencido y actualiza su fecha de modificación. No altera contrataciones Anuladas, ingresos ni relaciones históricas. Repetir la tarea no cambia los registros ya procesados. Los avisos de vencimiento y los recordatorios de clases se definen en 2.6.


### 2.14 Historial de auditoría

`log_auditoria` conserva las modificaciones funcionales y anulaciones de registros de negocio. También registra las eliminaciones permitidas de relaciones, como retirar un rol o quitar un horario, porque modifican la configuración existente. El alcance del hito comprende modificaciones y anulaciones; las altas no generan entradas. La captura se realiza en PostgreSQL mediante una función común y un trigger de fila `AFTER UPDATE OR DELETE` en cada tabla auditada. Las sesiones técnicas de autenticación, permisos técnicos y migraciones de preparación quedan fuera del historial de negocio. `sesiones_caja` y `movimientos_fondos` sí participan: los cierres y anulaciones se auditan con el mecanismo común, sin agregar auditoría de altas. La auditoría registra los cambios de caja; la protección de datos de caja se valida en los servicios según 2.5.

Cada entrada identifica tabla, clave simple o compuesta en JSON, acción, valores anteriores y actuales, fecha y hora con zona horaria, usuario de la aplicación cuando corresponde, cuenta de PostgreSQL y origen. En modificaciones y anulaciones sólo se guardan los campos que cambiaron. En las eliminaciones permitidas se conserva el registro anterior y un objeto vacío como valor actual. Las instantáneas usan JSON nativo de PostgreSQL; fechas y horas conservan su representación ISO y los importes se representan como números. La marca `actualizado_en` aislada no genera una modificación funcional. Las consultas, vistas previas y preparación de nuevos turnos no generan entradas por sí mismas.

El trigger obtiene los valores directamente de `OLD` y `NEW`. Reconoce como anulación la transición de un estado a Anulado y el registro del origen de anulación en una reserva. Las contraseñas y sus hashes se excluyen de las instantáneas. Cambio de contraseña y Restablecimiento de contraseña son acciones específicas: Django comunica la intención de la operación y el trigger verifica que el valor almacenado cambió. La cuenta afectada se identifica por la clave del registro y el responsable por el usuario del log. Sólo se conservan diferencias de campos reales no sensibles, como `debe_cambiar_contrasena`; la marca temporal auxiliar se omite en estos eventos. Si no cambió otro campo relevante, los valores anteriores y actuales son objetos vacíos. No se generan indicadores artificiales ni valores enmascarados de la contraseña. El guardado de la contraseña y de su obligación de cambio forma una sola actualización y produce una entrada. La actualización automática del hash al verificar credenciales se registra como Actualización de hash, sin confundirla con la elección de una contraseña nueva. El contexto de verificación identifica esta operación técnica; un cambio o restablecimiento confirmado utiliza su propia intención. Una modificación de la credencial por SQL sin una intención informada se registra como Cambio de contraseña, sin atribuirle un restablecimiento administrativo. Una intención sin cambio efectivo no genera un evento de contraseña. La fecha del último acceso se audita cuando cambia `last_login`.

Django comunica actor, origen, identificador UUID y, cuando corresponde, la acción específica mediante configuración local a la transacción, obtenidos del servidor y no de campos editables. El middleware establece el contexto de las solicitudes; la autenticación y la finalización resuelven sus actores específicos. La función de contexto sólo comunica esos datos y delimita la transacción: no captura ni inserta entradas. Los contextos anidados comparten el UUID y restauran el contexto superior al terminar. La configuración no se reutiliza para otra solicitud. Las respuestas de error HTTP revierten la transacción de la solicitud.

Los orígenes admitidos son `aplicacion`, `tarea` y `sql`. Las modificaciones desde la aplicación exigen un usuario. Durante la autenticación se comunica ese propósito al trigger, que identifica al titular desde la cuenta que se está guardando. La finalización automática utiliza origen `tarea` sin usuario; la acción de emergencia identifica al administrador en el log, sin agregar un responsable de finalización al evento. El autorregistro, las altas administrativas y el comando de creación de administradores no requieren un contexto especial de auditoría porque sus inserciones no se registran.

Una escritura SQL sin contexto se registra con origen `sql`, sin usuario web y con `session_user` como cuenta de base de datos. Las escrituras de una misma transacción SQL comparten un UUID generado por la base. Los triggers cubren también operaciones masivas y escrituras directas `UPDATE` y `DELETE`. Cada nueva tabla de negocio incorpora su trigger mediante una migración, declarando los componentes de su clave primaria. El contexto comunicado por la aplicación pertenece a la conexión confiable del servidor; no constituye una autenticación independiente del usuario dentro de PostgreSQL.

Las entradas forman parte de la misma transacción que la escritura auditada. Un error al insertar el log impide confirmar el cambio; un rollback elimina también sus entradas. Anular y bloquear y las operaciones masivas conservan un UUID común para sus modificaciones y anulaciones, sin agrupar los estados de los eventos. No se audita el propio log ni se infieren acciones históricas a partir de los datos existentes.

Los campos de creación, modificación, responsables, fecha de baja, motivos y fechas de anulación o finalización se conservan en sus entidades. Describen el registro vigente, sostienen las restricciones de coherencia y permiten consultas y comprobantes directos. El log conserva la secuencia de cambios y no reemplaza esos campos.

El historial es inmutable: un trigger rechaza `UPDATE`, `DELETE` y `TRUNCATE` sobre `log_auditoria`. La web no permite escribir en él. Auditoría es exclusiva de administradores activos con acceso vigente, sólo admite GET y presenta cambios sin entradas de alta. Muestra veinticinco entradas por página en filas compactas, en orden descendente de fecha e identificador. Cada fila reúne fecha, usuario, acción, tabla y clave; al desplegarla presenta origen, usuario de aplicación, usuario de PostgreSQL, UUID y valores anteriores y actuales. Los eventos de cambio y restablecimiento de contraseña ocultan los bloques de valores anteriores y actuales, aunque el historial conserva las diferencias no sensibles. El resumen identifica al usuario de aplicación, a un Proceso automático cuando el origen es una tarea o al usuario de PostgreSQL cuando la escritura proviene de SQL. El detalle muestra Usuario de aplicación únicamente para el origen Aplicación. La cuenta de PostgreSQL identifica la conexión, sin atribuirle una identidad humana. Los datos se muestran escapados y consultar no modifica el historial.
