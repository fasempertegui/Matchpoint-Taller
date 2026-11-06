# Avance del proyecto

## Academia de Tenis TM

La aplicación administra una academia de tenis mediante Python, Django y PostgreSQL, con ejecución en Docker Compose. El sistema completo contempla instalaciones, usuarios, clases, asistencia, membresías, reservas e ingresos.

## 1. Hito 1: sedes y canchas

Se dispone de alta, consulta, modificación, activación y desactivación de sedes y canchas. La baja es lógica y conserva los registros.

Desactivar una sede o cancha se rechaza si tiene una reserva, clase o bloqueo no Anulado cuyo turno esté en curso. Si no hay actividades en curso, se revisan las reservas, clases y bloqueos Programados con inicio futuro. Confirmar anula esas actividades con un motivo común y desactiva la instalación en una única transacción, con bloqueos y revalidación de la selección. Los turnos terminados no impiden desactivar y conservan su historia y finalización pendiente. Reactivar no restaura las actividades Anuladas ni modifica el estado de las canchas de una sede. Editar los datos no cambia el estado.

Cada cancha pertenece a una sede y tiene nombre, superficie y observaciones opcionales. No se permiten nombres de sedes duplicados ni nombres de canchas repetidos dentro de una sede, sin distinguir mayúsculas y minúsculas.

## 2. Hito 2: usuarios y seguridad

Se permite registrar usuarios desde la administración y mediante autorregistro, consultarlos, buscarlos, modificar su correo y activar o desactivar sus cuentas. También se puede consultar el perfil propio y restablecer administrativamente una contraseña.

El nombre de usuario se genera a partir del apellido y la inicial del nombre, agregando un número si es necesario. Se exige fecha de nacimiento, nombres y apellidos sin números, correo válido y único, y celular móvil argentino válido.

La autenticación incluye inicio y cierre de sesión y cambio de contraseña. Las contraseñas se almacenan mediante hash. Las cuentas creadas por otra persona o con contraseña restablecida deben reemplazar la contraseña provisoria antes de operar; la nueva debe ser diferente de la vigente.

Los roles son Administrador, Profesor, Alumno, Reservas y Público. Las cuentas no administrativas reciben Público y Reservas al crearse; la administración puede asignarles y retirarles Profesor, Alumno y Reservas. Las cuentas administrativas tienen únicamente Administrador, asignado mediante el comando de creación, y no admiten roles adicionales.

La gestión de roles envía explícitamente la acción Asignar o Quitar y la valida con el usuario bloqueado dentro de una transacción. Asignar un rol vigente o quitar uno ausente conserva el estado sin generar cambios ni auditoría. Cada retiro efectivo comprueba las relaciones que lo impiden y cada asignación respeta las incompatibilidades de roles.

Desactivar registra fecha y hora de baja; reactivar elimina esa marca. No se permite desactivar la cuenta propia ni al último administrador activo.

## 3. Hito 3: proceso de reservas

### Horarios y precios

El Administrador puede configurar hasta dos franjas de funcionamiento por día para cada sede. Los horarios deben ser en punto, los intervalos deben estar completos y terminar después de comenzar. Si hay dos franjas, debe existir al menos una hora sin funcionamiento entre ellas. Estas condiciones se validan en el formulario y en la base de datos. Un día sin franjas no tiene disponibilidad. Configurar o quitar franjas se rechaza si deja fuera una reserva, clase o bloqueo Programado cuyo turno no terminó. Se informa la primera actividad afectada y no se aplica ningún cambio. La sede se bloquea para coordinar esta comprobación con el registro de actividades.

Cada sede guarda una tarifa vigente, positiva y común a todas sus canchas, por turno de una hora. El Administrador puede configurarla o actualizarla. Guardar modifica el valor de la sede dentro de una transacción; se rechazan importes iguales al actual y cambios concurrentes que requieren revisar nuevamente el precio.

### Turno y evento

El proceso utiliza Turno, Evento y Reserva. Turno identifica una hora de una cancha en una fecha; su fin se calcula sumando una hora al inicio. Evento referencia directamente un único turno y concentra estado, observaciones y auditoría. Reserva referencia un único evento y guarda organizador, precio por turno aplicado y origen de la anulación.

La base de datos impide duplicar turnos para una cancha, fecha y hora. Una restricción única parcial sobre el turno del evento impide que dos eventos no Anulados ocupen el mismo turno y permite conservar varios eventos Anulados históricos. Exige inicios en punto entre las 00:00 y las 22:00; la duración fija de una hora determina el fin dentro de la misma fecha. Las relaciones protegen los registros vinculados contra la eliminación física.

Los estados del evento son Programado, Anulado y Finalizado, con auditoría coherente para cada caso. La ocupación común integra reservas, clases y bloqueos. Todas las altas de eventos exigen inicio estrictamente futuro, incluidos los turnos del día actual, y fecha hasta el último día del segundo mes calendario siguiente al actual. El límite se valida tanto en las altas individuales como en la generación masiva y las operaciones que crean bloqueos. La validación común del modelo protege las altas individuales; la generación masiva valida antes de insertar y antes de completar la transacción. La generación utiliza un selector de mes completo, con el mes actual seleccionado por defecto. Admite los días pasados incluidos en el mes e informa sus turnos y los de hoy ya iniciados como omitidos. Volver a generar conserva las clases existentes y sólo crea clases en turnos futuros disponibles. El registro crea el evento con su turno y la reserva en una única transacción.

### Disponibilidad

Se preparan y consultan turnos para una cancha y fecha entre hoy y catorce días después, inclusive. La sede y la cancha deben estar activas, y la sede debe tener una tarifa vigente configurada.

Los turnos faltantes se generan dentro de una transacción, según las franjas actuales de funcionamiento. Sólo se ofrecen turnos futuros y libres. Preparar turnos no registra una reserva ni ocupa horarios.

Los eventos Programados y Finalizados ocupan sus turnos; los Anulados los liberan. La disponibilidad consulta esa relación común y conserva las referencias históricas al turno. Los turnos existentes fuera de los horarios actuales se conservan, pero no se ofrecen.

### Registro

El Administrador puede registrar una reserva para un organizador activo con rol Reservas o Administrador. La selección y la confirmación validan esas condiciones; registrar una reserva no asigna roles automáticamente. El usuario con rol Reservas sólo puede reservar para sí mismo. Los datos relacionados se seleccionan entre las opciones disponibles, sin ingresar claves foráneas manualmente.

Cada reserva ocupa un único turno de una hora, contenido en una franja de funcionamiento. El formulario permite seleccionar sólo un turno y el servidor rechaza el envío de varios valores. El total corresponde a la tarifa vigente de la sede para una hora. Reservar varias horas exige registrar reservas independientes.

El servidor valida permisos, selección, estados, horarios, precio y disponibilidad dentro de una transacción, con bloqueos para coordinar solicitudes simultáneas. Registra la reserva y su evento Programado con referencia al turno, número, fecha y usuario responsable automáticos. Ante un error, no queda una reserva parcial. Si cambia el precio antes del registro, se exige revisar el importe y confirmar nuevamente.

Cada organizador puede tener como máximo cinco reservas en estado Programado, sumando todas las sedes y fechas. El límite se comprueba al confirmar, con el organizador bloqueado dentro de la transacción, tanto en el portal como en los registros administrativos, incluidas las reservas de cuentas administrativas. Los turnos terminados siguen contando mientras su evento permanezca Programado; las reservas Anuladas y Finalizadas no consumen cupo.

El importe por turno se copia desde la tarifa validada de la sede al registrar y se conserva en la reserva. El total es ese importe aplicado; actualizar la tarifa no modifica reservas existentes. No se permite retirar el rol Reservas a un usuario con reservas propias Programadas.

