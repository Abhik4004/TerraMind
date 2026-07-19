# src/graph/workflow.py
from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.graph.nodes import (
    check_cache,
    parse_query,
    direct_response,
    select_tools,
    retrieve,
    grade_documents,
    execute_tools,
    generate,
    check_hallucination,
    check_answer,
    format_final_answer,
    increment_retry
)

def should_use_cache(state: GraphState) -> str:
    """
    Cache hit ends the run; a miss continues into the retrieval chain.
    """
    if state.get("final_answer"):
        print("---DECISION: USE CACHED RESPONSE---")
        return "end"
    else:
        print("---DECISION: CACHE MISS, RUN RETRIEVAL CHAIN---")
        return "select_tools"


def route_after_parse(state: GraphState) -> str:
    """
    Intent gate. Trivial small-talk (greetings, thanks, capability questions)
    gets an immediate canned reply and never touches the cache, the vector
    store, the tools or an LLM. Everything else goes to the cache lookup and
    then the full retrieval chain.

    This runs on the user's own words: the location block the frontend appends
    is stripped first, so "hi" with a pin dropped is still a greeting.
    """
    if state.get("location_context", {}).get("smalltalk_type"):
        print("---DECISION: SMALL-TALK → IMMEDIATE RESPONSE---")
        return "direct_response"
    print("---DECISION: REAL QUERY → CACHE, THEN RETRIEVAL CHAIN---")
    return "check_cache"


def grade_generation_grounded(state: GraphState) -> str:
    """
    Check if generation is grounded in documents.
    """
    if state.get("hallucination_score") == "pass":
        print("---DECISION: GENERATION IS GROUNDED---")
        return "check_answer"
    else:
        print("---DECISION: GENERATION IS NOT GROUNDED, RETRY---")
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:
            print("---MAX RETRIES REACHED, PROCEEDING WITH ANSWER---")
            return "check_answer"
        return "increment_retry"

def grade_answer_useful(state: GraphState) -> str:
    """
    Check if answer is useful.
    """
    if state.get("answer_score") == "pass":
        print("---DECISION: ANSWER IS USEFUL---")
        return "format_final"
    else:
        print("---DECISION: ANSWER NOT USEFUL, RETRY---")
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:
            print("---MAX RETRIES REACHED, FORMATTING CURRENT ANSWER---")
            return "format_final"
        return "increment_retry"

def build_graph():
    """
    Build the LangGraph workflow for land analysis with caching and tool selection.
    """
    workflow = StateGraph(GraphState)

    # Define nodes
    workflow.add_node("check_cache", check_cache)
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("direct_response", direct_response)
    workflow.add_node("select_tools", select_tools)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("generate", generate)
    workflow.add_node("check_hallucination", check_hallucination)
    workflow.add_node("check_answer", check_answer)
    workflow.add_node("format_final", format_final_answer)
    workflow.add_node("increment_retry", increment_retry)

    # Build graph — INTENT FIRST. Classify what the user wants before spending
    # anything: a greeting never touches the cache, the vector store or an LLM.
    workflow.set_entry_point("parse_query")

    # Parse/intent -> immediate reply OR cache lookup -> full pipeline
    workflow.add_conditional_edges(
        "parse_query",
        route_after_parse,
        {
            "direct_response": "direct_response",
            "check_cache": "check_cache",
        },
    )

    # Cache hit ends the run; a miss continues into the retrieval chain.
    workflow.add_conditional_edges(
        "check_cache",
        should_use_cache,
        {
            "end": END,
            "select_tools": "select_tools",
        }
    )

    # Direct response -> END (bypasses the rest of the pipeline)
    workflow.add_edge("direct_response", END)

    # Select tools -> Retrieve
    workflow.add_edge("select_tools", "retrieve")

    # Retrieve -> Grade documents
    workflow.add_edge("retrieve", "grade_documents")

    # Grade documents -> Execute tools (always proceed regardless of relevance)
    workflow.add_edge("grade_documents", "execute_tools")

    # Execute tools -> Generate
    workflow.add_edge("execute_tools", "generate")

    # Generate -> Check hallucination
    workflow.add_edge("generate", "check_hallucination")

    # Check hallucination -> Conditional edge
    workflow.add_conditional_edges(
        "check_hallucination",
        grade_generation_grounded,
        {
            "check_answer": "check_answer",
            "increment_retry": "increment_retry"
        }
    )

    # Increment retry -> Generate
    workflow.add_edge("increment_retry", "generate")

    # Check answer -> Conditional edge
    workflow.add_conditional_edges(
        "check_answer",
        grade_answer_useful,
        {
            "format_final": "format_final",
            "increment_retry": "increment_retry"
        }
    )

    # Format final -> END
    workflow.add_edge("format_final", END)

    # Compile
    app = workflow.compile()

    return app

# Create the app
land_analysis_graph = build_graph()