"""
pje_monitor_service.py - Serviço de Monitoramento do PJe para prudentIA

Este módulo implementa um serviço completo para monitoramento automático de publicações
do PJe (Processo Judicial Eletrônico) para advogados cadastrados no sistema prudentIA.

Características:
- Integração com o web scraper do PJe
- Sistema de filas com Celery para processamento assíncrono
- Notificações via WhatsApp e email
- Armazenamento e histórico de publicações
- Análise de conteúdo e classificação de relevância
- Agendamento configurável por usuário
"""

import os
import re
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urlencode
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
import httpx

# Importações do Django (assumindo uso do Django como framework web)
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail

# Importações do Celery
from celery import Celery, Task, shared_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger

# Importação do módulo de scraping do PJe
from pje_scraper import PJeScraper, ConfiguracaoBusca, Publicacao, ResultadoBusca

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
celery_logger = get_task_logger(__name__)

# Configuração do Celery
app = Celery("prudentia")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Configurações do serviço
class Config:
    # Configurações gerais
    MONITORAMENTO_INTERVALO_PADRAO = 24  # horas
    MONITORAMENTO_DIAS_RETROATIVOS = 7  # dias
    MAX_TENTATIVAS_SCRAPING = 3

    # Configurações de notificação
    NOTIFICACAO_EMAIL_ATIVO = True
    NOTIFICACAO_WHATSAPP_ATIVO = True
    WHATSAPP_API_URL = os.getenv(
        "WHATSAPP_API_URL", "https://api.whatsapp.com/v1/messages"
    )
    WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "notificacoes@prudentia.com.br")

    # Configurações de análise de conteúdo
    PALAVRAS_CHAVE_URGENTE = [
        "liminar",
        "antecipação de tutela",
        "urgente",
        "mandado de segurança",
        "habeas corpus",
        "prazo",
        "intimação",
        "citação",
        "audiência",
        "sentença",
        "acórdão",
        "decisão",
        "despacho",
        "julgamento",
        "penhora",
        "bloqueio",
    ]

    # Classificação de prioridade
    PRIORIDADE_BAIXA = 1
    PRIORIDADE_MEDIA = 2
    PRIORIDADE_ALTA = 3
    PRIORIDADE_URGENTE = 4


# Modelos de dados (usando Django ORM)
class Advogado(models.Model):
    """Modelo para representar um advogado cadastrado no sistema."""

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    numero_oab = models.CharField(max_length=10)
    uf_oab = models.CharField(max_length=2)
    whatsapp = models.CharField(max_length=20, null=True, blank=True)

    # Configurações de monitoramento
    monitoramento_ativo = models.BooleanField(default=True)
    intervalo_monitoramento = models.IntegerField(
        default=Config.MONITORAMENTO_INTERVALO_PADRAO
    )
    notificacao_email = models.BooleanField(default=True)
    notificacao_whatsapp = models.BooleanField(default=True)
    ultima_verificacao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nome} (OAB {self.numero_oab}/{self.uf_oab})"

    class Meta:
        verbose_name = "Advogado"
        verbose_name_plural = "Advogados"
        indexes = [
            models.Index(fields=["numero_oab", "uf_oab"]),
        ]


