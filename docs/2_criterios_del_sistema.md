# Criterios del sistema

## 1. Propósito

Este documento resume los criterios generales del sistema a desarrollar para la Academia de Tenis TM, tomando como base el funcionamiento actual de la organización (ver `1_organizacion.md`).

El objetivo es definir qué hace el sistema y cómo resuelve cada operación: alcance, permisos, validaciones, interacción, auditoría y procesos automáticos. La representación de esos criterios mediante tablas, atributos, claves y restricciones se describe en `3_modelo_relacional.md`. Los puntos abiertos de definición se reúnen en [Pendientes de definición documental](pendientes_documentacion.md).

---

## 2. Alcance del sistema

El sistema será una única aplicación, con un solo backend y un único modelo de usuarios y roles, expuesta mediante dos interfaces separadas: la gestión interna para el personal (Administrador) y el portal público de autoservicio (Profesores,Público, Alumno, Reservas; ver 2.7). No son sistemas independientes: se separan por audiencia e interfaz, no por datos ni reglas de negocio.

La ocupación se organiza mediante turnos de una hora, con inicio en punto entre 00:00 y 22:00 inclusive y fin dentro de la misma fecha. Cada turno identifica una cancha, fecha y hora; esas coordenadas no se editan. Una reserva, clase o bloqueo ocupa un único turno y conserva estado, observaciones y auditoría de su actividad.

Una actividad Programada ocupa su turno, Anulada lo libera y Finalizada conserva su ocupación histórica. Un turno puede conservar varias actividades Anuladas, pero sólo una no Anulada. La existencia de un turno no significa que esté ocupado.

Las únicas transiciones son Programado a Anulado y Programado a Finalizado. Repetir una operación no sobrescribe su auditoría. Finalizar exige que el turno haya terminado; los bloqueos se finalizan automáticamente según 2.10. Las modificaciones de los datos específicos de una actividad actualizan también su fecha de última modificación.

Las clases y reservas previamente agendadas deberán respetarse. El sistema impedirá que dos eventos no Anulados ocupen el mismo turno. Ninguna actividad podrá desplazar automáticamente a otra. Las operaciones coordinan la ocupación según 2.12.

Cada sede tendrá su propio horario de funcionamiento, definido por día de la semana y con hasta dos franjas horarias por día (por ejemplo, de 8 a 12 y de 16 a 22). El inicio y el fin de cada franja deberán ser en punto y, si se configuran dos franjas, deberá haber al menos una hora sin funcionamiento entre ellas. Un día sin franjas configuradas significa que esa sede no funciona ese día. Toda reserva, clase o bloqueo debe quedar contenido íntegramente en una única franja habilitada. Esta condición rige para el portal, la administración, la planilla, la generación de clases y las operaciones masivas, sin excepciones confirmables. Un día sin franjas no admite nuevas actividades. Configurar o quitar franjas se rechaza si deja fuera una reserva, clase o bloqueo Programado cuyo turno aún no terminó. Los registros Anulados, Finalizados o con turno terminado se conservan como historia y no impiden actualizar el horario.

Todo motivo ingresado como texto libre requiere al menos cinco caracteres, sin contar espacios al principio y al final. La regla se aplica en formularios y servidor a anulaciones individuales y masivas, correcciones, ajustes y reversiones de horas, y justificaciones de diferencias de caja. Los motivos clasificados de bloqueo se seleccionan del catálogo y no requieren texto libre adicional.

### 2.0 Límites temporales y calendario operativo

La historia operativa administrada por el sistema comienza el **1 de agosto de 2026**. Ninguna clase, reserva, bloqueo, contratación de plan o membresía, fecha de alta, feriado ni ingreso puede registrarse antes de esa fecha. Esta fecha mínima es absoluta para la consulta y las correcciones históricas permitidas. La creación de eventos exige además un inicio estrictamente futuro.

Ningún evento de reserva, clase o bloqueo puede crearse si la fecha y hora de inicio de su turno es igual o anterior al momento actual del servidor, en la zona horaria del sistema. La regla incluye los turnos de hoy que ya comenzaron, la creación administrativa, las operaciones masivas y la generación desde planilla, sin excepciones. Todo evento nuevo, sin importar el método de creación, debe comenzar como máximo el último día del segundo mes calendario posterior al actual. En noviembre se admiten altas hasta el 31 de enero, inclusive; el cálculo contempla el cambio de año. Las reservas mantienen además su límite de tres días calendario siguientes inclusive. La agenda permite consultar desde el inicio de operaciones hasta un año calendario después de hoy y conserva el acceso a las actividades existentes. La anulación de reservas, clases o bloqueos exige que su turno no haya comenzado. Una reserva nueva debe comenzar en un horario futuro y su fecha debe estar entre hoy y tres días después, inclusive; no hay excepciones administrativas. Las consultas conservan el acceso a la historia.

La generación de clases permite elegir un mes calendario completo mediante un desplegable con etiquetas como «Noviembre de 2026», que sólo incluye los meses completos permitidos por el calendario operativo, con el mes actual seleccionado por defecto. El período seleccionado puede incluir días pasados: se omiten e informan todas las candidatas cuyo turno ya comenzó, incluidos los turnos de hoy. El servidor admite períodos dentro del calendario operativo y de **hasta 62 días corridos inclusive** por ejecución; la pantalla utiliza el primer y último día del mes elegido. El selector sólo ofrece el mes actual y los dos meses calendario siguientes. El mes completo debe quedar dentro del límite de creación de eventos. Si un turno revisado alcanza su inicio antes de terminar la confirmación, la operación se revierte y exige una nueva revisión. Las consultas de actividad de clases y uso de membresías aceptan rangos de **hasta 366 días corridos inclusive**. Un período mayor se consulta por tramos.

Administración registra contrataciones de planes y membresías desde agosto de 2026 hasta el mes calendario siguiente al actual; ese mes siguiente se habilita sólo desde el día 25 inclusive. El portal consulta contratos y responde continuidad, sin registrar altas ni renovaciones. Las contrataciones guardan el mes cubierto como una fecha del primer día; inicio y fin se calculan y siempre cubren meses completos. Una contratación histórica cuyo mes terminó nace Vencida. Una contratación de un mes futuro puede estar Activa, pero su cobertura corresponde a ese mes. La fecha efectiva de alta es independiente del mes cubierto y debe estar entre el inicio de operaciones y la fecha local actual, inclusive, en el alta administrativa.

Los movimientos de caja utilizan únicamente `creado_en`, asignado por el servidor al registrar. No se carga una fecha real histórica ni una fecha futura. Cada movimiento pertenece a la sesión abierta al momento de su registro; apertura, anulación y cierre también utilizan el momento del servidor.

Los feriados pueden registrarse desde el inicio de operaciones hasta cinco años calendario después de la fecha local actual. Registrar o quitar un feriado pasado no modifica retroactivamente las clases que ya fueron generadas.

La fecha de nacimiento es obligatoria y debe estar comprendida entre la fecha local actual menos 120 años y la fecha local actual. No se establece una edad mínima para ser usuario.

Todos estos límites se validan en el servidor y se exponen además en los controles HTML como ayuda de carga. Las comparaciones con el día o momento actual usan la zona `America/Argentina/Salta`. Los servicios que escriben datos vuelven a validar las reglas aunque la interfaz ya lo haya hecho, para que no puedan evitarse manipulando formularios o URLs.

### 2.1 Gestión de clases

El sistema incluirá la gestión de clases de la academia.

Cada clase y cada horario de planilla registran ubicación, horario, profesores, participantes y observaciones. Crear o editar un horario de planilla exige al menos un profesor activo con rol Profesor; no se permite guardar una selección sin profesores. La modalidad individual o grupal es una característica comercial de los planes.

La referencia organizacional para las clases grupales es de seis alumnos. Al superar esa cantidad se informa mediante un aviso, sin bloquear asignaciones, guardado ni generación de clases y sin exigir autorización adicional. El sistema no impone un cupo obligatorio de seis alumnos.

La gestión incluirá:

- Armado y edición continua de la planilla semanal (semana tipo) por sede: una única planilla viva por sede, sin conservar versiones históricas por período. Cada celda define, para un día y horario, los alumnos asignados.
- Generación de clases concretas para un período seleccionado, a partir del estado actual de la planilla en ese momento.
- Anulación de clases generadas por error, desde su detalle o mediante Acciones del día o del mes, antes del inicio del turno y conservando su historia.
- Consulta diaria de clases existentes en Agenda.
- Creación, edición y cancelación de clases individuales, generadas por la planilla o creadas manualmente.
- Asignación de profesores y alumnos.
- Finalización individual de clases por la administración o por alguno de sus profesores asignados.
- Registro y corrección de asistencia de clases Finalizadas.

Las clases generadas existirán como instancias individuales, con su origen identificado para distinguirlas de las creadas manualmente. No se conservará una referencia a la celda de planilla: la clase concreta ya contiene por sí sola todo lo necesario para la historia operativa (día, horario, cancha, alumnos, profesor).

En la grilla de Agenda y en la lista de anulaciones de cada turno, las clases visibles para el usuario muestran el primer profesor activo y, si hay más, la cantidad restante como `+N`. Los profesores se ordenan por identificador para mantener el mismo resumen en ambas consultas. El panel lateral presenta el primer profesor activo y la cantidad restante como texto fijo en Profesores activos cuando el usuario tiene permiso para consultar el grupo. La lista completa se consulta en el detalle de la clase.

No existirá una reprogramación de clases como operación propia: una clase Programada puede cambiar de cancha únicamente antes del inicio de su turno, pero nunca cambiar de día ni de horario. Si hace falta mover una clase a otro día u horario, se anula y se crea una nueva, sin ninguna vinculación entre ambas. Las reservas también se crean de manera independiente según 2.2.

Cambiar de cancha conserva fecha y hora, libera la ubicación original y exige disponibilidad y funcionamiento en el destino. Las clases Anuladas o Finalizadas conservan sus datos y asignaciones; el registro y corrección de asistencia de una clase Finalizada sigue las condiciones de esta sección.

Las clases y la planilla distinguen profesores que dictan la clase y participantes que asisten. Cada clase debe conservar al menos un profesor asignado. Asignar a un profesor exige una cuenta activa con rol Profesor; la creación o edición valida esas condiciones antes de guardar. Para los participantes, la selección muestra usuarios con rol Alumno por defecto y permite ampliar la búsqueda a cualquier usuario activo, incluidos profesores que asisten a una capacitación. Participar no exige ni otorga Alumno, no exige contratar un plan y no genera cargos: se admiten alumnos de prueba y participaciones acordadas fuera del sistema. Los planes conservan su alcance comercial definido en 2.4.

La disponibilidad personal se comprueba conjuntamente entre docencia, participación en clases y reservas según 2.2. Toda asignación de profesor o participante en Asistirá impide otra actividad simultánea, independientemente de sede o cancha. La participación No asistirá no ocupa disponibilidad personal. Una persona no puede estar asignada a la misma clase en ambas funciones. Las clases Anuladas no impiden otra actividad. Crear o editar revalida estas condiciones.

Las altas de asignaciones y la generación comprueban la disponibilidad personal definida en 2.2 y rechazan coincidencias con reservas. Asistirá ocupa disponibilidad personal; No asistirá la libera. La asignación docente vigente siempre impide coincidencias y no requiere respuesta.

Generar las clases de un período es una acción irreversible desde el sistema: no existe una operación de deshacer. Antes de ejecutarla, el sistema mostrará al menos dos confirmaciones explícitas advirtiendo que el proceso no puede deshacerse. Las clases manuales y generadas no admiten eliminación física. Las creadas por error pueden anularse antes del inicio del turno desde su detalle o mediante Acciones del día o del mes, conservando sus eventos, asignaciones y auditoría.

Modificar la planilla afecta las próximas clases que se generen. Volver a generar un mes conserva todas las clases existentes y omite los turnos ocupados; sólo crea clases en turnos futuros disponibles. Las clases concretas se modifican mediante sus acciones individuales. Eliminar una celda de planilla no elimina las clases concretas que originó ni modifica sus asignaciones o su indicador de origen.

La generación omite la clase candidata completa si el turno está ocupado o si cualquiera de sus profesores o participantes carece de disponibilidad personal para esa fecha y hora según 2.2. No elimina participantes para generar una clase parcial ni aborta las demás candidatas por ese conflicto. También compara las candidatas de la misma ejecución, en un orden estable por fecha, hora e identificadores de sede y cancha: la primera candidata válida se conserva y las posteriores en conflicto se omiten. También se omiten e informan las candidatas sobre instalaciones inactivas o cuyos usuarios previstos no cumplen las condiciones de asignación. La vista previa identifica cada clase omitida y el motivo. Antes de guardar se vuelve a validar el conjunto revisado; si cambia, se exige revisar la vista previa. Las coincidencias con reservas que impiden disponibilidad personal también omiten la candidata completa y se informan en la revisión.

La asignación a una clase concreta comienza en Asistirá (`asistira`) y ocupa disponibilidad personal. El titular habilitado puede indicar No asisto antes del inicio de una clase Programada y con asignación vigente. Se guarda No asistirá (`no_asistira`) y se libera disponibilidad personal. El aviso es irreversible y conserva asignación, plantilla e historia de auditoría, con titular y momento. Retirar elimina el vínculo; agregar nuevamente crea una participación con respuesta inicial Asistirá e identidad nueva. El formulario de respuesta comprueba esa identidad para rechazar una participación sustituida. Administración no lo revierte ni responde por el titular. Si finalmente asiste, se registra Presente en la asistencia real sin modificar el aviso ni volver a ocupar disponibilidad. Los profesores no tienen acciones de respuesta por docencia.

