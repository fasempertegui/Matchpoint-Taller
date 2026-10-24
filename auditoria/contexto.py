from contextlib import contextmanager
from uuid import uuid4

from django.db import connection, transaction


@contextmanager
def contexto_auditoria(usuario=None, origen="aplicacion", accion=None):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT current_setting('auditoria.usuario_id', true),
                       current_setting('auditoria.origen', true),
                       current_setting('auditoria.operacion_id', true),
                       current_setting('auditoria.accion', true)
            """)
            anteriores = cursor.fetchone()
            operacion = anteriores[2] or str(uuid4())
            cursor.execute("""
                SELECT set_config('auditoria.usuario_id', %s, true),
                       set_config('auditoria.origen', %s, true),
                       set_config('auditoria.operacion_id', %s, true),
                       set_config('auditoria.accion', %s, true)
            """, [str(usuario.pk) if usuario is not None else "", origen, operacion, str(accion) if accion else ""])
        yield
        if connection.needs_rollback:
            return
        # Ante un error, el rollback restaura también la configuración local.
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT set_config('auditoria.usuario_id', %s, true),
                       set_config('auditoria.origen', %s, true),
                       set_config('auditoria.operacion_id', %s, true),
                       set_config('auditoria.accion', %s, true)
            """, [valor or "" for valor in anteriores])
