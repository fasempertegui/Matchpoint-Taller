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

Los estados del evento son Programado, Anulado y Finalizado, con auditoría coherente para cada caso. La ocupación común integra reservas, clases y bloqueos. El registro crea el evento con su turno y la reserva en una única transacción.

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

Las celdas con anulaciones accesibles muestran un chip neutro con un ícono de círculo tachado y la cantidad de eventos accesibles. Se ubica en la esquina inferior derecha, separado del enlace que abre el turno. Abre una consulta emergente anclada en escritorio y un panel inferior en móvil, con una lista de sólo lectura ordenada por anulación más reciente. Cada tarjeta reutiliza el fondo de su tipo de evento en Agenda y muestra una flecha hacia su detalle. Toda la tarjeta funciona como enlace: reservas y clases utilizan sus pantallas de detalle y los bloqueos tienen un detalle de sólo lectura exclusivo de administración. Destaca el tipo sobre el organizador, modalidad o motivo clasificado del bloqueo, que se presenta como información secundaria. No incluye motivo de anulación, separadores, barra lateral, íconos ni tachado. No muestra cabecera, identificadores internos ni datos de responsable o momento de anulación. Se cierra con Escape o con clic fuera y devuelve el foco al chip. La administración ve todas las anulaciones; el portal sólo sus reservas y las clases vinculadas a su cuenta. El servidor aplica este filtro también a las consultas directas. Las filas con historial accesible permanecen visibles en fechas pasadas y fuera del horario actual, aunque el turno esté libre. El clic habitual en la celda conserva la consulta de su estado actual.

La sección Agenda permite consultar una sede por día, con una columna por cancha. Se seleccionan sede y fecha, y se navega al día anterior, siguiente o a Hoy. El selector muestra Día activo y Semana deshabilitado. El acceso está habilitado para cuentas activas con rol Administrador o Reservas y sin cambio de contraseña pendiente.

La consulta incluye instalaciones inactivas para acceder a su historia, representa los espacios libres desde los horarios de la sede y conserva los eventos existentes fuera de las franjas actuales. No registra turnos ni eventos por consultar. Sin canchas, horarios o actividades muestra los estados vacíos correspondientes. Las fechas inválidas y las canchas de otra sede se rechazan. Los límites de consulta son el inicio de operaciones y un año calendario después del día actual.

Seleccionar una celda muestra su fecha, cancha y horario. El detalle acompaña a la grilla diaria en un panel lateral y se ubica debajo en pantallas pequeñas. Seleccionar un turno o cerrar su panel no recarga la grilla ni cambia el desplazamiento: el servidor entrega el detalle autorizado y se actualizan el panel, el resaltado y la URL de selección. Ante errores se conserva el detalle anterior con un aviso; las selecciones rápidas sólo muestran la última respuesta. El registro, la anulación y la finalización mantienen sus envíos y redirecciones completos. Para reservas incluye organizador, estado junto al identificador, observaciones y acceso al detalle completo. El aviso de carga aparece únicamente cuando la consulta tarda más de 300 ms. Las reservas Anuladas conservan sus datos y no ocupan celdas; su localización por criterios está pendiente. Los turnos iniciados se atenúan; Ahora destaca únicamente la hora en el margen y se actualiza con la zona horaria del sistema.

Un turno libre permite registrar una reserva para un organizador habilitado desde el panel, con confirmación de participante, horario e importe. Se respetan precio, franjas, instalaciones activas y anticipación de catorce días. Una reserva futura permite anular y liberar con motivo; una vencida pendiente de finalización ofrece la acción administrativa de emergencia. Estas acciones reutilizan los servicios transaccionales de reservas. Si cambia el precio se exige revisar el importe; si cambia la reserva que ocupa el turno, la confirmación no se aplica a la actividad nueva.

La agenda integra reservas, clases y bloqueos. Permite consultar sus detalles, ejecutar las acciones individuales autorizadas y realizar operaciones masivas de anulación y bloqueo con exclusiones por tipo de evento.

Los turnos vacíos cuyo horario ya terminó no ofrecen acciones sobre su estado actual; si tienen anulaciones accesibles, conservan el chip de anulados para consultar su historial. Los eventos finalizados conservan acceso a su detalle histórico.

