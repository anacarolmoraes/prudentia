"""
document_processing.py - Módulo de Processamento de Documentos para prudentIA

Este módulo implementa funcionalidades avançadas para processamento de documentos,
incluindo extração de dados de PDFs (como documentos de identificação, comprovantes),
preenchimento automático de modelos de documentos, e integração com formulários externos.

Funcionalidades:
- OCR para extração de texto de imagens e PDFs escaneados
- Extração de dados estruturados de documentos de identificação (RG, CPF, OAB, CNH, Comprovante de Residência)
- Preenchimento automático de modelos de documentos (contratos, procurações)
- Integração com Google Forms para coleta de dados
- Geração de documentos PDF a partir de templates
- Validação e normalização de dados extraídos
- Fluxo completo de onboarding de clientes (extração, geração, envio para assinatura)
"""

import os
import re
import io
import json
import base64
import logging
import tempfile
import datetime
import requests
from typing import Dict, List, Optional, Union, Any, Tuple, BinaryIO
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

# Bibliotecas para processamento de PDF
import fitz  # PyMuPDF
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter, PdfFileReader, PdfFileWriter

# Bibliotecas para processamento de imagens e OCR
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes

# Bibliotecas para processamento de texto e NLP
import spacy
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Bibliotecas para geração de documentos
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docxtpl import DocxTemplate
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Bibliotecas para integração com Google Forms
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar modelo spaCy para NLP
try:
    nlp = spacy.load("pt_core_news_lg")
except OSError:
    logger.warning("Modelo spaCy pt_core_news_lg não encontrado. Tentando baixar...")
    try:
        from spacy.cli import download
        download("pt_core_news_lg")
        nlp = spacy.load("pt_core_news_lg")
    except Exception as e:
        logger.error(f"Erro ao baixar modelo spaCy: {e}")
        nlp = None

# Configurar NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Configurações
class Config:
    """Configurações para o processamento de documentos."""
    
    # Configurações de OCR
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    TESSERACT_LANG = os.getenv("TESSERACT_LANG", "por")
    
    # Configurações de armazenamento
    TEMP_DIR = os.getenv("TEMP_DIR", tempfile.gettempdir())
    TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", "templates")
    
    # Configurações de Google Forms
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
    
    # Configurações de processamento
    DPI = 300
    IMAGE_QUALITY = 95
    
    # Padrões de expressões regulares para documentos brasileiros
    PATTERNS = {
        'cpf': r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}',
        'cnpj': r'\d{2}\.?\d{3}\.?\d{3}/?0001-\d{2}',
        'rg': r'(\d{1,2})\.?(\d{3})\.?(\d{3})-?(\d|X|x)',
        'oab': r'OAB[:/\s]*(\d{3,6})[:/\s]*([A-Z]{2})',
        'cep': r'\d{5}-?\d{3}',
        'data': r'(\d{2})[/.-](\d{2})[/.-](\d{4})',
        'telefone': r'(?:\+55\s?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[-.\s]?\d{4}',
        'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    }

