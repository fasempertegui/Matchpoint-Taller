from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from common.fechas import validar_fecha_nacimiento


class Rol(models.Model):
    """Catálogo fijo, cargado por migración y sin gestión desde la aplicación."""

    ADMINISTRADOR = "administrador"
    PROFESOR = "profesor"
    ALUMNO = "alumno"
    RESERVAS = "reservas"
    PUBLICO = "publico"
    INICIALES = (PUBLICO,)

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
        if self.rol.codigo not in (Rol.PUBLICO, Rol.ADMINISTRADOR) and not self.usuario.esta_habilitado:
            raise ValidationError("La asignación de roles requiere una cuenta activa con correo verificado.")
        otros_roles = self.usuario.roles.exclude(pk=self.pk)
        if self.rol.codigo == Rol.ADMINISTRADOR:
            if otros_roles.exists():
                raise ValidationError("Administrador es un rol exclusivo y no puede combinarse con otros roles.")
        elif self.usuario.is_superuser or otros_roles.filter(rol__codigo=Rol.ADMINISTRADOR).exists():
            raise ValidationError("Los administradores solo pueden tener el rol Administrador.")
        if self.rol.codigo in (Rol.PROFESOR, Rol.ALUMNO):
            incompatible = Rol.ALUMNO if self.rol.codigo == Rol.PROFESOR else Rol.PROFESOR
            if otros_roles.filter(rol__codigo=incompatible).exists():
                raise ValidationError("Profesor y Alumno son roles incompatibles entre sí.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.usuario = Usuario.objects.select_for_update().get(pk=self.usuario_id)
            self.clean()
            return super().save(*args, **kwargs)


class UsuarioManager(UserManager):
    def habilitados(self):
        return self.filter(is_active=True, correo_verificado_en__isnull=False)

    def create_user(self, username, email=None, password=None, **extra_fields):
        ahora = timezone.now()
        extra_fields.setdefault("date_joined", ahora)
        extra_fields["verificacion_solicitada_en"] = ahora
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
            from .verificacion import preparar_bienvenida

            preparar_bienvenida(usuario)
        return usuario

    create_user.alters_data = True


class Usuario(AbstractUser):

    id = models.BigAutoField(primary_key=True)
    objects = UsuarioManager()
    first_name = models.CharField("nombre", max_length=100, blank=True)
    last_name = models.CharField("apellido", max_length=100, blank=True)
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
    correo_verificado_en = models.DateTimeField(null=True, blank=True)
    verificacion_solicitada_en = models.DateTimeField(null=True, blank=True)
    revision_correo = models.PositiveIntegerField(default=0)
    email_pendiente = models.EmailField(blank=True, default="")
    cambio_email_solicitado_en = models.DateTimeField(null=True, blank=True)
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
            models.CheckConstraint(condition=(
                models.Q(email_pendiente="", cambio_email_solicitado_en__isnull=True)
                | (~models.Q(email_pendiente="") & models.Q(cambio_email_solicitado_en__isnull=False))
            ), name="usuario_cambio_email_coherente"),
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
    def esta_habilitado(self):
        return self.is_active and self.correo_verificado_en is not None

    @property
    def puede_reservar(self):
        return self.esta_habilitado and self.roles.filter(rol__codigo__in=(Rol.ADMINISTRADOR, Rol.RESERVAS)).exists()


class LimpiezaCuenta(models.Model):
    usuario_eliminado_id = models.BigIntegerField()
    procesado_en = models.DateTimeField()
    resultado = models.CharField(max_length=15, choices=(("eliminada", "Eliminada"), ("inconsistente", "Inconsistente")))
    detalle = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "limpiezas_cuentas"
        default_permissions = ()
        ordering = ("-procesado_en", "-pk")