La retirada de profesores y participantes elimina la relación y conserva al menos un profesor. Sólo se admite antes del inicio de una clase Programada, con revalidación del horario al guardar. Se bloquean las personas, instalaciones, turnos y evento según el orden común. El aviso captura destinatario, función, fecha, horario y ubicación antes del borrado y se guarda en la misma transacción. Las asistencias no dependen del vínculo y no se borran. La auditoría de eliminación conserva quién fue quitado y quién realizó la operación. Una relación nueva tiene un UUID de participación distinto, aunque coincidan persona, clase y fecha de creación; sus avisos no reutilizan las claves de la relación retirada. Cambios de planilla no notifican retiradas ni alteran clases generadas.

Registrar o corregir asistencia efectiva exige que el evento de la clase esté Finalizado. La finalización manual puede realizarse junto con la carga de asistencia en una misma operación. La finalización automática sólo cierra el evento por horario y no marca presentes ni ausentes.

Se admite registrar asistencia de usuarios no asignados previamente. El estado Sin registrar distingue la falta de carga de una ausencia efectiva; cada presente o ausente conserva responsable y momento de registro, junto con las modificaciones posteriores.

La creación individual, el cambio de cancha y la generación de clases exigen que cada turno quede íntegramente dentro de una franja de funcionamiento de la sede. Las fechas fuera de horario se omiten y se informan en la vista previa de generación; la creación individual y el cambio de cancha se rechazan. No existe confirmación administrativa que permita una excepción.

Anular una clase es una operación exclusiva del administrador y exige que su turno no haya comenzado. Exige un motivo en texto libre, conserva la historia de la clase y libera el turno que ocupaba. No crea un bloqueo.

Los feriados rigen para todas las sedes y se omiten al generar clases desde la planilla. Se permite crear una clase manual en un feriado, respetando las demás reglas de funcionamiento y disponibilidad. Al registrar un feriado con fecha posterior a hoy, se muestra una vista previa de todas las clases Programadas de esa fecha y, al confirmar, se anulan con el motivo común «Clase anulada por registro de feriado». La anulación incluye las clases manuales existentes, conserva sus participantes y auditoría y libera sus turnos; no crea bloqueos ni modifica reservas. El registro del feriado y las anulaciones se confirman en una única transacción, coordinada con la generación y creación de clases. Una clase manual creada después del registro del feriado es una excepción explícita y permanece programada. Registrar un feriado de hoy o pasado no anula clases existentes. Quitar un feriado no reactiva clases Anuladas.

### 2.2 Gestión de reservas

Administración consulta, crea y cancela reservas de organizadores existentes. Cada organizador está activo y tiene rol Reservas o Administrador; reservar no crea usuarios ni asigna roles. Desde el portal, el organizador es la cuenta autenticada. El organizador conserva la responsabilidad de gestionar su propia reserva.

Cada reserva ocupa un turno de una hora con inicio futuro entre hoy y el tercer día calendario siguiente inclusive. El último día se admite completo dentro de las franjas de la sede. No hay excepciones administrativas ni reservas recurrentes.

Cada persona puede organizar como máximo dos reservas cuyo evento siga Programado, sumando ambas modalidades en todas las sedes y canchas. Las invitaciones no cuentan para este límite ni se comprueba ese máximo al agregar invitados o responder invitaciones. La disponibilidad personal y los cupos de horas de organizador e invitado se controlan por separado. El límite depende del estado almacenado, incluso si el turno terminó y la tarea aún no finalizó el evento. Las reservas Anuladas y Finalizadas no cuentan.

La disponibilidad personal se valida recíprocamente entre reservas y clases no Anuladas: organizar, tener una invitación Aceptada, participar en una clase con asignación en Asistirá, o dictarla con asignación impide otra actividad simultánea. Rechazar una invitación de reserva libera disponibilidad; el aviso de no asistencia de clase también libera disponibilidad. Estas reglas también se aplican a altas y generación desde planilla, sin excepciones confirmables.

#### Modalidades y creación

Desde un turno libre de Agenda, el portal ofrece Reserva normal y Reserva con membresía si el titular es socio para esa fecha; si no lo es, sólo Reserva normal. Administración elige Nueva reserva, selecciona organizador y pulsa Continuar antes de recibir esas opciones. Cada modalidad conserva turno y organizador. Tener membresía no obliga a utilizarla.

La reserva normal exige tarifa positiva de sede y conserva su importe. Registrar invitados es opcional y no altera la tarifa; no consulta ni aplica membresías, horas o adicionales de invitados. Con membresía se exige contratación Activa con cobertura y horas de organizador disponibles para el turno, se compromete una hora de organizador y se conserva el adicional unitario del producto. Los cobros se registran por separado.

Los invitados son cuentas activas con rol Reservas o Administrador, sin duplicados ni repetición del organizador. Cada invitación comienza Pendiente, sin ocupar disponibilidad ni aplicar condición comercial, comprometer horas o generar adicional. Invitar no comprueba disponibilidad personal del invitado: el titular la compromete al aceptar. La creación revalida permisos, elegibilidad, calendario, instalaciones, ocupación, límite y disponibilidad del organizador, cobertura e importes bajo bloqueos coordinados. Registra evento, reserva e invitaciones juntos.

La cantidad confirmada incluye organizador y participaciones aceptadas. En membresía el total deriva del adicional unitario por las participaciones computables sin beneficio. No existe una cantidad total declarada. La condición aplicada a turnos comenzados se conserva sin recalcular importes ni usos históricos.

#### Invitados y respuestas

Sólo el titular puede responder antes del inicio de una reserva Programada. Pendiente permite Aceptar o Rechazar; Aceptada permite Rechazar; Rechazada permite Aceptar. No se vuelve a Pendiente después de decidir y no existe límite de cambios. Al inicio se conserva la respuesta y se ocultan las acciones. Repetir la decisión no modifica datos ni auditoría.

Aceptar siempre exige disponibilidad personal, con independencia de tener horas o participar con adicional. Una coincidencia rechaza la operación sin cambiar estado, saldo o importe. En normal no aplica lógica de membresía. Con membresía cada aceptación evalúa cobertura y horas de invitado para la fecha: con beneficio compromete una hora; sin cobertura o con cupo agotado aplica el mismo adicional unitario de la reserva, conservando el motivo comercial. Se informa la condición antes de confirmar y se revalida bajo bloqueos; si cambia el beneficio o el importe se exige otra revisión. Las respuestas conservan titular y momento de la última decisión y toda la historia en auditoría.

Rechazar libera disponibilidad y la hora comprometida o quita el adicional. No modifica la hora del organizador, cancela la reserva ni devuelve dinero automáticamente. Una nueva aceptación revalida las condiciones y no garantiza recuperar un beneficio liberado.

El organizador o administración puede agregar o quitar invitados antes del inicio. Quitar elimina la invitación en cualquiera de sus tres estados y libera sus compromisos; sólo queda la historia en auditoría. No existe estado Retirada ni reincorporación. Volver a invitar crea una relación Pendiente y requiere nueva aceptación. Las solicitudes identifican la invitación concreta y su versión; una respuesta antigua no actúa sobre una invitación creada nuevamente. Editar otros invitados conserva respuestas y condiciones de quienes permanecen.

#### Compromiso y actualización de socios

Sólo las Aceptadas con beneficio comprometen horas de invitado y las consumen al inicio, aunque finalmente no asistan. Pendientes y Rechazadas no comprometen ni consumen horas ni generan adicional. Toda cancelación libera los compromisos de invitados, sin penalización por proximidad al inicio. Las condiciones comerciales efectivamente aplicadas a turnos comenzados se conservan y no se recalculan.

Actualizar socios actúa sólo sobre invitaciones Aceptadas con adicional, antes del inicio. Con cobertura y horas de invitado disponibles aplica el beneficio, compromete una hora y elimina el adicional. Sin saldo mantiene el cargo. La revisión y confirmación conservan el precio unitario, las respuestas y los cobros, sin aceptar por el titular ni modificar las otras participaciones. Los cambios comerciales quedan en auditoría.

#### Cancelación y consumo

El organizador cancela su propia reserva antes del inicio con motivo libre de al menos 5 caracteres sin espacios extremos. Con membresía, más de dos horas de antelación libera la hora; con dos horas o menos conserva el consumo. El reloj del servidor determina el plazo al confirmar, con precisión completa.

Administración cancela por causas de la academia, con motivo, y siempre libera la hora de organizador y las horas comprometidas de invitados. Esto rige también al bloquear, desactivar instalaciones y anular por día o mes. Los pedidos del organizador se resuelven por su recorrido propio. Ninguna cancelación afecta un turno iniciado. Toda cancelación libera cancha y cupo Programado, aunque una cancelación propia conserve consumo. Las reservas normales no tienen penalización por cancelación tardía ni resultado No realizada.

Una reserva con membresía Programada compromete una hora; Finalizada consume una hora. Una Anulada sólo computa si la canceló el organizador con dos horas o menos. La disponibilidad mensual por rol se deriva del cupo aplicado más ajustes netos menos compromisos y consumos del mismo titular y mes, incluidas contrataciones Anuladas. No hay saldo mutable ni arrastre entre meses.

#### Nueva reserva y resultado

Una reserva Anulada permanece Anulada, sin restauración ni vínculo a otra reserva. Para otro turno, o el mismo si está disponible, se utiliza el alta habitual. Se validan organizador, invitados explícitos, cupos, disponibilidad, cobertura, precios y ventana de tres días con último día completo. Las invitaciones comienzan Pendientes; no se copian participantes ni respuestas. Cada reserva conserva sus movimientos y el tratamiento de horas de su cancelación, sin transferencias ni compensaciones.

La tarea horaria finaliza eventos terminados; administración dispone de finalización manual alternativa sin depender de Celery ni Redis. Ninguna presume realización, asistencia ni pago. Después de Finalizado, administración registra Realizada o No realizada; antes se presenta Sin registrar. Se admite una sola corrección, con resultado distinto y motivo obligatorio, sin plazo límite. Se conservan resultado original, responsables y momentos de carga y corrección. No realizada y su corrección conservan el consumo y los invitados.

Cada reserva dispone de comprobante autorizado para administración y organizador, con sus importes aplicados; no acredita pago. El invitado consulta su participación y responde sin acceder a cobros, comprobantes ni datos financieros ajenos. Se muestran importe acordado, ingresos Vigentes, devoluciones Vigentes y neto recibido según 2.5.6. Cancelar, retirar, rechazar o actualizar socios no modifica cobros ni genera devoluciones. Si corresponde devolver dinero, se registra un Egreso independiente de categoría devoluciones. Una reserva Anulada no recibe nuevos ingresos.

Quitar invitados de una reserva Programada antes del inicio elimina la relación y guarda un aviso por invitado retirado en la misma transacción. La retirada no depende de la respuesta previa. Una nueva invitación empieza Pendiente, con identidad nueva; no recupera una respuesta Rechazada ni admite el formulario de una invitación sustituida. El aviso de retirada puede entregarse después del horario de la actividad y no requiere que el vínculo siga existiendo.

### 2.3 Usuarios y roles

El sistema no distinguirá entre clientes y usuarios del sistema: toda persona que interactúa con el sistema, incluidas las que hoy se gestionan como clientes, es un **usuario**. Lo que cada usuario puede hacer lo determinan los roles que tiene asignados, no una categoría separada de "cliente".

El alta exige nombre, apellido, correo, celular y fecha de nacimiento. Nombre y apellido admiten hasta 100 caracteres y no contienen números. El celular se valida como móvil argentino, puede pertenecer a un tercero y no debe ser único. Correo y nombre de usuario son únicos sin distinguir mayúsculas y minúsculas; los formularios comprueban la disponibilidad antes de guardar.

En el alta administrativa y el autorregistro, el nombre de usuario se genera con el apellido normalizado y la inicial del nombre. Si ya existe, se agrega un sufijo numérico desde 1. Se muestra sin permitir su edición y se confirma al guardar.

Los roles forman un catálogo fijo: no se crean, renombran ni eliminan desde la aplicación.

Los roles serán:

- **Administrador**: acceso total al sistema. Es un rol exclusivo: una cuenta administrativa sólo tiene esta asignación en `usuarios_roles`, sin Público, Reservas, Profesor ni Alumno. La marca técnica `is_superuser` permite que Django le conceda todos los permisos. Se crea con el comando `crear_administrador` ejecutado por el desarrollador y opera desde la interfaz de Academia TM. Ningún administrador puede asignar ni quitar este rol desde la aplicación.
- **Profesor**: gestiona las clases en las que está asignado para dictar y consulta las clases a las que asiste como participante. Lo asigna un administrador mediante la gestión de roles a una cuenta activa con correo verificado. Sólo puede quitarse si el usuario no tiene clases Programadas como profesor. Participar en una capacitación no concede acciones de docencia sobre ella.
- **Público**: permite consultar el perfil propio y la oferta activa de sedes, ubicación, canchas, precios de reserva, planes y membresías. Corresponde a una cuenta autenticada y permite esa lectura sin correo verificado. No concede escritura ni acceso a información ajena o de Caja. Es el único rol inicial de una cuenta no administrativa y no puede quitarse desde la aplicación.
- **Reservas**: permite crear, cancelar y consultar reservas propias. Toda cuenta no administrativa lo recibe al completar la verificación inicial de su correo, sin duplicarlo ni restituirlo si fue retirado después. Un administrador puede quitarlo únicamente si el usuario no tiene reservas programadas. El catálogo y el perfil corresponden al rol Público.
- **Alumno**: permite consultar sus clases asignadas y su historial de asistencia. Una cuenta no administrativa lo obtiene al registrar una contratación Activa de plan si no lo tiene, por el recorrido propio o administrativo autorizado; no exige que se haya registrado un ingreso. Una membresía no otorga este rol. También puede asignarlo un administrador mediante la gestión de roles después de verificar el correo. No se retira automáticamente al vencer una contratación; sólo un administrador puede quitarlo respetando las condiciones del retiro.

