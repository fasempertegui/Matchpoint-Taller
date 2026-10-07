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

Desactivar registra fecha y hora de baja; reactivar elimina esa marca. No se permite desactivar la cuenta propia ni al último administrador activo.

## 3. Hito 3: proceso de reservas

### Horarios y precios

El Administrador puede configurar hasta dos franjas de funcionamiento por día para cada sede. Los horarios deben ser en punto, los intervalos deben estar completos y terminar después de comenzar. Si hay dos franjas, debe existir al menos una hora sin funcionamiento entre ellas. Estas condiciones se validan en el formulario y en la base de datos. Un día sin franjas no tiene disponibilidad.

Cada sede guarda una tarifa vigente, positiva y común a todas sus canchas, por turno de una hora. El Administrador puede configurarla o actualizarla. Guardar modifica el valor de la sede dentro de una transacción; se rechazan importes iguales al actual y cambios concurrentes que requieren revisar nuevamente el precio.

### Cabecera y detalles

El proceso utiliza Turno, Evento, EventoTurno y Reserva. Turno identifica una hora de una cancha en una fecha; su fin se calcula desde el inicio. Evento concentra estado, observaciones y auditoría. Reserva referencia un único evento y guarda organizador, precio por turno aplicado y origen de la anulación. EventoTurno vincula cada evento con todos los turnos que utiliza.

La base de datos impide duplicar turnos para una cancha, fecha y hora, o repetir un turno dentro de un evento. Exige inicios en punto entre las 00:00 y las 22:00; la duración fija de una hora determina el fin dentro de la misma fecha. Las relaciones protegen los registros vinculados contra la eliminación física.

Los estados del evento son Programado, Anulado y Finalizado, con auditoría coherente para cada caso. La base común admite los tipos Reserva, Clase y Bloqueo; el proceso implementado registra reservas. El registro crea evento, reserva y vínculos horarios en una única transacción.

### Disponibilidad

Se preparan y consultan turnos para una cancha y fecha entre hoy y catorce días después, inclusive. La sede y la cancha deben estar activas, y la sede debe tener una tarifa vigente configurada.

Los turnos faltantes se generan dentro de una transacción, según las franjas actuales de funcionamiento. Sólo se ofrecen turnos futuros y libres. Preparar turnos no registra una reserva ni ocupa horarios.

Los eventos Programados y Finalizados ocupan sus turnos; los Anulados los liberan. La disponibilidad consulta esa relación común y conserva los vínculos históricos. Los turnos existentes fuera de los horarios actuales se conservan, pero no se ofrecen.

### Registro

El Administrador puede registrar una reserva para un organizador activo con rol Reservas o Administrador. La selección y la confirmación validan esas condiciones; registrar una reserva no asigna roles automáticamente. El usuario con rol Reservas sólo puede reservar para sí mismo. Los datos relacionados se seleccionan entre las opciones disponibles, sin ingresar claves foráneas manualmente.

Se admite uno o más turnos consecutivos de una misma cancha y fecha, dentro de una única franja de funcionamiento. La duración, los subtotales y el total se calculan automáticamente con el precio de la sede y la cantidad de turnos.

El servidor valida permisos, selección, estados, horarios, precio y disponibilidad dentro de una transacción, con bloqueos para coordinar solicitudes simultáneas. Registra la reserva y su evento Programado con todos los vínculos horarios, número, fecha y usuario responsable automáticos. Ante un error, no queda una reserva parcial. Si cambia el precio antes del registro, se exige revisar el importe y confirmar nuevamente.

El importe por turno se copia desde la tarifa validada de la sede al registrar y se conserva en la reserva. El total se calcula con ese importe y la cantidad de turnos; actualizar la tarifa no modifica reservas existentes. No se permite retirar el rol Reservas a un usuario con reservas propias Programadas.

### Consulta

El Administrador puede consultar todas las reservas; el usuario con rol Reservas, sólo las propias. Se permite filtrar por sede, cancha, rango inclusivo de fechas de uso y estado. La cancha debe pertenecer a la sede seleccionada y la fecha final no puede ser anterior a la inicial. Los filtros inválidos se rechazan. Se incluyen instalaciones inactivas para consultar registros históricos.

Cada reserva se presenta una sola vez, con número, organizador según el permiso, sede, cancha, fecha de uso, horario, total y estado. El detalle incluye los turnos, subtotales, precio aplicado, datos del registro y datos de anulación o finalización cuando corresponden.

### Anulación

El Administrador puede anular cualquier reserva Programada antes de que comience su primer turno. El usuario con rol Reservas puede anular únicamente las propias con al menos una hora de antelación al primer turno. El motivo es obligatorio y debe tener al menos 25 caracteres, sin contar los espacios al principio y al final. El formulario y el procesamiento de la anulación validan ese mínimo.

La operación cambia el evento a Anulado, registra motivo, fecha, hora y responsable, y libera todos sus turnos. Guarda en la reserva si la anulación corresponde al organizador o a la administración. Conserva reserva, evento, vínculos horarios e importe aplicado. Se ejecuta en una única transacción, validando nuevamente permisos, estado y horario después de obtener los bloqueos.

Se rechazan reservas iniciadas, Anuladas o Finalizadas, solicitudes sobre reservas ajenas desde el portal y anulaciones propias fuera del plazo. Una solicitud repetida no sobrescribe la auditoría. El actor debe conservar el acceso habilitado; el Administrador puede operar aunque el organizador esté inactivo. No se exige que las instalaciones o el precio sigan activos. Ante un error, no se modifica la reserva ni su ocupación.

### Finalización

Celery finaliza automáticamente las reservas Programadas cada hora en punto cuando la fecha y hora de fin de su último turno es igual o anterior al momento actual. El Administrador también puede finalizar una reserva vencida como acción de emergencia, con las mismas condiciones y sin depender de Celery ni Redis.

Cada reserva se procesa en una transacción, comprobando nuevamente el estado y horario después de bloquear los turnos y el evento. Registra estado Finalizado, fecha y hora de procesamiento en el evento, sin responsable. Conserva los vínculos horarios, el precio y la ocupación histórica, aunque los registros relacionados estén inactivos. No modifica reservas que no terminaron, Anuladas o Finalizadas, ni sobrescribe datos ante ejecuciones repetidas. La siguiente ejecución procesa todas las vencidas que sigan pendientes.

### Comprobante

Se dispone de un comprobante imprimible o guardable como PDF con número, estado, organizador, responsable, fecha de registro, sede, cancha, fecha de uso, duración, precio aplicado, turnos, subtotales y total. Incluye observaciones y datos de anulación o finalización cuando corresponden.

El Administrador puede emitir cualquier comprobante y el usuario con rol Reservas sólo los propios. Emitirlo no modifica la reserva ni crea registros adicionales. Acredita el registro de la reserva, no un pago.
