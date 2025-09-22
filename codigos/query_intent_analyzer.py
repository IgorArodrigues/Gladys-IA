"""
Analisador de Intenção de Consulta

Este módulo analisa consultas do usuário para determinar a intenção de busca e estratégia.
Ele detecta quando os usuários querem buscas abrangentes versus perguntas específicas.
"""

import re
from typing import Dict, List

# Configuração para padrões de busca abrangente
COMPREHENSIVE_PATTERNS = [
    # Padrões de descoberta de documentos
    r'tell me (all )?the documents?',
    r'what documents?',
    r'which documents?',
    r'find (all )?documents?',
    r'search for documents?',
    r'list (all )?documents?',
    r'show me (all )?documents?',
    r'get (all )?documents?',
    
    # Padrões de busca por termo específico
    r'contain(ing)?\s+',
    r'with\s+',
    r'that have\s+',
    r'that include\s+',
    r'mentioning\s+',
    r'referring to\s+',
    
    # Padrões específicos para CNPJ/CPF
    r'cnpj\s+[\d\.\/\-]+',
    r'cpf\s+[\d\.\-]+',
    r'[\d\.\/\-]+\s+cnpj',
    r'[\d\.\-]+\s+cpf',
    
    # Padrões abrangentes em português
    r'resumo\s+COMPLETO',  # Correspondência exata para consulta do usuário
    r'COMPLETO\s+por\s+se[cç][ãa]o',  # Outro padrão da consulta do usuário
    r'voce\s+tem\s+acesso\s+documento',  # Consultas "Você tem acesso ao documento"
    r'tem\s+acesso\s+documento',  # Consultas "Tem acesso ao documento"
    r'acesso\s+documento',  # Consultas "Acesso ao documento"
    r'neste\s+documento',  # Consultas de acompanhamento "Neste documento"
    r'no\s+documento',  # Consultas de acompanhamento "No documento"
    r'do\s+documento',  # Consultas de acompanhamento "Do documento"
    r'da\s+documento',  # Consultas de acompanhamento "Da documento"
    r'fale mais sobre',
    r'me d[êe] mais detalhes sobre',
    r'explique (um pouco )?mais sobre',
    r'se aprofunde (mais )?nisso',
    r'elabore mais sobre (esse|o último) ponto',
    r'e sobre (o|a)',
    
    # Padrões de esclarecimento - pedindo definições/explicações
    r'o que (exatamente )?significa',
    r'o que quer dizer',
    r'pode definir',
    r'o que é esse termo',
    r'o que é (esse|este) (termo|conceito|ponto)',
    r'defina (esse|este) (termo|conceito)',
    r'explique (esse|este) (termo|conceito)',
    
    # Padrões de referência direta - usando pronomes e referências diretas
    r'\b(e|mas|então)\s+isso\b',
    r'\bdisso\b',
    r'\bnisso\b',
    r'explique (o|a) (primeiro|segundo|último) (ponto|item)',
    r'baseado nisso',
    r'com base nisso',
    r'a partir disso',
    r'em relação a isso',
    r'sobre isso',
    r'quanto a isso',
    r'no que se refere a isso',
    r'resumo\s+(completo|detalhado|integral|abrangente)',
    r'resumo\s+[Cc]ompleto',  # Completo insensível a maiúsculas/minúsculas
    r'analise\s+(completa|detalhada|integral|abrangente)',
    r'me\s+d[êe]\s+um?\s+(resumo|analise)\s+(completo|completa|detalhado|detalhada)',
    r'me\s+mostre\s+(todos?|todas?|completo|completa)',
    r'me\s+explique\s+(todos?|todas?|completo|completa)',
    r'\bCOMPLETO\b',  # COMPLETO independente em maiúsculas
    r'\bcompleto\b',  # Completo independente em minúsculas
    
    # Padrões abrangentes específicos de documento
    r'com\s+base\s+(no|na)\s+documento\s+',
    r'baseado\s+(no|na)\s+documento\s+',
    r'baseada\s+(no|na)\s+documento\s+',
    r'segundo\s+o\s+documento\s+',
    r'segundo\s+a\s+documento\s+',
    r'conforme\s+o\s+documento\s+',
    r'conforme\s+a\s+documento\s+',
    r'de\s+acordo\s+com\s+o\s+documento\s+',
    r'de\s+acordo\s+com\s+a\s+documento\s+',
    r'apresentadas?\s+(no|na)\s+documento\s+',
    r'apresentados?\s+(no|na)\s+documento\s+',
    r'contidas?\s+(no|na)\s+documento\s+',
    r'contidos?\s+(no|na)\s+documento\s+',
    r'no\s+documento\s+',
    r'na\s+documento\s+',
    r'do\s+documento\s+',
    r'da\s+documento\s+',
    
    # Padrões abrangentes específicos de documento em português
    r'quais?\s+(as\s+)?(principais?|principais?)\s+(tend[eê]ncias?|caracter[ií]sticas?|aspectos?|pontos?)',
    r'qual\s+(o\s+)?(padr[aã]o|padr[oõ]es?|modelo|modelos?|estrutura|estruturas?)',
    r'o\s+que\s+é\s+',  # Perguntas "o que é"
    r'como\s+funciona\s+',  # Perguntas "como funciona"
    r'explique\s+(o\s+)?(conceito|conceitos?|termo|termos?|defini[cç][aã]o)',
    r'defina\s+(o\s+)?(conceito|conceitos?|termo|termos?)',
    r'descreva\s+(as\s+)?(principais?|caracter[ií]sticas?|aspectos?|pontos?)',
    r'apresente\s+(as\s+)?(principais?|caracter[ií]sticas?|aspectos?|pontos?)',
    r'detalhe\s+(as\s+)?(principais?|caracter[ií]sticas?|aspectos?|pontos?)',
    r'me\s+explique\s+(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+conte\s+(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+informe\s+(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+mostre\s+(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+d[êe]\s+(informa[cç][oõ]es?\s+)?(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+forne[cç]a\s+(informa[cç][oõ]es?\s+)?(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+apresente\s+(informa[cç][oõ]es?\s+)?(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+descreva\s+(informa[cç][oõ]es?\s+)?(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+detalle\s+(informa[cç][oõ]es?\s+)?(sobre|acerca\s+de|a\s+respeito\s+de)',
    r'me\s+explique\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+conte\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+informe\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+mostre\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+d[êe]\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+forne[cç]a\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+apresente\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+descreva\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    r'me\s+detalle\s+(o\s+)?(conte[uú]do|conte[uú]dos?|assunto|assuntos?)',
    
    # Padrões abrangentes em inglês
    r'give\s+me\s+(a\s+)?(complete|full|detailed|comprehensive)',
    r'show\s+me\s+(all|every|complete|full|detailed)',
    r'explain\s+(all|every|complete|full|detailed)',
    r'analyze\s+(all|every|complete|full|detailed)',
    
    # Solicitações gerais de informações abrangente
    r'\b(all|every|full|total|comprehensive)\b',  # Removido 'complete' para evitar conflito
    r'\b(todos?|todas?|total|integral|integralmente)\b',  # Removido 'completo|completa' para evitar conflito
    r'\b(detalhado|detalhada|detalhadamente|minucioso|minuciosa)\b',
    r'\b(abrangente|extenso|extensa|profundo|profunda)\b',
]

