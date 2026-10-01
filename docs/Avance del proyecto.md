# Avance del proyecto
## Academia de Tenis TM

El proyecto consiste en desarrollar un sistema para la administración de una academia de tenis. Su alcance contempla sedes y canchas, usuarios, clases, asistencia, pagos y reservas. El desarrollo se organiza por hitos, incorporando las funcionalidades solicitadas en cada entrega.

## Hito 1: sedes y canchas

En el primer hito se desarrolló el ABM de sedes y canchas, como base para registrar las instalaciones de la academia. Se implementaron los formularios de alta y modificación, las consultas y la baja lógica mediante la desactivación de los registros.

Cada cancha quedó vinculada a una sede, con sus datos de identificación y tipo de superficie. Se incorporaron validaciones para evitar nombres de sedes duplicados y nombres de canchas repetidos dentro de una misma sede.

Esta etapa estableció la base de la aplicación y la persistencia de los datos, utilizando Python, Django y PostgreSQL.

## Hito 2: usuarios y seguridad

En el segundo hito se incorporó la gestión de usuarios y el control de acceso al sistema. Se desarrollaron el alta, la consulta, la modificación del correo y la baja lógica de usuarios. Las modificaciones registran automáticamente su fecha y la baja conserva los datos del usuario, indicando su estado inactivo y la fecha de desactivación.

También se implementaron el inicio y cierre de sesión y el restablecimiento administrativo de contraseñas. Las contraseñas se almacenan mediante hash y las cuentas creadas por un administrador, o cuya contraseña fue restablecida, deben reemplazar la contraseña provisoria en el siguiente ingreso.

Se incorporaron los roles Administrador, Profesor, Alumno, Reservas y Público, junto con los controles de permisos para acceder a las operaciones disponibles. Así, la administración de sedes y canchas quedó integrada con la autenticación y la seguridad del sistema.

## Ajustes posteriores a la devolución del hito 2

- **Generación de usuarios:** el nombre de usuario pasó a generarse automáticamente con el apellido y la inicial del nombre, agregando un número cuando existe una coincidencia. El campo se muestra sin permitir su edición.
- **Validaciones y contraseñas:** se corrigió la aceptación de números en nombres y apellidos, se hizo obligatoria la fecha de nacimiento y se impidió utilizar la contraseña vigente como nueva contraseña.
- **Interfaz y navegación:** se incorporaron páginas de inicio para el portal y la administración, se unificaron colores, tipografías y logotipo, y se mejoraron formularios, mensajes y accesos a las acciones desde las pantallas de detalle.

Estos ajustes forman parte de la revisión del hito 2 y consolidan las funcionalidades de instalaciones, usuarios y seguridad desarrolladas hasta esta etapa.

## Hito 3: reservas

Para el tercer hito se acordó desarrollar el proceso completo de reservas normales de cancha, desde su registración hasta su finalización o anulación, con consulta y comprobante imprimible. El módulo de reservas y el ABM de precios por duración están pendientes.

La configuración de horarios por sede permite definir hasta dos franjas por día, con validaciones de intervalos completos y sin superposiciones. Los días sin franjas quedan sin funcionamiento. Su administración está restringida al Administrador.

Cada reserva tendrá una cabecera y un detalle con uno o varios turnos, relacionados con usuarios, canchas y tarifas. El número de comprobante, la fecha de registración, el usuario responsable y el estado inicial Programada serán automáticos. El sistema calculará horarios e importes y registrará toda la operación mediante una transacción, validando disponibilidad para evitar superposiciones.

La consulta permitirá filtrar por rango de fechas, estado, organizador, sede y cancha, y visualizar el detalle. El rol Reservas podrá registrar, consultar y emitir comprobantes de sus propias reservas; el Administrador tendrá acceso a todas.

La anulación quedará restringida al Administrador y registrará motivo, fecha y usuario, con estado Anulada. Liberará todos los turnos en una transacción, conservando los registros. La finalización también será administrativa y sólo podrá realizarse cuando hayan terminado todos los turnos.

Esta adaptación agrupa varios turnos en lugar del único evento previsto en la documentación y utiliza Anulada como estado de baja. La anulación propia, los bloqueos por cancelación y la reprogramación quedan fuera de esta entrega, junto con pases, invitados, ingresos, notificaciones y finalización automática. Los documentos del sistema completo conservan su alcance; estas diferencias se registran únicamente aquí.
