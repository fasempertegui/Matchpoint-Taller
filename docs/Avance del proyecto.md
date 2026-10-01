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