## 5. Bloqueos individuales

El Administrador puede crear un bloqueo sobre un turno futuro de una sede y cancha activas, hasta un año calendario después de la fecha actual. El motivo es Clima adverso, Torneo o Mantenimiento y se admiten observaciones opcionales. No exige tarifa, pero el turno debe quedar íntegramente dentro de una franja de funcionamiento de la sede. El servidor comprueba el horario dentro de la transacción y la agenda no ofrece crear bloqueos fuera de las franjas.

Cada bloqueo tiene un identificador B, su evento Programado y un único turno. El campo opcional y único `evento_origen` guarda la reserva o clase anulada que originó el bloqueo; queda vacío al bloquear un turno libre y conserva la referencia histórica al liberar el bloqueo. La grilla lo distingue de las reservas y muestra su motivo. El panel incluye identificador, estado registrado, motivo, responsable y momento del registro, observaciones y reserva de origen cuando corresponde. Los bloqueos iniciados o terminados se consultan sin acciones; su condición horaria no cambia el estado registrado ni finaliza el evento.

Anular y bloquear sobre una reserva futura exige el motivo de anulación de al menos 25 caracteres y el motivo del bloqueo. La confirmación identifica la reserva, su organizador y el turno. Dentro de una única transacción comprueba el acceso administrativo, las instalaciones activas, el horario de funcionamiento, el inicio futuro y la ocupación confirmada; anula la reserva, comprueba el turno libre y registra el bloqueo con su origen. Un fallo revierte también la anulación. Si la actividad cambió, exige revisar la selección y no anula la actividad nueva.

Anular y liberar un bloqueo exige motivo en texto libre y un inicio futuro. Conserva el bloqueo, su evento, el turno y el origen, y registra responsable, momento y motivo de anulación. No reactiva la reserva de origen. La operación no exige que la instalación permanezca activa. Se rechazan acciones repetidas, bloqueos iniciados y referencias a un bloqueo distinto del turno seleccionado.

Las operaciones se realizan desde el panel de Agenda, sin una sección independiente de bloqueos. Crear reserva y Crear bloqueo utilizan botones de contorno para desplegar los formularios, separados por una línea; Confirmar reserva y Confirmar bloqueo utilizan fondo violeta para destacar el envío de la operación. Sólo una acción del panel puede estar desplegada a la vez, por lo que abrir una cierra la anterior sin borrar los datos ingresados. Reutilizan la exclusión de ocupación del evento, bloquean el turno antes del evento y vuelven a validar permisos y límites horarios dentro de la transacción. La tarea de finalización de reservas no procesa bloqueos.

## 6. Acciones del día

La tarjeta del título de Agenda ofrece Acciones del día para la sede y fecha consultadas, desde hoy hasta un año después. Abre el mismo panel lateral utilizado por el detalle de turnos; la grilla permanece visible. Abrir, cerrar, revisar y volver a editar actualizan sólo el panel, sin desplazar la página. Seleccionar un turno reemplaza el contenido por su detalle. En pantallas pequeñas el panel se ubica debajo de la grilla. Permite seleccionar una o varias canchas y operar sobre el día completo o desde una hora de corte inclusiva. Sólo se actúa sobre turnos cuyo inicio sigue siendo futuro al confirmar. Un corte a las 18:30 incluye los turnos de las 19:00 en adelante.

Anular y liberar anula reservas, clases y bloqueos elegibles, con opción de excluir cada tipo; los turnos libres no requieren acción. Admite instalaciones inactivas y conserva la historia. Anular y bloquear exige sede y canchas activas y turnos íntegramente contenidos en las franjas de funcionamiento: anula las reservas y clases incluidas y crea un bloqueo independiente para cada turno efectivo, incluidos los libres. Permite excluir reservas y clases y conserva los bloqueos existentes como ya cubiertos. Cada bloqueo que nace de una anulación registra su reserva o clase de origen. Los turnos iniciados y eventos Finalizados se conservan; los eventos Anulados no ocupan turnos ni se procesan nuevamente.

