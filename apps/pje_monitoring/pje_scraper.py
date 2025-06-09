"""
pje_scraper.py - Módulo de Web Scraping do PJe para prudentIA

Este módulo implementa funcionalidades para buscar e processar publicações
do sistema PJe (Processo Judicial Eletrônico) a partir do site
https://comunica.pje.jus.br/consulta.

Permite buscar publicações por número OAB, UF, e intervalo de datas,
processando os resultados para extração de informações relevantes.
"""

import os
import re
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urlencode

import httpx
from selectolax.parser import HTMLParser
from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
BASE_URL = "https://comunica.pje.jus.br/consulta"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
DEFAULT_TIMEOUT = 30.0  # segundos
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1.0  # segundos entre requisições

# Modelos de dados
class Publicacao(BaseModel):
    """Modelo para representar uma publicação do PJe."""
    id: Optional[str] = None
    numero_processo: str
    data_publicacao: datetime
    orgao_julgador: str
    conteudo: str
    tribunal: str
    caderno: Optional[str] = None
    secao: Optional[str] = None
    magistrado: Optional[str] = None
    url_processo: Optional[str] = None
    partes: Optional[List[Dict[str, str]]] = None
    hash: Optional[str] = None
    
    @validator('numero_processo')
    def validar_numero_processo(cls, v):
        """Valida e formata o número do processo no padrão CNJ."""
        # Remove caracteres não numéricos
        nums = re.sub(r'\D', '', v)
        if len(nums) == 20:
            # Formata no padrão CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
            return f"{nums[0:7]}-{nums[7:9]}.{nums[9:13]}.{nums[13:14]}.{nums[14:16]}.{nums[16:20]}"
        return v
    
    def calcular_hash(self) -> str:
        """Calcula um hash único para a publicação baseado em seus atributos."""
        import hashlib
        texto = f"{self.numero_processo}|{self.data_publicacao.isoformat()}|{self.orgao_julgador}"
        return hashlib.md5(texto.encode()).hexdigest()
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.hash:
            self.hash = self.calcular_hash()

class ResultadoBusca(BaseModel):
    """Modelo para representar o resultado de uma busca de publicações."""
    publicacoes: List[Publicacao] = []
    total_encontrado: int = 0
    pagina_atual: int = 1
    total_paginas: int = 1
    parametros_busca: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    erro: Optional[str] = None

class ConfiguracaoBusca(BaseModel):
    """Configuração para busca de publicações no PJe."""
    numero_oab: str
    uf_oab: str
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    pagina: int = 1
    itens_por_pagina: int = 50
    
    @validator('uf_oab')
    def validar_uf(cls, v):
        """Valida a UF, convertendo para maiúsculas."""
        v = v.upper()
        ufs_validas = [
            "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", 
            "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", 
            "RO", "RR", "RS", "SC", "SE", "SP", "TO"
        ]
        if v not in ufs_validas:
            raise ValueError(f"UF inválida: {v}")
        return v
    
    def para_parametros_url(self) -> Dict[str, str]:
        """Converte a configuração para parâmetros de URL."""
        params = {
            "numeroOab": self.numero_oab,
            "ufOab": self.uf_oab,
            "pagina": str(self.pagina),
            "tamanhoPagina": str(self.itens_por_pagina)
        }
        
        if self.data_inicio:
            params["dataDisponibilizacaoInicio"] = self.data_inicio.strftime("%d/%m/%Y")
        
        if self.data_fim:
            params["dataDisponibilizacaoFim"] = self.data_fim.strftime("%d/%m/%Y")
            
        return params

class PJeScraperException(Exception):
    """Exceção base para erros do scraper do PJe."""
    pass

class ConexaoException(PJeScraperException):
    """Exceção para erros de conexão."""
    pass

class ParsingException(PJeScraperException):
    """Exceção para erros de parsing de HTML."""
    pass

class CaptchaException(PJeScraperException):
    """Exceção para detecção de captcha."""
    pass