El alta de una cuenta no administrativa, por autorregistro o por la administración, guarda únicamente Público y el correo sin verificar. La bienvenida con enlace se persiste en la misma transacción; al verificar se asigna Reservas, sin Alumno ni Profesor. La operación se confirma completa o se revierte según 2.12. Las asignaciones administrativas y automáticas respetan la exclusividad del rol Administrador. Profesor y Alumno son incompatibles entre sí: la misma cuenta no puede tener ambos. Para cambiar de rol se retira primero el anterior, respetando sus condiciones de retiro. Asistir como participante a una clase o capacitación no requiere cambiar de rol.

La edición de una cuenta se limita a estas operaciones:

| Operación | Quién puede realizarla |
|---|---|
| Consultar el perfil propio | El usuario autenticado. |
| Cambiar la contraseña propia | El titular de la cuenta, incluido un administrador. |
| Modificar el correo | Administración; el titular puede corregir el correo inicial sin verificar con su contraseña. |
| Recuperar una contraseña | El titular de una cuenta activa con correo verificado. |

El nombre, apellido, nombre de usuario, celular, fecha de nacimiento y observaciones se registran durante el alta y no se editan desde la aplicación. El estado de la cuenta y las asignaciones de roles se administran mediante sus operaciones específicas; no forman parte de la edición del perfil. El titular puede corregir su correo inicial sin verificar mediante contraseña vigente; una cuenta ya verificada utiliza el recorrido de cambio de correo administrado. No puede cambiar la contraseña de otra persona. La modificación del correo y el cambio de contraseña actualizan automáticamente la fecha de última modificación.

Las cuentas creadas por otra persona reciben una contraseña provisoria y quedan marcadas con `debe_cambiar_contrasena = true`. Esta regla comprende tanto el alta desde la aplicación como la creación de un administrador mediante `crear_administrador`. La persona puede autenticarse con esas credenciales, pero debe verificar primero el correo; puede consultar su estado, corregirlo, reenviar la verificación, recuperar la contraseña y cerrar sesión. Después de verificar debe establecer una contraseña propia para operar. El cambio correcto y la recuperación mediante el enlace enviado por email guardan el nuevo hash y desactivan la marca en la misma transacción.

El autorregistro no activa esa obligación: la persona elige y confirma su propia contraseña durante el alta. Tanto el cambio voluntario como el obligatorio exigen la contraseña vigente, la nueva contraseña y su confirmación. La nueva debe superar los validadores de Django y ser diferente de la vigente. Una validación fallida conserva el hash y la obligación pendiente; cerrar sesión tampoco desactiva esa obligación. Al cambiar la contraseña se conserva la sesión actual y las demás sesiones dejan de ser válidas al volver a utilizarse.

Las contraseñas provisorias del alta se muestran una sola vez y no pueden consultarse después. La recuperación utiliza el enlace enviado por email mediante el mecanismo nativo de Django, con vigencia de quince minutos desde su primera emisión (`PASSWORD_RESET_TIMEOUT = 900`). Al completar la recuperación, el enlace utilizado y los anteriores quedan invalidados por el cambio de contraseña. Cambiar el correo o registrar un nuevo inicio de sesión también puede invalidarlos. Solicitar otro enlace no cambia la cuenta ni invalida por sí solo los enlaces anteriores.

El cambio administrado del correo de una cuenta verificada guarda `email_pendiente` y `cambio_email_solicitado_en`. El correo vigente, su verificación y los roles se conservan hasta la confirmación explícita del titular mediante POST. Se avisa de la solicitud al correo vigente y se envía un enlace de quince minutos al nuevo. La confirmación revalida la unicidad bajo bloqueo, limpia la solicitud y notifica a ambas direcciones sin revelar la otra en el cuerpo. Las solicitudes sustituidas y los enlaces usados no se reutilizan. Una cuenta sin verificar utiliza corrección inicial.

La recuperación responde de forma genérica y sólo genera correo para una cuenta activa, verificada y con contraseña utilizable. El cambio propio y la recuperación guardan la credencial y retiran la obligación provisoria en una transacción, con un único aviso «Cambiaste tu contraseña». La recuperación no inicia sesión; las sesiones anteriores pierden validez. Los reintentos de entrega conservan el token y su vencimiento original.

A fines prácticos, un usuario con rol Alumno se considera vigente en un período determinado cuando tiene actividad de clases en ese período, por ejemplo un plan activo. Esto es informativo, para reportes y consultas; no equivale al estado de la cuenta ni condiciona ninguna otra regla del sistema.

La administración podrá asignar o quitar Profesor y Alumno, y volver a otorgar o quitar Reservas después del alta, únicamente a cuentas no administrativas. El retiro respeta las condiciones siguientes. Los perfiles de administradores no ofrecen modificación de roles y el servidor rechaza cualquier intento de asignarles otros.

El retiro de roles debe respetar las siguientes condiciones:

| Rol | Condición para quitarlo |
|---|---|
| Público | No se puede quitar. |
| Reservas | El usuario no tiene reservas propias en estado Programado. |
| Alumno | El usuario no tiene contrataciones de planes en estado Activo. Una membresía no impide retirar Alumno. |
| Profesor | El usuario no tiene asignaciones activas como profesor en clases cuyo evento esté Programado. |

Si existe una relación que impide el retiro, se rechaza la operación y se conserva el rol. No se cancelan reservas, contrataciones ni clases automáticamente para permitir quitarlo. Los registros históricos se conservan; las reservas y clases Anuladas o Finalizadas y las contrataciones Vencidas o Anuladas no bloquean por sí solas el retiro. Las comprobaciones se basan en el estado registrado, no solo en que una fecha haya pasado.

El estado activo o inactivo de las cuentas administrativas se gestiona con las mismas reglas de cambio de estado que el resto de los usuarios. `is_superuser` es la representación técnica de sus permisos, no otro rol ni una opción editable por separado.

Una persona con permiso para cambiar estados no puede desactivar su propia cuenta. Un administrador activo solo puede ser desactivado cuando permanece al menos otro administrador activo. Estas condiciones se validan al confirmar la operación y los cambios concurrentes se serializan para impedir que dos desactivaciones dejen al sistema sin administradores.

Una cuenta inactiva no puede autenticarse. La inactivación registra automáticamente la fecha y hora de baja de la cuenta. La reactivación elimina esa marca, de modo que una cuenta activa no conserva una fecha de baja vigente. Ambas operaciones actualizan también la fecha de última modificación.

La aplicación no expone la interfaz administrativa técnica de Django; toda operación cotidiana se realiza desde las pantallas de Academia TM.

#### Verificación y acceso de consulta

Verificación, habilitación administrativa y cambio de contraseña provisoria son condiciones independientes. Operar exige cuenta activa, correo verificado, contraseña propia cuando corresponda y roles o permisos de la operación. La elegibilidad de un destinatario para nuevas relaciones exige cuenta activa y correo verificado; no exige por sí sola haber sustituido la provisoria. Los selectores y la confirmación transaccional de clases, planilla, generación, reservas, invitaciones, contrataciones y roles aplican el mismo criterio. La asistencia conserva sus reglas históricas y no admite incorporar cuentas con correo inicial sin verificar.

Público sin verificar consulta sólo su perfil y oferta activa. Una cancha sólo se publica si también está activa su sede. Las consultas públicas usan vistas y plantillas de lectura con campos permitidos; no conceden permisos de Django para la gestión ni muestran observaciones internas, participantes, ocupaciones identificadas, contrataciones ajenas o Caja. Inicio y navegación no ofrecen operaciones a esa cuenta. Administrador sin verificar no accede a gestión; la provisoria conserva su restricción independiente. Verificar, corregir y reenviar siguen disponibles durante esa restricción.

La bienvenida incluye el enlace inicial y no contiene contraseña. El enlace identifica cuenta y correo, está firmado y vence a los quince minutos de su emisión; sólo un POST de confirmación registra la verificación. Se bloquea la cuenta al comprobar y guardar. No hay una tabla de enlaces ni una segunda bienvenida: la cola conserva la emisión técnica. Volver a usar el enlace informa que el correo ya está verificado y no restituye Reservas. Los enlaces iniciales pueden entregarse y confirmarse aunque la cuenta esté inactiva, sin conceder acceso operativo. Verificar una cuenta inactiva no la reactiva; la asignación automática de Reservas acompaña la verificación sin conceder acceso mientras esté inactiva.

El reenvío solicita email y responde genéricamente, exista o no la cuenta. Entre solicitudes de la misma cuenta hay un mínimo de cinco minutos. Cada enlace emitido tiene su propio plazo; pedir otro no invalida por sí solo los vigentes del mismo correo. La corrección inicial exige contraseña vigente al titular autenticado, o permiso de edición de usuarios a administración. Valida unicidad sin distinguir mayúsculas, actualiza la dirección bajo bloqueo y guarda el nuevo aviso en la misma transacción; invalida enlaces y avisos de la revisión anterior, aunque después vuelva a usarse aquella dirección. Ni reenvío ni corrección extienden los siete días desde el alta.

La limpieza horaria selecciona cuentas aún sin verificar que cumplieron siete días. Bloquea la misma fila que la verificación, revisa roles iniciales y todas las referencias operativas y elimina cuenta y roles en una transacción. Ante inconsistencias conserva todo y registra el resultado para corrección administrativa. La historia de acceso y auditoría no bloquea por sí sola la limpieza: conserva el identificador de actor sin una FK que obligue a mantener esa cuenta. No se actualiza ni borra el historial. Si se verificó primero, no se elimina; si se limpió primero, el enlace informa indisponibilidad y permite un nuevo registro. Mientras exista, una cuenta puede verificarse después de siete días con un enlace vigente.

El límite de reenvío se representa con `verificacion_solicitada_en`, dato técnico excluido del historial de diferencias funcionales. La cola registra cada aviso. El cambio de email y el registro de `correo_verificado_en` sí participan de auditoría. No se incluyen contraseñas, tokens o enlaces completos en sus valores ni errores.

### 2.4 Planes, membresías, contrataciones y precios

Los catálogos de planes y membresías son independientes. Cada producto guarda nombre, descripción, precio vigente, estado y su configuración específica.

- `planes` define modalidad individual o grupal, frecuencia de uno a siete encuentros semanales y una o dos clases consecutivas de una hora por encuentro.
- `membresias` define dos cupos mensuales positivos e independientes, de organizador y de invitado, precio mensual y adicional por invitado sin beneficio. Habilita cualquier día y sede, sujeto a disponibilidad.

Cada configuración de plan y cada membresía es un producto completo de su catálogo. Nombre, descripción y precios pueden actualizarse; la configuración estructural se conserva cuando tiene contrataciones históricas. Un producto inactivo no admite contrataciones nuevas y no altera las existentes.

El nombre es único sin distinguir mayúsculas y minúsculas entre productos Activos de cada catálogo; planes y membresías no comparten esa comparación. Los precios de catálogo pueden ser cero y no pueden ser negativos; las horas mensuales de una membresía son positivas.

`planes_usuarios` y `membresias_usuarios` registran las contrataciones por separado. Cada contratación identifica al usuario y al producto y conserva el mes cubierto, fecha efectiva de alta, precio aplicado, ambos cupos aplicados en membresías, responsable del registro, observaciones y estado Activo, Anulado o Vencido. Las contrataciones y renovaciones se registran por administración, con responsable obligatorio y cobro separado. El titular consulta y responde la encuesta de continuidad según 2.15.

Un usuario puede tener un plan y una membresía para el mismo mes, pero no dos contrataciones no Anuladas del mismo tipo. Los Vencidos también protegen la exclusividad histórica de su mes. Anular conserva la fila y permite registrar un reemplazo. Renovar para otro mes crea una contratación nueva; usuario, producto, mes e importe aplicado no se editan en un registro existente.

Sólo se anulan contrataciones Activas. La anulación administrativa exige motivo y conserva administrador y momento, sin modificar automáticamente cobros, clases, reservas ni coberturas aplicadas. Si corresponde reintegrar dinero, se registra un Egreso de categoría devoluciones según 2.5, separado de la anulación de la contratación. Una contratación de membresía Anulada no admite nuevas aplicaciones, pero mantiene las coberturas registradas. El vencimiento se define en 2.13 y los avisos en 2.6.

Registrar una contratación Activa de plan otorga Alumno si falta ese rol y el titular no es administrador; una membresía no lo otorga. Una cuenta con rol Profesor no puede contratar planes de clases mientras conserve ese rol. La incompatibilidad se valida al confirmar cualquier contratación de plan, propia o administrativa. Contratar membresías no tiene esta restricción. El titular puede consultar sus propias contrataciones de ambos tipos y el acceso a una membresía no exige Alumno. Las clases se organizan mediante asignaciones y asistencia; contratar un plan no genera clases ni asigna horarios automáticamente. La frecuencia contratada se administra según la organización de la academia, sin un control automático de cumplimiento del plan.

