import uuid
import os
from dotenv import load_dotenv
from openai import OpenAI
from openai import AzureOpenAI
from functools import partial

from typing import List, Dict, Annotated, Callable

from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

def get_embeddings(model_name="text-embedding-ada-002", use_local_embedding=False, local_model_name=None):
    """
    获取嵌入模型，根据环境变量决定使用标准OpenAI、Azure OpenAI或本地模型
    
    Args:
        model_name: 嵌入模型名称，默认为"text-embedding-ada-002"
        use_local_embedding: 是否使用本地嵌入模型
        local_model_name: 本地嵌入模型名称
        
    Returns:
        嵌入模型实例
    """
    if use_local_embedding:
        return HuggingFaceEmbeddings(model_name=local_model_name)
    
    # 优先使用Azure OpenAI
    if os.environ.get("AZURE_PAY_OPENAI_API_KEY"):
        # 处理Azure端点URL，确保它只包含基础URL部分
        endpoint = os.environ.get("AZURE_PAY_OPENAI_ENDPOINT", "")
        # 如果端点包含完整路径，提取基础URL
        if "deployments" in endpoint:
            endpoint = endpoint.split("azure.com")[0]+'azure.com'
        
        deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", model_name)
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15")
        
        from langchain_openai import AzureOpenAIEmbeddings

        embeddings = AzureOpenAIEmbeddings(
            openai_api_key=os.environ.get("AZURE_PAY_OPENAI_API_KEY"),
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            openai_api_version=api_version,
        )
        return embeddings
          
    
    # 使用标准OpenAI
    return OpenAIEmbeddings(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model=model_name
    )
class WebRetriever:
    def __init__(self, chunk_size=2000, chunk_overlap=200):
        self.embeddings = get_embeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    def split_content(self, content: str) -> List[Document]:
            split_texts = self.text_splitter.split_text(content)
            return [Document(page_content=text) for text in split_texts]

    def retrieve_relevant_chunks(self, search_results: List[Dict[str, str]], query: str, k: int = 4) -> Dict[str, Dict[str, str]]:
        all_documents = []
        for result in search_results:
            try:
                if len(result.get('content',''))>0:
                    docs = self.split_content(result['content'])
                    for doc in docs:
                        doc.metadata['title'] = result['title']
                        doc.metadata['snippet'] = result['snippet']
                        doc.metadata['link'] = result['link']
                        doc.metadata['source'] = 'content'
                        doc.metadata['content'] = result['content']
                    all_documents.extend(docs)

                if len(result.get('snippet',''))>0:
                    # Add the snippet as a separate document
                    snippet_doc = Document(
                        page_content=result['snippet'],
                        metadata={
                            'title': result['title'],
                            'snippet': result['snippet'],
                            'link': result['link'],
                            'source': 'snippet',
                            'content': result['content'],
                        }
                    )
                    all_documents.append(snippet_doc)
            except Exception as e:
                # print(result)
                print(f"Error processing content for {result['link']}: {str(e)}")
        
        if len(all_documents)<1:
            return search_results
        
        # Create Chroma vectorstore with unique collection name and persist directory
        collection_name = f"search_{uuid.uuid4().hex}"
        persist_directory = f"db/tmp/chroma_{collection_name}"
        
        vectorstore = Chroma.from_documents(
            all_documents, 
            self.embeddings, 
            collection_name=collection_name,
            persist_directory=persist_directory
        )
        
        # Create BM25 retriever
        bm25_retriever = BM25Retriever.from_documents(all_documents)
        bm25_retriever.k = k
        
        # Create ensemble retriever
        ensemble_retriever = EnsembleRetriever(
            retrievers=[vectorstore.as_retriever(search_kwargs={"k": k}), bm25_retriever],
            weights=[0.6, 0.4]
        )
        
        # Retrieve documents
        retrieved_docs = ensemble_retriever.get_relevant_documents(query)

        # Clean up
        vectorstore.delete_collection()
        import shutil
        if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
        
        top_results = []
        # for i, doc in enumerate(retrieved_docs[:k]):
        content_count = 0
        for doc in retrieved_docs:
            if doc.metadata.get('source','content') == 'content':
                if content_count >= k:
                    continue
                content_count += 1
            # elif doc.metadata.get('source','snippet') == 'snippet':
            #     if len(top_results) >= k-2:
            #         continue            
            top_results.append({
                'title': doc.metadata['title'],
                'snippet': doc.metadata['snippet'],
                'link': doc.metadata['link'],
                # 'source': doc.metadata['source'],
                # 'content': doc.metadata['content'],
                'content': doc.page_content if doc.metadata['snippet'] != doc.page_content else ''
            })
        
        return top_results