El formulario recoge alcance, exclusiones y motivos. Exige un motivo de anulación si se anulan eventos y un mínimo de 25 caracteres si incluye reservas. Los bloqueos requieren su motivo clasificado y admiten observaciones comunes. La vista previa no escribe turnos ni eventos. Presenta las cantidades y los listados desplegables de acciones y eventos conservados con su motivo. El formulario compacto utiliza listas desplegables para operación, canchas y horario. Canchas ofrece Todas las canchas de la sede y Seleccionar; la segunda opción permite marcar una o varias canchas. Horario ofrece Día completo y Desde las HH:00 para cada inicio habilitado de la fecha consultada que aún sea futuro; no ofrece turnos iniciados ni horas fuera de las franjas. La lista se calcula con el día de la semana y la hora local actual y se valida nuevamente al enviar. Si se elige un inicio, Hasta ofrece un fin opcional: sólo horas de finalización de turnos habilitados posteriores al inicio, incluida la hora de cierre. Las pausas entre franjas no agregan opciones. Sin fin indicado abarca el resto del día; con fin indicado sólo incluye turnos completos anteriores a ese límite. La vista previa, la edición y la confirmación conservan y validan ese intervalo. Permite volver a editar conservando los valores antes de confirmar. La confirmación efectiva mantiene el envío completo y la redirección a la agenda actualizada.

La confirmación utiliza una selección firmada, vinculada al actor, sede, fecha, parámetros y ocupación revisada, con validez de quince minutos. El servidor no acepta cambios de parámetros al confirmar. Dentro de una única transacción comprueba el acceso administrativo, bloquea sede, canchas, turnos y eventos en orden estable y vuelve a calcular el alcance. Si cambia la ocupación, las franjas o la elegibilidad, revierte todo y solicita revisar la vista previa. También comprueba al terminar que ningún turno efectivo haya alcanzado su hora de inicio. Cada acción reutiliza los servicios individuales de reservas, clases y bloqueos; un error no deja anulaciones o bloqueos parciales ni sobrescribe auditoría ante una confirmación repetida.

Las clases participan de la vista previa, las exclusiones y la confirmación transaccional del lote. Se conservan las clases excluidas, las Finalizadas y aquellas cuyo turno ya comenzó.

## 7. Navegación del portal y consulta de reservas

Agenda es la entrada única para consultar sedes, canchas y horarios y registrar reservas. La cabecera y los inicios administrativo y del portal enlazan a Agenda. No hay una sección independiente de Reservas o Mis reservas. El panel de las reservas autorizadas ofrece detalle y comprobante; ambas pantallas conservan el acceso por identificador y validan permisos. La búsqueda por criterios dentro de Agenda está pendiente. Los eventos Anulados se consultan desde el historial de su turno.

En el portal, las reservas propias muestran su detalle y permiten anulación con al menos una hora de antelación. Las actividades ajenas aparecen como No disponible, con sede, cancha, fecha y horario, sin tipo de actividad ni datos de otras personas. El servidor excluye los objetos de las actividades ajenas del contexto de las celdas y del panel. Los bloqueos, la finalización de emergencia y las acciones del día son exclusivos de la administración; los envíos del portal sólo admiten crear y anular reservas propias. El organizador de una reserva del portal es siempre la cuenta autenticada.

La grilla del portal oculta las filas y pausas iniciadas sin reservas propias. Una fila iniciada con una reserva propia se conserva completa, con las demás actividades como No disponible. Las horas futuras mantienen su presentación y la administración conserva todas las filas. Una selección directa de un horario iniciado oculto no abre el panel. Los días pasados sin eventos propios y el día actual sin eventos propios ni turnos pendientes de inicio muestran mensajes específicos.

## 8. Auditoría con triggers

La tabla `log_auditoria` conserva modificaciones funcionales, anulaciones y eliminaciones permitidas de relaciones en las diez tablas de negocio: usuarios, roles, asignaciones de roles, sedes, canchas, horarios, turnos, eventos, reservas y bloqueos. Las tarifas se auditan como cambios de la sede. Una función común de PostgreSQL captura `UPDATE` y `DELETE` mediante un trigger de fila en cada tabla; también cubre escrituras masivas y SQL. Las altas no generan entradas. Retirar roles y quitar horarios conserva registro de los datos eliminados.

