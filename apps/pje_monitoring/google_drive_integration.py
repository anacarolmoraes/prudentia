"""
google_drive_integration.py - Módulo de Integração com Google Drive para prudentIA

Este módulo implementa a integração completa com o Google Drive, permitindo
que o prudentIA sincronize, armazene e gerencie documentos diretamente
com as contas do Google Drive dos advogados e do escritório.

Funcionalidades:
- Autenticação OAuth2 com Google Drive
- Upload e download de documentos
- Sincronização automática
- Compartilhamento e gerenciamento de permissões
- Backup automático de documentos
- Organização de documentos por pastas (processos, clientes, etc.)
"""

import os
import io
import json
import logging
import time
import mimetypes
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, BinaryIO

# Bibliotecas do Google
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

# Django imports (assumindo uso do Django)
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
class DriveConfig:
    """Configurações para a integração com o Google Drive."""
    
    # Escopos de acesso necessários
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.metadata',
    ]
    
    # Configurações de autenticação
    CLIENT_SECRET_FILE = os.getenv('GOOGLE_CLIENT_SECRET_FILE', 'client_secret.json')
    SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json')
    TOKEN_STORAGE_DIR = os.getenv('GOOGLE_TOKEN_STORAGE_DIR', 'tokens')
    API_NAME = 'drive'
    API_VERSION = 'v3'
    
    # Configurações de sincronização
    SYNC_INTERVAL = int(os.getenv('DRIVE_SYNC_INTERVAL', '3600'))  # 1 hora em segundos
    MAX_SYNC_RETRIES = 3
    
    # Estrutura de pastas padrão
    DEFAULT_FOLDERS = {
        'root': 'prudentIA',
        'processos': 'Processos',
        'clientes': 'Clientes',
        'modelos': 'Modelos de Documentos',
        'contratos': 'Contratos',
        'financeiro': 'Financeiro',
        'backup': 'Backup'
    }
    
    # Mapeamento de mimetypes
    MIME_TYPES = {
        'folder': 'application/vnd.google-apps.folder',
        'document': 'application/vnd.google-apps.document',
        'spreadsheet': 'application/vnd.google-apps.spreadsheet',
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }

# Modelos de dados (usando Django ORM)
class DriveCredential(models.Model):
    """Modelo para armazenar credenciais do Google Drive."""
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drive_credential')
    token_json = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Drive Credential - {self.user.email}"
    
    def to_credentials(self) -> Credentials:
        """Converte o modelo para um objeto Credentials do Google."""
        token_data = json.loads(self.token_json)
        creds = Credentials.from_authorized_user_info(token_data, DriveConfig.SCOPES)
        return creds
    
    @classmethod
    def from_credentials(cls, user, credentials: Credentials):
        """Cria ou atualiza um modelo a partir de um objeto Credentials."""
        token_json = credentials.to_json()
        
        drive_cred, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'token_json': token_json,
                'refresh_token': credentials.refresh_token,
                'expiry': credentials.expiry
            }
        )
        return drive_cred

class DriveFile(models.Model):
    """Modelo para rastrear arquivos sincronizados com o Google Drive."""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drive_files')
    drive_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    parent_folder_id = models.CharField(max_length=100, null=True, blank=True)
    local_path = models.CharField(max_length=255, null=True, blank=True)
    web_view_link = models.URLField(null=True, blank=True)
    last_modified = models.DateTimeField()
    last_synced = models.DateTimeField(auto_now=True)
    md5_checksum = models.CharField(max_length=32, null=True, blank=True)
    size = models.BigIntegerField(default=0)
    is_folder = models.BooleanField(default=False)
    is_trashed = models.BooleanField(default=False)
    
    # Campos para relacionamento com entidades do prudentIA
    processo_id = models.IntegerField(null=True, blank=True)
    cliente_id = models.IntegerField(null=True, blank=True)
    documento_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'drive_id')
        indexes = [
            models.Index(fields=['drive_id']),
            models.Index(fields=['parent_folder_id']),
            models.Index(fields=['processo_id']),
            models.Index(fields=['cliente_id']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.drive_id})"

class DriveSyncLog(models.Model):
    """Modelo para registrar logs de sincronização com o Google Drive."""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drive_sync_logs')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)  # 'success', 'error', 'partial'
    files_uploaded = models.IntegerField(default=0)
    files_downloaded = models.IntegerField(default=0)
    files_updated = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Sync Log - {self.user.email} - {self.start_time}"

