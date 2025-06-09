"""
signature_service.py - Serviço de Assinatura Digital com Blockchain para prudentIA

Este módulo implementa o serviço de assinatura digital com integração blockchain,
permitindo a criação, gerenciamento e verificação de assinaturas digitais em documentos
com suporte a múltiplos signatários.
"""
import os
import hashlib
import json
import time
import uuid
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union, Any

import httpx
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr, validator
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from starlette.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from jose import jwt

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base para modelos SQLAlchemy
Base = declarative_base()

# Configurações
class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", "prudentia_signature_secret_key_change_in_production")
    BLOCKCHAIN_API_URL = os.getenv("BLOCKCHAIN_API_URL", "http://localhost:8545")
    BLOCKCHAIN_NETWORK = os.getenv("BLOCKCHAIN_NETWORK", "development")
    BLOCKCHAIN_CONTRACT_ADDRESS = os.getenv("BLOCKCHAIN_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
    BLOCKCHAIN_PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY", "0x0000000000000000000000000000000000000000")
    DOCUMENT_STORAGE_PATH = os.getenv("DOCUMENT_STORAGE_PATH", "/tmp/prudentia/documents")
    TOKEN_EXPIRY = int(os.getenv("TOKEN_EXPIRY", "86400"))  # 24 horas em segundos
    
    # Garantir que o diretório de armazenamento exista
    @classmethod
    def ensure_storage_path(cls):
        os.makedirs(cls.DOCUMENT_STORAGE_PATH, exist_ok=True)

settings = Settings()
settings.ensure_storage_path()

# Enums
class SignatureStatus(str, Enum):
    PENDING = "pending"
    SIGNED = "signed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"

class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REVOKED = "revoked"

# Modelos SQLAlchemy
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    status = Column(String(20), default=DocumentStatus.DRAFT.value)
    creator_id = Column(String(36), nullable=False)  # ID do usuário que criou o documento
    file_path = Column(String(255), nullable=False)  # Caminho para o arquivo no sistema
    file_hash = Column(String(64), nullable=False)  # Hash SHA-256 do arquivo original
    file_size = Column(Integer, nullable=False)  # Tamanho do arquivo em bytes
    file_type = Column(String(100), nullable=False)  # Tipo MIME do arquivo
    blockchain_tx = Column(String(66), nullable=True)  # Hash da transação blockchain
    blockchain_block = Column(Integer, nullable=True)  # Número do bloco na blockchain
    metadata = Column(JSON, nullable=True)  # Metadados adicionais
    
    # Relacionamentos
    signatures = relationship("Signature", back_populates="document", cascade="all, delete-orphan")

class Signature(Base):
    __tablename__ = "signatures"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    signer_id = Column(String(36), nullable=True)  # ID do usuário que assinou (null se pendente)
    signer_email = Column(String(255), nullable=False)  # Email do signatário
    signer_name = Column(String(255), nullable=False)  # Nome do signatário
    signer_role = Column(String(100), nullable=True)  # Cargo/função do signatário
    status = Column(String(20), default=SignatureStatus.PENDING.value)
    signature_token = Column(String(255), nullable=False)  # Token para assinatura
    signature_hash = Column(String(64), nullable=True)  # Hash da assinatura
    signature_date = Column(DateTime, nullable=True)  # Data da assinatura
    ip_address = Column(String(45), nullable=True)  # Endereço IP do signatário
    user_agent = Column(String(255), nullable=True)  # User-Agent do navegador
    blockchain_tx = Column(String(66), nullable=True)  # Hash da transação blockchain
    position_x = Column(Integer, nullable=True)  # Posição X da assinatura no documento
    position_y = Column(Integer, nullable=True)  # Posição Y da assinatura no documento
    page = Column(Integer, nullable=True)  # Página do documento onde a assinatura aparece
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    document = relationship("Document", back_populates="signatures")

# Modelos Pydantic para API
class SignatureBase(BaseModel):
    signer_email: EmailStr
    signer_name: str
    signer_role: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    page: Optional[int] = None

class SignatureCreate(SignatureBase):
    pass

class SignatureResponse(SignatureBase):
    id: str
    document_id: str
    status: SignatureStatus
    signature_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        orm_mode = True

class DocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    expires_at: Optional[datetime] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[datetime] = None

class DocumentResponse(DocumentBase):
    id: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    file_hash: str
    blockchain_tx: Optional[str] = None
    blockchain_block: Optional[int] = None
    signatures: List[SignatureResponse]
    
    class Config:
        orm_mode = True

class SignatureVerification(BaseModel):
    valid: bool
    document_hash: str
    blockchain_verified: bool
    signatures: List[Dict[str, Any]]
    document_id: str
    document_title: str
    created_at: datetime
    blockchain_tx: Optional[str] = None
    blockchain_block: Optional[int] = None

class BlockchainRegistration(BaseModel):
    document_hash: str
    timestamp: int
    signers: List[str]

# Classe para interação com blockchain
class BlockchainService:
    """Serviço para interação com a blockchain para registro e verificação de assinaturas."""
    
    def __init__(self):
        self.api_url = settings.BLOCKCHAIN_API_URL
        self.contract_address = settings.BLOCKCHAIN_CONTRACT_ADDRESS
        self.private_key = settings.BLOCKCHAIN_PRIVATE_KEY
        self.network = settings.BLOCKCHAIN_NETWORK
    
    async def register_document(self, document_hash: str, signers: List[str]) -> Dict[str, Any]:
        """
        Registra o hash de um documento na blockchain.
        
        Em produção, isso chamaria um smart contract em Ethereum ou Hyperledger.
        Para simplificar, simulamos o registro com um timestamp.
        """
        try:
            timestamp = int(time.time())
            
            # Em um ambiente de produção, aqui seria feita a chamada real à blockchain
            # Simulação de resposta para desenvolvimento
            tx_hash = f"0x{hashlib.sha256(f'{document_hash}:{timestamp}'.encode()).hexdigest()}"
            block_number = 1000000 + (timestamp % 1000)
            
            logger.info(f"Document hash {document_hash} registered on blockchain with tx {tx_hash}")
            
            return {
                "tx_hash": tx_hash,
                "block_number": block_number,
                "timestamp": timestamp,
                "status": "confirmed"
            }
        except Exception as e:
            logger.error(f"Error registering document on blockchain: {str(e)}")
            raise ValueError(f"Failed to register document on blockchain: {str(e)}")
    
    async def verify_document(self, document_hash: str, tx_hash: str) -> Dict[str, Any]:
        """
        Verifica se um hash de documento está registrado na blockchain.
        
        Em produção, isso consultaria o smart contract para verificar o registro.
        """
        try:
            # Em um ambiente de produção, aqui seria feita a consulta real à blockchain
            # Simulação de verificação para desenvolvimento
            # Em produção, verificaríamos o evento emitido pelo smart contract
            
            # Simulamos uma verificação bem-sucedida se o tx_hash começa com 0x
            is_valid = tx_hash.startswith("0x")
            
            return {
                "valid": is_valid,
                "document_hash": document_hash,
                "tx_hash": tx_hash,
                "timestamp": int(time.time()) - 3600,  # Simulamos que foi registrado há 1 hora
                "status": "confirmed" if is_valid else "not_found"
            }
        except Exception as e:
            logger.error(f"Error verifying document on blockchain: {str(e)}")
            return {
                "valid": False,
                "error": str(e),
                "status": "error"
            }

# Funções de utilidade
def calculate_file_hash(file_path: str) -> str:
    """Calcula o hash SHA-256 de um arquivo."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Lê o arquivo em chunks para lidar com arquivos grandes
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def generate_signature_token() -> str:
    """Gera um token único para assinatura."""
    return hashlib.sha256(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()

def create_signature_jwt(signature_id: str, document_id: str) -> str:
    """Cria um JWT para autenticação de assinatura."""
    expiry = datetime.utcnow() + timedelta(seconds=settings.TOKEN_EXPIRY)
    payload = {
        "sub": signature_id,
        "doc": document_id,
        "exp": expiry.timestamp()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def verify_signature_jwt(token: str) -> Dict[str, Any]:
    """Verifica e decodifica um JWT de assinatura."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired signature token: {str(e)}"
        )