Los precios vigentes se aplican a operaciones nuevas; Actualizar socios sólo modifica la condición comercial de invitados según 2.2 y conserva el adicional unitario aplicado. Cada contratación o reserva conserva sus importes aplicados; actualizar el catálogo o la tarifa de sede no modifica las operaciones existentes. La historia comercial se consulta a partir de esos importes, sin un historial independiente de cambios de precio.

El Administrador configura un único precio positivo por turno de una hora en cada sede, común a todas sus canchas. El valor puede estar vacío mientras no se configure; sin tarifa no se confirma una reserva normal. La configuración y el registro se coordinan bloqueando la sede dentro de la transacción. Un importe igual al vigente no genera cambios.

Al registrar una reserva normal, el servidor valida y copia el precio vigente de la sede. Si cambió mientras se seleccionaba el turno, muestra el nuevo total y exige confirmar nuevamente. El total de una reserva normal es el precio por turno aplicado, sin multiplicadores ni subtotales horarios.

Planes y membresías aplican el precio mensual vigente completo al confirmar y lo conservan en `precio_aplicado`, sin importe negociado al registrar ni descuentos o recargos por fecha de pago. El servidor determina el precio y exige nueva revisión si cambió desde el resumen. El pago posterior y los aumentos del catálogo no modifican la contratación. Renovar otro mes crea otra operación con el precio vigente en su propia confirmación. La membresía no tiene prorrateo; las altas tardías de planes se coordinan administrativamente.

Al registrar un ingreso vinculado se muestran producto, mes, precio aplicado y cobros Vigentes anteriores. El concepto explica pagos parciales o acuerdos excepcionales sobre el dinero recibido, sin cambiar el precio confirmado. Una contratación de ARS 40.000 puede recibir ARS 35.000 con esa explicación; la comparación con el neto indica Diferencia por cubrir según 2.5.6, sin modificar el importe acordado ni registrar descuentos. Las observaciones comerciales conservan acuerdos generales sin representar dinero recibido. Una contratación Vencida admite cobros posteriores; una Anulada no.

La membresía cubre el mes calendario completo, sin prorrateo, con cupo completo menos los usos conservados del titular y mes. No acumula horas ni tiene variantes por día o límites diarios. Los precios pueden cambiar para nuevas operaciones; las horas mensuales no se modifican si el producto tiene cualquier contratación histórica. La oferta inicial de diez horas de organizador y diez de invitado, ARS 40.000 mensuales y ARS 12.500 por invitado no socio es configurable en catálogo.

No se puede anular una contratación aplicada como organizador o invitado socio Aceptado en una reserva Programada. Pendientes, Rechazadas y reservas Anuladas o Finalizadas no bloquean; conservan sus referencias. Reemplazar la contratación del mismo titular y mes no reinicia horas: descuenta los usos conservados de todas sus contrataciones de ese período, incluso Anuladas y aunque el producto tenga otro cupo. Una contratación Anulada no admite nuevas aplicaciones. La condición de socio no requiere un rol propio.

Cada contratación de plan o membresía dispone de un comprobante desde su detalle, con el mismo estilo de los comprobantes de reserva y opción de imprimir o guardar como PDF mediante el navegador. Administración puede consultar todos; el titular sólo los propios. Incluye tipo y número de contratación, estado, usuario, producto, mes y período cubiertos, fecha efectiva de alta, condiciones del plan o de la membresía e importe guardado en la contratación. No utiliza el precio vigente del catálogo ni acredita un pago. Conserva el acceso para contrataciones Vencidas o Anuladas. Los responsables, las observaciones y el motivo de anulación son exclusivos de administración, igual que en el detalle; el titular puede consultar las fechas de registro y anulación.

#### Ajustes administrativos y disponibilidad por rol

El producto ofrece 10 horas de organizador y 10 de invitado. La contratación conserva ambos cupos frente a cambios del catálogo. Por rol y mes se muestran cupo, horas otorgadas y descontadas, comprometidas, consumidas y disponibles: `disponibles = cupo + otorgadas − descontadas − comprometidas − consumidas`. No se comparten ni transfieren horas entre roles o meses. Los usos conservados de contrataciones Anuladas cuentan en el reemplazo del mismo titular y mes para cada rol. Si esos usos alcanzan o superan el cupo, no hay horas para nuevas participaciones.

Sólo administración puede otorgar o quitar horas de una contratación Activa del mes vigente o programada para un mes futuro. Exige tipo de horas, operación, cantidad entera positiva, motivo obligatorio visible al titular, responsable y fecha. No modifica cupo base, producto, precio, ingresos ni devoluciones. Quitar más de lo disponible se rechaza e informa el máximo; no se cancelan participaciones ni se generan saldos negativos, penalizaciones pendientes o descuentos diferidos.

Los ajustes son movimientos inmutables con efecto firmado. Corregir exige reversión identificada con motivo y responsable, sin borrar el original ni admitir doble reversión. También se rechaza una reversión que deje disponibilidad negativa. El historial propio y administrativo muestra tipo, cantidad, operación, fecha, motivo y reversión. Los ajustes y reversiones conservan datos de creación; el registro original y su reversión explican la secuencia administrativa sin editar un saldo.

### 2.5 Caja y movimientos

El sistema administra una única caja para toda la academia y como máximo una sesión abierta. `movimientos_fondos` es la fuente única de cobros y registra las clases Ingreso, Egreso, Aporte y Retiro. Los cobros se cargan manualmente; no hay pasarela ni confirmación automática de pagos. Se admiten pagos parciales mediante varios ingresos vinculados al mismo origen. Las reservas confirmadas admiten señas o adelantos como ingresos vinculados, sin exigirlos para confirmar la reserva. La situación comercial se deriva del importe acordado y el neto recibido según 2.5.6; no altera la contratación ni exige cobro previo para utilizar beneficios.

#### 2.5.1 Acceso y sesión

El acceso a caja exige usuario autenticado, activo, sin cambio obligatorio de contraseña y con rol Administrador. La marca `is_superuser` por sí sola no habilita ese acceso. El administrador que abre es el responsable fijo y quien registra movimientos y cierra la sesión. Otros administradores pueden consultar, pero no operar esa sesión. No hay reasignación. Anular un movimiento requiere ser responsable de la sesión abierta actual, incluso si pertenece a una sesión cerrada. Los permisos se verifican en vistas y se vuelven a comprobar en los servicios al confirmar.

La apertura declara efectivo inicial no negativo y usa el momento del servidor. El contado del último cierre es una referencia, no un importe trasladado automáticamente. Si el inicial difiere, se muestra un aviso y se exige explicación breve en `motivo_apertura`; si coincide o es la primera apertura, queda vacío. La diferencia entre sesiones no genera un movimiento. Puede haber varias sesiones sucesivas por día y una sesión puede atravesar medianoche. No hay cierre automático ni reapertura.

#### 2.5.2 Registro y medios

Cada movimiento pertenece a una sesión abierta y registra concepto obligatorio, monto positivo en pesos, medio, fecha del servidor, responsable y UUID único de operación. Los importes usan dos decimales y Decimal, sin floats. Los estados son Vigente y Anulado. La única fecha de carga es `creado_en`; no se ingresa una fecha real histórica ni futura. Apertura, anulación y cierre utilizan también el momento del servidor y la zona `America/Argentina/Salta`.

Los medios son efectivo, transferencia, tarjeta y QR. Los no efectivos requieren referencia de texto y verificación manual del administrador: recepción para un ingreso, pago realizado para un egreso o aprobación de la operación con tarjeta. La referencia identifica la operación o el comprobante; no almacena credenciales ni datos completos de tarjeta. Registrar una tarjeta no confirma su acreditación bancaria. El módulo no administra saldos de cuentas personales ni liquidaciones de tarjetas.

Todo Ingreso tiene una categoría obligatoria: reservas, planes, membresías u otros. Si se vincula a una reserva o contratación, la categoría se determina por el tipo de origen y no es editable. Sin vínculo la categoría es Otros. La categoría agrupa cobros; el vínculo identifica el registro concreto pagado.

Un Ingreso puede referenciar como máximo una contratación concreta de plan, una contratación concreta de membresía o una reserva; el vínculo es opcional y el concepto siempre es obligatorio. No referencia productos del catálogo. No se registran nuevos ingresos vinculados a contrataciones Anuladas ni reservas con evento Anulado. La reserva o contratación se confirma y luego se registra el cobro en una operación separada; si falla la carga monetaria, el origen permanece confirmado. Registrar un cobro no crea ni renueva la contratación ni modifica el precio.

Un Egreso exige categoría, concepto, monto y medio. El destinatario es texto opcional, también para devoluciones. Las categorías son alquiler, servicios, profesores, insumos, mantenimiento, publicidad, otros y devoluciones. No requiere crear usuarios para proveedores. Registrar pagos a profesores no calcula salarios ni honorarios. El registro comprende pagos realizados, no compromisos futuros, y no constituye contabilidad general.

Aporte y Retiro son únicamente efectivo, con concepto explicativo. No se cuentan como ingresos ni gastos operativos. Retirar efectivo para depositarlo no genera un ingreso por transferencia. Una salida en efectivo no puede superar el efectivo esperado disponible. Si hace falta aportar dinero, el aporte se registra como otra operación y luego se carga la salida.

#### 2.5.3 Devoluciones y anulaciones

Una devolución es dinero efectivamente reintegrado a un cliente y se registra como Egreso de categoría devoluciones, por efectivo, transferencia, tarjeta o QR. Exige concepto, monto positivo y referencia si el medio no es efectivo; el destinatario es opcional. Puede vincularse a una reserva o contratación concreta, como máximo un origen, sin referenciar un ingreso particular. El máximo es ingresos Vigentes menos devoluciones Vigentes del origen; sólo un neto positivo permite una nueva devolución vinculada. Se admiten orígenes Anulados que conservan cobros. Sin vínculo exige concepto y validaciones habituales de caja y medio, sin tope comercial. Los demás egresos no admiten vínculos comerciales. Una compensación superior a lo recibido corresponde a otro egreso, con categoría y concepto propios. Se identifica por separado en los resúmenes y no se presenta como gasto operativo. No modifica automáticamente cobros, contratación ni reserva. Cancelar una reserva, o anular una contratación, no reintegra dinero ni anula cobros automáticamente: si corresponde devolver, la administración registra el egreso.

La anulación invalida una carga errónea, no entrega dinero. Ingresos y egresos, incluidas devoluciones, así como aportes y retiros, pueden anularse con motivo obligatorio, actor y momento del servidor. No se borran ni se editan sus datos originales. Un movimiento Anulado no se reactiva ni vuelve a anularse.

En una sesión abierta, la anulación recalcula el efectivo esperado y no puede dejarlo negativo. En una cerrada no modifica los importes guardados del cierre ni sus totales históricos. El hecho correcto se registra como nuevo movimiento independiente en la sesión actual, sin vínculo automático con la carga anulada. Si es efectivo tiene efecto ordinario aunque no haya movimiento físico actual: puede producir una diferencia explicada y el arqueo no representa exclusivamente movimientos físicos de esa sesión.

Se permite anular un ingreso erróneo o duplicado aunque revele neto comercial negativo. Las devoluciones permanecen Vigentes y se informa una diferencia para revisión administrativa; no se generan movimientos compensatorios. Se mantienen motivo, auditoría, permisos y validación de efectivo disponible.

#### 2.5.4 Arqueo y cierre

`efectivo esperado = efectivo inicial + ingresos en efectivo + aportes − egresos en efectivo − retiros`

El cálculo de la sesión abierta usa solo movimientos Vigentes. Transferencia, tarjeta y QR figuran en los resúmenes, pero no alteran el efectivo esperado. Los egresos de categoría devoluciones en efectivo también son salidas para el arqueo.

El responsable declara efectivo contado no negativo y el servidor calcula `diferencia = contado − esperado`: positiva significa sobrante y negativa, faltante. Si no es cero se exige motivo. No se genera un movimiento automático por la diferencia. Al confirmar se recalcula el esperado y se guardan esperado, contado, diferencia, motivo y momento del servidor. Si el cálculo definitivo presenta diferencia sin explicación, se solicita revisar y completar. Cancelar el formulario conserva Abierta la sesión.

El servicio impide modificar, borrar o reabrir una sesión Cerrada y agregarle movimientos. El resumen histórico incluye los movimientos válidos al cerrar: sin anulación o con `anulado_en > cerrada_en`. Los anulados con `anulado_en <= cerrada_en` no suman. Las anulaciones posteriores son consultables sin modificar los importes guardados del cierre.

#### 2.5.5 Consultas, auditoría y consistencia

La consulta comercial de una contratación o reserva presenta una única situación financiera según 2.5.6. Usa ingresos y devoluciones vinculados en estado Vigente y excluye movimientos Anulados. Este criterio es distinto del resumen histórico de una sesión cerrada.

Caja ofrece resumen de sesión por clase y medio, historial por fecha de apertura y estado, y movimientos filtrados por fecha de registro, sesión, clase, categoría, medio y estado. Los ingresos se resumen también por categoría. El detalle muestra datos de creación, referencia, vínculo comercial y anulación cuando corresponde. Los datos se muestran primero; apertura, carga, anulación y cierre se revelan mediante disparadores explícitos. Las listas usan filas compactas y un menú por movimiento, sin formularios permanentes por fila. El estado vacío tiene un texto breve y una acción principal; solo se ofrecen acciones válidas para el estado y los permisos.

