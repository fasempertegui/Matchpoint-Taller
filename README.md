# Guía de instalación y ejecución

Ejecutar los siguientes comandos desde la consola.

## Primera ejecución

1. Construir e iniciar el proyecto:

   ```powershell
   docker compose up --build -d
   ```

2. Ejecutar las migraciones de Django:

   ```powershell
   docker compose exec web python manage.py migrate
   ```

3. Crear el usuario administrador:

   ```powershell
   docker compose exec web python manage.py crear_administrador
   ```

   La contraseña ingresada es provisoria. El administrador deberá reemplazarla en su primer inicio de sesión antes de acceder a las funciones del sistema.

4. Abrir la aplicación en <http://localhost:8000/>.

## Actualizar el proyecto

1. Descargar los cambios:

   ```powershell
   git pull
   ```

   Los cambios de código y HTML se aplican automáticamente, sin reconstruir los contenedores.

2. Si el pull incluye migraciones nuevas, ejecutarlas:

   ```powershell
   docker compose exec web python manage.py migrate
   ```

## Detener el proyecto

```powershell
docker compose stop
```

## Iniciar el proyecto nuevamente

```powershell
docker compose start
```