# Configurar pytesseract
if os.path.exists(Config.TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_PATH

# Enums e tipos de dados
class DocumentType(Enum):
    """Tipos de documentos suportados para extração."""
    RG = "rg"
    CPF = "cpf"
    CNH = "cnh"
    COMPROVANTE_RESIDENCIA = "comprovante_residencia"
    OAB = "oab"
    CONTRATO = "contrato"
    PROCURACAO = "procuracao"
    OUTROS = "outros"

class DocumentField(Enum):
    """Campos comuns em documentos."""
    NOME = "nome"
    CPF = "cpf"
    RG = "rg"
    DATA_NASCIMENTO = "data_nascimento"
    ENDERECO = "endereco"
    CEP = "cep"
    CIDADE = "cidade"
    ESTADO = "estado"
    TELEFONE = "telefone"
    EMAIL = "email"
    NUMERO_OAB = "numero_oab"
    UF_OAB = "uf_oab"

@dataclass
class ExtractedData:
    """Classe para armazenar dados extraídos de documentos."""
    document_type: DocumentType
    fields: Dict[str, Any]
    confidence: float
    raw_text: str
    image_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte os dados extraídos para um dicionário."""
        return {
            "document_type": self.document_type.value,
            "fields": self.fields,
            "confidence": self.confidence,
            "raw_text": self.raw_text,
            "image_path": self.image_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractedData':
        """Cria um objeto ExtractedData a partir de um dicionário."""
        return cls(
            document_type=DocumentType(data["document_type"]),
            fields=data["fields"],
            confidence=data["confidence"],
            raw_text=data["raw_text"],
            image_path=data.get("image_path")
        )

# Classes de processamento de imagem e OCR
class ImageProcessor:
    """Classe para processamento de imagens antes do OCR."""
    
    @staticmethod
    def enhance_image(image: np.ndarray) -> np.ndarray:
        """
        Melhora a qualidade da imagem para OCR.
        
        Args:
            image: Imagem em formato numpy array
            
        Returns:
            np.ndarray: Imagem melhorada
        """
        # Converter para escala de cinza se for colorida
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Aplicar limiarização adaptativa
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Remover ruído
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return opening
    
    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """
        Corrige a inclinação da imagem.
        
        Args:
            image: Imagem em formato numpy array
            
        Returns:
            np.ndarray: Imagem corrigida
        """
        # Converter para escala de cinza se for colorida
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Detectar bordas
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detectar linhas
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        
        if lines is None or len(lines) == 0:
            return image
        
        # Calcular ângulo médio
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 == 0:
                continue
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            if -45 <= angle <= 45:
                angles.append(angle)
        
        if not angles:
            return image
        
        median_angle = np.median(angles)
        
        # Rotacionar imagem
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
        return rotated
    
    @staticmethod
    def remove_background(image: np.ndarray) -> np.ndarray:
        """
        Remove o fundo da imagem, mantendo apenas o texto.
        
        Args:
            image: Imagem em formato numpy array
            
        Returns:
            np.ndarray: Imagem com fundo removido
        """
        # Converter para escala de cinza se for colorida
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Aplicar blur para reduzir ruído
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Aplicar limiarização
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Criar máscara
        mask = np.zeros_like(thresh)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 100:  # Filtrar contornos pequenos
                cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # Aplicar máscara
        result = cv2.bitwise_and(gray, gray, mask=mask)
        
        return result
    
    @staticmethod
    def crop_to_content(image: np.ndarray) -> np.ndarray:
        """
        Corta a imagem para remover bordas em branco.
        
        Args:
            image: Imagem em formato numpy array
            
        Returns:
            np.ndarray: Imagem cortada
        """
        # Converter para escala de cinza se for colorida
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Inverter cores para facilitar a detecção de bordas
        gray = 255 - gray
        
        # Encontrar coordenadas de pixels não-zero
        coords = cv2.findNonZero(gray)
        
        if coords is None:
            return image
        
        # Encontrar o retângulo delimitador
        x, y, w, h = cv2.boundingRect(coords)
        
        # Adicionar uma margem
        margin = 10
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(image.shape[1] - x, w + 2 * margin)
        h = min(image.shape[0] - y, h + 2 * margin)
        
        # Cortar imagem
        if len(image.shape) == 3:
            return image[y:y+h, x:x+w]
        else:
            return image[y:y+h, x:x+w]

class OCRProcessor:
    """Classe para processamento de OCR em documentos."""
    
    @staticmethod
    def extract_text_from_image(image: Union[str, np.ndarray, Image.Image]) -> Tuple[str, Dict[str, Any]]:
        """
        Extrai texto de uma imagem usando OCR.
        
        Args:
            image: Caminho da imagem, array numpy ou objeto PIL.Image
            
        Returns:
            Tuple[str, Dict[str, Any]]: Texto extraído e dados do OCR
        """
        # Converter para array numpy se necessário
        if isinstance(image, str):
            img = cv2.imread(image)
        elif isinstance(image, Image.Image):
            img = np.array(image)
        else:
            img = image
        
        # Pré-processar imagem
        processed_img = ImageProcessor.enhance_image(img)
        processed_img = ImageProcessor.deskew(processed_img)
        
        # Converter para PIL Image
        pil_img = Image.fromarray(processed_img)
        
        # Extrair texto com OCR
        ocr_data = pytesseract.image_to_data(pil_img, lang=Config.TESSERACT_LANG, output_type=pytesseract.Output.DICT)
        
        # Extrair texto completo
        text = pytesseract.image_to_string(pil_img, lang=Config.TESSERACT_LANG)
        
        return text, ocr_data
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: Union[str, BinaryIO]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Extrai texto de um PDF usando OCR quando necessário.
        
        Args:
            pdf_path: Caminho do PDF ou objeto de arquivo
            
        Returns:
            List[Tuple[str, Dict[str, Any]]]: Lista de textos e dados OCR por página
        """
        results = []
        
        # Converter PDF para imagens
        try:
            if isinstance(pdf_path, str):
                images = convert_from_path(pdf_path, dpi=Config.DPI)
            else:
                pdf_path.seek(0)
                images = convert_from_bytes(pdf_path.read(), dpi=Config.DPI)
        except Exception as e:
            logger.error(f"Erro ao converter PDF para imagens: {e}")
            return []
        
        # Processar cada página
        for i, img in enumerate(images):
            # Converter para array numpy
            img_np = np.array(img)
            
            # Extrair texto com OCR
            text, ocr_data = OCRProcessor.extract_text_from_image(img_np)
            
            results.append((text, ocr_data))
        
        return results
    
    @staticmethod
    def extract_text_from_pdf_native(pdf_path: Union[str, BinaryIO]) -> List[str]:
        """
        Tenta extrair texto nativo de um PDF sem OCR.
        
        Args:
            pdf_path: Caminho do PDF ou objeto de arquivo
            
        Returns:
            List[str]: Lista de textos por página
        """
        try:
            if isinstance(pdf_path, str):
                pdf = fitz.open(pdf_path)
            else:
                pdf_path.seek(0)
                pdf = fitz.open(stream=pdf_path.read(), filetype="pdf")
            
            texts = []
            for page in pdf:
                texts.append(page.get_text())
            
            return texts
        except Exception as e:
            logger.error(f"Erro ao extrair texto nativo do PDF: {e}")
            return []
    
    @staticmethod
    def is_scanned_pdf(pdf_path: Union[str, BinaryIO]) -> bool:
        """
        Verifica se um PDF é escaneado (imagem) ou contém texto nativo.
        
        Args:
            pdf_path: Caminho do PDF ou objeto de arquivo
            
        Returns:
            bool: True se for escaneado, False se contiver texto nativo
        """
        try:
            # Extrair texto nativo
            texts = OCRProcessor.extract_text_from_pdf_native(pdf_path)
            
            # Verificar se há texto suficiente
            total_chars = sum(len(text.strip()) for text in texts)
            
            # Se tiver menos de 100 caracteres, provavelmente é escaneado
            if total_chars < 100:
                return True
            
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar se PDF é escaneado: {e}")
            return True  # Em caso de erro, assume que é escaneado

# Classes de extração de documentos específicos
class DocumentExtractor:
    """Classe base para extratores de documentos."""
    
    def __init__(self):
        """Inicializa o extrator de documentos."""
        pass
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")
    
    def extract_from_image(self, image_path: Union[str, np.ndarray]) -> ExtractedData:
        """
        Extrai dados de uma imagem.
        
        Args:
            image_path: Caminho da imagem ou array numpy
            
        Returns:
            ExtractedData: Dados extraídos
        """
        # Extrair texto com OCR
        text, ocr_data = OCRProcessor.extract_text_from_image(image_path)
        
        # Extrair dados do texto
        fields = self.extract_from_text(text)
        
        # Calcular confiança média
        if 'conf' in ocr_data and len(ocr_data['conf']) > 0:
            # Filtrar valores de confiança válidos (não -1)
            valid_conf = [conf for conf in ocr_data['conf'] if conf != -1]
            confidence = sum(valid_conf) / len(valid_conf) if valid_conf else 0
            confidence = confidence / 100.0  # Normalizar para 0-1
        else:
            confidence = 0.0
        
        return ExtractedData(
            document_type=self.get_document_type(),
            fields=fields,
            confidence=confidence,
            raw_text=text,
            image_path=image_path if isinstance(image_path, str) else None
        )
    
    def extract_from_pdf(self, pdf_path: Union[str, BinaryIO]) -> List[ExtractedData]:
        """
        Extrai dados de um PDF.
        
        Args:
            pdf_path: Caminho do PDF ou objeto de arquivo
            
        Returns:
            List[ExtractedData]: Lista de dados extraídos por página
        """
        results = []
        
        # Verificar se é um PDF escaneado
        is_scanned = OCRProcessor.is_scanned_pdf(pdf_path)
        
        if is_scanned:
            # Extrair texto com OCR
            page_texts = OCRProcessor.extract_text_from_pdf(pdf_path)
            
            for i, (text, ocr_data) in enumerate(page_texts):
                # Extrair dados do texto
                fields = self.extract_from_text(text)
                
                # Calcular confiança média
                if 'conf' in ocr_data and len(ocr_data['conf']) > 0:
                    valid_conf = [conf for conf in ocr_data['conf'] if conf != -1]
                    confidence = sum(valid_conf) / len(valid_conf) if valid_conf else 0
                    confidence = confidence / 100.0  # Normalizar para 0-1
                else:
                    confidence = 0.0
                
                results.append(ExtractedData(
                    document_type=self.get_document_type(),
                    fields=fields,
                    confidence=confidence,
                    raw_text=text,
                    image_path=None
                ))
        else:
            # Extrair texto nativo
            texts = OCRProcessor.extract_text_from_pdf_native(pdf_path)
            
            for i, text in enumerate(texts):
                # Extrair dados do texto
                fields = self.extract_from_text(text)
                
                results.append(ExtractedData(
                    document_type=self.get_document_type(),
                    fields=fields,
                    confidence=0.9,  # Alta confiança para texto nativo
                    raw_text=text,
                    image_path=None
                ))
        
        return results
    
    def get_document_type(self) -> DocumentType:
        """
        Retorna o tipo de documento que este extrator processa.
        
        Returns:
            DocumentType: Tipo de documento
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")

class RGExtractor(DocumentExtractor):
    """Extrator de dados de RG."""
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.RG
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto de RG.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        text = text.upper()
        
        fields = {}
        
        # Extrair número do RG
        rg_match = re.search(Config.PATTERNS['rg'], text)
        if rg_match:
            rg_number = rg_match.group(0)
            # Normalizar formato
            rg_number = re.sub(r'[^0-9X]', '', rg_number)
            fields[DocumentField.RG.value] = rg_number
        
        # Extrair nome
        nome_patterns = [
            r'NOME[:\s]+([A-ZÀ-Ú\s]+)',
            r'NOME DO PORTADOR[:\s]+([A-ZÀ-Ú\s]+)'
        ]
        
        for pattern in nome_patterns:
            nome_match = re.search(pattern, text)
            if nome_match:
                nome = nome_match.group(1).strip()
                fields[DocumentField.NOME.value] = nome
                break
        
        # Extrair data de nascimento
        data_patterns = [
            r'NASC[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'DATA DE NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})'
        ]
        
        for pattern in data_patterns:
            data_match = re.search(pattern, text)
            if data_match:
                data = data_match.group(1)
                # Normalizar formato
                data = re.sub(r'[/.-]', '/', data)
                fields[DocumentField.DATA_NASCIMENTO.value] = data
                break
        
        # Usar NLP para melhorar a extração
        if nlp:
            doc = nlp(text)
            
            # Extrair entidades nomeadas
            for ent in doc.ents:
                if ent.label_ == "PER" and DocumentField.NOME.value not in fields:
                    fields[DocumentField.NOME.value] = ent.text
                elif ent.label_ == "LOC" and DocumentField.CIDADE.value not in fields:
                    fields[DocumentField.CIDADE.value] = ent.text
        
        return fields

class CPFExtractor(DocumentExtractor):
    """Extrator de dados de CPF."""
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.CPF
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto de CPF.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        text = text.upper()
        
        fields = {}
        
        # Extrair número do CPF
        cpf_match = re.search(Config.PATTERNS['cpf'], text)
        if cpf_match:
            cpf_number = cpf_match.group(0)
            # Normalizar formato
            cpf_number = re.sub(r'[^0-9]', '', cpf_number)
            fields[DocumentField.CPF.value] = cpf_number
        
        # Extrair nome
        nome_patterns = [
            r'NOME[:\s]+([A-ZÀ-Ú\s]+)',
            r'NOME DO CONTRIBUINTE[:\s]+([A-ZÀ-Ú\s]+)'
        ]
        
        for pattern in nome_patterns:
            nome_match = re.search(pattern, text)
            if nome_match:
                nome = nome_match.group(1).strip()
                fields[DocumentField.NOME.value] = nome
                break
        
        # Extrair data de nascimento
        data_patterns = [
            r'NASC[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'DATA DE NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})'
        ]
        
        for pattern in data_patterns:
            data_match = re.search(pattern, text)
            if data_match:
                data = data_match.group(1)
                # Normalizar formato
                data = re.sub(r'[/.-]', '/', data)
                fields[DocumentField.DATA_NASCIMENTO.value] = data
                break
        
        return fields

class OABExtractor(DocumentExtractor):
    """Extrator de dados de carteira da OAB."""
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.OAB
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto de carteira da OAB.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        text = text.upper()
        
        fields = {}
        
        # Extrair número da OAB
        oab_match = re.search(Config.PATTERNS['oab'], text)
        if oab_match:
            numero_oab = oab_match.group(1)
            uf_oab = oab_match.group(2)
            fields[DocumentField.NUMERO_OAB.value] = numero_oab
            fields[DocumentField.UF_OAB.value] = uf_oab
        
        # Extrair nome
        nome_patterns = [
            r'NOME[:\s]+([A-ZÀ-Ú\s]+)',
            r'ADVOGADO[:\s]+([A-ZÀ-Ú\s]+)'
        ]
        
        for pattern in nome_patterns:
            nome_match = re.search(pattern, text)
            if nome_match:
                nome = nome_match.group(1).strip()
                fields[DocumentField.NOME.value] = nome
                break
        
        # Extrair data de nascimento
        data_patterns = [
            r'NASC[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'DATA DE NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})'
        ]
        
        for pattern in data_patterns:
            data_match = re.search(pattern, text)
            if data_match:
                data = data_match.group(1)
                # Normalizar formato
                data = re.sub(r'[/.-]', '/', data)
                fields[DocumentField.DATA_NASCIMENTO.value] = data
                break
        
        # Usar NLP para melhorar a extração
        if nlp:
            doc = nlp(text)
            
            # Extrair entidades nomeadas
            for ent in doc.ents:
                if ent.label_ == "PER" and DocumentField.NOME.value not in fields:
                    fields[DocumentField.NOME.value] = ent.text
        
        return fields

class ComprovanteResidenciaExtractor(DocumentExtractor):
    """Extrator de dados de comprovante de residência."""
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.COMPROVANTE_RESIDENCIA
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto de comprovante de residência.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        fields = {}
        
        # Extrair nome
        nome_patterns = [
            r'NOME[:\s]+([A-Za-zÀ-ÿ\s]+)',
            r'CLIENTE[:\s]+([A-Za-zÀ-ÿ\s]+)',
            r'CONSUMIDOR[:\s]+([A-Za-zÀ-ÿ\s]+)',
            r'TITULAR[:\s]+([A-Za-zÀ-ÿ\s]+)'
        ]
        
        for pattern in nome_patterns:
            nome_match = re.search(pattern, text, re.IGNORECASE)
            if nome_match:
                nome = nome_match.group(1).strip()
                fields[DocumentField.NOME.value] = nome
                break
        
        # Extrair endereço
        endereco_patterns = [
            r'ENDEREÇO[:\s]+([A-Za-zÀ-ÿ0-9\s,.°º-]+)',
            r'ENDEREÇO DE ENTREGA[:\s]+([A-Za-zÀ-ÿ0-9\s,.°º-]+)',
            r'LOCAL DE ENTREGA[:\s]+([A-Za-zÀ-ÿ0-9\s,.°º-]+)'
        ]
        
        for pattern in endereco_patterns:
            endereco_match = re.search(pattern, text, re.IGNORECASE)
            if endereco_match:
                endereco = endereco_match.group(1).strip()
                fields[DocumentField.ENDERECO.value] = endereco
                break
        
        # Extrair CEP
        cep_match = re.search(Config.PATTERNS['cep'], text)
        if cep_match:
            cep = cep_match.group(0)
            # Normalizar formato
            cep = re.sub(r'[^0-9]', '', cep)
            if len(cep) == 8:
                cep = f"{cep[:5]}-{cep[5:]}"
            fields[DocumentField.CEP.value] = cep
        
        # Usar NLP para melhorar a extração
        if nlp:
            doc = nlp(text)
            
            # Extrair entidades nomeadas
            for ent in doc.ents:
                if ent.label_ == "LOC" and DocumentField.CIDADE.value not in fields:
                    fields[DocumentField.CIDADE.value] = ent.text
        
        # Tentar extrair cidade e estado
        cidade_estado_pattern = r'([A-Za-zÀ-ÿ\s]+)[/-]([A-Z]{2})'
        cidade_estado_match = re.search(cidade_estado_pattern, text)
        if cidade_estado_match:
            cidade = cidade_estado_match.group(1).strip()
            estado = cidade_estado_match.group(2)
            fields[DocumentField.CIDADE.value] = cidade
            fields[DocumentField.ESTADO.value] = estado
        
        return fields

class CNHExtractor(DocumentExtractor):
    """Extrator de dados de CNH."""
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.CNH
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extrai dados de um texto de CNH.
        
        Args:
            text: Texto a ser processado
            
        Returns:
            Dict[str, Any]: Dados extraídos
        """
        text = text.upper()
        
        fields = {}
        
        # Extrair nome
        nome_patterns = [
            r'NOME[:\s]+([A-ZÀ-Ú\s]+)',
            r'NOME DO CONDUTOR[:\s]+([A-ZÀ-Ú\s]+)'
        ]
        
        for pattern in nome_patterns:
            nome_match = re.search(pattern, text)
            if nome_match:
                nome = nome_match.group(1).strip()
                fields[DocumentField.NOME.value] = nome
                break
        
        # Extrair CPF
        cpf_match = re.search(Config.PATTERNS['cpf'], text)
        if cpf_match:
            cpf_number = cpf_match.group(0)
            # Normalizar formato
            cpf_number = re.sub(r'[^0-9]', '', cpf_number)
            fields[DocumentField.CPF.value] = cpf_number
        
        # Extrair data de nascimento
        data_patterns = [
            r'NASC[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'DATA DE NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'NASCIMENTO[:\s]+(\d{2}[/.-]\d{2}[/.-]\d{4})'
        ]
        
        for pattern in data_patterns:
            data_match = re.search(pattern, text)
            if data_match:
                data = data_match.group(1)
                # Normalizar formato
                data = re.sub(r'[/.-]', '/', data)
                fields[DocumentField.DATA_NASCIMENTO.value] = data
                break
        
        # Extrair RG se presente
        rg_match = re.search(Config.PATTERNS['rg'], text)
        if rg_match:
            rg_number = rg_match.group(0)
            # Normalizar formato
            rg_number = re.sub(r'[^0-9X]', '', rg_number)
            fields[DocumentField.RG.value] = rg_number
        
        return fields

class DocumentClassifier:
    """Classe para classificar o tipo de documento."""
    
    @staticmethod
    def classify_document(text: str) -> DocumentType:
        """
        Classifica o tipo de documento com base no texto.
        
        Args:
            text: Texto do documento
            
        Returns:
            DocumentType: Tipo de documento
        """
        text = text.upper()
        
        # Verificar padrões específicos para cada tipo de documento
        if re.search(r'CARTEIRA\s+DE\s+IDENTIDADE|REGISTRO\s+GERAL|SECRETARIA\s+DE\s+SEGURANÇA', text):
            return DocumentType.RG
        
        if re.search(r'CARTEIRA\s+NACIONAL\s+DE\s+HABILITAÇÃO|PERMISSÃO\s+PARA\s+DIRIGIR|DETRAN', text):
            return DocumentType.CNH
        
        if re.search(r'CADASTRO\s+DE\s+PESSOAS\s+FÍSICAS|CPF|MINISTÉRIO\s+DA\s+FAZENDA', text):
            return DocumentType.CPF
        
        if re.search(r'ORDEM\s+DOS\s+ADVOGADOS\s+DO\s+BRASIL|OAB|IDENTIDADE\s+DE\s+ADVOGADO', text):
            return DocumentType.OAB
        
        if re.search(r'CONTA\s+DE\s+ENERGIA|CONTA\s+DE\s+ÁGUA|CONTA\s+DE\s+LUZ|COMPROVANTE\s+DE\s+RESIDÊNCIA|FATURA', text):
            return DocumentType.COMPROVANTE_RESIDENCIA
        
        if re.search(r'CONTRATO|ACORDO|TERMO\s+DE|CONVENÇÃO', text):
            return DocumentType.CONTRATO
        
        if re.search(r'PROCURAÇÃO|OUTORGA\s+DE\s+PODERES|OUTORGANTE|OUTORGADO', text):
            return DocumentType.PROCURACAO
        
        # Verificar padrões de dados específicos
        if re.search(Config.PATTERNS['oab'], text):
            return DocumentType.OAB
        
        if re.search(Config.PATTERNS['rg'], text):
            return DocumentType.RG
        
        if re.search(Config.PATTERNS['cpf'], text):
            return DocumentType.CPF
        
        # Se não conseguir classificar, retorna OUTROS
        return DocumentType.OUTROS
    
    @staticmethod
    def get_extractor_for_type(doc_type: DocumentType) -> DocumentExtractor:
        """
        Retorna o extrator apropriado para o tipo de documento.
        
        Args:
            doc_type: Tipo de documento
            
        Returns:
            DocumentExtractor: Extrator apropriado
        """
        extractors = {
            DocumentType.RG: RGExtractor(),
            DocumentType.CPF: CPFExtractor(),
            DocumentType.CNH: CNHExtractor(),
            DocumentType.OAB: OABExtractor(),
            DocumentType.COMPROVANTE_RESIDENCIA: ComprovanteResidenciaExtractor()
        }
        
        return extractors.get(doc_type, None)

# Classes para preenchimento de documentos
class DocumentTemplate:
    """Classe para gerenciar templates de documentos."""
    
    def __init__(self, template_path: Optional[str] = None):
        """
        Inicializa o gerenciador de templates.
        
        Args:
            template_path: Caminho para o arquivo de template (opcional)
        """
        self.template_path = template_path
    
    def render_docx(self, template_path: str, context: Dict[str, Any], output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Renderiza um template DOCX com os dados fornecidos.
        
        Args:
            template_path: Caminho para o template DOCX
            context: Dicionário com os dados para preenchimento
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        try:
            # Carregar o template
            doc = DocxTemplate(template_path)
            
            # Renderizar com o contexto
            doc.render(context)
            
            if output_path:
                # Salvar o documento resultante
                doc.save(output_path)
                return output_path
            else:
                # Retornar o documento como bytes
                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                    doc.save(tmp.name)
                    tmp.close()
                    with open(tmp.name, 'rb') as f:
                        content = f.read()
                    os.unlink(tmp.name)
                    return content
        except Exception as e:
            logger.error(f"Erro ao renderizar template DOCX: {e}")
            raise
    
    def render_pdf(self, template_path: str, context: Dict[str, Any], output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Renderiza um template PDF com os dados fornecidos.
        
        Args:
            template_path: Caminho para o template PDF
            context: Dicionário com os dados para preenchimento
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        try:
            # Criar um PDF temporário
            tmp_path = output_path or tempfile.mktemp(suffix='.pdf')
            
            # Criar o documento PDF
            doc = SimpleDocTemplate(tmp_path, pagesize=A4)
            
            # Criar estilos
            styles = getSampleStyleSheet()
            style_normal = styles['Normal']
            style_heading = styles['Heading1']
            
            # Criar elementos
            elements = []
            
            # Adicionar título
            if 'title' in context:
                elements.append(Paragraph(context['title'], style_heading))
                elements.append(Spacer(1, 12))
            
            # Adicionar conteúdo
            for key, value in context.items():
                if key != 'title' and key != 'signature_image':
                    elements.append(Paragraph(f"<b>{key}:</b> {value}", style_normal))
                    elements.append(Spacer(1, 6))
            
            # Adicionar imagem de assinatura, se presente
            if 'signature_image' in context and os.path.exists(context['signature_image']):
                elements.append(Spacer(1, 24))
                elements.append(Paragraph("Assinatura:", style_normal))
                elements.append(Spacer(1, 6))
                elements.append(Image(context['signature_image'], width=200, height=100))
            
            # Construir o documento
            doc.build(elements)
            
            if output_path:
                return output_path
            else:
                # Ler o conteúdo e excluir o arquivo temporário
                with open(tmp_path, 'rb') as f:
                    content = f.read()
                os.unlink(tmp_path)
                return content
        except Exception as e:
            logger.error(f"Erro ao renderizar template PDF: {e}")
            raise
    
    def fill_pdf_form(self, template_path: str, context: Dict[str, Any], output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Preenche um formulário PDF com os dados fornecidos.
        
        Args:
            template_path: Caminho para o template PDF
            context: Dicionário com os dados para preenchimento
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        try:
            # Abrir o template
            pdf = PdfReader(template_path)
            
            # Verificar se o PDF tem campos de formulário
            if '/AcroForm' not in pdf.trailer['/Root']:
                raise ValueError("O PDF não contém campos de formulário")
            
            # Criar um novo PDF para o resultado
            output = PdfWriter()
            
            # Copiar todas as páginas do template
            for i in range(len(pdf.pages)):
                output.add_page(pdf.pages[i])
            
            # Preencher os campos do formulário
            for field_name, field_value in context.items():
                try:
                    output.update_page_form_field_values(0, {field_name: field_value})
                except Exception as e:
                    logger.warning(f"Erro ao preencher campo '{field_name}': {e}")
            
            # Salvar o resultado
            if output_path:
                with open(output_path, 'wb') as f:
                    output.write(f)
                return output_path
            else:
                # Retornar o conteúdo em bytes
                with io.BytesIO() as output_buffer:
                    output.write(output_buffer)
                    return output_buffer.getvalue()
        except Exception as e:
            logger.error(f"Erro ao preencher formulário PDF: {e}")
            raise

class DocumentGenerator:
    """Classe para gerar documentos a partir de templates e dados."""
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Inicializa o gerador de documentos.
        
        Args:
            templates_dir: Diretório de templates (opcional)
        """
        self.templates_dir = templates_dir or Config.TEMPLATES_DIR
        self.template_manager = DocumentTemplate()
    
    def generate_document(self, 
                        template_name: str, 
                        context: Dict[str, Any], 
                        output_format: str = 'pdf',
                        output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Gera um documento a partir de um template e dados.
        
        Args:
            template_name: Nome do template
            context: Dicionário com os dados para preenchimento
            output_format: Formato de saída ('pdf' ou 'docx')
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        # Construir caminho do template
        template_path = os.path.join(self.templates_dir, template_name)
        
        # Verificar se o template existe
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template não encontrado: {template_path}")
        
        # Determinar o tipo de template
        if template_path.endswith('.docx'):
            # Renderizar template DOCX
            result = self.template_manager.render_docx(template_path, context, output_path)
            
            # Converter para PDF se necessário
            if output_format == 'pdf' and output_path:
                pdf_path = output_path if output_path.endswith('.pdf') else f"{os.path.splitext(output_path)[0]}.pdf"
                self._convert_docx_to_pdf(result, pdf_path)
                return pdf_path
            
            return result
        elif template_path.endswith('.pdf'):
            # Verificar se é um formulário PDF
            try:
                pdf = PdfReader(template_path)
                if '/AcroForm' in pdf.trailer['/Root']:
                    # Preencher formulário PDF
                    return self.template_manager.fill_pdf_form(template_path, context, output_path)
            except:
                pass
            
            # Renderizar template PDF
            return self.template_manager.render_pdf(template_path, context, output_path)
        else:
            raise ValueError(f"Formato de template não suportado: {os.path.splitext(template_path)[1]}")
    
    def generate_procuracao(self, 
                          outorgante_data: Dict[str, Any],
                          outorgado_data: Dict[str, Any],
                          poderes: List[str],
                          output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Gera uma procuração a partir dos dados fornecidos.
        
        Args:
            outorgante_data: Dados do outorgante
            outorgado_data: Dados do outorgado
            poderes: Lista de poderes concedidos
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        # Preparar contexto
        context = {
            'outorgante_nome': outorgante_data.get('nome', ''),
            'outorgante_nacionalidade': outorgante_data.get('nacionalidade', 'brasileiro(a)'),
            'outorgante_estado_civil': outorgante_data.get('estado_civil', ''),
            'outorgante_profissao': outorgante_data.get('profissao', ''),
            'outorgante_rg': outorgante_data.get('rg', ''),
            'outorgante_cpf': outorgante_data.get('cpf', ''),
            'outorgante_endereco': outorgante_data.get('endereco', ''),
            'outorgante_cidade': outorgante_data.get('cidade', ''),
            'outorgante_estado': outorgante_data.get('estado', ''),
            
            'outorgado_nome': outorgado_data.get('nome', ''),
            'outorgado_nacionalidade': outorgado_data.get('nacionalidade', 'brasileiro(a)'),
            'outorgado_estado_civil': outorgado_data.get('estado_civil', ''),
            'outorgado_profissao': outorgado_data.get('profissao', 'advogado(a)'),
            'outorgado_rg': outorgado_data.get('rg', ''),
            'outorgado_cpf': outorgado_data.get('cpf', ''),
            'outorgado_oab_numero': outorgado_data.get('numero_oab', ''),
            'outorgado_oab_uf': outorgado_data.get('uf_oab', ''),
            'outorgado_endereco': outorgado_data.get('endereco', ''),
            'outorgado_cidade': outorgado_data.get('cidade', ''),
            'outorgado_estado': outorgado_data.get('estado', ''),
            
            'poderes': ', '.join(poderes),
            'data_atual': datetime.datetime.now().strftime('%d/%m/%Y')
        }
        
        # Gerar documento
        return self.generate_document('procuracao.docx', context, 'pdf', output_path)
    
    def generate_contrato(self, 
                        cliente_data: Dict[str, Any],
                        advogado_data: Dict[str, Any],
                        servico_data: Dict[str, Any],
                        output_path: Optional[str] = None) -> Union[str, bytes]:
        """
        Gera um contrato de prestação de serviços advocatícios.
        
        Args:
            cliente_data: Dados do cliente
            advogado_data: Dados do advogado
            servico_data: Dados do serviço
            output_path: Caminho para salvar o arquivo resultante (opcional)
            
        Returns:
            Union[str, bytes]: Caminho do arquivo resultante ou conteúdo em bytes
        """
        # Preparar contexto
        context = {
            'cliente_nome': cliente_data.get('nome', ''),
            'cliente_nacionalidade': cliente_data.get('nacionalidade', 'brasileiro(a)'),
            'cliente_estado_civil': cliente_data.get('estado_civil', ''),
            'cliente_profissao': cliente_data.get('profissao', ''),
            'cliente_rg': cliente_data.get('rg', ''),
            'cliente_cpf': cliente_data.get('cpf', ''),
            'cliente_endereco': cliente_data.get('endereco', ''),
            'cliente_cidade': cliente_data.get('cidade', ''),
            'cliente_estado': cliente_data.get('estado', ''),
            
            'advogado_nome': advogado_data.get('nome', ''),
            'advogado_nacionalidade': advogado_data.get('nacionalidade', 'brasileiro(a)'),
            'advogado_estado_civil': advogado_data.get('estado_civil', ''),
            'advogado_oab_numero': advogado_data.get('numero_oab', ''),
            'advogado_oab_uf': advogado_data.get('uf_oab', ''),
            'advogado_cpf': advogado_data.get('cpf', ''),
            'advogado_endereco': advogado_data.get('endereco', ''),
            'advogado_cidade': advogado_data.get('cidade', ''),
            'advogado_estado': advogado_data.get('estado', ''),
            
            'servico_descricao': servico_data.get('descricao', ''),
            'servico_valor': servico_data.get('valor', ''),
            'servico_forma_pagamento': servico_data.get('forma_pagamento', ''),
            'servico_prazo': servico_data.get('prazo', ''),
            
            'data_atual': datetime.datetime.now().strftime('%d/%m/%Y')
        }
        
        # Gerar documento
        return self.generate_document('contrato_advocaticio.docx', context, 'pdf', output_path)
    
    def _convert_docx_to_pdf(self, docx_path: str, pdf_path: str) -> str:
        """
        Converte um documento DOCX para PDF.
        
        Args:
            docx_path: Caminho do documento DOCX
            pdf_path: Caminho para salvar o PDF resultante
            
        Returns:
            str: Caminho do PDF resultante
        """
        try:
            # Verificar se o LibreOffice está disponível
            import subprocess
            
            # Tentar converter usando LibreOffice
            try:
                subprocess.run([
                    'libreoffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', os.path.dirname(pdf_path),
                    docx_path
                ], check=True)
                
                # Renomear o arquivo se necessário
                base_name = os.path.splitext(os.path.basename(docx_path))[0]
                generated_pdf = os.path.join(os.path.dirname(pdf_path), f"{base_name}.pdf")
                
                if generated_pdf != pdf_path and os.path.exists(generated_pdf):
                    os.rename(generated_pdf, pdf_path)
                
                return pdf_path
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("LibreOffice não disponível para conversão. Tentando alternativa...")
            
            # Alternativa: usar python-docx2pdf
            try:
                from docx2pdf import convert
                convert(docx_path, pdf_path)
                return pdf_path
            except ImportError:
                logger.warning("python-docx2pdf não disponível. Tentando outra alternativa...")
            
            # Alternativa: usar comtypes (Windows apenas)
            if os.name == 'nt':
                try:
                    import comtypes.client
                    
                    word = comtypes.client.CreateObject('Word.Application')
                    word.Visible = False
                    
                    doc = word.Documents.Open(docx_path)
                    doc.SaveAs(pdf_path, FileFormat=17)  # 17 = PDF
                    doc.Close()
                    word.Quit()
                    
                    return pdf_path
                except ImportError:
                    logger.warning("comtypes não disponível.")
            
            # Se todas as tentativas falharem, retornar o caminho do DOCX
            logger.error("Não foi possível converter DOCX para PDF. Retornando documento DOCX.")
            return docx_path
        except Exception as e:
            logger.error(f"Erro ao converter DOCX para PDF: {e}")
            return docx_path

# Classes para integração com formulários externos
class FormIntegration:
    """Classe base para integração com formulários externos."""
    
    def get_form_data(self, form_id: str) -> List[Dict[str, Any]]:
        """
        Obtém dados de um formulário externo.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            List[Dict[str, Any]]: Lista de respostas do formulário
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")
    
    def create_form(self, title: str, fields: List[Dict[str, Any]]) -> str:
        """
        Cria um novo formulário.
        
        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            
        Returns:
            str: ID do formulário criado
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")
    
    def get_form_url(self, form_id: str) -> str:
        """
        Obtém a URL de um formulário.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            str: URL do formulário
        """
        raise NotImplementedError("Método deve ser implementado pelas subclasses")

class GoogleFormIntegration(FormIntegration):
    """Integração com Google Forms."""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Inicializa a integração com Google Forms.
        
        Args:
            credentials_path: Caminho para o arquivo de credenciais (opcional)
        """
        self.credentials_path = credentials_path or Config.GOOGLE_CREDENTIALS_FILE
        self.credentials = None
        self.forms_service = None
        self.sheets_service = None
        
        # Inicializar serviços
        self._init_services()
    
    def _init_services(self):
        """Inicializa os serviços do Google."""
        try:
            # Carregar credenciais
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/forms',
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            
            # Criar serviço do Forms
            self.forms_service = build('forms', 'v1', credentials=self.credentials)
            
            # Criar serviço do Sheets
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao inicializar serviços do Google: {e}")
            raise
    
    def create_form(self, title: str, fields: List[Dict[str, Any]]) -> str:
        """
        Cria um novo formulário do Google.
        
        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            
        Returns:
            str: ID do formulário criado
        """
        try:
            # Criar formulário
            form = {
                'info': {
                    'title': title,
                    'documentTitle': title
                }
            }
            
            result = self.forms_service.forms().create(body=form).execute()
            form_id = result['formId']
            
            # Adicionar campos
            items = []
            for field in fields:
                field_type = field.get('type', 'text')
                
                if field_type == 'text':
                    item = {
                        'title': field.get('title', ''),
                        'textQuestion': {
                            'paragraph': field.get('multiline', False)
                        }
                    }
                elif field_type == 'choice':
                    item = {
                        'title': field.get('title', ''),
                        'choiceQuestion': {
                            'type': 'RADIO',
                            'options': [{'value': option} for option in field.get('options', [])]
                        }
                    }
                elif field_type == 'checkbox':
                    item = {
                        'title': field.get('title', ''),
                        'choiceQuestion': {
                            'type': 'CHECKBOX',
                            'options': [{'value': option} for option in field.get('options', [])]
                        }
                    }
                elif field_type == 'date':
                    item = {
                        'title': field.get('title', ''),
                        'dateQuestion': {}
                    }
                else:
                    continue
                
                if field.get('required', False):
                    item['required'] = True
                
                items.append({'item': item})
            
            # Atualizar formulário com os campos
            update = {
                'requests': [{'createItem': item} for item in items]
            }
            
            self.forms_service.forms().batchUpdate(formId=form_id, body=update).execute()
            
            return form_id
        except Exception as e:
            logger.error(f"Erro ao criar formulário: {e}")
            raise
    
    def get_form_url(self, form_id: str) -> str:
        """
        Obtém a URL de um formulário do Google.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            str: URL do formulário
        """
        return f"https://docs.google.com/forms/d/{form_id}/viewform"
    
    def get_form_data(self, form_id: str) -> List[Dict[str, Any]]:
        """
        Obtém dados de um formulário do Google.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            List[Dict[str, Any]]: Lista de respostas do formulário
        """
        try:
            # Obter formulário
            form = self.forms_service.forms().get(formId=form_id).execute()
            
            # Obter respostas
            response = self.forms_service.forms().responses().list(formId=form_id).execute()
            
            # Processar respostas
            results = []
            for resp in response.get('responses', []):
                answers = resp.get('answers', {})
                result = {}
                
                for question_id, answer in answers.items():
                    # Encontrar a pergunta correspondente
                    question_title = None
                    for item in form.get('items', []):
                        if item.get('itemId') == question_id:
                            question_title = item.get('title', question_id)
                            break
                    
                    # Extrair resposta
                    if 'textAnswers' in answer:
                        result[question_title] = answer['textAnswers']['answers'][0]['value']
                    elif 'choiceAnswers' in answer:
                        result[question_title] = [choice['value'] for choice in answer['choiceAnswers']['answers']]
                    elif 'dateAnswers' in answer:
                        result[question_title] = answer['dateAnswers']['answers'][0]['value']
                
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Erro ao obter dados do formulário: {e}")
            raise
    
    def get_form_responses_sheet(self, form_id: str) -> str:
        """
        Obtém o ID da planilha associada a um formulário do Google.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            str: ID da planilha
        """
        try:
            # Obter formulário
            form = self.forms_service.forms().get(formId=form_id).execute()
            
            # Verificar se há uma planilha associada
            if 'linkedSheetId' in form:
                return form['linkedSheetId']
            
            # Criar uma nova planilha para as respostas
            drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # Criar planilha
            sheet_metadata = {
                'properties': {
                    'title': f"Respostas - {form.get('info', {}).get('title', 'Formulário')}"
                }
            }
            
            sheet = self.sheets_service.spreadsheets().create(body=sheet_metadata).execute()
            sheet_id = sheet['spreadsheetId']
            
            # Vincular planilha ao formulário
            update = {
                'requests': [{
                    'updateFormInfo': {
                        'info': {
                            'linkedSheetId': sheet_id
                        },
                        'updateMask': 'linkedSheetId'
                    }
                }]
            }
            
            self.forms_service.forms().batchUpdate(formId=form_id, body=update).execute()
            
            return sheet_id
        except Exception as e:
            logger.error(f"Erro ao obter planilha de respostas: {e}")
            raise

class CustomFormIntegration(FormIntegration):
    """Integração com formulários personalizados do prudentIA."""
    
    def __init__(self, api_base_url: Optional[str] = None):
        """
        Inicializa a integração com formulários personalizados.
        
        Args:
            api_base_url: URL base da API de formulários (opcional)
        """
        self.api_base_url = api_base_url or "https://api.prudentia.com.br/forms"
    
    def create_form(self, title: str, fields: List[Dict[str, Any]]) -> str:
        """
        Cria um novo formulário personalizado.
        
        Args:
            title: Título do formulário
            fields: Lista de campos do formulário
            
        Returns:
            str: ID do formulário criado
        """
        try:
            # Preparar dados do formulário
            form_data = {
                'title': title,
                'fields': fields
            }
            
            # Enviar requisição para a API
            response = requests.post(f"{self.api_base_url}/create", json=form_data)
            response.raise_for_status()
            
            result = response.json()
            return result['form_id']
        except Exception as e:
            logger.error(f"Erro ao criar formulário personalizado: {e}")
            raise
    
    def get_form_url(self, form_id: str) -> str:
        """
        Obtém a URL de um formulário personalizado.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            str: URL do formulário
        """
        return f"{self.api_base_url}/view/{form_id}"
    
    def get_form_data(self, form_id: str) -> List[Dict[str, Any]]:
        """
        Obtém dados de um formulário personalizado.
        
        Args:
            form_id: ID do formulário
            
        Returns:
            List[Dict[str, Any]]: Lista de respostas do formulário
        """
        try:
            # Enviar requisição para a API
            response = requests.get(f"{self.api_base_url}/responses/{form_id}")
            response.raise_for_status()
            
            result = response.json()
            return result['responses']
        except Exception as e:
            logger.error(f"Erro ao obter dados do formulário personalizado: {e}")
            raise

# Classe principal para processamento de documentos
class DocumentProcessor:
    """Classe principal para processamento de documentos."""
    
    def __init__(self):
        """Inicializa o processador de documentos."""
        self.extractors = {
            DocumentType.RG: RGExtractor(),
            DocumentType.CPF: CPFExtractor(),
            DocumentType.CNH: CNHExtractor(),
            DocumentType.OAB: OABExtractor(),
            DocumentType.COMPROVANTE_RESIDENCIA: ComprovanteResidenciaExtractor()
        }
        
        self.document_generator = DocumentGenerator()
        
        # Integração com formulários
        try:
            self.google_form_integration = GoogleFormIntegration()
        except Exception as e:
            logger.warning(f"Não foi possível inicializar integração com Google Forms: {e}")
            self.google_form_integration = None
        
        self.custom_form_integration = CustomFormIntegration()
    
    def process_document(self, 
                       document_path: Union[str, BinaryIO],
                       document_type: Optional[DocumentType] = None) -> Union[ExtractedData, List[ExtractedData]]:
        """
        Processa um documento para extrair dados.
        
        Args:
            document_path: Caminho do documento ou objeto de arquivo
            document_type: Tipo de documento (opcional, será detectado automaticamente se não fornecido)
            
        Returns:
            Union[ExtractedData, List[ExtractedData]]: Dados extraídos
        """
        # Verificar extensão do arquivo
        if isinstance(document_path, str):
            ext = os.path.splitext(document_path)[1].lower()
        else:
            # Tentar obter o nome do arquivo do objeto de arquivo
            if hasattr(document_path, 'name'):
                ext = os.path.splitext(document_path.name)[1].lower()
            else:
                # Assumir PDF se não for possível determinar
                ext = '.pdf'
        
        # Processar de acordo com o tipo de arquivo
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            # Processar imagem
            return self._process_image(document_path, document_type)
        elif ext == '.pdf':
            # Processar PDF
            return self._process_pdf(document_path, document_type)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {ext}")
    
    def _process_image(self, 
                     image_path: Union[str, np.ndarray],
                     document_type: Optional[DocumentType] = None) -> ExtractedData:
        """
        Processa uma imagem para extrair dados.
        
        Args:
            image_path: Caminho da imagem ou array numpy
            document_type: Tipo de documento (opcional)
            
        Returns:
            ExtractedData: Dados extraídos
        """
        # Extrair texto com OCR
        text, _ = OCRProcessor.extract_text_from_image(image_path)
        
        # Detectar tipo de documento se não fornecido
        if document_type is None:
            document_type = DocumentClassifier.classify_document(text)
        
        # Obter extrator apropriado
        extractor = self.extractors.get(document_type)
        if extractor is None:
            raise ValueError(f"Tipo de documento não suportado: {document_type}")
        
        # Extrair dados
        return extractor.extract_from_image(image_path)
    
    def _process_pdf(self, 
                   pdf_path: Union[str, BinaryIO],
                   document_type: Optional[DocumentType] = None) -> List[ExtractedData]:
        """
        Processa um PDF para extrair dados.
        
        Args:
            pdf_path: Caminho do PDF ou objeto de arquivo
            document_type: Tipo de documento (opcional)
            
        Returns:
            List[ExtractedData]: Lista de dados extraídos por página
        """
        # Verificar se é um PDF escaneado
        is_scanned = OCRProcessor.is_scanned_pdf(pdf_path)
        
        # Extrair texto
        if is_scanned:
            # Extrair texto com OCR
            page_texts = OCRProcessor.extract_text_from_pdf(pdf_path)
            texts = [text for text, _ in page_texts]
        else:
            # Extrair texto nativo
            texts = OCRProcessor.extract_text_from_pdf_native(pdf_path)
        
        # Detectar tipo de documento se não fornecido
        if document_type is None:
            # Concatenar textos de todas as páginas para melhor detecção
            all_text = "\n".join(texts)
            document_type = DocumentClassifier.classify_document(all_text)
        
        # Obter extrator apropriado
        extractor = self.extractors.get(document_type)
        if extractor is None:
            raise ValueError(f"Tipo de documento não suportado: {document_type}")
        
        # Extrair dados
        return extractor.extract_from_pdf(pdf_path)
    
    def create_client_form(self, 
                         title: str = "Cadastro de Cliente",
                         use_google_forms: bool = False,
                         additional_fields: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Cria um formulário para cadastro de cliente.
        
        Args:
            title: Título do formulário
            use_google_forms: Se True, usa Google Forms; se False, usa formulário personalizado
            additional_fields: Campos adicionais para o formulário
            
        Returns:
            Dict[str, Any]: Informações do formulário criado
        """
        # Definir campos do formulário
        fields = [
            {
                'title': 'Nome Completo',
                'type': 'text',
                'required': True
            },
            {
                'title': 'CPF',
                'type': 'text',
                'required': True
            },
            {
                'title': 'RG',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Data de Nascimento',
                'type': 'date',
                'required': True
            },
            {
                'title': 'Estado Civil',
                'type': 'choice',
                'options': ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viúvo(a)', 'União Estável'],
                'required': True
            },
            {
                'title': 'Profissão',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Endereço Completo',
                'type': 'text',
                'multiline': True,
                'required': True
            },
            {
                'title': 'CEP',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Cidade',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Estado',
                'type': 'choice',
                'options': ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'],
                'required': True
            },
            {
                'title': 'Telefone',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Email',
                'type': 'text',
                'required': True
            }
        ]
        
        # Adicionar campos adicionais se fornecidos
        if additional_fields:
            fields.extend(additional_fields)
        
        try:
            # Criar formulário usando a integração apropriada
            if use_google_forms and self.google_form_integration:
                form_id = self.google_form_integration.create_form(title, fields)
                form_url = self.google_form_integration.get_form_url(form_id)
                
                return {
                    'form_id': form_id,
                    'form_url': form_url,
                    'type': 'google_forms'
                }
            else:
                form_id = self.custom_form_integration.create_form(title, fields)
                form_url = self.custom_form_integration.get_form_url(form_id)
                
                return {
                    'form_id': form_id,
                    'form_url': form_url,
                    'type': 'custom_form'
                }
        except Exception as e:
            logger.error(f"Erro ao criar formulário de cliente: {e}")
            raise
    
    def create_case_form(self,
                        title: str = "Cadastro de Caso",
                        client_id: Optional[str] = None,
                        use_google_forms: bool = False) -> Dict[str, Any]:
        """
        Cria um formulário para cadastro de caso/processo.
        
        Args:
            title: Título do formulário
            client_id: ID do cliente (opcional)
            use_google_forms: Se True, usa Google Forms; se False, usa formulário personalizado
            
        Returns:
            Dict[str, Any]: Informações do formulário criado
        """
        # Definir campos do formulário
        fields = [
            {
                'title': 'Tipo de Caso',
                'type': 'choice',
                'options': [
                    'Cível', 'Trabalhista', 'Criminal', 'Família', 
                    'Tributário', 'Previdenciário', 'Administrativo', 'Outro'
                ],
                'required': True
            },
            {
                'title': 'Descrição do Caso',
                'type': 'text',
                'multiline': True,
                'required': True
            },
            {
                'title': 'Número do Processo (se já existir)',
                'type': 'text',
                'required': False
            },
            {
                'title': 'Vara/Tribunal',
                'type': 'text',
                'required': False
            },
            {
                'title': 'Parte Contrária',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Valor da Causa',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Honorários Combinados',
                'type': 'text',
                'required': True
            },
            {
                'title': 'Observações Adicionais',
                'type': 'text',
                'multiline': True,
                'required': False
            }
        ]
        
        # Se o cliente já estiver definido, adicionar campo oculto
        if client_id:
            fields.append({
                'title': 'ID do Cliente',
                'type': 'text',
                'required': True,
                'hidden': True,
                'default_value': client_id
            })
        
        try:
            # Criar formulário usando a integração apropriada
            if use_google_forms and self.google_form_integration:
                form_id = self.google_form_integration.create_form(title, fields)
                form_url = self.google_form_integration.get_form_url(form_id)
                
                return {
                    'form_id': form_id,
                    'form_url': form_url,
                    'type': 'google_forms'
                }
            else:
                form_id = self.custom_form_integration.create_form(title, fields)
                form_url = self.custom_form_integration.get_form_url(form_id)
                
                return {
                    'form_id': form_id,
                    'form_url': form_url,
                    'type': 'custom_form'
                }
        except Exception as e:
            logger.error(f"Erro ao criar formulário de caso: {e}")
            raise
    
    def process_form_data(self, 
                         form_id: str, 
                         form_type: str = 'custom_form') -> List[Dict[str, Any]]:
        """
        Processa dados de um formulário preenchido.
        
        Args:
            form_id: ID do formulário
            form_type: Tipo do formulário ('google_forms' ou 'custom_form')
            
        Returns:
            List[Dict[str, Any]]: Lista de respostas processadas
        """
        try:
            # Obter dados do formulário
            if form_type == 'google_forms' and self.google_form_integration:
                form_data = self.google_form_integration.get_form_data(form_id)
            else:
                form_data = self.custom_form_integration.get_form_data(form_id)
            
            # Processar e validar dados
            processed_data = []
            for response in form_data:
                processed_response = self._validate_form_data(response)
                processed_data.append(processed_response)
            
            return processed_data
        except Exception as e:
            logger.error(f"Erro ao processar dados do formulário: {e}")
            raise
    
    def _validate_form_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida e normaliza dados de formulário.
        
        Args:
            form_data: Dados do formulário
            
        Returns:
            Dict[str, Any]: Dados validados e normalizados
        """
        validated_data = {}
        
        # Processar cada campo
        for field, value in form_data.items():
            # Normalizar campos comuns
            if 'CPF' in field:
                # Remover caracteres não numéricos
                normalized_value = re.sub(r'\D', '', value)
                if len(normalized_value) == 11:
                    # Formatar como XXX.XXX.XXX-XX
                    validated_data['cpf'] = f"{normalized_value[:3]}.{normalized_value[3:6]}.{normalized_value[6:9]}-{normalized_value[9:]}"
                else:
                    validated_data['cpf'] = value
            
            elif 'RG' in field:
                # Remover caracteres não alfanuméricos
                normalized_value = re.sub(r'[^0-9Xx]', '', value)
                validated_data['rg'] = normalized_value
            
            elif 'Nome' in field:
                # Capitalizar nome
                validated_data['nome'] = value.title()
            
            elif 'Data de Nascimento' in field:
                # Normalizar formato de data
                if isinstance(value, dict) and 'year' in value:
                    # Formato do Google Forms
                    validated_data['data_nascimento'] = f"{value['day']:02d}/{value['month']:02d}/{value['year']}"
                else:
                    # Tentar converter para formato padrão
                    match = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', value)
                    if match:
                        dia, mes, ano = match.groups()
                        validated_data['data_nascimento'] = f"{int(dia):02d}/{int(mes):02d}/{ano}"
                    else:
                        validated_data['data_nascimento'] = value
            
            elif 'CEP' in field:
                # Normalizar CEP
                normalized_value = re.sub(r'\D', '', value)
                if len(normalized_value) == 8:
                    validated_data['cep'] = f"{normalized_value[:5]}-{normalized_value[5:]}"
                else:
                    validated_data['cep'] = value
            
            elif 'Telefone' in field:
                # Normalizar telefone
                normalized_value = re.sub(r'\D', '', value)
                if len(normalized_value) == 11:  # Celular com DDD
                    validated_data['telefone'] = f"({normalized_value[:2]}) {normalized_value[2:7]}-{normalized_value[7:]}"
                elif len(normalized_value) == 10:  # Fixo com DDD
                    validated_data['telefone'] = f"({normalized_value[:2]}) {normalized_value[2:6]}-{normalized_value[6:]}"
                else:
                    validated_data['telefone'] = value
            
            elif 'Email' in field:
                # Normalizar email
                validated_data['email'] = value.lower()
            
            elif 'Endereço' in field:
                validated_data['endereco'] = value
            
            elif 'Cidade' in field:
                validated_data['cidade'] = value.title()
            
            elif 'Estado' in field:
                validated_data['estado'] = value.upper()
            
            elif 'Estado Civil' in field:
                validated_data['estado_civil'] = value
            
            elif 'Profissão' in field:
                validated_data['profissao'] = value.title()
            
            else:
                # Campos não reconhecidos são armazenados com a chave original
                normalized_key = field.lower().replace(' ', '_')
                validated_data[normalized_key] = value
        
        return validated_data
    
    def extract_client_data_from_documents(self, 
                                         documents: List[Union[str, BinaryIO]]) -> Dict[str, Any]:
        """
        Extrai dados de cliente a partir de múltiplos documentos.
        
        Args:
            documents: Lista de caminhos ou objetos de arquivo de documentos
            
        Returns:
            Dict[str, Any]: Dados consolidados do cliente
        """
        client_data = {}
        
        for document in documents:
            try:
                # Processar documento
                extracted_data = self.process_document(document)
                
                # Se for uma lista (PDF com múltiplas páginas), usar o primeiro item
                if isinstance(extracted_data, list):
                    if not extracted_data:
                        continue
                    extracted_data = extracted_data[0]
                
                # Mesclar dados extraídos
                for field, value in extracted_data.fields.items():
                    # Só adicionar se o campo ainda não existir ou se a confiança for maior
                    if field not in client_data or extracted_data.confidence > client_data.get('_confidence', {}).get(field, 0):
                        client_data[field] = value
                        if '_confidence' not in client_data:
                            client_data['_confidence'] = {}
                        client_data['_confidence'][field] = extracted_data.confidence
                
                # Registrar tipo de documento processado
                if '_document_types' not in client_data:
                    client_data['_document_types'] = []
                client_data['_document_types'].append(extracted_data.document_type.value)
                
            except Exception as e:
                logger.error(f"Erro ao processar documento: {e}")
                continue
        
        # Remover metadados de confiança antes de retornar
        if '_confidence' in client_data:
            del client_data['_confidence']
        
        return client_data
    
    def generate_documents_from_client_data(self, 
                                          client_data: Dict[str, Any],
                                          document_types: List[str],
                                          output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Gera documentos a partir dos dados do cliente.
        
        Args:
            client_data: Dados do cliente
            document_types: Lista de tipos de documentos a gerar ('procuracao', 'contrato', etc.)
            output_dir: Diretório para salvar os documentos (opcional)
            
        Returns:
            Dict[str, str]: Mapeamento de tipos de documentos para caminhos de arquivo
        """
        generated_documents = {}
        
        # Criar diretório de saída se não existir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Gerar cada tipo de documento solicitado
        for doc_type in document_types:
            try:
                if doc_type == 'procuracao':
                    # Dados do advogado (usuário do sistema)
                    # Em um ambiente real, estes dados viriam do usuário logado
                    advogado_data = {
                        'nome': 'Nome do Advogado',
                        'numero_oab': '123456',
                        'uf_oab': 'SP',
                        'cpf': '123.456.789-00',
                        'endereco': 'Endereço do Advogado',
                        'cidade': 'Cidade do Advogado',
                        'estado': 'SP'
                    }
                    
                    # Poderes padrão
                    poderes = [
                        "representar o(a) outorgante perante qualquer juízo, instância ou tribunal",
                        "propor contra quem de direito as ações competentes e defendê-lo(a) nas contrárias",
                        "usar dos recursos legais e acompanhá-los",
                        "fazer acordos, transigir, desistir, renunciar, receber e dar quitação",
                        "substabelecer esta em outrem, com ou sem reservas de poderes"
                    ]
                    
                    # Gerar procuração
                    output_path = os.path.join(output_dir, f"procuracao_{client_data.get('cpf', 'cliente')}.pdf") if output_dir else None
                    result = self.document_generator.generate_procuracao(
                        client_data, advogado_data, poderes, output_path
                    )
                    
                    # Armazenar caminho do documento gerado
                    if isinstance(result, str):
                        generated_documents['procuracao'] = result
                    else:
                        # Se o resultado for bytes, salvar em arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                            tmp.write(result)
                            generated_documents['procuracao'] = tmp.name
                
                elif doc_type == 'contrato':
                    # Dados do advogado
                    advogado_data = {
                        'nome': 'Nome do Advogado',
                        'numero_oab': '123456',
                        'uf_oab': 'SP',
                        'cpf': '123.456.789-00',
                        'endereco': 'Endereço do Advogado',
                        'cidade': 'Cidade do Advogado',
                        'estado': 'SP'
                    }
                    
                    # Dados do serviço
                    servico_data = {
                        'descricao': 'Prestação de serviços advocatícios',
                        'valor': 'R$ 5.000,00',
                        'forma_pagamento': 'Em 10 parcelas mensais de R$ 500,00',
                        'prazo': '12 meses'
                    }
                    
                    # Gerar contrato
                    output_path = os.path.join(output_dir, f"contrato_{client_data.get('cpf', 'cliente')}.pdf") if output_dir else None
                    result = self.document_generator.generate_contrato(
                        client_data, advogado_data, servico_data, output_path
                    )
                    
                    # Armazenar caminho do documento gerado
                    if isinstance(result, str):
                        generated_documents['contrato'] = result
                    else:
                        # Se o resultado for bytes, salvar em arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                            tmp.write(result)
                            generated_documents['contrato'] = tmp.name
                
                elif doc_type == 'declaracao':
                    # Gerar declaração genérica
                    context = {
                        'title': 'DECLARAÇÃO',
                        'cliente_nome': client_data.get('nome', ''),
                        'cliente_cpf': client_data.get('cpf', ''),
                        'cliente_rg': client_data.get('rg', ''),
                        'cliente_endereco': client_data.get('endereco', ''),
                        'cliente_cidade': client_data.get('cidade', ''),
                        'cliente_estado': client_data.get('estado', ''),
                        'data_atual': datetime.datetime.now().strftime('%d/%m/%Y'),
                        'texto_declaracao': 'Declaro, para os devidos fins, que as informações prestadas são verdadeiras e assumo total responsabilidade pelas mesmas.'
                    }
                    
                    output_path = os.path.join(output_dir, f"declaracao_{client_data.get('cpf', 'cliente')}.pdf") if output_dir else None
                    result = self.document_generator.generate_document(
                        'declaracao.docx', context, 'pdf', output_path
                    )
                    
                    # Armazenar caminho do documento gerado
                    if isinstance(result, str):
                        generated_documents['declaracao'] = result
                    else:
                        # Se o resultado for bytes, salvar em arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                            tmp.write(result)
                            generated_documents['declaracao'] = tmp.name
                
                # Outros tipos de documentos podem ser adicionados aqui
                
            except Exception as e:
                logger.error(f"Erro ao gerar documento '{doc_type}': {e}")
        
        return generated_documents
    
    def send_documents_for_signature(self, 
                                   document_paths: List[str],
                                   signatories: List[Dict[str, Any]],
                                   signature_service_url: str,
                                   api_key: str) -> Dict[str, Any]:
        """
        Envia documentos para assinatura digital usando o serviço do prudentIA.
        
        Args:
            document_paths: Lista de caminhos de documentos para assinar
            signatories: Lista de dados dos signatários
            signature_service_url: URL do serviço de assinatura
            api_key: Chave de API para autenticação
            
        Returns:
            Dict[str, Any]: Resposta do serviço de assinatura
        """
        try:
            # Preparar dados para a requisição
            files = []
            for i, path in enumerate(document_paths):
                files.append(
                    ('documents', (os.path.basename(path), open(path, 'rb'), 'application/pdf'))
                )
            
            # Preparar dados dos signatários
            data = {
                'signatories': json.dumps(signatories),
                'workflow_type': 'sequential',  # ou 'parallel'
                'expires_in': '7d',  # 7 dias
                'notification_method': 'email,whatsapp'
            }
            
            # Enviar requisição para o serviço de assinatura
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            
            response = requests.post(
                f"{signature_service_url}/api/v1/signature/create",
                headers=headers,
                data=data,
                files=files
            )
            
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Erro ao enviar documentos para assinatura: {e}")
            raise
        finally:
            # Fechar arquivos
            for _, file_tuple in files: # Ajuste para iterar sobre a lista de tuplas
                file_tuple[1].close()
    
    def check_signature_status(self, 
                              signature_id: str,
                              signature_service_url: str,
                              api_key: str) -> Dict[str, Any]:
        """
        Verifica o status de um processo de assinatura.
        
        Args:
            signature_id: ID do processo de assinatura
            signature_service_url: URL do serviço de assinatura
            api_key: Chave de API para autenticação
            
        Returns:
            Dict[str, Any]: Status do processo de assinatura
        """
        try:
            # Enviar requisição para o serviço de assinatura
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            
            response = requests.get(
                f"{signature_service_url}/api/v1/signature/{signature_id}/status",
                headers=headers
            )
            
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Erro ao verificar status de assinatura: {e}")
            raise
    
    def download_signed_document(self, 
                               signature_id: str,
                               output_path: str,
                               signature_service_url: str,
                               api_key: str) -> str:
        """
        Baixa um documento assinado.
        
        Args:
            signature_id: ID do processo de assinatura
            output_path: Caminho para salvar o documento assinado
            signature_service_url: URL do serviço de assinatura
            api_key: Chave de API para autenticação
            
        Returns:
            str: Caminho do documento assinado
        """
        try:
            # Enviar requisição para o serviço de assinatura
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            
            response = requests.get(
                f"{signature_service_url}/api/v1/signature/{signature_id}/document",
                headers=headers,
                stream=True
            )
            
            response.raise_for_status()
            
            # Salvar documento
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return output_path
        
        except Exception as e:
            logger.error(f"Erro ao baixar documento assinado: {e}")
            raise

# Função para criar um fluxo completo de processamento de cliente
def process_client_onboarding(document_processor: DocumentProcessor, 
                             client_documents: List[str],
                             output_dir: str,
                             signature_service_url: str,
                             api_key: str) -> Dict[str, Any]:
    """
    Executa um fluxo completo de onboarding de cliente:
    1. Extrai dados dos documentos do cliente
    2. Gera documentos necessários (procuração e contrato)
    3. Envia documentos para assinatura
    
    Args:
        document_processor: Instância de DocumentProcessor
        client_documents: Lista de caminhos de documentos do cliente
        output_dir: Diretório para salvar documentos gerados
        signature_service_url: URL do serviço de assinatura
        api_key: Chave de API para autenticação
        
    Returns:
        Dict[str, Any]: Resultados do processo de onboarding
    """
    try:
        # 1. Extrair dados dos documentos do cliente
        client_data = document_processor.extract_client_data_from_documents(client_documents)
        
        # 2. Gerar documentos necessários
        generated_documents = document_processor.generate_documents_from_client_data(
            client_data,
            ['procuracao', 'contrato'],
            output_dir
        )
        
        # 3. Enviar documentos para assinatura
        signatories = [
            {
                'name': client_data.get('nome', 'Cliente'),
                'email': client_data.get('email', ''),
                'cpf': client_data.get('cpf', ''),
                'phone': client_data.get('telefone', '')
            },
            {
                'name': 'Nome do Advogado',  # Em um ambiente real, seria o usuário logado
                'email': 'advogado@exemplo.com',
                'cpf': '123.456.789-00',
                'phone': '(11) 98765-4321'
            }
        ]
        
        signature_result = document_processor.send_documents_for_signature(
            list(generated_documents.values()),
            signatories,
            signature_service_url,
            api_key
        )
        
        # 4. Retornar resultados
        return {
            'client_data': client_data,
            'generated_documents': generated_documents,
            'signature_id': signature_result.get('signature_id'),
            'signature_url': signature_result.get('signature_url'),
            'status': 'success'
        }
    
    except Exception as e:
        logger.error(f"Erro no fluxo de onboarding do cliente: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

# Exemplo de uso
if __name__ == "__main__":
    # Criar instância do processador
    processor = DocumentProcessor()
    
    # Exemplo: Criar formulário de cliente
    # client_form_info = processor.create_client_form(use_google_forms=False)
    # print(f"Formulário de cliente criado: {client_form_info}")
    
    # Exemplo: Processar um documento PDF (substitua pelo caminho de um PDF real)
    # try:
    #     pdf_path = "caminho/para/seu/documento.pdf"
    #     extracted_data = processor.process_document(pdf_path)
    #     print(f"Dados extraídos: {json.dumps([data.to_dict() for data in extracted_data], indent=2, ensure_ascii=False)}")
    # except FileNotFoundError:
    #     print(f"Arquivo de exemplo não encontrado: {pdf_path}")
    # except Exception as e:
    #     print(f"Erro ao processar PDF: {e}")
    
    # Exemplo: Gerar uma procuração (substitua pelos dados reais)
    # client_data_example = {
    #     'nome': 'Fulano de Tal',
    #     'nacionalidade': 'brasileiro',
    #     'estado_civil': 'casado',
    #     'profissao': 'engenheiro',
    #     'rg': '12.345.678-9',
    #     'cpf': '123.456.789-00',
    #     'endereco': 'Rua Exemplo, 123',
    #     'cidade': 'São Paulo',
    #     'estado': 'SP'
    # }
    
    # advogado_data_example = {
    #     'nome': 'Ciclano de Souza',
    #     'nacionalidade': 'brasileiro',
    #     'estado_civil': 'solteiro',
    #     'numero_oab': '123456',
    #     'uf_oab': 'SP',
    #     'cpf': '987.654.321-00',
    #     'endereco': 'Avenida Jurídica, 456',
    #     'cidade': 'São Paulo',
    #     'estado': 'SP'
    # }
    
    # poderes_example = [
    #     "representar o outorgante perante qualquer juízo, instância ou tribunal",
    #     "propor contra quem de direito as ações competentes e defendê-lo nas contrárias"
    # ]
    
    # try:
    #     # Criar diretório de templates se não existir
    #     os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
        
    #     # Criar um template de procuração DOCX (procuracao.docx) no diretório de templates
    #     # Este arquivo deve conter os campos de mesclagem (ex: {{ outorgante_nome }})
        
    #     procuracao_path = processor.document_generator.generate_procuracao(
    #         client_data_example,
    #         advogado_data_example,
    #         poderes_example,
    #         output_path="procuracao_gerada.pdf"
    #     )
    #     print(f"Procuração gerada em: {procuracao_path}")
    # except FileNotFoundError:
    #     print(f"Template de procuração não encontrado. Crie 'procuracao.docx' no diretório '{Config.TEMPLATES_DIR}'.")
    # except Exception as e:
    #     print(f"Erro ao gerar procuração: {e}")
    
    # Exemplo de fluxo de onboarding (requer documentos e configurações reais)
    # client_docs_paths = ["caminho/para/rg.pdf", "caminho/para/cpf.pdf"]
    # output_directory = "documentos_cliente"
    # signature_service_url_example = "http://localhost:8000"  # URL do seu serviço de assinatura
    # api_key_example = "sua_chave_de_api"
    
    # onboarding_result = process_client_onboarding(
    #     processor,
    #     client_docs_paths,
    #     output_directory,
    #     signature_service_url_example,
    #     api_key_example
    # )
    # print(f"Resultado do onboarding: {json.dumps(onboarding_result, indent=2, ensure_ascii=False)}")
    
    pass