### Consulta

El Administrador consulta las reservas desde Agenda; el usuario con rol Reservas puede consultar el detalle y comprobante de las propias. El panel del turno ofrece enlaces a ambas pantallas. El detalle incluye organizador, sede, cancha, fecha, horario, precio aplicado, estado, observaciones y los datos de registro, anulación o finalización que corresponden. Las rutas de detalle y comprobante comprueban el acceso al registro en el servidor.

La búsqueda por criterios desde Agenda está pendiente. Las reservas Anuladas se localizan desde el historial de su turno. No hay una sección independiente de Reservas ni un formulario de alta separado.

### Anulación

El Administrador puede anular cualquier reserva Programada antes de que comience su turno. El usuario con rol Reservas puede anular únicamente las propias con al menos una hora de antelación al turno. El motivo es obligatorio y debe tener al menos 25 caracteres, sin contar los espacios al principio y al final. El formulario y el procesamiento de la anulación validan ese mínimo.

La operación cambia el evento a Anulado, registra motivo, fecha, hora y responsable, y libera su turno. Guarda en la reserva si la anulación corresponde al organizador o a la administración. Conserva reserva, evento, referencia al turno e importe aplicado. Se ejecuta en una única transacción, validando nuevamente permisos, estado y horario después de obtener los bloqueos.

Se rechazan reservas iniciadas, Anuladas o Finalizadas, solicitudes sobre reservas ajenas desde el portal y anulaciones propias fuera del plazo. Una solicitud repetida no sobrescribe la auditoría. El actor debe conservar el acceso habilitado; el Administrador puede operar aunque el organizador esté inactivo. No se exige que las instalaciones o el precio sigan activos. Ante un error, no se modifica la reserva ni su ocupación.

### Finalización

Celery finaliza automáticamente las reservas Programadas cada hora en punto cuando la fecha y hora de fin de su turno es igual o anterior al momento actual. El Administrador también puede finalizar una reserva vencida como acción de emergencia, con las mismas condiciones y sin depender de Celery ni Redis.

Cada reserva se procesa en una transacción, comprobando nuevamente el estado y horario después de bloquear el turno y el evento. Registra estado Finalizado, fecha y hora de procesamiento en el evento, sin responsable. Conserva la referencia al turno, el precio y la ocupación histórica, aunque los registros relacionados estén inactivos. No modifica reservas que no terminaron, Anuladas o Finalizadas, ni sobrescribe datos ante ejecuciones repetidas. La siguiente ejecución procesa todas las vencidas que sigan pendientes.

### Comprobante

Se dispone de un comprobante imprimible o guardable como PDF con número, estado, organizador, responsable, fecha de registro, sede, cancha, fecha de uso, duración fija de una hora, precio aplicado y total. Incluye observaciones y datos de anulación o finalización cuando corresponden.

El Administrador puede emitir cualquier comprobante y el usuario con rol Reservas sólo los propios. Emitirlo no modifica la reserva ni crea registros adicionales. Acredita el registro de la reserva, no un pago.

## 4. Agenda

Las celdas con anulaciones accesibles muestran un chip neutro con un ícono de círculo tachado y la cantidad de eventos accesibles. Se ubica en la esquina inferior derecha, separado del enlace que abre el turno. Abre una consulta emergente anclada en escritorio y un panel inferior en móvil, con una lista de sólo lectura ordenada por anulación más reciente. Cada tarjeta reutiliza el fondo de su tipo de evento en Agenda y muestra una flecha hacia su detalle. Toda la tarjeta funciona como enlace: reservas y clases utilizan sus pantallas de detalle y los bloqueos tienen un detalle de sólo lectura exclusivo de administración. Destaca el tipo sobre el organizador de la reserva o el motivo clasificado del bloqueo, que se presenta como información secundaria. No incluye motivo de anulación, separadores, barra lateral, íconos ni tachado. No muestra cabecera, identificadores internos ni datos de responsable o momento de anulación. Se cierra con Escape o con clic fuera y devuelve el foco al chip. La administración ve todas las anulaciones; el portal sólo sus reservas y las clases vinculadas a su cuenta. El servidor aplica este filtro también a las consultas directas. Las filas con historial accesible permanecen visibles en fechas pasadas y fuera del horario actual, aunque el turno esté libre. El clic habitual en la celda conserva la consulta de su estado actual.

La sección Agenda permite consultar una sede por día, con una columna por cancha. La barra de controles identifica Sede, Vista y Fecha, con controles de 44 px de alto. Día y Semana forman un selector segmentado con Día activo y Semana deshabilitado. Las flechas de día anterior y siguiente se agrupan con el campo de fecha dentro de un borde común; Hoy se presenta separado como botón de fondo suave. Los controles se distribuyen en varias líneas según el ancho disponible. El acceso está habilitado para cuentas activas con rol Administrador o Reservas y sin cambio de contraseña pendiente.

La consulta incluye instalaciones inactivas para acceder a su historia, representa los espacios libres desde los horarios de la sede y conserva los eventos existentes fuera de las franjas actuales. No registra turnos ni eventos por consultar. Sin canchas, horarios o actividades muestra los estados vacíos correspondientes. Las fechas inválidas y las canchas de otra sede se rechazan. Los límites de consulta son el inicio de operaciones y un año calendario después del día actual.

Seleccionar una celda muestra su fecha, cancha y horario. El detalle acompaña a la grilla diaria en un panel lateral y se ubica debajo en pantallas pequeñas. Seleccionar un turno o cerrar su panel no recarga la grilla ni cambia el desplazamiento: el servidor entrega el detalle autorizado y se actualizan el panel, el resaltado y la URL de selección. Ante errores se conserva el detalle anterior con un aviso; las selecciones rápidas sólo muestran la última respuesta. El registro, la anulación y la finalización mantienen sus envíos y redirecciones completos. Para reservas incluye organizador, estado junto al identificador, observaciones y acceso al detalle completo. El aviso de carga aparece únicamente cuando la consulta tarda más de 300 ms. Las reservas Anuladas conservan sus datos y no ocupan celdas; su localización por criterios está pendiente. Los turnos iniciados se atenúan; Ahora destaca únicamente la hora en el margen y se actualiza con la zona horaria del sistema.

Un turno libre permite registrar una reserva para un organizador habilitado desde el panel, con confirmación de participante, horario e importe. Se respetan precio, franjas, instalaciones activas y anticipación de catorce días. Una reserva futura permite anular y liberar con motivo; una vencida pendiente de finalización ofrece la acción administrativa de emergencia. Estas acciones reutilizan los servicios transaccionales de reservas. Si cambia el precio se exige revisar el importe; si cambia la reserva que ocupa el turno, la confirmación no se aplica a la actividad nueva.

Las clases y la planilla registran profesores, participantes y observaciones; sus formularios, consultas y generación utilizan esos datos. La creación y edición de horarios de planilla exigen al menos un profesor activo con rol Profesor, con validación compartida en formulario y servicios. La modalidad pertenece al catálogo de planes. La agenda integra reservas, clases y bloqueos. En el portal, la consulta de vínculos de clases reúne los eventos del usuario para la fecha seleccionada mediante profesores, participantes y asistencias, por separado de la carga de eventos de la grilla y su historial. La administración consulta todas las actividades sin calcular esos vínculos. Permite consultar sus detalles, ejecutar las acciones individuales autorizadas y realizar operaciones masivas de anulación y bloqueo con exclusiones por tipo de evento.

Los turnos vacíos cuyo horario ya terminó no ofrecen acciones sobre su estado actual; si tienen anulaciones accesibles, conservan el chip de anulados para consultar su historial. Los eventos finalizados conservan acceso a su detalle histórico.

