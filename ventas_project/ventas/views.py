# Standard library
from decimal import Decimal, InvalidOperation
from datetime import datetime

# Django imports
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.template.loader import get_template
from django.utils import timezone

# Third-party imports
from xhtml2pdf import pisa

# Local app imports
from .models import (
    Cliente, Producto, Usuario, Venta, ItemVenta,
    MovimientoCuentaCorriente, Caja, MovimientoCaja
)
from .forms import (
    ClienteForm, ProductoForm, UsuarioEdicionForm,
    UsuarioCreacionForm, CajaAperturaForm, MovimientoCajaForm
)


def aplicar_pago_a_ventas(cliente, monto):
    """Marca como pagadas las ventas más antiguas mientras el monto cubre su total."""
    ventas_abiertas = Venta.objects.filter(cliente=cliente, pagada=False).order_by('fecha')
    restante = monto
    for venta in ventas_abiertas:
        if restante <= Decimal('0.00'):
            break
        if restante >= venta.total:
            restante -= venta.total
            venta.pagada = True
            venta.save(update_fields=['pagada'])
    return monto - restante


def registrar_ingreso_caja(monto, descripcion, usuario):
    caja = obtener_caja_abierta()
    if caja and monto > Decimal('0'):
        MovimientoCaja.objects.create(
            caja=caja,
            tipo='ingreso',
            descripcion=descripcion,
            monto=monto,
            usuario=usuario
        )


def registrar_pago_como_venta(request, cliente, monto, tipo_pago):
    """Registra el pago como una venta del día para visualizarlo en el resumen."""
    nota = tipo_pago
    venta_pago = Venta.objects.create(
        vendedor=request.user,
        cliente=cliente,
        pagada=True,
        total=monto,
        nota=nota
    )

    ItemVenta.objects.create(
        venta=venta_pago,
        producto=None,
        cantidad=1,
        subtotal=monto
    )


# ==========================
# Autenticación y home
# ==========================
def cerrar_sesion(request):
    logout(request)
    return redirect('login')


@login_required(login_url='/accounts/login/')
def home(request):
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

    vistos = set()
    accesos_unicos = []
    for acceso in accesos:
        key = (acceso['url'], acceso['label'])
        if key in vistos:
            continue
        vistos.add(key)
        accesos_unicos.append(acceso)

    rol_mostrar = {
        'admin': 'Administrador',
        'vendedor': 'Vendedor',
    }.get(user_rol, 'Invitado')

    resumen_home = {
        'total_clientes': Cliente.objects.count(),
        'total_productos': Producto.objects.count(),
        'ventas_contado': Venta.objects.filter(pagada=True).count(),
        'ventas_cta': Venta.objects.filter(pagada=False).count(),
        'caja_abierta': Caja.objects.filter(esta_abierta=True).exists(),
    }

    return render(request, 'ventas/home.html', {
        'accesos': accesos_unicos,
        'rol': user_rol,
        'role_display': rol_mostrar,
        'resumen_home': resumen_home,
    })


# ==========================
# Usuarios
# ==========================
@login_required
def usuarios(request):
    usuarios = Usuario.objects.all()
    return render(request, 'ventas/usuarios.html', {'usuarios': usuarios})


@login_required
def usuario_nuevo(request):
    if not request.user.is_superuser and request.user.rol != 'admin':
        return redirect('resumen_ventas')

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


@login_required
def usuario_borrar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == 'POST':
        usuario.delete()
        return redirect('usuarios')

    return render(request, 'ventas/usuario_confirmar_borrar.html', {'usuario': usuario})


