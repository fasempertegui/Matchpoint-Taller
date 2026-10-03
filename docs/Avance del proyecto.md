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