Django comunica actor, origen y UUID mediante configuración local a la transacción, con contexto por solicitud y tratamiento de autenticación y finalización. La autenticación identifica al titular al modificar su cuenta. La finalización automática utiliza origen de tarea, sin usuario ficticio; el SQL conserva su origen y cuenta de PostgreSQL. Autorregistro y creación de administradores no requieren contexto especial de auditoría. Los contextos anidados comparten el UUID y restauran su configuración superior al terminar. Las respuestas HTTP de error revierten la transacción de la solicitud.

Las instantáneas excluyen contraseñas y hashes. Cambio de contraseña y Restablecimiento de contraseña se identifican mediante acciones específicas, con una entrada por operación y sin marcas artificiales. Django informa la intención y el trigger comprueba el cambio efectivo. Las diferencias conservan sólo campos reales no sensibles; pueden ser objetos vacíos. La actualización técnica del hash tiene una acción propia y comparte el UUID del contexto de verificación. Se omiten modificaciones sin diferencias funcionales. Se conservan los campos propios de creación, modificación, responsables y transiciones. Las escrituras y su historial se confirman o revierten juntos. La tabla conserva sus entradas y rechaza modificación, eliminación y vaciado.

Auditoría está disponible en la cabecera y el inicio administrativo, sólo para administradores activos con acceso vigente. La consulta excluye las altas, muestra veinticinco entradas por página en filas compactas y despliega origen, usuario de aplicación, usuario de PostgreSQL, UUID y valores anteriores y actuales. El resumen muestra al usuario de aplicación, Proceso automático para tareas o PostgreSQL seguido de la cuenta utilizada para SQL. El detalle incluye Usuario de aplicación sólo para el origen Aplicación. Sólo admite GET.

### Verificación y revisión funcional

La revisión manual en una sesión SQL confirmó que insertar sedes y los registros de una reserva no agrega auditoría, que modificar una dirección conserva sus valores anterior y actual, y que anular una reserva registra sus cambios y los del evento con el mismo UUID y actor. La transacción se revirtió y el historial quedó vacío. Las restricciones de la base admiten sólo las acciones y orígenes definidos en el modelo.

Crear usuarios, instalaciones y reservas y comprobar que esas altas no agregan entradas. Modificar un correo, una tarifa o un horario y revisar sus valores anteriores y actuales. Retirar un rol o quitar un horario debe conservar el registro de la relación eliminada. Anular una reserva debe registrar los cambios de evento y reserva con un UUID común. Anular y bloquear conserva las anulaciones sin auditar el alta del bloqueo. Revisar autenticación, contraseñas y finalización manual y automática. Las operaciones SQL directas deben conservar origen y cuenta de base de datos. Los rollback no dejan auditoría de cambios revertidos y la consulta conserva el acceso administrativo de solo lectura.

No se crean ni ejecutan pruebas automatizadas ni se realiza commit. La estructura cabecera y detalle corresponde a la etapa de clases.


### Verificación del origen de bloqueos

La migración `bloqueos.0002_integrar_evento_origen` incorpora la referencia opcional a `bloqueos`, copia los vínculos existentes y conserva su unicidad y la protección del evento. La copia técnica se realiza dentro de la transacción de la migración sin generar entradas de auditoría de negocio. El esquema utiliza el trigger de `bloqueos` para registrar sus cambios. La agenda y las operaciones individuales y masivas utilizan la referencia directa.

Revisión manual: crear un bloqueo sobre un turno libre y comprobar que no tiene origen; anular y bloquear una reserva y consultar su enlace de origen; liberar ese bloqueo y comprobar que la reserva permanece Anulada y el vínculo se conserva. La base local no contiene bloqueos al aplicar la migración. No se crean ni ejecutan pruebas automatizadas ni se realiza commit.


### Eventos de contraseña

