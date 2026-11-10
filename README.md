# Guía de instalación y ejecución

Ejecutar desde la carpeta del proyecto, con Docker iniciado. Los servicios se manejan todos juntos.

## Primera ejecución

1. Construir e iniciar todo:

   ```powershell
   docker compose up --build -d
   ```

   Las migraciones se ejecutan automáticamente y se cargan sedes y usuarios de prueba. Los usuarios de ejemplo, incluido el administrador de ejemplo, tienen el correo verificado y pueden usarse directamente.

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

La aplicación usa `mailpit:1025`, sin autenticación ni TLS, e ignora las credenciales de Gmail mientras la simulación está activa. Esas credenciales se conservan en el entorno. Los mensajes de Mailpit persisten en un volumen propio y la bandeja sólo es accesible desde esta computadora.

La simulación no habilita las campañas programadas ni la limpieza de cuentas. Las pruebas automatizadas siguen usando correo en memoria.

Para salir de la simulación, configurar `EMAILS_SIMULACION=0` en `.env` y recrear los servicios:

```powershell
docker compose up -d --no-deps --force-recreate web worker beat
```

Los envíos reales requieren además configurar el proveedor y habilitar explícitamente `EMAILS_HABILITADOS=1` y `EMAILS_ENTREGA_EXTERNA_HABILITADA=1`. Los recordatorios y encuestas programados se habilitan por separado con `EMAILS_TAREAS_PROGRAMADAS_HABILITADAS=1`.

## Consultar registros

```powershell
docker compose logs --tail=50
```
