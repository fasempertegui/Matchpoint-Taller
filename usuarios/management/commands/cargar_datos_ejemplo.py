from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Carga el script PostgreSQL de ejemplo si no existen sedes."

    def handle(self, *args, **options):
        script = (settings.BASE_DIR / "scripts" / "datos_ejemplo.sql").read_text(encoding="utf-8")
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(script)
        self.stdout.write("Carga de ejemplo procesada; se omite si ya existen sedes.")
