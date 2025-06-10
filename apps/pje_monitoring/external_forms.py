"""
external_forms.py - Módulo de Gerenciamento de Formulários Externos para prudentIA

Este módulo implementa funcionalidades para criação, compartilhamento e processamento
de formulários externos para coleta de dados de clientes e processos, incluindo:
- Criação de formulários personalizados
- Integração com Google Forms
- Geração de links compartilháveis
- Processamento de respostas
- Geração automática de documentos a partir de respostas
- Notificações de novas respostas
"""

import os
import json
import uuid
import logging
import datetime
import secrets
import re
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict

# Bibliotecas para integração com Google Forms
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Bibliotecas para Django (assumindo uso do Django)
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Configurações
class Config:
    """Configurações para o módulo de formulários externos."""

    # Configurações gerais
    FORM_EXPIRY_DAYS = 30  # Dias até a expiração do formulário
    MAX_RESPONSES = 1000  # Máximo de respostas por formulário

    # Configurações de Google Forms
    GOOGLE_CREDENTIALS_FILE = os.getenv(
        "GOOGLE_CREDENTIALS_FILE", "google_credentials.json"
    )
    GOOGLE_FORM_DOMAIN = os.getenv("GOOGLE_FORM_DOMAIN", "docs.google.com")

    # Configurações de formulários personalizados
    CUSTOM_FORM_BASE_URL = os.getenv(
        "CUSTOM_FORM_BASE_URL", "https://forms.prudentia.com.br"
    )
    FORM_TEMPLATES_DIR = os.getenv("FORM_TEMPLATES_DIR", "form_templates")

    # Configurações de notificações
    NOTIFICATION_EMAIL = os.getenv(
        "NOTIFICATION_EMAIL", "notificacoes@prudentia.com.br"
    )
    NOTIFICATION_WHATSAPP_ENABLED = (
        os.getenv("NOTIFICATION_WHATSAPP_ENABLED", "true").lower() == "true"
    )
    WHATSAPP_API_URL = os.getenv(
        "WHATSAPP_API_URL", "https://api.whatsapp.com/v1/messages"
    )
    WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")


# Enums e tipos de dados
class FormType(Enum):
    """Tipos de formulários suportados."""

    CUSTOM = "custom"
    GOOGLE_FORMS = "google_forms"


class FieldType(Enum):
    """Tipos de campos suportados em formulários."""

    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    FILE = "file"
    HIDDEN = "hidden"


class FormPurpose(Enum):
    """Propósitos dos formulários."""

    CLIENT_REGISTRATION = "client_registration"
    CASE_REGISTRATION = "case_registration"
    DOCUMENT_REQUEST = "document_request"
    FEEDBACK = "feedback"
    CONTACT = "contact"
    CUSTOM = "custom"


@dataclass
class FormField:
    """Classe para representar um campo de formulário."""

    id: str
    name: str
    label: str
    type: FieldType
    required: bool = False
    placeholder: Optional[str] = None
    default_value: Optional[Any] = None
    options: List[Dict[str, str]] = field(default_factory=list)
    validation: Optional[Dict[str, Any]] = None
    help_text: Optional[str] = None
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converte o campo para um dicionário."""
        result = asdict(self)
        result["type"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormField":
        """Cria um objeto FormField a partir de um dicionário."""
        field_type = data.get("type")
        if isinstance(field_type, str):
            data["type"] = FieldType(field_type)
        return cls(**data)


@dataclass
class FormResponse:
    """Classe para representar uma resposta de formulário."""

    id: str
    form_id: str
    data: Dict[str, Any]
    submitted_at: datetime.datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    respondent_email: Optional[str] = None
    respondent_name: Optional[str] = None
    processed: bool = False
    processed_at: Optional[datetime.datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte a resposta para um dicionário."""
        result = asdict(self)
        result["submitted_at"] = self.submitted_at.isoformat()
        if self.processed_at:
            result["processed_at"] = self.processed_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormResponse":
        """Cria um objeto FormResponse a partir de um dicionário."""
        if isinstance(data.get("submitted_at"), str):
            data["submitted_at"] = datetime.datetime.fromisoformat(data["submitted_at"])
        if isinstance(data.get("processed_at"), str) and data["processed_at"]:
            data["processed_at"] = datetime.datetime.fromisoformat(data["processed_at"])
        return cls(**data)


# Modelos de dados (usando Django ORM)
class ExternalForm(models.Model):
    """Modelo para armazenar informações de formulários externos."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    form_type = models.CharField(
        max_length=20, choices=[(t.value, t.name) for t in FormType]
    )
    purpose = models.CharField(
        max_length=30, choices=[(p.value, p.name) for p in FormPurpose]
    )
    fields = models.JSONField()
    external_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # ID no sistema externo (Google Forms)
    external_url = models.URLField(null=True, blank=True)  # URL no sistema externo
    access_token = models.CharField(
        max_length=64, unique=True
    )  # Token para acesso ao formulário
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_forms"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)
    max_responses = models.IntegerField(default=Config.MAX_RESPONSES)
    response_count = models.IntegerField(default=0)
    success_message = models.TextField(null=True, blank=True)
    success_redirect_url = models.URLField(null=True, blank=True)
    notification_emails = models.JSONField(default=list)

    # Campos para integração com documentos
    document_template_id = models.CharField(max_length=255, null=True, blank=True)
    auto_generate_documents = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Formulário Externo"
        verbose_name_plural = "Formulários Externos"
        indexes = [
            models.Index(fields=["form_type"]),
            models.Index(fields=["purpose"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["access_token"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_form_type_display()})"

    def save(self, *args, **kwargs):
        # Gerar token de acesso se não existir
        if not self.access_token:
            self.access_token = secrets.token_hex(32)

        # Definir data de expiração se não existir
        if not self.expires_at:
            self.expires_at = timezone.now() + datetime.timedelta(
                days=Config.FORM_EXPIRY_DAYS
            )

        super().save(*args, **kwargs)

    @property
    def public_url(self):
        """Retorna a URL pública do formulário."""
        if self.form_type == FormType.GOOGLE_FORMS.value and self.external_url:
            return self.external_url

        return f"{Config.CUSTOM_FORM_BASE_URL}/{self.access_token}"

    @property
    def is_expired(self):
        """Verifica se o formulário expirou."""
        return self.expires_at and self.expires_at < timezone.now()

    @property
    def has_reached_max_responses(self):
        """Verifica se o formulário atingiu o número máximo de respostas."""
        return self.response_count >= self.max_responses

    @property
    def is_available(self):
        """Verifica se o formulário está disponível para respostas."""
        return (
            self.is_active
            and not self.is_expired
            and not self.has_reached_max_responses
        )


class FormResponseModel(models.Model):
    """Modelo para armazenar respostas de formulários."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        ExternalForm, on_delete=models.CASCADE, related_name="responses"
    )
    data = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    respondent_email = models.EmailField(null=True, blank=True)
    respondent_name = models.CharField(max_length=255, null=True, blank=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Campos para rastreamento de documentos gerados
    generated_documents = models.JSONField(default=list)

    class Meta:
        verbose_name = "Resposta de Formulário"
        verbose_name_plural = "Respostas de Formulários"
        indexes = [
            models.Index(fields=["form"]),
            models.Index(fields=["submitted_at"]),
            models.Index(fields=["processed"]),
            models.Index(fields=["respondent_email"]),
        ]

    def __str__(self):
        return f"Resposta de {self.respondent_name or 'Anônimo'} para {self.form.title}"

    def mark_as_processed(self):
        """Marca a resposta como processada."""
        self.processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=["processed", "processed_at"])

    def add_generated_document(
        self, document_type: str, document_path: str, document_id: Optional[str] = None
    ):
        """Adiciona um documento gerado à resposta."""
        doc_info = {
            "type": document_type,
            "path": document_path,
            "id": document_id,
            "generated_at": timezone.now().isoformat(),
        }

        self.generated_documents.append(doc_info)
        self.save(update_fields=["generated_documents"])


