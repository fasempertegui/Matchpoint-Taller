from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower

from common.fechas import validar_fecha_nacimiento


class Rol(models.Model):
    """Catálogo fijo, cargado por migración y sin gestión desde la aplicación."""

    ADMINISTRADOR = "administrador"
    PROFESOR = "profesor"
    ALUMNO = "alumno"
    RESERVAS = "reservas"
    PUBLICO = "publico"
    INICIALES = (PUBLICO, RESERVAS)

    id = models.BigAutoField(primary_key=True)
    codigo = models.SlugField(max_length=20, unique=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        db_table = "roles"
        ordering = ("id",)
        default_permissions = ()
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre


class UsuarioRol(models.Model):
    
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey("Usuario", on_delete=models.CASCADE, related_name="roles")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="asignaciones")
    asignado_por = models.ForeignKey(
        "Usuario",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="roles_asignados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "usuarios_roles"
        constraints = [
            models.UniqueConstraint(
                fields=("usuario", "rol"), name="usuario_rol_unico"
            ),
        ]
        verbose_name = "rol de usuario"
        verbose_name_plural = "roles de usuario"

    def __str__(self):
        return f"{self.usuario} - {self.rol}"

    def clean(self):
        super().clean()
        if not self.usuario_id or not self.rol_id:
            return
        otros_roles = self.usuario.roles.exclude(pk=self.pk)
        if self.rol.codigo == Rol.ADMINISTRADOR:
            if otros_roles.exists():
                raise ValidationError("Administrador es un rol exclusivo y no puede combinarse con otros roles.")
        elif self.usuario.is_superuser or otros_roles.filter(rol__codigo=Rol.ADMINISTRADOR).exists():
            raise ValidationError("Los administradores solo pueden tener el rol Administrador.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.usuario = Usuario.objects.select_for_update().get(pk=self.usuario_id)
            self.clean()
            return super().save(*args, **kwargs)


class UsuarioManager(UserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        with transaction.atomic():
            usuario = super().create_user(
                username,
                email=email,
                password=password,
                **extra_fields,
            )
            roles_iniciales = (Rol.ADMINISTRADOR,) if usuario.is_superuser else Rol.INICIALES
            for codigo in roles_iniciales:
                rol = Rol.objects.get(codigo=codigo)
                UsuarioRol.objects.create(
                    usuario=usuario,
                    rol=rol,
                )
        return usuario

    create_user.alters_data = True


class Usuario(AbstractUser):

    id = models.BigAutoField(primary_key=True)
    objects = UsuarioManager()
    email = models.EmailField(
        "correo electrónico",
    )
    fecha_nacimiento = models.DateField(
        validators=[validar_fecha_nacimiento],
    )
    celular_contacto = models.CharField(
        max_length=30,
    )
    observaciones = models.TextField(
        blank=True,
    )
    debe_cambiar_contrasena = models.BooleanField(
        default=False,
    )
    fecha_baja = models.DateTimeField(
        null=True,
        blank=True,
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "usuarios"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="usuario_email_unico_sin_mayusculas",
                violation_error_message="Ya existe un usuario registrado con ese email.",
            ),
            models.UniqueConstraint(
                Lower("username"),
                name="usuario_username_unico_sin_mayusculas",
                violation_error_message="Ya existe un usuario con ese nombre de usuario.",
            ),
            models.CheckConstraint(
                condition=models.Q(is_staff=False),
                name="usuarios_is_staff_false",
            ),
        ]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        nombre_completo = self.get_full_name()
        return nombre_completo or self.username

    def tiene_rol(self, rol):
        return self.roles.filter(rol__codigo=rol).exists()

    @property
    def puede_reservar(self):
        return self.roles.filter(rol__codigo__in=(Rol.ADMINISTRADOR, Rol.RESERVAS)).exists()