# Classes de serviço
class DriveAuthService:
    """Serviço para autenticação com o Google Drive."""
    
    def __init__(self):
        """Inicializa o serviço de autenticação."""
        self._ensure_token_dir()
    
    def _ensure_token_dir(self):
        """Garante que o diretório para armazenar tokens exista."""
        os.makedirs(DriveConfig.TOKEN_STORAGE_DIR, exist_ok=True)
    
    def get_credentials_flow(self, redirect_uri: str) -> Flow:
        """
        Cria um fluxo de autenticação OAuth2 para obter credenciais.
        
        Args:
            redirect_uri: URI de redirecionamento após autenticação
            
        Returns:
            Flow: Objeto de fluxo de autenticação
        """
        try:
            with open(DriveConfig.CLIENT_SECRET_FILE, 'r') as file:
                client_config = json.load(file)
            
            flow = Flow.from_client_config(
                client_config,
                scopes=DriveConfig.SCOPES,
                redirect_uri=redirect_uri
            )
            return flow
        except Exception as e:
            logger.error(f"Erro ao criar fluxo de autenticação: {str(e)}")
            raise
    
    def get_authorization_url(self, flow: Flow) -> str:
        """
        Obtém a URL para autorização do usuário.
        
        Args:
            flow: Objeto de fluxo de autenticação
            
        Returns:
            str: URL de autorização
        """
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url
    
    def exchange_code(self, flow: Flow, code: str) -> Credentials:
        """
        Troca o código de autorização por credenciais.
        
        Args:
            flow: Objeto de fluxo de autenticação
            code: Código de autorização
            
        Returns:
            Credentials: Credenciais do Google
        """
        try:
            flow.fetch_token(code=code)
            return flow.credentials
        except Exception as e:
            logger.error(f"Erro ao trocar código por credenciais: {str(e)}")
            raise
    
    def save_credentials(self, user, credentials: Credentials) -> DriveCredential:
        """
        Salva as credenciais no banco de dados.
        
        Args:
            user: Usuário do Django
            credentials: Credenciais do Google
            
        Returns:
            DriveCredential: Objeto de credencial salvo
        """
        return DriveCredential.from_credentials(user, credentials)
    
    def get_credentials(self, user) -> Optional[Credentials]:
        """
        Obtém as credenciais para um usuário.
        
        Args:
            user: Usuário do Django
            
        Returns:
            Optional[Credentials]: Credenciais do Google ou None se não encontradas
        """
        try:
            drive_cred = DriveCredential.objects.get(user=user)
            creds = drive_cred.to_credentials()
            
            # Verificar se as credenciais expiraram e precisam ser atualizadas
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.save_credentials(user, creds)
            
            return creds
        except DriveCredential.DoesNotExist:
            logger.warning(f"Credenciais não encontradas para o usuário {user.email}")
            return None
        except RefreshError as e:
            logger.error(f"Erro ao atualizar token: {str(e)}")
            return None
    
    def revoke_credentials(self, user):
        """
        Revoga as credenciais de um usuário.
        
        Args:
            user: Usuário do Django
        """
        try:
            drive_cred = DriveCredential.objects.get(user=user)
            creds = drive_cred.to_credentials()
            
            # Revogar token
            revoke = Request()
            revoke.post(
                url='https://oauth2.googleapis.com/revoke',
                params={'token': creds.token},
                headers={'content-type': 'application/x-www-form-urlencoded'}
            )
            
            # Remover do banco de dados
            drive_cred.delete()
            logger.info(f"Credenciais revogadas para o usuário {user.email}")
        except DriveCredential.DoesNotExist:
            logger.warning(f"Não há credenciais para revogar para o usuário {user.email}")
        except Exception as e:
            logger.error(f"Erro ao revogar credenciais: {str(e)}")
            raise

