from django.db import migrations


TABLAS_AUDITADAS = (
    ("usuarios", ("id",)),
    ("roles", ("id",)),
    ("usuarios_roles", ("id",)),
    ("sedes", ("id",)),
    ("canchas", ("id",)),
    ("sedes_horarios", ("sede_id", "dia_semana")),
    ("turnos", ("id",)),
    ("eventos", ("id",)),
    ("reservas", ("id",)),
    ("bloqueos", ("id",)),
)

CREAR_FUNCIONES = """
CREATE FUNCTION registrar_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    registro_anterior jsonb := to_jsonb(OLD);
    registro_actual jsonb;
    anteriores jsonb;
    actuales jsonb;
    clave jsonb := '{}'::jsonb;
    campo text;
    accion_log text;
    origen_log text;
    usuario_log bigint;
    operacion_log uuid;
    cambio_contrasena boolean := false;
BEGIN
    FOREACH campo IN ARRAY TG_ARGV LOOP
        clave := clave || jsonb_build_object(campo, registro_anterior -> campo);
    END LOOP;

    IF TG_OP = 'DELETE' THEN
        accion_log := 'eliminacion';
        anteriores := registro_anterior - 'password';
        actuales := '{}'::jsonb;
    ELSE
        registro_actual := to_jsonb(NEW);
        cambio_contrasena := TG_TABLE_NAME = 'usuarios'
            AND registro_anterior -> 'password' IS DISTINCT FROM registro_actual -> 'password';

        SELECT COALESCE(jsonb_object_agg(anterior.key, anterior.value), '{}'::jsonb),
               COALESCE(jsonb_object_agg(anterior.key, registro_actual -> anterior.key), '{}'::jsonb)
        INTO anteriores, actuales
        FROM jsonb_each(registro_anterior - 'password') AS anterior
        WHERE anterior.value IS DISTINCT FROM registro_actual -> anterior.key;

        IF cambio_contrasena THEN
            anteriores := anteriores - 'actualizado_en';
            actuales := actuales - 'actualizado_en';
            accion_log := NULLIF(current_setting('auditoria.accion', true), '');
            IF accion_log IS NULL OR accion_log NOT IN (
                'cambio_contrasena', 'restablecimiento_contrasena', 'actualizacion_hash'
            ) THEN
                accion_log := 'cambio_contrasena';
            END IF;
        ELSE
            IF anteriores - 'actualizado_en' = '{}'::jsonb THEN
                RETURN NEW;
            END IF;
            IF (registro_actual ->> 'estado' = 'anulado'
                AND registro_anterior -> 'estado' IS DISTINCT FROM registro_actual -> 'estado')
                OR (TG_TABLE_NAME = 'reservas'
                    AND registro_actual ->> 'anulada_por_organizador' IS NOT NULL
                    AND registro_anterior -> 'anulada_por_organizador'
                        IS DISTINCT FROM registro_actual -> 'anulada_por_organizador')
            THEN
                accion_log := 'anulacion';
            ELSE
                accion_log := 'modificacion';
            END IF;
        END IF;
    END IF;

    origen_log := COALESCE(NULLIF(current_setting('auditoria.origen', true), ''), 'sql');
    usuario_log := NULLIF(current_setting('auditoria.usuario_id', true), '')::bigint;
    IF origen_log = 'autenticacion' AND TG_TABLE_NAME = 'usuarios' AND TG_OP = 'UPDATE' THEN
        origen_log := 'aplicacion';
        usuario_log := (registro_anterior ->> 'id')::bigint;
    END IF;

    operacion_log := NULLIF(current_setting('auditoria.operacion_id', true), '')::uuid;
    IF operacion_log IS NULL THEN
        operacion_log := gen_random_uuid();
        PERFORM set_config('auditoria.operacion_id', operacion_log::text, true);
    END IF;

    INSERT INTO log_auditoria (
        operacion_id, tabla, clave_registro, accion,
        valores_anteriores, valores_actuales, realizado_en,
        usuario_id, usuario_bd, origen
    ) VALUES (
        operacion_log, TG_TABLE_NAME, clave, accion_log,
        anteriores, actuales, clock_timestamp(),
        usuario_log, session_user, origen_log
    );
    RETURN NULL;
END;
$$;

CREATE FUNCTION proteger_log_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El historial de auditoría no admite modificación, eliminación ni vaciado.';
END;
$$;

CREATE TRIGGER proteger_log_auditoria
BEFORE UPDATE OR DELETE OR TRUNCATE ON log_auditoria
FOR EACH STATEMENT EXECUTE FUNCTION proteger_log_auditoria();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("auditoria", "0002_initial"),
        ("usuarios", "0002_cargar_roles"),
        ("instalaciones", "0001_initial"),
        ("reservas", "0002_initial"),
        ("bloqueos", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            CREAR_FUNCIONES,
            reverse_sql="""
                DROP TRIGGER proteger_log_auditoria ON log_auditoria;
                DROP FUNCTION proteger_log_auditoria();
                DROP FUNCTION registrar_auditoria();
            """,
        ),
        *[
            migrations.RunSQL(
                sql=f"""
                    CREATE TRIGGER auditar_{tabla}
                    AFTER UPDATE OR DELETE ON {tabla}
                    FOR EACH ROW EXECUTE FUNCTION registrar_auditoria(
                        {', '.join(repr(campo) for campo in campos_clave)}
                    );
                """,
                reverse_sql=f"DROP TRIGGER auditar_{tabla} ON {tabla};",
            )
            for tabla, campos_clave in TABLAS_AUDITADAS
        ],
    ]
