from typing import List, Dict, Any, TypedDict, Annotated
import operator

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: The user's question
        generation: LLM generation
        documents: List of retrieved documents
        chat_history: Conversation history
        coordinates: Extracted coordinates (lat, lon)
        location_context: Location information
        tool_results: Results from external tools
        selected_tools: List of tools selected for execution
        relevance_score: Document relevance score
        hallucination_score: Hallucination check score
        answer_score: Answer quality score
        retry_count: Number of retries
        cache_key: Key for caching the query/response
        cached_response: Previously cached response if available
        sources: List of sources used to generate the answer
        final_answer: The final formatted answer
        use_cache: Per-request switch to bypass the response cache
    """
    question: str
    use_cache: bool
    generation: str
    documents: List[str]
    chat_history: Annotated[List[Dict], operator.add]
    coordinates: Dict[str, float]
    location_context: Dict[str, Any]
    tool_results: Annotated[Dict[str, Any], operator.or_]
    selected_tools: List[str]
    relevance_score: str
    hallucination_score: str
    answer_score: str
    retry_count: int
    cache_key: str
    cached_response: Dict[str, Any]
    sources: List[Dict[str, str]]
    final_answer: str