## 5. Bloqueos individuales

El Administrador puede crear un bloqueo sobre un turno futuro de una sede y cancha activas, hasta el último día del segundo mes calendario siguiente al actual. El motivo es Clima adverso, Torneo o Mantenimiento y se admiten observaciones opcionales. No exige tarifa, pero el turno debe quedar íntegramente dentro de una franja de funcionamiento de la sede. El servidor comprueba el horario dentro de la transacción y la agenda no ofrece crear bloqueos fuera de las franjas.

Cada bloqueo tiene un identificador B, su evento Programado y un único turno. El campo opcional y único `evento_origen` guarda la reserva o clase anulada que originó el bloqueo; queda vacío al bloquear un turno libre y conserva la referencia histórica al liberar el bloqueo. La grilla lo distingue de las reservas y muestra su motivo. El panel incluye identificador, estado registrado, motivo, responsable y momento del registro, observaciones y reserva de origen cuando corresponde. Los bloqueos iniciados o terminados se consultan sin acciones. La tarea horaria finaliza los Programados cuyo turno terminó y registra `finalizado_en` con el momento de procesamiento.

Anular y bloquear sobre una reserva futura exige el motivo de anulación de al menos 25 caracteres y el motivo del bloqueo. La confirmación identifica la reserva, su organizador y el turno. Dentro de una única transacción comprueba el acceso administrativo, las instalaciones activas, el horario de funcionamiento, el inicio futuro y la ocupación confirmada; anula la reserva, comprueba el turno libre y registra el bloqueo con su origen. Un fallo revierte también la anulación. Si la actividad cambió, exige revisar la selección y no anula la actividad nueva.

Anular y liberar un bloqueo exige motivo en texto libre y un inicio futuro. Conserva el bloqueo, su evento, el turno y el origen, y registra responsable, momento y motivo de anulación. No reactiva la reserva de origen. La operación no exige que la instalación permanezca activa. Se rechazan acciones repetidas, bloqueos iniciados y referencias a un bloqueo distinto del turno seleccionado.

Las operaciones se realizan desde el panel de Agenda, sin una sección independiente de bloqueos. Crear reserva y Crear bloqueo utilizan botones de contorno para desplegar los formularios, separados por una línea; Confirmar reserva y Confirmar bloqueo utilizan fondo violeta para destacar el envío de la operación. Sólo una acción del panel puede estar desplegada a la vez, por lo que abrir una cierra la anterior sin borrar los datos ingresados. Reutilizan la exclusión de ocupación del evento, bloquean el turno antes del evento y vuelven a validar permisos y límites horarios dentro de la transacción. Los bloqueos tienen una tarea horaria de finalización automática.

## 6. Acciones del día

La tarjeta del título de Agenda ofrece Acciones del día para la sede y fecha consultadas, desde hoy hasta un año después. Abre el mismo panel lateral utilizado por el detalle de turnos; la grilla permanece visible. Abrir, cerrar, revisar y volver a editar actualizan sólo el panel, sin desplazar la página. Seleccionar un turno reemplaza el contenido por su detalle. En pantallas pequeñas el panel se ubica debajo de la grilla. Permite seleccionar una o varias canchas y operar sobre el día completo o desde una hora de corte inclusiva. Sólo se actúa sobre turnos cuyo inicio sigue siendo futuro al confirmar. Un corte a las 18:30 incluye los turnos de las 19:00 en adelante.

Anular y liberar anula reservas, clases y bloqueos elegibles, con opción de excluir cada tipo; los turnos libres no requieren acción. Admite instalaciones inactivas y conserva la historia. Anular y bloquear exige sede y canchas activas y turnos íntegramente contenidos en las franjas de funcionamiento: anula las reservas y clases incluidas y crea un bloqueo independiente para cada turno efectivo, incluidos los libres. Permite excluir reservas y clases y conserva los bloqueos existentes como ya cubiertos. Cada bloqueo que nace de una anulación registra su reserva o clase de origen. Los turnos iniciados y eventos Finalizados se conservan; los eventos Anulados no ocupan turnos ni se procesan nuevamente.

El formulario recoge alcance, exclusiones y motivo. Anular y liberar exige un motivo libre si se anulan eventos y un mínimo de 25 caracteres si incluye reservas. Anular y bloquear pide únicamente el motivo clasificado del bloqueo, cuyo nombre se guarda también como motivo de anulación de las reservas y clases afectadas; admite observaciones comunes opcionales. La vista previa no escribe turnos ni eventos. Presenta las cantidades y los listados desplegables de acciones y eventos conservados con su motivo. El formulario compacto utiliza listas desplegables para operación, canchas y horario. Canchas ofrece Todas las canchas de la sede y Seleccionar; la segunda opción permite marcar una o varias canchas. Horario ofrece Día completo y Desde las HH:00 para cada inicio habilitado de la fecha consultada que aún sea futuro; no ofrece turnos iniciados ni horas fuera de las franjas. La lista se calcula con el día de la semana y la hora local actual y se valida nuevamente al enviar. Si se elige un inicio, Hasta ofrece un fin opcional: sólo horas de finalización de turnos habilitados posteriores al inicio, incluida la hora de cierre. Las pausas entre franjas no agregan opciones. Sin fin indicado abarca el resto del día; con fin indicado sólo incluye turnos completos anteriores a ese límite. La vista previa, la edición y la confirmación conservan y validan ese intervalo. Permite volver a editar conservando los valores antes de confirmar. La confirmación efectiva mantiene el envío completo y la redirección a la agenda actualizada.

La confirmación utiliza una selección firmada, vinculada al actor, sede, fecha, parámetros y ocupación revisada, con validez de quince minutos. El servidor no acepta cambios de parámetros al confirmar. Dentro de una única transacción comprueba el acceso administrativo, bloquea sede, canchas, turnos y eventos en orden estable y vuelve a calcular el alcance. Si cambia la ocupación, las franjas o la elegibilidad, revierte todo y solicita revisar la vista previa. También comprueba al terminar que ningún turno efectivo haya alcanzado su hora de inicio. Cada acción reutiliza los servicios individuales de reservas, clases y bloqueos; un error no deja anulaciones o bloqueos parciales ni sobrescribe auditoría ante una confirmación repetida.

Las clases participan de la vista previa, las exclusiones y la confirmación transaccional del lote. Se conservan las clases excluidas, las Finalizadas y aquellas cuyo turno ya comenzó.

La cabecera de Agenda ofrece Acciones del mes en el mismo panel lateral de Acciones del día, conservando la sede, fecha y grilla consultadas. Permite elegir mes completo, todas o varias canchas, horario diario con fin opcional y tipos de actividad a conservar. Elegir mes, revisar, volver a editar y cerrar actualizan sólo el panel. Reutiliza el formulario, la vista previa y la confirmación de Acciones del día y sólo permite Anular y liberar. Los listados incluyen la fecha; las actividades iniciadas, Finalizadas o excluidas se conservan. El selector ofrece el mes actual y los dos siguientes. El mes de la fecha consultada es la selección inicial si está habilitado; para fechas fuera de ese intervalo se utiliza el actual. La confirmación firmada vence a los quince minutos y toda la operación mensual se valida y guarda en una única transacción. No crea bloqueos.

## 7. Navegación del portal y consulta de reservas

Agenda es la entrada única para consultar sedes, canchas y horarios y registrar reservas. La cabecera y los inicios administrativo y del portal enlazan a Agenda. No hay una sección independiente de Reservas o Mis reservas. El panel de las reservas autorizadas ofrece detalle y comprobante; ambas pantallas conservan el acceso por identificador y validan permisos. La búsqueda por criterios dentro de Agenda está pendiente. Los eventos Anulados se consultan desde el historial de su turno.

