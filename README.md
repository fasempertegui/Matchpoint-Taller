# Guía de instalación y ejecución

Ejecutar desde la carpeta del proyecto, con Docker iniciado. Los servicios se manejan todos juntos.

## Primera ejecución

1. Construir e iniciar todo:

   ```powershell
   docker compose up --build -d
   ```

   Las migraciones se ejecutan automáticamente y se cargan sedes y usuarios de prueba.

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

## Consultar registros

```powershell
docker compose logs --tail=50
```