@login_required
def usuario_toggle(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    usuario.is_active = not usuario.is_active
    usuario.save()

    if usuario.is_active:
        messages.success(request, f"El usuario {usuario.username} fue activado correctamente.")
    else:
        messages.warning(request, f"El usuario {usuario.username} fue desactivado correctamente.")

    return redirect("usuarios")


# ==========================
# Clientes
# ==========================
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


# ==========================
# Productos
# ==========================
@login_required
def productos(request):
    productos = Producto.objects.all()
    rubro_values = Producto.objects.values_list('rubro', flat=True).distinct()
    rubros = []
    sin_rubro = False
    for valor in rubro_values:
        if valor:
            rubros.append(valor)
        else:
            sin_rubro = True
    rubros = sorted(set(rubros))

    opciones_rubro = [{'value': 'all', 'label': 'Todos los rubros'}]
    for rubro in rubros:
        opciones_rubro.append({'value': rubro, 'label': rubro})
    if sin_rubro:
        opciones_rubro.append({'value': '', 'label': 'Sin rubro'})
    return render(request, 'ventas/productos.html', {
        'productos': productos,
        'rubro_options': opciones_rubro,
    })


@login_required
@transaction.atomic
def actualizar_precios_rubro(request):
    if request.method != 'POST':
        return redirect('productos')

    rubro = request.POST.get('rubro', 'all')
    porcentaje_str = request.POST.get('porcentaje', '0').replace(',', '.')
    try:
        porcentaje = Decimal(porcentaje_str)
    except InvalidOperation:
        messages.error(request, 'El porcentaje debe ser un número válido.')
        return redirect('productos')

    if porcentaje == Decimal('0'):
        messages.warning(request, 'El porcentaje no puede ser cero.')
        return redirect('productos')

    productos_qs = Producto.objects.all()
    if rubro != 'all':
        productos_qs = productos_qs.filter(rubro=rubro)

    if not productos_qs.exists():
        messages.warning(request, 'No se encontraron productos para el rubro seleccionado.')
        return redirect('productos')

    factor = Decimal('1') + (porcentaje / Decimal('100'))
    updated = 0
    for producto in productos_qs:
        nuevo_precio = (producto.precio * factor).quantize(Decimal('0.01'))
        if nuevo_precio <= Decimal('0'):
            continue
        producto.precio = nuevo_precio
        producto.save(update_fields=['precio', 'ganancia'])
        updated += 1

    ventas_afectadas = Venta.objects.filter(
        pagada=False,
        items__producto__in=productos_qs
    ).distinct()

    for venta in ventas_afectadas:
        total_anterior = venta.total
        items = venta.items.select_related('producto')
        nuevo_total = Decimal('0')
        for item in items:
            if item.producto:
                subtotal = (item.producto.precio * item.cantidad).quantize(Decimal('0.01'))
            else:
                subtotal = Decimal('0.00')
            if item.subtotal != subtotal:
                ItemVenta.objects.filter(pk=item.pk).update(subtotal=subtotal)
            nuevo_total += subtotal
        nuevo_total = nuevo_total.quantize(Decimal('0.01'))
        if nuevo_total != total_anterior:
            diferencia = nuevo_total - total_anterior
            venta.total = nuevo_total
            venta.save(update_fields=['total'])
            MovimientoCuentaCorriente.objects.filter(venta=venta).update(monto=nuevo_total)
            venta.cliente.saldo_cc = max(venta.cliente.saldo_cc + diferencia, Decimal('0.00'))
            venta.cliente.save(update_fields=['saldo_cc'])

    accion = 'aumentaron' if porcentaje > 0 else 'disminuyeron'
    porcentaje_display = abs(porcentaje)
    messages.success(
        request,
        f'Los precios de {updated} productos {accion} {porcentaje_display:.2f}%.'
    )
    return redirect('productos')


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


@login_required
def producto_borrar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    messages.success(request, f'Producto "{producto.nombre}" ha sido eliminado.')
    return redirect('productos')


# ==========================
# Ventas
# ==========================
@login_required
@transaction.atomic
def registrar_venta(request):
    clientes = Cliente.objects.all()
    productos = Producto.objects.all()

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

        if cliente and not pagada and not cliente.habilita_cuenta_corriente:
            messages.warning(
                request,
                f"El cliente {cliente.nombre} no tiene habilitada la cuenta corriente."
            )
            return redirect('registrar_venta')
        descuento_porcentaje = Decimal(request.POST.get('descuento', '0'))
        recargo_porcentaje = Decimal(request.POST.get('recargo', '0'))
        nota = request.POST.get('nota', '')

        nueva_venta = Venta.objects.create(
            vendedor=request.user,
            cliente=cliente,
            pagada=pagada,
            nota=nota
        )

        total_venta = Decimal('0.00')
        productos_encontrados = False

        for key in request.POST:
            if key.startswith('producto_'):
                productos_encontrados = True
                producto_id = request.POST.get(key)
                cantidad = int(request.POST.get(f'cantidad_{producto_id}', 1))
                prod = Producto.objects.get(pk=producto_id)

                if cantidad > prod.stock:
                    messages.error(request, f"No hay suficiente stock de {prod.nombre} (disponible: {prod.stock})")
                    nueva_venta.delete()
                    return redirect('registrar_venta')

                subtotal = prod.precio * cantidad
                ItemVenta.objects.create(
                    venta=nueva_venta,
                    producto=prod,
                    cantidad=cantidad,
                    subtotal=subtotal
                )
                prod.stock -= cantidad
                prod.save()
                total_venta += subtotal

        if not productos_encontrados:
            messages.error(request, "Debe agregar al menos un producto al carrito.")
            nueva_venta.delete()
            return redirect('registrar_venta')

        if descuento_porcentaje > 0:
            total_venta *= (1 - descuento_porcentaje / 100)
        if recargo_porcentaje > 0:
            total_venta *= (1 + recargo_porcentaje / 100)

        nueva_venta.total = total_venta
        nueva_venta.save()

        if not pagada and cliente:
            MovimientoCuentaCorriente.objects.create(
                cliente=cliente,
                venta=nueva_venta,
                monto=total_venta,
                tipo='deuda'
            )
            cliente.saldo_cc += total_venta
            cliente.save()

        messages.success(
            request,
            f'Venta registrada correctamente. Total: ${total_venta:.2f} - '
            f'<a href="{reverse("recibo_venta", args=[nueva_venta.id])}" target="_blank">Descargar recibo</a>'
        )
        if pagada:
            registrar_ingreso_caja(
                nueva_venta.total,
                f"Venta al contado #{nueva_venta.id}",
                request.user
            )
        return redirect('registrar_venta')

    cliente_seleccionado = None
    cliente_param = request.GET.get('cliente')
    if cliente_param:
        try:
            cliente_seleccionado = Cliente.objects.get(pk=cliente_param)
        except (Cliente.DoesNotExist, ValueError):
            cliente_seleccionado = None

    if request.method == 'POST':
        pagada_por_defecto = request.POST.get('pagada', 'true')
    else:
        pagada_por_defecto = request.GET.get('pagada', 'true') or 'true'

    return render(request, 'ventas/registrar_venta.html', {
        'clientes': clientes,
        'productos': productos,
        'query': query,
        'cliente_seleccionado': cliente_seleccionado,
        'pagada_por_defecto': pagada_por_defecto,
    })


@login_required
def recibo_venta(request, venta_id):
    venta = get_object_or_404(Venta, pk=venta_id)
    items = venta.items.all()

    template_path = 'ventas/recibo.html'
    context = {'venta': venta, 'items': items}
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_venta_{venta.id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Hubo un error al generar el PDF <pre>' + html + '</pre>')

    return response


# ==========================
# Cuentas corrientes y pagos
# ==========================
@login_required
def cuentas_corrientes(request, cliente_id=None):
    if cliente_id is None:
        clientes = Cliente.objects.order_by('nombre')
        return render(request, 'ventas/saldos_clientes.html', {'saldos_clientes': clientes})

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    movimientos = MovimientoCuentaCorriente.objects.filter(cliente=cliente).order_by('-fecha')
    ventas_pendientes = Venta.objects.filter(cliente=cliente, pagada=False).order_by('-fecha')
    total_pagos = movimientos.filter(tipo='pago').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    total_deudas = movimientos.filter(tipo='deuda').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    deuda_total = sum(m.monto if m.tipo == 'deuda' else -m.monto for m in movimientos)

    resumen = {
        'pagos': total_pagos,
        'deudas': total_deudas,
        'pendiente': cliente.saldo_cc,
        'movimientos': movimientos.count(),
        'ventas_pendientes': ventas_pendientes.count(),
    }

    return render(request, 'ventas/cuentas_corrientes.html', {
        'cliente': cliente,
        'movimientos': movimientos,
        'deuda_total': deuda_total,
        'resumen': resumen,
        'ventas_pendientes': ventas_pendientes,
    })


@login_required
@transaction.atomic
def registrar_pago(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    ventas_vigentes = Venta.objects.filter(cliente=cliente, pagada=False)
    total_pendiente = ventas_vigentes.aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    if total_pendiente <= Decimal('0.00'):
        messages.warning(request, f"El cliente {cliente.nombre} no tiene deuda pendiente.")
        return redirect('cuentas_corrientes_detalle', cliente_id=cliente.id)

    next_url = request.POST.get('next_url') or reverse('cuentas_corrientes_detalle', args=[cliente.id])

    if request.method == 'POST':
        try:
            monto = Decimal(request.POST.get('monto', str(total_pendiente)))
        except InvalidOperation:
            monto = total_pendiente
    else:
        monto = total_pendiente

    monto = max(Decimal('0.00'), min(monto, total_pendiente, cliente.saldo_cc))

    if monto <= Decimal('0.00'):
        messages.warning(request, "El monto debe ser mayor a cero.")
        return redirect(next_url)

    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        monto=monto,
        tipo='pago'
    )
    cliente.saldo_cc = max(cliente.saldo_cc - monto, Decimal('0.00'))
    cliente.save(update_fields=['saldo_cc'])

    descripcion = "Pago de cuenta corriente" if monto >= total_pendiente else "Pago parcial de cuenta corriente"
    registrar_pago_como_venta(request, cliente, monto, descripcion)
    aplicar_pago_a_ventas(cliente, monto)

    if monto >= total_pendiente:
        messages.success(
            request,
            f"Pago registrado para {cliente.nombre}: ${monto:.2f}. No quedan deudas pendientes."
        )
    else:
        restante = total_pendiente - monto
        messages.success(
            request,
            f"Pago parcial de ${monto:.2f} registrado. Quedan ${restante:.2f} pendientes."
        )

    return redirect('cuentas_corrientes_detalle', cliente_id=cliente.id)


# ==========================
# Otros
# ==========================
@login_required(login_url='login')
def resumen_ventas(request):
    ventas = Venta.objects.all().order_by('-fecha')

    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    cliente_id = request.GET.get('cliente')
    tipo = request.GET.get('tipo')

    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        ventas = ventas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
        fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
        ventas = ventas.filter(fecha__lte=fecha_fin)
    if cliente_id:
        ventas = ventas.filter(cliente_id=cliente_id)
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


@login_required
def estadisticas_ventas(request):
    vendedores = Usuario.objects.filter(rol='vendedor').order_by('username')
    vendedor_seleccionado = request.GET.get('vendedor', '').strip()
    vendedor_id = None
    if vendedor_seleccionado:
        try:
            vendedor_id = int(vendedor_seleccionado)
        except (ValueError, TypeError):
            vendedor_id = None
    comision_porcentaje_str = request.GET.get('comision', '').strip()
    try:
        comision_porcentaje = Decimal(comision_porcentaje_str) if comision_porcentaje_str else Decimal('0')
    except InvalidOperation:
        comision_porcentaje = Decimal('0')

    ventas_qs = Venta.objects.select_related('vendedor')
    if vendedor_id:
        ventas_qs = ventas_qs.filter(vendedor_id=vendedor_id)

    agregados = (
        ventas_qs
        .values('vendedor__id', 'vendedor__username')
        .annotate(cantidad_ventas=Count('id'), total_vendido=Sum('total'))
    )

    ventas_por_vendedor = []
    for fila in agregados:
        total_vendido = fila.get('total_vendido') or Decimal('0')
        comision = Decimal('0')
        if comision_porcentaje:
            comision = (total_vendido * comision_porcentaje / Decimal('100')).quantize(Decimal('0.01'))

        ventas_por_vendedor.append({
            'username': fila.get('vendedor__username'),
            'cantidad_ventas': fila.get('cantidad_ventas', 0),
            'total_vendido': total_vendido.quantize(Decimal('0.01')) if isinstance(total_vendido, Decimal) else total_vendido,
            'comision': comision,
        })

    productos_mas_vendidos = (
        ItemVenta.objects
        .filter(producto__isnull=False)
        .values('producto__nombre')
        .annotate(cantidad_total=Sum('cantidad'), total_vendido=Sum('subtotal'))
        .order_by('-cantidad_total', '-total_vendido')[:5]
    )

    productos_bajo_stock = Producto.objects.filter(stock__lte=5).order_by('stock')

    total_ganancia = Decimal('0.00')
    for item in ItemVenta.objects.select_related('producto'):
        if not item.producto:
            continue
        ganancia_unitaria = item.producto.precio - item.producto.costo
        total_ganancia += ganancia_unitaria * item.cantidad
    total_ganancia = total_ganancia.quantize(Decimal('0.01'))

    total_ventas = ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_pagado = ventas_qs.filter(pagada=True).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_cta_corriente = ventas_qs.filter(pagada=False).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_totales = ventas_qs.count()
    promedio_ticket = (total_ventas / ventas_totales).quantize(Decimal('0.01')) if ventas_totales else Decimal('0.00')
    porcentaje_cta = (total_cta_corriente / total_ventas * Decimal('100')).quantize(Decimal('0.01')) if total_ventas > 0 else Decimal('0.00')
    clientes_con_deuda = Cliente.objects.filter(saldo_cc__gt=0).count()

    context = {
        'vendedores': vendedores,
        'ventas_por_vendedor': ventas_por_vendedor,
        'productos_mas_vendidos': productos_mas_vendidos,
        'productos_bajo_stock': productos_bajo_stock,
        'total_ganancia': total_ganancia,
        'comision_porcentaje': comision_porcentaje,
        'vendedor_seleccionado': vendedor_seleccionado,
        'total_ventas': total_ventas,
        'total_pagado': total_pagado,
        'total_cta_corriente': total_cta_corriente,
        'ventas_totales': ventas_totales,
        'promedio_ticket': promedio_ticket,
        'porcentaje_cta': porcentaje_cta,
        'clientes_con_deuda': clientes_con_deuda,
    }

    return render(request, 'ventas/estadisticas_ventas.html', context)


@login_required
@transaction.atomic
def eliminar_ventas(request):
    if request.method != 'POST':
        return redirect('resumen_ventas')

    ventas_ids = request.POST.getlist('ventas_a_eliminar')
    if not ventas_ids:
        messages.warning(request, "Selecciona al menos una venta para eliminar.")
        return redirect('resumen_ventas')

    ventas_qs = Venta.objects.filter(id__in=ventas_ids)
    cantidad = ventas_qs.count()
    ventas_qs.delete()
    messages.success(request, f"{cantidad} venta(s) eliminadas correctamente.")
    return redirect('resumen_ventas')


def obtener_caja_abierta():
    caja = Caja.objects.filter(esta_abierta=True).first()
    hoy = timezone.localdate()
    if caja and caja.fecha_apertura.date() < hoy:
        caja.cerrar()
        caja = None
    return caja


def saldos_clientes(request):
    saldos = Cliente.objects.order_by('-saldo_cc')
    total_general = sum((cliente.saldo_cc for cliente in saldos), Decimal('0.00'))
    cliente_simulado = None
    deuda_original = Decimal('0.00')
    movimientos = []
    ventas_pendientes = []
    resumen_cliente = {}

    cliente_param = request.GET.get('cliente')
    if cliente_param:
        try:
            cliente_simulado = Cliente.objects.get(pk=cliente_param)
        except (Cliente.DoesNotExist, ValueError):
            cliente_simulado = None
        else:
            deuda_original = cliente_simulado.saldo_cc
            movimientos = MovimientoCuentaCorriente.objects.filter(cliente=cliente_simulado).order_by('-fecha')
            ventas_pendientes = Venta.objects.filter(cliente=cliente_simulado, pagada=False).order_by('-fecha')
            total_pagos = movimientos.filter(tipo='pago').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
            total_deudas = movimientos.filter(tipo='deuda').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
            resumen_cliente = {
                'pagos': total_pagos,
                'deudas': total_deudas,
                'movimientos': movimientos.count(),
                'ventas_pendientes': ventas_pendientes.count(),
            }

    return render(request, 'ventas/saldos_clientes.html', {
        'saldos_clientes': saldos,
        'cliente_simulado': cliente_simulado,
        'deuda_original': deuda_original,
        'movimientos': movimientos,
        'ventas_pendientes': ventas_pendientes,
        'resumen_cliente': resumen_cliente,
        'total_general': total_general,
    })


@login_required
def abrir_caja(request):
    caja_actual = obtener_caja_abierta()
    if caja_actual:
        messages.info(request, "Ya existe una caja abierta.")
        return redirect('caja_resumen')

    if request.method == 'POST':
        form = CajaAperturaForm(request.POST)
        if form.is_valid():
            caja = form.save(commit=False)
            caja.usuario = request.user
            caja.esta_abierta = True
            caja.save()
            messages.success(request, "Caja abierta correctamente.")
            return redirect('caja_resumen')
    else:
        form = CajaAperturaForm()

    return render(request, 'ventas/caja_form.html', {'form': form})


@login_required
def caja_resumen(request):
    caja = obtener_caja_abierta()
    if not caja:
        return redirect('abrir_caja')

    form = MovimientoCajaForm()
    movimientos = caja.movimientos.all()

    ingresos = sum(m.monto for m in movimientos if m.tipo in ('ingreso', 'apertura'))
    egresos = sum(m.monto for m in movimientos if m.tipo == 'egreso')

    return render(request, 'ventas/caja_resumen.html', {
        'caja': caja,
        'form': form,
        'movimientos': movimientos,
        'ingresos': ingresos,
        'egresos': egresos,
        'saldo_actual': caja.saldo_actual(),
    })


@login_required
def registrar_movimiento_caja(request):
    caja = obtener_caja_abierta()
    if not caja:
        messages.warning(request, "No hay caja abierta.")
        return redirect('abrir_caja')

    if request.method == 'POST':
        form = MovimientoCajaForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.caja = caja
            movimiento.usuario = request.user
            movimiento.save()
            messages.success(request, "Movimiento cargado correctamente.")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    return redirect('caja_resumen')


@login_required
def cerrar_caja(request):
    caja = obtener_caja_abierta()
    if not caja:
        messages.warning(request, "No hay caja abierta para cerrar.")
        return redirect('abrir_caja')

    if request.method == 'POST':
        caja.cerrar()
        messages.success(request, "Caja cerrada correctamente.")
        return redirect('abrir_caja')

    return render(request, 'ventas/caja_cerrar.html', {'caja': caja})


@login_required
def pagar_cuenta_corriente_memoria(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    productos = ItemVenta.objects.filter(
        venta__cliente=cliente,
        venta__pagada=False
    ).select_related('producto', 'venta')

    total_pendiente = sum((item.subtotal for item in productos), Decimal('0.00'))

    return render(request, 'ventas/resumen_cuenta_memoria.html', {
        'cliente': cliente,
        'productos': productos,
        'total_pendiente': total_pendiente,
    })


@login_required
@transaction.atomic
def procesar_pago_cuenta_corriente(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    if request.method != 'POST':
        return redirect('pagar_cuenta_corriente_memoria', cliente_id=cliente.id)

    ventas_vigentes = Venta.objects.filter(cliente=cliente, pagada=False)
    total_pendiente = sum((venta.total for venta in ventas_vigentes), Decimal('0.00'))

    if total_pendiente <= Decimal('0.00'):
        messages.info(request, f"{cliente.nombre} no tiene deudas pendientes.")
        return redirect('cuentas_corrientes_detalle', cliente_id=cliente.id)

    try:
        monto = Decimal(request.POST.get('monto', str(total_pendiente)))
    except InvalidOperation:
        monto = total_pendiente

    monto = max(Decimal('0.00'), min(monto, total_pendiente, cliente.saldo_cc))

    if monto <= Decimal('0.00'):
        messages.warning(request, "El monto debe ser mayor a cero.")
        return redirect('pagar_cuenta_corriente_memoria', cliente_id=cliente.id)

    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        monto=monto,
        tipo='pago'
    )

    cliente.saldo_cc = max(cliente.saldo_cc - monto, Decimal('0.00'))
    cliente.save(update_fields=['saldo_cc'])

    descripcion = "Pago de cuenta corriente" if monto >= total_pendiente else "Pago parcial de cuenta corriente"
    registrar_pago_como_venta(request, cliente, monto, descripcion)
    aplicar_pago_a_ventas(cliente, monto)

    if monto >= total_pendiente:
        messages.success(request, f"Pago registrado para {cliente.nombre}: ${monto:.2f}. No quedan deudas pendientes.")
    else:
        restante = total_pendiente - monto
        messages.success(
            request,
            f"Pago parcial de ${monto:.2f} registrado. Quedan ${restante:.2f} en deuda."
        )

    return redirect(next_url)