class PaginaNaoEncontradaException(PJeScraperException):
    """Exceção para página não encontrada (404)."""
    pass

# Funções de parsing HTML
def extrair_dados_publicacao(elemento_html) -> Optional[Dict[str, Any]]:
    """
    Extrai dados de uma publicação a partir de um elemento HTML.
    
    Args:
        elemento_html: Elemento HTML contendo os dados da publicação
        
    Returns:
        Dict contendo os dados extraídos ou None se não for possível extrair
    """
    try:
        # Nota: A estrutura exata do HTML pode variar, este é um exemplo
        # que precisará ser ajustado conforme a estrutura real do site
        
        # Extrair número do processo
        numero_processo_elem = elemento_html.css_first("div.numero-processo")
        if not numero_processo_elem:
            numero_processo_elem = elemento_html.css_first("span.processo-numero")
        
        numero_processo = numero_processo_elem.text().strip() if numero_processo_elem else "N/A"
        
        # Extrair data da publicação
        data_elem = elemento_html.css_first("div.data-publicacao")
        if not data_elem:
            data_elem = elemento_html.css_first("span.data")
        
        data_texto = data_elem.text().strip() if data_elem else ""
        data_publicacao = None
        
        # Tentar diferentes formatos de data
        data_formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for formato in data_formatos:
            try:
                data_publicacao = datetime.strptime(data_texto, formato)
                break
            except ValueError:
                continue
        
        if not data_publicacao and data_texto:
            # Tentar extrair com regex se os formatos padrão falharem
            match = re.search(r'(\d{2})[/\-](\d{2})[/\-](\d{4})', data_texto)
            if match:
                dia, mes, ano = match.groups()
                data_publicacao = datetime(int(ano), int(mes), int(dia))
        
        if not data_publicacao:
            data_publicacao = datetime.now()  # Fallback para data atual
        
        # Extrair órgão julgador
        orgao_elem = elemento_html.css_first("div.orgao-julgador")
        if not orgao_elem:
            orgao_elem = elemento_html.css_first("span.orgao")
        
        orgao_julgador = orgao_elem.text().strip() if orgao_elem else "N/A"
        
        # Extrair conteúdo da publicação
        conteudo_elem = elemento_html.css_first("div.conteudo-publicacao")
        if not conteudo_elem:
            conteudo_elem = elemento_html.css_first("div.texto-publicacao")
        
        conteudo = conteudo_elem.text().strip() if conteudo_elem else "N/A"
        
        # Extrair tribunal
        tribunal_elem = elemento_html.css_first("div.tribunal")
        tribunal = tribunal_elem.text().strip() if tribunal_elem else "N/A"
        
        # Extrair URL do processo, se disponível
        url_processo = None
        link_elem = elemento_html.css_first("a.link-processo")
        if link_elem and link_elem.attributes.get("href"):
            url_processo = link_elem.attributes.get("href")
        
        return {
            "numero_processo": numero_processo,
            "data_publicacao": data_publicacao,
            "orgao_julgador": orgao_julgador,
            "conteudo": conteudo,
            "tribunal": tribunal,
            "url_processo": url_processo
        }
    except Exception as e:
        logger.error(f"Erro ao extrair dados da publicação: {str(e)}")
        return None