En el portal, las reservas propias muestran su detalle y permiten anulación con al menos una hora de antelación. Las actividades ajenas aparecen como No disponible, con sede, cancha, fecha y horario, sin tipo de actividad ni datos de otras personas. El servidor excluye los objetos de las actividades ajenas del contexto de las celdas y del panel. Los bloqueos, la finalización de emergencia y las acciones del día son exclusivos de la administración; los envíos del portal sólo admiten crear y anular reservas propias. El organizador de una reserva del portal es siempre la cuenta autenticada.

La grilla del portal oculta las filas y pausas iniciadas sin reservas propias. Una fila iniciada con una reserva propia se conserva completa, con las demás actividades como No disponible. Las horas futuras mantienen su presentación y la administración conserva todas las filas. Una selección directa de un horario iniciado oculto no abre el panel. Los días pasados sin eventos propios y el día actual sin eventos propios ni turnos pendientes de inicio muestran mensajes específicos.

## 8. Auditoría con triggers

La tabla `log_auditoria` conserva modificaciones funcionales, anulaciones y eliminaciones permitidas de relaciones en las diez tablas de negocio: usuarios, roles, asignaciones de roles, sedes, canchas, horarios, turnos, eventos, reservas y bloqueos. Las tarifas se auditan como cambios de la sede. Una función común de PostgreSQL captura `UPDATE` y `DELETE` mediante un trigger de fila en cada tabla; también cubre escrituras masivas y SQL. Las altas no generan entradas. Retirar roles y quitar horarios conserva registro de los datos eliminados.

Django comunica actor, origen y UUID mediante configuración local a la transacción, con contexto por solicitud y tratamiento de autenticación y finalización. La autenticación identifica al titular al modificar su cuenta. La finalización automática utiliza origen de tarea, sin usuario ficticio; el SQL conserva su origen y cuenta de PostgreSQL. Autorregistro y creación de administradores no requieren contexto especial de auditoría. Los contextos anidados comparten el UUID y restauran su configuración superior al terminar. Las respuestas HTTP de error revierten la transacción de la solicitud.

Las instantáneas excluyen contraseñas y hashes. Cambio de contraseña y Restablecimiento de contraseña se identifican mediante acciones específicas, con una entrada por operación y sin marcas artificiales. Django informa la intención y el trigger comprueba el cambio efectivo. Las diferencias conservan sólo campos reales no sensibles; pueden ser objetos vacíos. La actualización técnica del hash tiene una acción propia y comparte el UUID del contexto de verificación. Se omiten modificaciones sin diferencias funcionales. Se conservan los campos propios de creación, modificación, responsables y transiciones. Las escrituras y su historial se confirman o revierten juntos. La tabla conserva sus entradas y rechaza modificación, eliminación y vaciado.

Auditoría está disponible en la cabecera y el inicio administrativo, sólo para administradores activos con acceso vigente. La consulta excluye las altas y muestra veinticinco entradas por página en una tabla con encabezados, tipo funcional y una única referencia breve por registro. Las personas, instalaciones y productos se identifican por nombre; los horarios, por sede y día; las actividades y turnos, por código o número; las asignaciones, por persona y número de actividad; las contrataciones, por titular y mes. Los eventos identifican su clase, reserva o bloqueo asociado. La referencia enlaza a la ficha vigente o a la pantalla que contiene el registro: sede para canchas y horarios, usuario para sus roles, clase o turno de planilla para asignaciones y Agenda para turnos. Las entradas de eliminación, los destinos no disponibles y los tipos sin pantalla de consulta conservan la referencia como texto. Un catálogo central reúne tipos, modelos, relaciones y rutas. La referencia utiliza el registro vigente; las eliminaciones utilizan exclusivamente valores anteriores y claves, sin consultas a nombres relacionados actuales ni combinación de diferencias con campos vigentes. Los enlaces se resuelven al consultar y utilizan los permisos de las pantallas existentes. Ver cambios despliega tabla técnica, clave JSON, origen, usuario de aplicación, usuario de PostgreSQL, UUID y valores anteriores y actuales, sin repetir el contexto ampliado del registro. La evidencia histórica permanece en esas diferencias. El resumen muestra al usuario de aplicación, Proceso automático para tareas o PostgreSQL seguido de la cuenta utilizada para SQL. El detalle incluye Usuario de aplicación sólo para el origen Aplicación. Sólo admite GET.

La columna Acción identifica como Inicio de sesión las modificaciones de la propia cuenta desde la aplicación que sólo actualizan `last_login`, sin contar `actualizado_en`. El acceso debe tener una fecha actual informada. Presenta Finalización cuando un evento pasa de Programado a Finalizado y Activación o Desactivación cuando cambia la vigencia de usuarios, sedes, canchas o planes. Estas transiciones de estado se reconocen para todos los orígenes y las finalizaciones incluyen las manuales y automáticas. Las etiquetas se calculan durante la consulta con los valores anteriores y actuales; conservan la acción almacenada y las diferencias del historial. Las ediciones de otros datos mantienen Modificación y las anulaciones, eliminaciones y acciones de contraseña conservan sus etiquetas específicas.

Auditoría ofrece Cambios realizados e Intentos rechazados. La tabla inmutable `intentos_auditoria` conserva exclusivamente inicio de sesión fallido, cambio de contraseña rechazado por contraseña actual incorrecta y acceso denegado por autorización. Los destinos privados de reservas, comprobantes y contrataciones que ocultan registros ajenos con 404 se registran sólo si existe pertenencia ajena comprobada. Los errores comunes de formulario, 404 ordinarios, CSRF, cancelaciones y redirecciones al login quedan fuera. Cada solicitud tiene como máximo un intento y comparte el UUID de contexto; el middleware lo persiste fuera de la transacción de negocio y sobrevive a su rollback. Una falla de persistencia registra únicamente el UUID en el log técnico y mantiene la respuesta original. Una terminación abrupta antes de insertar puede impedir la persistencia. Se conserva el actor autenticado opcional, identificador declarado sólo para login, motivo de catálogo, vista, método y parámetros de ruta permitidos, sin secretos, formularios completos, URLs libres, IP ni encabezados. Los login fallidos se presentan como No autenticado. La consulta administrativa pagina veinticinco filas y permite desplegar los datos técnicos, sin acciones de escritura ni enlaces a ejecutar el intento.

### Verificación y revisión funcional

La revisión manual en una sesión SQL confirmó que insertar sedes y los registros de una reserva no agrega auditoría, que modificar una dirección conserva sus valores anterior y actual, y que anular una reserva registra sus cambios y los del evento con el mismo UUID y actor. La transacción se revirtió y el historial quedó vacío. Las restricciones de la base admiten sólo las acciones y orígenes definidos en el modelo.

Crear usuarios, instalaciones y reservas y comprobar que esas altas no agregan entradas. Modificar un correo, una tarifa o un horario y revisar sus valores anteriores y actuales. Retirar un rol o quitar un horario debe conservar el registro de la relación eliminada. Anular una reserva debe registrar los cambios de evento y reserva con un UUID común. Anular y bloquear conserva las anulaciones sin auditar el alta del bloqueo. Revisar autenticación, contraseñas y finalización manual y automática. Las operaciones SQL directas deben conservar origen y cuenta de base de datos. Los rollback no dejan auditoría de cambios revertidos y la consulta conserva el acceso administrativo de solo lectura.

No se crean ni ejecutan pruebas automatizadas ni se realiza commit. La estructura cabecera y detalle corresponde a la etapa de clases.


