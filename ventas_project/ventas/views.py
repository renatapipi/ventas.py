from urllib import request
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from .models import Cliente, Producto, Usuario
from .forms import ClienteForm, ProductoForm, UsuarioEdicionForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from django.contrib import messages
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.contrib.auth import logout
from django.shortcuts import render

# views.py
from django.contrib.auth import logout
from django.shortcuts import redirect

def cerrar_sesion(request):
    logout(request)
    return redirect('login')  # o tu página de logout


from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

@login_required(login_url='/accounts/login/')
def home(request):
    # Obtener rol seguro
    user_rol = getattr(request.user, 'rol', None)

    if user_rol == 'admin':
        accesos = [
            {'url': 'registrar_venta', 'icon': 'bi-cart-plus', 'label': 'Registrar Venta'},
            {'url': 'productos', 'icon': 'bi-box-seam', 'label': 'Productos'},
            {'url': 'clientes', 'icon': 'bi-people', 'label': 'Clientes'},
            {'url': 'usuarios', 'icon': 'bi-person-badge', 'label': 'Usuarios'},
            {'url': 'resumen_ventas', 'icon': 'bi-graph-up', 'label': 'Resumenes'},
            {'url': 'saldos_clientes', 'icon': 'bi-cash-stack', 'label': 'Saldos Clientes'},
            {'url': 'estadisticas_ventas', 'icon': 'bi-bar-chart-line', 'label': 'Estadísticas'},
        ]
    elif user_rol == 'vendedor':
        accesos = [
            {'url': 'registrar_venta', 'icon': 'bi-cart-plus', 'label': 'Registrar Venta'},
            {'url': 'clientes', 'icon': 'bi-people', 'label': 'Clientes'},
        ]
    else:
        accesos = []

    return render(request, 'ventas/home.html', {'accesos': accesos, 'rol': user_rol})




from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Usuario

@login_required
def usuario_borrar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == 'POST':
        usuario.delete()
        return redirect('usuarios')  # Volver a la lista de usuarios

    return render(request, 'ventas/usuario_confirmar_borrar.html', {'usuario': usuario})

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Usuario