# Classe principal do serviço de assinatura
class SignatureService:
    """
    Serviço principal para gerenciamento de assinaturas digitais com blockchain.
    
    Esta classe implementa a lógica de negócio para criação, gerenciamento e 
    verificação de assinaturas digitais em documentos.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.blockchain = BlockchainService()
    
    async def create_document(self, 
                             user_id: str, 
                             document_data: DocumentCreate, 
                             file: UploadFile) -> Document:
        """
        Cria um novo documento para assinatura.
        
        Args:
            user_id: ID do usuário criador
            document_data: Dados do documento
            file: Arquivo do documento (PDF)
            
        Returns:
            Document: Objeto do documento criado
        """
        # Validar tipo de arquivo (apenas PDF)
        if not file.content_type == "application/pdf":
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )
        
        # Gerar ID único para o documento
        doc_id = str(uuid.uuid4())
        
        # Criar diretório para o documento
        doc_dir = os.path.join(settings.DOCUMENT_STORAGE_PATH, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # Salvar o arquivo
        file_path = os.path.join(doc_dir, f"original_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Calcular hash do arquivo
        file_hash = calculate_file_hash(file_path)
        
        # Criar registro do documento
        document = Document(
            id=doc_id,
            title=document_data.title,
            description=document_data.description,
            expires_at=document_data.expires_at,
            creator_id=user_id,
            file_path=file_path,
            file_hash=file_hash,
            file_size=os.path.getsize(file_path),
            file_type=file.content_type,
            status=DocumentStatus.DRAFT.value
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        logger.info(f"Document created: {doc_id}")
        return document
    
    def add_signatories(self, 
                       document_id: str, 
                       signatories: List[SignatureCreate]) -> List[Signature]:
        """
        Adiciona signatários a um documento.
        
        Args:
            document_id: ID do documento
            signatories: Lista de dados dos signatários
            
        Returns:
            List[Signature]: Lista de objetos de assinatura criados
        """
        # Verificar se o documento existe
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Verificar se o documento está em estado válido para adicionar signatários
        if document.status not in [DocumentStatus.DRAFT.value, DocumentStatus.PENDING.value]:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Cannot add signatories to document with status {document.status}"
            )
        
        # Criar registros de assinatura para cada signatário
        signatures = []
        for sig_data in signatories:
            # Verificar se este email já está registrado como signatário
            existing = self.db.query(Signature).filter(
                Signature.document_id == document_id,
                Signature.signer_email == sig_data.signer_email
            ).first()
            
            if existing:
                continue  # Pular este signatário, já está registrado
            
            signature = Signature(
                document_id=document_id,
                signer_email=sig_data.signer_email,
                signer_name=sig_data.signer_name,
                signer_role=sig_data.signer_role,
                status=SignatureStatus.PENDING.value,
                signature_token=generate_signature_token(),
                position_x=sig_data.position_x,
                position_y=sig_data.position_y,
                page=sig_data.page
            )
            
            self.db.add(signature)
            signatures.append(signature)
        
        # Atualizar status do documento para pendente se houver signatários
        if signatures and document.status == DocumentStatus.DRAFT.value:
            document.status = DocumentStatus.PENDING.value
        
        self.db.commit()
        
        # Atualizar objetos com dados do banco
        for sig in signatures:
            self.db.refresh(sig)
        
        logger.info(f"Added {len(signatures)} signatories to document {document_id}")
        return signatures
    
    async def sign_document(self, 
                           signature_id: str, 
                           token: str, 
                           signer_id: Optional[str] = None,
                           ip_address: Optional[str] = None,
                           user_agent: Optional[str] = None) -> Signature:
        """
        Assina um documento.
        
        Args:
            signature_id: ID da assinatura
            token: Token de assinatura para validação
            signer_id: ID do usuário assinante (opcional)
            ip_address: Endereço IP do assinante
            user_agent: User-Agent do navegador do assinante
            
        Returns:
            Signature: Objeto de assinatura atualizado
        """
        # Buscar a assinatura
        signature = self.db.query(Signature).filter(Signature.id == signature_id).first()
        if not signature:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found"
            )
        
        # Verificar se o token é válido
        if signature.signature_token != token:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Invalid signature token"
            )
        
        # Verificar se a assinatura já foi realizada
        if signature.status != SignatureStatus.PENDING.value:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Signature already has status {signature.status}"
            )
        
        # Buscar o documento
        document = self.db.query(Document).filter(Document.id == signature.document_id).first()
        if not document:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Document {signature.document_id} not found"
            )
        
        # Verificar se o documento está em estado válido para assinatura
        if document.status != DocumentStatus.PENDING.value:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Cannot sign document with status {document.status}"
            )
        
        # Verificar se o documento não expirou
        if document.expires_at and document.expires_at < datetime.utcnow():
            signature.status = SignatureStatus.EXPIRED.value
            self.db.commit()
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Document has expired"
            )
        
        # Atualizar a assinatura
        signature.status = SignatureStatus.SIGNED.value
        signature.signer_id = signer_id
        signature.signature_date = datetime.utcnow()
        signature.ip_address = ip_address
        signature.user_agent = user_agent
        
        # Gerar hash da assinatura
        signature_data = f"{document.file_hash}:{signature.signer_email}:{signature.signature_date.isoformat()}"
        signature.signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        # Registrar na blockchain se for a última assinatura pendente
        pending_signatures = self.db.query(Signature).filter(
            Signature.document_id == document.id,
            Signature.status == SignatureStatus.PENDING.value
        ).count()
        
        if pending_signatures == 0:
            # Todas as assinaturas foram concluídas, registrar na blockchain
            signers = [
                sig.signer_email for sig in self.db.query(Signature).filter(
                    Signature.document_id == document.id,
                    Signature.status == SignatureStatus.SIGNED.value
                ).all()
            ]
            
            # Registrar na blockchain
            blockchain_result = await self.blockchain.register_document(document.file_hash, signers)
            
            # Atualizar documento com informações da blockchain
            document.blockchain_tx = blockchain_result["tx_hash"]
            document.blockchain_block = blockchain_result["block_number"]
            document.status = DocumentStatus.COMPLETED.value
        
        self.db.commit()
        self.db.refresh(signature)
        
        logger.info(f"Document {document.id} signed by {signature.signer_email}")
        return signature
    
    async def verify_document(self, document_id: str) -> SignatureVerification:
        """
        Verifica a autenticidade e integridade de um documento assinado.
        
        Args:
            document_id: ID do documento
            
        Returns:
            SignatureVerification: Resultado da verificação
        """
        # Buscar o documento
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Verificar se o documento foi finalizado
        if document.status != DocumentStatus.COMPLETED.value:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Document has status {document.status}, not completed"
            )
        
        # Calcular hash atual do arquivo
        current_hash = calculate_file_hash(document.file_path)
        
        # Verificar se o hash atual corresponde ao hash original
        hash_valid = current_hash == document.file_hash
        
        # Verificar registro na blockchain
        blockchain_verified = False
        if document.blockchain_tx:
            blockchain_result = await self.blockchain.verify_document(
                document.file_hash, document.blockchain_tx
            )
            blockchain_verified = blockchain_result["valid"]
        
        # Obter informações das assinaturas
        signatures = self.db.query(Signature).filter(
            Signature.document_id == document_id,
            Signature.status == SignatureStatus.SIGNED.value
        ).all()
        
        signature_info = []
        for sig in signatures:
            signature_info.append({
                "signer_name": sig.signer_name,
                "signer_email": sig.signer_email,
                "signer_role": sig.signer_role,
                "signature_date": sig.signature_date.isoformat() if sig.signature_date else None,
                "signature_hash": sig.signature_hash
            })
        
        return SignatureVerification(
            valid=hash_valid and blockchain_verified,
            document_hash=document.file_hash,
            blockchain_verified=blockchain_verified,
            signatures=signature_info,
            document_id=document.id,
            document_title=document.title,
            created_at=document.created_at,
            blockchain_tx=document.blockchain_tx,
            blockchain_block=document.blockchain_block
        )
    
    def get_document(self, document_id: str) -> Document:
        """
        Obtém um documento pelo ID.
        
        Args:
            document_id: ID do documento
            
        Returns:
            Document: Objeto do documento
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        return document
    
    def get_signature(self, signature_id: str) -> Signature:
        """
        Obtém uma assinatura pelo ID.
        
        Args:
            signature_id: ID da assinatura
            
        Returns:
            Signature: Objeto da assinatura
        """
        signature = self.db.query(Signature).filter(Signature.id == signature_id).first()
        if not signature:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found"
            )
        return signature
    
    def get_signature_url(self, signature_id: str) -> str:
        """
        Gera uma URL para assinatura.
        
        Args:
            signature_id: ID da assinatura
            
        Returns:
            str: URL para assinatura
        """
        signature = self.get_signature(signature_id)
        token = create_signature_jwt(signature_id, signature.document_id)
        return f"/api/v1/signatures/{signature_id}/sign?token={token}"
    
    def revoke_document(self, document_id: str, user_id: str) -> Document:
        """
        Revoga um documento.
        
        Args:
            document_id: ID do documento
            user_id: ID do usuário que está revogando
            
        Returns:
            Document: Objeto do documento atualizado
        """
        document = self.get_document(document_id)
        
        # Verificar se o usuário é o criador do documento
        if document.creator_id != user_id:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Only the document creator can revoke it"
            )
        
        # Verificar se o documento pode ser revogado
        if document.status not in [DocumentStatus.DRAFT.value, DocumentStatus.PENDING.value]:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Cannot revoke document with status {document.status}"
            )
        
        # Atualizar status do documento e das assinaturas pendentes
        document.status = DocumentStatus.REVOKED.value
        
        pending_signatures = self.db.query(Signature).filter(
            Signature.document_id == document_id,
            Signature.status == SignatureStatus.PENDING.value
        ).all()
        
        for signature in pending_signatures:
            signature.status = SignatureStatus.REVOKED.value
        
        self.db.commit()
        self.db.refresh(document)
        
        logger.info(f"Document {document_id} revoked by user {user_id}")
        return document