# Classes de serviço para formulários
class FormService:
    """Classe base para serviços de formulários."""

    def __init__(self):
        """Inicializa o serviço de formulários."""
        pass

    def create_form(
        self,
        title: str,
        fields: List[Dict[str, Any]],
        purpose: FormPurpose,
        description: Optional[str] = None,
        **kwargs,
    ) -> ExternalForm:
        """
        Cria um novo formulário.

        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            purpose: Propósito do formulário
            description: Descrição do formulário (opcional)
            **kwargs: Argumentos adicionais específicos do tipo de formulário

        Returns:
            ExternalForm: Objeto do formulário criado
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")

    def update_form(
        self,
        form_id: str,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> ExternalForm:
        """
        Atualiza um formulário existente.

        Args:
            form_id: ID do formulário
            title: Novo título do formulário (opcional)
            fields: Nova lista de campos do formulário (opcional)
            description: Nova descrição do formulário (opcional)
            **kwargs: Argumentos adicionais específicos do tipo de formulário

        Returns:
            ExternalForm: Objeto do formulário atualizado
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")

    def get_form(self, form_id: str) -> ExternalForm:
        """
        Obtém um formulário pelo ID.

        Args:
            form_id: ID do formulário

        Returns:
            ExternalForm: Objeto do formulário
        """
        try:
            return ExternalForm.objects.get(id=form_id)
        except ExternalForm.DoesNotExist:
            raise ValueError(f"Formulário com ID {form_id} não encontrado")

    def get_form_by_token(self, access_token: str) -> ExternalForm:
        """
        Obtém um formulário pelo token de acesso.

        Args:
            access_token: Token de acesso do formulário

        Returns:
            ExternalForm: Objeto do formulário
        """
        try:
            return ExternalForm.objects.get(access_token=access_token)
        except ExternalForm.DoesNotExist:
            raise ValueError(f"Formulário com token {access_token} não encontrado")

    def delete_form(self, form_id: str) -> bool:
        """
        Exclui um formulário.

        Args:
            form_id: ID do formulário

        Returns:
            bool: True se o formulário foi excluído com sucesso
        """
        try:
            form = self.get_form(form_id)
            form.delete()
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir formulário {form_id}: {e}")
            return False

    def get_form_responses(self, form_id: str) -> List[FormResponseModel]:
        """
        Obtém todas as respostas de um formulário.

        Args:
            form_id: ID do formulário

        Returns:
            List[FormResponseModel]: Lista de respostas do formulário
        """
        form = self.get_form(form_id)
        return FormResponseModel.objects.filter(form=form).order_by("-submitted_at")

    def process_form_response(
        self,
        form_id: str,
        response_data: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FormResponseModel:
        """
        Processa uma resposta de formulário.

        Args:
            form_id: ID do formulário
            response_data: Dados da resposta
            ip_address: Endereço IP do respondente (opcional)
            user_agent: User-Agent do navegador do respondente (opcional)

        Returns:
            FormResponseModel: Objeto da resposta processada
        """
        form = self.get_form(form_id)

        # Verificar se o formulário está disponível para respostas
        if not form.is_available:
            if form.is_expired:
                raise ValueError("Este formulário expirou")
            elif form.has_reached_max_responses:
                raise ValueError("Este formulário atingiu o número máximo de respostas")
            else:
                raise ValueError("Este formulário não está disponível para respostas")

        # Extrair informações do respondente
        respondent_email = None
        respondent_name = None

        # Buscar campos de email e nome nas respostas
        for field in form.fields:
            field_name = field.get("name", "").lower()
            field_type = field.get("type", "").lower()

            if field_type == "email" or "email" in field_name:
                respondent_email = response_data.get(field.get("name", ""))
            elif "nome" in field_name or "name" in field_name:
                respondent_name = response_data.get(field.get("name", ""))

        # Criar resposta
        with transaction.atomic():
            response = FormResponseModel.objects.create(
                form=form,
                data=response_data,
                ip_address=ip_address,
                user_agent=user_agent,
                respondent_email=respondent_email,
                respondent_name=respondent_name,
            )

            # Incrementar contador de respostas
            form.response_count += 1
            form.save(update_fields=["response_count"])

        # Enviar notificações
        self._send_response_notifications(form, response)

        # Gerar documentos automaticamente, se configurado
        if form.auto_generate_documents and form.document_template_id:
            self._generate_documents_from_response(form, response)

        return response

    def _send_response_notifications(
        self, form: ExternalForm, response: FormResponseModel
    ):
        """
        Envia notificações sobre uma nova resposta.

        Args:
            form: Objeto do formulário
            response: Objeto da resposta
        """
        # Verificar se há emails para notificação
        if not form.notification_emails:
            return

        # Preparar dados para o email
        context = {
            "form": form,
            "response": response,
            "response_data": response.data,
            "submitted_at": response.submitted_at.strftime("%d/%m/%Y %H:%M:%S"),
            "respondent_name": response.respondent_name or "Anônimo",
            "respondent_email": response.respondent_email or "N/A",
            "admin_url": f"/admin/external_forms/formresponsemodel/{response.id}/",
        }

        # Renderizar email
        subject = f"Nova resposta no formulário: {form.title}"
        html_message = render_to_string("emails/new_form_response.html", context)
        plain_message = render_to_string("emails/new_form_response.txt", context)

        # Enviar email
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=Config.NOTIFICATION_EMAIL,
                recipient_list=form.notification_emails,
                html_message=html_message,
            )
        except Exception as e:
            logger.error(f"Erro ao enviar notificação por email: {e}")

    def _generate_documents_from_response(
        self, form: ExternalForm, response: FormResponseModel
    ):
        """
        Gera documentos a partir de uma resposta de formulário.

        Args:
            form: Objeto do formulário
            response: Objeto da resposta
        """
        # Esta função seria implementada com a integração ao módulo de processamento de documentos
        # Por enquanto, apenas logamos a intenção
        logger.info(
            f"Gerando documentos para resposta {response.id} do formulário {form.id}"
        )

        # Em uma implementação real, chamaríamos o serviço de documentos
        # document_service = DocumentService()
        # generated_docs = document_service.generate_from_template(
        #     template_id=form.document_template_id,
        #     context=response.data
        # )
        #
        # for doc in generated_docs:
        #     response.add_generated_document(doc['type'], doc['path'], doc['id'])


