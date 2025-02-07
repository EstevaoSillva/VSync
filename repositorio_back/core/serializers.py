from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from django.utils import timezone
from django.utils.timezone import now
from django.db import transaction
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError

from core.models import Usuario, UsuarioCompleto, Veiculo, Hodometro, Abastecimento
from core.behaviors import HodometroBehavior, UsuarioBehavior, AbastecimentoBehavior

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from validate_docbr import CPF
import re





Usuario = get_user_model()

class UsuarioCadastroSerializer(serializers.ModelSerializer):
    
    username = serializers.CharField(
        max_length=150,
        required=True,
        validators=[UniqueValidator(queryset=Usuario.objects.all(), message="Este nome de usuário já está em uso.")],
        error_messages={
            'required': 'Este campo é obrigatório.',
            'max_length': 'O nome de usuário não pode ter mais de 150 caracteres.',
        }
    )
    senha = serializers.CharField(
        max_length=128,
        write_only=True,
        required=True,
        style={"input_type": "password"},
        error_messages={"required": "A senha é obrigatória."}
    )

    class Meta:
        model = Usuario
        fields = ['username', 'senha']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_senha(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("A senha deve ter pelo menos 8 caracteres.")
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("A senha deve conter pelo menos um número.")
        if not any(char.isalpha() for char in value):
            raise serializers.ValidationError("A senha deve conter pelo menos uma letra.")
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("A senha deve conter pelo menos uma letra maiúscula.")

        return value

    def create(self, validated_data):
        senha = validated_data.pop('senha', None)
        usuario = Usuario(**validated_data)
        if senha:
            usuario.set_password(senha)
        usuario.save()
        return usuario


class UsuarioCompletoSerializer(serializers.ModelSerializer):
    """
    Serializer para gerenciar criação ou atualização do cadastro completo de um usuário.
    """

    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=UsuarioCompleto.objects.all(), message="Este email já está cadastrado.")],
        error_messages={
            'required': 'O email é obrigatório.',
            'invalid': 'Informe um endereço de email válido.',
        }
    )
    cpf = serializers.CharField(
        max_length=14,
        min_length=11,
        required=True,
        validators=[UniqueValidator(queryset=UsuarioCompleto.objects.all(), message="Este CPF já está cadastrado.")],
        error_messages={
            'required': 'O CPF é obrigatório.',
            'max_length': 'O CPF deve ter exatamente 11 dígitos.',
            'min_length': 'O CPF deve ter exatamente 11 dígitos.',
        }
    )
    telefone = serializers.CharField(
        max_length=15,
        min_length=10,
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': 'O telefone não pode exceder 15 caracteres.',
            'min_length': 'O telefone deve ter pelo menos 10 caracteres.',
        }
    )

    class Meta:
        model = UsuarioCompleto
        fields = ['id', 'username', 'email', 'cpf', 'telefone']
        extra_kwargs = {
            CPF: {'validators': [CPF()]}
        }

    def validate_cpf(self, value):
        cpf = re.sub(r'\D', '', value)
        if len(cpf) != 11 or not cpf.isdigit():
            raise serializers.ValidationError("O CPF deve ter exatamente 11 dígitos numéricos.")
        return cpf

    def validate_telefone(self, value):
        telefone = re.sub(r'\D', '', value)
        if value and not re.match(r'^\+?\d{10,15}$', telefone):
            raise serializers.ValidationError("O telefone deve ter entre 10 e 15 dígitos e pode incluir o código do país.")
        return value

    def save(self, **kwargs):
        """
        Método customizado para criar ou atualizar o cadastro completo do usuário autenticado.
        """
        usuario = self.context['request'].user
        instance = getattr(usuario, 'usuariocompleto', None)  # Recupera o cadastro completo, se existir

        if instance:  # Se já existir, atualiza os dados
            for attr, value in self.validated_data.items():
                setattr(instance, attr, value)
            instance.save()
        else:  # Caso contrário, cria um novo
            self.validated_data['usuario'] = usuario
            instance = UsuarioCompleto.objects.create(**self.validated_data)

        return instance

class UsuarioCompletoListSerializer(serializers.ModelSerializer):
    
    """
    Serializer para exibir todos os dados do usuário, incluindo os dados do perfil completo.
    """
    email = serializers.EmailField(source='usuariocompleto.email', read_only=True)
    cpf = serializers.CharField(source='usuariocompleto.cpf', read_only=True)
    telefone = serializers.CharField(source='usuariocompleto.telefone', read_only=True)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'cpf', 'telefone', 'date_joined', 'last_login']

