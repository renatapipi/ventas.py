from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Cliente, Producto, Usuario
from .models import Caja, MovimientoCaja


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'stock', 'precio', 'costo', 'marca', 'ganancia', 'rubro']


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email', 'habilita_cuenta_corriente']
        widgets = {
            'habilita_cuenta_corriente': forms.CheckboxInput(attrs={'class': 'form-check-input me-2', 'role': 'switch'}),
        }


class CajaAperturaForm(forms.ModelForm):
    class Meta:
        model = Caja
        fields = ['saldo_inicial', 'notas']
        widgets = {
            'saldo_inicial': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notas': forms.Textarea(attrs={'rows': 3}),
        }


class MovimientoCajaForm(forms.ModelForm):
    class Meta:
        model = MovimientoCaja
        fields = ['tipo', 'descripcion', 'monto']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Resumen (ej. Venta, Pago proveedor, etc.)'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class UsuarioCreacionForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'rol', 'is_active']


class UsuarioEdicionForm(UserChangeForm):
    password = None

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'rol', 'is_active']