# Padrões para extrair termos de busca com seus índices de grupo de captura
# Formato: (pattern, capture_group_index) onde capture_group_index indica qual grupo contém o termo de busca
TERM_EXTRACTION_PATTERNS = [
    # Padrões em inglês - grupo de captura único (índice 0)
    (r'containing\s+([^\s,]+)', 0),
    (r'with\s+([^\s,]+)', 0),
    (r'that have\s+([^\s,]+)', 0),
    (r'mentioning\s+([^\s,]+)', 0),
    
    # Padrões em português - grupo de captura único (índice 0)
    (r'contendo\s+([^\s,]+)', 0),
    (r'com\s+([^\s,]+)', 0),
    (r'mencionando\s+([^\s,]+)', 0),
    (r'documento\s+([^?]+)', 0),
    (r'no\s+documento\s+([^?]+)', 0),
    (r'do\s+documento\s+([^?]+)', 0),
    (r'da\s+documento\s+([^?]+)', 0),
    (r'com\s+base\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'baseado\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'baseada\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'apresentadas?\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'apresentados?\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'contidas?\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'contidos?\s+(no|na)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'segundo\s+(o|a)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'conforme\s+(o|a)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    (r'de\s+acordo\s+com\s+(o|a)\s+documento\s+([^?]+)', 1),  # Grupo de captura 1 é o nome do documento
    
    # Padrões em português - múltiplos grupos de captura, termo de busca é o último grupo (índice 1)
    (r'que\s+(tem|tenha|inclui|inclua)\s+([^\s,]+)', 1),
    (r'falando\s+(sobre|de)\s+([^\s,]+)', 1),
    (r'resumo\s+(de|sobre)\s+([^\s,]+)', 1),
    (r'analise\s+(de|sobre)\s+([^\s,]+)', 1),
]

def analyze_query_intent(query: str, enable_debug_logging: bool = False) -> Dict:
    """
    Analisa a consulta do usuário para determinar a intenção de busca e estratégia.
    
    Args:
        query: String da consulta do usuário
        enable_debug_logging: Se deve imprimir informações de debug
        
    Returns:
        Dicionário contendo:
        - is_comprehensive_search: Booleano indicando se busca abrangente é necessária
        - intent_type: String descrevendo o tipo de intenção
        - search_terms: Lista de termos de busca extraídos
        - query_lower: Versão em minúsculas da consulta
    """
    query_lower = query.lower()
    
    # Verificar padrões abrangentes PRIMEIRO
    is_comprehensive = False
    matched_pattern = None
    for pattern in COMPREHENSIVE_PATTERNS:
        if re.search(pattern, query_lower):
            is_comprehensive = True
            matched_pattern = pattern
            break
    
    # Extrair termos de busca para buscas abrangentes
    search_terms = []
    if is_comprehensive:
        # Extrair números de CNPJ/CPF
        cnpj_matches = re.findall(r'[\d\.\/\-]{14,18}', query)
        search_terms.extend(cnpj_matches)
        
        # Extrair outros termos específicos
        # Procurar por strings entre aspas
        quoted_terms = re.findall(r'"([^"]+)"', query)
        search_terms.extend(quoted_terms)
        
        # Procurar por termos após "containing", "with", etc. (Português e Inglês)
        for pattern_info in TERM_EXTRACTION_PATTERNS:
            pattern, capture_group_index = pattern_info
            matches = re.findall(pattern, query_lower)
            if matches:
                # Extrair o grupo de captura específico que contém o termo de busca
                if isinstance(matches[0], tuple):
                    search_terms.extend([match[capture_group_index] for match in matches])
                else:
                    search_terms.extend(matches)
        
        # Remover duplicatas mantendo a ordem
        seen = set()
        unique_search_terms = []
        for term in search_terms:
            if term not in seen:
                seen.add(term)
                unique_search_terms.append(term)
        search_terms = unique_search_terms
    
    # Log de debug
    if enable_debug_logging:
        print(f"Análise de intenção da consulta:")
        print(f"  Consulta: '{query}'")
        print(f"  Consulta em minúsculas: '{query_lower}'")
        print(f"  É abrangente: {is_comprehensive}")
        print(f"  Padrão correspondente: {matched_pattern}")
        print(f"  Termos de busca encontrados: {search_terms}")
    
    # Determinar tipo de intenção
    if is_comprehensive:
        if search_terms:
            intent_type = "comprehensive_term_search"
        else:
            intent_type = "comprehensive_document_search"
    else:
        intent_type = "specific_question"
    
    return {
        'is_comprehensive_search': is_comprehensive,
        'intent_type': intent_type,
        'search_terms': search_terms,
        'query_lower': query_lower
    }

def add_comprehensive_pattern(pattern: str, priority: int = None):
    """
    Adiciona um novo padrão de busca abrangente.
    
    Args:
        pattern: Padrão de expressão regular para adicionar
        priority: Posição para inserir (0 = maior prioridade, None = anexar ao final)
    """
    if priority is not None and 0 <= priority < len(COMPREHENSIVE_PATTERNS):
        COMPREHENSIVE_PATTERNS.insert(priority, pattern)
    else:
        COMPREHENSIVE_PATTERNS.append(pattern)
    print(f"Padrão abrangente adicionado: {pattern}")

def add_term_extraction_pattern(pattern: str, capture_group_index: int = 0):
    """
    Adiciona um novo padrão para extrair termos de busca.
    
    Args:
        pattern: Padrão de expressão regular para adicionar
        capture_group_index: Índice do grupo de captura que contém o termo de busca (baseado em 0)
    """
    TERM_EXTRACTION_PATTERNS.append((pattern, capture_group_index))
    print(f"Padrão de extração de termo adicionado: {pattern} (grupo de captura {capture_group_index})")

def get_comprehensive_patterns() -> List[str]:
    """Obtém todos os padrões de busca abrangente atuais."""
    return COMPREHENSIVE_PATTERNS.copy()

def get_term_extraction_patterns() -> List[tuple]:
    """Obtém todos os padrões de extração de termos atuais."""
    return TERM_EXTRACTION_PATTERNS.copy()