"""
LLM + embedding provider factory.

Selects the backend by env var so the same code runs on a dev machine with
Ollama and on a 1 GB EC2 free-tier box with Groq + fastembed (no local model
weights, no GPU/RAM-heavy inference process in the container).

  LLM_PROVIDER   = ollama (default) | groq
  EMBED_PROVIDER = ollama (default) | fastembed
"""
from src.config.settings import settings


def get_llm(temperature: float = None):
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    provider = settings.LLM_PROVIDER

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.GROQ_MODEL,
            temperature=temperature,
            api_key=settings.GROQ_API_KEY,
        )

    from langchain_ollama import ChatOllama
    return ChatOllama(model=settings.LLM_MODEL, temperature=temperature)


def get_embeddings():
    provider = settings.EMBED_PROVIDER

    if provider == "fastembed":
        from langchain_community.embeddings import FastEmbedEmbeddings
        # Small ONNX model, CPU-only, no torch — fits a 1 GB instance.
        return FastEmbedEmbeddings(model_name=settings.FASTEMBED_MODEL)

    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(model=settings.EMBEDDING_MODEL)
