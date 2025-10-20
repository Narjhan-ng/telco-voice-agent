"""
Knowledge Base RAG System

This module implements the Retrieval Augmented Generation system that allows
the AI agent to access and reason over the troubleshooting documentation.

Architecture:
1. Documents are loaded from knowledge_base/ directory
2. Documents are split into chunks for better retrieval
3. Chunks are embedded using sentence-transformers
4. Embeddings are stored in ChromaDB vector store
5. At runtime, relevant chunks are retrieved based on user query

Why RAG?
- Agent doesn't need entire knowledge base in prompt (token efficiency)
- Can scale to large documentation without hitting context limits
- Retrieves only relevant information for each specific problem
- Easy to update knowledge base without retraining
"""

from pathlib import Path
from typing import List
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document


class KnowledgeBase:
    """
    Manages the RAG knowledge base for technical troubleshooting documentation.

    The knowledge base uses:
    - HuggingFace embeddings (sentence-transformers) for local, free embeddings
    - ChromaDB for vector storage and similarity search
    - RecursiveCharacterTextSplitter for intelligent document chunking
    """

    def __init__(
        self,
        knowledge_base_path: str = "knowledge_base",
        persist_directory: str = ".chromadb",
        collection_name: str = "telco_support"
    ):
        """
        Initialize the knowledge base system.

        Args:
            knowledge_base_path: Path to directory containing markdown docs
            persist_directory: Where to store ChromaDB data
            collection_name: Name for the vector store collection
        """
        self.knowledge_base_path = Path(knowledge_base_path)
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Initialize embeddings
        # Using all-MiniLM-L6-v2: small, fast, good quality
        # Alternative: all-mpnet-base-v2 (larger, better quality)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},  # Use 'cuda' if GPU available
            encode_kwargs={'normalize_embeddings': True}
        )

        # Initialize or load vector store
        self.vectorstore = None
        self._initialize_vectorstore()

    def _initialize_vectorstore(self):
        """
        Initialize the vector store, either by loading existing or creating new.

        Why check if exists?
        - Building embeddings takes time (especially first time)
        - If already built, just load from disk (much faster)
        - Rebuild only when knowledge base changes
        """
        persist_path = Path(self.persist_directory)

        if persist_path.exists() and len(list(persist_path.iterdir())) > 0:
            # Vector store already exists, load it
            print(f"Loading existing vector store from {self.persist_directory}")
            self.vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
        else:
            # Need to build vector store from documents
            print(f"Building vector store from {self.knowledge_base_path}")
            self._build_vectorstore()

    def _build_vectorstore(self):
        """
        Build the vector store from knowledge base documents.

        Process:
        1. Load all .md files from knowledge_base/
        2. Split documents into chunks
        3. Create embeddings for each chunk
        4. Store in ChromaDB
        """
        # Load all markdown files
        if not self.knowledge_base_path.exists():
            raise FileNotFoundError(f"Knowledge base path not found: {self.knowledge_base_path}")

        loader = DirectoryLoader(
            str(self.knowledge_base_path),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'}
        )

        documents = loader.load()

        if not documents:
            raise ValueError(f"No documents found in {self.knowledge_base_path}")

        print(f"Loaded {len(documents)} documents")

        # Split documents into chunks
        # Why chunk?
        # - Better retrieval precision (find exact relevant section)
        # - Fit into LLM context window more efficiently
        # - Balance between too small (lose context) and too large (retrieve irrelevant info)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # ~250 tokens, good balance
            chunk_overlap=200,  # Overlap to maintain context across chunks
            length_function=len,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""]  # Split on markdown headers first
        )

        splits = text_splitter.split_documents(documents)
        print(f"Split into {len(splits)} chunks")

        # Create vector store
        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            collection_name=self.collection_name,
            persist_directory=self.persist_directory
        )

        print(f"Vector store created and persisted to {self.persist_directory}")

    def retrieve(self, query: str, k: int = 3) -> List[Document]:
        """
        Retrieve the most relevant documents for a query.

        Args:
            query: The user's question or problem description
            k: Number of documents to retrieve (default 3)

        Returns:
            List of Document objects with relevant content

        How it works:
        1. Query is embedded into same vector space as documents
        2. Similarity search finds k nearest neighbors
        3. Returns documents ordered by relevance

        Why k=3?
        - Balance between having enough context and not overloading prompt
        - 3 chunks ≈ 750 tokens of context
        - Can be tuned based on needs
        """
        if not self.vectorstore:
            raise ValueError("Vector store not initialized")

        # Perform similarity search
        docs = self.vectorstore.similarity_search(query, k=k)

        return docs

    def retrieve_with_scores(self, query: str, k: int = 3) -> List[tuple]:
        """
        Retrieve documents with similarity scores.

        Useful for debugging and understanding what the RAG is finding.

        Returns:
            List of (Document, score) tuples
        """
        if not self.vectorstore:
            raise ValueError("Vector store not initialized")

        docs_and_scores = self.vectorstore.similarity_search_with_score(query, k=k)

        return docs_and_scores

    def rebuild_vectorstore(self):
        """
        Force rebuild the vector store from scratch.

        Use this when:
        - Knowledge base documents have been updated
        - Want to change chunking strategy
        - Corrupted vector store

        WARNING: This will delete existing vector store and rebuild from docs.
        Takes time on first run (embeddings generation).
        """
        import shutil

        # Delete existing vector store
        if Path(self.persist_directory).exists():
            shutil.rmtree(self.persist_directory)
            print(f"Deleted existing vector store at {self.persist_directory}")

        # Rebuild
        self._build_vectorstore()

    def get_retriever(self, search_kwargs: dict = None):
        """
        Get a LangChain retriever object for use in chains.

        This is the interface that LangChain agents use to query the knowledge base.

        Args:
            search_kwargs: Arguments for retriever (e.g., {"k": 3})

        Returns:
            LangChain retriever object
        """
        if not self.vectorstore:
            raise ValueError("Vector store not initialized")

        if search_kwargs is None:
            search_kwargs = {"k": 3}

        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)