class CustomFormService(FormService):
    """Serviço para formulários personalizados do prudentIA."""

    def create_form(
        self,
        title: str,
        fields: List[Dict[str, Any]],
        purpose: FormPurpose,
        description: Optional[str] = None,
        user=None,
        is_public: bool = False,
        success_message: Optional[str] = None,
        success_redirect_url: Optional[str] = None,
        notification_emails: Optional[List[str]] = None,
        expires_at: Optional[datetime.datetime] = None,
        max_responses: Optional[int] = None,
        document_template_id: Optional[str] = None,
        auto_generate_documents: bool = False,
    ) -> ExternalForm:
        """
        Cria um novo formulário personalizado.

        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            purpose: Propósito do formulário
            description: Descrição do formulário (opcional)
            user: Usuário criador do formulário
            is_public: Se o formulário é público
            success_message: Mensagem de sucesso após envio
            success_redirect_url: URL para redirecionamento após envio
            notification_emails: Lista de emails para notificação
            expires_at: Data de expiração do formulário
            max_responses: Número máximo de respostas
            document_template_id: ID do template de documento
            auto_generate_documents: Se deve gerar documentos automaticamente

        Returns:
            ExternalForm: Objeto do formulário criado
        """
        # Validar campos
        validated_fields = []
        for i, field_data in enumerate(fields):
            # Garantir que o campo tenha um ID
            if "id" not in field_data:
                field_data["id"] = f"field_{i+1}"

            # Garantir que o campo tenha um nome
            if "name" not in field_data:
                field_data["name"] = f"field_{i+1}"

            # Validar tipo do campo
            field_type = field_data.get("type")
            if field_type:
                try:
                    field_data["type"] = FieldType(field_type).value
                except ValueError:
                    field_data["type"] = FieldType.TEXT.value
            else:
                field_data["type"] = FieldType.TEXT.value

            # Adicionar ordem se não existir
            if "order" not in field_data:
                field_data["order"] = i

            validated_fields.append(field_data)

        # Criar formulário
        form = ExternalForm(
            title=title,
            description=description,
            form_type=FormType.CUSTOM.value,
            purpose=purpose.value,
            fields=validated_fields,
            created_by=user,
            is_public=is_public,
            success_message=success_message,
            success_redirect_url=success_redirect_url,
            notification_emails=notification_emails or [],
            expires_at=expires_at,
            max_responses=max_responses or Config.MAX_RESPONSES,
            document_template_id=document_template_id,
            auto_generate_documents=auto_generate_documents,
        )

        form.save()
        return form

    def update_form(
        self,
        form_id: str,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
        success_message: Optional[str] = None,
        success_redirect_url: Optional[str] = None,
        notification_emails: Optional[List[str]] = None,
        expires_at: Optional[datetime.datetime] = None,
        max_responses: Optional[int] = None,
        document_template_id: Optional[str] = None,
        auto_generate_documents: Optional[bool] = None,
    ) -> ExternalForm:
        """
        Atualiza um formulário personalizado existente.

        Args:
            form_id: ID do formulário
            title: Novo título do formulário (opcional)
            fields: Nova lista de campos do formulário (opcional)
            description: Nova descrição do formulário (opcional)
            is_public: Se o formulário é público (opcional)
            success_message: Mensagem de sucesso após envio (opcional)
            success_redirect_url: URL para redirecionamento após envio (opcional)
            notification_emails: Lista de emails para notificação (opcional)
            expires_at: Data de expiração do formulário (opcional)
            max_responses: Número máximo de respostas (opcional)
            document_template_id: ID do template de documento (opcional)
            auto_generate_documents: Se deve gerar documentos automaticamente (opcional)

        Returns:
            ExternalForm: Objeto do formulário atualizado
        """
        form = self.get_form(form_id)

        # Verificar se é um formulário personalizado
        if form.form_type != FormType.CUSTOM.value:
            raise ValueError(
                f"O formulário {form_id} não é um formulário personalizado"
            )

        # Atualizar campos
        if title is not None:
            form.title = title

        if description is not None:
            form.description = description

        if fields is not None:
            # Validar campos
            validated_fields = []
            for i, field_data in enumerate(fields):
                # Garantir que o campo tenha um ID
                if "id" not in field_data:
                    field_data["id"] = f"field_{i+1}"

                # Garantir que o campo tenha um nome
                if "name" not in field_data:
                    field_data["name"] = f"field_{i+1}"

                # Validar tipo do campo
                field_type = field_data.get("type")
                if field_type:
                    try:
                        field_data["type"] = FieldType(field_type).value
                    except ValueError:
                        field_data["type"] = FieldType.TEXT.value
                else:
                    field_data["type"] = FieldType.TEXT.value

                # Adicionar ordem se não existir
                if "order" not in field_data:
                    field_data["order"] = i

                validated_fields.append(field_data)

            form.fields = validated_fields

        if is_public is not None:
            form.is_public = is_public

        if success_message is not None:
            form.success_message = success_message

        if success_redirect_url is not None:
            form.success_redirect_url = success_redirect_url

        if notification_emails is not None:
            form.notification_emails = notification_emails

        if expires_at is not None:
            form.expires_at = expires_at

        if max_responses is not None:
            form.max_responses = max_responses

        if document_template_id is not None:
            form.document_template_id = document_template_id

        if auto_generate_documents is not None:
            form.auto_generate_documents = auto_generate_documents

        form.save()
        return form

    def render_form_html(self, form_id: str) -> str:
        """
        Renderiza o HTML de um formulário personalizado.

        Args:
            form_id: ID do formulário

        Returns:
            str: HTML do formulário
        """
        form = self.get_form(form_id)

        # Verificar se é um formulário personalizado
        if form.form_type != FormType.CUSTOM.value:
            raise ValueError(
                f"O formulário {form_id} não é um formulário personalizado"
            )

        # Em uma implementação real, renderizaríamos um template Django
        # Por enquanto, geramos um HTML básico
        html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{form.title}</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <style>
                :root {{
                    --color-primary: #FFC145;
                    --color-primary-dark: #CC972E;
                    --color-primary-light: #FFE5A6;
                    --color-secondary: #45A2FF;
                    --color-secondary-dark: #377FCC;
                    --color-bg: #F7F8FA;
                    --color-surface: #FFFFFF;
                    --color-text: #1E2025;
                    --color-text-light: #5A5D65;
                }}
                
                body {{
                    background-color: var(--color-bg);
                    color: var(--color-text);
                    font-family: 'Roboto', sans-serif;
                }}
                
                .form-container {{
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 30px;
                    background-color: var(--color-surface);
                    border-radius: 10px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                }}
                
                .form-header {{
                    margin-bottom: 30px;
                    text-align: center;
                }}
                
                .form-footer {{
                    margin-top: 30px;
                    text-align: center;
                }}
                
                .btn-primary {{
                    background-color: var(--color-primary);
                    border-color: var(--color-primary);
                }}
                
                .btn-primary:hover {{
                    background-color: var(--color-primary-dark);
                    border-color: var(--color-primary-dark);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-container">
                    <div class="form-header">
                        <h1>{form.title}</h1>
                        {f'<p>{form.description}</p>' if form.description else ''}
                    </div>
                    
                    <form id="custom-form" method="post" action="/api/forms/{form.access_token}/submit">
        """

        # Adicionar campos
        for field in form.fields:
            field_id = field.get("id")
            field_name = field.get("name")
            field_label = field.get("label")
            field_type = field.get("type")
            field_required = field.get("required", False)
            field_placeholder = field.get("placeholder", "")
            field_help = field.get("help_text", "")
            field_options = field.get("options", [])

            html += f"""
                        <div class="mb-3">
                            <label for="{field_id}" class="form-label">{field_label}{' *' if field_required else ''}</label>
            """

            if field_type == FieldType.TEXTAREA.value:
                html += f"""
                            <textarea class="form-control" id="{field_id}" name="{field_name}" 
                                placeholder="{field_placeholder}" {'required' if field_required else ''}></textarea>
                """
            elif field_type == FieldType.SELECT.value:
                html += f"""
                            <select class="form-select" id="{field_id}" name="{field_name}" {'required' if field_required else ''}>
                                <option value="">Selecione...</option>
                """
                for option in field_options:
                    option_value = option.get("value", "")
                    option_label = option.get("label", option_value)
                    html += f"""
                                <option value="{option_value}">{option_label}</option>
                    """
                html += """
                            </select>
                """
            elif field_type == FieldType.RADIO.value:
                for option in field_options:
                    option_value = option.get("value", "")
                    option_label = option.get("label", option_value)
                    html += f"""
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="{field_name}" 
                                    id="{field_id}_{option_value}" value="{option_value}" {'required' if field_required else ''}>
                                <label class="form-check-label" for="{field_id}_{option_value}">
                                    {option_label}
                                </label>
                            </div>
                    """
            elif field_type == FieldType.CHECKBOX.value:
                for option in field_options:
                    option_value = option.get("value", "")
                    option_label = option.get("label", option_value)
                    html += f"""
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" name="{field_name}[]" 
                                    id="{field_id}_{option_value}" value="{option_value}">
                                <label class="form-check-label" for="{field_id}_{option_value}">
                                    {option_label}
                                </label>
                            </div>
                    """
            elif field_type == FieldType.DATE.value:
                html += f"""
                            <input type="date" class="form-control" id="{field_id}" name="{field_name}" 
                                {'required' if field_required else ''}>
                """
            elif field_type == FieldType.TIME.value:
                html += f"""
                            <input type="time" class="form-control" id="{field_id}" name="{field_name}" 
                                {'required' if field_required else ''}>
                """
            elif field_type == FieldType.DATETIME.value:
                html += f"""
                            <input type="datetime-local" class="form-control" id="{field_id}" name="{field_name}" 
                                {'required' if field_required else ''}>
                """
            elif field_type == FieldType.FILE.value:
                html += f"""
                            <input type="file" class="form-control" id="{field_id}" name="{field_name}" 
                                {'required' if field_required else ''}>
                """
            elif field_type == FieldType.HIDDEN.value:
                html += f"""
                            <input type="hidden" id="{field_id}" name="{field_name}" 
                                value="{field.get('default_value', '')}">
                """
            else:  # TEXT, EMAIL, PHONE, NUMBER, etc.
                input_type = "text"
                if field_type == FieldType.EMAIL.value:
                    input_type = "email"
                elif field_type == FieldType.PHONE.value:
                    input_type = "tel"
                elif field_type == FieldType.NUMBER.value:
                    input_type = "number"

                html += f"""
                            <input type="{input_type}" class="form-control" id="{field_id}" name="{field_name}" 
                                placeholder="{field_placeholder}" {'required' if field_required else ''}>
                """

            if field_help:
                html += f"""
                            <div class="form-text">{field_help}</div>
                """

            html += """
                        </div>
            """

        # Adicionar botão de envio
        html += """
                        <div class="form-footer">
                            <button type="submit" class="btn btn-primary">Enviar</button>
                        </div>
                    </form>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                document.getElementById('custom-form').addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const form = e.target;
                    const formData = new FormData(form);
                    
                    fetch(form.action, {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Mostrar mensagem de sucesso
                            alert(data.message || 'Formulário enviado com sucesso!');
                            
                            // Redirecionar, se configurado
                            if (data.redirect_url) {
                                window.location.href = data.redirect_url;
                            } else {
                                form.reset();
                            }
                        } else {
                            // Mostrar mensagem de erro
                            alert(data.message || 'Erro ao enviar formulário. Tente novamente.');
                        }
                    })
                    .catch(error => {
                        console.error('Erro:', error);
                        alert('Erro ao enviar formulário. Tente novamente.');
                    });
                });
            </script>
        </body>
        </html>
        """

        return html


class GoogleFormService(FormService):
    """Serviço para integração com Google Forms."""

    def __init__(self):
        """Inicializa o serviço de Google Forms."""
        super().__init__()
        self.credentials = None
        self.forms_service = None
        self.drive_service = None
        self.sheets_service = None

        # Inicializar serviços
        self._init_services()

    def _init_services(self):
        """Inicializa os serviços do Google."""
        try:
            # Carregar credenciais
            self.credentials = service_account.Credentials.from_service_account_file(
                Config.GOOGLE_CREDENTIALS_FILE,
                scopes=[
                    "https://www.googleapis.com/auth/forms",
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )

            # Criar serviço do Forms
            self.forms_service = build("forms", "v1", credentials=self.credentials)

            # Criar serviço do Drive
            self.drive_service = build("drive", "v3", credentials=self.credentials)

            # Criar serviço do Sheets
            self.sheets_service = build("sheets", "v4", credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao inicializar serviços do Google: {e}")
            raise

    def create_form(
        self,
        title: str,
        fields: List[Dict[str, Any]],
        purpose: FormPurpose,
        description: Optional[str] = None,
        user=None,
        notification_emails: Optional[List[str]] = None,
        document_template_id: Optional[str] = None,
        auto_generate_documents: bool = False,
    ) -> ExternalForm:
        """
        Cria um novo formulário do Google.

        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            purpose: Propósito do formulário
            description: Descrição do formulário (opcional)
            user: Usuário criador do formulário
            notification_emails: Lista de emails para notificação
            document_template_id: ID do template de documento
            auto_generate_documents: Se deve gerar documentos automaticamente

        Returns:
            ExternalForm: Objeto do formulário criado
        """
        try:
            # Criar formulário no Google Forms
            form_body = {"info": {"title": title, "documentTitle": title}}

            if description:
                form_body["info"]["description"] = description

            # Criar formulário
            created_form = self.forms_service.forms().create(body=form_body).execute()
            form_id = created_form["formId"]

            # Adicionar campos
            requests = []
            for i, field_data in enumerate(fields):
                field_title = field_data.get("label", "")
                field_type = field_data.get("type", "")
                field_required = field_data.get("required", False)
                field_options = field_data.get("options", [])

                # Criar item de acordo com o tipo
                item = {"title": field_title, "required": field_required}

                if (
                    field_type == FieldType.TEXT.value
                    or field_type == FieldType.TEXTAREA.value
                ):
                    item["textQuestion"] = {
                        "paragraph": field_type == FieldType.TEXTAREA.value
                    }
                elif field_type == FieldType.CHECKBOX.value:
                    item["choiceQuestion"] = {
                        "type": "CHECKBOX",
                        "options": [
                            {"value": opt.get("label", opt.get("value", ""))}
                            for opt in field_options
                        ],
                    }
                elif (
                    field_type == FieldType.RADIO.value
                    or field_type == FieldType.SELECT.value
                ):
                    item["choiceQuestion"] = {
                        "type": "RADIO",
                        "options": [
                            {"value": opt.get("label", opt.get("value", ""))}
                            for opt in field_options
                        ],
                    }
                elif field_type == FieldType.DATE.value:
                    item["dateQuestion"] = {}
                elif field_type == FieldType.TIME.value:
                    item["timeQuestion"] = {}
                elif field_type == FieldType.SCALE.value:
                    item["scaleQuestion"] = {"low": 1, "high": 5}
                else:
                    # Tipo padrão: texto
                    item["textQuestion"] = {"paragraph": False}

                # Adicionar solicitação para criar item
                requests.append(
                    {"createItem": {"item": item, "location": {"index": i}}}
                )

            # Executar solicitações em lote
            if requests:
                self.forms_service.forms().batchUpdate(
                    formId=form_id, body={"requests": requests}
                ).execute()

            # Obter URL do formulário
            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

            # Criar registro no banco de dados
            form = ExternalForm(
                title=title,
                description=description,
                form_type=FormType.GOOGLE_FORMS.value,
                purpose=purpose.value,
                fields=fields,
                external_id=form_id,
                external_url=form_url,
                created_by=user,
                is_public=True,  # Formulários do Google são sempre públicos
                notification_emails=notification_emails or [],
                document_template_id=document_template_id,
                auto_generate_documents=auto_generate_documents,
            )

            form.save()
            return form
        except Exception as e:
            logger.error(f"Erro ao criar formulário do Google: {e}")
            raise

    def update_form(
        self,
        form_id: str,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        notification_emails: Optional[List[str]] = None,
        document_template_id: Optional[str] = None,
        auto_generate_documents: Optional[bool] = None,
    ) -> ExternalForm:
        """
        Atualiza um formulário do Google existente.

        Args:
            form_id: ID do formulário
            title: Novo título do formulário (opcional)
            fields: Nova lista de campos do formulário (opcional)
            description: Nova descrição do formulário (opcional)
            notification_emails: Lista de emails para notificação (opcional)
            document_template_id: ID do template de documento (opcional)
            auto_generate_documents: Se deve gerar documentos automaticamente (opcional)

        Returns:
            ExternalForm: Objeto do formulário atualizado
        """
        form = self.get_form(form_id)

        # Verificar se é um formulário do Google
        if form.form_type != FormType.GOOGLE_FORMS.value:
            raise ValueError(f"O formulário {form_id} não é um formulário do Google")

        try:
            # Atualizar formulário no Google Forms
            if title is not None or description is not None:
                update_mask = []
                info_update = {}

                if title is not None:
                    info_update["title"] = title
                    info_update["documentTitle"] = title
                    update_mask.append("title")
                    update_mask.append("documentTitle")

                if description is not None:
                    info_update["description"] = description
                    update_mask.append("description")

                self.forms_service.forms().batchUpdate(
                    formId=form.external_id,
                    body={
                        "requests": [
                            {
                                "updateFormInfo": {
                                    "info": info_update,
                                    "updateMask": ",".join(update_mask),
                                }
                            }
                        ]
                    },
                ).execute()

            # Atualizar campos
            if fields is not None:
                # Limpar campos existentes
                existing_form = (
                    self.forms_service.forms().get(formId=form.external_id).execute()
                )
                existing_items = existing_form.get("items", [])

                # Criar solicitações para excluir itens existentes
                delete_requests = []
                for item in existing_items:
                    delete_requests.append({"deleteItem": {"itemId": item["itemId"]}})

                # Executar exclusões
                if delete_requests:
                    self.forms_service.forms().batchUpdate(
                        formId=form.external_id, body={"requests": delete_requests}
                    ).execute()

                # Adicionar novos campos
                create_requests = []
                for i, field_data in enumerate(fields):
                    field_title = field_data.get("label", "")
                    field_type = field_data.get("type", "")
                    field_required = field_data.get("required", False)
                    field_options = field_data.get("options", [])

                    # Criar item de acordo com o tipo
                    item = {"title": field_title, "required": field_required}

                    if (
                        field_type == FieldType.TEXT.value
                        or field_type == FieldType.TEXTAREA.value
                    ):
                        item["textQuestion"] = {
                            "paragraph": field_type == FieldType.TEXTAREA.value
                        }
                    elif field_type == FieldType.CHECKBOX.value:
                        item["choiceQuestion"] = {
                            "type": "CHECKBOX",
                            "options": [
                                {"value": opt.get("label", opt.get("value", ""))}
                                for opt in field_options
                            ],
                        }
                    elif (
                        field_type == FieldType.RADIO.value
                        or field_type == FieldType.SELECT.value
                    ):
                        item["choiceQuestion"] = {
                            "type": "RADIO",
                            "options": [
                                {"value": opt.get("label", opt.get("value", ""))}
                                for opt in field_options
                            ],
                        }
                    elif field_type == FieldType.DATE.value:
                        item["dateQuestion"] = {}
                    elif field_type == FieldType.TIME.value:
                        item["timeQuestion"] = {}
                    elif field_type == FieldType.SCALE.value:
                        item["scaleQuestion"] = {"low": 1, "high": 5}
                    else:
                        # Tipo padrão: texto
                        item["textQuestion"] = {"paragraph": False}

                    # Adicionar solicitação para criar item
                    create_requests.append(
                        {"createItem": {"item": item, "location": {"index": i}}}
                    )

                # Executar solicitações em lote
                if create_requests:
                    self.forms_service.forms().batchUpdate(
                        formId=form.external_id, body={"requests": create_requests}
                    ).execute()

            # Atualizar registro no banco de dados
            if title is not None:
                form.title = title

            if description is not None:
                form.description = description

            if fields is not None:
                form.fields = fields

            if notification_emails is not None:
                form.notification_emails = notification_emails

            if document_template_id is not None:
                form.document_template_id = document_template_id

            if auto_generate_documents is not None:
                form.auto_generate_documents = auto_generate_documents

            form.save()
            return form
        except Exception as e:
            logger.error(f"Erro ao atualizar formulário do Google: {e}")
            raise

    def get_form_responses(self, form_id: str) -> List[FormResponseModel]:
        """
        Obtém todas as respostas de um formulário do Google.

        Args:
            form_id: ID do formulário

        Returns:
            List[FormResponseModel]: Lista de respostas do formulário
        """
        form = self.get_form(form_id)

        # Verificar se é um formulário do Google
        if form.form_type != FormType.GOOGLE_FORMS.value:
            raise ValueError(f"O formulário {form_id} não é um formulário do Google")

        try:
            # Obter respostas do banco de dados
            db_responses = FormResponseModel.objects.filter(form=form).order_by(
                "-submitted_at"
            )

            # Obter respostas do Google Forms
            try:
                google_responses = (
                    self.forms_service.forms()
                    .responses()
                    .list(formId=form.external_id)
                    .execute()
                )

                # Processar respostas do Google Forms
                for response_data in google_responses.get("responses", []):
                    response_id = response_data.get("responseId")

                    # Verificar se a resposta já existe no banco de dados
                    if not FormResponseModel.objects.filter(
                        form=form, data__responseId=response_id
                    ).exists():
                        # Obter detalhes da resposta
                        response_detail = (
                            self.forms_service.forms()
                            .responses()
                            .get(formId=form.external_id, responseId=response_id)
                            .execute()
                        )

                        # Processar dados da resposta
                        processed_data = self._process_google_form_response(
                            form, response_detail
                        )

                        # Criar resposta no banco de dados
                        FormResponseModel.objects.create(
                            form=form,
                            data=processed_data,
                            submitted_at=datetime.datetime.fromisoformat(
                                response_detail.get("lastSubmittedTime")
                            ),
                            respondent_email=processed_data.get("email"),
                            respondent_name=processed_data.get("nome"),
                        )

                # Atualizar contador de respostas
                response_count = FormResponseModel.objects.filter(form=form).count()
                if response_count != form.response_count:
                    form.response_count = response_count
                    form.save(update_fields=["response_count"])

                # Buscar respostas atualizadas
                return FormResponseModel.objects.filter(form=form).order_by(
                    "-submitted_at"
                )
            except Exception as e:
                logger.error(f"Erro ao obter respostas do Google Forms: {e}")
                # Retornar respostas do banco de dados em caso de erro
                return db_responses
        except Exception as e:
            logger.error(f"Erro ao obter respostas do formulário: {e}")
            raise

    def _process_google_form_response(
        self, form: ExternalForm, response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Processa uma resposta do Google Forms.

        Args:
            form: Objeto do formulário
            response_data: Dados da resposta do Google Forms

        Returns:
            Dict[str, Any]: Dados processados da resposta
        """
        processed_data = {
            "responseId": response_data.get("responseId"),
            "lastSubmittedTime": response_data.get("lastSubmittedTime"),
        }

        # Processar respostas para cada pergunta
        answers = response_data.get("answers", {})

        # Obter formulário do Google Forms para mapear IDs de perguntas para títulos
        try:
            google_form = (
                self.forms_service.forms().get(formId=form.external_id).execute()
            )
            items = google_form.get("items", [])

            # Criar mapeamento de ID para título e tipo
            id_to_title = {}
            id_to_type = {}

            for item in items:
                item_id = item.get("itemId")
                item_title = item.get("title")

                if "textQuestion" in item:
                    id_to_type[item_id] = "text"
                elif "choiceQuestion" in item:
                    choice_type = item.get("choiceQuestion", {}).get("type")
                    id_to_type[item_id] = (
                        "checkbox" if choice_type == "CHECKBOX" else "radio"
                    )
                elif "dateQuestion" in item:
                    id_to_type[item_id] = "date"
                elif "timeQuestion" in item:
                    id_to_type[item_id] = "time"
                elif "scaleQuestion" in item:
                    id_to_type[item_id] = "scale"
                else:
                    id_to_type[item_id] = "unknown"

                id_to_title[item_id] = item_title

            # Processar respostas
            for question_id, answer_data in answers.items():
                question_title = id_to_title.get(question_id, question_id)
                question_type = id_to_type.get(question_id, "unknown")

                # Normalizar chave da resposta
                key = slugify(question_title).replace("-", "_")

                # Extrair valor da resposta com base no tipo
                if question_type == "text":
                    text_answers = answer_data.get("textAnswers", {}).get("answers", [])
                    if text_answers:
                        processed_data[key] = text_answers[0].get("value", "")
                elif question_type == "checkbox":
                    choice_answers = answer_data.get("choiceAnswers", {}).get(
                        "answers", []
                    )
                    processed_data[key] = [
                        answer.get("value", "") for answer in choice_answers
                    ]
                elif question_type == "radio":
                    choice_answers = answer_data.get("choiceAnswers", {}).get(
                        "answers", []
                    )
                    if choice_answers:
                        processed_data[key] = choice_answers[0].get("value", "")
                elif question_type == "date":
                    date_answers = answer_data.get("dateAnswers", {}).get("answers", [])
                    if date_answers:
                        date_value = date_answers[0].get("value", {})
                        if date_value:
                            processed_data[key] = (
                                f"{date_value.get('day', 1):02d}/{date_value.get('month', 1):02d}/{date_value.get('year', 2023)}"
                            )
                elif question_type == "time":
                    time_answers = answer_data.get("timeAnswers", {}).get("answers", [])
                    if time_answers:
                        time_value = time_answers[0].get("value", {})
                        if time_value:
                            processed_data[key] = (
                                f"{time_value.get('hours', 0):02d}:{time_value.get('minutes', 0):02d}"
                            )
                elif question_type == "scale":
                    scale_answers = answer_data.get("scaleAnswers", {}).get(
                        "answers", []
                    )
                    if scale_answers:
                        processed_data[key] = scale_answers[0].get("value", 0)
                else:
                    # Tipo desconhecido - tentar extrair como texto
                    if "textAnswers" in answer_data:
                        text_answers = answer_data.get("textAnswers", {}).get(
                            "answers", []
                        )
                        if text_answers:
                            processed_data[key] = text_answers[0].get("value", "")

            # Tentar identificar email e nome
            for key, value in processed_data.items():
                if "email" in key.lower() and isinstance(value, str) and "@" in value:
                    processed_data["email"] = value
                elif "nome" in key.lower() and isinstance(value, str):
                    processed_data["nome"] = value

        except Exception as e:
            logger.error(f"Erro ao processar resposta do Google Forms: {e}")

        return processed_data