# API Endpoints
def create_signature_router(get_db_session):
    """
    Cria o router FastAPI para o serviço de assinatura.
    
    Args:
        get_db_session: Função para obter uma sessão de banco de dados
        
    Returns:
        APIRouter: Router FastAPI configurado
    """
    router = FastAPI(title="prudentIA - Serviço de Assinatura Digital")
    
    @router.post("/documents", response_model=DocumentResponse, status_code=HTTP_201_CREATED)
    async def create_document(
        background_tasks: BackgroundTasks,
        title: str = Form(...),
        description: str = Form(None),
        file: UploadFile = File(...),
        user_id: str = Depends(lambda: "current_user_id"),  # Substituir por autenticação real
        db: Session = Depends(get_db_session)
    ):
        """Cria um novo documento para assinatura."""
        service = SignatureService(db)
        
        document_data = DocumentCreate(
            title=title,
            description=description
        )
        
        document = await service.create_document(user_id, document_data, file)
        return document
    
    @router.post("/documents/{document_id}/signatories", response_model=List[SignatureResponse])
    def add_signatories(
        document_id: str,
        signatories: List[SignatureCreate],
        db: Session = Depends(get_db_session)
    ):
        """Adiciona signatários a um documento."""
        service = SignatureService(db)
        signatures = service.add_signatories(document_id, signatories)
        return signatures
    
    @router.post("/signatures/{signature_id}/sign", response_model=SignatureResponse)
    async def sign_document(
        signature_id: str,
        token: str = Query(...),
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        db: Session = Depends(get_db_session)
    ):
        """Assina um documento."""
        service = SignatureService(db)
        signature = await service.sign_document(
            signature_id, token, None, ip_address, user_agent
        )
        return signature
    
    @router.get("/documents/{document_id}/verify", response_model=SignatureVerification)
    async def verify_document(
        document_id: str,
        db: Session = Depends(get_db_session)
    ):
        """Verifica a autenticidade e integridade de um documento assinado."""
        service = SignatureService(db)
        verification = await service.verify_document(document_id)
        return verification
    
    @router.get("/documents/{document_id}", response_model=DocumentResponse)
    def get_document(
        document_id: str,
        db: Session = Depends(get_db_session)
    ):
        """Obtém informações de um documento."""
        service = SignatureService(db)
        document = service.get_document(document_id)
        return document
    
    @router.get("/signatures/{signature_id}")
    def get_signature_url(
        signature_id: str,
        db: Session = Depends(get_db_session)
    ):
        """Gera uma URL para assinatura."""
        service = SignatureService(db)
        url = service.get_signature_url(signature_id)
        return {"signature_url": url}
    
    @router.post("/documents/{document_id}/revoke", response_model=DocumentResponse)
    def revoke_document(
        document_id: str,
        user_id: str = Depends(lambda: "current_user_id"),  # Substituir por autenticação real
        db: Session = Depends(get_db_session)
    ):
        """Revoga um documento."""
        service = SignatureService(db)
        document = service.revoke_document(document_id, user_id)
        return document
    
    @router.get("/documents/{document_id}/download")
    def download_document(
        document_id: str,
        db: Session = Depends(get_db_session)
    ):
        """Faz download de um documento."""
        service = SignatureService(db)
        document = service.get_document(document_id)
        return FileResponse(
            document.file_path,
            media_type="application/pdf",
            filename=os.path.basename(document.file_path)
        )
    
    return router

# Exemplo de uso
if __name__ == "__main__":
    import uvicorn
    
    # Configuração de exemplo para teste local
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Criar banco de dados SQLite em memória para teste
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Criar e iniciar a API
    app = create_signature_router(get_db)
    uvicorn.run(app, host="127.0.0.1", port=8000)
