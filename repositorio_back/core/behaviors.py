from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AnonymousUser
from django.db.models import Sum
from rest_framework.response import Response
from django.db import models
from django.conf import settings
from rest_framework import status
from decimal import Decimal, ROUND_DOWN
from core.models import Hodometro, Abastecimento, Veiculo

class UsuarioBehavior:
    @staticmethod
    def check_user_password(usuario, raw_password):
        """
        Verifica se a senha fornecida corresponde à senha do usuário.
        """
        if not usuario.password:
            raise ValidationError("O usuário não possui uma senha definida.")
        if not raw_password:
            raise ValidationError("A senha fornecida não pode ser vazia.")
        if not check_password(raw_password, usuario.password):
            raise ValidationError("A senha fornecida está incorreta.")

        # Verificar a complexidade da senha
        if len(raw_password) < 8:
            raise ValidationError("A senha deve ter pelo menos 8 caracteres.")
        if not any(char.isdigit() for char in raw_password):
            raise ValidationError("A senha deve conter pelo menos um número.")
        if not any(char.isalpha() for char in raw_password):
            raise ValidationError("A senha deve conter pelo menos uma letra.")
        if not any(char.isupper() for char in raw_password):  # Verificando letra maiúscula
            raise ValidationError("A senha deve conter pelo menos uma letra maiúscula.")
        if not any(char in "!@#$%^&*()-_+=<>?/" for char in raw_password):  # Verificando caracteres especiais
            raise ValidationError("A senha deve conter pelo menos um caractere especial.")
            
        return True
    
    @staticmethod
    def check_user_password(usuario, raw_password):
        """
        Verifica se a senha fornecida corresponde à senha do usuário.
        """
        if not usuario.password:
            raise ValidationError("O usuário não possui uma senha definida.")
        if not raw_password:
            raise ValidationError("A senha fornecida não pode ser vazia.")
        if not check_password(raw_password, usuario.password):
            raise ValidationError("A senha fornecida está incorreta.")
        return True

    @staticmethod
    def update_usuario_status(usuario, is_active):
        """
        Atualiza o status ativo do usuário, com validação de superusuário.
        """
        if not usuario:
            raise ValidationError("Usuário inválido ou inexistente.")
        if usuario.is_superuser:
            raise ValidationError("Não é permitido alterar o status de um superusuário.")
        usuario.is_active = is_active
        usuario.save()

class HodometroBehavior:

    @staticmethod
    def calcular_diferenca(veiculo, hodometro_atual):
        # Obtendo o primeiro registro de hodômetro do veículo
        registro_inicial = Hodometro.objects.filter(veiculo=veiculo).order_by('hodometro').first()
        hodometro_inicial = registro_inicial.hodometro if registro_inicial else 0

        # Convertendo os valores para Decimal antes de realizar a subtração
        hodometro_atual = Decimal(str(hodometro_atual)) if not isinstance(hodometro_atual, (int, float, Decimal)) else hodometro_atual
        hodometro_inicial = Decimal(str(hodometro_inicial)) if not isinstance(hodometro_inicial, (int, float, Decimal)) else hodometro_inicial

        # Calculando e retornando a diferença
        return hodometro_atual - hodometro_inicial

    @staticmethod
    def obter_valor_ultimo_hodometro(veiculo):
        """
        Obtém o valor do último hodômetro registrado para o veículo.
        Retorna o valor do hodômetro ou None se não houver registros.
        """
        ultimo_registro = Hodometro.objects.filter(veiculo=veiculo).order_by('-hodometro').first()
        return ultimo_registro.hodometro if ultimo_registro else None

    @staticmethod
    def inicializar_hodometro(usuario, veiculo, hodometro, hodometro_diferenca=None):
        return Hodometro.objects.create(
            usuario=usuario,
            veiculo=veiculo,
            hodometro=hodometro,
            hodometro_diferenca=hodometro_diferenca
        )

    @staticmethod
    def atualizar_hodometro(instance, hodometro_atual):
        """
        Atualiza o registro de hodômetro existente.
        """
        if not isinstance(hodometro_atual, int):
            raise ValueError("O hodômetro atual deve ser um valor inteiro.")

        if hodometro_atual < instance.hodometro:
            raise ValueError("O hodômetro atual não pode ser menor que o valor registrado anteriormente.")

        # Atualiza o hodômetro e calcula a diferença.
        instance.hodometro_diferenca = HodometroBehavior.calcular_diferenca(instance.hodometro, hodometro_atual)
        instance.hodometro = hodometro_atual
        instance.save()

    @staticmethod
    def validar_hodometro(hodometro_atual, veiculo):
        """
        Valida o valor do hodômetro atual em relação ao último registro.
        """
        if not isinstance(hodometro_atual, int):
            raise ValueError("O hodômetro atual deve ser um valor inteiro.")

        hodometro_inicial = HodometroBehavior.obter_valor_ultimo_hodometro(veiculo)
        if hodometro_inicial and hodometro_atual < hodometro_inicial:
            raise ValueError("O hodômetro atual não pode ser menor que o último registro.")