def extrair_informacoes_paginacao(html_parser) -> Tuple[int, int, int]:
    """
    Extrai informações de paginação do HTML.
    
    Args:
        html_parser: Parser HTML da página
        
    Returns:
        Tupla (total_encontrado, pagina_atual, total_paginas)
    """
    try:
        # Buscar elemento de paginação
        paginacao_elem = html_parser.css_first("div.paginacao")
        if not paginacao_elem:
            paginacao_elem = html_parser.css_first("ul.pagination")
        
        if not paginacao_elem:
            return 0, 1, 1
        
        # Extrair informações de texto como "Exibindo 1-50 de 320 resultados"
        info_texto = paginacao_elem.text()
        match = re.search(r'de\s+(\d+)\s+resultados', info_texto)
        total_encontrado = int(match.group(1)) if match else 0
        
        # Extrair página atual
        pagina_atual_elem = html_parser.css_first("li.active span")
        pagina_atual = int(pagina_atual_elem.text()) if pagina_atual_elem else 1
        
        # Calcular total de páginas
        total_paginas = (total_encontrado + 49) // 50  # Assumindo 50 itens por página
        
        return total_encontrado, pagina_atual, total_paginas
    except Exception as e:
        logger.error(f"Erro ao extrair informações de paginação: {str(e)}")
        return 0, 1, 1

def verificar_captcha(html_content: str) -> bool:
    """
    Verifica se a página contém um captcha.
    
    Args:
        html_content: Conteúdo HTML da página
        
    Returns:
        True se um captcha for detectado, False caso contrário
    """
    captcha_indicators = [
        "captcha",
        "recaptcha",
        "g-recaptcha",
        "Verificação de segurança",
        "Prove que você é humano",
        "robot"
    ]
    
    html_lower = html_content.lower()
    return any(indicator in html_lower for indicator in captcha_indicators)

def verificar_erro_404(html_content: str) -> bool:
    """
    Verifica se a página retornou um erro 404.
    
    Args:
        html_content: Conteúdo HTML da página
        
    Returns:
        True se um erro 404 for detectado, False caso contrário
    """
    not_found_indicators = [
        "404",
        "não encontrada",
        "not found",
        "página inexistente"
    ]
    
    html_lower = html_content.lower()
    return any(indicator in html_lower for indicator in not_found_indicators)

