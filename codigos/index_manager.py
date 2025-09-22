import os
import faiss
import pickle
import numpy as np
import hashlib
import time
import threading
from datetime import datetime, timedelta
from openai import OpenAI
from typing import List, Dict, Optional, Tuple
from file_readers import read_file
from config import INDEX_CONFIG, OPENAI_API_KEY, EMBEDDING_MODEL
from logger import log_index_manager_error, log_index_manager_warning, log_index_manager_info, log_index_manager_success, log_index_manager_debug

class IndexManager:
    def __init__(self, vault_path: str = None, index_path: str = None, enable_usage_tracking: bool = None, verbose: bool = None):
        # Usar valores de configuração com alternativas (fallbacks)
        self.vault_path = vault_path or INDEX_CONFIG["vault_path"]
        self.index_path = index_path or INDEX_CONFIG["index_path"]
        self.index = None
        # Manter apenas metadados essenciais em memória para buscas rápidas
        self.chunk_hashes = []  # Apenas referências de hash para o índice FAISS
        self.chunk_ids = []  # IDs de banco de dados para os fragmentos
        
        self.last_update = None
        self.is_updating = False
        self.enable_usage_tracking = enable_usage_tracking if enable_usage_tracking is not None else INDEX_CONFIG["enable_usage_tracking"]
        self.verbose = verbose if verbose is not None else INDEX_CONFIG["verbose"]
        
        # Parâmetros de fragmentação (chunking)
        self.max_chunk_size = INDEX_CONFIG["max_chunk_size"]
        self.chunk_overlap = INDEX_CONFIG["chunk_overlap"]
        self.min_chunk_size = INDEX_CONFIG["min_chunk_size"]
        
        # Configurações de cache
        self.max_cache_size = 1000  # Máximo de fragmentos a manter no cache de memória
        self.memory_cache = {}  # Cache em memória para fragmentos acessados com frequência
        
        # Definir caminhos excluídos (relativos a vault_path)
        # Estas pastas e seus conteúdos serão ignorados
        self.excluded_paths = set() # Alterado de lista para conjunto para buscas mais rápidas
        
        # Inicializar cliente OpenAI
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Carregar ou criar índice
        self.load_or_create_index()
        
        # Carregar caminhos excluídos do banco de dados
        self._load_excluded_paths_from_db()
        
        # Iniciar thread de atualização automática
        self.start_auto_update()
    
    def log_verbose(self, level: str, message: str):
        """Registrar mensagem apenas se o modo verboso estiver ativado"""
        if self.verbose:
            if level == "info":
                log_index_manager_info(message)
            elif level == "debug":
                log_index_manager_debug(message)
            elif level == "warning":
                log_index_manager_warning(message)
            elif level == "error":
                log_index_manager_error(message)
            elif level == "success":
                log_index_manager_success(message)

    def log_always(self, level: str, message: str):
        """Registrar mensagem independentemente do modo verboso (para erros/infos importantes)"""
        if level == "info":
            log_index_manager_info(message)
        elif level == "debug":
            log_index_manager_debug(message)
        elif level == "warning":
            log_index_manager_warning(message)
        elif level == "error":
            log_index_manager_error(message)
        elif level == "success":
            log_index_manager_success(message)
    
    def _load_excluded_paths_from_db(self):
        """Carregar caminhos excluídos do banco de dados"""
        try:
            from database import ExcludedPath, db
            from flask import current_app
            
            # Tentar primeiro o contexto do app Flask
            try:
                app = current_app._get_current_object()
                # Inicializar caminhos padrão se não existirem
                ExcludedPath.initialize_default_paths()
                # Carregar todos os caminhos excluídos
                self.excluded_paths = ExcludedPath.get_all_paths()
                if self.verbose:
                    self.log_verbose("info", f"Carregados {len(self.excluded_paths)} caminhos excluídos do banco de dados")
                    
            except RuntimeError:
                # Sem contexto Flask, tentar conexão autônoma
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para o arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        # Usar padrões da configuração como fallback
                        self.excluded_paths = set(INDEX_CONFIG.get("excluded_paths", {}))
                        return
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Inicializar caminhos padrão se não existirem
                    if session.query(ExcludedPath).count() == 0:
                        # Obter caminhos padrão da configuração
                        config_paths = INDEX_CONFIG.get("excluded_paths", {})
                        default_paths = []
                        
                        # Converter caminhos de configuração para tuplas com descrições
                        for path in config_paths:
                            # Gerar descrição baseada no caminho
                            if path == '.obsidian':
                                description = 'Obsidian configuration folder'
                            elif path == '.git':
                                description = 'Git repository folder'
                            elif path == '.vscode':
                                description = 'VS Code settings'
                            elif path == 'node_modules':
                                description = 'Node.js dependencies'
                            elif path == '__pycache__':
                                description = 'Python cache'
                            elif path == '.DS_Store':
                                description = 'macOS system files'
                            elif path == 'Thumbs.db':
                                description = 'Windows thumbnail cache'
                            elif path == 'desktop.ini':
                                description = 'Windows desktop settings'
                            else:
                                description = f'Excluded path: {path}'
                            
                            default_paths.append((path, description))
                        
                        for path, description in default_paths:
                            excluded_path = ExcludedPath(
                                path=path,
                                description=description,
                                created_by='system'
                            )
                            session.add(excluded_path)
                        
                        session.commit()
                        if self.verbose:
                            self.log_verbose("success", f"Inicializados {len(default_paths)} caminhos excluídos padrão da configuração")
                    
                    # Carregar todos os caminhos excluídos
                    paths = session.query(ExcludedPath).all()
                    self.excluded_paths = {path.path for path in paths}
                    session.close()
                    
                    if self.verbose:
                        self.log_verbose("info", f"Carregados {len(self.excluded_paths)} caminhos excluídos do banco de dados (autônomo)")
                        
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro no carregamento autônomo de caminhos excluídos: {e}")
                    # Usar padrões da configuração como fallback
                    self.excluded_paths = set(INDEX_CONFIG.get("excluded_paths", {}))
            
        except Exception as e:
            if self.verbose:
                self.log_always("error", f"Erro ao carregar caminhos excluídos do banco de dados: {e}")
            # Usar padrões da configuração como fallback
            self.excluded_paths = set(INDEX_CONFIG.get("excluded_paths", {}))
    
    def chunk_text(self, text: str, file_path: str) -> List[Tuple[str, Dict]]:
        """
        Dividir texto em fragmentos sobrepostos para melhor processamento.
        Retorna lista de tuplas (chunk_text, chunk_metadata).
        """
        if len(text) <= self.max_chunk_size:
            # Não é necessário fragmentar
            if self.verbose:
                self.log_verbose("info", f"Comprimento do texto {len(text)} <= max_chunk_size {self.max_chunk_size}, não é necessário fragmentar")
            return [(text, {
                'chunk_id': 0,
                'total_chunks': 1,
                'start_char': 0,
                'end_char': len(text),
                'file_path': file_path
            })]
        
        chunks = []
        start = 0
        chunk_id = 0
        max_iterations = len(text) + 1000  # Limite de segurança para evitar loops infinitos
        iteration_count = 0
        
        if self.verbose:
            self.log_verbose("info", f"Fragmentando texto de {len(text)} caracteres com max_chunk_size {self.max_chunk_size}")
        
        while start < len(text) and iteration_count < max_iterations:
            iteration_count += 1
            # Calcular posição final para este fragmento
            end = min(start + self.max_chunk_size, len(text))
            
            # Se não for o último fragmento, tentar quebrar em limite de sentença
            if end < len(text):
                # Buscar finais de sentença nos últimos 500 caracteres do fragmento
                search_start = max(start, end - 500)
                search_text = text[search_start:end]
                
                # Encontrar o último final de sentença (., !, ?) seguido por espaço em branco
                sentence_end = -1
                for i in range(len(search_text) - 1, -1, -1):
                    if search_text[i] in '.!?' and i + 1 < len(search_text) and search_text[i + 1].isspace():
                        sentence_end = search_start + i + 1
                        break
                
                # Se for encontrado um bom limite de sentença, usar
                if sentence_end > start and sentence_end < end:
                    end = sentence_end
            
            # Extrair o fragmento
            chunk_text = text[start:end].strip()
            
            # Adicionar apenas fragmentos não vazios
            if chunk_text:
                chunk_metadata = {
                    'chunk_id': chunk_id,
                    'total_chunks': -1,  # Será atualizado após todos os fragmentos serem criados
                    'start_char': start,
                    'end_char': end,
                    'file_path': file_path
                }
                chunks.append((chunk_text, chunk_metadata))
                chunk_id += 1
                
                if self.verbose:
                    self.log_verbose("debug", f"  Fragmento {chunk_id}: {len(chunk_text)} caracteres ({start}-{end})")
            
            # Ir para o próximo fragmento, considerando a sobreposição
            # Garantir avanço para evitar loops infinitos
            new_start = end  # Começar do fim do fragmento atual
            
            # Aplicar sobreposição, mas garantindo progresso
            if new_start > start:  # Aplicar apenas se houve progresso
                new_start = max(new_start - self.chunk_overlap, start + 1)
            
            # Forçar avanço se a sobreposição causar retrocesso
            if new_start <= start:
                new_start = start + 1
            
            # Segurança adicional: se estiver perto do fim e o restante for pequeno, encerrar
            remaining_text = len(text) - new_start
            if remaining_text <= self.chunk_overlap:
                break
            
            # Segurança adicional: se não houver progresso suficiente, forçar avanço
            if new_start <= start:
                new_start = start + self.max_chunk_size // 2  # Avançar metade do tamanho do fragmento
                self.log_always("warning", f"Forçando progresso de {start} para {new_start}")
            
            start = new_start
            
            # Saída de debug para progresso do loop
            if self.verbose and iteration_count % 100 == 0:
                self.log_verbose("debug", f"  Iteração do loop {iteration_count}: início={start}, fim={end}, progresso={start}/{len(text)} ({start/len(text)*100:.1f}%)")
            
            # Verificação de segurança para evitar loops infinitos
            if start >= len(text):
                break
            
            # Segurança adicional: interromper se não houver progresso suficiente
            if iteration_count > 100 and start < len(text) * 0.1:
                self.log_always("warning", f"Progresso insuficiente após {iteration_count} iterações. Interrompendo loop para evitar loop infinito.")
                self.log_always("warning", f"Posição atual: {start}/{len(text)} ({start/len(text)*100:.1f}%)")
                break
        
        # Verificar se o limite de iterações foi atingido (potencial loop infinito)
        if iteration_count >= max_iterations:
            self.log_always("warning", f"Limite de iteração atingido ({max_iterations}) durante fragmentação. Isso pode indicar um loop infinito.")
            self.log_always("warning", f"Comprimento do texto: {len(text)}, fragmentos criados: {len(chunks)}, posição inicial final: {start}")
        
        # Mesclar fragmentos pequenos com os anteriores para evitar trechos minúsculos
        if len(chunks) > 1:
            merged_chunks = []
            i = 0
            while i < len(chunks):
                chunk_text, metadata = chunks[i]
                
                # Se o fragmento for muito pequeno e não o primeiro, mesclar com o anterior
                if len(chunk_text) < self.min_chunk_size and i > 0:
                    prev_chunk_text, prev_metadata = merged_chunks[-1]
                    # Mesclar os fragmentos
                    merged_text = prev_chunk_text + " " + chunk_text
                    merged_metadata = prev_metadata.copy()
                    merged_metadata['end_char'] = metadata['end_char']
                    merged_chunks[-1] = (merged_text, merged_metadata)
                    if self.verbose:
                        self.log_verbose("debug", f"  Fragmento pequeno {i} ({len(chunk_text)} chars) mesclado com fragmento anterior")
                else:
                    merged_chunks.append((chunk_text, metadata))
                i += 1
            
            chunks = merged_chunks
            if self.verbose:
                self.log_verbose("info", f"  Após mesclagem: {len(chunks)} fragmentos")
        
        # Atualizar total_chunks para todos os fragmentos
        for chunk_text, metadata in chunks:
            metadata['total_chunks'] = len(chunks)
        
        # Verificação final de segurança: garantir que nenhum fragmento exceda o tamanho máximo
        oversized_chunks = [i for i, (chunk_text, _) in enumerate(chunks) if len(chunk_text) > self.max_chunk_size]
        if oversized_chunks:
            self.log_always("warning", f"Encontrados {len(oversized_chunks)} fragmentos grandes demais, truncando-os")
            for i in oversized_chunks:
                chunk_text, metadata = chunks[i]
                if len(chunk_text) > self.max_chunk_size:
                    chunks[i] = (chunk_text[:self.max_chunk_size], metadata)
                    self.log_verbose("warning", f"  Fragmento {i} truncado de {len(chunk_text)} para {self.max_chunk_size} caracteres")
        
        if self.verbose:
            self.log_verbose("info", f"Dividido {os.path.basename(file_path)} em {len(chunks)} fragmentos")
        
        return chunks
    
    def embed_text(self, text: str, file_path: str = None, operation: str = "create") -> Optional[np.ndarray]:
        """Criar embedding para o texto usando a API da OpenAI"""
        try:
            # Verificação de segurança: garantir que o texto não exceda o limite de tokens
            # A maioria dos modelos de embedding tem limite de 8k tokens; usar estimativa conservadora
            max_chars = 6000  # Estimativa conservadora para 8k tokens
            if len(text) > max_chars:
                self.log_always("warning", f"Comprimento do texto {len(text)} excede o limite seguro {max_chars}, truncando")
                text = text[:max_chars]
            
            if self.verbose:
                self.log_verbose("info", f"Criando embedding para texto de {len(text)} caracteres")
            
            resp = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            
            # Rastrear uso de tokens para embeddings
            if hasattr(resp, 'usage') and resp.usage and hasattr(resp.usage, 'total_tokens'):
                tokens_used = resp.usage.total_tokens
            else:
                # Estimar tokens se info de uso não estiver disponível (alguns modelos não fornecem sempre)
                tokens_used = len(text) // 4  # Estimativa: 1 token ≈ 4 caracteres
            
            # Salvar uso no banco se file_path for fornecido
            if file_path and self.enable_usage_tracking:
                self._track_embedding_usage(file_path, len(text), tokens_used, operation)
            
            return np.array(resp.data[0].embedding, dtype=np.float32)
        except Exception as e:
            self.log_always("error", f"Erro ao criar embedding: {e}")
            return None
    
    def _track_embedding_usage(self, file_path: str, text_length: int, tokens_used: int, operation: str):
        """Rastrear o uso de embeddings no banco de dados"""
        if not self.enable_usage_tracking:
            return
            
        try:
            # Tentar usar primeiro o contexto do app Flask
            try:
                from flask import current_app
                from database import db, IndexEmbeddingUsage
                
                app = current_app._get_current_object()
                
                usage = IndexEmbeddingUsage(
                    file_path=file_path,
                    model=EMBEDDING_MODEL,
                    text_length=text_length,
                    tokens_used=tokens_used,
                    operation=operation
                )
                
                db.session.add(usage)
                db.session.commit()
                if self.verbose:
                    self.log_verbose("info", f"Uso de embedding rastreado: {tokens_used} tokens para {os.path.basename(file_path)} ({operation})")
                    
            except RuntimeError:
                # Sem contexto Flask, tentar criar conexão autônoma com o banco
                if self.verbose:
                    self.log_verbose("info", f"Sem contexto Flask, tentando conexão autônoma com banco de dados para {os.path.basename(file_path)}")
                
                try:
                    # Importar componentes do banco de dados
                    from database import IndexEmbeddingUsage
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho do banco pelo ambiente ou usar padrão
                    db_path = os.environ.get('DATABASE_URL', 'instance/app.db')
                    if not db_path.startswith('sqlite:///'):
                        db_path = f'sqlite:///{db_path}'
                    
                    # Criar engine e sessão
                    engine = create_engine(db_path)
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Criar registro de uso
                    usage = IndexEmbeddingUsage(
                        file_path=file_path,
                        model=EMBEDDING_MODEL,
                        text_length=text_length,
                        tokens_used=tokens_used,
                        operation=operation
                    )
                    
                    session.add(usage)
                    session.commit()
                    session.close()
                    
                    if self.verbose:
                        self.log_verbose("info", f"Uso de embedding rastreado (autônomo): {tokens_used} tokens para {os.path.basename(file_path)} ({operation})")
                        
                except Exception as standalone_error:
                    self.log_always("error", f"Erro no rastreamento autônomo de uso: {standalone_error}")
                    # Não falhar a operação principal se o rastreamento autônomo falhar
            
        except Exception as e:
            self.log_always("error", f"Erro ao rastrear uso de embedding: {e}")
            # Não falhar a operação principal se o rastreamento falhar
    
    def _get_file_metadata_from_db(self, file_path: str) -> dict:
        """Obter metadados do arquivo no banco de dados"""
        try:
            from database import FileMetadata, db
            from flask import current_app
            
            # Tentar primeiro o contexto do app Flask
            try:
                app = current_app._get_current_object()
                metadata = FileMetadata.get_by_file_path(file_path)
                if metadata:
                    return {
                        'mtime': metadata.mtime,
                        'size': metadata.size,
                        'hash': metadata.hash,
                        'last_checked': metadata.last_checked
                    }
            except RuntimeError:
                # Sem contexto Flask, tentar conexão autônoma
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para o arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return {}
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    metadata = session.query(FileMetadata).filter_by(file_path=file_path).first()
                    session.close()
                    
                    if metadata:
                        return {
                            'mtime': metadata.mtime,
                            'size': metadata.size,
                            'hash': metadata.hash,
                            'last_checked': metadata.last_checked
                        }
                except Exception as e:
                    self.log_always("error", f"Erro na busca autônoma de metadados: {e}")
            
        except Exception as e:
            self.log_always("error", f"Erro ao obter metadados do arquivo do banco de dados: {e}")
        
        return {}
    
    def _save_file_metadata_to_db(self, file_path: str, mtime: float, size: int, file_hash: str):
        """Salvar metadados do arquivo no banco de dados"""
        try:
            from database import FileMetadata, db
            from flask import current_app
            
            # Tentar primeiro o contexto do app Flask
            try:
                app = current_app._get_current_object()
                FileMetadata.update_or_create(file_path, mtime, size, file_hash)
                db.session.commit()
                if self.verbose:
                    self.log_verbose("info", f"Metadados salvos no banco de dados para {os.path.basename(file_path)}")
                    
            except RuntimeError:
                # Sem contexto Flask, tentar conexão autônoma
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para o arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Verificar se o registro existe
                    existing = session.query(FileMetadata).filter_by(file_path=file_path).first()
                    if existing:
                        # Atualizar registro existente
                        existing.mtime = mtime
                        existing.size = size
                        existing.hash = file_hash
                        existing.last_checked = datetime.utcnow()
                    else:
                        # Criar novo registro
                        new_metadata = FileMetadata(
                            file_path=file_path,
                            mtime=mtime,
                            size=size,
                            hash=file_hash
                        )
                        session.add(new_metadata)
                    
                    session.commit()
                    session.close()
                    
                    if self.verbose:
                        self.log_verbose("info", f"Metadados salvos no banco de dados (autônomo) para {os.path.basename(file_path)}")
                        
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro no salvamento autônomo de metadados: {e}")
                        import traceback
                        traceback.print_exc()
            
        except Exception as e:
            self.log_always("error", f"Erro ao salvar metadados do arquivo no banco de dados: {e}")
            #  não falhar na operação principal se o salvamento de metadados falhar
    
    def _cleanup_file_metadata_from_db(self, file_path: str):
        """Remover metadados do arquivo do banco de dados quando o arquivo for excluído"""
        try:
            from database import FileMetadata, db
            from flask import current_app
            
            # Tentar primeiro o contexto do app Flask
            try:
                app = current_app._get_current_object()
                metadata = FileMetadata.get_by_file_path(file_path)
                if metadata:
                    db.session.delete(metadata)
                    db.session.commit()
                    if self.verbose:
                        self.log_verbose("info", f"  Metadados limpos do banco de dados para arquivo removido: {os.path.basename(file_path)}")
                    
            except RuntimeError:
                # Sem contexto Flask, tentar conexão autônoma
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para o arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    metadata = session.query(FileMetadata).filter_by(file_path=file_path).first()
                    if metadata:
                        session.delete(metadata)
                        session.commit()
                        if self.verbose:
                            self.log_verbose("info", f"  Metadados limpos do banco de dados (autônomo) para arquivo removido: {os.path.basename(file_path)}")
                    
                    session.close()
                        
                except Exception as e:
                    self.log_always("error", f"Erro na limpeza autônoma de metadados: {e}")
            
        except Exception as e:
            self.log_always("error", f"Erro ao limpar metadados do arquivo do banco de dados: {e}")
            #  não falhar na operação principal se a limpeza de metadados falhar
    
    def hash_text(self, text: str) -> str:
        """Gerar hash para o texto para detectar alterações"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    def should_exclude_path(self, full_path: str) -> bool:
        """Verificar se um caminho deve ser excluído da indexação"""
        try:
            # Obter caminho relativo da raiz do vault
            rel_path = os.path.relpath(full_path, self.vault_path)
            
            # Verificar se alguma parte do caminho corresponde a padrões excluídos
            path_parts = rel_path.split(os.sep)
            
            for part in path_parts:
                if part in self.excluded_paths:
                    return True
                    
            return False
        except ValueError:
            # Se o caminho está fora do vault, excluir
            return True
    
    def load_or_create_index(self):
        """Carregar índice existente ou criar um novo"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.index = data["index"]
                    self.chunk_hashes = data.get("chunk_hashes", []) # carega o hash dos fragmentos
                    self.chunk_ids = data.get("chunk_ids", []) # carrega os ids dos fragmentos
                    self.last_update = data.get("last_update")
                    if self.verbose:
                        # print(f"FAISS index loaded with {len(self.chunk_hashes)} chunks")
                        self.log_verbose("info", f"Índice FAISS carregado com {len(self.chunk_hashes)} fragmentos")
            except Exception as e:
                # print(f"Error loading index: {e}")
                self.log_always("error", f"Erro ao carregar índice: {e}")
                self.create_new_index()
        else:
            self.create_new_index()
    
    def create_new_index(self):
        """Criar novo índice FAISS do zero"""
        self.log_always("info", "Criando novo índice FAISS...")
        self.chunk_hashes = [] # Inicializar para novo índice
        self.chunk_ids = [] # Inicializar para novo índice
        
        if not os.path.exists(self.vault_path):
            self.log_always("error", f"Caminho do vault {self.vault_path} não existe")
            return
        
        embeddings = []
        # Recursivamente escanear todos os subdiretórios para arquivos markdown
        for root, dirs, files in os.walk(self.vault_path):
            # Pular diretórios excluídos
            if self.should_exclude_path(root):
                self.log_verbose("info", f"Pulando diretório excluído: {root}")
                continue
                
            for file in files:
                if file.endswith(".md") or file.endswith(".txt") or file.endswith(".docx") or file.endswith(".xlsx") or file.endswith(".pdf"):
                    file_path = os.path.join(root, file)
                    
                    # Verificar novamente se o caminho do arquivo não está excluído
                    if self.should_exclude_path(file_path):
                        self.log_verbose("info", f"Pulando arquivo excluído: {file_path}")
                        continue
                        
                    try:
                        # Usar o módulo file_readers para ler diferentes formatos de arquivo
                        text = read_file(file_path)
                        if text.strip():  # Processar apenas arquivos não vazios
                            # Dividir texto em fragmentos
                            chunks = self.chunk_text(text, file_path)
                            for chunk_text, chunk_meta in chunks:
                                # Salvar fragmento no banco de dados
                                chunk_hash = self.hash_text(chunk_text)
                                chunk_id = self._save_chunk_to_db(chunk_text, file_path, chunk_meta, chunk_hash)
                                if chunk_id is not None:
                                    self.chunk_hashes.append(chunk_hash)
                                    self.chunk_ids.append(chunk_id)
                                    embedding = self.embed_text(chunk_text, file_path, "create")
                                    if embedding is not None:
                                        embeddings.append(embedding)
                                    else:
                                        # Remover o fragmento se o embedding falhar
                                        self._delete_chunk_from_db(chunk_id)
                                        self.chunk_hashes.pop()
                                        self.chunk_ids.pop()
                                else:
                                    self.log_always("error", f"Falha ao salvar fragmento para {os.path.basename(file_path)}")
                    except Exception as e:
                        self.log_always("error", f"Erro ao processar arquivo {file_path}: {e}")
        
        if embeddings:
            dim = len(embeddings[0])
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(np.array(embeddings))
            self.save_index()
            self.log_always("success", f"Novo índice FAISS criado com {len(self.chunk_hashes)} fragmentos de {self.vault_path} e subdiretórios")
            
            # Sync document metadata to database after creating index
            if self.verbose:
                self.log_verbose("info", "Sincronizando metadados de documentos com banco de dados...")
            self._sync_document_metadata_to_db()
        else:
            self.log_always("warning", "Nenhum documento válido encontrado para criar índice")
    
    def update_index(self):
        """Atualizar o índice incrementalmente com arquivos novos/modificados"""
        if self.is_updating:
            self.log_verbose("info", "Atualização já em andamento, pulando...")
            return
        
        self.is_updating = True
        try:
            if not os.path.exists(self.vault_path):
                self.log_always("error", f"Caminho do vault {self.vault_path} não existe")
                return
            
            changes = {
                'added': [],
                'modified': [],
                'removed': [],
                'unchanged': []
            }
            
            current_files = set()
            
            # Escanear recursivamente todos os subdiretórios por arquivos suportados
            if self.verbose:
                self.log_verbose("info", f"Escaneando diretório: {self.vault_path}")
            
            for root, dirs, files in os.walk(self.vault_path):
                # Pular diretórios excluídos
                if self.should_exclude_path(root):
                    if self.verbose:
                        self.log_verbose("info", f"Pulando diretório excluído: {root}")
                    continue
                
                # Filtrar arquivos suportados
                supported_files = [f for f in files if f.endswith(".md") or f.endswith(".txt") or f.endswith(".docx") or f.endswith(".xlsx") or f.endswith(".pdf")]
                if self.verbose and supported_files:
                    self.log_verbose("info", f"Encontrados {len(supported_files)} arquivos suportados em {root}: {supported_files}")
                
                for file in supported_files:
                    
                    file_path = os.path.join(root, file)
                    
                    # Pular arquivos excluídos
                    if self.should_exclude_path(file_path):
                        continue
                    
                    current_files.add(file_path)
                    
                    try:
                        # Verificar primeiro a data de modificação e tamanho do arquivo (verificação rápida)
                        stat = os.stat(file_path)
                        file_mtime = stat.st_mtime
                        file_size = stat.st_size
                        
                        # Verificar se este arquivo existe no nosso índice consultando o banco de dados
                        file_exists = self._file_exists_in_index(file_path)
                        
                        if not file_exists:
                            # Novo arquivo - ler e adicionar todos os fragmentos
                            text = read_file(file_path)
                            if not text.strip():
                                if self.verbose:
                                    self.log_verbose("warning", f"Arquivo está vazio ou falhou ao ler: {file_path}")
                                continue
                            
                            if self.verbose:
                                self.log_verbose("info", f"Arquivo lido com sucesso: {file_path} ({len(text)} caracteres)")
                            
                            chunks = self.chunk_text(text, file_path)
                            changes['added'].append((file_path, chunks))
                            if self.verbose:
                                self.log_verbose("info", f"Adicionando: {os.path.basename(file_path)} ({len(chunks)} fragmentos)")
                        else:
                            # Verificar se o arquivo pode ter mudado usando a data de modificação e tamanho (verificação rápida)
                            # Obter fragmentos existentes para este arquivo do banco de dados
                            existing_chunks = self._get_chunks_for_file(file_path)
                            if existing_chunks:
                                # Obter metadados armazenados no banco de dados para comparação
                                stored_metadata = self._get_file_metadata_from_db(file_path)
                                
                                if self.verbose and stored_metadata:
                                    self.log_verbose("info", f"  Metadados recuperados do banco de dados para {os.path.basename(file_path)}: mtime={stored_metadata.get('mtime')}, size={stored_metadata.get('size')}")
                                elif self.verbose:
                                    self.log_verbose("info", f"  Nenhum metadado encontrado no banco de dados para {os.path.basename(file_path)}")
                                
                                # Verificação rápida: se a data de modificação e tamanho não mudaram, pular a leitura
                                if (stored_metadata.get('mtime') == file_mtime and 
                                    stored_metadata.get('size') == file_size):
                                    changes['unchanged'].append(file_path)
                                    if self.verbose:
                                        self.log_verbose("info", f"  Arquivo {os.path.basename(file_path)} inalterado (mtime/size correspondem)")
                                    continue
                                
                                # O arquivo pode ter mudado - ler e verificar hash
                                text = read_file(file_path)
                                if not text.strip():
                                    if self.verbose:
                                        self.log_verbose("warning", f"Arquivo está vazio ou falhou ao ler: {file_path}")
                                    continue
                                
                                if self.verbose:
                                    self.log_verbose("info", f"Arquivo lido com sucesso: {file_path} ({len(text)} caracteres)")
                                
                                full_file_hash = self.hash_text(text)

                                # Verificar se existe um hash armazenado para este arquivo
                                stored_hash = stored_metadata.get('hash')
                                
                                if stored_hash is None:
                                    # Primeira vez vendo este arquivo, salvar metadados e assumir inalterado
                                    if self.verbose:
                                        self.log_verbose("info", f"  Primeira vez processando {os.path.basename(file_path)}")
                                    self._save_file_metadata_to_db(file_path, file_mtime, file_size, full_file_hash)
                                    changes['unchanged'].append(file_path)
                                elif stored_hash == full_file_hash:
                                    # Hash do arquivo corresponde, não há mudança - atualizar metadados
                                    self._save_file_metadata_to_db(file_path, file_mtime, file_size, full_file_hash)
                                    changes['unchanged'].append(file_path)
                                    if self.verbose:
                                        self.log_verbose("info", f"  Arquivo {os.path.basename(file_path)} inalterado (hash corresponde)")
                                else:
                                    # Hash do arquivo mudou, o conteúdo realmente mudou
                                    chunks = self.chunk_text(text, file_path)
                                    changes['modified'].append((file_path, chunks))
                                    # Atualizar metadados armazenados
                                    self._save_file_metadata_to_db(file_path, file_mtime, file_size, full_file_hash)
                                    if self.verbose:
                                        self.log_verbose("info", f"Modificando: {os.path.basename(file_path)} ({len(chunks)} fragmentos) - hash alterado")
                    except Exception as e:
                        self.log_always("error", f"Erro ao processar arquivo {file_path}: {e}")
            
            # Encontrar arquivos removidos verificando quais arquivos no banco não estão mais em disco
            indexed_files = self._get_all_indexed_files()
            for file_path in indexed_files:
                if file_path not in current_files:
                    changes['removed'].append(file_path)
                    # Limpar metadados do banco para arquivo removido
                    self._cleanup_file_metadata_from_db(file_path)
                    if self.verbose:
                        self.log_verbose("info", f"Removendo: {os.path.basename(file_path)}")
            
            # Estratégia de atualização inteligente
            if changes['added'] or changes['removed']:
                # File count changed - need to rebuild
                if self.verbose:
                    self.log_verbose("info", f"Contagem de arquivos alterada ({len(changes['added'])} adicionados, {len(changes['removed'])} removidos) - reconstruindo índice")
                    self.log_verbose("info", f"Estado atual: {len(self.chunk_hashes)} fragmentos")
                self._apply_changes_and_rebuild(changes)
            elif changes['modified']:
                # Apenas conteúdo alterado - tentar atualização incremental
                if self.verbose:
                    self.log_verbose("info", f"Conteúdo alterado para {len(changes['modified'])} arquivos - tentando atualização incremental")
                self._apply_incremental_update(changes)
            else:
                if self.verbose:
                    self.log_verbose("info", "Nenhuma alteração detectada")
            
            self.last_update = datetime.now()
            
            # Sincronizar metadados de documentos com o banco de dados após atualização do índice
            if self.verbose:
                self.log_verbose("info", "Sincronizando metadados de documentos com banco de dados...")
            self._sync_document_metadata_to_db()
            
        except Exception as e:
            self.log_always("error", f"Erro ao atualizar índice: {e}")
        finally:
            self.is_updating = False
    
    def _apply_changes_and_rebuild(self, changes):
        """Aplicar alterações de arquivos e reconstruir o índice inteiro"""
        try:
            # Criar novas listas em vez de modificar as existentes para evitar problemas de índice
            new_chunk_hashes = []
            new_chunk_ids = []
            
            # Começar com fragmentos existentes que não serão modificados ou removidos
            files_to_remove = set(changes['removed'] + [fp for fp, _ in changes['modified']])
            
            # Remover fragmentos antigos do banco antes de adicionar novos
            for file_path in files_to_remove:
                self._remove_chunks_for_file(file_path)
            
            # Adicionar novos fragmentos de arquivos adicionados
            for file_path, chunks in changes['added']:
                for chunk_text, chunk_meta in chunks:
                    chunk_hash = self.hash_text(chunk_text)
                    chunk_id = self._save_chunk_to_db(chunk_text, file_path, chunk_meta, chunk_hash)
                    if chunk_id is not None:
                        new_chunk_hashes.append(chunk_hash)
                        new_chunk_ids.append(chunk_id)
                    else:
                        self.log_always("error", f"Falha ao salvar fragmento para {os.path.basename(file_path)} durante reconstrução")
            
            # Adicionar novos fragmentos de arquivos modificados
            for file_path, chunks in changes['modified']:
                for chunk_text, chunk_meta in chunks:
                    chunk_hash = self.hash_text(chunk_text)
                    chunk_id = self._save_chunk_to_db(chunk_text, file_path, chunk_meta, chunk_hash)
                    if chunk_id is not None:
                        new_chunk_hashes.append(chunk_hash)
                        new_chunk_ids.append(chunk_id)
                    else:
                        self.log_always("error", f"Falha ao salvar fragmento para {os.path.basename(file_path)} durante reconstrução")
            
            # Substituir as listas antigas pelas novas
            self.chunk_hashes = new_chunk_hashes
            self.chunk_ids = new_chunk_ids
            
            # Garantir consistência
            self._ensure_list_consistency()
            
            if self.verbose:
                self.log_verbose("info", f"Estruturas de dados reconstruídas: {len(self.chunk_hashes)} fragmentos")
            
            # Reconstruir o índice inteiro
            self.rebuild_index()
            self.save_index()
            self.log_always("success", "Índice reconstruído com sucesso")
            
        except Exception as e:
            self.log_always("error", f"Erro em _apply_changes_and_rebuild: {e}")
            # Se algo der errado, tentar recuperar fazendo uma reconstrução completa
            self.log_always("info", "Tentando recuperação de reconstrução completa...")
            self._full_rebuild_recovery()
    
    def _apply_incremental_update(self, changes):
        """Aplicar alterações de conteúdo incrementalmente sem reconstrução completa"""
        updated_count = 0
        
        for file_path, chunks in changes['modified']:
            try:
                # Adicionar novos fragmentos
                for chunk_text, chunk_meta in chunks:
                    chunk_hash = self.hash_text(chunk_text)
                    chunk_id = self._save_chunk_to_db(chunk_text, file_path, chunk_meta, chunk_hash)
                    if chunk_id is not None:
                        self.chunk_hashes.append(chunk_hash)
                        self.chunk_ids.append(chunk_id)
                
                updated_count += 1
            except Exception as e:
                self.log_always("error", f"Erro ao atualizar {os.path.basename(file_path)}: {e}")
        
        if updated_count > 0:
            # Garantir consistência após todas as atualizações
            self._ensure_list_consistency()
            # Precisamos reconstruir porque o FAISS não atualiza vetores individuais
            self.log_verbose("info", f"Reconstruindo índice para {updated_count} arquivos modificados")
            self.rebuild_index()
            self.save_index()
            self.log_verbose("success", "Atualização incremental concluída")
        else:
            self.log_verbose("info", "Nenhuma atualização bem-sucedida para aplicar")
    
    def _full_rebuild_recovery(self):
        """Método de recuperação quando a reconstrução normal falha"""
        try:
            self.log_always("info", "Iniciando recuperação de reconstrução completa...")
            # Limpar todas as estruturas de dados
            self.chunk_hashes = []
            self.chunk_ids = []
            
            # Recriar índice do zero
            self.create_new_index()
            self.log_always("success", "Recuperação de reconstrução completa concluída")
        except Exception as e:
            self.log_always("error", f"Recuperação de reconstrução completa falhou: {e}")
            # Último recurso: tentar carregar do índice salvo
            try:
                self.log_always("info", "Tentando carregar do índice salvo...")
                self.load_or_create_index()
            except Exception as load_error:
                self.log_always("error", f"Falha ao carregar índice salvo: {load_error}")
                self.log_always("error", "Gerenciador de índice está em estado inconsistente. Intervenção manual pode ser necessária.")
    
    def rebuild_index(self):
        """Reconstruir todo o índice FAISS a partir de todos os fragmentos no banco"""
        self.log_always("info", "Reconstruindo índice FAISS do banco de dados...")
        
        # Obter todos os fragmentos do banco de dados em vez de depender de self.chunk_hashes
        all_chunks = self._get_all_chunks_from_db()
        
        if not all_chunks:
            self.log_always("warning", "Nenhum fragmento encontrado no banco de dados para reconstrução")
            return
        
        self.log_verbose("info", f"Encontrados {len(all_chunks)} fragmentos no banco de dados, reconstruindo índice...")
        
        # Reconstruir listas chunk_hashes e chunk_ids a partir do banco de dados
        self.chunk_hashes = []
        self.chunk_ids = []
        embeddings = []
        
        for chunk_id, chunk_text, chunk_meta in all_chunks:
            if chunk_text is not None:
                # Gerar hash para este fragmento
                chunk_hash = self.hash_text(chunk_text)
                
                # Adicionar à nossas listas
                self.chunk_hashes.append(chunk_hash)
                self.chunk_ids.append(chunk_id)
                
                # Criar embedding
                file_path = chunk_meta.get('file_path')
                emb = self.embed_text(chunk_text, file_path, "rebuild")
                if emb is not None:
                    embeddings.append(emb)
                else:
                    self.log_always("error", f"Falha ao criar embedding do fragmento {chunk_id} durante reconstrução")
            else:
                self.log_always("error", f"Falha ao recuperar fragmento {chunk_id} para reconstrução")
        
        if embeddings:
            dim = len(embeddings[0])
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(np.array(embeddings))
            self.log_always("success", f"Índice FAISS reconstruído com {len(embeddings)} fragmentos")
        else:
            self.log_always("warning", "Nenhum embedding criado durante reconstrução")
    
    def save_index(self):
        """Salvar índice em arquivo"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        data = {
            "index": self.index,
            "chunk_hashes": self.chunk_hashes, # Salvar no arquivo de índice
            "chunk_ids": self.chunk_ids, # Salvar no arquivo de índice
            "last_update": self.last_update
        }
        with open(self.index_path, "wb") as f:
            pickle.dump(data, f)
    
    def search(self, query: str, k: int = 3) -> List[Dict]:
        """Buscar documentos similares e retornar informações dos fragmentos"""
        if self.index is None or not self.chunk_hashes:
            return []
        
        # Garantir consistência das listas antes de buscar
        if not self._ensure_list_consistency():
            self.log_always("warning", "Problemas de consistência de lista detectados durante busca")
        
        query_emb = self.embed_text(query)
        if query_emb is None:
            return []
        
        try:
            D, I = self.index.search(np.array([query_emb]), k)
            results = []
            for i, idx in enumerate(I[0]):
                if idx < len(self.chunk_hashes): 
                    chunk_id = self.chunk_ids[idx] # Obter o ID do fragmento da lista
                    chunk_text, chunk_meta = self._get_chunk_from_db(chunk_id) # Obter texto e metadados do fragmento do banco de dados
                    if chunk_text is not None:
                        result = {
                            'text': chunk_text,
                            'file_path': chunk_meta.get('file_path'),
                            'chunk_info': chunk_meta,
                            'similarity_score': float(D[0][i])
                        }
                        results.append(result)
                    else:
                        self.log_always("error", f"ID do fragmento {idx} não encontrado no BD durante busca")
            return results
        except Exception as e:
            self.log_always("error", f"Erro ao buscar no índice: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Obter estatísticas do índice"""
        # Garantir consistência das listas antes de obter estatísticas
        self._ensure_list_consistency()
        
            # Obter informações da estrutura de pastas
        folder_info = self.get_folder_structure()
        
            # Obter estatísticas de uso de embeddings
        embedding_stats = self.get_embedding_usage_stats()
        
            # Contar arquivos únicos do banco de dados
        unique_files = self._get_unique_file_count()
        
        return {
            "total_chunks": len(self.chunk_hashes),
            "unique_files": unique_files,
            "index_size": self.index.ntotal if self.index else 0,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "vault_path": self.vault_path,
            "folder_structure": folder_info,
            "excluded_paths": list(self.excluded_paths),
            "embedding_usage": embedding_stats,
            "chunking_info": {
                "max_chunk_size": self.max_chunk_size,
                "chunk_overlap": self.chunk_overlap
            }
        }
    
    def get_embedding_usage_stats(self) -> Dict:
        """Obter estatísticas sobre o uso de embeddings"""
        try:
            from database import IndexEmbeddingUsage, db
            from sqlalchemy import func
            
            # Verificar se estamos no contexto do app Flask
            try:
                from flask import current_app
                app = current_app._get_current_object()
            except RuntimeError:
                # Não no contexto do app, retornar estatísticas vazias
                self.log_verbose("info", "Nota: Pulando estatísticas de uso (sem contexto de aplicação)")
                return {
                    "total_tokens_used": 0,
                    "recent_tokens_used": 0,
                    "operations": []
                }
            
            # Obter total de uso
            total_usage = db.session.query(func.sum(IndexEmbeddingUsage.tokens_used)).scalar() or 0
            
            # Obter uso por operação
            operation_stats = db.session.query(
                IndexEmbeddingUsage.operation,
                func.count(IndexEmbeddingUsage.id).label('count'),
                func.sum(IndexEmbeddingUsage.tokens_used).label('total_tokens')
            ).group_by(IndexEmbeddingUsage.operation).all()
            
            # Obter uso recente (últimos 30 dias)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_usage = db.session.query(func.sum(IndexEmbeddingUsage.tokens_used)).filter(
                IndexEmbeddingUsage.created_at >= thirty_days_ago
            ).scalar() or 0
            
            return {
                "total_tokens_used": total_usage,
                "recent_tokens_used": recent_usage,
                "operations": [
                    {
                        "operation": op.operation,
                        "count": op.count,
                        "total_tokens": op.total_tokens or 0
                    }
                    for op in operation_stats
                ]
            }
            
        except Exception as e:
            self.log_always("error", f"Erro ao obter estatísticas de uso de embedding: {e}")
            return {
                "total_tokens_used": 0,
                "recent_tokens_used": 0,
                "operations": []
            }
    
    def add_excluded_path(self, path: str):
        """Adicionar um caminho à lista de exclusão"""
        self.excluded_paths.add(path)
        self.log_verbose("info", f"Caminho excluído adicionado: {path}")
    
    def remove_excluded_path(self, path: str):
        """Remover um caminho da lista de exclusão"""
        if path in self.excluded_paths:
            self.excluded_paths.remove(path)
            self.log_verbose("info", f"Caminho excluído removido: {path}")
        else:
            self.log_verbose("info", f"Caminho {path} não estava na lista de exclusão")
    
    def get_excluded_paths(self) -> set:
        """Obter os caminhos excluídos atuais"""
        return self.excluded_paths.copy()
    
    def test_usage_tracking(self, file_path: str = "test_file.md"):
        """Testar a funcionalidade de rastreamento de uso"""
        self.log_verbose("info", f"Testando rastreamento de uso para: {file_path}")
        self._track_embedding_usage(file_path, 1000, 250, "test")
        self.log_verbose("info", "Teste de rastreamento de uso concluído")
    
    def _ensure_list_consistency(self):
        """Garantir que todas as listas internas tenham o mesmo comprimento"""
        lengths = [len(self.chunk_hashes)] 
        if len(set(lengths)) != 1:
            min_length = min(lengths)
            self.log_always("warning", f"Incompatibilidade de comprimento de lista detectada: chunk_hashes={lengths[0]}")
            self.log_always("info", f"Truncando todas as listas para comprimento mínimo: {min_length}")
            
            # Truncar todas as listas para o comprimento mínimo
            self.chunk_hashes = self.chunk_hashes[:min_length]
            self.chunk_ids = self.chunk_ids[:min_length] 
            
            return False
        return True
    
    def get_folder_structure(self, use_cache: bool = True) -> Dict:
        """Obter informações sobre a estrutura de pastas monitorada"""
        if not os.path.exists(self.vault_path):
            return {"error": "Vault path does not exist"}
        
        # Tentar obter dados em cache do banco de dados primeiro
        if use_cache:
            try:
                from database import DocumentMetadata, db
                from flask import current_app
                
                try:
                    app = current_app._get_current_object()
                    cached_structure = DocumentMetadata.get_folder_structure()
                    if cached_structure and cached_structure.get('folders'):
                        # Adicionar informações de root path e full_path
                        cached_structure["root"] = self.vault_path
                        for folder in cached_structure["folders"]:
                            if folder["path"] == "Root":
                                folder["full_path"] = self.vault_path
                            else:
                                folder["full_path"] = os.path.join(self.vault_path, folder["path"])
                        return cached_structure
                        
                except RuntimeError:
                    # Não no contexto do app, tentar conexão standalone
                    try:
                        from sqlalchemy import create_engine
                        from sqlalchemy.orm import sessionmaker
                        
                        # Obter caminho absoluto para arquivo de banco de dados
                        db_path = os.path.abspath('instance/app.db')
                        if os.path.exists(db_path):
                            engine = create_engine(f'sqlite:///{db_path}')
                            Session = sessionmaker(bind=engine)
                            session = Session()
                            
                            # Obter estrutura em cache
                            documents = session.query(DocumentMetadata).filter_by(is_supported=True).all()
                            session.close()
                            
                            if documents:
                                # Construir estrutura a partir dos dados em cache
                                folders = {}
                                for doc in documents:
                                    folder_path = doc.folder_path
                                    if folder_path not in folders:
                                        folders[folder_path] = {
                                            'path': folder_path,
                                            'full_path': os.path.join(self.vault_path, folder_path) if folder_path != "Root" else self.vault_path,
                                            'files': 0,
                                            'supported_files': 0,
                                            'file_types': {'md': 0, 'txt': 0, 'docx': 0, 'xlsx': 0, 'pdf': 0}
                                        }
                                    
                                    folders[folder_path]['files'] += 1
                                    folders[folder_path]['supported_files'] += 1
                                    folders[folder_path]['file_types'][doc.file_type] += 1
                                
                                folder_list = list(folders.values())
                                folder_list.sort(key=lambda x: x['path'])
                                
                                total_files = sum(f['files'] for f in folder_list)
                                total_supported = sum(f['supported_files'] for f in folder_list)
                                total_file_types = {'md': 0, 'txt': 0, 'docx': 0, 'xlsx': 0, 'pdf': 0}
                                for folder in folder_list:
                                    for file_type, count in folder['file_types'].items():
                                        total_file_types[file_type] += count
                                
                                return {
                                    "root": self.vault_path,
                                    "folders": folder_list,
                                    "total_files": total_files,
                                    "supported_files": total_supported,
                                    "file_types": total_file_types
                                }
                    except Exception as e:
                        if self.verbose:
                            # print(f"Error accessing cached folder structure: {e}")
                            self.log_verbose("error", f"Erro ao acessar estrutura de pasta em cache: {e}")
                        
            except Exception as e:
                if self.verbose:
                    # print(f"Error getting cached folder structure: {e}")
                    self.log_verbose("error", f"Erro ao obter estrutura de pasta em cache: {e}")
        
        # Voltar para escaneamento do sistema de arquivos se o cache não estiver disponível ou solicitado
        return self._scan_folder_structure()
    
    def _scan_folder_structure(self) -> Dict:
        """Escanear o sistema de arquivos para montar a estrutura de pastas (fallback)"""
        structure = {
            "root": self.vault_path,
            "folders": [],
            "total_files": 0,
            "supported_files": 0,
            "file_types": {
                "md": 0,
                "txt": 0,
                "docx": 0,
                "xlsx": 0,
                "pdf": 0
            }
        }
        
        try:
            for root, dirs, files in os.walk(self.vault_path):
                # Pular diretórios excluídos
                if self.should_exclude_path(root):
                    continue
                    
                # Obter caminho relativo da raiz do vault
                rel_path = os.path.relpath(root, self.vault_path)
                if rel_path == ".":
                    rel_path = "Root"
                
                # Filtrar arquivos excluídos
                valid_files = [f for f in files if not self.should_exclude_path(os.path.join(root, f))]
                markdown_files = [f for f in valid_files if f.endswith('.md')]
                txt_files = [f for f in valid_files if f.endswith('.txt')]
                docx_files = [f for f in valid_files if f.endswith('.docx')]
                xlsx_files = [f for f in valid_files if f.endswith('.xlsx')]
                pdf_files = [f for f in valid_files if f.endswith('.pdf')]
                supported_files = markdown_files + txt_files + docx_files + xlsx_files + pdf_files
                
                folder_info = {
                    "path": rel_path,
                    "full_path": root,
                    "files": len(valid_files),
                    "supported_files": len(supported_files),
                    "file_types": {
                        "md": len(markdown_files),
                        "txt": len(txt_files),
                        "docx": len(docx_files),
                        "xlsx": len(xlsx_files),
                        "pdf": len(pdf_files)
                    }
                }
                structure["folders"].append(folder_info)
                structure["total_files"] += len(valid_files)
                structure["supported_files"] += len(supported_files)
                structure["file_types"]["md"] += len(markdown_files)
                structure["file_types"]["txt"] += len(txt_files)
                structure["file_types"]["docx"] += len(docx_files)
                structure["file_types"]["xlsx"] += len(xlsx_files)
                structure["file_types"]["pdf"] += len(pdf_files)
            
            # Ordenar pastas por caminho para melhor exibição
            structure["folders"].sort(key=lambda x: x["path"])
            
        except Exception as e:
            structure["error"] = str(e)
        
        return structure
    
    def start_auto_update(self, interval_sec: int = None):
        if interval_sec is None:
            interval_sec = INDEX_CONFIG["auto_update_interval"]
        """Iniciar atualizações automáticas do índice em thread de background"""
        def auto_update_loop():
            while True:
                try:
                    self.update_index()
                except Exception as e:
                    # print(f"Error in auto-update loop: {e}")
                    self.log_always("error", f"Erro no loop de atualização automática: {e}")
                time.sleep(interval_sec)
        
        update_thread = threading.Thread(target=auto_update_loop, daemon=True)
        update_thread.start()
        if self.verbose:
            # print(f"Auto-update started with {interval_sec}s interval")
                    self.log_verbose("info", f"Atualização automática iniciada com intervalo de {interval_sec}s")

    def get_smart_summary(self, text: str, max_length: int = 1000) -> str:
        """Criar um resumo inteligente do conteúdo, priorizando sentenças importantes"""
        if len(text) <= max_length:
            return text
        
        # Dividir em sentenças (abordagem simples)
        sentences = text.replace('\n', ' ').split('. ')
        
        # classificar sentenças importantes
        scored_sentences = []
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            # Aumentar pontuação de sentenças com indicadores importantes
            if any(word in sentence_lower for word in ['important', 'key', 'critical', 'essential', 'main', 'primary']):
                score += 3
            if any(word in sentence_lower for word in ['example', 'instance', 'case', 'scenario']):
                score += 2
            if any(word in sentence_lower for word in ['definition', 'concept', 'principle', 'rule']):
                score += 2
            if any(word in sentence_lower for word in ['however', 'but', 'although', 'nevertheless']):
                score += 1  # Contrasting statements often contain important info
            
            # Aumentar pontuação de sentenças com números ou datas
            import re
            if re.search(r'\d+', sentence):
                score += 1
            
            scored_sentences.append((sentence, score))
        
        # Ordenar por pontuação e criar resumo
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        summary = ""
        for sentence, _ in scored_sentences:
            if len(summary + sentence + ". ") <= max_length:
                summary += sentence + ". "
            else:
                break
        
        if summary and not summary.endswith('.'):
            summary = summary.rstrip() + '.'
        
        return summary.strip() or text[:max_length] + "..."
    
    def search_with_summaries(self, query: str, k: int = 3, max_chunk_length: int = 1500) -> List[Dict]:
        """Buscar e retornar resultados com resumos inteligentes para fragmentos longos"""
        results = self.search(query, k)
        
        # Adicionar resumos para fragmentos longos
        for result in results:
            text = result['text']
            if len(text) > max_chunk_length:
                result['summary'] = self.get_smart_summary(text, max_chunk_length)
                result['is_summarized'] = True
            else:
                result['summary'] = text
                result['is_summarized'] = False
        
        return results

    def _save_chunk_to_db(self, text: str, file_path: str, chunk_meta: Dict, chunk_hash: str) -> Optional[int]:
        """Salvar um fragmento no banco de dados e retornar seu ID."""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                existing_chunk = TextChunk.get_by_hash(chunk_hash)
                if existing_chunk:
                    return existing_chunk.id
                
                # Criar novo fragmento
                new_chunk = TextChunk(
                    chunk_text=text,
                    chunk_hash=chunk_hash,
                    file_path=file_path,
                    chunk_metadata=chunk_meta
                )
                db.session.add(new_chunk)
                db.session.commit()
                return new_chunk.id
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            # print(f"Database file not found at: {db_path}")
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return None
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Verificar se o fragmento já existe
                    existing_chunk = session.query(TextChunk).filter_by(chunk_hash=chunk_hash).first()
                    if existing_chunk:
                        session.close()
                        return existing_chunk.id
                    
                    # Criar novo fragmento
                    new_chunk = TextChunk(
                        chunk_text=text,
                        chunk_hash=chunk_hash,
                        file_path=file_path,
                        chunk_metadata=chunk_meta
                    )
                    session.add(new_chunk)
                    session.commit()
                    chunk_id = new_chunk.id
                    session.close()
                    return chunk_id
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Error in standalone chunk save: {e}")
                    return None
                    
        except Exception as e:
            self.log_always("error", f"Error saving chunk to database: {e}")
            return None

    def _get_chunk_from_db(self, chunk_id: int) -> Optional[Tuple[str, Dict]]:
        """Recuperar um fragmento do banco de dados pelo seu ID."""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                chunk = TextChunk.query.get(chunk_id)
                if chunk:
                    # Atualizar estatísticas de acesso
                    TextChunk.update_access_stats(chunk_id)
                    
                    # Verificar cache de memória primeiro
                    if chunk.chunk_hash in self.memory_cache:
                        return self.memory_cache[chunk.chunk_hash]['text'], chunk.chunk_metadata
                    
                    # Adicionar ao cache de memória se não estiver cheio
                    if len(self.memory_cache) < self.max_cache_size:
                        self.memory_cache[chunk.chunk_hash] = {
                            'text': chunk.chunk_text,
                            'metadata': chunk.chunk_metadata
                        }
                    
                    return chunk.chunk_text, chunk.chunk_metadata
                return None, {}
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return None, {}
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    chunk = session.query(TextChunk).get(chunk_id)
                    session.close()
                    
                    if chunk:
                        # Verificar cache de memória primeiro
                        if chunk.chunk_hash in self.memory_cache:
                            return self.memory_cache[chunk.chunk_hash]['text'], chunk.chunk_metadata
                        
                        # Adicionar ao cache de memória se não estiver cheio
                        if len(self.memory_cache) < self.max_cache_size:
                            self.memory_cache[chunk.chunk_hash] = {
                                'text': chunk.chunk_text,
                                'metadata': chunk.chunk_metadata
                            }
                        
                        return chunk.chunk_text, chunk.chunk_metadata
                    return None, {}
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Error in standalone chunk retrieval: {e}")
                    return None, {}
                    
        except Exception as e:
            self.log_always("error", f"Error retrieving chunk from database: {e}")
            return None, {}

    def _delete_chunk_from_db(self, chunk_id: int):
        """Excluir um fragmento do banco de dados pelo seu ID."""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                chunk = TextChunk.query.get(chunk_id)
                if chunk:
                    # Remover do cache de memória se presente
                    if chunk.chunk_hash in self.memory_cache:
                        del self.memory_cache[chunk.chunk_hash]
                    
                    db.session.delete(chunk)
                    db.session.commit()
                    if self.verbose:
                        self.log_verbose("info", f"Fragmento excluído com ID: {chunk_id}")
                else:
                    if self.verbose:
                        self.log_verbose("info", f"Fragmento com ID {chunk_id} não encontrado para exclusão.")
                        
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    chunk = session.query(TextChunk).get(chunk_id)
                    if chunk:
                        # Remover do cache de memória se existir
                        if chunk.chunk_hash in self.memory_cache:
                            del self.memory_cache[chunk.chunk_hash]
                        
                        session.delete(chunk)
                        session.commit()
                        if self.verbose:
                            self.log_verbose("info", f"Fragmento excluído com ID: {chunk_id} (autônomo)")
                    else:
                        if self.verbose:
                            self.log_verbose("info", f"Fragmento com ID {chunk_id} não encontrado para exclusão (autônomo).")
                    
                    session.close()
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na exclusão autônoma de fragmento: {e}")
            
        except Exception as e:
            self.log_always("error", f"Erro ao excluir fragmento do banco de dados: {e}")

    def _cleanup_memory_cache(self):
        """Limpar o cache de memória para evitar crescimento excessivo"""
        if len(self.memory_cache) > self.max_cache_size:
            # Remover fragmentos menos acessados recentemente
            sorted_chunks = sorted(
                self.memory_cache.items(),
                key=lambda x: x[1].get('last_accessed', 0)
            )
            
            # Remover 20% mais antigos dos fragmentos
            chunks_to_remove = int(len(sorted_chunks) * 0.2)
            for i in range(chunks_to_remove):
                del self.memory_cache[sorted_chunks[i][0]]
            
            if self.verbose:
                self.log_verbose("info", f"Cache de memória limpo, removidos {chunks_to_remove} fragmentos")

    def get_memory_usage_stats(self) -> Dict:
        """Obter estatísticas sobre uso de memória e cache"""
        return {
            "memory_cache_size": len(self.memory_cache),
            "max_cache_size": self.max_cache_size,
            "cache_utilization": len(self.memory_cache) / self.max_cache_size * 100,
            "total_chunks_in_db": len(self.chunk_hashes),
            "estimated_memory_saved": "Text chunks moved to database, FAISS index kept in memory"
        }

    def _get_unique_file_count(self) -> int:
        """Obter contagem de arquivos únicos do banco de dados"""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                unique_count = db.session.query(db.func.count(db.func.distinct(TextChunk.file_path))).scalar()
                return unique_count or 0
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return 0
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    unique_count = session.query(db.func.count(db.func.distinct(TextChunk.file_path))).scalar()
                    session.close()
                    return unique_count or 0
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na contagem autônoma de arquivos únicos: {e}")
                    return 0
                    
        except Exception as e:
            self.log_always("error", f"Erro ao obter contagem de arquivos únicos: {e}")
            return 0

    def _file_exists_in_index(self, file_path: str) -> bool:
        """Verificar se um arquivo existe no índice consultando o banco de dados"""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                count = db.session.query(TextChunk).filter_by(file_path=file_path).count()
                return count > 0
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return False
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    count = session.query(TextChunk).filter_by(file_path=file_path).count()
                    session.close()
                    return count > 0
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na verificação autônoma de existência de arquivo: {e}")
                    return False
                    
        except Exception as e:
            self.log_always("error", f"Erro ao verificar se arquivo existe no índice: {e}")
            return False

    def _get_chunks_for_file(self, file_path: str) -> List[Dict]:
        """Obter todos os fragmentos de um arquivo específico no banco de dados"""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                chunks = TextChunk.query.filter_by(file_path=file_path).all()
                return [{'id': chunk.id, 'hash': chunk.chunk_hash} for chunk in chunks]
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return []
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    chunks = session.query(TextChunk).filter_by(file_path=file_path).all()
                    result = [{'id': chunk.id, 'hash': chunk.chunk_hash} for chunk in chunks]
                    session.close()
                    return result
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na recuperação autônoma de fragmentos: {e}")
                    return []
                    
        except Exception as e:
            self.log_always("error", f"Erro ao obter fragmentos para arquivo: {e}")
            return []

    def _get_all_indexed_files(self) -> List[str]:
        """Obter todos os caminhos de arquivos atualmente indexados no banco de dados"""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                files = db.session.query(db.func.distinct(TextChunk.file_path)).all()
                return [file[0] for file in files]
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return []
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    files = session.query(db.func.distinct(TextChunk.file_path)).all()
                    result = [file[0] for file in files]
                    session.close()
                    return result
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na recuperação autônoma de arquivos indexados: {e}")
                    return []
                    
        except Exception as e:
            self.log_always("error", f"Erro ao obter arquivos indexados: {e}")
            return []

    def _get_all_chunks_from_db(self) -> List[Tuple[int, str, Dict]]:
        """Obter todos os fragmentos do banco de dados para reconstrução do índice"""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                chunks = TextChunk.query.all()
                return [(chunk.id, chunk.chunk_text, chunk.chunk_metadata) for chunk in chunks]
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return []
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    chunks = session.query(TextChunk).all()
                    result = [(chunk.id, chunk.chunk_text, chunk.chunk_metadata) for chunk in chunks]
                    session.close()
                    return result
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na recuperação autônoma de fragmentos: {e}")
                    return []
                    
        except Exception as e:
            self.log_always("error", f"Erro ao obter todos os fragmentos do banco de dados: {e}")
            return []

    def _remove_chunks_for_file(self, file_path: str):
        """Remover todos os fragmentos associados a um arquivo específico do banco de dados."""
        try:
            from database import TextChunk, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                # Obter todos os IDs de fragmento para o arquivo
                chunk_ids_to_delete = [tc.id for tc in TextChunk.query.filter_by(file_path=file_path).all()]
                
                if chunk_ids_to_delete:
                    for chunk_id in chunk_ids_to_delete:
                        self._delete_chunk_from_db(chunk_id)
                    db.session.commit()
                    if self.verbose:
                        self.log_verbose("info", f"Todos os fragmentos removidos para arquivo: {os.path.basename(file_path)}")
                else:
                    if self.verbose:
                        self.log_verbose("info", f"Nenhum fragmento encontrado para arquivo: {os.path.basename(file_path)} para remover.")
                        
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Obter todos os IDs de fragmento para o arquivo
                    chunk_ids_to_delete = [tc.id for tc in session.query(TextChunk).filter_by(file_path=file_path).all()]
                    
                    if chunk_ids_to_delete:
                        for chunk_id in chunk_ids_to_delete:
                            self._delete_chunk_from_db(chunk_id)
                        session.commit()
                        if self.verbose:
                            self.log_verbose("info", f"Todos os fragmentos removidos para arquivo: {os.path.basename(file_path)} (autônomo)")
                    else:
                        if self.verbose:
                            self.log_verbose("info", f"Nenhum fragmento encontrado para arquivo: {os.path.basename(file_path)} para remover (autônomo).")
                        
                    session.close()
                        
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na remoção autônoma de fragmento para arquivo: {e}")
            
        except Exception as e:
            self.log_always("error", f"Erro ao remover fragmentos para arquivo do banco de dados: {e}")

    def _sync_document_metadata_to_db(self, file_paths: set = None):
        """Sincronizar metadados de documentos com o banco para todos ou arquivos específicos"""
        try:
            from database import DocumentMetadata, db
            from flask import current_app
            from datetime import datetime
            
            try:
                app = current_app._get_current_object()
                
                if file_paths is None:
                    # Obter todos os arquivos atuais do sistema de arquivos
                    file_paths = set()
                    for root, dirs, files in os.walk(self.vault_path):
                        if self.should_exclude_path(root):
                            continue
                        for file in files:
                            if file.endswith(('.md', '.txt', '.docx', '.xlsx', '.pdf')):
                                file_path = os.path.join(root, file)
                                if not self.should_exclude_path(file_path):
                                    file_paths.add(file_path)
                
                synced_count = 0
                for file_path in file_paths:
                    try:
                        if os.path.exists(file_path):
                            # Obter informações do arquivo
                            stat = os.stat(file_path)
                            file_name = os.path.basename(file_path)
                            folder_path = os.path.relpath(os.path.dirname(file_path), self.vault_path)
                            if folder_path == ".":
                                folder_path = "Root"
                            
                            # Determinar tipo de arquivo
                            if file_name.endswith('.md'):
                                file_type = 'md'
                            elif file_name.endswith('.txt'):
                                file_type = 'txt'
                            elif file_name.endswith('.docx'):
                                file_type = 'docx'
                            elif file_name.endswith('.xlsx'):
                                file_type = 'xlsx'
                            elif file_name.endswith('.pdf'):
                                file_type = 'pdf'
                            else:
                                continue
                            
                            # Verificar se o arquivo está indexado
                            is_indexed = self._file_exists_in_index(file_path)
                            chunk_count = 0
                            if is_indexed:
                                chunks = self._get_chunks_for_file(file_path)
                                chunk_count = len(chunks)
                            
                            # Atualizar ou criar metadados
                            DocumentMetadata.update_or_create(
                                file_path=file_path,
                                file_name=file_name,
                                folder_path=folder_path,
                                file_type=file_type,
                                file_size=stat.st_size,
                                last_modified=datetime.fromtimestamp(stat.st_mtime),
                                is_indexed=is_indexed,
                                chunk_count=chunk_count
                            )
                            synced_count += 1
                            
                    except Exception as e:
                        if self.verbose:
                            self.log_always("error", f"Erro ao sincronizar metadados para {file_path}: {e}")
                
                # Limpar metadados de arquivos que não existem mais
                if file_paths is not None:
                    removed_count = DocumentMetadata.cleanup_removed_files(file_paths)
                    if removed_count > 0 and self.verbose:
                        self.log_verbose("info", f"Metadados limpos para {removed_count} arquivos removidos")
                
                db.session.commit()
                if self.verbose:
                    self.log_verbose("info", f"Metadados sincronizados para {synced_count} arquivos")
                return synced_count
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return 0
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    if file_paths is None:
                        # Obter todos os arquivos atuais do sistema de arquivos
                        file_paths = set()
                        for root, dirs, files in os.walk(self.vault_path):
                            if self.should_exclude_path(root):
                                continue
                            for file in files:
                                if file.endswith(('.md', '.txt', '.docx', '.xlsx', '.pdf')):
                                    file_path = os.path.join(root, file)
                                    if not self.should_exclude_path(file_path):
                                        file_paths.add(file_path)
                    
                    synced_count = 0
                    for file_path in file_paths:
                        try:
                            if os.path.exists(file_path):
                                # Obter informações do arquivo
                                stat = os.stat(file_path)
                                file_name = os.path.basename(file_path)
                                folder_path = os.path.relpath(os.path.dirname(file_path), self.vault_path)
                                if folder_path == ".":
                                    folder_path = "Root"
                                
                                # Determinar tipo de arquivo
                                if file_name.endswith('.md'):
                                    file_type = 'md'
                                elif file_name.endswith('.txt'):
                                    file_type = 'txt'
                                elif file_name.endswith('.docx'):
                                    file_type = 'docx'
                                elif file_name.endswith('.xlsx'):
                                    file_type = 'xlsx'
                                elif file_name.endswith('.pdf'):
                                    file_type = 'pdf'
                                else:
                                    continue
                                
                                # Verificar se o arquivo está indexado
                                is_indexed = self._file_exists_in_index(file_path)
                                chunk_count = 0
                                if is_indexed:
                                    chunks = self._get_chunks_for_file(file_path)
                                    chunk_count = len(chunks)
                                
                                # Atualizar ou criar metadados
                                metadata = session.query(DocumentMetadata).filter_by(file_path=file_path).first()
                                if metadata:
                                    # Atualizar registro existente
                                    metadata.file_name = file_name
                                    metadata.folder_path = folder_path
                                    metadata.file_type = file_type
                                    metadata.file_size = stat.st_size
                                    metadata.file_size_mb = round(stat.st_size / (1024 * 1024), 2)
                                    metadata.last_modified = datetime.fromtimestamp(stat.st_mtime)
                                    metadata.is_indexed = is_indexed
                                    metadata.chunk_count = chunk_count
                                    metadata.last_checked = datetime.utcnow()
                                else:
                                    # Criar novo registro
                                    metadata = DocumentMetadata(
                                        file_path=file_path,
                                        file_name=file_name,
                                        folder_path=folder_path,
                                        file_type=file_type,
                                        file_size=stat.st_size,
                                        file_size_mb=round(stat.st_size / (1024 * 1024), 2),
                                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                                        is_indexed=is_indexed,
                                        chunk_count=chunk_count
                                    )
                                    session.add(metadata)
                                synced_count += 1
                                
                        except Exception as e:
                            if self.verbose:
                                self.log_always("error", f"Error syncing metadata for {file_path}: {e}")
                    
                    # Limpar metadados de arquivos que não existem mais
                    if file_paths is not None:
                        all_metadata = session.query(DocumentMetadata).all()
                        removed_count = 0
                        for metadata in all_metadata:
                            if metadata.file_path not in file_paths:
                                session.delete(metadata)
                                removed_count += 1
                        if removed_count > 0 and self.verbose:
                            self.log_verbose("info", f"Metadados limpos para {removed_count} arquivos removidos")
                    
                    session.commit()
                    session.close()
                    if self.verbose:
                        self.log_verbose("info", f"Metadados sincronizados para {synced_count} arquivos (autônomo)")
                    return synced_count
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na sincronização autônoma de metadados: {e}")
                    return 0
                    
        except Exception as e:
            self.log_always("error", f"Erro ao sincronizar metadados de documento com banco de dados: {e}")
            return 0

    def refresh_document_metadata_cache(self):
        """Atualizar o cache de metadados de documentos escaneando o sistema de arquivos"""
        if self.verbose:
            self.log_verbose("info", "Atualizando cache de metadados de documento...")
        
        synced_count = self._sync_document_metadata_to_db()
        if self.verbose:
            self.log_verbose("info", f"Cache de metadados de documento atualizado: {synced_count} arquivos sincronizados")
        
        return synced_count

    def cleanup_banned_folder_metadata(self, folder_path: str):
        """Limpar metadados de documentos para uma pasta banida/excluída"""
        try:
            from database import DocumentMetadata, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                # Encontrar todos os documentos na pasta banida
                banned_docs = DocumentMetadata.query.filter(
                    DocumentMetadata.folder_path.like(f"{folder_path}%")
                ).all()
                
                removed_count = 0
                for doc in banned_docs:
                    # Remover fragmentos para este arquivo se ele foi indexado
                    if doc.is_indexed:
                        self._remove_chunks_for_file(doc.file_path)
                    
                    # Remover registro de metadados
                    db.session.delete(doc)
                    removed_count += 1
                
                db.session.commit()
                if self.verbose:
                    self.log_verbose("info", f"Metadados limpos para {removed_count} documentos na pasta banida: {folder_path}")
                return removed_count
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        if self.verbose:
                            self.log_always("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                        return 0
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    # Encontrar todos os documentos na pasta banida
                    banned_docs = session.query(DocumentMetadata).filter(
                        DocumentMetadata.folder_path.like(f"{folder_path}%")
                    ).all()
                    
                    removed_count = 0
                    for doc in banned_docs:
                        # Remover fragmentos para este arquivo se ele foi indexado
                        if doc.is_indexed:
                            self._remove_chunks_for_file(doc.file_path)
                        
                        # Remover registro de metadados
                        session.delete(doc)
                        removed_count += 1
                    
                    session.commit()
                    session.close()
                    if self.verbose:
                        self.log_verbose("info", f"Metadados limpos para {removed_count} documentos na pasta banida: {folder_path} (autônomo)")
                    return removed_count
                    
                except Exception as e:
                    if self.verbose:
                        self.log_always("error", f"Erro na limpeza autônoma de pasta banida: {e}")
                    return 0
                    
        except Exception as e:
            self.log_always("error", f"Erro ao limpar metadados de pasta banida: {e}")
            return 0

    def cleanup_removed_folder_metadata(self, folder_path: str):
        """Limpar metadados de documentos para uma pasta removida"""
        return self.cleanup_banned_folder_metadata(folder_path)

    def get_document_metadata_stats(self) -> Dict:
        """Obter estatísticas sobre o cache de metadados de documentos"""
        try:
            from database import DocumentMetadata, db
            from flask import current_app
            
            try:
                app = current_app._get_current_object()
                
                total_docs = DocumentMetadata.query.count()
                indexed_docs = DocumentMetadata.query.filter_by(is_indexed=True).count()
                supported_docs = DocumentMetadata.query.filter_by(is_supported=True).count()
                
                # Obter breakdown de tipo de arquivo
                file_types = {}
                for doc_type in ['md', 'txt', 'docx', 'xlsx', 'pdf']:
                    count = DocumentMetadata.query.filter_by(file_type=doc_type).count()
                    file_types[doc_type] = count
                
                # Obter breakdown de pasta
                folder_count = db.session.query(db.func.count(db.func.distinct(DocumentMetadata.folder_path))).scalar()
                
                return {
                    "total_documents": total_docs,
                    "indexed_documents": indexed_docs,
                    "supported_documents": supported_docs,
                    "file_types": file_types,
                    "folder_count": folder_count,
                    "cache_status": "active" if total_docs > 0 else "empty"
                }
                
            except RuntimeError:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    
                    # Obter caminho absoluto para arquivo de banco de dados
                    db_path = os.path.abspath('instance/app.db')
                    if not os.path.exists(db_path):
                        return {"error": "Database not found"}
                    
                    engine = create_engine(f'sqlite:///{db_path}')
                    Session = sessionmaker(bind=engine)
                    session = Session()
                    
                    total_docs = session.query(DocumentMetadata).count()
                    indexed_docs = session.query(DocumentMetadata).filter_by(is_indexed=True).count()
                    supported_docs = session.query(DocumentMetadata).filter_by(is_supported=True).count()
                    
                    # Obter breakdown de tipo de arquivo
                    file_types = {}
                    for doc_type in ['md', 'txt', 'docx', 'xlsx', 'pdf']:
                        count = session.query(DocumentMetadata).filter_by(file_type=doc_type).count()
                        file_types[doc_type] = count
                    
                    # Obter breakdown de pasta
                    folder_count = session.query(db.func.count(db.func.distinct(DocumentMetadata.folder_path))).scalar()
                    
                    session.close()
                    
                    return {
                        "total_documents": total_docs,
                        "indexed_documents": indexed_docs,
                        "supported_documents": supported_docs,
                        "file_types": file_types,
                        "folder_count": folder_count,
                        "cache_status": "active" if total_docs > 0 else "empty"
                    }
                    
                except Exception as e:
                    return {"error": f"Database access error: {e}"}
                    
        except Exception as e:
            return {"error": f"Error getting metadata stats: {e}"}

    # Instância global
    index_manager = None

    def get_index_manager():
        """Obter ou criar a instância global de IndexManager"""
        global index_manager
        if index_manager is None:
            index_manager = IndexManager()
        return index_manager

    def init_index_manager(enable_usage_tracking: bool = True, verbose: bool = False):
        """Inicializar o gerenciador de índice (chamar ao iniciar o app Flask)"""
        global index_manager
        if index_manager is None:
            index_manager = IndexManager(enable_usage_tracking=enable_usage_tracking, verbose=verbose)
        return index_manager