def usuario_toggle(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    usuario.is_active = not usuario.is_active  # cambia el estado
    usuario.save()

    if usuario.is_active:
        messages.success(request, f"El usuario {usuario.username} fue activado correctamente.")
    else:
        messages.warning(request, f"El usuario {usuario.username} fue desactivado correctamente.")

    return redirect("usuarios")  # redirige a la lista de usuarios






from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse
from .models import Cliente, Producto, Venta, ItemVenta, MovimientoCuentaCorriente

@login_required
@transaction.atomic
def registrar_venta(request):
    # Traer todos los clientes y productos
    clientes = Cliente.objects.all()
    productos = Producto.objects.all()

    # Filtro de búsqueda de productos
    query = request.GET.get('q', '')
    if query:
        palabras = query.split()
        q_objects = Q()
        for palabra in palabras:
            q_objects |= Q(nombre__icontains=palabra)
            q_objects |= Q(marca__icontains=palabra)
            q_objects |= Q(rubro__icontains=palabra)
            q_objects |= Q(descripcion__icontains=palabra)
        productos = productos.filter(q_objects).distinct()

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        cliente = Cliente.objects.get(pk=cliente_id) if cliente_id else None
        pagada = request.POST.get('pagada') == 'true'
        descuento_porcentaje = Decimal(request.POST.get('descuento', '0'))
        recargo_porcentaje = Decimal(request.POST.get('recargo', '0'))
        nota = request.POST.get('nota', '')

        # Crear venta con el usuario logueado como vendedor
        nueva_venta = Venta.objects.create(
            vendedor=request.user,
            cliente=cliente,
            pagada=pagada,
            nota=nota
        )

        total_venta = Decimal('0.00')
        productos_encontrados = False  # bandera para validar carrito vacío

        # Agregar items de venta
        for key in request.POST:
            if key.startswith('producto_'):
                productos_encontrados = True
                producto_id = request.POST.get(key)
                cantidad = int(request.POST.get(f'cantidad_{producto_id}', 1))
                prod = Producto.objects.get(pk=producto_id)

                # Validar stock antes de restar
                if cantidad > prod.stock:
                    messages.error(
                        request,
                        f"No hay suficiente stock de {prod.nombre} (disponible: {prod.stock})"
                    )
                    nueva_venta.delete()  # eliminar venta vacía
                    return redirect('registrar_venta')

                subtotal = prod.precio * cantidad

                # Crear ItemVenta y descontar stock
                ItemVenta.objects.create(
                    venta=nueva_venta,
                    producto=prod,
                    cantidad=cantidad,
                    subtotal=subtotal
                )

                # Descontar stock una sola vez
                prod.stock -= cantidad
                prod.save()

                total_venta += subtotal

        # Validar carrito vacío
        if not productos_encontrados:
            messages.error(request, "Debe agregar al menos un producto al carrito.")
            nueva_venta.delete()
            return redirect('registrar_venta')

        # Aplicar descuento y recargo
        if descuento_porcentaje > 0:
            total_venta *= (1 - descuento_porcentaje / 100)
        if recargo_porcentaje > 0:
            total_venta *= (1 + recargo_porcentaje / 100)

        # Guardar total
        nueva_venta.total = total_venta
        nueva_venta.save()

        # Registrar deuda si no fue pagada
        if not pagada and cliente:
            MovimientoCuentaCorriente.objects.create(
                cliente=cliente,
                venta=nueva_venta,
                monto=total_venta,
                tipo='deuda'
            )
            cliente.saldo_cc += total_venta
            cliente.save()

        # Mensaje de éxito con link al recibo
        messages.success(
            request,
            f'Venta registrada correctamente. Total: ${total_venta:.2f} - '
            f'<a href="{reverse("recibo_venta", args=[nueva_venta.id])}" target="_blank">Descargar recibo</a>'
        )
        return redirect('registrar_venta')

    # GET: mostrar formulario
    return render(request, 'ventas/registrar_venta.html', {
        'clientes': clientes,
        'productos': productos,
        'query': query
    })

from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required
def recibo_venta(request, venta_id):
    venta = get_object_or_404(Venta, pk=venta_id)
    items = venta.items.all()

    # Renderizar HTML
    template_path = 'ventas/recibo.html'
    context = {'venta': venta, 'items': items}
    template = get_template(template_path)
    html = template.render(context)

    # Crear PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_venta_{venta.id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)

    # Revisar errores
    if pisa_status.err:
        return HttpResponse('Hubo un error al generar el PDF <pre>' + html + '</pre>')

    return response

@login_required
def cuentas_corrientes(request, cliente_id=None):
    if cliente_id is None:
        clientes = Cliente.objects.all()
        return render(request, 'ventas/saldos_clientes.html', {'saldos_clientes': clientes})

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    movimientos = MovimientoCuentaCorriente.objects.filter(cliente=cliente).order_by('-fecha')
    deuda_total = sum(m.monto if m.tipo == 'deuda' else -m.monto for m in movimientos)

    return render(request, 'ventas/cuentas_corrientes.html', {
        'cliente': cliente,
        'movimientos': movimientos,
        'deuda_total': deuda_total,
    })

@login_required
def detalle_venta(request, venta_id):
    venta = get_object_or_404(Venta, pk=venta_id)
    return render(request, 'ventas/detalle_venta.html', {'venta': venta})

@login_required
@transaction.atomic
def registrar_pago(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    if request.method == 'POST':
        monto = Decimal(request.POST.get('monto', '0'))
    else:
        monto = cliente.saldo_cc

    if monto <= 0:
        messages.warning(request, f"El cliente {cliente.nombre} no tiene deuda pendiente.")
        return redirect('cuentas_corrientes_detalle', cliente_id=cliente.id)

    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        monto=monto,
        tipo='pago'
    )
    cliente.saldo_cc = max(cliente.saldo_cc - monto, Decimal('0.00'))
    cliente.save()
    messages.success(request, f"Pago registrado para {cliente.nombre}: ${monto:.2f}")
    return redirect('cuentas_corrientes_detalle', cliente_id=cliente.id)



@login_required
def clientes(request):
    clientes = Cliente.objects.all()
    return render(request, 'ventas/clientes.html', {'clientes': clientes})

@login_required
def cliente_nuevo(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente guardado correctamente.")
            return redirect('clientes')
        else:
            messages.error(request, "Error en el formulario:")
            print(form.errors)
    else:
        form = ClienteForm()
    return render(request, 'ventas/cliente_form.html', {'form': form})

@login_required
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente actualizado correctamente.")
            return redirect('clientes')
        else:
            messages.error(request, "Error en el formulario:")
            print(form.errors)
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'ventas/cliente_form.html', {'form': form})

@login_required
def productos(request):
    productos = Producto.objects.all()
    return render(request, 'ventas/productos.html', {'productos': productos})

@login_required
def producto_nuevo(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto guardado correctamente.")
            return redirect('productos')
        else:
            messages.error(request, "Error en el formulario:")
            print(form.errors)
    else:
        form = ProductoForm()
    return render(request, 'ventas/producto_form.html', {'form': form})

@login_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect('productos')
        else:
            messages.error(request, "Error en el formulario:")
            print(form.errors)
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'ventas/producto_form.html', {'form': form})

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404





@login_required
def usuarios(request):
    usuarios = Usuario.objects.all()
    return render(request, 'ventas/usuarios.html', {'usuarios': usuarios})

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import UsuarioCreacionForm

@login_required
def usuario_nuevo(request):
    if not request.user.is_superuser and request.user.rol != 'admin':
     return redirect('resumen_ventas')  # ahora está correctamente indentado

    if request.method == 'POST':
        form = UsuarioCreacionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('usuarios')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = UsuarioCreacionForm()

    return render(request, 'ventas/usuario_form.html', {'form': form})




from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import UsuarioCreacionForm
@login_required
def usuario_editar(request, pk):
    if not request.user.is_superuser and request.user.rol != 'admin':
     return redirect('resumen_ventas')

    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioEdicionForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            return redirect('usuarios')
    else:
        form = UsuarioEdicionForm(instance=usuario)
    return render(request, 'ventas/usuario_form.html', {'form': form})

from django.shortcuts import render
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from datetime import datetime
from .models import Venta, Cliente

@login_required(login_url='login')
def resumen_ventas(request):

    ventas = Venta.objects.all().order_by('-fecha')

    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    cliente_id = request.GET.get('cliente')
    tipo = request.GET.get('tipo')

    # FILTRO FECHA INICIO
    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        ventas = ventas.filter(fecha__gte=fecha_inicio)

    # FILTRO FECHA FIN
    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
        fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
        ventas = ventas.filter(fecha__lte=fecha_fin)

    # FILTRO CLIENTE
    if cliente_id:
        ventas = ventas.filter(cliente_id=cliente_id)

    # FILTRO TIPO
    if tipo == "contado":
        ventas = ventas.filter(pagada=True)

    elif tipo == "cta_corriente":
        ventas = ventas.filter(pagada=False)

    filtros = {
        'fecha_inicio': request.GET.get('fecha_inicio', ''),
        'fecha_fin': request.GET.get('fecha_fin', ''),
        'cliente_id': cliente_id or '',
        'tipo': tipo or '',
    }

    total_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
    total_contado = ventas.filter(pagada=True).aggregate(total=Sum('total'))['total'] or 0
    total_cta_corriente = ventas.filter(pagada=False).aggregate(total=Sum('total'))['total'] or 0

    clientes = Cliente.objects.all()

    context = {
        'ventas': ventas,
        'total_ventas': total_ventas,
        'total_contado': total_contado,
        'total_cta_corriente': total_cta_corriente,
        'clientes': clientes,
        'filtros': filtros,
    }

    return render(request, 'ventas/resumen_ventas.html', context)



from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from .models import Cliente, MovimientoCuentaCorriente
from decimal import Decimal

def pagar_cuenta_corriente_memoria(request, cliente_id):
    """
    Procesa el pago total de la cuenta corriente de un cliente.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if cliente.saldo_cc <= 0:
        messages.warning(request, f"El cliente {cliente.nombre} no tiene deuda pendiente.")
        return redirect('saldos_clientes')

    # Registrar el pago en Movimientos
    monto_pagado = cliente.saldo_cc
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        venta=None,  # Si no corresponde a una venta específica
        monto=monto_pagado,
        tipo='pago'
    )

    # Actualizar el saldo del cliente a 0
    cliente.saldo_cc = Decimal('0.00')
    cliente.save()

    messages.success(request, f"Se registró el pago de ${monto_pagado} para {cliente.nombre}.")
    return redirect('saldos_clientes')









from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import Cliente, Venta, ItemVenta, MovimientoCuentaCorriente

@transaction.atomic
def procesar_pago_cuenta_corriente(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)

    # Ventas no pagadas (cuenta corriente)
    ventas_pendientes = Venta.objects.filter(cliente=cliente, pagada=False)

    if not ventas_pendientes.exists():
        messages.warning(request, "No hay deudas pendientes para este cliente.")
        return redirect('pagar_cuenta_corriente', cliente_id=cliente.id)

    # Calcula el total pendiente
    total_pendiente = sum(item.subtotal for item in ItemVenta.objects.filter(venta__in=ventas_pendientes))

    if request.method == 'POST':
        # 1️⃣ Marcar todas las ventas como pagadas
        ventas_pendientes.update(pagada=True)

        # 2️⃣ Crear movimiento de pago
        MovimientoCuentaCorriente.objects.create(
            cliente=cliente,
            monto=total_pendiente,
            tipo='pago'
        )

        # 3️⃣ Actualizar saldo del cliente
        cliente.saldo_cc -= total_pendiente
        cliente.save()

        messages.success(request, f"Se registró el pago de ${total_pendiente} correctamente.")
        return redirect('pagar_cuenta_corriente', cliente_id=cliente.id)

    # Si no es POST, volvemos a la vista de cuenta
    return redirect('pagar_cuenta_corriente', cliente_id=cliente.id)

# views.py


from django.shortcuts import get_object_or_404
from .models import Cliente, Venta, MovimientoCuentaCorriente

def registrar_venta_cc(vendedor, cliente_id, total, pagada=True):
    cliente = get_object_or_404(Cliente, id=cliente_id) if cliente_id else None

    # Crear venta
    venta = Venta.objects.create(
        vendedor=vendedor,
        cliente=cliente,
        total=total,
        pagada=pagada
    )

    # Si la venta NO está pagada, se registra en cuenta corriente
    if cliente and not pagada:
        MovimientoCuentaCorriente.objects.create(
            cliente=cliente,
            venta=venta,
            monto=total,
            tipo='deuda'
        )
        # Actualizar saldo total del cliente
        cliente.saldo_cc += total
        cliente.save()

    return venta




from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Cliente, MovimientoCuentaCorriente

@login_required
def saldos_clientes(request):
    clientes = Cliente.objects.all()

    cliente_id = request.GET.get('pagar')
    if cliente_id:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        if cliente.saldo_cc > 0:
            # Registrar movimiento de pago
            MovimientoCuentaCorriente.objects.create(
                cliente=cliente,
                venta=None,  # si no hay venta específica
                monto=cliente.saldo_cc,
                tipo='pago'
            )

            # Actualizar saldo del cliente
            cliente.saldo_cc = 0
            cliente.save()

            # Marcar todas las ventas pendientes del cliente como pagadas
            ventas_pendientes = cliente.venta_set.filter(pagada=False)
            for venta in ventas_pendientes:
                venta.pagada = True
                venta.save()

            messages.success(request, f'Se ha registrado el pago de {cliente.nombre}. Las ventas pendientes ahora están al contado.')

        return redirect('saldos_clientes')

    return render(request, 'ventas/saldos_clientes.html', {
        'saldos_clientes': clientes
    })







from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import Producto

def producto_borrar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    producto.delete()  # Esto elimina el producto completamente de la DB

    messages.success(request, f'Producto "{producto.nombre}" ha sido eliminado.')
    return redirect('productos')  # nombre de la vista que lista productos


from django.shortcuts import render
from django.db.models import Sum, Count, F
from .models import Venta, ItemVenta, Producto, Usuario
from decimal import Decimal


from django.shortcuts import render
from django.db.models import Sum, F
from .models import Venta, ItemVenta, Producto, Usuario
from decimal import Decimal

def estadisticas_ventas(request):
    # Parámetro de filtro por vendedor
    vendedor_id = request.GET.get('vendedor', None)

    # Porcentaje de comisión
    comision_str = request.GET.get('comision', '0')
    try:
        comision_porcentaje = float(comision_str) if comision_str else 0
    except ValueError:
        comision_porcentaje = 0

    # Filtrar ventas por vendedor si se indicó
    ventas_qs = Venta.objects.all()
    if vendedor_id:
        ventas_qs = ventas_qs.filter(vendedor_id=vendedor_id)

    # Ganancia total (suma de totales de ventas)
    total_ganancia = int(ventas_qs.aggregate(total=Sum('total'))['total'] or 0)

    # Ventas por vendedor
    vendedores = Usuario.objects.all()
    ventas_por_vendedor = []
    for v in vendedores:
        ventas_v = ventas_qs.filter(vendedor=v)
        total_v = int(ventas_v.aggregate(total=Sum('total'))['total'] or 0)
        cant_v = ventas_v.count()
        comision = int(total_v * comision_porcentaje / 100)
        ventas_por_vendedor.append({
            'id': v.id,
            'username': v.username,
            'cantidad_ventas': cant_v,
            'total_vendido': total_v,
            'comision': comision
        })

    # Top 5 productos más vendidos
    productos_mas_vendidos = (
        ItemVenta.objects
        .values('producto__nombre', 'producto__precio', 'producto__costo')
        .annotate(
            cantidad_total=Sum('cantidad'),
            total_vendido=Sum(F('subtotal')),
            ganancia_real=Sum(F('cantidad') * (F('producto__precio') - F('producto__costo')))
        )
        .order_by('-cantidad_total')[:5]
    )

    # Global de ventas por producto
    productos_globales = (
        ItemVenta.objects
        .values('producto__nombre', 'producto__precio', 'producto__costo')
        .annotate(
            cantidad_total=Sum('cantidad'),
            total_vendido=Sum(F('subtotal')),
            ganancia_real=Sum(F('cantidad') * (F('producto__precio') - F('producto__costo')))
        )
        .order_by('-cantidad_total')
    )

    # Productos con bajo stock
    productos_bajo_stock = Producto.objects.filter(stock__lte=5)

    # Ganancia neta total
    ganancia_neta_total = int(sum([p['ganancia_real'] for p in productos_globales]) or 0)

    context = {
        'vendedores': vendedores,
        'vendedor_seleccionado': vendedor_id,
        'total_ganancia': total_ganancia,
        'ventas_por_vendedor': ventas_por_vendedor,
        'productos_mas_vendidos': productos_mas_vendidos,
        'productos_globales': productos_globales,
        'productos_bajo_stock': productos_bajo_stock,
        'comision_porcentaje': comision_porcentaje,
        'ganancia_neta_total': ganancia_neta_total
    }

    return render(request, 'ventas/estadisticas_ventas.html', context)


from django.contrib import messages
from django.shortcuts import redirect
from .models import Venta

@login_required
def eliminar_ventas(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ventas_a_eliminar')
        if ids:
            Venta.objects.filter(id__in=ids).delete()
            messages.success(request, f'Se eliminaron {len(ids)} ventas.')
        else:
            messages.warning(request, 'No seleccionaste ninguna venta.')
    return redirect('resumen_ventas')  # Ajusta el nombre de tu URL









