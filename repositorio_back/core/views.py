from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import login, authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
import json

from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, permissions, status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

from core import pagination
from core.models import Usuario,UsuarioCompleto, Veiculo, Hodometro, Abastecimento, TipoCombustivel
from core.serializers import UsuarioCompletoSerializer, UsuarioCadastroSerializer, VeiculoSerializer, HodometroSerializer, AbastecimentoSerializer
from core.filters import UsuarioFilter, VeiculoFilter, HodometroFilter, AbastecimentoFilter
from core.behaviors import UsuarioBehavior, HodometroBehavior, AbastecimentoBehavior


class UsuarioCadastroViewSet(viewsets.ViewSet):
    """
    ViewSet para cadastrar usuários com username, senha e outros dados.
    """
    queryset = Usuario.objects.all()
    serializer_class = UsuarioCadastroSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]

    @action(detail=False, methods=['post', 'get'])
    def cadastro(self, request):
        """
        Endpoint para realizar o cadastro do usuário.
        """
        # Usando o serializer para validar os dados do cadastro
        serializer = UsuarioCadastroSerializer(data=request.data)
        
        if serializer.is_valid():
            # Extraímos os dados validados
            username = serializer.validated_data['username']
            senha = serializer.validated_data['senha']

            # Criar o novo usuário
            usuario = Usuario(
                username=username,
            )

            # Definir a senha do usuário
            usuario.set_password(senha)

            # Salvar o usuário no banco de dados
            usuario.save()

            return Response({"message": "Usuário cadastrado com sucesso."}, status=status.HTTP_201_CREATED)
        
        # Caso o serializer não seja válido, retornamos os erros
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UsuarioCompletoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar o cadastro completo de usuários.
    """
    queryset = UsuarioCompleto.objects.select_related('usuario').all()
    serializer_class = UsuarioCompletoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UsuarioFilter

    def get_queryset(self):
        """
        Retorna apenas o cadastro completo do usuário autenticado.
        """
        return UsuarioCompleto.objects.filter(usuario=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Criar ou atualizar o cadastro completo do usuário autenticado.
        """
        # Força o usuário autenticado no contexto do serializer
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """
        Atualizar parcialmente o cadastro completo do usuário autenticado.
        """
        usuario_completo = self.get_queryset().first()
        if not usuario_completo:
            return Response(
                {"detail": "Dados completos do usuário não encontrados."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(
            usuario_completo, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def perfil_completo(self, request):
        """
        Retorna os dados completos do usuário autenticado.
        """
        usuario = request.user
        serializer = UsuarioDetalhadoSerializer(usuario)
        return Response(serializer.data, status=status.HTTP_200_OK)

class VeiculoViewSet(viewsets.ModelViewSet):

    queryset = Veiculo.objects.filter(is_deleted=False)
    serializer_class = VeiculoSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = VeiculoFilter

    def destroy(self, request, *args, **kwargs):
        veiculo = self.get_object()  # Obtém o veículo atual
        # Evita a exclusão permanente, marca o veículo como deletado (soft delete)
        if veiculo.is_deleted:
            return Response({"detail": "Veículo já está desativado."}, status=status.HTTP_400_BAD_REQUEST)
        
        veiculo.is_deleted = True
        veiculo.save()
        return Response({"detail": "Veículo desativado com sucesso."}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        veiculo = self.get_object()  # Obtém o veículo atual
        veiculo.is_deleted = False
        veiculo.save()
        return Response({"detail": "Veículo ativado com sucesso."}, status=status.HTTP_200_OK)

class HodometroViewSet(viewsets.ModelViewSet):
    queryset = Hodometro.objects.all()
    serializer_class = HodometroSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = HodometroFilter

    def get_queryset(self):
        """
        Filtra para mostrar apenas os hodômetros do usuário autenticado
        """
        return Hodometro.objects.filter(usuario=self.request.user)

class AbastecimentoViewSet(viewsets.ModelViewSet):

    queryset = Abastecimento.objects.all()
    serializer_class = AbastecimentoSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AbastecimentoFilter

    def get_queryset(self):
        
        """
        Retorna apenas os abastecimentos do usuário autenticado.
        """
        usuario = self.request.user
        return Abastecimento.objects.filter(veiculo__usuario=usuario)

    def perform_create(self, serializer):
        """
        Trata a criação de um abastecimento, garantindo que o usuário esteja associado.
        """
        # Obtém o usuário autenticado
        usuario = self.request.user

        # Cria o abastecimento associando o usuário ao registro
        serializer.save(usuario=usuario)