class AbastecimentoBehavior:
    """
    Classe para encapsular lógica de negócio relacionada aos abastecimentos.
    """

    @staticmethod
    def inicializar_abastecimento(abastecimento_atual, veiculo):
        """
        Inicializa o abastecimento e calcula a diferença com base no último registro.
        """
        if not isinstance(abastecimento_atual, int, float):
            raise ValueError("O abastecimento atual deve ser um valor inteiro.")

        abastecimento_anterior = AbastecimentoBehavior.obter_valor_ultimo_abastecimento(veiculo)
        abastecimento_diferenca = AbastecimentoBehavior.calcular_diferenca(abastecimento_anterior, abastecimento_atual) if abastecimento_anterior else None

        return abastecimento_atual, abastecimento_diferenca

    @staticmethod
    def atualizar_abastecimento(instance, abastecimento_atual):
        """
        Atualiza o registro de abastecimento existente.
        """
        if not isinstance(abastecimento_atual, int, float):
            raise ValueError("O abastecimento atual deve ser um valor inteiro.")

        if abastecimento_atual < instance.abastecimento:
            raise ValueError("O abastecimento atual não pode ser menor que o valor registrado anteriormente.")

        # Atualiza o abastecimento e calcula a diferença.
        instance.abastecimento_diferenca = AbastecimentoBehavior.calcular_diferenca(instance.abastecimento, abastecimento_atual)
        instance.abastecimento = abastecimento_atual
        instance.save()

    @staticmethod
    def obter_ultimo_abastecimento(veiculo):
        """
        Obtém o último abastecimento registrado para o veículo.
        """
        # Assume que existe um modelo chamado 'Abastecimento' que está associado ao veículo
        ultimo_abastecimento = Abastecimento.objects.filter(veiculo=veiculo).order_by('-hodometro').first()
        # Log de depuração
        print(f"Obter_ultimo_abastecimento: {ultimo_abastecimento}")

        return ultimo_abastecimento  # Retorna o último abastecimento ou None, caso não haja registros

    @staticmethod
    def calcular_consumo_medio(hodometro_diferenca, veiculo):
        """
        Calcula o consumo médio em km/litro com base no último abastecimento.
        """
        ultimo_abastecimento = AbastecimentoBehavior.obter_ultimo_abastecimento(veiculo)
        # Se não encontrar um abastecimento, pode retornar 0 ou outro valor padrão
        if not ultimo_abastecimento:
            return 0  # Ou algum valor padrão, como None, se preferir

        # Verifique se existe um último abastecimento, total_litros é maior que 0 e a diferença do hodômetro é válida
        if ultimo_abastecimento and hodometro_diferenca > 0:
            total_litros = ultimo_abastecimento.total_litros  # Usando o total_litros do último abastecimento
            print(f"Total litros do último abastecimento: {total_litros}")
            
            # Verifique se o total_litros é válido e maior que 0
            if total_litros and total_litros > 0:
                return hodometro_diferenca / total_litros
            
        # Retorna None se não for possível calcular o consumo médio
        return None

    @staticmethod
    def calcular_diferenca(ultimo_hodometro, penultimo_hodometro):
        """
        Calcula a diferença entre os valores de hodômetro de dois registros.
        """
        ultimo_hodometro = Decimal(str(ultimo_hodometro)) if not isinstance(ultimo_hodometro, (int, float, Decimal)) else ultimo_hodometro
        penultimo_hodometro = Decimal(str(penultimo_hodometro)) if not isinstance(penultimo_hodometro, (int, float, Decimal)) else penultimo_hodometro


        return ultimo_hodometro - penultimo_hodometro

    @staticmethod
    def calcular_preco_total(total_litros, preco_combustivel):

        if total_litros and preco_combustivel:
            preco_total = total_litros * preco_combustivel
            preco_total = Decimal(preco_total).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

            # Limitar a 999.99
            if preco_total >= Decimal('1000.00'):
                return Decimal('999.99')

            return preco_total

        return Decimal('0.00')

    @staticmethod
    def calcular_diferenca_dias(data_atual, data_anterior):
        """
        Calcula a diferença em dias entre duas datas.
        """
        if not data_atual or not data_anterior:
            raise ValueError("Ambas as datas devem ser fornecidas para calcular a diferença.")

        return (data_atual - data_anterior).days

    @staticmethod
    def calcular_litros_por_dia(total_litros, dias_entre_abastecimentos):
        """
        Calcula os litros consumidos por dia, dado o total de litros abastecidos
        e os dias entre abastecimentos.
        """
        if dias_entre_abastecimentos and dias_entre_abastecimentos > 0:
            litros_por_dia = total_litros / dias_entre_abastecimentos
            litros_por_dia = Decimal(litros_por_dia).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            return litros_por_dia
        return None

    @staticmethod
    def km_dias(diferenca_km, dias_percorridos):
        """
        Calcula a quilometragem por dia, dado a quilometragem total e o número de dias.
        """
        if diferenca_km is not None and dias_percorridos is not None and diferenca_km > 0 and dias_percorridos > 0:
            km_dias = diferenca_km / dias_percorridos
            km_dias = Decimal(km_dias).quantize(Decimal('0'), rounding=ROUND_DOWN)
            return km_dias
        return None  # Retorna None caso qualquer valor seja inválido


    @staticmethod
    def calcular_total_gasto_abastecimento(novo_preco_total, veiculo):
        """
        Soma o último valor de total_gasto_abastecimento com o novo preco_total.
        """
        from core.models import Abastecimento

        # Obtem o último registro do mesmo veículo, ordenado por ID
        ultimo_abastecimento = Abastecimento.objects.filter(veiculo=veiculo).order_by('-id').first()

        # Se não houver registros anteriores, retorna apenas o novo valor
        total_anterior = ultimo_abastecimento.total_gasto_abastecimento if ultimo_abastecimento else Decimal('0.00')
        total_gasto = total_anterior + Decimal(str(novo_preco_total))
        # Soma o valor anterior com o novo preco_total
        return total_gasto