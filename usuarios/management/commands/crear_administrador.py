import re
from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from usuarios.forms import UsuarioCrearForm
from usuarios.models import Rol, UsuarioRol


class Command(BaseCommand):
    help = "Crea un usuario con el rol Administrador y contraseña provisoria."

    def pedir_fecha_nacimiento(self):
        campo = UsuarioCrearForm.base_fields["fecha_nacimiento"]
        while True:
            fecha = input("Fecha de nacimiento (AAAA-MM-DD): ").strip()
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", fecha):
                self.stderr.write("Ingresá la fecha con el formato AAAA-MM-DD.")
                continue
            try:
                campo.clean(fecha)
            except ValidationError as error:
                self.stderr.write("; ".join(error.messages))
                continue
            return fecha

    def handle(self, *args, **options):
        datos = {
            "nombre": input("Nombre: ").strip(),
            "apellido": input("Apellido: ").strip(),
            "email": input("Email: ").strip(),
            "celular_contacto": input("Celular: ").strip(),
            "fecha_nacimiento": self.pedir_fecha_nacimiento(),
            "contrasena": getpass("Contraseña provisoria: "),
        }
        confirmacion = getpass("Repetí la contraseña provisoria: ")
        if datos["contrasena"] != confirmacion:
            raise CommandError("Las contraseñas no coinciden.")

        formulario = UsuarioCrearForm(datos)
        if not formulario.is_valid():
            errores = "; ".join(
                f"{campo}: {', '.join(mensajes)}"
                for campo, mensajes in formulario.errors.items()
            )
            raise CommandError(f"No se pudo crear el administrador: {errores}")

        with transaction.atomic():
            usuario = formulario.guardar(
                exigir_cambio_contrasena=True,
                es_superusuario=True,
            )
            rol_administrador = Rol.objects.get(codigo=Rol.ADMINISTRADOR)
            UsuarioRol.objects.create(
                usuario=usuario,
                rol=rol_administrador,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Administrador "{usuario.username}" creado correctamente. '
                "Deberá cambiar la contraseña en el próximo inicio de sesión."
            )
        )