Registro, anulación y cierre usan `transaction.atomic` y `select_for_update` sobre la sesión. Anular un movimiento de otra sesión bloquea también esa sesión de origen. La apertura usa transacción e índice único parcial sobre estado Abierta; una colisión informa que existe una sesión abierta. Un registro concurrente con cierre se confirma dentro de la sesión abierta o se rechaza por sesión cerrada. Se validan campos, responsabilidad, estado, vínculo y disponibilidad dentro de la transacción; un error revierte la operación completa. Las escrituras usan POST y protección CSRF; las consultas no modifican datos.

El UUID de movimiento se conserva al reenviar el formulario. Un reintento con el mismo actor y contenido devuelve el registro existente; con otros datos se rechaza. Es distinto del UUID del contexto transaccional de auditoría y no se exige que coincidan.

Ambas tablas participan de la auditoría transversal de 2.14: el cierre es una modificación y la invalidación de un movimiento es una anulación. Las altas conservan sus campos de creación sin generar entradas de alta en el historial. La inmutabilidad de caja se garantiza en servicios; no hay triggers adicionales que impidan modificar sus tablas por SQL. Los triggers de auditoría registran esos cambios, pero no los impiden.

#### 2.5.6 Situación financiera por operación

Reservas y contrataciones presentan una única situación financiera en su detalle, con importe acordado, cobros vigentes (suma de ingresos Vigentes), devoluciones vigentes (suma de devoluciones Vigentes) y neto recibido (`ingresos − devoluciones`). Los saldos y estados se calculan a partir de esos datos, sin almacenarlos como valores mutables. Para operaciones no anuladas, neto menor al importe indica Diferencia por cubrir; igual, Cubierto; mayor, Excedente por resolver. Diferencia por cubrir expresa la diferencia entre el importe acordado y el neto recibido, sin afirmar por sí sola una deuda exigible. El excedente no genera devolución automática. Un neto negativo muestra además una diferencia para revisión administrativa.

Las operaciones Anuladas muestran movimientos y neto sin exigir completar el importe original ni presumir obligación de devolución. Cada movimiento permanece en su operación; no se reasigna ni compensa automáticamente con una nueva reserva o contratación. Una devolución efectiva se registra en la sesión abierta y reduce el neto recibido sin borrar ni modificar los ingresos originales, el importe acordado o los cierres históricos. Devolver dinero y modificar el precio son decisiones distintas: cualquier modificación del importe acordado requiere una operación autorizada y auditada; registrar una devolución no realiza ese ajuste. Administración y titular consultan su situación y movimientos autorizados; los invitados no acceden a información financiera ajena.


### 2.6 Notificaciones

Los emails de bienvenida y verificación, seguridad de cuenta, clases, reservas, contrataciones, ajustes, movimientos vinculados y continuidad se describen dentro de sus flujos de origen. Los destinatarios y exclusiones se rigen por estos criterios y por los flujos de origen de cada operación. No hay una bandeja de notificaciones para usuarios ni seguimiento de lectura.

#### Persistencia y entrega

La operación guarda su email en `envios_email` dentro de la misma transacción. Si se revierte la operación, tampoco queda el aviso. Cada aviso tiene una clave única por hecho efectivo y destinatario; reintentar una solicitud sin otro cambio no crea un segundo envío. La clave no se reutiliza para contenido o destinatario diferente. Pedir expresamente otro enlace constituye otra solicitud y respeta su límite funcional.

El correo se entrega en segundo plano mediante Celery. Después del commit sólo se intenta despertar al trabajador; si Redis no está disponible, la operación permanece confirmada y el aviso sigue pendiente. Un barrido técnico cada sesenta segundos recupera pendientes cuyo próximo intento ya llegó y reservas de procesamiento abandonadas. Ese barrido no selecciona clases, reservas ni campañas: sus procedimientos funcionales tienen sus propios horarios.

Los estados son Pendiente, En proceso, Enviado, Fallido y Descartado. El trabajador reclama un aviso mediante bloqueo de fila y una reserva de cinco minutos con identificador propio. La llamada al proveedor ocurre fuera de las transacciones de base y tiene un timeout de treinta segundos. Dos trabajadores no reclaman simultáneamente el mismo pendiente. Si la reserva vence sin resultado, se registra la interrupción y se aplica la política de fallo; una confirmación del trabajador anterior no puede sobrescribir una reserva nueva.

Un fallo programa reintentos a los 5, 15 y 60 minutos después del fallo correspondiente. Tras cuatro intentos fallidos queda Fallido. Los avisos que pierden vigencia quedan Descartados, sin reintento. El error resumido no incorpora el texto devuelto por el proveedor ni contiene contraseñas, tokens o enlaces. Enviado significa aceptación por el servicio de correo, no llegada a la bandeja de entrada. Si el proveedor acepta pero se pierde la confirmación local, puede repetirse una entrega al reintentar; la unicidad local no elimina ese límite del transporte.

Los enlaces se preparan en el primer intento, guardando la emisión. Vencen a los quince minutos, incluido el extremo final, y los reintentos conservan ese plazo. No se persisten enlaces completos ni tokens firmados en los datos de la cola. Las solicitudes sustituidas y los enlaces vencidos se descartan. Las direcciones y datos mínimos necesarios se capturan al confirmar el hecho; antes de entregar se comprueban cuenta, solicitud, participación y vigencia según el tipo. Los recordatorios no se entregan si la actividad empezó o dejó de estar Programada. No asisto excluye recordatorio de clase; una invitación Rechazada excluye posteriores avisos de esa reserva. Una nueva participación se distingue de otra retirada mediante su identidad y fecha de creación.

Los avisos de retirada conservan evidencia de la asignación eliminada y no exigen que siga existiendo. Anulación y retirada pueden entregarse después de la hora de la actividad. El aviso de deshabilitación admite la cuenta ya deshabilitada, y los cambios de correo utilizan las direcciones del recorrido confirmado. Estos mensajes no restauran permisos ni asignaciones.

#### Presentación y consulta

Todos los tipos usan una base HTML compartida de Academia TM, con logo, violeta `#4B176D`, acento `#B6D532`, tipografía Arial con alternativas sans-serif, encabezado, datos, acciones y pie. El logo se incorpora como imagen adjunta inline referenciada por Content-ID; no requiere descargar archivos desde el servidor web. Cada mensaje tiene una versión de texto simple con igual información y enlaces, legible sin imágenes. Los apartados agrupan únicamente información autorizada para su destinatario. Las fechas usan `dd/mm/aaaa`, las horas `HH:MM` y los importes `ARS` con dos decimales. Los estilos son propios del email y no dependen de CSS o JavaScript del sitio.

Los enlaces usan exclusivamente el origen público configurado y rutas internas; no se construyen desde el Host de una solicitud. Remitente, backend, servidor y credenciales se configuran por entorno. La entrega está desactivada por defecto; la salida a servicios externos requiere habilitación explícita adicional. El transporte de pruebas permanece en memoria. Activar infraestructura no autoriza desplegar recorridos funcionales incompletos.

La activación exige un origen público accesible para los destinatarios, remitente y credenciales por entorno, PostgreSQL y Redis disponibles, trabajadores y un único proceso Beat. Los interruptores `EMAILS_HABILITADOS`, `EMAILS_ENTREGA_EXTERNA_HABILITADA` y `EMAILS_TAREAS_PROGRAMADAS_HABILITADAS` se habilitan como un paso separado de la revisión técnica. El entorno local puede conservarlos apagados y usar localhost sin autorizar entregas externas.

Antes de aplicar migraciones incompatibles se respaldan los datos y se detienen las escrituras de web, trabajadores y planificador. Se comprueban las migraciones y restricciones antes de reabrir escrituras. Un fallo de migración mantiene detenidas las operaciones afectadas; un fallo del proveedor conserva la operación confirmada y su aviso pendiente. La reversión no reconstruye asignaciones eliminadas ni sus identidades; recuperar esas relaciones requiere un respaldo consistente. No se truncan tablas ni se borran volúmenes como procedimiento de activación.

Administración consulta los envíos en una tabla compacta de veinticinco filas por página, con fecha, tipo, destinatario y estado. Los filtros por estado, tipo y destinatario aparecen al pedirlos. Cada fila permite desplegar intentos, fechas de entrega y error resumido. No se muestran datos de preparación, claves de aviso, tokens ni enlaces de acceso. La consulta exige cuenta activa, sin cambio obligatorio de contraseña y rol Administrador, y sólo admite GET. No ofrece reenvío manual ni edición del registro técnico.

Los avisos se guardan dentro de la transacción de la operación confirmada, con claves por participación o cambio efectivo. Las llamadas anidadas de feriados, bloqueos y lotes utilizan la misma anulación individual y no multiplican mensajes. Revertir una operación revierte sus avisos; la entrega del proveedor ocurre fuera de la transacción.

Antes de entregar se comprueban cuenta activa y verificada, dirección vigente, relación y permisos aplicables. La deshabilitación permite su propio aviso. Los cambios de correo conservan sus destinatarios especiales. Una invitación Rechazada queda fuera de posteriores avisos de reserva; No asistirá excluye recordatorio, no anulación. La retirada conserva evidencia mínima sin exigir el vínculo borrado. Los agrupados de generación eliminan sólo los apartados que perdieron vigencia.

No generan emails cambios de roles, planilla u observaciones, vencimiento efectivo, movimientos sin vínculo, anulación de movimientos, liberación de bloqueos, finalización, asistencia ni resultado de uso. Los avisos de asignación dentro de la hora previa conservan cobertura de recordatorio por participación; las campañas horarias utilizan ese seguimiento.

Los recordatorios se revisan una vez por hora, en punto de Salta. Se seleccionan inicios todavía futuros cuya hora de aviso ya llegó, sin exigir coincidencia exacta del minuto ni de la fecha. Un aviso de alta dentro de la hora previa cubre el recordatorio aun pendiente de entrega; el fallo se reintenta sobre el mismo envío. La identidad de participación distingue retiradas y nuevos agregados. Aceptar después del recordatorio de invitación Pendiente no produce otro aviso de inicio.

Las campañas de encuesta se revisan a las 09:00: el 25 corresponde a apertura; el último día real del mes y el 5 siguiente son recordatorios sólo de Sin responder. El 5 usa el mes cubierto anterior y admite contratos Vencidos con encuesta abierta. Cada persona recibe un agrupado por fecha; antes de entregar se excluyen los apartados que perdieron vigencia o recibieron respuesta. El aviso vence al terminar ese día de Salta. La confirmación de una contratación tardía con encuesta abierta cubre su apertura, sin excluir recordatorios posteriores cuando falte responder.

`EMAILS_TAREAS_PROGRAMADAS_HABILITADAS` controla la programación y ejecución de recordatorios y campañas, con valor desactivado por defecto e independiente de los interruptores de entrega. No se activan por aplicar migraciones. El seguimiento de envíos reemplaza las marcas individuales de recordatorio y vencimiento.

### 2.7 Portal de usuarios

El sistema tendrá un único portal de acceso externo, para cualquier persona que se registre como usuario, separado de la interfaz de gestión interna (ver intro de la sección 2).

El catálogo de planes, membresías y tarifas vigentes sólo puede consultarse estando registrado y autenticado con el rol Público: es el equivalente, dentro del sistema, a tener que preguntar en la sede antes de conocer los precios.

Un usuario con rol Reservas podrá consultar, crear y cancelar sus propias reservas de cancha desde el portal, normales o con membresía, con las mismas reglas que la gestión interna (ver 2.2); se asigna automáticamente al verificar por primera vez el correo de una cuenta no administrativa. El portal incluye la grilla de Agenda para consultar disponibilidad y elegir un turno libre desde el que iniciar la reserva. Agenda es la entrada única para las actividades. El panel de una reserva propia permite acceder a su detalle y comprobante, con las acciones propias autorizadas. La búsqueda de registros se contempla dentro de Agenda. El historial de cada turno permite consultar las anulaciones propias. Puede gestionar invitados de ambas modalidades según 2.2 y solicitar Actualizar socios en reservas con membresía; las invitaciones tienen respuesta propia del titular.

Cualquier usuario autenticado puede consultar sus clases asignadas como participante y su historial de asistencia, aunque no tenga Alumno. El Administrador conserva el acceso total. Los profesores tienen acciones de docencia únicamente en las clases que están asignados a dictar; asistir como participante no agrega esas acciones. Cualquier titular autenticado puede consultar sus propios planes y membresías contratados, incluidos sus importes, período, cobros vigentes desde movimientos y usos de membresía, sin exigir Alumno para una membresía. La consulta propia de cobros no permite acceder a caja, informes globales ni movimientos de terceros y no muestra deuda calculada.

El invitado consulta y responde sus invitaciones propias según 2.2, sin acceder a comprobantes ni información financiera ajena. Puede cambiar su decisión antes del inicio, conservando auditoría. El participante registra un aviso irreversible de no asistencia de sus clases concretas según 2.1, antes del inicio.

Desde Mis contrataciones el titular consulta planes y membresías, sus movimientos autorizados y responde la encuesta de continuidad según 2.15. Las contrataciones, renovaciones, cambios, anulaciones y reemplazos son administrativos. Oferta es de sólo lectura.

El perfil propio permite consultar los datos personales y de la cuenta, los roles y el estado, y cambiar únicamente la contraseña propia mediante **Cambiar mi contraseña**. La modificación del correo se realiza exclusivamente por el Administrador mediante la gestión de usuarios; el resto de los datos personales no tiene edición desde la aplicación. La obligación de reemplazar una contraseña provisoria se cumple antes de acceder al perfil o a cualquier otra función del portal. El portal ofrece catálogo, consulta de contrataciones propias y la encuesta de continuidad de 2.15; los cobros son exclusivamente administrativos.

