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

        FOR cancha_numero IN 1..(CASE sede_numero WHEN 1 THEN 3 ELSE 2 END) LOOP
            INSERT INTO canchas (sede_id, nombre, superficie, observaciones, estado, creado_en, actualizado_en)
            VALUES (sede_id, 'Cancha ' || cancha_numero,
                CASE sede_numero WHEN 1 THEN 'cemento' ELSE 'polvo_ladrillo' END,
                '', 'activa', now(), now());
        END LOOP;
    END LOOP;
    RAISE NOTICE 'Datos de ejemplo cargados.';
END;
$$;