La acción `cambio_contrasena` corresponde al cambio voluntario u obligatorio de la contraseña propia; `restablecimiento_contrasena` identifica al administrador que restablece la cuenta indicada por la clave del registro. `actualizacion_hash` identifica la actualización técnica al verificar credenciales. El contexto temporal comunica la acción y se restaura al terminar; el log conserva origen, responsable, cuenta afectada, fecha y UUID. Los eventos de contraseña omiten `password` y la marca auxiliar `actualizado_en` de las instantáneas, sin agregar campos artificiales. El resto de los campos modificados, como `debe_cambiar_contrasena`, conserva sus valores anteriores y actuales. La cuenta de usuario mantiene sus atributos habituales.

El cambio propio guarda contraseña y obligación de cambio en una única actualización y conserva la sesión mediante el mecanismo de Django. El restablecimiento también guarda ambos datos juntos; la contraseña provisoria se presenta según su recorrido administrativo y no se incorpora al log. Una escritura SQL de la credencial sin intención explícita se identifica como Cambio de contraseña con su origen SQL.

Revisión manual: cambiar una contraseña provisoria y una propia, restablecer la de otra cuenta y comprobar una entrada por operación, actor y cuenta afectada correctos, estado de la obligación de cambio y ausencia de contraseñas, hashes y marcas artificiales en el historial. Revisar que una verificación que actualiza el hash conserva su acción técnica y que modificar otros datos no se clasifica como evento de contraseña.


La migración `auditoria.0003_triggers_auditoria` instala la captura de las diez tablas de negocio y la protección del historial. Su función reconoce las acciones de contraseña según el contexto y el cambio efectivo de la credencial, conserva las diferencias no sensibles y comparte el UUID de la operación. Las dependencias aseguran que las tablas y sus relaciones estén creadas antes de instalar los triggers.


## Navegación e inicio

El navbar ofrece Inicio, Agenda, Clases, Oferta para cuentas con rol Público y las herramientas administrativas disponibles según los roles y permisos vigentes. Clases mantiene un desplegable incluso con un solo destino: Planilla semanal para Administrador o Mi actividad para Profesor y Alumno. Mi actividad enlaza a la consulta de Actividad de clases del titular.

Administración agrupa Usuarios, Sedes y canchas, Planes, Pases, Feriados y Auditoría en ese orden. Sedes y canchas enlaza al listado de Sedes. Si sólo hay un destino administrativo autorizado, se presenta directamente. Mi perfil y Cerrar sesión permanecen disponibles en la navegación.

Las homes presentan una única grilla titulada Módulos del sistema, filtrada por los permisos de los destinos: Agenda, Usuarios, Sedes y canchas, Clases, Membresías y Auditoría. Cada tarjeta con destino tiene un único botón con el mismo estilo. Clases conserva su descripción del módulo y ofrece Ver planilla semanal para Administrador o Mi actividad para Profesor y Alumno. Feriados se accede desde el navbar, sin tarjeta en la home. Membresías ofrece Ver membresías para elegir entre Planes, Pases de cancha y Contrataciones de planes. La gestión de catálogos y contrataciones tiene acceso administrativo y una única entrada Membresías en el desplegable Administración. En el portal, Oferta de la academia permite consultar productos Activos y tarifas vigentes en modo de lectura. Pagos e ingresos aparece al final de la home administrativa como En preparación, sin botón ni entrada en el navbar.

La ruta actual resalta el destino o su grupo. Los desplegables abren con clic, Enter o Espacio; las flechas recorren sus enlaces y Escape cierra devolviendo el foco al disparador. En móvil se expanden dentro de la navegación vertical. Las rutas mantienen las autorizaciones del servidor.


## Catálogo de planes

La administración dispone de alta, listado, búsqueda por nombre o descripción, filtro por estado, detalle y edición de planes mensuales. Los planes se ordenan por modalidad, duración del encuentro y frecuencia semanal, en orden ascendente; nombre e identificador resuelven los empates. Este orden se aplica a la administración y al portal. El listado administrativo muestra veinticinco planes por página y cada fila ofrece un único acceso al detalle. La ficha presenta características, descripción cuando existe, precio y datos de registro; la edición se abre desde su acción y los cambios de estado requieren confirmación.