class VeiculoSerializer(serializers.ModelSerializer):

    usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all(), required=True)
    usuario_nome = serializers.SerializerMethodField()

    class Meta:
        model = Veiculo
        fields = [
            'id', 
            'usuario_nome', 
            'usuario', 
            'marca', 
            'modelo', 
            'ano', 
            'cor', 
            'placa'
        ]

    def get_usuario_nome(self, obj):
        return obj.usuario.username  

    def validate_marca(self, value):
        """Valida a marca do veículo."""    
        return value.title()

    def validate_modelo(self, value):
        """Valida o modelo do veículo."""
        return value.title()

    def validate_ano(self, value):
        """Valida o ano do veículo."""
        ano_atual = now().year
        if not (1886 <= value <= ano_atual):
            raise serializers.ValidationError(f"O ano deve estar entre 1886 e {ano_atual}.")
        return value

    def validate_placa(self, value):
        """Valida o formato da placa."""
        padrao_antigo = r'(?i)^[a-z]{3}\d{4}$'  # ABC1234
        padrao_mercosul = r'(?i)^[a-z]{3}\d[a-z]\d{2}$'  # ABC1D23
        if not (re.match(padrao_antigo, value) or re.match(padrao_mercosul, value)):
            raise serializers.ValidationError("A placa deve estar no formato ABC1234 ou ABC1D23.")
        return value.upper()

    def validate_cor(self, value):
        """Valida a cor do veículo."""
        cores_validas = ['Preto', 'Branco', 'Prata', 'Vermelho', 'Azul', 'Cinza', 'Amarelo', 'Verde']
        if value.capitalize() not in cores_validas:
            raise serializers.ValidationError(f"A cor deve ser uma das seguintes: {', '.join(cores_validas)}.")
        return value.title()

    def validate(self, data):
        """Valida dados gerais do veículo."""
        placa = data.get('placa')

        # Verifica unicidade, excluindo o veículo atual em caso de atualização
        if self.instance:  # Atualização de veículo
            if Veiculo.objects.exclude(id=self.instance.id).filter(placa=placa, is_deleted=False).exists():
                raise serializers.ValidationError({"placa": "Já existe um veículo registrado com esta placa."})
        else:  # Novo registro
            if Veiculo.objects.filter(placa=placa, is_deleted=False).exists():
                raise serializers.ValidationError({"placa": "Já existe um veículo registrado com esta placa."})

        return data

    def create(self, validated_data):
        """Cria o veículo associado ao usuário autenticado."""
        # Substituir `usuario_id` pelo usuário autenticado
        validated_data['usuario'] = self.context['request'].user
        return Veiculo.objects.create(**validated_data)

    def update_is_deleted(self, veiculo, is_deleted):
        """Desativa o veículo (soft delete)"""
        veiculo.is_deleted = is_deleted
        veiculo.save()
        return veiculo

    def update_activate_status(self, veiculo, status):
        """Ativa ou desativa o veículo alterando o status de exclusão lógica."""
        veiculo.is_deleted = not status  # Se status for False, marca como excluído
        veiculo.save()
        return veiculo


        """Ativa o veículo"""
        veiculo.activate = status
        veiculo.save()
        return veiculo