Las reservas creadas desde el portal se pagarán en la sede, igual que las gestionadas internamente; el portal no integrará un cobro online para reservas.

Quedan fuera del portal en esta etapa: elegir el turno semanal de un plan (lo sigue asignando la administración) y una bandeja de notificaciones dentro del sistema.

### 2.8 Agenda unificada

Cada celda con un evento visible muestra su icono de estado en la esquina superior derecha, con la misma representación del resumen del panel lateral. Si tiene eventos Anulados accesibles, muestra un icono calendar-minus de Iconoir en la esquina inferior derecha, sin fondo, cantidad ni acción independiente, con el mismo tamaño, color y márgenes que el icono de estado. Al seleccionar el turno, el panel lateral ofrece «Ver eventos anulados», que abre una vista de sólo lectura dentro del mismo panel, con horario, cancha y un enlace para volver al turno. La lista se ordena por momento de anulación descendente. Cada fila reutiliza el fondo de su tipo de evento y funciona como enlace a su detalle: reservas y clases utilizan sus pantallas de detalle y los bloqueos tienen un detalle de sólo lectura exclusivo de administración. Destaca el tipo sobre el organizador de la reserva o el motivo clasificado del bloqueo, presentado como información secundaria. No incluye motivo de anulación, identificadores internos ni datos de responsable o momento de anulación. Escape cierra el panel y devuelve el foco al turno seleccionado. La administración consulta todas las anulaciones; el portal sólo las reservas propias y las clases vinculadas al usuario como profesor, participante o asistente. La consulta directa aplica el mismo filtro y no revela datos ajenos. Las horas con historial accesible se conservan visibles y seleccionables incluso en fechas pasadas o fuera de las franjas actuales. La selección del turno se conserva mientras se consulta su listado de anulaciones.

Agenda permite consultar disponibilidad, elegir turnos y ejecutar las acciones autorizadas. La administración accede a toda la ocupación; el portal ofrece la misma grilla para consultar disponibilidad y operar sobre reservas propias según los permisos. Los turnos ocupados por actividades ajenas se muestran como No disponible, sin tipo de actividad, identificadores, participantes, observaciones ni datos comerciales. Su panel sólo muestra sede, cancha, fecha y horario. Las acciones administrativas son exclusivas de la administración. La vista diaria muestra todas las canchas de una sede en columnas y las horas en filas. La vista semanal de Agenda está en pausa. Se navega mediante sede, fecha, día anterior o siguiente y Hoy. El cambio de sede limpia la selección de cancha y turno. La navegación respeta los límites del calendario.

En el portal se ocultan las filas cuyo turno ya comenzó cuando ninguna cancha de esa fila contiene un evento propio. Las filas con eventos propios se conservan completas para consultar su detalle y comprobante, manteniendo la privacidad de las demás celdas. Las pausas iniciadas sin eventos propios también se ocultan. El corte se aplica al inicio del turno, con la zona horaria del sistema. La administración conserva la grilla completa. Un día pasado sin eventos propios muestra No tenés eventos en esta fecha; para hoy, sin eventos propios ni turnos pendientes de inicio, se informa esa condición.

La administración dispone además de una consulta rápida de disponibilidad: ingresa sede, fecha y hora de inicio, y puede indicar opcionalmente una cancha de esa sede. Sin cancha seleccionada se consultan todas sus canchas. El resultado identifica las canchas disponibles para el turno de una hora solicitado, sin exigir navegar por Agenda. Aplica los mismos horarios, estados de instalaciones, ocupación y límites de calendario que la consulta de Agenda, sin registrar turnos ni eventos. La consulta informa disponibilidad; la creación de una reserva comienza en Agenda y conserva su límite de tres días calendario siguientes inclusive.

En la vista administrativa cada celda distingue turno libre, reserva, clase o bloqueo. Seleccionarla muestra un panel con cancha, fecha, horario, participantes, estado e importes cuando corresponden y las acciones autorizadas para ese evento. En la vista diaria el panel acompaña a la grilla y se ubica debajo en pantallas pequeñas. Seleccionar un turno o cerrar el detalle actualiza sólo el panel y el resaltado, sin recargar la grilla ni desplazar la página. La consulta comprueba acceso y selección en el servidor. Ante un fallo conserva el detalle anterior y muestra un aviso; ante selecciones rápidas sólo aplica la última respuesta. Sobre un turno libre se puede crear una reserva, clase o bloqueo; sobre una reserva o clase, anular para liberar o anular y bloquear; sobre un bloqueo, anular para liberar. Cada acción conserva sus permisos, límites temporales y confirmaciones. La finalización administrativa de emergencia de una reserva vencida también está disponible desde su detalle en la agenda.

La consulta no registra eventos ni necesita una tarifa configurada. Los espacios libres se representan a partir del horario de funcionamiento, sin crear turnos persistidos por la mera consulta. Las actividades existentes fuera de las franjas actuales permanecen visibles. Una franja común sin actividad se representa como pausa; si un evento ocupa una hora de esa pausa, se muestra esa hora y su actividad. Los días o canchas sin horarios ni eventos tienen un estado vacío. Las instalaciones inactivas se incluyen para consulta histórica y no admiten nuevas actividades. Las horas fuera de las franjas no ofrecen creación de reservas, clases ni bloqueos.

El calendario puede consultarse desde el inicio de operaciones hasta un año después de la fecha local actual. Ver una fecha futura no habilita reservas fuera de los tres días de anticipación. La hora actual se destaca únicamente en el margen de horarios con la indicación Ahora; no se dibuja una línea sobre los eventos. Los turnos iniciados se atenúan y conservan su detalle. Las comparaciones utilizan la zona horaria del sistema.

Los formularios de acción permanecen vinculados al turno seleccionado. La confirmación muestra el organizador, cancha, fecha, horario e importe de la reserva; una ocupación o precio que cambió exige revisión. Una anulación identifica la reserva confirmada y no puede aplicarse a otra actividad que haya ocupado el mismo turno entretanto. Cada operación reutiliza sus validaciones transaccionales y vuelve a comprobar el acceso.

La administración puede consultar toda la ocupación. El profesor consulta las clases que dicta y aquellas a las que está asignado como participante, con las acciones propias de cada función y sin datos personales o comerciales de reservas ajenas. El portal mantiene las consultas y acciones propias definidas en 2.7. La creación y consulta de reservas se inicia desde Agenda, tanto en la administración como en el portal, sin una sección independiente de Reservas o Mis reservas ni un formulario de alta separado. El panel de cada reserva ofrece acceso a su detalle y comprobante; se conservan los datos de auditoría y las acciones autorizadas sobre registros existentes. La búsqueda por criterios se contempla dentro de Agenda. Los eventos Anulados se consultan desde el historial de su turno. Los bloqueos se consultan y operan desde Agenda, sin una sección independiente de navegación.

Los turnos vacíos cuyo horario ya terminó no ofrecen acciones sobre su estado actual; si tienen anulaciones accesibles, permiten seleccionar el turno y consultar su historial desde la opción del panel lateral. Los eventos finalizados conservan acceso a su detalle histórico.


### 2.9 Apariencia de la web

Las interfaces de administración y portal mantienen lectura primero, acciones bajo demanda y edición compacta por fila en todo el sistema.

Los permisos, estados y validaciones funcionales de este documento se aplican también a las consultas y escrituras de la interfaz. Ocultar controles no sustituye la autorización del servidor y ninguna confirmación permite ignorar una prohibición de negocio.

### 2.10 Bloqueos y acciones del día y del mes

#### 2.10.1 Bloqueos individuales

El Administrador podrá iniciar un bloqueo sobre un turno libre u ocupado por una reserva o clase Programada cuyo turno no haya comenzado. El motivo del bloqueo será clima adverso, torneo o mantenimiento. Su turno debe quedar íntegramente dentro de una franja de funcionamiento de la sede. La vista previa mostrará la actividad que deba anularse y el bloqueo que se creará. Primero se anula la actividad y se libera el turno; después se comprueba que esté libre y se registra un nuevo evento de bloqueo sobre ese mismo turno. Ambas acciones y su trazabilidad se guardan en una misma transacción. Anular una actividad por sí sola libera su turno y no crea un bloqueo.

Cada bloqueo ocupa un único turno y tiene estado y auditoría propios. Mientras esté vigente, impide registrar reservas, clases u otros bloqueos sobre ese turno. Liberarlo cambia su evento a Anulado, requiere un motivo y registra quién lo liberó y cuándo. Sólo se permite anular actividades y crear o liberar bloqueos antes del inicio del turno; los días pasados y los turnos iniciados quedan para consulta. Un bloqueo Programado cuyo turno terminó pasa a Finalizado mediante la tarea horaria de Celery, que registra el momento de procesamiento sin responsable de finalización. No admite liberación ni finalización manual. La tarea recupera también los bloqueos vencidos pendientes y conserva su ocupación histórica. Los eventos de reserva o clase anulados para bloquear se conservan vinculados mediante `bloqueos.evento_origen_id`, opcional y único cuando está informado.

#### 2.10.2 Alcance de las acciones del día

Las operaciones administrativas masivas permiten anular y liberar eventos o anular y bloquear turnos de una fecha completa o desde una hora de corte inclusiva, sobre una o varias canchas seleccionadas de una sede. Conservar actividades ofrece casillas independientes para clases creadas manualmente, clases generadas desde la planilla y reservas; para liberar también ofrece bloqueos. Las categorías marcadas se conservan y las no marcadas quedan incluidas en la operación si son elegibles. Marcar ambas categorías de clases conserva todas las clases; no marcar ninguna incluye ambos orígenes. La selección se aplica a Acciones del día y Acciones del mes. Bloquear incluye los turnos libres y conserva los bloqueos existentes, informados como ya cubiertos. Cada turno a bloquear origina su propio bloqueo, sin un evento agrupador ni un estado compartido.

En el día en curso sólo se incluyen turnos cuyo inicio sea posterior al momento de confirmar y sea igual o posterior al corte; a las 18:30 se puede operar desde las 19:00. A la hora exacta de inicio el turno ya se considera iniciado. Los turnos iniciados, los eventos Finalizados y los tipos excluidos se muestran como conservados y no impiden actuar sobre los demás. Los eventos Anulados se mantienen como historia y no se anulan nuevamente. Los cierres crean bloqueos únicamente sobre turnos contenidos en las franjas de funcionamiento. Las actividades existentes fuera de las franjas actuales se conservan y se informan; pueden anularse para liberar, pero no originar un bloqueo fuera de horario.

En Anular y bloquear de Acciones del día se elige un único motivo de bloqueo. Su nombre se guarda también como motivo de anulación de cada reserva o clase afectada, sin solicitar un campo adicional. La vista previa presenta ese motivo una sola vez y las observaciones del bloqueo siguen siendo opcionales.

#### 2.10.3 Selección y revisión

La entrada Acciones del día está en la tarjeta del título de Agenda y abre el mismo panel lateral del detalle, conservando la grilla visible y la sede y fecha consultadas. La lista Canchas ofrece Todas las canchas de la sede o Seleccionar; esta última opción permite marcar una o varias canchas. Horario ofrece Día completo y los cortes Desde las HH:00 correspondientes a inicios habilitados aún futuros en la fecha consultada. Al elegir un inicio, Hasta permite indicar opcionalmente una hora de fin, entre las horas de finalización de turnos habilitados posteriores al inicio, incluida la hora de cierre; no ofrece horas dentro de las pausas. El límite de fin es exclusivo: de 08:00 a 10:00 comprende los turnos de 08:00 y 09:00. Sin fin indicado se incluye el resto del día. Primero se eligen canchas, alcance, exclusiones y motivos; después se revisan las cantidades y los listados desplegables de acciones y eventos sin cambios. Abrir, revisar, volver a editar y cerrar actualiza únicamente el panel y la selección, sin navegar a otra página ni desplazar la grilla. Seleccionar un turno reemplaza el contenido del panel por su detalle.

La vista previa diferencia las acciones, los eventos conservados y los bloqueos ya existentes.

#### 2.10.4 Confirmación

La confirmación efectiva utiliza un envío completo y actualiza la agenda. La confirmación queda vinculada al actor y a los datos revisados y vence a los quince minutos. Si cambia la ocupación, el alcance o la elegibilidad después de preparar la vista previa, se exige revisarla nuevamente. La confirmación aplica el lote completo con las garantías de 2.12.


#### 2.10.5 Acciones del mes

La cabecera de Agenda ofrece la acción administrativa Acciones del mes. Abre el mismo panel lateral de Acciones del día, conserva la grilla y la sede consultadas y permite elegir un mes calendario completo. El selector es un desplegable con etiquetas como «Noviembre de 2026» y sólo muestra el mes actual y los dos siguientes. El mes de la fecha consultada se selecciona por defecto si está habilitado; al consultar una fecha fuera de ese intervalo se utiliza el mes actual. Cambiar el selector de mes actualiza automáticamente el panel; no requiere un botón de aplicación. Abrir, elegir mes, revisar, volver a editar y cerrar actualizan sólo el panel, sin navegar a otra pantalla ni desplazar la grilla. Seleccionar un turno reemplaza el panel por su detalle. El mes debe quedar dentro del calendario operativo. Reutiliza las opciones de Anular y liberar de Acciones del día: todas las canchas de la sede o una selección, día completo o desde una hora de inicio con fin opcional exclusivo, conservación de clases, reservas y bloqueos y motivo común de anulación. No ofrece crear bloqueos.

