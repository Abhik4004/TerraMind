import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.graph.workflow import land_analysis_graph
from src.config.settings import settings
from src.rag.rag_pipeline import RAGPipeline, RAGCONFIG
from src.utils.cache_manager import cache_manager
from pprint import pprint

def initialize_system():
    """Initialize the system - create vector store if needed"""
    print("Initializing Land Analysis System...")
    print("="*80)

    # Initialize RAG pipeline
    rag = RAGPipeline(RAGCONFIG)

    # Check if vector store exists
    if not rag.vector_store_exists():
        print("⚠️  Vector store not found. Creating new vector store...")

        # Check if data directory has files
        data_dir = Path(settings.DATA_DIR)
        geojson_files = list(data_dir.glob("*.geojson"))

        if not geojson_files:
            print("❌ Error: No GeoJSON files found in src/data/ directory")
            print(f"   Please add .geojson files to: {data_dir}")
            print("   Then run the initialization again.")
            return False

        print(f"📂 Found {len(geojson_files)} GeoJSON file(s)")
        print("🔄 Creating vector store (this may take a few minutes)...")

        try:
            rag.ingestion_vs()
            print("✅ Vector store created successfully!")
        except Exception as e:
            print(f"❌ Error creating vector store: {e}")
            return False
    else:
        print("✅ Vector store already exists. Ready to use!")

    # Display cache stats
    stats = cache_manager.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"  - Response cache: {stats['response_cache']} entries")
    print(f"  - Embedding cache: {stats['embedding_cache']} entries")
    print(f"  - Tool cache: {stats['tool_cache']} entries")
    print(f"  - Total size: {stats['total_size_mb']:.2f} MB")
    print("="*80 + "\n")

    return True

def run_query(question: str, chat_history: list = None):
    """
    Run a query through the land analysis graph.

    Args:
        question: User's question
        chat_history: Previous conversation history

    Returns:
        Final answer with sources
    """
    if chat_history is None:
        chat_history = []

    # Initial state
    inputs = {
        "question": question,
        "chat_history": chat_history,
        "documents": [],
        "generation": "",
        "coordinates": {},
        "location_context": {},
        "tool_results": {},
        "selected_tools": [],
        "relevance_score": "",
        "hallucination_score": "",
        "answer_score": "",
        "retry_count": 0,
        "cache_key": "",
        "cached_response": {},
        "sources": [],
        "final_answer": ""
    }

    # Run the graph
    print(f"\n{'='*80}")
    print(f"Processing: {question}")
    print(f"{'='*80}\n")

    result = land_analysis_graph.invoke(inputs)

    return result

def main():
    """Main function to run the application"""
    # Initialize system
    if not initialize_system():
        print("\n❌ System initialization failed. Please fix the errors and try again.")
        return

    print("\n" + "="*80)
    print("LAND ANALYSIS SYSTEM - LangGraph with Self-RAG, Caching & Tool Selection")
    print("="*80 + "\n")

    # Example queries
    queries = [
        "What is the best location for tea gardening?",
        "What's the soil type at 22.5726° N, 88.3639° E?",
        "Analyze the land characteristics for construction at coordinates 23.5, 87.2",
        "What's the weather and road network at 22.57, 88.36?",
    ]

    chat_history = []

    for query in queries:
        result = run_query(query, chat_history)

        print("\n" + "="*80)
        print("FINAL ANSWER")
        print("="*80 + "\n")
        print(result.get("final_answer", result.get("generation", "No answer generated")))
        print("\n" + "="*80)

        # Update chat history
        chat_history.append({
            "role": "user",
            "content": query
        })
        chat_history.append({
            "role": "assistant",
            "content": result.get("final_answer", result.get("generation", ""))
        })

        # Show cache stats
        stats = cache_manager.get_cache_stats()
        print(f"\nCache Stats: {stats['total_entries']} total entries ({stats['total_size_mb']:.2f} MB)")

        print("\n" + "="*80 + "\n")
        input("Press Enter to continue to next query...")

def interactive_mode():
    """Run in interactive mode"""
    if not initialize_system():
        print("\n❌ System initialization failed. Please fix the errors and try again.")
        return

    print("\n" + "="*80)
    print("LAND ANALYSIS SYSTEM - Interactive Mode")
    print("="*80)
    print("Commands:")
    print("  - Type your question")
    print("  - 'cache' - Show cache statistics")
    print("  - 'clear' - Clear all caches")
    print("  - 'exit' - Quit")
    print("="*80 + "\n")

    chat_history = []

    while True:
        query = input("\n🌍 You: ").strip()

        if query.lower() in ['exit', 'quit', 'q']:
            print("Goodbye! 👋")
            break

        if query.lower() == 'cache':
            stats = cache_manager.get_cache_stats()
            print(f"\n📊 Cache Statistics:")
            print(f"  Response cache: {stats['response_cache']} entries")
            print(f"  Embedding cache: {stats['embedding_cache']} entries")
            print(f"  Tool cache: {stats['tool_cache']} entries")
            print(f"  Total size: {stats['total_size_mb']:.2f} MB")
            continue

        if query.lower() == 'clear':
            count = cache_manager.clear_all()
            print(f"\n🗑️  Cleared {count} cache entries")
            continue

        if not query:
            continue

        print("\n🔄 Processing...\n")

        result = run_query(query, chat_history)

        answer = result.get("final_answer", result.get("generation", "No answer generated"))
        print(f"\n🤖 Assistant:\n{answer}\n")

        # Update chat history
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": answer})

def benchmark_mode():
    """Run benchmark queries to test performance"""
    if not initialize_system():
        print("\n❌ System initialization failed. Please fix the errors and try again.")
        return

    print("\n" + "="*80)
    print("BENCHMARK MODE - Testing Cache Performance")
    print("="*80 + "\n")

    test_query = "What is the best location for tea gardening?"

    # First run - cache miss
    print("Run 1 (Cache Miss):")
    import time
    start = time.time()
    result1 = run_query(test_query)
    time1 = time.time() - start
    print(f"Time: {time1:.2f}s\n")

    # Second run - cache hit
    print("Run 2 (Cache Hit):")
    start = time.time()
    result2 = run_query(test_query)
    time2 = time.time() - start
    print(f"Time: {time2:.2f}s\n")

    print(f"Performance Improvement: {((time1 - time2) / time1 * 100):.1f}% faster")
    print("="*80)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Land Analysis System")
    parser.add_argument(
        "--mode",
        choices=["demo", "interactive", "benchmark"],
        default="demo",
        help="Run mode: demo (example queries), interactive (chat), or benchmark (performance test)"
    )

    args = parser.parse_args()

    if args.mode == "interactive":
        interactive_mode()
    elif args.mode == "benchmark":
        benchmark_mode()
    else:
        main()