from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from decimal import Decimal

class ModelBase(models.Model):
    """
    Modelo base para fornecer campos de ID, data de criação e modificação para outros modelos.
    """
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    modified_at = models.DateTimeField(auto_now=True, db_column='modified_at')
    activate = models.BooleanField(db_column='activate', default=True, null=False)

    class Meta:
        abstract = True
        managed = True


class Usuario(AbstractUser):
    """
    Modelo de usuário para login.
    """
    email = None

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"ID: {self.id} - Login: {self.username}"

class UsuarioCompleto(Usuario):
    """
    Modelo de usuário personalizado para conlcuir o cadastro.
    """
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='perfil_completo', db_column='usuario_id')
    email = models.EmailField(unique=True, db_column='email', verbose_name='Email', blank=True, null=True)
    cpf = models.CharField(max_length=11, db_column='cpf', verbose_name='CPF', unique=True, blank=False, null=False)
    telefone = models.CharField(max_length=15, db_column='telefone', verbose_name='Telefone', blank=True, null=True)

    def __str__(self):
        return f" Login:{self.usuario.username} - ID:{self.id}"


class Veiculo(ModelBase):
    """
    Representa um veículo do sistema.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='veiculos', on_delete=models.CASCADE, db_column='usuario_id', verbose_name='Usuário')
    placa = models.CharField(max_length=7, db_column='placa', verbose_name='Placa', unique=True)
    marca = models.CharField(max_length=255, db_column='marca', verbose_name='Marca')
    modelo = models.CharField(max_length=255, db_column='modelo', verbose_name='Modelo')
    cor = models.CharField(max_length=255, db_column='cor', verbose_name='Cor')
    ano = models.IntegerField(db_column='ano', verbose_name='Ano')
    is_deleted = models.BooleanField(db_column='is_deleted', default=False, null=False)

    class Meta:
        db_table = 'veiculos'
        

    def __str__(self):
        return f"ID:{self.id} - Modelo: {self.modelo} - Placa: {self.placa} - Usuário: {self.usuario}"


class Hodometro(ModelBase):
    """
    Representa o controle de hodômetro de um veículo.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hodometros", db_column='usuario_id')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name="hodometros", db_column='veiculo_id')
    
    hodometro = models.PositiveIntegerField(verbose_name="Hodômetro Inicial", db_column='hodometro_inicial', null=False)
    hodometro_diferenca = models.PositiveIntegerField(verbose_name="Diferenca", db_column='hodometro_diferenca', null=True, blank=True)
    
    
    # Auditoria
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="modified_hodometros")
    last_modified_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'hodometros'
        # Garantir que não existam duplicatas para (veiculo, usuario, hodometro_inicial)
        indexes = [
            models.Index(fields=['veiculo']),
            models.Index(fields=['usuario']),
            models.Index(fields=['hodometro']),
        ]

    def __str__(self):
        return f"{self.veiculo} ({self.id})"


class Abastecimento(ModelBase):
    """
    Representa um abastecimento registrado no sistema.
    """
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name='abastecimentos', verbose_name='Veículo', db_column='veiculo_id')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='abastecimentos', verbose_name='Usuário', db_column='usuario_id')
    hodometro = models.PositiveIntegerField(verbose_name='Hodômetro', db_column='hodometro')
    hodometro_diferenca = models.PositiveIntegerField(verbose_name='Diferenca', db_column='hodometro_diferenca', null=True, blank=True)
    desempenho_veiculo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Desempenho do Veículo', db_column='desempenho_veiculo', null=True, blank=True)
    preco_combustivel = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Preço do Combustível', db_column='preco_combustivel')
    total_litros = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total de Litros', db_column='total_litros')
    preco_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Preço Total', db_column='preco_total')
    data_abastecimento = models.DateTimeField(verbose_name='Data do Abastecimento', db_column='data_abastecimento')
    total_gasto_abastecimento = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'abastecimentos'
        verbose_name = 'Abastecimento'
        verbose_name_plural = 'Abastecimentos'
        ordering = ['data_abastecimento']
        constraints = [
            models.UniqueConstraint(fields=['veiculo', 'data_abastecimento'], name='abastecimento_por_veiculo_e_data')
        ]

    def __str__(self):
        return f"Abastecimento em {self.data_abastecimento} | Veículo {getattr(self.veiculo, 'placa', 'Sem placa')}"

    def save(self, *args, **kwargs):
        from core.behaviors import AbastecimentoBehavior
        

        # Delegar o cálculo do preço total para o Behavior
        if self.veiculo:  # Verifica se o veículo está associado ao abastecimento
            ultimo_abastecimento = Hodometro.objects.filter(veiculo=self.veiculo).order_by('-id').first()

            if ultimo_abastecimento:
                self.hodometro_diferenca = AbastecimentoBehavior.calcular_diferenca(
                    self.hodometro, ultimo_abastecimento.hodometro
                )
            else:
                self.hodometro_diferenca = 0  # Se for o primeiro abastecimento para o veículo

        # Calcular o preço total usando o comportamento
        self.preco_total = AbastecimentoBehavior.calcular_preco_total(self.total_litros, self.preco_combustivel)

        # Limitar o preço total, se necessário
        if self.preco_total >= Decimal("1000.00"): 
            self.preco_total = Decimal("999.99")

        # Calcular o consumo medio
        self.desempenho_veiculo = AbastecimentoBehavior.calcular_consumo_medio(self.hodometro_diferenca, self.total_litros)

        # Calcula o total gasto acumulado
        self.total_gasto_abastecimento = AbastecimentoBehavior.calcular_total_gasto_abastecimento(
            self.preco_total,
            self.veiculo
        )

        # Chama o método save original para garantir que o registro seja salvo
        super().save(*args, **kwargs)


class TipoCombustivel(models.TextChoices):
    GASOLINA = 'GAS', 'Gasolina'
    ETANOL = 'ETA', 'Etanol'
    DIESEL = 'DIE', 'Diesel'
    GNV = 'GNV', 'Gás Natural Veicular'
