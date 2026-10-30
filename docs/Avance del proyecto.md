# Avance del proyecto

## Academia de Tenis TM

La aplicación administra una academia de tenis mediante Python, Django y PostgreSQL, con ejecución en Docker Compose. El sistema completo contempla instalaciones, usuarios, clases, asistencia, membresías, reservas e ingresos.

## 1. Hito 1: sedes y canchas

Se dispone de alta, consulta, modificación, activación y desactivación de sedes y canchas. La baja es lógica y conserva los registros.

No se permite desactivar una sede o cancha con reservas Programadas, incluidas las vencidas pendientes de finalizar. La comprobación se coordina con el registro de reservas mediante una transacción y bloqueos. La reactivación está permitida y editar los datos no cambia el estado.

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

Los estados del evento son Programado, Anulado y Finalizado, con auditoría coherente para cada caso. La base común admite los tipos Reserva, Clase y Bloqueo; el proceso implementado registra reservas y bloqueos. El registro crea el evento con su turno y la reserva en una única transacción.

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

La búsqueda por criterios y la localización de reservas Anuladas desde Agenda están pendientes. No hay una sección independiente de Reservas ni un formulario de alta separado.

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

La sección Agenda permite consultar una sede por día, con una columna por cancha. Se seleccionan sede y fecha, y se navega al día anterior, siguiente o a Hoy. El selector muestra Día activo y Semana deshabilitado. El acceso está habilitado para cuentas activas con rol Administrador o Reservas y sin cambio de contraseña pendiente.

La consulta incluye instalaciones inactivas para acceder a su historia, representa los espacios libres desde los horarios de la sede y conserva los eventos existentes fuera de las franjas actuales. No registra turnos ni eventos por consultar. Sin canchas, horarios o actividades muestra los estados vacíos correspondientes. Las fechas inválidas y las canchas de otra sede se rechazan. Los límites de consulta son el inicio de operaciones y un año calendario después del día actual.

Seleccionar una celda muestra su fecha, cancha y horario. El detalle acompaña a la grilla diaria en un panel lateral y se ubica debajo en pantallas pequeñas. Seleccionar un turno o cerrar su panel no recarga la grilla ni cambia el desplazamiento: el servidor entrega el detalle autorizado y se actualizan el panel, el resaltado y la URL de selección. Ante errores se conserva el detalle anterior con un aviso; las selecciones rápidas sólo muestran la última respuesta. El registro, la anulación y la finalización mantienen sus envíos y redirecciones completos. Para reservas incluye organizador, estado junto al identificador, observaciones y acceso al detalle completo. El aviso de carga aparece únicamente cuando la consulta tarda más de 300 ms. Las reservas Anuladas conservan sus datos y no ocupan celdas; su localización por criterios está pendiente. Los turnos iniciados se atenúan; Ahora destaca únicamente la hora en el margen y se actualiza con la zona horaria del sistema.

Un turno libre permite registrar una reserva para un organizador habilitado desde el panel, con confirmación de participante, horario e importe. Se respetan precio, franjas, instalaciones activas y anticipación de catorce días. Una reserva futura permite anular y liberar con motivo; una vencida pendiente de finalización ofrece la acción administrativa de emergencia. Estas acciones reutilizan los servicios transaccionales de reservas. Si cambia el precio se exige revisar el importe; si cambia la reserva que ocupa el turno, la confirmación no se aplica a la actividad nueva.

La agenda permite operar reservas y bloqueos individuales y realizar operaciones masivas sobre ambos tipos. Las acciones de clases pertenecen a su etapa de implementación.

Los turnos vacíos cuyo horario ya terminó se muestran sin enlace ni interacción. Los eventos finalizados conservan acceso a su detalle histórico.

## 5. Bloqueos individuales

