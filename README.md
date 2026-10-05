# Guía de instalación y ejecución

Ejecutar los siguientes comandos desde la consola.

## Primera ejecución

1. Construir e iniciar el proyecto:

   ```powershell
   docker compose up --build -d db redis web adminer
   ```

2. Ejecutar las migraciones de Django:

   ```powershell
   docker compose exec web python manage.py migrate
   ```

3. Iniciar los procesos de tareas:

   ```powershell
   docker compose up -d worker beat
   ```

4. Crear el usuario administrador:

   ```powershell
   docker compose exec web python manage.py crear_administrador
   ```

5. Abrir la aplicación en <http://localhost:8000/>.

## Actualizar el proyecto

1. Detener los procesos de tareas y descargar los cambios:

   ```powershell
   docker compose stop worker beat
   git pull
   ```

   Los cambios de código y HTML se aplican automáticamente al servicio web. Si cambian dependencias o la configuración de contenedores, reconstruir e iniciar los servicios de aplicación:

   ```powershell
   docker compose up --build -d db redis web adminer
   ```

2. Si el pull incluye migraciones nuevas, ejecutarlas:

   ```powershell
   docker compose exec web python manage.py migrate
   ```

3. Iniciar los procesos de tareas con el código vigente:

   ```powershell
   docker compose up -d worker beat
   docker compose restart worker beat
   ```

## Tareas automáticas

Redis transporta las tareas, Celery Worker las ejecuta y Celery Beat programa la finalización de reservas cada hora en punto, según la zona horaria de Buenos Aires. Sólo debe ejecutarse una instancia de Beat. Las reservas Programadas pasan a Finalizadas cuando terminó su último turno; la tarea conserva la fecha y hora de finalización y no modifica reservas Anuladas o Finalizadas.

Los servicios deben permanecer encendidos para que la ejecución sea automática. La siguiente ejecución horaria procesa todas las reservas vencidas pendientes. Redis y la agenda de Beat utilizan volúmenes persistentes.

Para consultar los registros de ejecución:

```powershell
docker compose logs --tail=50 worker beat
```

## Detener el proyecto

```powershell
docker compose stop
```

## Iniciar el proyecto nuevamente

```powershell
docker compose start
```