# Funções de utilidade
def create_form_service(
    form_type: FormType = None, form_id: Optional[str] = None
) -> FormService:
    """
    Cria um serviço de formulário apropriado.

    Args:
        form_type: Tipo de formulário (opcional)
        form_id: ID do formulário (opcional, para determinar o tipo)

    Returns:
        FormService: Serviço de formulário apropriado
    """
    if form_id and not form_type:
        try:
            form = ExternalForm.objects.get(id=form_id)
            form_type = FormType(form.form_type)
        except (ExternalForm.DoesNotExist, ValueError):
            form_type = FormType.CUSTOM

    if form_type == FormType.GOOGLE_FORMS:
        return GoogleFormService()
    else:
        return CustomFormService()


def create_client_registration_form(
    user, use_google_forms: bool = False
) -> ExternalForm:
    """
    Cria um formulário para cadastro de cliente.

    Args:
        user: Usuário criador do formulário
        use_google_forms: Se True, usa Google Forms; se False, usa formulário personalizado

    Returns:
        ExternalForm: Objeto do formulário criado
    """
    # Definir campos do formulário
    fields = [
        {
            "id": "nome",
            "name": "nome",
            "label": "Nome Completo",
            "type": FieldType.TEXT.value,
            "required": True,
        },
        {
            "id": "cpf",
            "name": "cpf",
            "label": "CPF",
            "type": FieldType.TEXT.value,
            "required": True,
            "placeholder": "000.000.000-00",
            "help_text": "Digite apenas números ou no formato 000.000.000-00",
        },
        {
            "id": "rg",
            "name": "rg",
            "label": "RG",
            "type": FieldType.TEXT.value,
            "required": True,
        },
        {
            "id": "data_nascimento",
            "name": "data_nascimento",
            "label": "Data de Nascimento",
            "type": FieldType.DATE.value,
            "required": True,
        },
        {
            "id": "estado_civil",
            "name": "estado_civil",
            "label": "Estado Civil",
            "type": FieldType.SELECT.value,
            "options": [
                {"value": "solteiro", "label": "Solteiro(a)"},
                {"value": "casado", "label": "Casado(a)"},
                {"value": "divorciado", "label": "Divorciado(a)"},
                {"value": "viuvo", "label": "Viúvo(a)"},
                {"value": "uniao_estavel", "label": "União Estável"},
            ],
            "required": True,
        },
        {
            "id": "profissao",
            "name": "profissao",
            "label": "Profissão",
            "type": FieldType.TEXT.value,
            "required": True,
        },
        {
            "id": "endereco",
            "name": "endereco",
            "label": "Endereço Completo",
            "type": FieldType.TEXTAREA.value,
            "required": True,
        },
        {
            "id": "cep",
            "name": "cep",
            "label": "CEP",
            "type": FieldType.TEXT.value,
            "placeholder": "00000-000",
            "required": True,
        },
        {
            "id": "cidade",
            "name": "cidade",
            "label": "Cidade",
            "type": FieldType.TEXT.value,
            "required": True,
        },
        {
            "id": "estado",
            "name": "estado",
            "label": "Estado",
            "type": FieldType.SELECT.value,
            "options": [
                {"value": "AC", "label": "Acre"},
                {"value": "AL", "label": "Alagoas"},
                {"value": "AP", "label": "Amapá"},
                {"value": "AM", "label": "Amazonas"},
                {"value": "BA", "label": "Bahia"},
                {"value": "CE", "label": "Ceará"},
                {"value": "DF", "label": "Distrito Federal"},
                {"value": "ES", "label": "Espírito Santo"},
                {"value": "GO", "label": "Goiás"},
                {"value": "MA", "label": "Maranhão"},
                {"value": "MT", "label": "Mato Grosso"},
                {"value": "MS", "label": "Mato Grosso do Sul"},
                {"value": "MG", "label": "Minas Gerais"},
                {"value": "PA", "label": "Pará"},
                {"value": "PB", "label": "Paraíba"},
                {"value": "PR", "label": "Paraná"},
                {"value": "PE", "label": "Pernambuco"},
                {"value": "PI", "label": "Piauí"},
                {"value": "RJ", "label": "Rio de Janeiro"},
                {"value": "RN", "label": "Rio Grande do Norte"},
                {"value": "RS", "label": "Rio Grande do Sul"},
                {"value": "RO", "label": "Rondônia"},
                {"value": "RR", "label": "Roraima"},
                {"value": "SC", "label": "Santa Catarina"},
                {"value": "SP", "label": "São Paulo"},
                {"value": "SE", "label": "Sergipe"},
                {"value": "TO", "label": "Tocantins"},
            ],
            "required": True,
        },
        {
            "id": "telefone",
            "name": "telefone",
            "label": "Telefone",
            "type": FieldType.PHONE.value,
            "required": True,
        },
        {
            "id": "email",
            "name": "email",
            "label": "Email",
            "type": FieldType.EMAIL.value,
            "required": True,
        },
    ]

    # Criar formulário usando o serviço apropriado
    service = create_form_service(
        FormType.GOOGLE_FORMS if use_google_forms else FormType.CUSTOM
    )

    form = service.create_form(
        title="Cadastro de Cliente",
        fields=fields,
        purpose=FormPurpose.CLIENT_REGISTRATION,
        description="Preencha este formulário para cadastro em nosso sistema.",
        user=user,
        notification_emails=[user.email] if hasattr(user, "email") else [],
        auto_generate_documents=True,
        document_template_id="procuracao_padrao",  # ID do template de procuração padrão
    )

    return form