El Administrador puede crear un bloqueo sobre un turno futuro de una sede y cancha activas, hasta un año calendario después de la fecha actual. El motivo es Clima adverso, Torneo o Mantenimiento y se admiten observaciones opcionales. No exige tarifa, pero el turno debe quedar íntegramente dentro de una franja de funcionamiento de la sede. El servidor comprueba el horario dentro de la transacción y la agenda no ofrece crear bloqueos fuera de las franjas.

Cada bloqueo tiene un identificador B, su evento Programado y un único turno. El campo opcional y único `evento_origen` guarda la reserva o clase anulada que originó el bloqueo; queda vacío al bloquear un turno libre y conserva la referencia histórica al liberar el bloqueo. La grilla lo distingue de las reservas y muestra su motivo. El panel incluye identificador, estado registrado, motivo, responsable y momento del registro, observaciones y reserva de origen cuando corresponde. Los bloqueos iniciados o terminados se consultan sin acciones; su condición horaria no cambia el estado registrado ni finaliza el evento.

Anular y bloquear sobre una reserva futura exige el motivo de anulación de al menos 25 caracteres y el motivo del bloqueo. La confirmación identifica la reserva, su organizador y el turno. Dentro de una única transacción comprueba el acceso administrativo, las instalaciones activas, el horario de funcionamiento, el inicio futuro y la ocupación confirmada; anula la reserva, comprueba el turno libre y registra el bloqueo con su origen. Un fallo revierte también la anulación. Si la actividad cambió, exige revisar la selección y no anula la actividad nueva.

Anular y liberar un bloqueo exige motivo en texto libre y un inicio futuro. Conserva el bloqueo, su evento, el turno y el origen, y registra responsable, momento y motivo de anulación. No reactiva la reserva de origen. La operación no exige que la instalación permanezca activa. Se rechazan acciones repetidas, bloqueos iniciados y referencias a un bloqueo distinto del turno seleccionado.

Las operaciones se realizan desde el panel de Agenda, sin una sección independiente de bloqueos. Crear reserva y Crear bloqueo utilizan botones de contorno para desplegar los formularios, separados por una línea; Confirmar reserva y Confirmar bloqueo utilizan fondo violeta para destacar el envío de la operación. Sólo una acción del panel puede estar desplegada a la vez, por lo que abrir una cierra la anterior sin borrar los datos ingresados. Reutilizan la exclusión de ocupación del evento, bloquean el turno antes del evento y vuelven a validar permisos y límites horarios dentro de la transacción. La tarea de finalización de reservas no procesa bloqueos.

## 6. Acciones del día

La tarjeta del título de Agenda ofrece Acciones del día para la sede y fecha consultadas, desde hoy hasta un año después. Abre el mismo panel lateral utilizado por el detalle de turnos; la grilla permanece visible. Abrir, cerrar, revisar y volver a editar actualizan sólo el panel, sin desplazar la página. Seleccionar un turno reemplaza el contenido por su detalle. En pantallas pequeñas el panel se ubica debajo de la grilla. Permite seleccionar una o varias canchas y operar sobre el día completo o desde una hora de corte inclusiva. Sólo se actúa sobre turnos cuyo inicio sigue siendo futuro al confirmar. Un corte a las 18:30 incluye los turnos de las 19:00 en adelante.

Anular y liberar anula reservas y bloqueos elegibles, con opción de excluir cualquiera de esos tipos o ambos; los turnos libres no requieren acción. Admite instalaciones inactivas y conserva la historia. Anular y bloquear exige sede y canchas activas y turnos íntegramente contenidos en las franjas de funcionamiento: anula las reservas incluidas y crea un bloqueo independiente para cada turno efectivo, incluidos los libres. Permite excluir reservas y conserva los bloqueos existentes como ya cubiertos. Cada bloqueo que nace de una anulación registra su reserva de origen. Los turnos iniciados y eventos Finalizados se conservan; los eventos Anulados no ocupan turnos ni se procesan nuevamente.

