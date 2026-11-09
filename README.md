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


## Emails

La cola persistente se registra en `envios_email`. Su migración es `comunicaciones/0001_initial`. La consulta administrativa de entregas requiere esa migración aplicada y está disponible en **Administración → Envíos de email**.

La configuración por entorno se comparte entre web, trabajador y Beat mediante `entorno_aplicacion` de Compose:

| Variable | Uso / valor predeterminado |
|---|---|
| `EMAILS_HABILITADOS` | Procesamiento y barrido de pendientes; `0`. |
| `EMAILS_ENTREGA_EXTERNA_HABILITADA` | Permite un backend distinto del correo en memoria; `0`. |
| `EMAILS_URL_PUBLICA` | Origen validado de enlaces; `http://localhost:8000`. |
| `EMAIL_BACKEND` | Backend de Django; correo en memoria. |
| `DEFAULT_FROM_EMAIL` | Remitente; `Academia TM <academia@localhost>`. |
| `EMAIL_HOST`, `EMAIL_PORT` | Servicio SMTP; localhost y 587. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciales externas; vacías. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | TLS explícito o SSL; `1` y `0`. |

Los secretos se suministran fuera del repositorio. Las pruebas usan PostgreSQL aislado y correo en memoria. La activación de entregas y tareas requiere completar y revisar los recorridos funcionales del plan de emails; desarrollar una etapa no activa entregas externas. El seguimiento indica aceptación del proveedor y no garantiza recepción ni lectura.
