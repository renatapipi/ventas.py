from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    marca = models.CharField(max_length=100, blank=True)
    descripcion = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rubro = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.nombre

    def clean(self):
        """Validate that precio and costo are non‑negative."""
        from django.core.exceptions import ValidationError
        if self.precio < 0 or self.costo < 0:
            raise ValidationError("Precio y costo deben ser valores positivos.")

    def save(self, *args, **kwargs):
        # mantenga la ganancia sincronizada
        self.ganancia = self.precio - self.costo
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'productos'

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    saldo_cc = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'clientes'

class Venta(models.Model):
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pagada = models.BooleanField(default=True)
    nota = models.TextField(blank=True)

    def __str__(self):
        return f"Venta {self.id} - {self.fecha.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        # recalcule el total a partir de los ítems asociados si ya existe la venta
        if self.pk:
            self.total = sum(i.subtotal for i in self.items.all())
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-fecha']
        verbose_name_plural = 'ventas'

class ItemVenta(models.Model):
    venta = models.ForeignKey(Venta, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        db_column='productos_id'
    )
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

    def save(self, *args, **kwargs):
        if self.producto:
            self.subtotal = self.producto.precio * self.cantidad
        else:
            self.subtotal = 0

        super().save(*args, **kwargs)

        # actualizar total de la venta padre
        venta = self.venta
        venta.total = sum(i.subtotal for i in venta.items.all())
        venta.save(update_fields=['total'])

    class Meta:
        ordering = ['venta', 'producto']



class MovimientoCuentaCorriente(models.Model):
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        related_name='movimientocuentacorriente'
    )
    venta = models.ForeignKey(
        Venta, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(
        max_length=10, 
        choices=[('deuda', 'Deuda'), ('pago', 'Pago')]
    )

    def __str__(self):
        return f"{self.tipo} {self.monto} - {self.cliente.nombre}"

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'movimiento de cuenta corriente'
        verbose_name_plural = 'movimientos de cuenta corriente'


class Usuario(AbstractUser):
    rol = models.CharField(max_length=20, choices=[('admin', 'Administrador'), ('vendedor', 'Vendedor')])

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='Grupos a los que pertenece este usuario.',
        verbose_name='grupos',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Permisos específicos para este usuario.',
        verbose_name='permisos de usuario',
    )

    def __str__(self):
        return self.get_full_name() or self.username

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'




