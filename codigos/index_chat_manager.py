import os
import faiss
import pickle
import numpy as np
import hashlib
import time
import threading
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from typing import List, Dict, Optional, Tuple, Set
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json
from config import CHAT_MEMORY_CONFIG, OPENAI_API_KEY, EMBEDDING_MODEL
from logger import log_index_chat_manager_error, log_index_chat_manager_warning, log_index_chat_manager_info, log_index_chat_manager_success, log_index_chat_manager_debug

class ChatMemoryManager:
    def __init__(self, chat_index_path: str = None, enable_usage_tracking: bool = None, verbose: bool = None):
        # Usar valores de configuração com fallbacks
        self.chat_index_path = chat_index_path or CHAT_MEMORY_CONFIG["chat_index_path"]
        self.enable_usage_tracking = enable_usage_tracking if enable_usage_tracking is not None else CHAT_MEMORY_CONFIG["enable_usage_tracking"]
        self.verbose = verbose if verbose is not None else CHAT_MEMORY_CONFIG["chat_verbose"]
        
        # Configuração de memória
        self.max_short_term_memory = CHAT_MEMORY_CONFIG["max_short_term_memory"]
        self.max_short_term_tokens = CHAT_MEMORY_CONFIG["max_short_term_tokens"]
        self.long_term_memory_chunk_size = CHAT_MEMORY_CONFIG["long_term_memory_chunk_size"]
        self.relevance_threshold = CHAT_MEMORY_CONFIG["relevance_threshold"]
        self.max_memory_results = CHAT_MEMORY_CONFIG["max_memory_results"]
        self.default_hard_delete = CHAT_MEMORY_CONFIG["default_hard_delete"]
        
        # Inicializar cliente OpenAI
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Armazenamento de memória - agora usando banco de dados como fonte única da verdade
        self.long_term_index = None  # Índice FAISS para busca rápida de vetores
        self.chunk_ids = []  # Lista de IDs de chunks para mapear de volta ao banco de dados
        
        # Conexão com banco de dados
        self.db_engine = None
        self.db_session = None
        self._init_database()
        
        # Carregar ou criar índice de memória de longo prazo
        self.load_or_create_memory_index()
        
        # Iniciar thread de atualização automática
        self.start_auto_update()
    
    def log_verbose(self, level: str, message: str):
        """Registrar mensagem apenas se o modo verboso estiver habilitado"""
        if self.verbose:
            if level == "info":
                log_index_chat_manager_info(message)
            elif level == "debug":
                log_index_chat_manager_debug(message)
            elif level == "warning":
                log_index_chat_manager_warning(message)
            elif level == "error":
                log_index_chat_manager_error(message)
            elif level == "success":
                log_index_chat_manager_success(message)

    def log_always(self, level: str, message: str):
        """Registrar mensagem independentemente da configuração verbosa (para erros/informações importantes)"""
        if level == "info":
            log_index_chat_manager_info(message)
        elif level == "debug":
            log_index_chat_manager_debug(message)
        elif level == "warning":
            log_index_chat_manager_warning(message)
        elif level == "error":
            log_index_chat_manager_error(message)
        elif level == "success":
            log_index_chat_manager_success(message)
    
    def _init_database(self):
        """Inicializar conexão com banco de dados"""
        try:
            # Obter caminho absoluto para o arquivo de banco de dados
            db_path = os.path.abspath('instance/app.db')
            if not os.path.exists(db_path):
                if self.verbose:
                    # print(f"Database file not found at: {db_path}")
                    self.log_verbose("warning", f"Arquivo de banco de dados não encontrado em: {db_path}")
                return
            
            self.db_engine = create_engine(f'sqlite:///{db_path}')
            Session = sessionmaker(bind=self.db_engine)
            self.db_session = Session()
            
            if self.verbose:
                # print("Database connection established for chat memory")
                self.log_verbose("success", "Conexão com banco de dados estabelecida para memória de chat")
                
        except Exception as e:
            if self.verbose:
                # print(f"Error initializing database: {e}")
                self.log_always("error", f"Erro ao inicializar banco de dados: {e}")
    
    def _get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """Obter mensagens de uma conversa do banco de dados, excluindo chats excluídos suavemente"""
        if not self.db_session:
            return []
        
        try:
            # Consultar mensagens da conversa, excluindo chats excluídos suavemente
            result = self.db_session.execute(
                text("""
                    SELECT m.id, m.role, m.content, m.timestamp 
                    FROM message m
                    JOIN chat c ON m.chat_id = c.id
                    LEFT JOIN chat_memory cm ON c.id = cm.chat_id
                    WHERE m.chat_id = :conv_id 
                    AND (cm.is_deleted IS NULL OR cm.is_deleted = 0)
                    ORDER BY m.timestamp
                """),
                {"conv_id": conversation_id}
            )
            
            messages = []
            for row in result:
                messages.append({
                    'id': row[0],
                    'role': row[1],
                    'content': row[2],
                    'timestamp': row[3]
                })
            
            return messages
            
        except Exception as e:
            if self.verbose:
                # print(f"Error getting conversation messages: {e}")
                self.log_always("error", f"Erro ao obter mensagens da conversa: {e}")
            return []
    
    def _get_all_conversations(self) -> List[Dict]:
        """Obter todas as conversas não excluídas do banco de dados"""
        if not self.db_session:
            return []
        
        try:
            # Consultar todas as conversas que não foram excluídas suavemente
            result = self.db_session.execute(
                text("""
                    SELECT c.id, c.title, c.created_at, c.user_id
                    FROM chat c
                    LEFT JOIN chat_memory cm ON c.id = cm.chat_id
                    WHERE (cm.is_deleted IS NULL OR cm.is_deleted = 0)
                    ORDER BY c.created_at DESC
                """)
            )
            
            conversations = []
            for row in result:
                conversations.append({
                    'id': row[0],
                    'title': row[1],
                    'created_at': row[2],
                    'user_id': row[3]
                })
            
            return conversations
            
        except Exception as e:
            if self.verbose:
                # print(f"Error getting conversations: {e}")
                self.log_always("error", f"Erro ao obter conversas: {e}")
            return []
    
    def _is_conversation_deleted(self, conversation_id: str) -> bool:
        """Verificar se uma conversa foi excluída suavemente"""
        if not self.db_session:
            return False
        
        try:
            result = self.db_session.execute(
                text("""
                    SELECT cm.is_deleted 
                    FROM chat_memory cm 
                    WHERE cm.chat_id = :conv_id
                """),
                {"conv_id": conversation_id}
            )
            
            row = result.fetchone()
            return row and row[0] == 1
            
        except Exception as e:
            if self.verbose:
                # print(f"Error checking conversation deletion status: {e}")
                self.log_always("error", f"Erro ao verificar status de exclusão da conversa: {e}")
            return False
    
    def _soft_delete_conversation(self, conversation_id: str, user_id: int):
        """Marcar uma conversa como excluída (exclusão suave)"""
        if not self.db_session:
            return False
        
        try:
            # Obter ou criar registro de memória
            result = self.db_session.execute(
                text("""
                    INSERT OR REPLACE INTO chat_memory (chat_id, user_id, is_deleted, deleted_at, last_updated)
                    VALUES (:chat_id, :user_id, 1, :deleted_at, :last_updated)
                """),
                {
                    "chat_id": conversation_id,
                    "user_id": user_id,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Também excluir suavemente todos os chunks de memória para esta conversa
            result = self.db_session.execute(
                text("""
                    UPDATE memory_chunks 
                    SET is_deleted = 1, deleted_at = :deleted_at
                    WHERE conversation_id = :conv_id
                """),
                {
                    "deleted_at": datetime.utcnow().isoformat(),
                    "conv_id": conversation_id
                }
            )
            
            self.db_session.commit()
            
            if self.verbose:
                # print(f"Soft-deleted conversation: {conversation_id}")
                self.log_verbose("success", f"Conversa excluída suavemente: {conversation_id}")
            return True
            
        except Exception as e:
            if self.verbose:
                # print(f"Error soft-deleting conversation: {e}")
                self.log_always("error", f"Erro ao excluir suavemente a conversa: {e}")
            return False
    
    def _create_memory_chunk(self, user_message: str, assistant_message: str, conversation_id: str, timestamp: str) -> str:
        """Criar um chunk de memória a partir de mensagens do usuário e assistente"""
        # Combinar mensagens com separação clara
        memory_text = f"User: {user_message}\n\nAssistant: {assistant_message}"
        
        # Truncar se muito longo
        if len(memory_text) > self.long_term_memory_chunk_size:
            # Tentar truncar do meio, mantendo ambas as partes do usuário e assistente
            user_part = user_message[:self.long_term_memory_chunk_size // 3]
            assistant_part = assistant_message[:self.long_term_memory_chunk_size // 3]
            memory_text = f"User: {user_part}...\n\nAssistant: {assistant_part}..."
        
        return memory_text
    
    def _embed_memory(self, memory_text: str, conversation_id: str, operation: str = "create") -> Optional[np.ndarray]:
        """Criar embedding para texto de memória usando API OpenAI"""
        try:
            # Verificação de segurança: garantir que o texto não exceda o limite de tokens
            max_chars = 6000  # Estimativa conservadora para 8k tokens
            if len(memory_text) > max_chars:
                # print(f"Warning: Memory text length {len(memory_text)} exceeds safe limit {max_chars}, truncating")
                self.log_always("warning", f"Comprimento do texto de memória {len(memory_text)} excede o limite seguro {max_chars}, truncando")
                memory_text = memory_text[:max_chars]
            
            if self.verbose:
                # print(f"Creating embedding for memory of length {len(memory_text)} characters")
                self.log_verbose("info", f"Criando embedding para memória de {len(memory_text)} caracteres")
            
            resp = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=memory_text
            )
            
            # Rastrear uso de tokens para embeddings
            if hasattr(resp, 'usage') and resp.usage and hasattr(resp.usage, 'total_tokens'):
                tokens_used = resp.usage.total_tokens
            else:
                # Estimar tokens se informações de uso não estiverem disponíveis
                tokens_used = len(memory_text) // 4  # Estimativa grosseira: 1 token ≈ 4 caracteres
            
            # Salvar uso no banco de dados se habilitado
            if self.enable_usage_tracking:
                self._track_memory_embedding_usage(conversation_id, len(memory_text), tokens_used, operation)
            
            return np.array(resp.data[0].embedding, dtype=np.float32)
            
        except Exception as e:
            # print(f"Error creating memory embedding: {e}")
            self.log_always("error", f"Erro ao criar embedding de memória: {e}")
            return None
    
    def _track_memory_embedding_usage(self, conversation_id: str, text_length: int, tokens_used: int, operation: str):
        """Rastrear uso de embedding de memória no banco de dados"""
        if not self.enable_usage_tracking:
            return
            
        try:
            # Tentar usar conexão existente com banco de dados
            if self.db_session:
                # Inserir registro de uso na tabela de uso existente
                result = self.db_session.execute(
                    text("""
                        INSERT INTO index_embedding_usage 
                        (file_path, model, text_length, tokens_used, operation, created_at) 
                        VALUES (:file_path, :model, :text_length, :tokens_used, :operation, :created_at)
                    """),
                    {
                        "file_path": f"chat_memory_{conversation_id}",
                        "model": EMBEDDING_MODEL,
                        "text_length": text_length,
                        "tokens_used": tokens_used,
                        "operation": operation,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.db_session.commit()
                
                if self.verbose:
                    # print(f"Tracked memory embedding usage: {tokens_used} tokens for conversation {conversation_id} ({operation})")
                    self.log_verbose("info", f"Uso de embedding de memória rastreado: {tokens_used} tokens para conversa {conversation_id} ({operation})")
                    
        except Exception as e:
            if self.verbose:
                # print(f"Error tracking memory embedding usage: {e}")
                self.log_always("error", f"Erro ao rastrear uso de embedding de memória: {e}")
            # Não falhar a operação principal se o rastreamento falhar
    
    def load_or_create_memory_index(self):
        """Carregar índice de memória existente ou criar novo"""
        if os.path.exists(self.chat_index_path):
            try:
                with open(self.chat_index_path, "rb") as f:
                    data = pickle.load(f)
                    self.long_term_index = data["index"]
                    self.chunk_ids = data["chunk_ids"]
                    if self.verbose:
                        # print(f"Chat memory index loaded with {len(self.chunk_ids)} memory chunks")
                        self.log_verbose("success", f"Índice de memória de chat carregado com {len(self.chunk_ids)} fragmentos de memória")
            except Exception as e:
                if self.verbose:
                    # print(f"Error loading chat memory index: {e}")
                    self.log_always("error", f"Erro ao carregar índice de memória de chat: {e}")
                self.create_new_memory_index()
        else:
            self.create_new_memory_index()
    
    def create_new_memory_index(self):
        """Criar novo índice de memória a partir de conversas existentes"""
        if self.verbose:
            # print("Creating new chat memory index...")
            self.log_verbose("info", "Criando novo índice de memória de chat...")
        
        self.chunk_ids = []
        
        if not self.db_session:
            if self.verbose:
                # print("No database connection available")
                self.log_always("warning", "Nenhuma conexão com banco de dados disponível")
            return
        
        embeddings = []
        conversations = self._get_all_conversations()
        
        for conv in conversations:
            conversation_id = str(conv['id'])
            messages = self._get_conversation_messages(conversation_id)
            
            # Processar mensagens em pares (usuário + assistente)
            for i in range(0, len(messages) - 1, 2):
                if i + 1 < len(messages):
                    user_msg = messages[i]['content']
                    assistant_msg = messages[i + 1]['content']
                    timestamp = messages[i]['timestamp']
                    
                    # Criar chunk de memória
                    memory_text = self._create_memory_chunk(user_msg, assistant_msg, conversation_id, timestamp)
                    
                    # Criar embedding
                    embedding = self._embed_memory(memory_text, conversation_id, "create")
                    if embedding is not None:
                        # Armazenar no banco de dados em vez de RAM
                        chunk_id = self._store_memory_chunk_in_db(
                            conversation_id, memory_text, user_msg, assistant_msg, timestamp, embedding
                        )
                        
                        if chunk_id is not None:
                            self.chunk_ids.append(chunk_id)
                            embeddings.append(embedding)
        
        if embeddings:
            dim = len(embeddings[0])
            self.long_term_index = faiss.IndexFlatL2(dim)
            self.long_term_index.add(np.array(embeddings))
            self.save_memory_index()
            if self.verbose:
                # print(f"New chat memory index created with {len(self.chunk_ids)} memory chunks")
                self.log_verbose("success", f"Novo índice de memória de chat criado com {len(self.chunk_ids)} fragmentos de memória")
        else:
            if self.verbose:
                # print("No valid conversations found to create memory index")
                self.log_verbose("warning", "Nenhuma conversa válida encontrada para criar índice de memória")
    
    def _store_memory_chunk_in_db(self, conversation_id: str, memory_text: str, user_message: str, 
                                 assistant_message: str, timestamp: str, embedding: np.ndarray) -> Optional[int]:
        """Armazenar chunk de memória no banco de dados e retornar chunk_id"""
        if not self.db_session:
            return None
        
        try:
            # Obter próximo chunk_id para esta conversa
            result = self.db_session.execute(
                text("""
                    SELECT COALESCE(MAX(chunk_id), -1) + 1 
                    FROM memory_chunks 
                    WHERE conversation_id = :conv_id
                """),
                {"conv_id": conversation_id}
            )
            chunk_id = result.fetchone()[0]
            
            # Inserir chunk de memória
            result = self.db_session.execute(
                text("""
                    INSERT INTO memory_chunks 
                    (conversation_id, memory_text, user_message, assistant_message, timestamp, chunk_id, embedding_vector)
                    VALUES (:conv_id, :memory_text, :user_msg, :assistant_msg, :timestamp, :chunk_id, :embedding)
                """),
                {
                    "conv_id": conversation_id,
                    "memory_text": memory_text,
                    "user_msg": user_message,
                    "assistant_msg": assistant_message,
                    "timestamp": timestamp,
                    "chunk_id": chunk_id,
                    "embedding": embedding.tobytes()
                }
            )
            
            self.db_session.commit()
            return chunk_id
            
        except Exception as e:
            if self.verbose:
                # print(f"Error storing memory chunk in database: {e}")
                self.log_always("error", f"Erro ao armazenar fragmento de memória no banco de dados: {e}")
            return None
    
    def save_memory_index(self):
        """Salvar índice de memória em arquivo"""
        os.makedirs(os.path.dirname(self.chat_index_path), exist_ok=True)
        data = {
            "index": self.long_term_index,
            "chunk_ids": self.chunk_ids
        }
        with open(self.chat_index_path, "wb") as f:
            pickle.dump(data, f)
    
    def get_short_term_memory(self, conversation_id: str, max_exchanges: int = None) -> List[Dict]:
        """Obter memória de curto prazo para uma conversa do banco de dados"""
        if max_exchanges is None:
            max_exchanges = self.max_short_term_memory
        
        messages = self._get_conversation_messages(conversation_id)
        
        # Converter para formato de troca e limitar a trocas recentes
        exchanges = []
        for i in range(0, len(messages) - 1, 2):
            if i + 1 < len(messages):
                exchanges.append({
                    'user_message': messages[i]['content'],
                    'assistant_message': messages[i + 1]['content'],
                    'timestamp': messages[i]['timestamp']
                })
        
        # Retornar apenas as trocas mais recentes
        return exchanges[-max_exchanges:]
    
    def add_conversation_memory(self, conversation_id: str, user_message: str, assistant_message: str, timestamp: str = None):
        """Adicionar uma nova troca de conversa à memória de longo prazo"""
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        # Criar chunk de memória
        memory_text = self._create_memory_chunk(user_message, assistant_message, conversation_id, timestamp)
        embedding = self._embed_memory(memory_text, conversation_id, "create")
        
        if embedding is not None:
            # Armazenar no banco de dados em vez de RAM
            chunk_id = self._store_memory_chunk_in_db(
                conversation_id, memory_text, user_message, assistant_message, timestamp, embedding
            )
            
            if chunk_id is not None:
                self.chunk_ids.append(chunk_id)
                
                # Adicionar ao índice FAISS
                if self.long_term_index is not None:
                    self.long_term_index.add(np.array([embedding]))
                
                # Salvar índice atualizado
                self.save_memory_index()
                
                if self.verbose:
                    # print(f"Added memory for conversation {conversation_id}")
                    self.log_verbose("success", f"Memória adicionada para conversa {conversation_id}")
    
    def search_long_term_memory(self, query: str, conversation_id: str = None, k: int = None) -> List[Dict]:
        """Buscar memória de longo prazo por conversas passadas relevantes"""
        if k is None:
            k = self.max_memory_results
        
        if self.long_term_index is None or not self.chunk_ids:
            return []
        
        # Criar embedding de consulta
        query_embedding = self._embed_memory(query, "search_query", "search")
        if query_embedding is None:
            return []
        
        try:
            # Buscar no índice
            D, I = self.long_term_index.search(np.array([query_embedding]), k)
            results = []
            
            if self.verbose:
                # print(f"Memory search: query='{query}', conversation_id='{conversation_id}', found {len(I[0])} candidates")
                self.log_verbose("debug", f"Busca de memória: consulta='{query}', conversation_id='{conversation_id}', encontrados {len(I[0])} candidatos")
            
            for i, idx in enumerate(I[0]):
                if idx < len(self.chunk_ids):
                    similarity_score = float(D[0][i])
                    
                    # Incluir apenas resultados acima do limite de relevância
                    if similarity_score >= self.relevance_threshold:
                        chunk_id = self.chunk_ids[idx]
                        
                        # Obter dados de memória do banco de dados em vez de RAM
                        memory_data = self._get_memory_chunk_from_db(chunk_id)
                        if memory_data is None:
                            continue
                        
                        memory_conv_id = memory_data.get('conversation_id', '')
                        
                        if self.verbose:
                            # print(f"  Candidate {i}: conv_id='{memory_conv_id}', score={similarity_score:.3f}")
                            self.log_verbose("debug", f"  Candidato {i}: conv_id='{memory_conv_id}', pontuação={similarity_score:.3f}")
                        
                        # Pular se esta memória for de uma conversa excluída
                        if self._is_conversation_deleted(memory_conv_id):
                            if self.verbose:
                                # print(f"    Skipping deleted conversation: {memory_conv_id}")
                                self.log_verbose("debug", f"    Pulando conversa excluída: {memory_conv_id}")
                            continue
                        
                        # Pular se estivermos filtrando por conversa específica e esta memória NÃO for dessa conversa
                        if conversation_id and memory_conv_id != conversation_id:
                            if self.verbose:
                                # print(f"    Skipping different conversation: {memory_conv_id} != {conversation_id}")
                                self.log_verbose("debug", f"    Pulando conversa diferente: {memory_conv_id} != {conversation_id}")
                            continue
                        
                        if self.verbose:
                            # print(f"    Including memory from conversation: {memory_conv_id}")
                            self.log_verbose("debug", f"    Incluindo memória da conversa: {memory_conv_id}")
                        
                        result = {
                            'memory_text': memory_data.get('memory_text'),
                            'similarity_score': similarity_score,
                            'conversation_id': memory_conv_id,
                            'timestamp': memory_data.get('timestamp'),
                            'user_message': memory_data.get('user_message'),
                            'assistant_message': memory_data.get('assistant_message')
                        }
                        results.append(result)
            
            # Ordenar por pontuação de similaridade (maior primeiro)
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            if self.verbose:
                # print(f"Memory search returned {len(results)} results for conversation {conversation_id}")
                self.log_verbose("debug", f"Busca de memória retornou {len(results)} resultados para conversa {conversation_id}")
            
            return results
            
        except Exception as e:
            # print(f"Error searching long-term memory: {e}")
            self.log_always("error", f"Erro ao buscar memória de longo prazo: {e}")
            return []
    
    def _get_memory_chunk_from_db(self, chunk_id: int) -> Optional[Dict]:
        """Obter dados de chunk de memória do banco de dados por chunk_id"""
        if not self.db_session:
            return None
        
        try:
            result = self.db_session.execute(
                text("""
                    SELECT conversation_id, memory_text, user_message, assistant_message, timestamp
                    FROM memory_chunks 
                    WHERE chunk_id = :chunk_id
                """),
                {"chunk_id": chunk_id}
            )
            
            row = result.fetchone()
            if row:
                return {
                    'conversation_id': row[0],
                    'memory_text': row[1],
                    'user_message': row[2],
                    'assistant_message': row[3],
                    'timestamp': row[4]
                }
            return None
            
        except Exception as e:
            if self.verbose:
                # print(f"Error getting memory chunk from database: {e}")
                self.log_always("error", f"Erro ao obter fragmento de memória do banco de dados: {e}")
            return None
    
    def get_context_with_memory(self, conversation_id: str, current_query: str, max_memories: int = 3) -> str:
        """Obter contexto combinando memória de curto prazo e memórias de longo prazo relevantes"""
        context_parts = []
        
        if self.verbose:
            # print(f"Getting context for conversation: {conversation_id}")
            self.log_verbose("debug", f"Obtendo contexto para conversa: {conversation_id}")
        
        # Adicionar memória de curto prazo do banco de dados
        short_term = self.get_short_term_memory(conversation_id, max_exchanges=3)
        if short_term:
            if self.verbose:
                # print(f"  Found {len(short_term)} short-term memory exchanges")
                self.log_verbose("debug", f"  Encontradas {len(short_term)} trocas de memória de curto prazo")
            context_parts.append("Recent conversation context:")
            for i, exchange in enumerate(short_term, 1):
                context_parts.append(f"{i}. User: {exchange['user_message']}")
                context_parts.append(f"   Assistant: {exchange['assistant_message']}")
            context_parts.append("")
        else:
            if self.verbose:
                # print("  No short-term memory found")
                self.log_verbose("debug", "  Nenhuma memória de curto prazo encontrada")
        
        # Adicionar memórias de longo prazo relevantes APENAS desta conversa
        relevant_memories = self.search_long_term_memory(current_query, conversation_id, max_memories)
        if relevant_memories:
            if self.verbose:
                # print(f"  Found {len(relevant_memories)} relevant long-term memories from this conversation")
                self.log_verbose("debug", f"  Encontradas {len(relevant_memories)} memórias de longo prazo relevantes desta conversa")
            context_parts.append("Relevant past exchanges from this conversation:")
            for i, memory in enumerate(relevant_memories, 1):
                context_parts.append(f"{i}. {memory['memory_text']}")
            context_parts.append("")
        else:
            if self.verbose:
                # print("  No relevant long-term memories found from this conversation")
                self.log_verbose("debug", "  Nenhuma memória de longo prazo relevante encontrada desta conversa")
        
        final_context = "\n".join(context_parts)
        if self.verbose:
            # print(f"Final context length: {len(final_context)} characters")
            self.log_verbose("debug", f"Comprimento do contexto final: {len(final_context)} caracteres")
        
        return final_context
    
    def delete_conversation_memory(self, conversation_id: str, user_id: int, hard_delete: bool = None):
        """Excluir memória de conversa (usa padrão de configuração se não especificado)"""
        if hard_delete is None:
            hard_delete = self.default_hard_delete
        if hard_delete:
            # Exclusão definitiva: remover do banco de dados e reconstruir índice
            if self.db_session:
                try:
                    # Excluir chunks de memória do banco de dados
                    self.db_session.execute(
                        text("DELETE FROM memory_chunks WHERE conversation_id = :conv_id"),
                        {"conv_id": conversation_id}
                    )
                    
                    # Excluir registro de memória de chat
                    self.db_session.execute(
                        text("DELETE FROM chat_memory WHERE chat_id = :conv_id"),
                        {"conv_id": conversation_id}
                    )
                    
                    self.db_session.commit()
                    
                    # Reconstruir índice FAISS
                    self._rebuild_memory_index()
                    
                    if self.verbose:
                        # print(f"Hard deleted conversation {conversation_id}")
                        self.log_verbose("success", f"Conversa {conversation_id} excluída permanentemente")
                        
                except Exception as e:
                    if self.verbose:
                        # print(f"Error hard deleting conversation: {e}")
                        self.log_always("error", f"Erro ao excluir permanentemente a conversa: {e}")
        else:
            # Exclusão suave: marcar como excluído no banco de dados
            self._soft_delete_conversation(conversation_id, user_id)
            if self.verbose:
                # print(f"Soft deleted conversation {conversation_id}")
                self.log_verbose("success", f"Conversa {conversation_id} excluída suavemente")
    
    def _rebuild_memory_index(self):
        """Reconstruir o índice FAISS após exclusões definitivas"""
        if not self.db_session:
            return
        
        try:
            # Obter todos os chunks de memória não excluídos do banco de dados
            result = self.db_session.execute(
                text("SELECT chunk_id, embedding_vector FROM memory_chunks WHERE is_deleted = 0 ORDER BY chunk_id")
            )
            
            embeddings = []
            chunk_ids = []
            
            for row in result:
                chunk_id = row[0]
                embedding_bytes = row[1]
                
                if embedding_bytes:
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    embeddings.append(embedding)
                    chunk_ids.append(chunk_id)
            
            if embeddings:
                dim = len(embeddings[0])
                self.long_term_index = faiss.IndexFlatL2(dim)
                self.long_term_index.add(np.array(embeddings))
                self.chunk_ids = chunk_ids
                self.save_memory_index()
                # print(f"Memory index rebuilt with {len(embeddings)} embeddings")
                self.log_verbose("success", f"Índice de memória reconstruído com {len(embeddings)} embeddings")
            else:
                self.long_term_index = None
                self.chunk_ids = []
                self.save_memory_index()
                # print("Memory index cleared - no embeddings found")
                self.log_verbose("warning", "Índice de memória limpo - nenhum embedding encontrado")
                
        except Exception as e:
            if self.verbose:
                # print(f"Error rebuilding memory index: {e}")
                self.log_always("error", f"Erro ao reconstruir índice de memória: {e}")
    
    def cleanup_orphaned_memory_chunks(self, hard_delete: bool = None) -> int:
        """Limpar chunks de memória órfãos que referenciam chats inexistentes"""
        if hard_delete is None:
            hard_delete = self.default_hard_delete
        
        if not self.db_session:
            return 0
        
        try:
            # Encontrar chunks de memória órfãos
            result = self.db_session.execute(
                text("""
                    SELECT mc.id, mc.conversation_id 
                    FROM memory_chunks mc
                    LEFT JOIN chat c ON mc.conversation_id = c.id
                    WHERE c.id IS NULL
                """)
            )
            orphaned_chunks = result.fetchall()
            
            if not orphaned_chunks:
                if self.verbose:
                    # print("No orphaned memory chunks found")
                    self.log_verbose("info", "Nenhum fragmento de memória órfão encontrado")
                return 0
            
            cleaned_count = 0
            
            for chunk in orphaned_chunks:
                chunk_id = chunk[0]
                conversation_id = chunk[1]
                
                if hard_delete:
                    # Exclusão definitiva: remover do banco de dados
                    self.db_session.execute(
                        text("DELETE FROM memory_chunks WHERE id = :chunk_id"),
                        {"chunk_id": chunk_id}
                    )
                    if self.verbose:
                        # print(f"Hard deleted orphaned memory chunk {chunk_id} for conversation {conversation_id}")
                        self.log_verbose("success", f"Fragmento de memória órfão {chunk_id} excluído permanentemente para conversa {conversation_id}")
                else:
                    # Exclusão suave: marcar como excluído
                    self.db_session.execute(
                        text("""
                            UPDATE memory_chunks 
                            SET is_deleted = 1, deleted_at = :deleted_at
                            WHERE id = :chunk_id
                        """),
                        {
                                                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "chunk_id": chunk_id
                        }
                    )
                    if self.verbose:
                        # print(f"Soft deleted orphaned memory chunk {chunk_id} for conversation {conversation_id}")
                        self.log_verbose("success", f"Fragmento de memória órfão {chunk_id} excluído suavemente para conversa {conversation_id}")
                
                cleaned_count += 1
            
            # Também limpar registros órfãos de chat_memory
            result = self.db_session.execute(
                text("""
                    SELECT cm.id, cm.chat_id 
                    FROM chat_memory cm
                    LEFT JOIN chat c ON cm.chat_id = c.id
                    WHERE c.id IS NULL
                """)
            )
            orphaned_memories = result.fetchall()
            
            for memory in orphaned_memories:
                memory_id = memory[0]
                chat_id = memory[1]
                
                if hard_delete:
                    # Exclusão definitiva: remover do banco de dados
                    self.db_session.execute(
                        text("DELETE FROM chat_memory WHERE id = :memory_id"),
                        {"memory_id": memory_id}
                    )
                    if self.verbose:
                        # print(f"Hard deleted orphaned chat memory {memory_id} for chat {chat_id}")
                        self.log_verbose("success", f"Memória de chat órfã {memory_id} excluída permanentemente para chat {chat_id}")
                    cleaned_count += 1
                else:
                    # Exclusão suave: marcar como excluído
                    self.db_session.execute(
                        text("""
                            UPDATE chat_memory 
                            SET is_deleted = 1, deleted_at = :deleted_at, last_updated = :last_updated
                            WHERE id = :memory_id
                        """),
                        {
                                                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "memory_id": memory_id
                        }
                    )
                    if self.verbose:
                        # print(f"Soft deleted orphaned chat memory {memory_id} for chat {chat_id}")
                        self.log_verbose("success", f"Memória de chat órfã {memory_id} excluída suavemente para chat {chat_id}")
                    cleaned_count += 1
            
            # Confirmar alterações
            self.db_session.commit()
            
            # Reconstruir índice se excluímos chunks definitivamente
            if hard_delete and cleaned_count > 0:
                self._rebuild_memory_index()
            
            if self.verbose:
                # print(f"Cleaned up {cleaned_count} orphaned memory records")
                self.log_verbose("success", f"Limpeza de {cleaned_count} registros de memória órfãos concluída")
            
            return cleaned_count
            
        except Exception as e:
            if self.verbose:
                # print(f"Error cleaning up orphaned memory chunks: {e}")
                self.log_always("error", f"Erro ao limpar fragmentos de memória órfãos: {e}")
            self.db_session.rollback()
            return 0
    
    def get_memory_stats(self) -> Dict:
        """Obter estatísticas do sistema de memória"""
        # Contar chunks de memória no banco de dados
        chunk_count = 0
        deleted_count = 0
        orphaned_count = 0
        
        if self.db_session:
            try:
                # Contar chunks totais
                result = self.db_session.execute(
                    text("SELECT COUNT(*) FROM memory_chunks")
                )
                chunk_count = result.fetchone()[0] or 0
                
                # Contar conversas e chunks de memória excluídos suavemente
                result = self.db_session.execute(
                    text("SELECT COUNT(*) FROM chat_memory WHERE is_deleted = 1")
                )
                deleted_conversations = result.fetchone()[0] or 0
                
                result = self.db_session.execute(
                    text("SELECT COUNT(*) FROM memory_chunks WHERE is_deleted = 1")
                )
                deleted_chunks = result.fetchone()[0] or 0
                
                deleted_count = deleted_conversations + deleted_chunks
                
                # Contar chunks de memória órfãos (referenciando chats inexistentes)
                result = self.db_session.execute(
                    text("""
                        SELECT COUNT(*) FROM memory_chunks mc
                        LEFT JOIN chat c ON mc.conversation_id = c.id
                        WHERE c.id IS NULL AND mc.is_deleted = 0
                    """)
                )
                orphaned_count = result.fetchone()[0] or 0
                
                # Armazenar detalhamento para exibição de administrador
                self._deleted_breakdown = {
                    'conversations': deleted_conversations,
                    'chunks': deleted_chunks,
                    'total': deleted_count
                }
                
            except Exception as e:
                if self.verbose:
                    # print(f"Error counting memory statistics: {e}")
                    self.log_always("error", f"Erro ao contar estatísticas de memória: {e}")
        
        return {
            "short_term_memory": {
                "source": "database_messages_table",
                "max_exchanges": self.max_short_term_memory,
                "max_tokens": self.max_short_term_tokens
            },
            "long_term_memory": {
                "total_chunks": chunk_count,
                "index_size": self.long_term_index.ntotal if self.long_term_index else 0,
                "deleted_conversations": deleted_count,
                "orphaned_chunks": orphaned_count,
                "deleted_breakdown": getattr(self, '_deleted_breakdown', {'conversations': 0, 'chunks': 0, 'total': 0})
            },
            "configuration": {
                "relevance_threshold": self.relevance_threshold,
                "max_memory_results": self.max_memory_results,
                "chunk_size": self.long_term_memory_chunk_size,
                "default_hard_delete": self.default_hard_delete
            }
        }
    
    def start_auto_update(self, interval_sec: int = None):
        """Iniciar atualizações automáticas de memória em thread de segundo plano"""
        if interval_sec is None:
            interval_sec = CHAT_MEMORY_CONFIG["chat_auto_update_interval"]
        
        def auto_update_loop():
            while True:
                try:
                    self._sync_with_database()
                except Exception as e:
                    if self.verbose:
                        # print(f"Error in memory auto-update loop: {e}")
                        self.log_always("error", f"Erro no loop de atualização automática de memória: {e}")
                time.sleep(interval_sec)
        
        update_thread = threading.Thread(target=auto_update_loop, daemon=True)
        update_thread.start()
        if self.verbose:
            # print(f"Memory auto-update started with {interval_sec}s interval")
            self.log_verbose("info", f"Atualização automática de memória iniciada com intervalo de {interval_sec}s")
    
    def _sync_with_database(self):
        """Sincronizar memória com alterações do banco de dados"""
        try:
            # Verificar novas conversas e mensagens
            conversations = self._get_all_conversations()
            
            for conv in conversations:
                conversation_id = str(conv['id'])
                
                # Verificar se temos esta conversa na memória (excluindo chunks excluídos suavemente)
                result = self.db_session.execute(
                    text("SELECT COUNT(*) FROM memory_chunks WHERE conversation_id = :conv_id AND is_deleted = 0"),
                    {"conv_id": conversation_id}
                )
                existing_count = result.fetchone()[0] or 0
                
                if existing_count == 0:
                    # Nova conversa, adicionar à memória
                    messages = self._get_conversation_messages(conversation_id)
                    for i in range(0, len(messages) - 1, 2):
                        if i + 1 < len(messages):
                            self.add_conversation_memory(
                                conversation_id,
                                messages[i]['content'],
                                messages[i + 1]['content'],
                                messages[i]['timestamp']
                            )
            
            # Limpeza automática de chunks órfãos se exclusão definitiva estiver habilitada
            if self.default_hard_delete:
                orphaned_count = self.cleanup_orphaned_memory_chunks(hard_delete=True)
                if orphaned_count > 0 and self.verbose:
                    # print(f"Auto-cleaned up {orphaned_count} orphaned memory chunks during sync")
                    self.log_verbose("info", f"Limpeza automática de {orphaned_count} fragmentos de memória órfãos durante sincronização")
            
            # Salvar quaisquer atualizações
            if self.chunk_ids:
                self.save_memory_index()
                
        except Exception as e:
            if self.verbose:
                # print(f"Error syncing with database: {e}")
                self.log_always("error", f"Erro ao sincronizar com banco de dados: {e}")

# Instância global
chat_memory_manager = None

def get_chat_memory_manager():
    """Obter ou criar a instância global do gerenciador de memória de chat"""
    global chat_memory_manager
    if chat_memory_manager is None:
        chat_memory_manager = ChatMemoryManager()
    return chat_memory_manager

def init_chat_memory_manager(enable_usage_tracking: bool = True, verbose: bool = False):
    """Inicializar o gerenciador de memória de chat"""
    global chat_memory_manager
    if chat_memory_manager is None:
        chat_memory_manager = ChatMemoryManager(enable_usage_tracking=enable_usage_tracking, verbose=verbose)
    return chat_memory_manager
