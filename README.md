# Guía de instalación y ejecución

## Requisitos

- Git :)
- Docker :)
- No tener otros contenedores ocupando los puertos 8000, 8025 ni 8080

## Primera ejecucion

1. Clonar este repositorio en el directorio de tu preferencia
2. Ingresar a la carpeta del repositorio y abrir una consola
3. Ejecutar:

   ```bash
   docker compose up --build -d
   ```

4. Una vez que termine:
   - Sistema en `localhost:8000`
   - Mailpit en `localhost:8025`
   - Adminer en `localhost:8080`

> **Nota 1:** el administrador de prueba es el que ustedes conocen

> **Nota 2:** en `output/semilla/usuarios.txt` estan los usuarios con sus roles y contraseñas

## Actualizaciones

1. Ingresar a la carpeta del repositorio y abrir una consola
2. Ejecutar:

   ```bash
   docker compose down -v
   ```

3. Una vez que termine, ejecutar:

   ```bash
   git pull
   ```

4. Una vez que termine, ejecutar:

   ```bash
   docker compose up --build -d
   ```

5. Listo!

## Después

- Para detener:

   ```bash
   docker compose stop
   ```

- Para volver a arrancar:

   ```bash
   docker compose start
   ```