### Verificación del origen de bloqueos

Las acciones en los detalles de entidades utilizan botones compactos. En las columnas laterales ocupan todo el ancho disponible, tanto los enlaces como los botones de formularios y los disparadores de formularios desplegables. Las acciones de consulta y edición usan el estilo secundario; anular y desactivar usan el estilo de peligro. Los grupos comparten un espaciado de doce píxeles.

La migración `bloqueos.0002_integrar_evento_origen` incorpora la referencia opcional a `bloqueos`, copia los vínculos existentes y conserva su unicidad y la protección del evento. La copia técnica se realiza dentro de la transacción de la migración sin generar entradas de auditoría de negocio. El esquema utiliza el trigger de `bloqueos` para registrar sus cambios. La agenda y las operaciones individuales y masivas utilizan la referencia directa.

Revisión manual: crear un bloqueo sobre un turno libre y comprobar que no tiene origen; anular y bloquear una reserva y consultar su enlace de origen; liberar ese bloqueo y comprobar que la reserva permanece Anulada y el vínculo se conserva. La base local no contiene bloqueos al aplicar la migración. No se crean ni ejecutan pruebas automatizadas ni se realiza commit.


### Eventos de contraseña

La acción `cambio_contrasena` corresponde al cambio voluntario u obligatorio de la contraseña propia; `restablecimiento_contrasena` identifica al administrador que restablece la cuenta indicada por la clave del registro. `actualizacion_hash` identifica la actualización técnica al verificar credenciales. El contexto temporal comunica la acción y se restaura al terminar; el log conserva origen, responsable, cuenta afectada, fecha y UUID. Los eventos de contraseña omiten `password` y la marca auxiliar `actualizado_en` de las instantáneas, sin agregar campos artificiales. El resto de los campos modificados, como `debe_cambiar_contrasena`, conserva sus valores anteriores y actuales. La cuenta de usuario mantiene sus atributos habituales.

El cambio propio guarda contraseña y obligación de cambio en una única actualización y conserva la sesión mediante el mecanismo de Django. El restablecimiento también guarda ambos datos juntos; la contraseña provisoria se presenta según su recorrido administrativo y no se incorpora al log. Una escritura SQL de la credencial sin intención explícita se identifica como Cambio de contraseña con su origen SQL.

Revisión manual: cambiar una contraseña provisoria y una propia, restablecer la de otra cuenta y comprobar una entrada por operación, actor y cuenta afectada correctos, estado de la obligación de cambio y ausencia de contraseñas, hashes y marcas artificiales en el historial. Revisar que una verificación que actualiza el hash conserva su acción técnica y que modificar otros datos no se clasifica como evento de contraseña.


La migración `auditoria.0003_triggers_auditoria` instala la captura de las diez tablas de negocio y la protección del historial. Su función reconoce las acciones de contraseña según el contexto y el cambio efectivo de la credencial, conserva las diferencias no sensibles y comparte el UUID de la operación. Las dependencias aseguran que las tablas y sus relaciones estén creadas antes de instalar los triggers.


## Navegación e inicio

El navbar ofrece Inicio, Agenda, Planilla semanal para Administrador o Mis clases para Profesor y Alumno, Oferta para cuentas con rol Público y las herramientas administrativas disponibles según los roles y permisos vigentes. Planilla semanal y Mis clases son enlaces directos. Mis clases enlaza a la consulta de Actividad de clases del titular. Los destinos de trabajo se agrupan a la izquierda y el menú de cuenta, identificado por el nombre del usuario, a la derecha. La sección activa se distingue con fondo suave y una línea de acento. Planilla semanal se marca activa sólo en la configuración de la planilla y la generación de clases. Para administración, los detalles, la actividad y las operaciones de clases concretas activan Agenda; para profesores y alumnos activan Mis clases. Los detalles y operaciones de reservas y bloqueos activan Agenda. Feriados conserva su propia entrada activa.

Administración agrupa Usuarios, Sedes y canchas, Membresías, Feriados y Auditoría en ese orden. Sedes y canchas enlaza al listado de Sedes. Si sólo hay un destino administrativo autorizado, se presenta directamente. El menú de cuenta reúne Mi perfil y Cerrar sesión; cerrar sesión utiliza POST. Los desplegables conservan navegación por teclado e indicadores de foco.

Las homes presentan una única grilla titulada Módulos del sistema, filtrada por los permisos de los destinos: Agenda, Usuarios, Sedes y canchas, Clases, Membresías y Auditoría. Cada tarjeta con destino tiene un único botón con el mismo estilo. Clases conserva su descripción del módulo y ofrece Ver planilla semanal para Administrador o Mi actividad para Profesor y Alumno. Feriados se accede desde el navbar, sin tarjeta en la home. Membresías ofrece Ver membresías para elegir entre Planes, Membresías de socios, Contrataciones de planes y Contrataciones de membresías. La gestión de catálogos y contrataciones tiene acceso administrativo y una única entrada Membresías en el desplegable Administración. En el portal, Oferta de la academia permite consultar productos Activos y tarifas vigentes en modo de lectura. Pagos e ingresos aparece al final de la home administrativa como En preparación, sin botón ni entrada en el navbar.

La ruta actual resalta el destino o su grupo. Los desplegables abren con clic, Enter o Espacio; las flechas recorren sus enlaces y Escape cierra devolviendo el foco al disparador. En móvil se expanden dentro de la navegación vertical. Las rutas mantienen las autorizaciones del servidor.


## Catálogo de planes

La administración dispone de alta, listado, búsqueda por nombre o descripción, filtro por estado, detalle y edición de planes mensuales. Los planes se ordenan por modalidad, duración del encuentro y frecuencia semanal, en orden ascendente; nombre e identificador resuelven los empates. Este orden se aplica a la administración y al portal. El listado administrativo muestra veinticinco planes por página y cada fila ofrece un único acceso al detalle. La ficha presenta características, descripción cuando existe, precio y datos de registro; la edición se abre desde su acción y los cambios de estado requieren confirmación.

Cada plan define nombre, modalidad Individual o Grupal, entre uno y siete encuentros semanales, encuentros de una o dos horas y precio mensual no negativo. La descripción es opcional. El nombre es único entre planes Activos sin distinguir mayúsculas y minúsculas; activar un plan comprueba nuevamente esa condición. Las características comerciales se mantienen separadas de las clases y de los cobros.

El acceso exige una cuenta activa con rol Administrador y sin cambio de contraseña pendiente. Los servicios de escritura vuelven a comprobar el acceso con el usuario bloqueado y guardan los cambios dentro de una transacción. La edición y el cambio de estado utilizan una selección firmada vinculada al administrador, al plan y a su última modificación: si cambió, se exige revisar sus datos. La edición no modifica el estado; activar o desactivar establece un estado explícito y repetir el estado vigente no genera cambios. Guardar datos iguales a los vigentes conserva la fecha de modificación.

Las restricciones de PostgreSQL protegen configuración, importes, estado y nombres activos. Los identificadores se generan en la base. El trigger de planes registra modificaciones, cambios de estado y eliminaciones SQL mediante la auditoría transversal, con actor y UUID del contexto; las altas no agregan entradas al historial. El catálogo conserva sus filas y no expone eliminación desde la aplicación.

Revisión manual: crear y editar un plan, revisar nombres Activos repetidos incluso con mayúsculas distintas, precio cero y negativo, límites de frecuencia y duración, búsqueda y filtros, activación/desactivación y solicitudes repetidas. Revisar también una edición abierta en dos pestañas, el rechazo de acceso a cuentas no administrativas y las diferencias registradas en Auditoría.


## Oferta de la academia en el portal

