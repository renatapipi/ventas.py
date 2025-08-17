from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import Usuario, Producto, Cliente
from django.contrib.auth.forms import UserCreationForm

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'stock', 'precio', 'costo', 'marca', 'ganancia', 'rubro']


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email', 'saldo_cc']


# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario

class UsuarioCreacionForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'rol', 'is_active']

class UsuarioEdicionForm(UserChangeForm):
    password = None  # para que no muestre el campo password
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'rol', 'is_active']