class HodometroSerializer(serializers.ModelSerializer):

    data_registro = serializers.DateTimeField(source='last_modified_at', read_only=True, format="%d/%m/%Y - %H:%M")
    usuario_nome = serializers.SerializerMethodField()
    placa_veiculo = serializers.SerializerMethodField()

    class Meta:
        model = Hodometro
        fields = [
            'id',
            'veiculo',
            'placa_veiculo',
            'hodometro',
            'hodometro_diferenca',
            'data_registro',
            'usuario_nome',
            'usuario'
        ]
        read_only_fields = ['hodometro_diferenca', 'usuario', 'data_registro']

    def get_placa_veiculo(self, obj):
        return obj.veiculo.placa

    def get_usuario_nome(self, obj):
        return obj.usuario.username

    def validate(self, data):

        veiculo = data.get('veiculo')
        hodometro = data.get('hodometro')

        if not veiculo:
            raise serializers.ValidationError({"veiculo": "Campo veículo é obrigatório."})

        if hodometro is None:
            raise serializers.ValidationError({"hodometro": "Campo hodômetro é obrigatório."})

        # Obtém o último registro de hodômetro para o veículo
        ultimo_registro = Hodometro.objects.filter(veiculo=veiculo).order_by('-hodometro').first()

        if ultimo_registro and hodometro < ultimo_registro.hodometro:
            raise serializers.ValidationError({"hodometro": "O valor do hodômetro não pode ser menor que o último registro."})

        return data

    def create(self, validated_data):
        veiculo = validated_data.get('veiculo')
        usuario = self.context['request'].user
        hodometro = validated_data.get('hodometro')

        ultimo_registro = Hodometro.objects.filter(veiculo=veiculo).order_by('-hodometro').first()

        hodometro_diferenca = None
        if ultimo_registro:
            hodometro_diferenca = HodometroBehavior.calcular_diferenca(veiculo, hodometro)

        # Usando o HodometroBehavior
        return HodometroBehavior.inicializar_hodometro(
            usuario=usuario,
            veiculo=veiculo,
            hodometro=hodometro,
            hodometro_diferenca=hodometro_diferenca
        )

    def update(self, instance, validated_data):
        hodometro = validated_data.get('hodometro', instance.hodometro)

        if hodometro < instance.hodometro:
            raise serializers.ValidationError({"hodometro": "O valor do hodômetro não pode ser menor que o atual."})

        # Calcula a diferença de hodômetro
        instance.hodometro_diferenca = HodometroBehavior.calcular_diferenca(instance.hodometro, hodometro)
        instance.hodometro = hodometro
        instance.save()

        return instance