def create_case_registration_form(user, use_google_forms: bool = False) -> ExternalForm:
    """
    Cria um formulário para cadastro de caso/processo.

    Args:
        user: Usuário criador do formulário
        use_google_forms: Se True, usa Google Forms; se False, usa formulário personalizado

    Returns:
        ExternalForm: Objeto do formulário criado
    """
    # Definir campos do formulário
    fields = [
        {
            "id": "tipo_caso",
            "name": "tipo_caso",
            "label": "Tipo de Caso",
            "type": FieldType.SELECT.value,
            "options": [
                {"value": "civel", "label": "Cível"},
                {"value": "trabalhista", "label": "Trabalhista"},
                {"value": "criminal", "label": "Criminal"},
                {"value": "familia", "label": "Família"},
                {"value": "tributario", "label": "Tributário"},
                {"value": "previdenciario", "label": "Previdenciário"},
                {"value": "administrativo", "label": "Administrativo"},
                {"value": "outro", "label": "Outro"},
            ],
            "required": True,
        },
        {
            "id": "descricao",
            "name": "descricao",
            "label": "Descrição do Caso",
            "type": FieldType.TEXTAREA.value,
            "required": True,
            "help_text": "Descreva detalhadamente o seu caso",
        },
        {
            "id": "numero_processo",
            "name": "numero_processo",
            "label": "Número do Processo (se já existir)",
            "type": FieldType.TEXT.value,
            "required": False,
            "help_text": "No formato NNNNNNN-DD.AAAA.J.TR.OOOO",
        },
        {
            "id": "vara_tribunal",
            "name": "vara_tribunal",
            "label": "Vara/Tribunal",
            "type": FieldType.TEXT.value,
            "required": False,
        },
        {
            "id": "parte_contraria",
            "name": "parte_contraria",
            "label": "Parte Contrária",
            "type": FieldType.TEXT.value,
            "required": True,
        },
        {
            "id": "valor_causa",
            "name": "valor_causa",
            "label": "Valor da Causa",
            "type": FieldType.TEXT.value,
            "required": True,
            "placeholder": "R$ 0,00",
        },
        {
            "id": "observacoes",
            "name": "observacoes",
            "label": "Observações Adicionais",
            "type": FieldType.TEXTAREA.value,
            "required": False,
        },
    ]

    # Criar formulário usando o serviço apropriado
    service = create_form_service(
        FormType.GOOGLE_FORMS if use_google_forms else FormType.CUSTOM
    )

    form = service.create_form(
        title="Cadastro de Caso/Processo",
        fields=fields,
        purpose=FormPurpose.CASE_REGISTRATION,
        description="Preencha este formulário para cadastrar um novo caso ou processo.",
        user=user,
        notification_emails=[user.email] if hasattr(user, "email") else [],
        auto_generate_documents=False,
    )

    return form


# Exemplo de uso
if __name__ == "__main__":
    # Este código seria executado em um ambiente Django
    pass
