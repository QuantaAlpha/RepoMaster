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
    Get embedding model, decide whether to use standard OpenAI, Azure OpenAI or local model based on environment variables
    
    Args:
        model_name: Embedding model name, default is "text-embedding-ada-002"
        use_local_embedding: Whether to use local embedding model
        local_model_name: Local embedding model name
        
    Returns:
        Embedding model instance
    """
    if use_local_embedding:
        return HuggingFaceEmbeddings(model_name=local_model_name)
    
    # Prioritize Azure OpenAI
    if os.environ.get("AZURE_PAY_OPENAI_API_KEY"):
        # Handle Azure endpoint URL, ensure it only contains base URL part
        endpoint = os.environ.get("AZURE_PAY_OPENAI_ENDPOINT", "")
        # If endpoint contains full path, extract base URL
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
          
    
    # Use standard OpenAI
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
            
        # Persistent database settings
        self.persistent_db = persistent_db
        self.persistent_db_path = persistent_db_path
        self.persistent_collection_name = persistent_collection_name or "persistent_collection"
        self.vectorstore_db = None
        
        # If persistent database is enabled
        if persistent_db:
            if os.path.exists(self.persistent_db_path) and initial_docs is None:
                # If no initial documents provided but database path exists, load existing database
                print(f"Loading existing persistent database from {self.persistent_db_path}")
                self._load_persistent_db()
            elif initial_docs:
                # If initial documents provided, create new persistent database
                print(f"Creating persistent database with {len(initial_docs)} documents")
                self._prepare_vectorstore_for_search(initial_docs, persistent=True)
            else:
                raise ValueError(f"Persistent database is enabled but no initial documents provided and path does not exist: {self.persistent_db_path}")

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
        """Split a single Document object into multiple smaller Document objects
        
        Args:
            document: Document object to split
            
        Returns:
            List[Document]: List of split Document objects
        """
        # Use text_splitter to split document content
        splits = self.text_splitter.split_text(document.page_content)
        # Create new Document objects for each split, preserving original metadata
        return [Document(
            page_content=split,
            metadata=document.metadata
        ) for split in splits]

    def _prepare_vectorstore_for_search(self, docs, persistent=False):
        """Prepare documents and create vector store
            docs: Documents to process
            persistent: Whether to create persistent storage, default False
        """
        # First use document_converter to convert documents
        initial_documents = self.document_converter(docs)
        
        # Split each document
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
            # Calculate remaining document count
            remaining_docs = len(documents) - max_docs_iter
            # Calculate how many batches needed
            batch_count = (remaining_docs + slice_size - 1) // slice_size  # Round up
            print(f"Remaining {remaining_docs} documents, will be processed in {batch_count} batches, {slice_size} documents per batch")
            
            # Prepare batch document addition
            for batch_idx in range(batch_count):
                start_idx = max_docs_iter + batch_idx * slice_size
                end_idx = min(start_idx + slice_size, len(documents))
                batch_docs = documents[start_idx:end_idx]
                
                if batch_docs:
                    try:
                        # import pdb; pdb.set_trace()
                        self.vectorstore_db.add_documents(batch_docs)
                        print(f"Added batch {batch_idx+1}/{batch_count} documents, {len(batch_docs)} items", flush=True)
                    except Exception as e:
                        print(f"Error adding batch {batch_idx+1} documents: {e}", flush=True)
                        
                    # Brief pause after each batch to avoid API limits
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
            print(f"Created persistent database, path: {self.persistent_db_path}, collection name: {self.persistent_collection_name}", flush=True)
        
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
        """Default similarity search result processor"""
        matched_docs = []
        for doc, score in results:
            doc = doc.page_content
            matched_docs.append(doc)
        return matched_docs
    
    def _default_ensemble_processor(self, results):
        """Default ensemble retrieval result processor"""
        matched_docs = []
        for doc in results:
            doc = doc.page_content
            matched_docs.append(doc)
        return matched_docs

    def _load_persistent_db(self):
        """Load persistent vector database"""
        if os.path.exists(self.persistent_db_path):
            self.vectorstore_db = Chroma(
                collection_name=self.persistent_collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persistent_db_path
            )
            print(f"Loaded persistent database, path: {self.persistent_db_path}, collection name: {self.persistent_collection_name}")
        else:
            raise ValueError(f"Persistent database path does not exist: {self.persistent_db_path}")

    def add_documents_to_persistent_db(self, docs):
        """Add new documents to persistent database"""
        if not self.persistent_db:
            raise ValueError("Persistent database feature not enabled")
            
        documents = self.document_converter(docs)
        
        # If persistent database is not loaded yet, load it
        if self.vectorstore_db is None:
            self._load_persistent_db()
        
        # Add documents
        self.vectorstore_db.add_documents(documents)
        
        # Persist to disk
        self.vectorstore_db.persist()
        print(f"Added {len(documents)} documents to persistent database")

    def match_docs(self, user_input, docs=None, result_processor=None):
        """
        Execute similarity search
        
        Parameters:
            user_input: User input query
            docs: Documents to search, if None and persistent database is enabled, use persistent database
            result_processor: Optional result processing function
        """
        if docs is not None:
            self._prepare_vectorstore_for_search(docs)

        results = self.vectorstore_db.similarity_search_with_score(user_input, k=self.topk)
        
        if docs is not None or not self.persistent_db:
            self._cleanup_vectorstore()

        # Process results
        processor = result_processor or self._default_similarity_processor
        return processor(results)

    def match_docs_with_bm25(self, user_input, docs=None, result_processor=None):
        """
        Execute BM25 and vector search ensemble retrieval
        
        Parameters:
            user_input: User input query
            docs: Documents to search, if None and persistent database is enabled, use persistent database
            result_processor: Optional result processing function
        """
        if docs is not None:
            self._prepare_vectorstore_for_search(docs)
            
        # First use vector search to get topk*2 documents instead of loading all documents
        initial_retriever_results = self.vectorstore_db.similarity_search(
            user_input, 
            k=max(self.topk*10, 100)
        )
        
        # Create BM25 retriever
        bm25_retriever = BM25Retriever.from_documents(initial_retriever_results)
        bm25_retriever.k = self.topk
        
        # Create ensemble retriever
        ensemble_retriever = EnsembleRetriever(
            retrievers=[self.vectorstore_db.as_retriever(search_kwargs={"k": self.topk}), bm25_retriever],
            weights=[self.embedding_weight, 1 - self.embedding_weight]
        )
        
        # Retrieve documents
        results = ensemble_retriever.get_relevant_documents(user_input)
        
        if docs is not None or not self.persistent_db:
            self._cleanup_vectorstore()
        
        # Process results
        processor = result_processor or self._default_ensemble_processor
        return processor(results[:self.topk])

    def retrieve_docs(self, user_input, docs, result_processor=None):
        """
        Decide which matching method to use based on weight and execute search
        
        Parameters:
            user_input: User input query
            docs: Documents to search
            result_processor: Optional result processing function
        """
        if self.embedding_weight < 1:
            return self.match_docs_with_bm25(user_input, docs, result_processor)
        else:
            return self.match_docs(user_input, docs, result_processor)