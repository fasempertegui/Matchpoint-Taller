# Avance del proyecto

## Academia de Tenis TM

El proyecto es una aplicación para administrar una academia de tenis. El sistema completo contempla instalaciones, usuarios, clases, asistencia, membresías, reservas e ingresos. La aplicación utiliza Python, Django y PostgreSQL, con ejecución mediante Docker Compose.

Este documento describe las funcionalidades implementadas y el trabajo pendiente para el hito 3. La propuesta de la entrega se desarrolla en [Propuesta hito 3](Propuesta%20hito%203.md).

## 1. Hito 1: sedes y canchas

La aplicación cuenta con alta, consulta, modificación, activación y desactivación de sedes y canchas. La baja es lógica: los registros se conservan con estado inactivo.

Cada cancha pertenece a una sede y tiene un nombre, un tipo de superficie y observaciones opcionales. Se valida que no existan nombres de sedes duplicados ni nombres de canchas repetidos dentro de una misma sede, sin distinguir mayúsculas y minúsculas.

## 2. Hito 2: usuarios y seguridad

La aplicación permite registrar usuarios desde la administración y mediante autorregistro. Cuenta con consulta y búsqueda, modificación del correo, activación y desactivación, y restablecimiento administrativo de contraseñas.

El nombre de usuario se genera automáticamente a partir del apellido y la inicial del nombre. Se comprueba su disponibilidad y se agrega un número cuando es necesario. La fecha de nacimiento es obligatoria y los nombres y apellidos no admiten números. Se valida el formato del correo y que no esté registrado por otro usuario. El celular debe ser un número móvil argentino válido.

La autenticación incluye inicio y cierre de sesión y cambio de contraseña. Las contraseñas se almacenan mediante hash. Las cuentas creadas por otra persona y las cuentas con contraseña restablecida deben reemplazar la contraseña provisoria antes de acceder a las operaciones habituales. La nueva contraseña debe ser diferente de la vigente.

Existen los roles Administrador, Profesor, Alumno, Reservas y Público. Público y Reservas se asignan automáticamente al crear un usuario. La administración permite asignar y retirar Profesor, Alumno y Reservas. El rol Administrador se establece mediante el comando de creación de administradores.

La desactivación registra fecha y hora de baja; la reactivación elimina esa marca. Una persona no puede desactivar su propia cuenta y debe conservarse al menos un administrador activo.

La aplicación dispone de una página de inicio administrativa y una página de inicio para el portal. Desde el portal se puede consultar el perfil propio. Las pantallas utilizan estilos visuales compartidos.

## 3. Funcionalidades disponibles para el hito 3

### Horarios de funcionamiento

Cada sede permite configurar hasta dos franjas de funcionamiento por día de la semana. Se validan intervalos completos, horas de fin posteriores al inicio y ausencia de superposición entre franjas. Un día sin franjas configuradas queda sin funcionamiento.

La configuración está disponible desde el detalle de la sede y su administración está restringida al Administrador.

### Precios de reservas

La configuración de precios está disponible en la pestaña Precios de reservas del detalle de cada sede. La tabla muestra importes, estados y fechas de creación y desactivación, y permite filtrar por estado. Se puede crear un precio si no existe uno activo o actualizar el vigente desde su fila.

Cada precio pertenece a una sede y tiene un importe positivo por turno de una hora, común a todas sus canchas. El total de una reserva se calcula multiplicando ese importe por la cantidad de turnos.

Sólo puede existir un precio activo por sede; esta condición está garantizada en la base de datos. Actualizar desactiva el precio actual y crea un registro nuevo en una única transacción, bloqueando la sede para coordinar operaciones simultáneas. Un importe igual al actual se rechaza sin guardar cambios. Los precios inactivos quedan disponibles para consulta y no pueden editarse ni reactivarse. Las operaciones están restringidas al Administrador.

### Modelo de reservas

El modelo cuenta con las tablas Turno, Reserva y ReservaTurno. Un turno identifica una cancha, una fecha y un intervalo de una hora. La reserva es la cabecera: guarda el organizador, el usuario que registra, el precio aplicado, las observaciones y el estado. Cada detalle vincula la reserva con uno de sus turnos.

La base de datos impide repetir un turno para la misma cancha, fecha y hora de inicio, y repetir un mismo turno dentro de una reserva. También exige que los turnos comiencen en punto, duren exactamente una hora y terminen dentro de la misma fecha.