Cada plan define nombre, modalidad Individual o Grupal, entre uno y siete encuentros semanales, encuentros de una o dos horas y precio mensual no negativo. La descripción es opcional. El nombre es único entre planes Activos sin distinguir mayúsculas y minúsculas; activar un plan comprueba nuevamente esa condición. Las características comerciales se mantienen separadas de las clases y de los cobros.

El acceso exige una cuenta activa con rol Administrador y sin cambio de contraseña pendiente. Los servicios de escritura vuelven a comprobar el acceso con el usuario bloqueado y guardan los cambios dentro de una transacción. La edición y el cambio de estado utilizan una selección firmada vinculada al administrador, al plan y a su última modificación: si cambió, se exige revisar sus datos. La edición no modifica el estado; activar o desactivar establece un estado explícito y repetir el estado vigente no genera cambios. Guardar datos iguales a los vigentes conserva la fecha de modificación.

Las restricciones de PostgreSQL protegen configuración, importes, estado y nombres activos. Los identificadores se generan en la base. El trigger de planes registra modificaciones, cambios de estado y eliminaciones SQL mediante la auditoría transversal, con actor y UUID del contexto; las altas no agregan entradas al historial. El catálogo conserva sus filas y no expone eliminación desde la aplicación.

Revisión manual: crear y editar un plan, revisar nombres Activos repetidos incluso con mayúsculas distintas, precio cero y negativo, límites de frecuencia y duración, búsqueda y filtros, activación/desactivación y solicitudes repetidas. Revisar también una edición abierta en dos pestañas, el rechazo de acceso a cuentas no administrativas y las diferencias registradas en Auditoría.


## Catálogo de pases

La administración dispone de alta, listado, búsqueda por nombre o descripción, filtro por estado, detalle, edición y activación/desactivación de pases mensuales de cancha. El listado presenta veinticinco productos por página y un único acceso al detalle por fila. La ficha muestra las características y los precios; la edición se abre desde su acción y los cambios de estado exigen confirmación.

Cada pase tiene nombre, descripción opcional, variante Libre o Fin de semana, límite diario de horas, precio mensual y adicional por invitado sin cobertura para un turno de una hora. Libre habilita todos los días y Fin de semana, sábados y domingos. El límite diario es positivo y se propone en dos horas al crear. Ambos importes admiten cero y no pueden ser negativos. Los nombres son únicos entre pases Activos sin distinguir mayúsculas y minúsculas; la comparación es independiente del catálogo de planes y se repite al activar un producto.

El acceso exige una cuenta activa con rol Administrador y sin cambio de contraseña pendiente. Los servicios revalidan acceso y datos dentro de la transacción, con bloqueo del actor y del producto. La selección firmada distingue plan y pase, usuario, registro y última modificación. Si el producto cambió, se exige revisar antes de confirmar. La edición conserva el estado; repetir el estado vigente o guardar datos iguales no actualiza la fecha ni genera auditoría.

El catálogo define la oferta comercial. Las contrataciones, las coberturas aplicadas a reservas y los consumos diarios tienen sus propios registros y recorridos. PostgreSQL protege los dominios, importes y nombres activos, genera los identificadores y audita las modificaciones mediante el trigger de pases. Las altas no generan entradas de auditoría y las pantallas no ofrecen eliminación física.

Planes y pases comparten el formulario de catálogo, la protección de la selección y el guardado auditado, conservando campos y recorridos específicos. La entrada Membresías permite elegir entre los dos catálogos y las contrataciones de planes; los breadcrumbs conservan ese acceso.

Revisión manual: crear un pase Libre y uno de Fin de semana; revisar nombres repetidos, importes cero y negativos, límite diario cero y positivo, filtro por estado, edición y activación/desactivación. Comprobar también reenvíos, dos pestañas editando el mismo producto, rechazo de acceso no administrativo y las diferencias en Auditoría.


## Oferta de la academia en el portal

Las cuentas activas con rol Público y sin cambio de contraseña pendiente acceden a Oferta desde el navbar y desde el inicio del portal. La entrada presenta Planes de clases, Pases de cancha y Tarifas de reservas. Los administradores conservan su acceso de gestión y pueden consultar las pantallas de oferta por sus rutas.