# Classe principal do scraper
class PJeScraper:
    """
    Classe para scraping de publicações do PJe.
    
    Implementa métodos para buscar e processar publicações do sistema PJe
    a partir do site https://comunica.pje.jus.br/consulta.
    """
    
    def __init__(self, 
                proxy: Optional[str] = None, 
                timeout: float = DEFAULT_TIMEOUT,
                max_retries: int = MAX_RETRIES,
                rate_limit: float = RATE_LIMIT_DELAY):
        """
        Inicializa o scraper do PJe.
        
        Args:
            proxy: URL do proxy (opcional)
            timeout: Timeout para requisições em segundos
            max_retries: Número máximo de tentativas para requisições
            rate_limit: Delay entre requisições em segundos
        """
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        # Headers padrão para simular um navegador
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "TE": "Trailers",
        }
    
    def _aplicar_rate_limit(self):
        """
        Aplica rate limiting para evitar sobrecarga do servidor.
        """
        agora = time.time()
        tempo_desde_ultima_req = agora - self.last_request_time
        
        if tempo_desde_ultima_req < self.rate_limit:
            time.sleep(self.rate_limit - tempo_desde_ultima_req)
        
        self.last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def _fazer_requisicao_async(self, url: str, params: Dict[str, str]) -> str:
        """
        Faz uma requisição HTTP assíncrona com rate limiting e retries.
        
        Args:
            url: URL para requisição
            params: Parâmetros da query string
            
        Returns:
            Conteúdo HTML da resposta
            
        Raises:
            ConexaoException: Se houver erro de conexão
            CaptchaException: Se um captcha for detectado
            PaginaNaoEncontradaException: Se a página não for encontrada
        """
        self._aplicar_rate_limit()
        
        try:
            async with httpx.AsyncClient(
                proxies=self.proxy, 
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                
                html_content = response.text
                
                # Verificar se há captcha
                if verificar_captcha(html_content):
                    raise CaptchaException("Captcha detectado na página")
                
                # Verificar se é uma página 404
                if verificar_erro_404(html_content) or response.status_code == 404:
                    raise PaginaNaoEncontradaException("Página não encontrada (404)")
                
                return html_content
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise ConexaoException(f"Erro ao conectar ao PJe: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    def _fazer_requisicao_sync(self, url: str, params: Dict[str, str]) -> str:
        """
        Faz uma requisição HTTP síncrona com rate limiting e retries.
        
        Args:
            url: URL para requisição
            params: Parâmetros da query string
            
        Returns:
            Conteúdo HTML da resposta
            
        Raises:
            ConexaoException: Se houver erro de conexão
            CaptchaException: Se um captcha for detectado
            PaginaNaoEncontradaException: Se a página não for encontrada
        """
        self._aplicar_rate_limit()
        
        try:
            with httpx.Client(
                proxies=self.proxy, 
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                
                html_content = response.text
                
                # Verificar se há captcha
                if verificar_captcha(html_content):
                    raise CaptchaException("Captcha detectado na página")
                
                # Verificar se é uma página 404
                if verificar_erro_404(html_content) or response.status_code == 404:
                    raise PaginaNaoEncontradaException("Página não encontrada (404)")
                
                return html_content
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise ConexaoException(f"Erro ao conectar ao PJe: {str(e)}")
    
    def _processar_html(self, html_content: str, config: ConfiguracaoBusca) -> ResultadoBusca:
        """
        Processa o HTML para extrair publicações e informações de paginação.
        
        Args:
            html_content: Conteúdo HTML da página
            config: Configuração da busca
            
        Returns:
            ResultadoBusca contendo as publicações encontradas e metadados
            
        Raises:
            ParsingException: Se houver erro no parsing do HTML
        """
        try:
            parser = HTMLParser(html_content)
            
            # Extrair informações de paginação
            total_encontrado, pagina_atual, total_paginas = extrair_informacoes_paginacao(parser)
            
            # Buscar elementos de publicação
            # Nota: O seletor CSS exato depende da estrutura do site
            elementos_publicacao = parser.css("div.publicacao")
            if not elementos_publicacao:
                elementos_publicacao = parser.css("div.resultado-item")
            
            if not elementos_publicacao:
                logger.warning("Nenhum elemento de publicação encontrado no HTML")
            
            # Extrair dados de cada publicação
            publicacoes = []
            for elem in elementos_publicacao:
                dados = extrair_dados_publicacao(elem)
                if dados:
                    try:
                        publicacoes.append(Publicacao(**dados))
                    except Exception as e:
                        logger.error(f"Erro ao criar objeto Publicacao: {str(e)}")
            
            return ResultadoBusca(
                publicacoes=publicacoes,
                total_encontrado=total_encontrado,
                pagina_atual=pagina_atual,
                total_paginas=total_paginas,
                parametros_busca=config.dict()
            )
        except Exception as e:
            logger.error(f"Erro ao processar HTML: {str(e)}")
            raise ParsingException(f"Erro ao processar HTML: {str(e)}")
    
    async def buscar_publicacoes_async(self, config: ConfiguracaoBusca) -> ResultadoBusca:
        """
        Busca publicações de forma assíncrona.
        
        Args:
            config: Configuração da busca
            
        Returns:
            ResultadoBusca contendo as publicações encontradas e metadados
        """
        try:
            params = config.para_parametros_url()
            html_content = await self._fazer_requisicao_async(BASE_URL, params)
            return self._processar_html(html_content, config)
        except PJeScraperException as e:
            logger.error(f"Erro na busca de publicações: {str(e)}")
            return ResultadoBusca(
                publicacoes=[],
                erro=str(e),
                parametros_busca=config.dict()
            )
    
    def buscar_publicacoes(self, config: ConfiguracaoBusca) -> ResultadoBusca:
        """
        Busca publicações de forma síncrona.
        
        Args:
            config: Configuração da busca
            
        Returns:
            ResultadoBusca contendo as publicações encontradas e metadados
        """
        try:
            params = config.para_parametros_url()
            html_content = self._fazer_requisicao_sync(BASE_URL, params)
            return self._processar_html(html_content, config)
        except PJeScraperException as e:
            logger.error(f"Erro na busca de publicações: {str(e)}")
            return ResultadoBusca(
                publicacoes=[],
                erro=str(e),
                parametros_busca=config.dict()
            )
    
    async def buscar_todas_paginas_async(self, config: ConfiguracaoBusca) -> ResultadoBusca:
        """
        Busca todas as páginas de publicações de forma assíncrona.
        
        Args:
            config: Configuração da busca
            
        Returns:
            ResultadoBusca contendo todas as publicações encontradas
        """
        # Buscar primeira página para obter o total de páginas
        config.pagina = 1
        resultado = await self.buscar_publicacoes_async(config)
        
        if resultado.erro or resultado.total_paginas <= 1:
            return resultado
        
        # Buscar páginas restantes em paralelo
        tarefas = []
        for pagina in range(2, resultado.total_paginas + 1):
            config_pagina = ConfiguracaoBusca(**config.dict())
            config_pagina.pagina = pagina
            tarefas.append(self.buscar_publicacoes_async(config_pagina))
        
        # Aguardar todas as tarefas e combinar resultados
        resultados_adicionais = await asyncio.gather(*tarefas)
        
        # Combinar publicações de todas as páginas
        todas_publicacoes = resultado.publicacoes.copy()
        for res in resultados_adicionais:
            todas_publicacoes.extend(res.publicacoes)
        
        # Atualizar resultado com todas as publicações
        resultado.publicacoes = todas_publicacoes
        resultado.total_encontrado = len(todas_publicacoes)
        
        return resultado
    
    def buscar_todas_paginas(self, config: ConfiguracaoBusca) -> ResultadoBusca:
        """
        Busca todas as páginas de publicações de forma síncrona.
        
        Args:
            config: Configuração da busca
            
        Returns:
            ResultadoBusca contendo todas as publicações encontradas
        """
        # Buscar primeira página para obter o total de páginas
        config.pagina = 1
        resultado = self.buscar_publicacoes(config)
        
        if resultado.erro or resultado.total_paginas <= 1:
            return resultado
        
        # Buscar páginas restantes sequencialmente
        todas_publicacoes = resultado.publicacoes.copy()
        for pagina in range(2, resultado.total_paginas + 1):
            config_pagina = ConfiguracaoBusca(**config.dict())
            config_pagina.pagina = pagina
            res = self.buscar_publicacoes(config_pagina)
            if not res.erro:
                todas_publicacoes.extend(res.publicacoes)
        
        # Atualizar resultado com todas as publicações
        resultado.publicacoes = todas_publicacoes
        resultado.total_encontrado = len(todas_publicacoes)
        
        return resultado
    
    async def buscar_por_periodo_async(self, 
                                      numero_oab: str, 
                                      uf_oab: str, 
                                      data_inicio: Optional[datetime] = None,
                                      data_fim: Optional[datetime] = None) -> ResultadoBusca:
        """
        Busca publicações por período de forma assíncrona.
        
        Args:
            numero_oab: Número da OAB
            uf_oab: UF da OAB
            data_inicio: Data inicial (opcional)
            data_fim: Data final (opcional)
            
        Returns:
            ResultadoBusca contendo as publicações encontradas
        """
        config = ConfiguracaoBusca(
            numero_oab=numero_oab,
            uf_oab=uf_oab,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
        return await self.buscar_todas_paginas_async(config)
    
    def buscar_por_periodo(self, 
                          numero_oab: str, 
                          uf_oab: str, 
                          data_inicio: Optional[datetime] = None,
                          data_fim: Optional[datetime] = None) -> ResultadoBusca:
        """
        Busca publicações por período de forma síncrona.
        
        Args:
            numero_oab: Número da OAB
            uf_oab: UF da OAB
            data_inicio: Data inicial (opcional)
            data_fim: Data final (opcional)
            
        Returns:
            ResultadoBusca contendo as publicações encontradas
        """
        config = ConfiguracaoBusca(
            numero_oab=numero_oab,
            uf_oab=uf_oab,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
        return self.buscar_todas_paginas(config)
    
    async def buscar_ultimos_dias_async(self, 
                                       numero_oab: str, 
                                       uf_oab: str, 
                                       dias: int = 7) -> ResultadoBusca:
        """
        Busca publicações dos últimos dias de forma assíncrona.
        
        Args:
            numero_oab: Número da OAB
            uf_oab: UF da OAB
            dias: Número de dias para buscar
            
        Returns:
            ResultadoBusca contendo as publicações encontradas
        """
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        return await self.buscar_por_periodo_async(
            numero_oab=numero_oab,
            uf_oab=uf_oab,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
    
    def buscar_ultimos_dias(self, 
                           numero_oab: str, 
                           uf_oab: str, 
                           dias: int = 7) -> ResultadoBusca:
        """
        Busca publicações dos últimos dias de forma síncrona.
        
        Args:
            numero_oab: Número da OAB
            uf_oab: UF da OAB
            dias: Número de dias para buscar
            
        Returns:
            ResultadoBusca contendo as publicações encontradas
        """
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        return self.buscar_por_periodo(
            numero_oab=numero_oab,
            uf_oab=uf_oab,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
    
    def salvar_resultado_json(self, resultado: ResultadoBusca, caminho: str) -> None:
        """
        Salva o resultado da busca em um arquivo JSON.
        
        Args:
            resultado: Resultado da busca
            caminho: Caminho do arquivo para salvar
        """
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(resultado.dict(), f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
        logger.info(f"Resultado salvo em {caminho}")

# Função para uso em linha de comando
async def main_async():
    """Função principal para execução assíncrona via linha de comando."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper de publicações do PJe')
    parser.add_argument('--oab', required=True, help='Número da OAB')
    parser.add_argument('--uf', required=True, help='UF da OAB')
    parser.add_argument('--dias', type=int, default=7, help='Número de dias para buscar')
    parser.add_argument('--saida', default='publicacoes.json', help='Arquivo de saída JSON')
    parser.add_argument('--proxy', help='URL do proxy (opcional)')
    
    args = parser.parse_args()
    
    scraper = PJeScraper(proxy=args.proxy)
    
    print(f"Buscando publicações para OAB {args.oab}/{args.uf} nos últimos {args.dias} dias...")
    resultado = await scraper.buscar_ultimos_dias_async(args.oab, args.uf, args.dias)
    
    print(f"Encontradas {len(resultado.publicacoes)} publicações")
    scraper.salvar_resultado_json(resultado, args.saida)
    print(f"Resultado salvo em {args.saida}")

def main():
    """Função principal para execução síncrona via linha de comando."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper de publicações do PJe')
    parser.add_argument('--oab', required=True, help='Número da OAB')
    parser.add_argument('--uf', required=True, help='UF da OAB')
    parser.add_argument('--dias', type=int, default=7, help='Número de dias para buscar')
    parser.add_argument('--saida', default='publicacoes.json', help='Arquivo de saída JSON')
    parser.add_argument('--proxy', help='URL do proxy (opcional)')
    parser.add_argument('--async', dest='async_mode', action='store_true', help='Usar modo assíncrono')
    
    args = parser.parse_args()
    
    if args.async_mode:
        asyncio.run(main_async())
        return
    
    scraper = PJeScraper(proxy=args.proxy)
    
    print(f"Buscando publicações para OAB {args.oab}/{args.uf} nos últimos {args.dias} dias...")
    resultado = scraper.buscar_ultimos_dias(args.oab, args.uf, args.dias)
    
    print(f"Encontradas {len(resultado.publicacoes)} publicações")
    scraper.salvar_resultado_json(resultado, args.saida)
    print(f"Resultado salvo em {args.saida}")

if __name__ == "__main__":
    main()