class EmbeddingMatcher:
    def __init__(
        self,
        topk=10,
        chunk_size=1000,
        chunk_overlap=100,
        embedding_weight=1.0,
        embedding_model_name=None, #sentence-transformers/all-MiniLM-L6-v2
        use_local_embedding=False,
        document_converter=None,
        persistent_db=False,
        persistent_db_path="db/persistent_chroma",
        persistent_collection_name="persistent_collection",
        initial_docs=None
    ):
        self.topk = topk
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_weight = embedding_weight
        
        self.client = self._get_openai_client()
        self.embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-ada-002")
        
        self.embeddings = get_embeddings(
            model_name=self.embedding_model,
            use_local_embedding=use_local_embedding,
            local_model_name=embedding_model_name
        )
        
        self.persist_directory = None
        self.collection_name = None
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        self.document_converter = document_converter or partial(self._prepare_documents)
            
        # 持久化数据库设置
        self.persistent_db = persistent_db
        self.persistent_db_path = persistent_db_path
        self.persistent_collection_name = persistent_collection_name or "persistent_collection"
        self.vectorstore_db = None
        
        # 如果启用持久化数据库
        if persistent_db:
            if os.path.exists(self.persistent_db_path) and initial_docs is None:
                # 如果没有提供初始文档但数据库路径存在，则加载现有数据库
                print(f"Loading existing persistent database from {self.persistent_db_path}")
                self._load_persistent_db()
            elif initial_docs:
                # 如果提供了初始文档，则创建新的持久化数据库
                print(f"Creating persistent database with {len(initial_docs)} documents")
                self._prepare_vectorstore_for_search(initial_docs, persistent=True)
            else:
                raise ValueError(f"启用了持久化数据库但未提供初始文档且路径不存在: {self.persistent_db_path}")

    def _get_openai_client(self):
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        if use_azure:
            return AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        else:
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _simplify_metadata(self, metadata):
        """Convert complex metadata types to simple types."""
        simplified = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                simplified[key] = value
            elif isinstance(value, list):
                simplified[key] = ', '.join(map(str, value))
            else:
                simplified[key] = str(value)
        return simplified

    def split_content(self, content: str) -> List[Document]:
        split_texts = self.text_splitter.split_text(content)
        return [Document(page_content=text) for text in split_texts]      
        
    def _prepare_documents(self, docs):
        """Convert docs to Langchain Documents."""
        if isinstance(docs, str):
            return self.split_content(docs)
        elif isinstance(docs, list):
            if isinstance(docs[0], dict):
                return [
                    Document(
                        page_content=f"{doc['title']}: {doc['summary']}",
                        metadata=self._simplify_metadata(doc)  # Include all fields from the original doc
                    ) for doc in docs
                ]

    def split_document(self, document: Document) -> List[Document]:
        """将单个Document对象切分成多个较小的Document对象
        
        Args:
            document: 要切分的Document对象
            
        Returns:
            List[Document]: 切分后的Document对象列表
        """
        # 使用text_splitter切分文档内容
        splits = self.text_splitter.split_text(document.page_content)
        # 为每个切分创建新的Document对象，保留原始元数据
        return [Document(
            page_content=split,
            metadata=document.metadata
        ) for split in splits]

    def _prepare_vectorstore_for_search(self, docs, persistent=False):
        """准备文档并创建向量存储
            docs: 要处理的文档
            persistent: 是否创建持久化存储，默认为False
        """
        # 先使用document_converter转换文档
        initial_documents = self.document_converter(docs)
        
        # 对每个文档进行切分
        documents = []
        for doc in initial_documents:
            documents.extend(self.split_document(doc))
        # import pdb; pdb.set_trace()
        
        collection_name = self.persistent_collection_name if persistent else f"matcher_{uuid.uuid4().hex}"
        persist_directory = self.persistent_db_path if persistent else f"db/tmp/chroma_{collection_name}"
        
        max_docs_iter = 100
        if len(documents)>max_docs_iter:
            self.vectorstore_db = Chroma.from_documents(
                documents[:max_docs_iter], 
                self.embeddings, 
                collection_name=collection_name,
                persist_directory=persist_directory
            )
            import time 
            slice_size = max_docs_iter
            # 计算剩余文档数量
            remaining_docs = len(documents) - max_docs_iter
            # 计算需要分成多少批次处理
            batch_count = (remaining_docs + slice_size - 1) // slice_size  # 向上取整
            print(f"剩余{remaining_docs}个文档，将分成{batch_count}批处理，每批{slice_size}个文档")
            
            # 准备批量添加文档
            for batch_idx in range(batch_count):
                start_idx = max_docs_iter + batch_idx * slice_size
                end_idx = min(start_idx + slice_size, len(documents))
                batch_docs = documents[start_idx:end_idx]
                
                if batch_docs:
                    try:
                        # import pdb; pdb.set_trace()
                        self.vectorstore_db.add_documents(batch_docs)
                        print(f"已添加第{batch_idx+1}/{batch_count}批文档，{len(batch_docs)}个", flush=True)
                    except Exception as e:
                        print(f"添加第{batch_idx+1}批文档时出错: {e}", flush=True)
                        
                    # 每批处理后短暂暂停，避免API限制
                    if batch_idx < batch_count - 1:
                        time.sleep(1)
                
        else:
            self.vectorstore_db = Chroma.from_documents(
                documents, 
                self.embeddings, 
                collection_name=collection_name,
                persist_directory=persist_directory
            )
            
        
        if persistent:
            self.vectorstore_db.persist()
            print(f"已创建持久化数据库，路径: {self.persistent_db_path}, 集合名: {self.persistent_collection_name}", flush=True)
        
        return documents

    def _cleanup_vectorstore(self):
        """Clean up Chroma resources."""
        if self.vectorstore_db:
            self.vectorstore_db.delete_collection()
            if self.persistent_db and self.persist_directory:
                import shutil
                if os.path.exists(self.persist_directory):
                    shutil.rmtree(self.persist_directory)

    def _default_similarity_processor(self, results):
        """默认的相似性搜索结果处理器"""
        matched_docs = []
        for doc, score in results:
            doc = doc.page_content
            matched_docs.append(doc)
        return matched_docs
    
    def _default_ensemble_processor(self, results):
        """默认的集成检索结果处理器"""
        matched_docs = []
        for doc in results:
            doc = doc.page_content
            matched_docs.append(doc)
        return matched_docs

    def _load_persistent_db(self):
        """加载持久化的向量数据库"""
        if os.path.exists(self.persistent_db_path):
            self.vectorstore_db = Chroma(
                collection_name=self.persistent_collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persistent_db_path
            )
            print(f"已加载持久化数据库，路径: {self.persistent_db_path}, 集合名: {self.persistent_collection_name}")
        else:
            raise ValueError(f"持久化数据库路径不存在: {self.persistent_db_path}")

    def add_documents_to_persistent_db(self, docs):
        """向持久化数据库添加新文档"""
        if not self.persistent_db:
            raise ValueError("未启用持久化数据库功能")
            
        documents = self.document_converter(docs)
        
        # 如果持久化数据库尚未加载，则加载它
        if self.vectorstore_db is None:
            self._load_persistent_db()
        
        # 添加文档
        self.vectorstore_db.add_documents(documents)
        
        # 持久化到磁盘
        self.vectorstore_db.persist()
        print(f"已向持久化数据库添加 {len(documents)} 个文档")

    def match_docs(self, user_input, docs=None, result_processor=None):
        """
        执行相似性搜索
        
        参数:
            user_input: 用户输入的查询
            docs: 要搜索的文档，如果为None且启用了持久化数据库，则使用持久化数据库
            result_processor: 可选的结果处理函数
        """
        if docs is not None:
            self._prepare_vectorstore_for_search(docs)

        results = self.vectorstore_db.similarity_search_with_score(user_input, k=self.topk)
        
        if docs is not None or not self.persistent_db:
            self._cleanup_vectorstore()

        # 处理结果
        processor = result_processor or self._default_similarity_processor
        return processor(results)

    def match_docs_with_bm25(self, user_input, docs=None, result_processor=None):
        """
        执行BM25和向量搜索的集成检索
        
        参数:
            user_input: 用户输入的查询
            docs: 要搜索的文档，如果为None且启用了持久化数据库，则使用持久化数据库
            result_processor: 可选的结果处理函数
        """
        if docs is not None:
            self._prepare_vectorstore_for_search(docs)
            
        # 先使用向量搜索获取topk*2的文档，而不是加载全部文档
        initial_retriever_results = self.vectorstore_db.similarity_search(
            user_input, 
            k=max(self.topk*10, 100)
        )
        
        # 创建BM25检索器
        bm25_retriever = BM25Retriever.from_documents(initial_retriever_results)
        bm25_retriever.k = self.topk
        
        # 创建集成检索器
        ensemble_retriever = EnsembleRetriever(
            retrievers=[self.vectorstore_db.as_retriever(search_kwargs={"k": self.topk}), bm25_retriever],
            weights=[self.embedding_weight, 1 - self.embedding_weight]
        )
        
        # 检索文档
        results = ensemble_retriever.get_relevant_documents(user_input)
        
        if docs is not None or not self.persistent_db:
            self._cleanup_vectorstore()
        
        # 处理结果
        processor = result_processor or self._default_ensemble_processor
        return processor(results[:self.topk])

    def retrieve_docs(self, user_input, docs, result_processor=None):
        """
        根据权重决定使用哪种匹配方法并执行搜索
        
        参数:
            user_input: 用户输入的查询
            docs: 要搜索的文档
            result_processor: 可选的结果处理函数
        """
        if self.embedding_weight < 1:
            return self.match_docs_with_bm25(user_input, docs, result_processor)
        else:
            return self.match_docs(user_input, docs, result_processor)