Las cuentas activas con rol Público y sin cambio de contraseña pendiente acceden a Oferta desde el navbar y desde el inicio del portal. La entrada abre Planes de clases. Las pestañas Planes, Membresías y Tarifas permiten recorrer la oferta, indican la sección actual y siguen disponibles cuando un catálogo está vacío. Los administradores conservan su acceso de gestión y pueden consultar las pantallas de oferta por sus rutas.

Los catálogos del portal muestran únicamente productos Activos, con búsqueda por nombre o descripción y veinticinco resultados por página. Las tarjetas presentan nombre, categoría, precio mensual y características comerciales: frecuencia y cantidad de clases por encuentro para planes; horas mensuales y adicional por invitado no socio y turno de una hora para membresías. Los importes se muestran con dos decimales. La descripción, si existe, ocupa hasta dos líneas y habilita Leer descripción. Esa acción abre un modal en la misma página con el nombre y el texto completo, conservando los párrafos y escapando HTML. El modal se cierra con ×, Escape o clic fuera y devuelve el foco al botón. Una tarjeta sin descripción no ofrece acción y las tarjetas del catálogo no son enlaces completos. El portal no tiene pantallas separadas de detalle de productos; la administración conserva las suyas.

La consulta de tarifas muestra las sedes Activas con precio de reserva configurado, en pesos por turno de una hora, común a sus canchas. Cada sede ofrece un acceso a Agenda para consultar disponibilidad. Las sedes Inactivas y las tarifas sin configurar no se incluyen en esta oferta.

Las pantallas de oferta son de lectura: no incluyen edición, cambios de estado, altas comerciales, datos internos de registro ni formularios de contratación. Las escrituras conservan las rutas y controles administrativos. Las consultas sólo admiten GET y comprueban en el servidor que la cuenta esté habilitada y tenga Público o Administrador; consultar no crea turnos, contrataciones ni auditoría.

Revisión manual: acceder con Público, Profesor y Alumno que conserven Público; consultar los catálogos de planes y membresías y sus descripciones, buscar y navegar páginas; revisar importes cero, productos Inactivos por enlace directo, sedes Inactivas y tarifas ausentes. Comprobar la navegación hacia Agenda, el rechazo de acceso sin rol habilitado y que las rutas administrativas sigan rechazando a cuentas no administrativas.


## Contrataciones administrativas de planes

Administración registra y consulta las contrataciones de planes desde Membresías. El listado permite buscar usuario o producto, filtrar por mes y estado y navegar de a veinticinco resultados. El detalle conserva titular, plan, período completo, fecha efectiva, importe aplicado, observaciones y responsable del registro. El estado se muestra con texto; Vencido usa el badge neutro compartido.

El alta comienza seleccionando una cuenta activa sin Profesor y un plan Activo. Luego se elige un mes desde agosto de 2026 hasta el actual; el siguiente al actual se habilita desde el día 25 inclusive según el calendario de Salta. La fecha efectiva se encuentra entre el inicio operativo y hoy y es independiente del mes cubierto. El resumen muestra el precio mensual vigente completo como importe a aplicar, sin campo editable. Una revisión firmada vincula administrador, titular, producto e importe. La confirmación verifica esa revisión con el plan bloqueado y copia su precio vigente, admitiendo cero. Si el precio o la selección cambiaron, no registra la contratación y presenta el importe vigente para una nueva confirmación, conservando mes, fecha efectiva y observaciones. El importe aplicado permanece en la contratación y no se recalcula al cambiar el catálogo. El alta no registra cobros ni genera clases o asignaciones.

La confirmación bloquea las cuentas involucradas en orden de identificador y después el plan; comprueba nuevamente la elegibilidad y la exclusividad del mes. Los registros Activos y Vencidos impiden otra contratación de plan para el mismo usuario y mes. Un mes terminado nace Vencido; el actual o futuro nace Activo. Registrar una contratación Activa otorga Alumno cuando falta y el titular no es Administrador, en la misma transacción. Las cuentas Profesor no pueden contratar planes.

Los planes con cualquier contratación conservan modalidad, frecuencia y duración: el formulario impide editar esos campos y el servicio rechaza su modificación. Nombre, descripción, precio y estado mantienen sus operaciones de catálogo. PostgreSQL protege importe, mes y estados, exige coherencia de datos de anulación y dispone de auditoría de modificaciones y eliminaciones; las altas no generan entradas.

El formulario, listado, detalle, avisos y badges reutilizan los componentes vigentes, sin estilos específicos ni cambios de identidad. La anulación, el vencimiento automático, la consulta propia y los cobros tienen sus entregas funcionales independientes.

Revisión manual: registrar mes actual, futuro habilitado e histórico; contratar un plan con precio cero; revisar los días 24/25 y el cambio de año; rechazar duplicados y fechas fuera de rango; verificar Alumno automático y rechazo de Profesor, cuenta Inactiva o plan Inactivo. Cambiar el precio entre preparación y confirmación y comprobar la nueva revisión sin alta parcial; cambiarlo después del alta y comprobar el importe conservado; intentar cambiar la estructura de un plan con historia. Revisar listado, filtros, detalle, teclado, móvil y rechazo a cuentas no administrativas.


## Anulación administrativa de contrataciones de planes

El detalle de una contratación Activa ofrece Anular contratación. La acción abre una página de revisión con titular, plan, período, importe y efectos. Exige motivo no vacío y confirmación explícita; el formulario se muestra únicamente al solicitar la acción. Las contrataciones Vencidas no admiten anulación. Las Anuladas conservan motivo, responsable y momento visibles en su ficha.

La confirmación comprueba de nuevo el acceso administrativo, bloquea las cuentas involucradas en orden de identificador y después la contratación, y revalida el estado y la versión revisada. Si el registro cambió, exige abrir una nueva revisión. Anular conserva titular, producto, mes, fecha efectiva e importe, y permite registrar una contratación de reemplazo para el mismo mes. El reenvío de una anulación conserva el resultado y no sobrescribe motivo, responsable, momento ni auditoría.

La operación no modifica clases, asignaciones, cobros ni roles, y no genera devoluciones. Puede anularse una contratación Activa de un titular inactivo; quien realiza la operación debe conservar su acceso administrativo. La auditoría de PostgreSQL registra la anulación con su responsable y los campos modificados.

Retirar Alumno bloquea al usuario y comprueba que no existan contrataciones de planes en estado Activo, incluidas las de meses futuros o pendientes de vencimiento automático. Las contrataciones Vencidas o Anuladas no impiden ese retiro. Registrar y anular planes usan el mismo bloqueo del usuario para coordinarse con la gestión de roles.

El recorrido reutiliza el formulario, botones, avisos y ficha compartidos, sin CSS nuevo ni cambios visuales globales. La revisión y confirmación muestran los datos y efectos del plan contratado.

Revisión manual: solicitar y cancelar la revisión, rechazar motivo vacío, confirmar una anulación y comprobar responsable, fecha y auditoría. Reenviar y comprobar que se conservan los datos; intentar anular una Vencida y registrar un reemplazo del mismo mes. Intentar quitar Alumno con un plan Activo, con otro mes Activo y después de anular la última contratación Activa; revisar también un titular inactivo, acceso no administrativo, teclado y móvil.


## Vencimiento automático de contrataciones

Celery Beat programa el vencimiento de planes diariamente a las 00:05 de Salta. La tarea procesa las contrataciones de planes cuyo estado siga Activo y cuyo mes sea anterior al mes local actual; recupera todos los pendientes, no sólo el mes anterior. Las contrataciones del mes actual o futuro, las Anuladas y las Vencidas quedan fuera.