class Processo(models.Model):
    """Modelo para representar um processo monitorado."""

    id = models.AutoField(primary_key=True)
    numero_processo = models.CharField(max_length=25)
    advogados = models.ManyToManyField(Advogado, related_name="processos")
    titulo = models.CharField(max_length=255, null=True, blank=True)
    tribunal = models.CharField(max_length=50, null=True, blank=True)
    vara = models.CharField(max_length=100, null=True, blank=True)
    cliente = models.CharField(max_length=255, null=True, blank=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.numero_processo

    class Meta:
        verbose_name = "Processo"
        verbose_name_plural = "Processos"
        indexes = [
            models.Index(fields=["numero_processo"]),
        ]


class PublicacaoMonitorada(models.Model):
    """Modelo para armazenar publicações monitoradas do PJe."""

    id = models.AutoField(primary_key=True)
    processo = models.ForeignKey(
        Processo, on_delete=models.CASCADE, related_name="publicacoes"
    )
    data_publicacao = models.DateTimeField()
    data_captura = models.DateTimeField(auto_now_add=True)
    conteudo = models.TextField()
    tribunal = models.CharField(max_length=50)
    orgao_julgador = models.CharField(max_length=100)
    caderno = models.CharField(max_length=100, null=True, blank=True)
    hash = models.CharField(max_length=64, unique=True)
    url_processo = models.URLField(null=True, blank=True)

    # Análise de conteúdo
    prioridade = models.IntegerField(default=Config.PRIORIDADE_MEDIA)
    palavras_chave = models.JSONField(null=True, blank=True)
    resumo = models.TextField(null=True, blank=True)

    # Status de notificação
    notificado_email = models.BooleanField(default=False)
    notificado_whatsapp = models.BooleanField(default=False)

    def __str__(self):
        return f"Publicação {self.id} - Processo {self.processo.numero_processo}"

    class Meta:
        verbose_name = "Publicação Monitorada"
        verbose_name_plural = "Publicações Monitoradas"
        indexes = [
            models.Index(fields=["hash"]),
            models.Index(fields=["data_publicacao"]),
            models.Index(fields=["prioridade"]),
        ]


class LogMonitoramento(models.Model):
    """Modelo para registrar logs de monitoramento."""

    id = models.AutoField(primary_key=True)
    advogado = models.ForeignKey(
        Advogado, on_delete=models.CASCADE, related_name="logs"
    )
    data_execucao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)
    mensagem = models.TextField(null=True, blank=True)
    publicacoes_encontradas = models.IntegerField(default=0)
    publicacoes_novas = models.IntegerField(default=0)
    erro = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Log {self.id} - {self.advogado.nome} - {self.data_execucao}"

    class Meta:
        verbose_name = "Log de Monitoramento"
        verbose_name_plural = "Logs de Monitoramento"