class AbastecimentoSerializer(serializers.ModelSerializer):

    data_abastecimento = serializers.DateTimeField(required=False, allow_null=True, format="%d/%m/%Y - %H:%M", default=timezone.now)
    veiculo = serializers.PrimaryKeyRelatedField(queryset=Veiculo.objects.all(), required=True)
    hodometro = serializers.IntegerField(required=True)
    dias_entre_abastecimentos = serializers.SerializerMethodField()
    litros_por_dia = serializers.SerializerMethodField()
    km_dias = serializers.SerializerMethodField()
    total_gasto_abastecimento = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Abastecimento
        fields = [
            'id',
            'veiculo',
            'hodometro',
            'hodometro_diferenca',  
            'total_litros',
            'preco_combustivel',
            'preco_total',
            'desempenho_veiculo',
            'data_abastecimento',
            'dias_entre_abastecimentos',
            'litros_por_dia',
            'km_dias',
            'total_gasto_abastecimento'
        ]

        read_only_fields = ['preco_total', 'desempenho_veiculo', 'hodometro_diferenca', 'dias_entre_abastecimentos', 'litros_por_dia', 'km_dias', 'total_gasto_abastecimento']



    def get_total_gasto_abastecimento(self, obj):
            veiculo = obj.veiculo
            return AbastecimentoBehavior.calcular_total_gasto(veiculo)

    def get_km_dias(self, obj):
        return AbastecimentoBehavior.km_dias(obj.hodometro_diferenca, self.get_dias_entre_abastecimentos(obj))

    def get_litros_por_dia(self, obj):
        return AbastecimentoBehavior.calcular_litros_por_dia(obj.total_litros, self.get_dias_entre_abastecimentos(obj))

    def get_dias_entre_abastecimentos(self, obj):
        ultimo_abastecimento = Abastecimento.objects.filter(veiculo=obj.veiculo, id__lt=obj.id).order_by('-data_abastecimento').first()
        if ultimo_abastecimento:
            return (obj.data_abastecimento - ultimo_abastecimento.data_abastecimento).days
        return None

    def validate(self, data):
        veiculo = data.get('veiculo')
        novo_hodometro = data.get('hodometro')
        
        # Obter o último registro de hodômetro
        ultimo_hodometro = Hodometro.objects.filter(veiculo=veiculo).order_by('-id').first()
        ultimo_valor_hodometro = ultimo_hodometro.hodometro if ultimo_hodometro else 0

        # Validar o novo valor do hodômetro com base na diferença
        if novo_hodometro < ultimo_valor_hodometro:
            raise serializers.ValidationError({
                "hodometro": f"O valor do hodômetro ({novo_hodometro}) não pode ser menor que o último registrado ({ultimo_valor_hodometro})."
            })

        return data

    def create(self, validated_data):
        veiculo = validated_data['veiculo']
        total_litros = validated_data['total_litros']
        preco_combustivel = validated_data['preco_combustivel']
        usuario = self.context['request'].user
        hodometro = validated_data['hodometro']

        # Obter o último registro de hodômetro do veículo
        ultimo_hodometro = Hodometro.objects.filter(veiculo=veiculo).order_by('-id').first()
        ultimo_valor_hodometro = ultimo_hodometro.hodometro if ultimo_hodometro else 0

        # Novo valor do hodômetro fornecido
        novo_hodometro = validated_data.get('hodometro', ultimo_valor_hodometro)

        # Calcular a diferença do hodômetro com o Behavior para o abastecimento
        abast_hodometro_diferenca = AbastecimentoBehavior.calcular_diferenca(novo_hodometro, ultimo_valor_hodometro)
        ultimo_registro = Hodometro.objects.filter(veiculo=veiculo).order_by('-hodometro').first()
        hodometro_diferenca = None
        if ultimo_registro:
            hodometro_diferenca = HodometroBehavior.calcular_diferenca(veiculo, hodometro)
        # Calcular o preço total com o Behavior
        preco_total = AbastecimentoBehavior.calcular_preco_total(total_litros, preco_combustivel)

        if hodometro is None:
            hodometro = 0

        # Criar o registro do abastecimento
        abastecimento = Abastecimento.objects.create(
            veiculo=veiculo,
            total_litros=total_litros,
            hodometro=hodometro,
            preco_combustivel=preco_combustivel,
            preco_total=preco_total,
            hodometro_diferenca=abast_hodometro_diferenca,  
            data_abastecimento=validated_data.get('data_abastecimento', timezone.now()),
            usuario=usuario
        )

        # Criar o novo registro de Hodômetro
        if novo_hodometro is not None:
            Hodometro.objects.create(
                veiculo=veiculo,
                hodometro=novo_hodometro,
                hodometro_diferenca=hodometro_diferenca,  
                usuario=usuario
            )

        return abastecimento


    def update(self, instance, validated_data):
        veiculo = validated_data.get('veiculo', instance.veiculo)
        total_litros = validated_data.get('total_litros', instance.total_litros)
        preco_combustivel = validated_data.get('preco_combustivel', instance.preco_combustivel)
        usuario = self.context['request'].user
        hodometro = self.context['request'].data.get('hodometro')

        # Obter o último valor de hodômetro registrado no veículo
        ultimo_hodometro = Hodometro.objects.filter(veiculo=veiculo).order_by('-id').first()
        ultimo_valor_hodometro = ultimo_hodometro.hodometro if ultimo_hodometro else 0

        # Novo valor do hodômetro fornecido
        novo_hodometro = validated_data.pop('hodometro', instance.hodometro)

        if novo_hodometro != instance.hodometro:
            # Validar o novo hodômetro com o Behavior
            if not HodometroBehavior.validar_hodometro(ultimo_valor_hodometro, novo_hodometro):
                raise serializers.ValidationError({
                    "hodometro": f"O valor do hodômetro ({novo_hodometro}) não pode ser menor que o último registrado ({ultimo_valor_hodometro})."
                })

            # # Calcular a diferença do hodômetro com o Behavior
            # hodometro_diferenca = HodometroBehavior.calcular_diferenca(ultimo_valor_hodometro, novo_hodometro)

            ultimo_registro = Hodometro.objects.filter(veiculo=veiculo).order_by('-hodometro').first()
            hodometro_diferenca = None
            if ultimo_registro:
                hodometro_diferenca = HodometroBehavior.calcular_diferenca(veiculo, hodometro)

            # Criar um novo registro de Hodômetro
            Hodometro.objects.create(
                veiculo=veiculo,
                hodometro=novo_hodometro,
                hodometro_diferenca=hodometro_diferenca,
                usuario=usuario
            )

            # Atualizar o campo de diferença no abastecimento
            instance.hodometro_diferenca = hodometro_diferenca

        # Atualizar os outros campos
        instance.total_litros = total_litros
        instance.preco_combustivel = preco_combustivel
        instance.preco_total = AbastecimentoBehavior.calcular_preco_total(total_litros, preco_combustivel)
        instance.save()

        return instance
