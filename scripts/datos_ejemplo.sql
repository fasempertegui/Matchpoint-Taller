-- Ejecutar después de las migraciones, dentro de una transacción.
DO $$
DECLARE
    sede_id bigint;
    sede_numero integer;
    cancha_numero integer;
BEGIN
    PERFORM pg_advisory_xact_lock(734021, 1);
    IF EXISTS (SELECT 1 FROM sedes) THEN
        RAISE NOTICE 'Carga omitida: ya existen sedes.';
        RETURN;
    END IF;

    FOR sede_numero IN 1..2 LOOP
        INSERT INTO sedes (
            nombre, direccion, precio_reserva_vigente, observaciones, estado, creado_en, actualizado_en
        ) VALUES (
            CASE sede_numero WHEN 1 THEN 'Sociedad Española' ELSE 'Sirio Libanesa' END,
            CASE sede_numero WHEN 1 THEN 'Balcarce 643' ELSE 'San Martin 673' END,
            25000, '', 'activa', now(), now()
        ) RETURNING id INTO sede_id;

        INSERT INTO sedes_horarios (
            sede_id, dia_semana, hora_inicio_1, hora_fin_1, hora_inicio_2, hora_fin_2,
            creado_en, actualizado_en
        ) SELECT sede_id, numero, '08:00'::time, '13:00'::time, '16:00'::time, '23:00'::time,
            now(), now() FROM generate_series(1, 7) AS numero;

        FOR cancha_numero IN 1..2 LOOP
            INSERT INTO canchas (sede_id, nombre, superficie, observaciones, estado, creado_en, actualizado_en)
            VALUES (sede_id, 'Cancha ' || cancha_numero,
                CASE sede_numero WHEN 1 THEN 'cemento' ELSE 'polvo_ladrillo' END,
                '', 'activa', now(), now());
        END LOOP;
    END LOOP;
    RAISE NOTICE 'Datos de ejemplo cargados.';
END;
$$;

DO $$
DECLARE
    usuario_id bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(734021, 1);
    IF EXISTS (
        SELECT 1 FROM usuarios
        WHERE lower(username) = 'mamanit' OR lower(email) = 'mamanit@gmail.com'
    ) THEN
        RAISE NOTICE 'Administrador de ejemplo omitido: el usuario o email ya existe.';
        RETURN;
    END IF;

    INSERT INTO usuarios (
        username, first_name, last_name, email, password, fecha_nacimiento,
        celular_contacto, observaciones, debe_cambiar_contrasena, is_active,
        is_staff, is_superuser, correo_verificado_en, revision_correo, email_pendiente, date_joined, actualizado_en
    ) VALUES (
        'mamanit', 'Tomas', 'Mamani', 'mamanit@gmail.com',
        'pbkdf2_sha256$1000000$9WAvFtHttzDUqul2SRNGyK$DSmxFyt8hCORkgwKQJNoPwhjXPneiLWArdTdqXfpUhM=', '2000-01-01'::date,
        '3875001220', '', false, true, false, true, now(), 0, '', now(), now()
    ) RETURNING id INTO usuario_id;

    INSERT INTO usuarios_roles (usuario_id, rol_id, creado_en)
    SELECT usuario_id, id, now() FROM roles WHERE codigo = 'administrador';
    RAISE NOTICE 'Administrador de ejemplo creado.';
END;
$$;