El horario elegido se aplica a cada día del mes. Las horas de inicio y fin se ofrecen según los turnos habilitados en los horarios semanales de la sede; los días con distintas franjas comparten la selección horaria, sin exigir que todos funcionen a la misma hora. Las actividades existentes dentro del intervalo pueden anularse aunque queden fuera del horario de funcionamiento vigente, con las mismas reglas que Anular y liberar del día.

Los días pasados y los turnos de hoy ya iniciados no se modifican. Los eventos iniciados, Finalizados y de tipos excluidos se muestran como conservados; los Anulados no se procesan. La vista previa muestra cantidades y listados desplegables con fecha, cancha, hora y acción o motivo de conservación. Los turnos libres no requieren acción. El motivo es obligatorio si hay anulaciones y exige al menos 5 caracteres para cualquier tipo de actividad.

Editar selección y confirmar utilizan el mismo recorrido de Acciones del día. La confirmación firma usuario, sede, mes, parámetros y conjunto revisado y vence a los quince minutos. El servidor sólo admite Anular y liberar para el alcance mensual. El mes completo se confirma en una única transacción: bloquea usuarios, sede, canchas, turnos y eventos, vuelve a validar el conjunto y revierte todo ante un cambio o si un turno alcanza su inicio. Conserva los datos y la auditoría de cada actividad.

Toda anulación administrativa de reservas mediante acciones del día o del mes libera la hora de membresía. La vista previa informa ese efecto y la confirmación lo guarda junto con eventos, cupos y auditoría, sin modificar cobros.

### 2.11 Instalaciones

#### 2.11.1 Datos y horarios

Los nombres de sede son únicos sin distinguir mayúsculas y minúsculas. Los nombres de cancha tienen la misma condición dentro de su sede, pero pueden repetirse entre sedes. Los formularios informan los conflictos antes de guardar. Los horarios de funcionamiento y sus cambios respetan las reglas comunes del inicio de la sección 2.

#### 2.11.2 Activación y desactivación

Desactivar una sede comprende los eventos de todas sus canchas; desactivar una cancha comprende sólo sus eventos. La operación es administrativa y se rechaza si existe una reserva, clase o bloqueo no Anulado cuyo turno esté en curso. Un turno está en curso desde su inicio inclusive hasta su fin exclusivo.

Si no hay eventos en curso, se muestra una vista previa de todas las reservas, clases y bloqueos Programados con inicio futuro. Confirmar anula esos eventos y desactiva la instalación en una única transacción. Todos reciben el motivo común «Actividad anulada por desactivación de la sede» o «Actividad anulada por desactivación de la cancha», según el alcance. Cada evento conserva actor, momento, participantes, importes y relaciones históricas. Las reservas quedan anuladas administrativamente y dejan de computar horas de membresía; no se registran bloqueos nuevos ni se modifican ingresos, devoluciones o contrataciones.

Los eventos Anulados y los turnos terminados no se anulan ni impiden desactivar. Las clases y reservas terminadas pendientes de finalización conservan su procesamiento normal. Los bloqueos terminados conservan su finalización automática y ocupación histórica.

La operación coordina el bloqueo de sede, canchas, turnos y eventos con la creación, edición, anulación y finalización de actividades. Vuelve a validar acceso, ocupación y límites temporales al confirmar y antes de terminar. Si cambia el conjunto de eventos revisado o alguno de los turnos a anular alcanza su inicio, revierte toda la operación y exige revisar la vista previa. No permite una desactivación con anulaciones parciales.

Las solicitudes establecen un estado concreto; repetirlas no invierte la acción ni sobrescribe auditoría. Modificar los datos de una instalación no puede sobrescribir su estado. Reactivar no restaura eventos Anulados ni modifica el estado individual de las canchas de una sede.


### 2.12 Consistencia de las operaciones e historia

Las operaciones que escriben datos vuelven a comprobar acceso, estado y condiciones de negocio al confirmar, independientemente de las validaciones de la interfaz. Los cambios que forman una sola acción se guardan en una única transacción: un error revierte todos sus efectos. Si cambia la selección o el conjunto de condiciones respecto de lo revisado, se solicita revisión antes de confirmar. Una operación repetida no duplica resultados ni sobrescribe auditoría.

La coordinación de escrituras concurrentes mantiene un orden consistente: cuentas administrativas que protegen el acceso, usuarios involucrados ordenados por identificador, instalaciones y calendario, turnos, eventos y sus relaciones, y contrataciones aplicadas ordenadas por identificador. Los servicios que utilizan un subconjunto respetan ese orden y las operaciones masivas reúnen todos los organizadores e invitados afectados antes de bloquear. No se adquieren usuarios después de bloquear eventos o contrataciones. La coordinación se aplica así:

- La asignación y el retiro de roles bloquean al usuario y se coordinan con la creación de relaciones que condicionan esos cambios.
- La inactivación de usuarios bloquea a los administradores activos para impedir que dos solicitudes concurrentes dejen al sistema sin uno. Las condiciones de permiso y retiro se definen en 2.3.
- Las operaciones de clases, reservas e invitados y la generación bloquean a los usuarios involucrados en orden de identificador antes de comprobar cupos y coincidencias.
- La configuración de tarifas y horarios, el cambio de estado de instalaciones y el registro de actividades se coordinan mediante la sede y sus canchas. Registrar o mover una actividad bloquea además los turnos involucrados y comprueba su ocupación compartida antes de escribir. Preparar un turno no crea un evento ni ocupa la cancha.
- Las operaciones con membresía, invitaciones, ajustes y reversiones bloquean personas y contrataciones aplicadas en orden estable antes de calcular usos mensuales por rol o actualizar beneficios. El mismo bloqueo coordina gasto y descuento de horas para que no utilicen simultáneamente la misma disponibilidad. El bloqueo del titular coordina altas y reemplazos de contratación, reservas e invitados para conservar usos del mismo mes y evitar participaciones o consumos concurrentes incompatibles.
- La contratación bloquea al usuario y al producto antes de comprobar exclusividad del mes, precio y configuración estructural protegida. La anulación bloquea al usuario y la contratación antes de validar su estado. El retiro de Alumno bloquea al usuario antes de comprobar que no tenga contrataciones de planes Activas.
- El alta administrativa bloquea al titular y al producto y revalida precio, apertura mensual y exclusividad. Responder continuidad bloquea titular y contratación, coordinándose con anulaciones y revalidando estado y plazo. Los reenvíos no generan otra contratación ni cobros; una revisión con datos diferentes exige confirmar nuevamente.
- Registro, anulación de movimientos y cierre usan `transaction.atomic` y bloqueo de la sesión mediante `select_for_update`. La anulación de un movimiento histórico bloquea también su sesión de origen. La apertura utiliza el índice único parcial para resolver concurrencia. Los vínculos comerciales se validan por existencia y estado al confirmar. Ingresos, devoluciones y anulaciones coordinan el bloqueo común del origen comercial y sus movimientos, además de la sesión, en orden estable. El neto se recalcula dentro de la transacción para impedir devoluciones concurrentes superiores al disponible y coordinar correcciones de movimientos. Las altas de reserva o contratación y sus cobros son operaciones separadas según 2.5.
- Anular o finalizar una actividad coordina el bloqueo de turno y evento con las demás operaciones sobre esa ocupación.

Las comprobaciones que dependen de varias filas se realizan en los servicios de escritura, dentro de esas transacciones. La base complementa esa coordinación con las claves y restricciones definidas en el modelo relacional.

La aplicación conserva la historia de usuarios, instalaciones, productos, contrataciones, actividades, sesiones de caja y movimientos. No ofrece eliminación física de clases, sean manuales o generadas desde la planilla; su anulación conserva sus datos y libera el turno antes de su inicio. Quitar celdas de la planilla viva elimina esas celdas y sus asignaciones previstas, sin modificar las clases concretas. Las operaciones de configuración permiten quitar feriados, horarios de funcionamiento y vínculos de roles conforme a sus reglas específicas.

### 2.13 Procesos automáticos de finalización y vencimiento

Celery Beat ejecuta la finalización de clases y reservas cada hora en punto de Salta. Selecciona eventos Programados cuyo turno terminó antes o en el momento de la ejecución. Para cada uno coordina turno y evento, vuelve a comprobar las condiciones y guarda Finalizado con el momento real de procesamiento. No modifica asistencias, respuestas ni resultado de uso de reservas, ni sobrescribe eventos Anulados o Finalizados. Los bloqueos quedan fuera de esta tarea.

La finalización automática de una clase no tiene responsable manual. Una finalización manual registra al administrador o profesor autorizado; las reservas no registran responsable de finalización, tampoco en la acción administrativa de emergencia. Cada ejecución recupera todas las clases y reservas pendientes, incluidas las que terminaron durante una interrupción de los servicios.

El vencimiento diario se ejecuta a las 00:05 de Salta y procesa las contrataciones Activas de planes y membresías cuyo mes terminó, cambia su estado a Vencido y actualiza su fecha de modificación. No altera contrataciones Anuladas, ingresos ni relaciones históricas. Repetir la tarea no cambia los registros ya procesados. Los avisos de vencimiento y los recordatorios de clases se definen en 2.6.


### 2.14 Historial de auditoría

`log_auditoria` conserva las modificaciones funcionales y anulaciones de registros de negocio. También registra las eliminaciones permitidas de relaciones, como retirar un rol o quitar un horario, porque modifican la configuración existente. El alcance del hito comprende modificaciones y anulaciones; las altas no generan entradas. La captura se realiza en PostgreSQL mediante una función común y un trigger de fila `AFTER UPDATE OR DELETE` en cada tabla auditada. Las sesiones técnicas de autenticación, permisos técnicos y migraciones de preparación quedan fuera del historial de negocio. `sesiones_caja` y `movimientos_fondos` sí participan: los cierres y anulaciones se auditan con el mecanismo común, sin agregar auditoría de altas. La auditoría registra los cambios de caja; la protección de datos de caja se valida en los servicios según 2.5.

Cada entrada identifica tabla, clave simple o compuesta en JSON, acción, valores anteriores y actuales, fecha y hora con zona horaria, usuario de la aplicación cuando corresponde, cuenta de PostgreSQL y origen. En modificaciones y anulaciones sólo se guardan los campos que cambiaron. En las eliminaciones permitidas se conserva el registro anterior y un objeto vacío como valor actual. Las instantáneas usan JSON nativo de PostgreSQL; fechas y horas conservan su representación ISO y los importes se representan como números. La marca `actualizado_en` aislada no genera una modificación funcional. Las consultas, vistas previas y preparación de nuevos turnos no generan entradas por sí mismas.

El trigger obtiene los valores directamente de `OLD` y `NEW`. Reconoce como anulación la transición de un estado a Anulado y el registro del origen de anulación en una reserva. Las contraseñas y sus hashes se excluyen de las instantáneas. Cambio de contraseña es una acción específica: Django comunica la intención de la operación y el trigger verifica que el valor almacenado cambió. La cuenta afectada se identifica por la clave del registro y el responsable por el usuario del log. Sólo se conservan diferencias de campos reales no sensibles, como `debe_cambiar_contrasena`; la marca temporal auxiliar se omite en estos eventos. Si no cambió otro campo relevante, los valores anteriores y actuales son objetos vacíos. No se generan indicadores artificiales ni valores enmascarados de la contraseña. El guardado de la contraseña y de su obligación de cambio forma una sola actualización y produce una entrada. La actualización automática del hash al verificar credenciales se registra como Actualización de hash, sin confundirla con la elección de una contraseña nueva. El contexto de verificación identifica esta operación técnica; un cambio confirmado utiliza su propia intención. Una modificación de la credencial por SQL sin una intención informada se registra como Cambio de contraseña, sin atribuirle un restablecimiento administrativo. Una intención sin cambio efectivo no genera un evento de contraseña. La fecha del último acceso se audita cuando cambia `last_login`.

Django comunica actor, origen, identificador UUID y, cuando corresponde, la acción específica mediante configuración local a la transacción, obtenidos del servidor y no de campos editables. El middleware establece el contexto de las solicitudes; la autenticación y la finalización resuelven sus actores específicos. La función de contexto sólo comunica esos datos y delimita la transacción: no captura ni inserta entradas. Los contextos anidados comparten el UUID y restauran el contexto superior al terminar. La configuración no se reutiliza para otra solicitud. Las respuestas de error HTTP revierten la transacción de la solicitud.

Los orígenes admitidos son `aplicacion`, `tarea` y `sql`. Las modificaciones desde la aplicación exigen un usuario. Durante la autenticación se comunica ese propósito al trigger, que identifica al titular desde la cuenta que se está guardando. La finalización automática utiliza origen `tarea` sin usuario; la acción de emergencia identifica al administrador en el log, sin agregar un responsable de finalización al evento. El autorregistro, las altas administrativas y el comando de creación de administradores no requieren un contexto especial de auditoría porque sus inserciones no se registran.

Una escritura SQL sin contexto se registra con origen `sql`, sin usuario web y con `session_user` como cuenta de base de datos. Las escrituras de una misma transacción SQL comparten un UUID generado por la base. Los triggers cubren también operaciones masivas y escrituras directas `UPDATE` y `DELETE`. Cada nueva tabla de negocio incorpora su trigger mediante una migración, declarando los componentes de su clave primaria. El contexto comunicado por la aplicación pertenece a la conexión confiable del servidor; no constituye una autenticación independiente del usuario dentro de PostgreSQL.

