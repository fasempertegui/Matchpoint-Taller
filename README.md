# Guía de instalación y ejecución

Ejecutar desde la carpeta del proyecto, con Docker iniciado. Los servicios se manejan todos juntos.

## Primera ejecución

1. Construir e iniciar todo:

   ```powershell
   docker compose up --build -d
   ```

   Las migraciones y la carga completa de demostración se ejecutan automáticamente: dos sedes, cuatro canchas, un administrador, 90 usuarios adicionales, ocho planes, dos membresías, contrataciones, clases, asistencias, reservas, bloqueos y pagos. La primera carga puede demorar varios minutos. Los usuarios de ejemplo tienen el correo verificado y pueden usarse directamente. Los reinicios conservan los datos sin duplicarlos.

2. Crear el administrador:

   ```powershell
   docker compose exec web python manage.py crear_administrador
   ```

3. Abrir <http://localhost:8000/>.

## Actualizar conservando los datos

```powershell
docker compose down
git pull
docker compose up --build -d
```

Las migraciones se aplican automáticamente. Los datos existentes se conservan.

## Detener todo

```powershell
docker compose stop
```

Para volver a iniciar:

```powershell
docker compose start
```

## Correos de prueba con Mailpit

Docker Compose habilita la simulación por defecto con `EMAILS_SIMULACION=1`. Todos los correos llegan a la bandeja local en <http://localhost:8025/>, independientemente del destinatario: nadie los recibe en su casilla real. Podés consultar el HTML, el texto y abrir los enlaces.

## Límites de autenticación

`REDIS_LIMITES_URL` configura la caché compartida para los contadores. Docker Compose usa la base 1 del servicio Redis y Celery usa la base 0. Los límites por IP usan `REMOTE_ADDR`. Si el despliegue incorpora un proxy, la integración con Django debe establecer ese valor a partir de una fuente confiable para que represente al cliente.

## Notificaciones internas

Cada cuenta activa y verificada, con su contraseña personal, consulta sus avisos desde Notificaciones en la cabecera. El contador muestra los no leídos. La bandeja y la lectura funcionan independientemente de la entrega de emails. Los enlaces de verificación, confirmación de correo y recuperación se reciben exclusivamente por correo.

Los recordatorios y las campañas de continuidad se revisan cada minuto y se programan con `NOTIFICACIONES_TAREAS_PROGRAMADAS_HABILITADAS=1`, habilitado por defecto. Requieren los servicios worker y beat activos. Los avisos se generan desde las operaciones y tareas funcionales; no se importan emails históricos a la bandeja.

Administración consulta los plazos desde **Reglas de notificación** en la navegación. Cada fila ofrece Modificar para abrir únicamente su campo y Guardar regla para aplicar ese cambio de forma independiente. Los valores iniciales son sesenta minutos para clases y reservas; continuidad abre el 25 y recuerda el último día del mes y el 5 siguiente, a las 09:00 de Salta. Los cambios se aplican sin reiniciar los servicios y también ajustan la ventana para responder continuidad.

## Consultar registros

```powershell
docker compose logs --tail=50
```