La actualización de los planes se realiza en una transacción y limita cada escritura al estado Activo. PostgreSQL coordina los bloqueos de fila y vuelve a comprobar esa condición frente a una anulación concurrente, sin sobrescribirla. Sólo se modifican estado a Vencido y fecha de modificación con el momento del procesamiento. No se cambian usuarios, roles, productos, fechas efectivas, importes, clases, reservas, coberturas, cobros ni marcas de aviso. Las restricciones de exclusividad del mes conservan las contrataciones Vencidas.

La auditoría registra las modificaciones con origen tarea y sin responsable manual. El log informa la cantidad de planes procesados. Repetir la ejecución no actualiza filas ya Vencidas ni sus fechas o auditoría. Los errores operativos se reintentan con espera progresiva y confirmación tardía del mensaje; si falla la transacción, no quedan escrituras parciales.

La consulta de vigencia de planes comprueba el estado y el período calendario, aunque la tarea se demore. Un mes futuro no da cobertura al actual, ni un mes terminado conserva cobertura por seguir almacenado como Activo. El retiro de Alumno continúa basándose en el estado registrado: el vencimiento no retira el rol automáticamente.

No hay botones de vencimiento ni pantallas nuevas. Los avisos por email tienen su proceso independiente.

Revisión manual: comprobar el cambio al iniciar un mes, la conservación del mes actual y futuro y la recuperación de meses pendientes. Revisar Anulados y Vencidos, ejecución repetida, concurrencia con anulación, importes, roles y auditoría. Comprobar que una contratación fuera de su período no otorgue vigencia aunque su estado almacenado siga Activo.


## Contrataciones propias en el portal

Las cuentas autenticadas, activas y sin cambio de contraseña pendiente consultan sus planes desde Mis contrataciones en la navegación del portal y desde su perfil. No se exige Alumno ni Reservas, ni siquiera para la consulta histórica. La navegación administrativa conserva Membresías; un administrador puede consultar sus contrataciones por el acceso de su perfil, con el mismo alcance de titular.

El listado permite buscar por nombre del plan, filtrar por mes y estado y navegar de a veinticinco resultados. Muestra producto, mes cubierto, importe aplicado y estado con texto. Sin contrataciones propias presenta un estado vacío breve. Se consultan estados Activo, Anulado y Vencido sin excluir productos Inactivos del catálogo.

El detalle muestra producto y configuración comercial, mes y período completo, importe aplicado, estado, fecha efectiva de alta, fecha de registro y fecha de anulación cuando corresponde. No presenta observaciones internas, motivo libre de anulación ni responsables administrativos. No enlaza al catálogo administrativo ni a fichas de otros usuarios y no incluye alta, edición, anulación o cobro. Los cobros tienen su bloque funcional correspondiente.

Las rutas propias sólo admiten GET y comprueban nuevamente la cuenta habilitada en el servidor. Todas las consultas se restringen al identificador de la cuenta autenticada antes de obtener los registros; ningún filtro permite sustituir al titular. Solicitar una contratación ajena por su número devuelve no encontrado, también para un administrador que utiliza una ruta propia. La consulta no registra auditoría ni modifica estados o roles. Las rutas administrativas mantienen sus controles independientes.

Administración y portal comparten las plantillas de listado y detalle y el filtrado/paginación; las vistas propias mantienen explícita su comprobación de titularidad. No se incorpora CSS, JavaScript, iconos ni bibliotecas nuevas. La composición del rediseño conserva su alcance de presentación independiente.

Revisión manual: consultar con y sin Alumno o Reservas, con Profesor y con una cuenta sin contrataciones; revisar planes Activos, Anulados, Vencidos y de productos Inactivos. Navegar desde el menú y el perfil, buscar, filtrar y paginar los planes. Cambiar el número por uno ajeno, agregar parámetros de otro usuario e intentar acceso directo a rutas de escritura administrativas. Comprobar permisos, estado vacío, teclado y móvil.


## Anulación de clases desde el panel de Agenda

Anular y liberar y Anular y bloquear revelan sus formularios dentro del panel. La liberación solicita el motivo; el bloqueo solicita el motivo clasificado y ofrece observaciones opcionales antes del separador y las acciones. Continuar revisa los datos en el servidor y abre el modal compartido con turno, motivo y efecto. Cancelar el modal conserva la selección y los datos.

La confirmación vuelve a Agenda y utiliza los servicios transaccionales de anulación con revisión firmada, versión de la clase y revalidación de permisos, estado, horario y ocupación. La anulación con bloqueo confirma ambas operaciones juntas. Las acciones conservan sus condiciones de disponibilidad y la ficha completa mantiene su recorrido propio.

Verificación realizada: controles de Django, carga de plantillas y sintaxis JavaScript. Revisión manual pendiente de ambas acciones, motivos requeridos, cancelación del modal, observaciones, clase iniciada, revisión vencida, cambios concurrentes y permisos. No se crean ni ejecutan pruebas automatizadas.


## Creación de clases por pasos en Agenda

Crear clase abre un formulario de tres pasos dentro del panel lateral, conservando visible la tarjeta del turno. Profesores exige una selección; Participantes admite continuar sin asignados y ofrece observaciones opcionales. Ambos pasos usan el orden título, buscador y asignaciones, sin mensajes de alta al agregar personas. Atrás conserva los datos y Cancelar limpia el recorrido.

El paso Resumen se obtiene del servidor y muestra turno, profesores, participantes, observaciones y advertencias. Confirmar creación utiliza la revisión firmada y los servicios transaccionales existentes, que revalidan permisos, profesores, participantes, calendario, coincidencias y ocupación. Los errores conservan la selección y vuelven al paso correspondiente; los cambios requieren una nueva revisión.

El alta actualiza la grilla y el panel sin recargar la página. Si la clase se creó pero falla la actualización visual, Actualizar agenda reintenta la consulta sin repetir el alta. Las búsquedas y revisiones pendientes se cancelan al retirar el formulario y las respuestas de selecciones modificadas se descartan. La edición de clases conserva su recorrido propio.

Verificación: controles de Django, carga de plantillas y sintaxis JavaScript. Revisión manual pendiente de los tres pasos, Atrás, Cancelar, clase sin participantes, profesores obligatorios, búsqueda ampliada, observaciones, advertencias, permisos, turno ocupado y cambios de elegibilidad al confirmar. No se crean ni ejecutan pruebas automatizadas.


## Alcance comercial e instalación

La gestión comercial implementada comprende los catálogos de planes de clases y membresías de socios, y las contrataciones administrativas de ambos tipos. Oferta presenta planes y membresías Activos y tarifas de reservas; Mis contrataciones consulta planes propios. Administración registra y consulta contrataciones de membresías de socios, con comprobante e importe aplicado.

Las migraciones definen una instalación limpia con tablas y triggers de auditoría de planes y sus contrataciones. La revisión de esquema comprende migración completa sobre una base temporal, controles de Django, coincidencia entre modelos y migraciones y carga de todas las plantillas. Queda pendiente la revisión manual de navegación, oferta, contrataciones propias, permisos y administración de planes.


## Catálogo de membresías de socios

Administración accede desde Membresías al catálogo de socios, con listado de veinticinco productos por página, búsqueda por nombre o descripción y filtro de estado. Cada fila muestra nombre, horas mensuales, precio mensual, adicional por invitado no socio y estado, con un único enlace al detalle. La ficha presenta características, descripción y fechas; editar y cambiar el estado son acciones explícitas separadas. El formulario se abre al solicitar alta o edición.

El producto registra horas mensuales positivas y dos importes no negativos, admitiendo precios cero. El nombre es único entre Activas sin distinguir mayúsculas y minúsculas, independiente del catálogo de planes. PostgreSQL protege nombre no vacío, horas, precios y estados. La oferta inicial se carga como un producto editable «Socio 10 horas», con diez horas, ARS 40.000 mensuales y ARS 12.500 por invitado no socio y turno de una hora.