El formulario recoge alcance, exclusiones y motivos. Exige un motivo de anulación si se anulan eventos y un mínimo de 25 caracteres si incluye reservas. Los bloqueos requieren su motivo clasificado y admiten observaciones comunes. La vista previa no escribe turnos ni eventos. Presenta las cantidades y los listados desplegables de acciones y eventos conservados con su motivo. El formulario compacto utiliza listas desplegables para operación, canchas y horario. Canchas ofrece Todas las canchas de la sede y Seleccionar; la segunda opción permite marcar una o varias canchas. Horario ofrece Día completo y Desde las HH:00 para cada inicio habilitado de la fecha consultada que aún sea futuro; no ofrece turnos iniciados ni horas fuera de las franjas. La lista se calcula con el día de la semana y la hora local actual y se valida nuevamente al enviar. Si se elige un inicio, Hasta ofrece un fin opcional: sólo horas de finalización de turnos habilitados posteriores al inicio, incluida la hora de cierre. Las pausas entre franjas no agregan opciones. Sin fin indicado abarca el resto del día; con fin indicado sólo incluye turnos completos anteriores a ese límite. La vista previa, la edición y la confirmación conservan y validan ese intervalo. Permite volver a editar conservando los valores antes de confirmar. La confirmación efectiva mantiene el envío completo y la redirección a la agenda actualizada.

La confirmación utiliza una selección firmada, vinculada al actor, sede, fecha, parámetros y ocupación revisada, con validez de quince minutos. El servidor no acepta cambios de parámetros al confirmar. Dentro de una única transacción comprueba el acceso administrativo, bloquea sede, canchas, turnos y eventos en orden estable y vuelve a calcular el alcance. Si cambia la ocupación, las franjas o la elegibilidad, revierte todo y solicita revisar la vista previa. También comprueba al terminar que ningún turno efectivo haya alcanzado su hora de inicio. Cada acción reutiliza los servicios individuales de reservas y bloqueos; un error no deja anulaciones o bloqueos parciales ni sobrescribe auditoría ante una confirmación repetida.

Las clases se conservan mientras su módulo no esté implementado. El recorrido de operaciones masivas contempla su incorporación con las exclusiones y condiciones de la especificación completa.

## 7. Navegación del portal y consulta de reservas

Agenda es la entrada única para consultar sedes, canchas y horarios y registrar reservas. La cabecera y los inicios administrativo y del portal enlazan a Agenda. No hay una sección independiente de Reservas o Mis reservas. El panel de las reservas autorizadas ofrece detalle y comprobante; ambas pantallas conservan el acceso por identificador y validan permisos. La búsqueda dentro de Agenda, incluida la localización de eventos Anulados, está pendiente.

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

El navbar ofrece Inicio, Agenda, Clases y las herramientas administrativas disponibles según los roles y permisos vigentes. Clases mantiene un desplegable incluso con un solo destino: Planilla semanal para Administrador o Mi actividad para Profesor y Alumno. Mi actividad enlaza a la consulta de Actividad de clases del titular.

Administración agrupa Usuarios, Sedes y canchas, Feriados y Auditoría en ese orden. Sedes y canchas enlaza al listado de Sedes. Si sólo hay un destino administrativo autorizado, se presenta directamente. Mi perfil y Cerrar sesión permanecen disponibles en la navegación.

Las homes presentan una única grilla titulada Módulos del sistema, filtrada por los permisos de los destinos: Agenda, Usuarios, Sedes y canchas, Clases y Auditoría. Cada tarjeta con destino tiene un único botón con el mismo estilo. Clases conserva su descripción del módulo y ofrece Ver planilla semanal para Administrador o Mi actividad para Profesor y Alumno. Feriados se accede desde el navbar, sin tarjeta en la home. Membresías y Pagos e ingresos aparecen al final de la home administrativa como En preparación, sin botones ni entradas en el navbar.

La ruta actual resalta el destino o su grupo. Los desplegables abren con clic, Enter o Espacio; las flechas recorren sus enlaces y Escape cierra devolviendo el foco al disparador. En móvil se expanden dentro de la navegación vertical. Las rutas mantienen las autorizaciones del servidor.