# Serviço de Monitoramento
class PJeMonitorService:
    """
    Serviço principal para monitoramento de publicações do PJe.

    Esta classe implementa a lógica de negócio para monitoramento, processamento
    e notificação de publicações do PJe para advogados cadastrados.
    """

    def __init__(self):
        self.scraper = PJeScraper()

    def agendar_monitoramento_para_todos_advogados(self):
        """Agenda tarefas de monitoramento para todos os advogados ativos."""
        advogados_ativos = Advogado.objects.filter(monitoramento_ativo=True)

        for advogado in advogados_ativos:
            self.agendar_monitoramento_para_advogado(advogado)

    def agendar_monitoramento_para_advogado(self, advogado):
        """
        Agenda uma tarefa de monitoramento para um advogado específico.

        Args:
            advogado: Objeto Advogado a ser monitorado
        """
        # Determinar quando a próxima verificação deve ocorrer
        if advogado.ultima_verificacao:
            # Calcular próxima verificação com base na última e no intervalo configurado
            horas_desde_ultima = (
                timezone.now() - advogado.ultima_verificacao
            ).total_seconds() / 3600
            if horas_desde_ultima < advogado.intervalo_monitoramento:
                # Ainda não é hora de verificar novamente
                proxima_verificacao = advogado.ultima_verificacao + timedelta(
                    hours=advogado.intervalo_monitoramento
                )
                delay_seconds = (proxima_verificacao - timezone.now()).total_seconds()
                if delay_seconds <= 0:
                    delay_seconds = 60  # Mínimo de 1 minuto
            else:
                # Já passou do tempo, agendar para execução imediata (1 minuto)
                delay_seconds = 60
        else:
            # Primeira verificação, agendar para execução imediata (1 minuto)
            delay_seconds = 60

        # Agendar tarefa Celery
        monitorar_publicacoes_advogado.apply_async(
            args=[advogado.id], countdown=delay_seconds
        )

        logger.info(
            f"Monitoramento agendado para advogado {advogado.id} em {delay_seconds/60:.1f} minutos"
        )

    async def buscar_publicacoes_para_advogado(self, advogado_id):
        """
        Busca publicações para um advogado específico.

        Args:
            advogado_id: ID do advogado

        Returns:
            ResultadoBusca contendo as publicações encontradas
        """
        advogado = Advogado.objects.get(id=advogado_id)

        # Determinar período de busca
        data_fim = datetime.now()

        if advogado.ultima_verificacao:
            # Buscar desde a última verificação (com 1 dia de sobreposição para garantir)
            data_inicio = advogado.ultima_verificacao - timedelta(days=1)
        else:
            # Primeira verificação, buscar os últimos X dias
            data_inicio = data_fim - timedelta(
                days=Config.MONITORAMENTO_DIAS_RETROATIVOS
            )

        # Buscar publicações
        try:
            resultado = await self.scraper.buscar_por_periodo_async(
                numero_oab=advogado.numero_oab,
                uf_oab=advogado.uf_oab,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )

            # Atualizar data da última verificação
            advogado.ultima_verificacao = timezone.now()
            advogado.save(update_fields=["ultima_verificacao"])

            return resultado
        except Exception as e:
            logger.error(
                f"Erro ao buscar publicações para advogado {advogado_id}: {str(e)}"
            )

            # Registrar log de erro
            LogMonitoramento.objects.create(
                advogado_id=advogado_id,
                status="ERRO",
                mensagem=f"Falha ao buscar publicações: {str(e)}",
                erro=str(e),
            )

            raise

    def processar_publicacoes(self, advogado_id, resultado_busca):
        """
        Processa as publicações encontradas para um advogado.

        Args:
            advogado_id: ID do advogado
            resultado_busca: ResultadoBusca contendo as publicações

        Returns:
            Tuple[int, int]: (total de publicações, novas publicações)
        """
        advogado = Advogado.objects.get(id=advogado_id)
        publicacoes_novas = 0

        with transaction.atomic():
            for pub in resultado_busca.publicacoes:
                # Verificar se a publicação já existe pelo hash
                if PublicacaoMonitorada.objects.filter(hash=pub.hash).exists():
                    continue

                # Buscar ou criar o processo
                processo, criado = Processo.objects.get_or_create(
                    numero_processo=pub.numero_processo,
                    defaults={"tribunal": pub.tribunal, "vara": pub.orgao_julgador},
                )

                # Adicionar advogado ao processo se ainda não estiver associado
                if advogado not in processo.advogados.all():
                    processo.advogados.add(advogado)

                # Analisar conteúdo e determinar prioridade
                prioridade, palavras_chave = self.analisar_conteudo(pub.conteudo)
                resumo = self.gerar_resumo(pub.conteudo)

                # Criar registro de publicação
                publicacao = PublicacaoMonitorada.objects.create(
                    processo=processo,
                    data_publicacao=pub.data_publicacao,
                    conteudo=pub.conteudo,
                    tribunal=pub.tribunal,
                    orgao_julgador=pub.orgao_julgador,
                    caderno=pub.caderno,
                    hash=pub.hash,
                    url_processo=pub.url_processo,
                    prioridade=prioridade,
                    palavras_chave=palavras_chave,
                    resumo=resumo,
                )

                publicacoes_novas += 1

                # Enviar notificações
                self.notificar_publicacao(publicacao, advogado)

        # Registrar log de sucesso
        LogMonitoramento.objects.create(
            advogado=advogado,
            status="SUCESSO",
            mensagem=f"Monitoramento concluído com sucesso",
            publicacoes_encontradas=len(resultado_busca.publicacoes),
            publicacoes_novas=publicacoes_novas,
        )

        return len(resultado_busca.publicacoes), publicacoes_novas

    def analisar_conteudo(self, conteudo):
        """
        Analisa o conteúdo de uma publicação para determinar prioridade e palavras-chave.

        Args:
            conteudo: Texto da publicação

        Returns:
            Tuple[int, List[str]]: (prioridade, lista de palavras-chave encontradas)
        """
        conteudo_lower = conteudo.lower()
        palavras_chave_encontradas = []

        # Buscar palavras-chave urgentes
        for palavra in Config.PALAVRAS_CHAVE_URGENTE:
            if palavra.lower() in conteudo_lower:
                palavras_chave_encontradas.append(palavra)

        # Determinar prioridade com base na quantidade de palavras-chave encontradas
        if len(palavras_chave_encontradas) >= 3:
            prioridade = Config.PRIORIDADE_URGENTE
        elif len(palavras_chave_encontradas) >= 2:
            prioridade = Config.PRIORIDADE_ALTA
        elif len(palavras_chave_encontradas) >= 1:
            prioridade = Config.PRIORIDADE_MEDIA
        else:
            prioridade = Config.PRIORIDADE_BAIXA

        # Verificar prazos específicos
        padrao_prazo = r"prazo\s+de\s+(\d+)\s+dias?"
        match_prazo = re.search(padrao_prazo, conteudo_lower)
        if match_prazo:
            dias_prazo = int(match_prazo.group(1))
            if dias_prazo <= 5:
                prioridade = max(prioridade, Config.PRIORIDADE_URGENTE)
                palavras_chave_encontradas.append(f"Prazo de {dias_prazo} dias")
            elif dias_prazo <= 15:
                prioridade = max(prioridade, Config.PRIORIDADE_ALTA)
                palavras_chave_encontradas.append(f"Prazo de {dias_prazo} dias")

        # Verificar audiências
        padrao_audiencia = r"audiência.+?(\d{2}/\d{2}/\d{4})"
        match_audiencia = re.search(padrao_audiencia, conteudo_lower)
        if match_audiencia:
            data_audiencia = match_audiencia.group(1)
            palavras_chave_encontradas.append(f"Audiência em {data_audiencia}")
            prioridade = max(prioridade, Config.PRIORIDADE_ALTA)

        return prioridade, palavras_chave_encontradas

    def gerar_resumo(self, conteudo):
        """
        Gera um resumo do conteúdo da publicação.

        Em uma implementação completa, isso poderia usar NLP ou IA,
        mas aqui vamos simplesmente pegar as primeiras frases.

        Args:
            conteudo: Texto da publicação

        Returns:
            str: Resumo do conteúdo
        """
        # Dividir por frases e pegar as primeiras 2-3 frases
        frases = re.split(r"[.!?]+", conteudo)
        frases = [f.strip() for f in frases if f.strip()]

        if not frases:
            return "Sem conteúdo para resumir."

        # Limitar a 2-3 frases ou 200 caracteres
        resumo = ". ".join(frases[: min(3, len(frases))])
        if len(resumo) > 200:
            resumo = resumo[:197] + "..."

        return resumo

    def notificar_publicacao(self, publicacao, advogado):
        """
        Envia notificações sobre uma nova publicação para um advogado.

        Args:
            publicacao: Objeto PublicacaoMonitorada
            advogado: Objeto Advogado
        """
        # Preparar dados para notificação
        dados = {
            "advogado": advogado,
            "publicacao": publicacao,
            "processo": publicacao.processo,
            "data_formatada": publicacao.data_publicacao.strftime("%d/%m/%Y %H:%M"),
            "resumo": publicacao.resumo or self.gerar_resumo(publicacao.conteudo),
            "url_processo": publicacao.url_processo
            or f"https://prudentia.com.br/processo/{publicacao.processo.numero_processo}/",
            "url_detalhe": f"https://prudentia.com.br/publicacao/{publicacao.id}/",
            "prioridade_texto": self._obter_texto_prioridade(publicacao.prioridade),
        }

        # Enviar email se configurado
        if Config.NOTIFICACAO_EMAIL_ATIVO and advogado.notificacao_email:
            self._enviar_email_notificacao(dados)
            publicacao.notificado_email = True
            publicacao.save(update_fields=["notificado_email"])

        # Enviar WhatsApp se configurado
        if (
            Config.NOTIFICACAO_WHATSAPP_ATIVO
            and advogado.notificacao_whatsapp
            and advogado.whatsapp
        ):
            self._enviar_whatsapp_notificacao(dados)
            publicacao.notificado_whatsapp = True
            publicacao.save(update_fields=["notificado_whatsapp"])

    def _obter_texto_prioridade(self, prioridade):
        """Retorna o texto correspondente ao nível de prioridade."""
        if prioridade == Config.PRIORIDADE_URGENTE:
            return "URGENTE"
        elif prioridade == Config.PRIORIDADE_ALTA:
            return "Alta"
        elif prioridade == Config.PRIORIDADE_MEDIA:
            return "Média"
        else:
            return "Baixa"

    def _enviar_email_notificacao(self, dados):
        """
        Envia email de notificação sobre uma nova publicação.

        Args:
            dados: Dicionário com dados para o template
        """
        try:
            assunto = f"[{dados['prioridade_texto']}] Nova publicação - Processo {dados['processo'].numero_processo}"

            # Renderizar template HTML
            html_content = render_to_string("emails/nova_publicacao.html", dados)

            # Renderizar template texto
            text_content = render_to_string("emails/nova_publicacao.txt", dados)

            # Enviar email
            send_mail(
                subject=assunto,
                message=text_content,
                from_email=Config.EMAIL_REMETENTE,
                recipient_list=[dados["advogado"].email],
                html_message=html_content,
                fail_silently=False,
            )

            logger.info(
                f"Email enviado para {dados['advogado'].email} sobre publicação {dados['publicacao'].id}"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")

    def _enviar_whatsapp_notificacao(self, dados):
        """
        Envia notificação WhatsApp sobre uma nova publicação.

        Args:
            dados: Dicionário com dados para o template
        """
        try:
            # Formatar mensagem WhatsApp
            prioridade_emoji = (
                "🔴"
                if dados["prioridade_texto"] == "URGENTE"
                else "🟠" if dados["prioridade_texto"] == "Alta" else "🟡"
            )

            mensagem = (
                f"*{prioridade_emoji} Nova publicação - prudentIA*\n\n"
                f"*Processo:* {dados['processo'].numero_processo}\n"
                f"*Data:* {dados['data_formatada']}\n"
                f"*Órgão:* {dados['publicacao'].orgao_julgador}\n\n"
                f"*Resumo:*\n{dados['resumo']}\n\n"
                f"Acesse os detalhes: {dados['url_detalhe']}"
            )

            # Preparar payload para API do WhatsApp
            payload = {
                "phone": dados["advogado"]
                .whatsapp.replace("+", "")
                .replace("-", "")
                .replace(" ", ""),
                "message": mensagem,
            }

            # Enviar requisição para API do WhatsApp
            headers = {
                "Authorization": f"Bearer {Config.WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json",
            }

            response = httpx.post(
                Config.WHATSAPP_API_URL, json=payload, headers=headers
            )

            if response.status_code != 200:
                logger.error(f"Erro ao enviar WhatsApp: {response.text}")
            else:
                logger.info(
                    f"WhatsApp enviado para {dados['advogado'].whatsapp} sobre publicação {dados['publicacao'].id}"
                )

        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {str(e)}")


# Tarefas Celery
@shared_task(bind=True, max_retries=3)
def monitorar_publicacoes_advogado(self, advogado_id):
    """
    Tarefa Celery para monitorar publicações de um advogado específico.

    Args:
        advogado_id: ID do advogado a ser monitorado
    """
    try:
        celery_logger.info(f"Iniciando monitoramento para advogado {advogado_id}")

        service = PJeMonitorService()

        # Executar busca de forma assíncrona
        loop = asyncio.get_event_loop()
        resultado = loop.run_until_complete(
            service.buscar_publicacoes_para_advogado(advogado_id)
        )

        # Processar publicações encontradas
        total, novas = service.processar_publicacoes(advogado_id, resultado)

        celery_logger.info(
            f"Monitoramento concluído para advogado {advogado_id}: {total} publicações, {novas} novas"
        )

        # Reagendar próximo monitoramento
        advogado = Advogado.objects.get(id=advogado_id)
        service.agendar_monitoramento_para_advogado(advogado)

        return f"Monitoramento concluído: {total} publicações, {novas} novas"

    except Exception as e:
        celery_logger.error(
            f"Erro no monitoramento do advogado {advogado_id}: {str(e)}"
        )

        # Tentar novamente em caso de falha
        try:
            self.retry(countdown=60 * 30)  # Tentar novamente em 30 minutos
        except Exception as retry_error:
            celery_logger.error(
                f"Falha definitiva no monitoramento do advogado {advogado_id}: {str(retry_error)}"
            )

            # Registrar log de erro
            LogMonitoramento.objects.create(
                advogado_id=advogado_id,
                status="FALHA",
                mensagem=f"Falha definitiva após {self.request.retries + 1} tentativas",
                erro=str(e),
            )

            # Reagendar com um intervalo maior
            service = PJeMonitorService()
            advogado = Advogado.objects.get(id=advogado_id)
            service.agendar_monitoramento_para_advogado(advogado)

            raise


@shared_task
def iniciar_monitoramento_diario():
    """
    Tarefa Celery para iniciar o monitoramento diário de todos os advogados.
    Esta tarefa deve ser agendada para execução periódica.
    """
    celery_logger.info("Iniciando monitoramento diário para todos os advogados")

    service = PJeMonitorService()
    service.agendar_monitoramento_para_todos_advogados()

    return "Monitoramento diário agendado para todos os advogados"


# Configuração de tarefas periódicas do Celery
app.conf.beat_schedule = {
    "monitoramento-diario": {
        "task": "pje_monitor_service.iniciar_monitoramento_diario",
        "schedule": crontab(hour=6, minute=0),  # Executar todos os dias às 6h da manhã
    },
}


# Função para inicialização do serviço
def inicializar_servico():
    """Inicializa o serviço de monitoramento."""
    logger.info("Inicializando serviço de monitoramento do PJe")

    service = PJeMonitorService()
    service.agendar_monitoramento_para_todos_advogados()

    logger.info("Serviço de monitoramento do PJe inicializado com sucesso")


# Ponto de entrada para execução direta
if __name__ == "__main__":
    inicializar_servico()
