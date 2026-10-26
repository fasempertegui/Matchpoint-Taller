from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Carga sedes de ejemplo si no existen y agrega los usuarios de ejemplo que falten."

    def handle(self, *args, **options):
        script = (settings.BASE_DIR / "scripts" / "datos_ejemplo.sql").read_text(encoding="utf-8")
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(script)
        self.stdout.write("Carga de ejemplo procesada; las sedes y los usuarios existentes se conservan.")
