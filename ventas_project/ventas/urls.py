from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Home principal
    # Ventas
    path('ventas/', views.resumen_ventas, name='resumen_ventas'),
    path('registrar/', views.registrar_venta, name='registrar_venta'),
    path('recibo/<int:venta_id>/', views.recibo_venta, name='recibo_venta'),
    path('estadisticas/', views.estadisticas_ventas, name='estadisticas_ventas'),
    # Productos
    path('productos/', views.productos, name='productos'),
    path('productos/nuevo/', views.producto_nuevo, name='producto_nuevo'),
    path('productos/editar/<int:pk>/', views.producto_editar, name='producto_editar'),
    path('productos/borrar/<int:pk>/', views.producto_borrar, name='producto_borrar'),
    path('productos/actualizar-rubro/', views.actualizar_precios_rubro, name='actualizar_precios_rubro'),
    path('eliminar/', views.eliminar_ventas, name='eliminar_ventas'),
    # Clientes
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/nuevo/', views.cliente_nuevo, name='cliente_nuevo'),
    path('clientes/editar/<int:pk>/', views.cliente_editar, name='cliente_editar'),
    # Usuarios
    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/nuevo/', views.usuario_nuevo, name='usuario_nuevo'),
    path('usuarios/editar/<int:pk>/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/borrar/<int:pk>/', views.usuario_borrar, name='usuario_borrar'),
    path('usuarios/toggle/<int:usuario_id>/', views.usuario_toggle, name='usuario_toggle'),
    # Cuentas corrientes
    path('cuentas_corrientes/', views.cuentas_corrientes, name='cuentas_corrientes'),
    path('cuentas_corrientes/<int:cliente_id>/', views.cuentas_corrientes, name='cuentas_corrientes_detalle'),
    path('cuentas_corrientes/<int:cliente_id>/pago/', views.registrar_pago, name='registrar_pago'),
    path('pagar/<int:cliente_id>/', views.pagar_cuenta_corriente_memoria, name='pagar_cuenta_corriente'),
    path('procesar_pago_cuenta_corriente/<int:cliente_id>/', views.procesar_pago_cuenta_corriente, name='procesar_pago_cuenta_corriente'),
    path('caja/abrir/', views.abrir_caja, name='abrir_caja'),
    path('caja/', views.caja_resumen, name='caja_resumen'),
    path('caja/movimiento/', views.registrar_movimiento_caja, name='registrar_movimiento_caja'),
    path('caja/cerrar/', views.cerrar_caja, name='cerrar_caja'),
    # Logout
    path('logout/', views.cerrar_sesion, name='logout'),
    # Saldos clientes
    path('saldos/', views.saldos_clientes, name='saldos_clientes'),
]

