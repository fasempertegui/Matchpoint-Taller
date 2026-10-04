# Avance del proyecto

## Academia de Tenis TM

La aplicación administra una academia de tenis mediante Python, Django y PostgreSQL, con ejecución en Docker Compose. El sistema completo contempla instalaciones, usuarios, clases, asistencia, membresías, reservas e ingresos.

## 1. Hito 1: sedes y canchas

Se dispone de alta, consulta, modificación, activación y desactivación de sedes y canchas. La baja es lógica y conserva los registros.

Cada cancha pertenece a una sede y tiene nombre, superficie y observaciones opcionales. No se permiten nombres de sedes duplicados ni nombres de canchas repetidos dentro de una sede, sin distinguir mayúsculas y minúsculas.

## 2. Hito 2: usuarios y seguridad

Se permite registrar usuarios desde la administración y mediante autorregistro, consultarlos, buscarlos, modificar su correo y activar o desactivar sus cuentas. También se puede consultar el perfil propio y restablecer administrativamente una contraseña.

El nombre de usuario se genera a partir del apellido y la inicial del nombre, agregando un número si es necesario. Se exige fecha de nacimiento, nombres y apellidos sin números, correo válido y único, y celular móvil argentino válido.

La autenticación incluye inicio y cierre de sesión y cambio de contraseña. Las contraseñas se almacenan mediante hash. Las cuentas creadas por otra persona o con contraseña restablecida deben reemplazar la contraseña provisoria antes de operar; la nueva debe ser diferente de la vigente.

Los roles son Administrador, Profesor, Alumno, Reservas y Público. Público y Reservas se asignan al crear un usuario. La administración puede asignar y retirar Profesor, Alumno y Reservas; Administrador se establece mediante el comando de creación de administradores.

Desactivar registra fecha y hora de baja; reactivar elimina esa marca. No se permite desactivar la cuenta propia ni al último administrador activo.

## 3. Hito 3: proceso de reservas

### Horarios y precios

El Administrador puede configurar hasta dos franjas de funcionamiento por día para cada sede. Los intervalos deben estar completos, terminar después de comenzar y no superponerse. Un día sin franjas no tiene disponibilidad.

Cada sede tiene un único precio activo, positivo y común a todas sus canchas, por turno de una hora. El Administrador puede crearlo o actualizarlo. Actualizar desactiva el precio vigente y crea otro en una única transacción; no se admite repetir el importe actual. Los precios inactivos se conservan para consulta y no pueden editarse ni reactivarse.

### Cabecera y detalles

El proceso utiliza las tablas Turno, Reserva y ReservaTurno, relacionadas con usuarios, canchas y precios. Cada Turno representa una hora de una cancha en una fecha. Reserva es la cabecera y guarda organizador, responsable del registro, precio aplicado, observaciones y estado. Cada ReservaTurno es un detalle que vincula la cabecera con un turno.

La base de datos impide duplicar turnos para una cancha, fecha y hora, o repetir un turno dentro de una reserva. Exige horas de inicio en punto, duración de una hora y finalización dentro de la misma fecha. Las relaciones protegen los registros vinculados contra la eliminación física.

Los estados son Programada, Anulada y Finalizada. Se exigen los datos de auditoría correspondientes a cada estado.

### Disponibilidad

Se preparan y consultan turnos para una cancha y fecha entre hoy y catorce días después, inclusive. La sede y la cancha deben estar activas, y la sede debe tener un precio vigente.

Los turnos faltantes se generan dentro de una transacción, según las franjas actuales de funcionamiento. Sólo se ofrecen turnos futuros y libres. Preparar turnos no registra una reserva ni ocupa horarios.

Las reservas Programadas y Finalizadas ocupan sus turnos; las Anuladas los liberan. Los turnos existentes fuera de los horarios actuales se conservan, pero no se ofrecen.

### Registro

El Administrador puede registrar una reserva para un organizador activo. El usuario con rol Reservas sólo puede reservar para sí mismo. Los datos relacionados se seleccionan entre las opciones disponibles, sin ingresar claves foráneas manualmente.

Se admite uno o más turnos consecutivos de una misma cancha y fecha, dentro de una única franja de funcionamiento. La duración, los subtotales y el total se calculan automáticamente con el precio de la sede y la cantidad de turnos.

El servidor valida permisos, selección, estados, horarios, precio y disponibilidad dentro de una transacción, con bloqueos para coordinar solicitudes simultáneas. Registra la cabecera en estado Programada y todos sus detalles, con número, fecha y usuario responsable automáticos. Ante un error, no queda una reserva parcial. Si cambia el precio antes del registro, se exige revisar el importe y confirmar nuevamente.

El precio aplicado se conserva como referencia histórica. No se permite retirar el rol Reservas a un usuario con reservas propias Programadas.

### Consulta

El Administrador puede consultar todas las reservas; el usuario con rol Reservas, sólo las propias. Se permite filtrar por sede, cancha, rango inclusivo de fechas de uso y estado. La cancha debe pertenecer a la sede seleccionada y la fecha final no puede ser anterior a la inicial. Los filtros inválidos se rechazan. Se incluyen instalaciones inactivas para consultar registros históricos.

Cada reserva se presenta una sola vez, con número, organizador según el permiso, sede, cancha, fecha de uso, horario, total y estado. El detalle incluye los turnos, subtotales, precio aplicado, datos del registro y datos de anulación o finalización cuando corresponden.

### Anulación

El Administrador puede anular cualquier reserva Programada antes de que comience su primer turno. El usuario con rol Reservas puede anular únicamente las propias con al menos una hora de antelación al primer turno. El motivo es obligatorio y debe tener contenido.

La operación cambia el estado a Anulada, registra motivo, fecha, hora y responsable, y libera todos sus turnos. Conserva la cabecera, los detalles y el precio aplicado. Se ejecuta en una única transacción, validando nuevamente permisos, estado y horario después de obtener los bloqueos.

Se rechazan reservas iniciadas, Anuladas o Finalizadas, solicitudes sobre reservas ajenas desde el portal y anulaciones propias fuera del plazo. Una solicitud repetida no sobrescribe la auditoría. El actor debe conservar el acceso habilitado; el Administrador puede operar aunque el organizador esté inactivo. No se exige que las instalaciones o el precio sigan activos. Ante un error, no se modifica la reserva ni su ocupación.

### Finalización

Sólo el Administrador puede finalizar una reserva Programada cuando terminó su último turno. El paso del tiempo no cambia el estado automáticamente.

La operación registra estado Finalizada, fecha, hora y responsable en una única transacción. Conserva los detalles, el precio y la ocupación histórica, aunque los registros relacionados estén inactivos. Se rechazan reservas que no terminaron, Anuladas o Finalizadas, sin sobrescribir datos ante solicitudes repetidas.

### Comprobante

Se dispone de un comprobante imprimible o guardable como PDF con número, estado, organizador, responsable, fecha de registro, sede, cancha, fecha de uso, duración, precio aplicado, turnos, subtotales y total. Incluye observaciones y datos de anulación o finalización cuando corresponden.

El Administrador puede emitir cualquier comprobante y el usuario con rol Reservas sólo los propios. Emitirlo no modifica la reserva ni crea registros adicionales. Acredita el registro de la reserva, no un pago.