La reserva tiene estado inicial Programada y fecha de registración automática. Los estados permitidos son Programada, Anulada y Finalizada. La base exige fecha, responsable y motivo con contenido para una anulación, y fecha y responsable para una finalización. Estos datos sólo pueden estar presentes en el estado correspondiente. Las relaciones protegen los registros vinculados contra la eliminación física.

La anulación, la finalización y la impresión están pendientes de implementación.

### Turnos y disponibilidad

El backend prepara y consulta los turnos disponibles para una cancha y fecha de uso. La fecha debe estar entre hoy y catorce días después, inclusive, y la sede y la cancha deben estar activas. La sede necesita un precio vigente.

Al enviar la consulta se preparan los turnos faltantes de esa cancha y fecha, dentro de una transacción que bloquea la sede y la cancha. Se generan únicamente horas completas que comiencen en punto y estén dentro de una franja de funcionamiento. La consulta conserva todos los turnos existentes y no registra ni ocupa una reserva.

El resultado contiene los turnos futuros y libres. Las reservas Programadas y Finalizadas ocupan sus turnos; las Anuladas dejan de contarse como ocupación. Se aplican los horarios actuales de la sede: los turnos que queden fuera de ellos se conservan, pero no se ofrecen. Un día sin horario configurado no tiene disponibilidad.

### Registro de reservas

Nueva reserva está disponible desde el inicio administrativo y el portal. El Administrador selecciona un organizador activo; el usuario con rol Reservas reserva para sí mismo. El formulario muestra organizador, sede y canchas en una columna, y el calendario y los turnos en otra. El calendario habilita las fechas dentro del rango permitido y las canchas se ofrecen según la sede seleccionada.

El usuario marca uno, dos o más turnos consecutivos de la misma cancha y fecha, dentro de una misma franja de funcionamiento. La cantidad de horas y el total se obtienen de la selección. Cada turno tiene el importe vigente de la sede. El total se actualiza en el navegador y se pide confirmación mediante un diálogo antes de enviar el registro.

Cada turno se muestra como una opción con su rango horario. El precio por turno aparece una sola vez junto al total de la selección.

El servidor comprueba la selección, los permisos, los estados de usuarios e instalaciones, los horarios y el precio dentro de una transacción. Bloquea las cuentas participantes, la sede, la cancha y los turnos seleccionados; vuelve a comprobar la ocupación antes de guardar. Crea una cabecera en estado Programada y todos sus detalles, con número, fecha y responsable automáticos. Si falla la operación, no queda una reserva parcial. Si cambió el precio, se muestra el actualizado y se exige una nueva confirmación.

El detalle de la reserva muestra organizador, responsable, fecha de registro, cancha, fecha de uso, duración, turnos, subtotales y total. El Administrador puede consultar cualquier reserva; el usuario con rol Reservas sólo puede acceder a las propias. Los importes se obtienen del precio referenciado por la cabecera y la cantidad de detalles. El rol Reservas no puede retirarse mientras el usuario tenga reservas propias Programadas; esta comprobación se coordina con el registro mediante el bloqueo de su cuenta.

### Consulta de reservas

El inicio administrativo ofrece Consultar reservas y el portal ofrece Mis reservas. El listado utiliza las tablas y los estilos compartidos del proyecto. Muestra número, sede, cancha, fecha de uso, horario completo, total, estado y acceso al detalle. El Administrador ve todas las reservas y el organizador de cada una; el usuario con rol Reservas sólo obtiene las propias.

Los filtros son opcionales: sede, cancha, fecha de uso desde, fecha de uso hasta y estado. Las fechas se eligen mediante selectores y permiten consultar un día o un rango, incluidos registros históricos. Sus límites son inclusivos; la fecha hasta no puede ser anterior a la fecha desde. La acción Limpiar vuelve al listado sin filtros.

El selector de cancha se habilita al elegir una sede y ofrece sólo sus canchas. Al cambiar la sede, se descarta una cancha que no le pertenezca. El servidor valida los identificadores, la pertenencia de la cancha, las fechas y el estado; ante filtros inválidos muestra los errores y no devuelve resultados. Las opciones incluyen sedes y canchas inactivas para conservar la consulta de reservas históricas.

Cada reserva aparece una sola vez, aunque incluya varios turnos. El horario y el total se obtienen de todos sus detalles y del precio aplicado al registrarla. El detalle muestra también los datos de anulación o finalización cuando corresponden y permite volver al listado.
