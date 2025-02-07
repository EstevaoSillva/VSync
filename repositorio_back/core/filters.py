from django_filters import rest_framework as filters
from django_filters import NumberFilter, RangeFilter, OrderingFilter
from core.models import Usuario, Veiculo, Hodometro, Abastecimento, TipoCombustivel

class UsuarioFilter(filters.FilterSet):
    username = filters.CharFilter(lookup_expr='icontains', label='Nome')
    cpf = filters.CharFilter(lookup_expr='icontains', label='CPF')
    email = filters.CharFilter(lookup_expr='icontains', label='Email')
    telefone = filters.CharFilter(lookup_expr='icontains', label='Telefone')
    activate = filters.BooleanFilter(label='Ativo', field_name='activate')
    class Meta:
        model = Usuario
        fields = ['username', 'cpf', 'email', 'telefone', 'activate']


class VeiculoFilter(filters.FilterSet):
    placa = filters.CharFilter(lookup_expr='icontains', label='Placa')
    marca = filters.CharFilter(lookup_expr='icontains', label='Marca')
    modelo = filters.CharFilter(lookup_expr='icontains', label='Modelo')
    cor = filters.CharFilter(lookup_expr='icontains', label='Cor')
    ano = NumberFilter(field_name='ano', lookup_expr='exact', label='Ano Exato')
    ano_range = RangeFilter(field_name='ano', label='Intervalo de Anos')
    is_deleted = filters.BooleanFilter(field_name='is_deleted', label='Desativado')
    ordering = OrderingFilter(
        fields=(
            ('ano', 'ano'),
            ('marca', 'marca'),
            ('modelo', 'modelo'),
        ),
        label="Ordenar Por"
    )

    class Meta:
        model = Veiculo
        fields = ['placa', 'marca', 'modelo', 'cor', 'ano', 'is_deleted']


class HodometroFilter(filters.FilterSet):
    usuario = filters.NumberFilter(field_name="usuario__id")
    veiculo = filters.NumberFilter(field_name="veiculo__id")

    class Meta:
        model = Hodometro
        fields = ['usuario', 'veiculo']



class AbastecimentoFilter(filters.FilterSet):
    
    data_inicio = filters.DateFilter(field_name='data_abastecimento', lookup_expr='gte')
    data_fim = filters.DateFilter(field_name='data_abastecimento', lookup_expr='lte')
    
    class Meta:
        model = Abastecimento
        fields = ['veiculo', 'data_abastecimento']