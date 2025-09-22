from docx import Document
import pandas as pd
import pdfplumber
import math
import os
from config import FILE_READER_CONFIG
from logger import log_file_readers_error, log_file_readers_warning, log_file_readers_info, log_file_readers_success, log_file_readers_debug

# Configuration
verbose = FILE_READER_CONFIG.get("verbose", False)

def log_verbose(level: str, message: str):
    """log de qualquer nível dependendo do verbose"""
    if verbose:
        if level == "info":
            log_file_readers_info(message)
        elif level == "debug":
            log_file_readers_debug(message)
        elif level == "warning":
            log_file_readers_warning(message)
        elif level == "error":
            log_file_readers_error(message)
        elif level == "success":
            log_file_readers_success(message)

def log_always(level: str, message: str):
    """log de qualquer nível sem depender do verbose"""
    if level == "info":
        log_file_readers_info(message)
    elif level == "debug":
        log_file_readers_debug(message)
    elif level == "warning":
        log_file_readers_warning(message)
    elif level == "error":
        log_file_readers_error(message)
    elif level == "success":
        log_file_readers_success(message)

def read_md(file_path: str) -> str:
    """Lê arquivos .md"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        # print(f"Erro lendo {file_path}: {e}")
        log_always("error", f"Erro lendo {file_path}: {e}")
        return ""

def read_txt(file_path: str) -> str:
    """Lê arquivos .txt"""
    try:
        # print(f"Tentando ler arquivo TXT: {file_path}")
        log_verbose("info", f"Tentando ler arquivo TXT: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Add filename to the text for better searchability
        filename = os.path.basename(file_path)
        text = f"Arquivo: {filename}\n\n{content}"
        
        # print(f"Arquivo TXT lido com sucesso: {len(text)} caracteres")
        log_verbose("success", f"Arquivo TXT lido com sucesso: {len(text)} caracteres")
        return text
    except Exception as e:
        # print(f"Erro lendo arquivo TXT {file_path}: {e}")
        # import traceback
        # traceback.print_exc()
        log_always("error", f"Erro lendo arquivo TXT {file_path}: {e}")
        return ""

def read_docx(file_path: str) -> str:
    """Lê arquivos .docx"""
    try:
        # print(f"Tentando ler arquivo DOCX: {file_path}")
        log_verbose("info", f"Tentando ler arquivo DOCX: {file_path}")
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        # print(f"Arquivo DOCX lido com sucesso: {len(text)} caracteres")
        log_verbose("success", f"Arquivo DOCX lido com sucesso: {len(text)} caracteres")
        return text
    except Exception as e:
        # print(f"Erro lendo arquivo DOCX {file_path}: {e}")
        # import traceback
        # traceback.print_exc()
        log_always("error", f"Erro lendo arquivo DOCX {file_path}: {e}")
        return ""

def read_xlsx(file_path: str) -> str:
    """Lê arquivos .xlsx usando pandas com serialização linha por linha"""
    try:
        # print(f"Tentando ler arquivo XLSX: {file_path}")
        log_verbose("info", f"Tentando ler arquivo XLSX: {file_path}")
        
        # Ler todas as planilhas do arquivo Excel
        excel_file = pd.ExcelFile(file_path)
        all_text = []
        
        for sheet_name in excel_file.sheet_names:
            # print(f"Processando planilha: {sheet_name}")
            log_verbose("debug", f"Processando planilha: {sheet_name}")
            
            # Ler a planilha
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Remover linhas completamente vazias
            df = df.dropna(how='all')
            
            if df.empty:
                # print(f"Planilha '{sheet_name}' está vazia, pulando...")
                log_verbose("debug", f"Planilha '{sheet_name}' está vazia, pulando...")
                continue
            
            # Adicionar cabeçalho da planilha
            sheet_text = [f"Planilha: {sheet_name}"]
            
            # Processar cada linha como uma "frase" com todos os valores
            for index, row in df.iterrows():
                # Converter todos os valores da linha para string, tratando NaN
                row_values = []
                for value in row:
                    if pd.isna(value):
                        row_values.append("")
                    elif isinstance(value, (int, float)):
                        # Para números, usar formatação mais limpa
                        if isinstance(value, float) and value.is_integer():
                            row_values.append(str(int(value)))
                        else:
                            row_values.append(str(value))
                    else:
                        row_values.append(str(value))
                
                # Criar uma "frase" com todos os valores da linha
                row_sentence = " | ".join(row_values)
                
                # Adicionar informações de contexto se necessário
                if len(row_values) > 1:
                    row_sentence = f"Linha {index + 1}: {row_sentence}"
                else:
                    row_sentence = f"Linha {index + 1}: {row_sentence}"
                
                sheet_text.append(row_sentence)
            
            # Adicionar separador entre planilhas
            all_text.extend(sheet_text)
            all_text.append("---")  # Separador entre planilhas
        
        # Remover o último separador se existir
        if all_text and all_text[-1] == "---":
            all_text.pop()
        
        final_text = "\n".join(all_text)
        # print(f"Arquivo XLSX lido com sucesso: {len(final_text)} caracteres, {len(excel_file.sheet_names)} planilhas")
        log_verbose("success", f"Arquivo XLSX lido com sucesso: {len(final_text)} caracteres, {len(excel_file.sheet_names)} planilhas")
        return final_text
        
    except Exception as e:
        # print(f"Erro lendo arquivo XLSX {file_path}: {e}")
        # import traceback
        # traceback.print_exc()
        log_always("error", f"Erro lendo arquivo XLSX {file_path}: {e}")
        return ""

def read_pdf(file_path: str) -> str:
    """Lê arquivos .pdf usando pdfplumber (texto + tabelas em Markdown)"""
    try:
        # print(f"Tentando ler arquivo PDF: {file_path}")
        log_verbose("info", f"Tentando ler arquivo PDF: {file_path}")
        text = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_content = []
                
                # Extrair texto
                page_text = page.extract_text()
                if page_text:
                    page_content.append(f"### Texto da Página {i+1}\n\n{page_text.strip()}")
                
                # Extrair tabelas
                tables = page.extract_tables()
                if tables:
                    for t_index, table in enumerate(tables, start=1):
                        if not table:
                            continue
                        # Converte tabela em Markdown
                        md_table = []
                        header = table[0]
                        if header:
                            md_table.append("| " + " | ".join([h if h else "" for h in header]) + " |")
                            md_table.append("| " + " | ".join(["---"] * len(header)) + " |")
                        for row in table[1:]:
                            row_clean = [cell if cell is not None else "" for cell in row]
                            md_table.append("| " + " | ".join(row_clean) + " |")
                        
                        table_md = "\n".join(md_table)
                        page_content.append(f"### Tabela {t_index} da Página {i+1}\n\n{table_md}")
                
                if page_content:
                    text.append("\n\n".join(page_content))
        
        final_text = "\n\n---\n\n".join(text)
        # print(f"Arquivo PDF lido com sucesso: {len(final_text)} caracteres, {len(pdf.pages)} páginas")
        log_verbose("success", f"Arquivo PDF lido com sucesso: {len(final_text)} caracteres, {len(pdf.pages)} páginas")
        return final_text
    except Exception as e:
        # print(f"Erro lendo arquivo PDF {file_path}: {e}")
        # import traceback
        # traceback.print_exc()
        log_always("error", f"Erro lendo arquivo PDF {file_path}: {e}")
        return ""

def read_file(file_path: str) -> str:
    """Lê arquivos suportados (.md, .txt, .docx, .xlsx, .pdf)"""
    ext = os.path.splitext(file_path)[1].lower()
    # print(f"Lendo arquivo: {file_path} (extensão: {ext})")
    log_verbose("info", f"Lendo arquivo: {file_path} (extensão: {ext})")
    
    if ext == ".md":
        return read_md(file_path)
    elif ext == ".txt":
        return read_txt(file_path)
    elif ext == ".docx":
        return read_docx(file_path)
    elif ext == ".xlsx":
        return read_xlsx(file_path)
    elif ext == ".pdf":
        return read_pdf(file_path)
    else:
        # print(f"Extensão não suportada: {ext}")
        log_always("warning", f"Extensão não suportada: {ext}")
        return ""