class DriveService:
    """Serviço para operações com o Google Drive."""
    
    def __init__(self, credentials: Credentials):
        """
        Inicializa o serviço do Drive.
        
        Args:
            credentials: Credenciais do Google
        """
        self.service = build(
            DriveConfig.API_NAME,
            DriveConfig.API_VERSION,
            credentials=credentials,
            cache_discovery=False
        )
    
    def list_files(self, folder_id: Optional[str] = None, query: Optional[str] = None) -> List[Dict]:
        """
        Lista arquivos e pastas no Google Drive.
        
        Args:
            folder_id: ID da pasta para listar (None para raiz)
            query: Query personalizada para filtrar resultados
            
        Returns:
            List[Dict]: Lista de arquivos e pastas
        """
        try:
            if folder_id:
                q = f"'{folder_id}' in parents"
            else:
                q = "'root' in parents"
            
            if query:
                q += f" and {query}"
            
            # Adicionar filtro para não mostrar itens na lixeira
            q += " and trashed=false"
            
            results = []
            page_token = None
            
            while True:
                response = self.service.files().list(
                    q=q,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size)',
                    pageToken=page_token
                ).execute()
                
                results.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                
                if not page_token:
                    break
            
            return results
        except HttpError as e:
            logger.error(f"Erro ao listar arquivos: {str(e)}")
            raise
    
    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict:
        """
        Cria uma pasta no Google Drive.
        
        Args:
            name: Nome da pasta
            parent_id: ID da pasta pai (None para raiz)
            
        Returns:
            Dict: Informações da pasta criada
        """
        try:
            file_metadata = {
                'name': name,
                'mimeType': DriveConfig.MIME_TYPES['folder']
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, mimeType, parents, webViewLink'
            ).execute()
            
            return folder
        except HttpError as e:
            logger.error(f"Erro ao criar pasta: {str(e)}")
            raise
    
    def upload_file(self, 
                   file_path: str, 
                   parent_id: Optional[str] = None, 
                   file_name: Optional[str] = None) -> Dict:
        """
        Faz upload de um arquivo para o Google Drive.
        
        Args:
            file_path: Caminho do arquivo local
            parent_id: ID da pasta de destino (None para raiz)
            file_name: Nome personalizado para o arquivo (None para usar o nome original)
            
        Returns:
            Dict: Informações do arquivo enviado
        """
        try:
            if not file_name:
                file_name = os.path.basename(file_path)
            
            file_metadata = {
                'name': file_name
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size'
            ).execute()
            
            return file
        except HttpError as e:
            logger.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            raise
    
    def upload_file_content(self, 
                          content: Union[bytes, BinaryIO], 
                          file_name: str, 
                          mime_type: str,
                          parent_id: Optional[str] = None) -> Dict:
        """
        Faz upload do conteúdo de um arquivo para o Google Drive.
        
        Args:
            content: Conteúdo do arquivo em bytes ou como objeto de arquivo
            file_name: Nome do arquivo
            mime_type: Tipo MIME do arquivo
            parent_id: ID da pasta de destino (None para raiz)
            
        Returns:
            Dict: Informações do arquivo enviado
        """
        try:
            file_metadata = {
                'name': file_name
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            if isinstance(content, bytes):
                fh = io.BytesIO(content)
            else:
                fh = content
            
            media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size'
            ).execute()
            
            return file
        except HttpError as e:
            logger.error(f"Erro ao fazer upload do conteúdo: {str(e)}")
            raise
    
    def download_file(self, file_id: str, local_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Baixa um arquivo do Google Drive.
        
        Args:
            file_id: ID do arquivo no Google Drive
            local_path: Caminho local para salvar o arquivo (None para retornar bytes)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo salvo ou conteúdo em bytes
        """
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            if local_path:
                with open(local_path, 'wb') as f:
                    downloader = MediaIoBaseDownload(f, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                return local_path
            else:
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                return fh.read()
        except HttpError as e:
            logger.error(f"Erro ao baixar arquivo: {str(e)}")
            raise
    
    def get_file(self, file_id: str) -> Dict:
        """
        Obtém metadados de um arquivo.
        
        Args:
            file_id: ID do arquivo no Google Drive
            
        Returns:
            Dict: Metadados do arquivo
        """
        try:
            return self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size, trashed'
            ).execute()
        except HttpError as e:
            logger.error(f"Erro ao obter metadados do arquivo: {str(e)}")
            raise
    
    def update_file(self, 
                   file_id: str, 
                   file_path: Optional[str] = None,
                   content: Optional[Union[bytes, BinaryIO]] = None,
                   mime_type: Optional[str] = None) -> Dict:
        """
        Atualiza o conteúdo de um arquivo.
        
        Args:
            file_id: ID do arquivo no Google Drive
            file_path: Caminho do arquivo local (alternativa a content)
            content: Conteúdo do arquivo em bytes ou como objeto de arquivo (alternativa a file_path)
            mime_type: Tipo MIME do arquivo (obrigatório se content for fornecido)
            
        Returns:
            Dict: Informações do arquivo atualizado
        """
        try:
            if file_path:
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = 'application/octet-stream'
                media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            elif content:
                if not mime_type:
                    raise ValueError("mime_type é obrigatório quando content é fornecido")
                
                if isinstance(content, bytes):
                    fh = io.BytesIO(content)
                else:
                    fh = content
                
                media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True)
            else:
                raise ValueError("file_path ou content deve ser fornecido")
            
            file = self.service.files().update(
                fileId=file_id,
                media_body=media,
                fields='id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size'
            ).execute()
            
            return file
        except HttpError as e:
            logger.error(f"Erro ao atualizar arquivo: {str(e)}")
            raise
    
    def update_file_metadata(self, file_id: str, metadata: Dict) -> Dict:
        """
        Atualiza os metadados de um arquivo.
        
        Args:
            file_id: ID do arquivo no Google Drive
            metadata: Dicionário com os metadados a serem atualizados
            
        Returns:
            Dict: Informações do arquivo atualizado
        """
        try:
            file = self.service.files().update(
                fileId=file_id,
                body=metadata,
                fields='id, name, mimeType, parents, webViewLink, modifiedTime'
            ).execute()
            
            return file
        except HttpError as e:
            logger.error(f"Erro ao atualizar metadados do arquivo: {str(e)}")
            raise
    
    def delete_file(self, file_id: str, permanent: bool = False):
        """
        Exclui um arquivo ou pasta.
        
        Args:
            file_id: ID do arquivo ou pasta no Google Drive
            permanent: Se True, exclui permanentemente; se False, move para a lixeira
        """
        try:
            if permanent:
                self.service.files().delete(fileId=file_id).execute()
            else:
                self.service.files().update(
                    fileId=file_id,
                    body={'trashed': True}
                ).execute()
        except HttpError as e:
            logger.error(f"Erro ao excluir arquivo: {str(e)}")
            raise
    
    def share_file(self, 
                  file_id: str, 
                  email: str, 
                  role: str = 'reader', 
                  send_notification: bool = True,
                  message: Optional[str] = None) -> Dict:
        """
        Compartilha um arquivo ou pasta com um usuário.
        
        Args:
            file_id: ID do arquivo ou pasta no Google Drive
            email: Email do usuário para compartilhar
            role: Papel do usuário ('reader', 'writer', 'commenter', 'owner')
            send_notification: Se True, envia email de notificação
            message: Mensagem personalizada para o email de notificação
            
        Returns:
            Dict: Informações da permissão criada
        """
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            return self.service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=send_notification,
                emailMessage=message,
                fields='id, emailAddress, role'
            ).execute()
        except HttpError as e:
            logger.error(f"Erro ao compartilhar arquivo: {str(e)}")
            raise
    
    def list_permissions(self, file_id: str) -> List[Dict]:
        """
        Lista permissões de um arquivo ou pasta.
        
        Args:
            file_id: ID do arquivo ou pasta no Google Drive
            
        Returns:
            List[Dict]: Lista de permissões
        """
        try:
            response = self.service.permissions().list(
                fileId=file_id,
                fields='permissions(id, emailAddress, role, type)'
            ).execute()
            
            return response.get('permissions', [])
        except HttpError as e:
            logger.error(f"Erro ao listar permissões: {str(e)}")
            raise
    
    def remove_permission(self, file_id: str, permission_id: str):
        """
        Remove uma permissão de um arquivo ou pasta.
        
        Args:
            file_id: ID do arquivo ou pasta no Google Drive
            permission_id: ID da permissão a ser removida
        """
        try:
            self.service.permissions().delete(
                fileId=file_id,
                permissionId=permission_id
            ).execute()
        except HttpError as e:
            logger.error(f"Erro ao remover permissão: {str(e)}")
            raise
    
    def create_shortcut(self, target_id: str, name: str, parent_id: Optional[str] = None) -> Dict:
        """
        Cria um atalho para um arquivo ou pasta.
        
        Args:
            target_id: ID do arquivo ou pasta alvo
            name: Nome do atalho
            parent_id: ID da pasta onde o atalho será criado (None para raiz)
            
        Returns:
            Dict: Informações do atalho criado
        """
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.shortcut',
                'shortcutDetails': {
                    'targetId': target_id
                }
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            shortcut = self.service.files().create(
                body=file_metadata,
                fields='id, name, mimeType, parents, webViewLink'
            ).execute()
            
            return shortcut
        except HttpError as e:
            logger.error(f"Erro ao criar atalho: {str(e)}")
            raise
    
    def search_files(self, query: str) -> List[Dict]:
        """
        Pesquisa arquivos no Google Drive.
        
        Args:
            query: Query de pesquisa
            
        Returns:
            List[Dict]: Lista de arquivos encontrados
        """
        try:
            results = []
            page_token = None
            
            while True:
                response = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, parents, webViewLink, modifiedTime, md5Checksum, size)',
                    pageToken=page_token
                ).execute()
                
                results.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                
                if not page_token:
                    break
            
            return results
        except HttpError as e:
            logger.error(f"Erro ao pesquisar arquivos: {str(e)}")
            raise

class DriveSyncService:
    """Serviço para sincronização com o Google Drive."""
    
    def __init__(self, user):
        """
        Inicializa o serviço de sincronização.
        
        Args:
            user: Usuário do Django
        """
        self.user = user
        self.auth_service = DriveAuthService()
        
        credentials = self.auth_service.get_credentials(user)
        if not credentials:
            raise ValueError(f"Credenciais não disponíveis para o usuário {user.email}")
        
        self.drive_service = DriveService(credentials)
        self.sync_log = None
    
    def _start_sync_log(self):
        """Inicia um registro de log de sincronização."""
        self.sync_log = DriveSyncLog.objects.create(
            user=self.user,
            status='in_progress'
        )
    
    def _finish_sync_log(self, status='success', error_message=None):
        """Finaliza um registro de log de sincronização."""
        if self.sync_log:
            self.sync_log.status = status
            self.sync_log.end_time = timezone.now()
            if error_message:
                self.sync_log.error_message = error_message
            self.sync_log.save()
    
    def _increment_sync_counter(self, counter_type):
        """Incrementa um contador no log de sincronização."""
        if self.sync_log:
            if counter_type == 'uploaded':
                self.sync_log.files_uploaded += 1
            elif counter_type == 'downloaded':
                self.sync_log.files_downloaded += 1
            elif counter_type == 'updated':
                self.sync_log.files_updated += 1
            self.sync_log.save()
    
    def ensure_default_folders(self) -> Dict[str, str]:
        """
        Garante que as pastas padrão existam no Google Drive.
        
        Returns:
            Dict[str, str]: Mapeamento de nomes de pastas para IDs
        """
        folder_ids = {}
        
        try:
            # Verificar se a pasta raiz já existe
            root_query = f"name='{DriveConfig.DEFAULT_FOLDERS['root']}' and mimeType='{DriveConfig.MIME_TYPES['folder']}' and trashed=false"
            root_results = self.drive_service.search_files(root_query)
            
            if root_results:
                root_folder = root_results[0]
                root_id = root_folder['id']
                folder_ids['root'] = root_id
            else:
                # Criar pasta raiz
                root_folder = self.drive_service.create_folder(DriveConfig.DEFAULT_FOLDERS['root'])
                root_id = root_folder['id']
                folder_ids['root'] = root_id
            
            # Verificar e criar subpastas
            for key, folder_name in DriveConfig.DEFAULT_FOLDERS.items():
                if key == 'root':
                    continue
                
                folder_query = f"name='{folder_name}' and mimeType='{DriveConfig.MIME_TYPES['folder']}' and '{root_id}' in parents and trashed=false"
                folder_results = self.drive_service.search_files(folder_query)
                
                if folder_results:
                    folder_ids[key] = folder_results[0]['id']
                else:
                    folder = self.drive_service.create_folder(folder_name, root_id)
                    folder_ids[key] = folder['id']
            
            return folder_ids
        except Exception as e:
            logger.error(f"Erro ao criar estrutura de pastas: {str(e)}")
            if self.sync_log:
                self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def sync_file_to_drive(self, 
                          local_path: str, 
                          folder_key: str, 
                          file_name: Optional[str] = None,
                          process_id: Optional[int] = None,
                          client_id: Optional[int] = None,
                          document_id: Optional[int] = None) -> DriveFile:
        """
        Sincroniza um arquivo local para o Google Drive.
        
        Args:
            local_path: Caminho do arquivo local
            folder_key: Chave da pasta de destino (ex: 'processos', 'clientes')
            file_name: Nome personalizado para o arquivo (None para usar o nome original)
            process_id: ID do processo relacionado (opcional)
            client_id: ID do cliente relacionado (opcional)
            document_id: ID do documento relacionado (opcional)
            
        Returns:
            DriveFile: Objeto do arquivo sincronizado
        """
        try:
            # Garantir que as pastas padrão existam
            folder_ids = self.ensure_default_folders()
            
            if folder_key not in folder_ids:
                raise ValueError(f"Pasta '{folder_key}' não encontrada")
            
            folder_id = folder_ids[folder_key]
            
            # Verificar se o arquivo já existe no Drive
            if not file_name:
                file_name = os.path.basename(local_path)
            
            file_query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            file_results = self.drive_service.search_files(file_query)
            
            if file_results:
                # Atualizar arquivo existente
                drive_file_info = self.drive_service.update_file(file_results[0]['id'], file_path=local_path)
                action = 'updated'
            else:
                # Fazer upload de novo arquivo
                drive_file_info = self.drive_service.upload_file(local_path, folder_id, file_name)
                action = 'uploaded'
            
            # Salvar ou atualizar registro no banco de dados
            drive_file, created = DriveFile.objects.update_or_create(
                user=self.user,
                drive_id=drive_file_info['id'],
                defaults={
                    'name': drive_file_info['name'],
                    'mime_type': drive_file_info['mimeType'],
                    'parent_folder_id': folder_id,
                    'local_path': local_path,
                    'web_view_link': drive_file_info.get('webViewLink'),
                    'last_modified': datetime.fromisoformat(drive_file_info['modifiedTime'].replace('Z', '+00:00')),
                    'md5_checksum': drive_file_info.get('md5Checksum'),
                    'size': int(drive_file_info.get('size', 0)),
                    'is_folder': drive_file_info['mimeType'] == DriveConfig.MIME_TYPES['folder'],
                    'processo_id': process_id,
                    'cliente_id': client_id,
                    'documento_id': document_id
                }
            )
            
            # Atualizar contador no log de sincronização
            if action == 'uploaded':
                self._increment_sync_counter('uploaded')
            else:
                self._increment_sync_counter('updated')
            
            return drive_file
        except Exception as e:
            logger.error(f"Erro ao sincronizar arquivo para o Drive: {str(e)}")
            if self.sync_log:
                self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def sync_content_to_drive(self,
                            content: Union[bytes, BinaryIO],
                            file_name: str,
                            mime_type: str,
                            folder_key: str,
                            process_id: Optional[int] = None,
                            client_id: Optional[int] = None,
                            document_id: Optional[int] = None) -> DriveFile:
        """
        Sincroniza conteúdo em memória para o Google Drive.
        
        Args:
            content: Conteúdo do arquivo em bytes ou como objeto de arquivo
            file_name: Nome do arquivo
            mime_type: Tipo MIME do arquivo
            folder_key: Chave da pasta de destino (ex: 'processos', 'clientes')
            process_id: ID do processo relacionado (opcional)
            client_id: ID do cliente relacionado (opcional)
            document_id: ID do documento relacionado (opcional)
            
        Returns:
            DriveFile: Objeto do arquivo sincronizado
        """
        try:
            # Garantir que as pastas padrão existam
            folder_ids = self.ensure_default_folders()
            
            if folder_key not in folder_ids:
                raise ValueError(f"Pasta '{folder_key}' não encontrada")
            
            folder_id = folder_ids[folder_key]
            
            # Verificar se o arquivo já existe no Drive
            file_query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            file_results = self.drive_service.search_files(file_query)
            
            if file_results:
                # Atualizar arquivo existente
                drive_file_info = self.drive_service.update_file(
                    file_results[0]['id'],
                    content=content,
                    mime_type=mime_type
                )
                action = 'updated'
            else:
                # Fazer upload de novo arquivo
                drive_file_info = self.drive_service.upload_file_content(
                    content,
                    file_name,
                    mime_type,
                    folder_id
                )
                action = 'uploaded'
            
            # Salvar ou atualizar registro no banco de dados
            drive_file, created = DriveFile.objects.update_or_create(
                user=self.user,
                drive_id=drive_file_info['id'],
                defaults={
                    'name': drive_file_info['name'],
                    'mime_type': drive_file_info['mimeType'],
                    'parent_folder_id': folder_id,
                    'web_view_link': drive_file_info.get('webViewLink'),
                    'last_modified': datetime.fromisoformat(drive_file_info['modifiedTime'].replace('Z', '+00:00')),
                    'md5_checksum': drive_file_info.get('md5Checksum'),
                    'size': int(drive_file_info.get('size', 0)),
                    'is_folder': False,
                    'processo_id': process_id,
                    'cliente_id': client_id,
                    'documento_id': document_id
                }
            )
            
            # Atualizar contador no log de sincronização
            if action == 'uploaded':
                self._increment_sync_counter('uploaded')
            else:
                self._increment_sync_counter('updated')
            
            return drive_file
        except Exception as e:
            logger.error(f"Erro ao sincronizar conteúdo para o Drive: {str(e)}")
            if self.sync_log:
                self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def sync_file_from_drive(self, drive_id: str, local_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Sincroniza um arquivo do Google Drive para o local.
        
        Args:
            drive_id: ID do arquivo no Google Drive
            local_path: Caminho local para salvar o arquivo (None para retornar bytes)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo salvo ou conteúdo em bytes
        """
        try:
            # Baixar o arquivo
            result = self.drive_service.download_file(drive_id, local_path)
            
            # Atualizar registro no banco de dados
            try:
                drive_file = DriveFile.objects.get(user=self.user, drive_id=drive_id)
                
                if local_path:
                    drive_file.local_path = local_path
                    drive_file.last_synced = timezone.now()
                    drive_file.save()
                
                # Atualizar contador no log de sincronização
                self._increment_sync_counter('downloaded')
            except DriveFile.DoesNotExist:
                # Obter informações do arquivo e criar registro
                file_info = self.drive_service.get_file(drive_id)
                
                drive_file = DriveFile.objects.create(
                    user=self.user,
                    drive_id=drive_id,
                    name=file_info['name'],
                    mime_type=file_info['mimeType'],
                    parent_folder_id=file_info.get('parents', [None])[0],
                    local_path=local_path,
                    web_view_link=file_info.get('webViewLink'),
                    last_modified=datetime.fromisoformat(file_info['modifiedTime'].replace('Z', '+00:00')),
                    md5_checksum=file_info.get('md5Checksum'),
                    size=int(file_info.get('size', 0)),
                    is_folder=file_info['mimeType'] == DriveConfig.MIME_TYPES['folder']
                )
                
                # Atualizar contador no log de sincronização
                self._increment_sync_counter('downloaded')
            
            return result
        except Exception as e:
            logger.error(f"Erro ao sincronizar arquivo do Drive: {str(e)}")
            if self.sync_log:
                self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def sync_all_files_to_drive(self, 
                               local_dir: str, 
                               folder_key: str,
                               process_id: Optional[int] = None,
                               client_id: Optional[int] = None) -> List[DriveFile]:
        """
        Sincroniza todos os arquivos de um diretório local para o Google Drive.
        
        Args:
            local_dir: Caminho do diretório local
            folder_key: Chave da pasta de destino (ex: 'processos', 'clientes')
            process_id: ID do processo relacionado (opcional)
            client_id: ID do cliente relacionado (opcional)
            
        Returns:
            List[DriveFile]: Lista de objetos dos arquivos sincronizados
        """
        try:
            self._start_sync_log()
            
            # Garantir que as pastas padrão existam
            folder_ids = self.ensure_default_folders()
            
            if folder_key not in folder_ids:
                raise ValueError(f"Pasta '{folder_key}' não encontrada")
            
            folder_id = folder_ids[folder_key]
            
            # Listar arquivos no diretório local
            local_files = []
            for root, _, files in os.walk(local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    rel_path = os.path.relpath(local_path, local_dir)
                    local_files.append((local_path, rel_path))
            
            # Sincronizar cada arquivo
            synced_files = []
            for local_path, rel_path in local_files:
                # Criar estrutura de pastas no Drive se necessário
                current_folder_id = folder_id
                if os.path.dirname(rel_path):
                    parts = os.path.dirname(rel_path).split(os.path.sep)
                    for part in parts:
                        # Verificar se a pasta já existe
                        folder_query = f"name='{part}' and mimeType='{DriveConfig.MIME_TYPES['folder']}' and '{current_folder_id}' in parents and trashed=false"
                        folder_results = self.drive_service.search_files(folder_query)
                        
                        if folder_results:
                            current_folder_id = folder_results[0]['id']
                        else:
                            folder = self.drive_service.create_folder(part, current_folder_id)
                            current_folder_id = folder['id']
                
                # Sincronizar o arquivo
                file_name = os.path.basename(rel_path)
                drive_file = self.sync_file_to_drive(
                    local_path,
                    folder_key,
                    file_name=file_name,
                    process_id=process_id,
                    client_id=client_id
                )
                synced_files.append(drive_file)
            
            self._finish_sync_log()
            return synced_files
        except Exception as e:
            logger.error(f"Erro ao sincronizar diretório para o Drive: {str(e)}")
            self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def backup_to_drive(self, 
                       data_type: str, 
                       content: Union[bytes, BinaryIO],
                       file_name: Optional[str] = None) -> DriveFile:
        """
        Realiza backup de dados para o Google Drive.
        
        Args:
            data_type: Tipo de dados (ex: 'database', 'files', 'settings')
            content: Conteúdo do backup em bytes ou como objeto de arquivo
            file_name: Nome personalizado para o arquivo (None para gerar nome automático)
            
        Returns:
            DriveFile: Objeto do arquivo de backup
        """
        try:
            self._start_sync_log()
            
            # Gerar nome de arquivo se não fornecido
            if not file_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_name = f"backup_{data_type}_{timestamp}.zip"
            
            # Sincronizar para a pasta de backup
            drive_file = self.sync_content_to_drive(
                content,
                file_name,
                'application/zip',
                'backup'
            )
            
            self._finish_sync_log()
            return drive_file
        except Exception as e:
            logger.error(f"Erro ao fazer backup para o Drive: {str(e)}")
            self._finish_sync_log(status='error', error_message=str(e))
            raise
    
    def share_with_client(self, 
                         drive_id: str, 
                         client_email: str,
                         message: Optional[str] = None) -> Dict:
        """
        Compartilha um arquivo com um cliente.
        
        Args:
            drive_id: ID do arquivo no Google Drive
            client_email: Email do cliente
            message: Mensagem personalizada para o email de notificação
            
        Returns:
            Dict: Informações da permissão criada
        """
        try:
            # Compartilhar com permissão de leitura
            permission = self.drive_service.share_file(
                drive_id,
                client_email,
                role='reader',
                send_notification=True,
                message=message or "Um documento foi compartilhado com você pelo escritório de advocacia."
            )
            
            return permission
        except Exception as e:
            logger.error(f"Erro ao compartilhar arquivo com cliente: {str(e)}")
            raise

# Funções de utilidade para uso em views
def get_drive_service_for_user(user):
    """
    Obtém um serviço do Drive para um usuário.
    
    Args:
        user: Usuário do Django
        
    Returns:
        Optional[DriveService]: Serviço do Drive ou None se não houver credenciais
    """
    auth_service = DriveAuthService()
    credentials = auth_service.get_credentials(user)
    
    if credentials:
        return DriveService(credentials)
    return None

def get_drive_sync_service_for_user(user):
    """
    Obtém um serviço de sincronização do Drive para um usuário.
    
    Args:
        user: Usuário do Django
        
    Returns:
        Optional[DriveSyncService]: Serviço de sincronização ou None se não houver credenciais
    """
    try:
        return DriveSyncService(user)
    except ValueError:
        return None

def start_drive_auth_flow(request, redirect_uri):
    """
    Inicia o fluxo de autenticação do Google Drive.
    
    Args:
        request: Objeto de requisição do Django
        redirect_uri: URI de redirecionamento após autenticação
        
    Returns:
        str: URL de autorização
    """
    auth_service = DriveAuthService()
    flow = auth_service.get_credentials_flow(redirect_uri)
    
    # Armazenar o estado do fluxo na sessão
    request.session['drive_auth_flow'] = {
        'state': flow.state
    }
    
    # Obter URL de autorização
    auth_url = auth_service.get_authorization_url(flow)
    return auth_url

def complete_drive_auth_flow(request, code, state):
    """
    Completa o fluxo de autenticação do Google Drive.
    
    Args:
        request: Objeto de requisição do Django
        code: Código de autorização
        state: Estado do fluxo
        
    Returns:
        bool: True se a autenticação foi bem-sucedida, False caso contrário
    """
    # Verificar estado
    if 'drive_auth_flow' not in request.session or request.session['drive_auth_flow'].get('state') != state:
        logger.error("Estado inválido no fluxo de autenticação do Drive")
        return False
    
    try:
        auth_service = DriveAuthService()
        flow = auth_service.get_credentials_flow(request.build_absolute_uri('/drive/auth/callback/'))
        flow.state = state
        
        # Trocar código por credenciais
        credentials = auth_service.exchange_code(flow, code)
        
        # Salvar credenciais
        auth_service.save_credentials(request.user, credentials)
        
        # Limpar estado da sessão
        del request.session['drive_auth_flow']
        
        return True
    except Exception as e:
        logger.error(f"Erro ao completar fluxo de autenticação do Drive: {str(e)}")
        return False

# Exemplo de uso
if __name__ == "__main__":
    # Este código seria executado em um ambiente Django
    pass
