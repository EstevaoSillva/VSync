from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (UsuarioCompletoViewSet, UsuarioCadastroViewSet, VeiculoViewSet, HodometroViewSet, AbastecimentoViewSet)

# Criação do roteador padrão
router = DefaultRouter()

# Registro de rotas para os ViewSets
router.register(r'register', UsuarioCadastroViewSet, basename='register')
router.register(r'usuarios', UsuarioCompletoViewSet, basename='usuarios')
router.register(r'veiculos', VeiculoViewSet, basename='veiculos')
router.register(r'hodometros', HodometroViewSet, basename='hodometros')
router.register(r'abastecimentos', AbastecimentoViewSet, basename='abastecimentos')

# Definição das URLs
urlpatterns = [
    path('api/', include(router.urls)),  # Inclui todas as rotas do roteador
]
