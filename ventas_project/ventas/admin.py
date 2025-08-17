

# Register your models here.
from django.contrib import admin
from .models import Producto, Cliente, Venta, ItemVenta, MovimientoCuentaCorriente

from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Producto, Cliente, Venta, ItemVenta, MovimientoCuentaCorriente
class ItemVentaInline(admin.TabularInline):
    model = ItemVenta
    extra = 1

class VentaAdmin(admin.ModelAdmin):
    inlines = [ItemVentaInline]

admin.site.register(Producto)
admin.site.register(Cliente)
admin.site.register(Venta, VentaAdmin)
admin.site.register(MovimientoCuentaCorriente)

@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    model = Usuario
    list_display = ['username', 'email', 'rol', 'is_staff', 'is_active']
    list_filter = ['rol', 'is_staff', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('rol',)}),
    )