Las operaciones exigen Administrador activo sin cambio de contraseña pendiente y revalidan permisos bajo bloqueo del actor y del producto. Una versión firmada identifica actor, producto, tipo y momento de modificación. Las ediciones concurrentes requieren nueva revisión; guardar sin cambios o reenviar el mismo estado no actualiza el registro. La auditoría identifica las membresías, sus modificaciones y sus cambios de estado.

El catálogo conserva sus operaciones separadas del registro de contrataciones, usos y cobros. Las horas mensuales quedan en lectura y no admiten modificaciones desde el servicio cuando existe cualquier contratación histórica. La oferta del portal permite consultar las membresías Activas, sus horas mensuales y su adicional por invitado no socio.

Verificación realizada: instalación limpia en base temporal, controles de Django, coincidencia de modelos y migraciones, carga de 84 plantillas y consulta de oferta inicial y trigger. Revisión manual pendiente: altas y ediciones válidas, duplicados entre Activas, activación con nombre ocupado, precios cero y negativos, horas cero, reenvíos, modificaciones concurrentes y permisos. No se crean ni ejecutan pruebas automatizadas.


## Consulta de oferta de membresías

La oferta incorpora membresías de socios en el catálogo compartido de lectura, con búsqueda por nombre o descripción, paginación y descripciones extensas bajo demanda. Limpiar búsqueda conserva el catálogo consultado. La navegación entre Planes, Membresías y Tarifas usa enlaces con sección actual accesible, sin controles administrativos ni contratación propia hasta su entrega correspondiente.

Verificación realizada: controles de Django, carga de 84 plantillas y revisión de diferencias. Revisión manual pendiente de las pestañas, búsquedas, paginación, descripción, importes cero, productos Inactivos, estados vacíos, permisos, teclado y móvil. No se crean ni ejecutan pruebas automatizadas.


## Confirmación comercial de planes

El alta administrativa aplica el precio vigente confirmado del plan. La revisión del precio se valida dentro de la transacción junto con la habilitación de las cuentas, el producto y la exclusividad del mes. Reenviar una operación registrada no duplica la contratación: la exclusividad de usuario y mes conserva el registro existente. Las contrataciones mantienen sus importes aplicados ante cambios de catálogo o cobros posteriores.

El calendario, las presentaciones y las tareas utilizan America/Argentina/Salta. La selección y el servicio habilitan el mes siguiente desde el día 25 inclusive. Los filtros de consulta permiten ver el mes siguiente independientemente de esa habilitación para conservar acceso a registros existentes.

Verificación realizada: controles de Django, coincidencia de modelos y migraciones, carga de plantillas y aplicación de la migración de etiqueta del importe. Queda pendiente la revisión manual del bloque 2.1, incluidos cambio de precio durante la revisión, envíos manipulados, reenvíos, días 24/25, cambio de año, precio cero, roles y permisos. No se crean ni ejecutan pruebas automatizadas.


## Contrataciones administrativas de membresías de socios

Membresías ofrece el registro y la consulta de contrataciones de socios mediante un recorrido administrativo de dos pasos: selección de cuenta activa y membresía Activa, y confirmación de mes, fecha efectiva, precio mensual y observaciones. El mes cubierto es calendario completo, desde agosto de 2026 hasta el actual, con el siguiente habilitado desde el día 25 de Salta. La fecha efectiva de alta es independiente del mes y no puede ser futura. Una contratación histórica terminada nace Vencida; la actual o futura nace Activa y sólo otorga cobertura en su propio período.

La confirmación aplica el precio mensual vigente completo, incluido cero, sin prorrateo ni importe negociado. La revisión firmada vincula actor, titular, producto e importe; el servicio la revalida con el producto bloqueado. Un cambio exige nueva revisión y confirmación. El importe aplicado permanece independiente del catálogo y del cobro. Registrar no crea reservas, usos ni movimientos de dinero.

Las contrataciones se guardan en membresias_usuarios y tienen exclusividad propia de titular y mes entre Activas o Vencidas, con una restricción única parcial. Pueden coexistir con un plan del mismo mes. Se admiten profesores y cuentas sin Alumno; contratar no modifica roles. La operación bloquea las cuentas por identificador y después el producto para coordinar altas, cambios de acceso y edición del catálogo. Las horas mensuales del producto se conservan desde la primera contratación, cualquiera sea su estado; el formulario muestra el campo en lectura y el servicio rechaza cambios.

El listado permite buscar usuario o producto, filtrar por mes y estado y paginar. El detalle y el comprobante presentan titular, membresía, horas mensuales, período, importe aplicado, fecha efectiva y registro; el detalle administrativo conserva observaciones y responsables. Las consultas propias, el vencimiento automático de membresías y los cobros corresponden a sus entregas independientes. La anulación administrativa se solicita bajo demanda desde el detalle de una contratación Activa. El detalle sólo ofrece acciones implementadas.

PostgreSQL protege mes, importes, estados y coherencia de datos de anulación, genera los identificadores y audita modificaciones y eliminaciones. Auditoría identifica la contratación y enlaza al detalle administrativo. Los datos comerciales de una contratación registrada no admiten edición desde el modelo.

Verificación realizada: instalación limpia en base temporal, controles de Django, coincidencia de modelos y migraciones y carga de 84 plantillas. Revisión manual pendiente del bloque 2.2: profesor socio, plan simultáneo, duplicados, fechas históricas y futuras habilitadas, precio cero, precio cambiado durante la confirmación, protección de horas, comprobante y permisos. No se crean ni ejecutan pruebas automatizadas.


## Anulación administrativa de contrataciones de membresías

El detalle de una contratación de membresía Activa ofrece Anular contratación. La acción abre una página de revisión con titular, producto, período e importe aplicado, informa los efectos y exige motivo no vacío y confirmación. Vencidas y Anuladas no muestran la acción. El registro Anulado conserva motivo, responsable y momento en su detalle y comprobante.

La confirmación exige Administrador activo con acceso vigente, bloquea las cuentas por identificador y después la contratación y revalida estado y revisión firmada. La firma identifica administrador, contratación, tipo de producto y momento de modificación. Una revisión de plan no autoriza anular una membresía. Los cambios requieren nueva revisión y no dejan escrituras parciales. El titular puede estar inactivo. Reenviar una anulación conserva motivo, responsable, momento y auditoría originales.

Anular conserva producto, titular, mes, importe aplicado e historia y permite registrar otra membresía para ese titular y mes. No modifica planes, roles, clases, asignaciones ni cobros y no genera devoluciones. La vigencia rechaza nuevas aplicaciones de una contratación Anulada; las horas del catálogo permanecen protegidas aunque todas sus contrataciones estén Anuladas. La auditoría registra la transición con su responsable.

Los impedimentos por aplicaciones como organizador o invitado socio vigente en reservas Programadas se integran al crear esas relaciones. El cómputo de usos conservados del titular y mes se integra con reservas; no hay reinicio de registros comerciales ni eliminación de contrataciones al reemplazar.

Verificación realizada: controles de Django, coincidencia de modelos y migraciones, carga de plantillas y revisión de rutas y condiciones de acciones. Revisión manual pendiente: anulación, motivo vacío, reenvío, Vencidas, reemplazo del mes, convivencia con plan, titular inactivo, firma de otro tipo, acceso no administrativo y protección de horas. Los vínculos de reservas, invitados y usos mantienen su revisión pendiente en el plan. No se crean ni ejecutan pruebas automatizadas.