Las entradas forman parte de la misma transacción que la escritura auditada. Un error al insertar el log impide confirmar el cambio; un rollback elimina también sus entradas. Anular y bloquear y las operaciones masivas conservan un UUID común para sus modificaciones y anulaciones, sin agrupar los estados de los eventos. No se audita el propio log ni se infieren acciones históricas a partir de los datos existentes.

Los campos de creación, modificación, responsables, fecha de baja, motivos y fechas de anulación o finalización se conservan en sus entidades. Describen el registro vigente, sostienen las restricciones de coherencia y permiten consultas y comprobantes directos. El log conserva la secuencia de cambios y no reemplaza esos campos.

El identificador de actor en Auditoría se conserva aunque una cuenta inicial sin verificar se elimine. La consulta muestra Cuenta eliminada con su identificador y sin enlace cuando ya no existe; no lo atribuye a SQL ni a una persona distinta. Las referencias comerciales conservan sus protecciones.

El historial es inmutable: un trigger rechaza `UPDATE`, `DELETE` y `TRUNCATE` sobre `log_auditoria`. La web no permite escribir en él. Auditoría es exclusiva de administradores activos con acceso vigente, sólo admite GET y presenta cambios sin entradas de alta. Muestra veinticinco entradas por página en filas compactas, en orden descendente de fecha e identificador. La tabla presenta encabezados para Fecha y hora, Responsable, Acción, Tipo de registro, Registro afectado y Detalle. Cada fila identifica el tipo con una etiqueta funcional y el registro afectado con una única referencia breve, sin JSON en el resumen. La referencia enlaza a la consulta del registro vigente cuando está disponible. El botón Ver cambios despliega la tabla técnica, la clave JSON, el origen, el usuario de aplicación, el usuario de PostgreSQL, el UUID y los valores anteriores y actuales. Los eventos de cambio y restablecimiento de contraseña ocultan los bloques de valores anteriores y actuales, aunque el historial conserva las diferencias no sensibles. El resumen identifica al usuario de aplicación, a un Proceso automático cuando el origen es una tarea o al usuario de PostgreSQL cuando la escritura proviene de SQL. El detalle muestra Usuario de aplicación únicamente para el origen Aplicación. La cuenta de PostgreSQL identifica la conexión, sin atribuirle una identidad humana. Los datos se muestran escapados y consultar no modifica el historial.


La columna Acción distingue las modificaciones mediante los valores anteriores y actuales de la entrada:

| Etiqueta | Condición |
| --- | --- |
| Inicio de sesión | Modificación de `usuarios` con origen Aplicación y responsable igual a la cuenta afectada. El único campo modificado es `last_login`, sin contar `actualizado_en`, y su valor actual está informado. |
| Finalización | Cambio de `eventos.estado` de Programado a Finalizado, tanto en operaciones manuales como automáticas. |
| Activación | Cambio de `usuarios.is_active` de falso a verdadero, de `sedes.estado` o `canchas.estado` de Inactiva a Activa, o de `planes.estado` o `membresias.estado` de Inactivo a Activo. |
| Desactivación | Cambio inverso a la activación en esas mismas tablas y campos. |

Estas etiquetas se determinan al consultar, sin modificar la acción almacenada ni las diferencias del log. Se exige la transición entre los valores indicados; una edición de otros datos o un estado sin cambio conserva Modificación. Finalización, Activación y Desactivación se reconocen para todos los orígenes, incluido SQL. Inicio de sesión se limita a los accesos desde la aplicación. Anulación, Eliminación y las acciones de contraseña conservan sus etiquetas específicas. Las asignaciones de personas y las contrataciones tienen sus propias reglas de estado y no se clasifican como activaciones o desactivaciones de cuentas, instalaciones o productos.

Las referencias del historial se presentan según el tipo de registro:

| Tipo | Referencia breve |
| --- | --- |
| Usuario y rol | Nombre del usuario o del rol. |
| Rol de usuario | Usuario y rol asignado o retirado. |
| Sede y cancha | Nombre de la sede; para una cancha, su nombre y sede. |
| Horario de sede | Sede y nombre del día de la semana. |
| Turno | Número de turno. |
| Evento | Número de la clase o código de la reserva o bloqueo asociado. Si la actividad no está disponible, tipo de actividad y número de evento. |
| Reserva | Código de reserva. |
| Bloqueo y clase | Código de bloqueo o número de clase. |
| Feriado | Fecha. |
| Turno de planilla | Número de turno de planilla. |
| Profesor o alumno de planilla | Persona y número del turno de planilla. |
| Profesor o alumno de clase y asistencia | Persona y número de clase. |
| Plan y membresía de socio | Nombre del producto. |
| Contratación de plan o membresía | Titular y mes cubierto. |
| Ajuste de horas de membresía | Titular, mes cubierto y tipo de horas. |

Las referencias de las entradas de eliminación se presentan en cursiva.

El resumen muestra una única referencia breve, sin repetir los identificadores en una línea secundaria. Los nombres identifican personas, instalaciones y productos; los códigos o números identifican actividades y turnos. La información completa del registro se consulta desde el enlace de esa referencia. El detalle desplegable concentra las claves, los datos de la operación y las diferencias auditadas, sin repetir una descripción ampliada del registro.

Usuarios, sedes, clases, reservas, bloqueos, feriados, turnos de planilla, productos y contrataciones enlazan a sus fichas. Las canchas y los horarios enlazan a la sección correspondiente de la sede; los vínculos de roles, al perfil del usuario; las asignaciones y asistencias, a su clase o turno de planilla; los turnos, a su selección en Agenda. Los eventos enlazan a su clase, reserva o bloqueo asociado. Las entradas de eliminación, los registros o destinos que ya no están disponibles y los tipos sin pantalla de consulta, como el catálogo de roles, muestran la referencia como texto. Las rutas se construyen al consultar a partir de los registros vigentes, respetan los permisos de las pantallas de destino y no se almacenan en el log.

La referencia de un registro disponible describe su identidad vigente y enlaza a su consulta. Las entradas de eliminación utilizan únicamente los valores anteriores conservados y las claves, sin consultar nombres relacionados actuales. Si falta información suficiente se muestra el tipo y el identificador o los componentes etiquetados de la clave. No se reconstruyen objetos combinando diferencias históricas con campos vigentes. La referencia permite identificar y navegar; la evidencia histórica permanece en los valores anteriores y actuales del detalle. Un catálogo central define el modelo, nombre funcional, relaciones necesarias y ruta de consulta de cada tipo. La consulta carga registros y relaciones en grupos por tipo dentro de la página, sin modificar el log.

#### Intentos rechazados

Auditoría ofrece dos consultas: Cambios realizados e Intentos rechazados. Ambas exigen un administrador activo y sin cambio de contraseña pendiente, admiten sólo GET y presentan veinticinco entradas por página en orden descendente de fecha e identificador. Los intentos se almacenan en `intentos_auditoria`, separados de las escrituras confirmadas de `log_auditoria`.

El alcance de intentos comprende exclusivamente:

| Intento | Condición de captura | Motivos |
| --- | --- | --- |
| Inicio de sesión fallido | La validación de autenticación rechaza las credenciales. | Credenciales incorrectas o cuenta inactiva. |
| Cambio de contraseña rechazado | La validación rechaza la contraseña actual ingresada. | Contraseña actual incorrecta. |
| Acceso denegado | La autorización rechaza el acceso a una consulta o acción de usuarios, instalaciones, clases, reservas, agenda, membresías o auditoría. | Permisos insuficientes o registro ajeno. |

Los motivos son códigos de catálogo, no textos extraídos de errores ni de formularios. Una respuesta 403 por `PermissionDenied` identifica el rechazo de autorización en los módulos indicados. En las consultas privadas de reservas, comprobantes y contrataciones, una respuesta 404 se registra sólo si se comprueba que el registro solicitado existe y pertenece a otra cuenta; la respuesta al solicitante conserva el 404. Los demás 404 no generan intentos. No se registran errores comunes de formato, campos vacíos, contraseñas nuevas débiles, errores CSRF, cancelaciones, redirecciones normales al login ni rechazos de reglas de negocio.

Cada intento conserva UUID de solicitud, fecha y hora, tipo, motivo, usuario autenticado opcional, identificador ingresado opcional, nombre de vista, método HTTP y parámetros permitidos del destino. El UUID coincide con el contexto de auditoría de la solicitud y es único en esta tabla. Un login fallido no se atribuye a la cuenta cuyo nombre se ingresó: el responsable se presenta como No autenticado y el identificador ingresado aparece en el destino. Los otros intentos no guardan un identificador de login. Los parámetros se limitan a identificadores numéricos de ruta y códigos de roles conocidos; no se almacena la URL completa ni su query string. No se conservan contraseñas, hashes, formularios, cookies, tokens, IP ni encabezados de solicitud.

La detección conserva como máximo un intento por solicitud y lo inserta en una transacción independiente al salir del contexto de negocio, incluso si la operación se revierte. El registro de intentos no utiliza `on_commit`, porque también debe ejecutarse tras un rollback. Si la persistencia falla, se emite un error técnico con el UUID, sin contenido de la solicitud, y se conserva la respuesta original. Una terminación abrupta del proceso antes de insertar el intento puede impedir su persistencia. Los intentos no se generan para tareas automáticas ni para escrituras SQL directas.

La tabla de intentos es inmutable: PostgreSQL rechaza UPDATE, DELETE y TRUNCATE. Su consulta muestra Fecha y hora, Responsable, Intento, Destino, Motivo y Detalle. Ver datos despliega UUID de solicitud, vista, método e identificadores permitidos del destino, sin enlaces que ejecuten la acción rechazada. No existe edición, borrado ni registro manual desde la web.

### 2.15 Contratación administrativa y continuidad

#### 2.15.1 Contrataciones

Administración registra todas las altas, renovaciones y cambios de producto. El portal permite consultar catálogo, contratos propios, comprobantes, importes, movimientos y beneficios autorizados; no registra contrataciones ni renovaciones por URL, formulario o servicio de titular. El mes siguiente se habilita para administración desde el día 25 inclusive de Salta. Se conservan precios mensuales aplicados, validación de productos Activos, exclusividad de un contrato no Anulado por titular, tipo y mes, y restricciones de roles. Los cobros y la asignación de horarios se registran por sus propios recorridos.

La confirmación administrativa guarda en la misma transacción un aviso al titular, con producto, período e importe aplicado, sin acreditar pago. El acceso lleva al detalle propio con autenticación. Si su encuesta está abierta, el mismo mensaje informa el plazo y acceso; no agrega otro aviso de apertura. La respuesta de continuidad no envía emails a administración.

#### 2.15.2 Encuesta por contratación

Cada contrato mensual de plan o membresía tiene su propia respuesta: `continuar`, `cambiar`, `indeciso` o `no_continuar`. Sin responder se representa con respuesta vacía y fecha nula; no es una opción seleccionable ni puede restaurarse mediante una entrada manipulada. Indeciso es una respuesta. Si la persona tiene ambos tipos de contrato, puede responder distinto en cada uno.

La ventana abre el 25 del mes cubierto a las 00:00 y cierra el 6 del siguiente a las 00:00, extremo final excluido, en America/Argentina/Salta. La encuesta de noviembre pregunta por diciembre. El titular activo, verificado y sin provisoria pendiente puede responder y cambiar su respuesta durante esa ventana. Vencido no impide responder del 1 al 5. Anulado lo impide; las respuestas anteriores permanecen consultables. Administración consulta, pero no responde por otra persona ni por una cuenta administrativa propia.

Se conserva la última respuesta y su fecha bajo bloqueo de titular y contratación, con auditoría de diferencias. La misma respuesta no reescribe fechas ni genera efectos adicionales. El estado y la ventana se comprueban al confirmar. El detalle presenta respuesta o Sin responder primero; el formulario sólo se abre mediante Responder o Cambiar respuesta. Después del cierre, sólo se consulta.

La encuesta informa intención: no acredita contratación ni pago, no crea, renueva o anula contratos, no cambia productos, roles, horarios o planilla, no retira personas, no cancela actividades y no genera movimientos. Tener otra contratación para el mes siguiente no completa la respuesta. El silencio no significa baja ni indecisión.

#### 2.15.3 Consulta administrativa

La lista general de continuidad se filtra por mes cubierto, tipo de producto y respuesta, incluido Sin responder. Muestra titular, producto, mes, estado, respuesta y fecha, con enlace al contrato. Incluye planes y membresías sin depender de que sus titulares aparezcan en una planilla. Las contrataciones Anuladas permiten consultar sus respuestas conservadas.

El seguimiento de la plantilla semanal conserva su consulta comercial por cancha y mes, los horarios previstos, contratos y casos Sin contratación. Muestra la respuesta del contrato de ese mes y enlaza a la lista general. Sin contratación no supone baja, indecisión, deuda o falta de pago. Las participaciones de prueba y acuerdos fuera de un plan conservan sus recorridos; las modificaciones de plantilla requieren su operación propia.

Los avisos de encuesta son el 25, último día del mes y 5 siguiente, a las 09:00 de Salta; los dos recordatorios incluyen sólo encuestas sin respuesta. Se agrupan por persona y fecha y se comprueba apertura, estado, cuenta habilitada y verificación antes de entregar. Los enlaces llevan al detalle con autenticación y no guardan respuestas al abrirlos. Las reglas de campañas se desarrollan en su proceso de origen.