Los catálogos del portal muestran únicamente productos Activos, con búsqueda por nombre o descripción y veinticinco resultados por página. Las tarjetas presentan nombre, categoría, precio mensual y características comerciales: frecuencia y cantidad de clases por encuentro para planes; variante, límite diario y adicional por invitado sin cobertura para pases. La descripción, si existe, ocupa hasta dos líneas y habilita Leer descripción. Esa acción abre un modal en la misma página con el nombre y el texto completo, conservando los párrafos y escapando HTML. El modal se cierra con ×, Escape o clic fuera y devuelve el foco al botón. Una tarjeta sin descripción no ofrece acción y las tarjetas del catálogo no son enlaces completos. El portal no tiene pantallas separadas de detalle de productos; la administración conserva las suyas.

La consulta de tarifas muestra las sedes Activas con precio de reserva configurado, en pesos por turno de una hora, común a sus canchas. Cada sede ofrece un acceso a Agenda para consultar disponibilidad. Las sedes Inactivas y las tarifas sin configurar no se incluyen en esta oferta.

Las pantallas de oferta son de lectura: no incluyen edición, cambios de estado, altas comerciales, datos internos de registro ni formularios de contratación. Las escrituras conservan las rutas y controles administrativos. Las consultas sólo admiten GET y comprueban en el servidor que la cuenta esté habilitada y tenga Público o Administrador; consultar no crea turnos, contrataciones ni auditoría.

Revisión manual: acceder con Público, Profesor y Alumno que conserven Público; consultar ambos catálogos y sus descripciones, buscar y navegar páginas; revisar importes cero, productos Inactivos por enlace directo, sedes Inactivas y tarifas ausentes. Comprobar la navegación hacia Agenda, el rechazo de acceso sin rol habilitado y que las rutas administrativas sigan rechazando a cuentas no administrativas.


## Contrataciones administrativas de planes

Administración registra y consulta las contrataciones de planes desde Membresías. El listado permite buscar usuario o producto, filtrar por mes y estado y navegar de a veinticinco resultados. El detalle conserva titular, plan, período completo, fecha efectiva, importe acordado, observaciones y responsable del registro. El estado se muestra con texto; Vencido usa el badge neutro compartido.

El alta comienza seleccionando una cuenta activa sin Profesor y un plan Activo. Luego se elige un mes desde agosto de 2026 hasta el siguiente al actual; cada opción muestra su período completo. La fecha efectiva se encuentra entre el inicio operativo y hoy y es independiente del mes cubierto. Se propone el precio vigente y la administración puede establecer un importe acordado no negativo. Ese importe permanece en la contratación y no se recalcula al cambiar el catálogo. El alta no registra cobros ni genera clases o asignaciones.

La confirmación bloquea las cuentas involucradas en orden de identificador y después el plan; comprueba nuevamente la elegibilidad y la exclusividad del mes. Los registros Activos y Vencidos impiden otra contratación de plan para el mismo usuario y mes. Un mes terminado nace Vencido; el actual o futuro nace Activo. Registrar una contratación Activa otorga Alumno cuando falta y el titular no es Administrador, en la misma transacción. Las cuentas Profesor no pueden contratar planes.

Los planes con cualquier contratación conservan modalidad, frecuencia y duración: el formulario impide editar esos campos y el servicio rechaza su modificación. Nombre, descripción, precio y estado mantienen sus operaciones de catálogo. PostgreSQL protege importe, mes y estados, exige coherencia de datos de anulación y dispone de auditoría de modificaciones y eliminaciones; las altas no generan entradas.

El formulario, listado, detalle, avisos y badges reutilizan los componentes vigentes, sin estilos específicos ni cambios de identidad. La anulación, el vencimiento automático, la consulta propia y los cobros tienen sus entregas funcionales independientes.

Revisión manual: registrar mes actual, futuro e histórico; ajustar el importe incluido cero; rechazar duplicados, precio negativo y fechas fuera de rango; verificar Alumno automático y rechazo de Profesor, cuenta Inactiva o plan Inactivo. Cambiar el precio de catálogo y comprobar el importe conservado; intentar cambiar la estructura de un plan con historia. Revisar listado, filtros, detalle, teclado, móvil y rechazo a cuentas no administrativas.
