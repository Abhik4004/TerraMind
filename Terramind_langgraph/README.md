# TerraMind LangGraph - Land Analysis System

A sophisticated land analysis system built with LangGraph and Self-RAG (Retrieval-Augmented Generation) capabilities for geospatial queries.

## Features

- **Self-RAG Architecture**: Implements document grading, hallucination checking, and answer validation
- **Geospatial Analysis**: Analyzes land characteristics, soil types, construction suitability
- **Coordinate Parsing**: Automatically extracts and validates coordinates from queries
- **Weather & Road Network Integration**: Ready for external tool integration
- **Vector Store**: Uses Chroma for efficient document retrieval
- **Iterative Refinement**: Automatically retries generation if quality checks fail

## Architecture

```
User Query
    ↓
Parse Query (Extract Coordinates)
    ↓
Retrieve Documents (RAG)
    ↓
Grade Documents (Relevance Check)
    ↓
Generate Answer
    ↓
Check Hallucination (Grounding Check)
    ↓
Check Answer Quality
    ↓
Final Answer
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
# Add any API keys or configuration here
```

4. Prepare your GeoJSON data files in `src/data/`

## Usage

### Demo Mode (Example Queries)
```bash
python main.py --mode demo
```

### Interactive Mode (Chat)
```bash
python main.py --mode interactive
```

### Programmatic Usage
```python
from src.graph.workflow import land_analysis_graph

# Prepare input
inputs = {
    "question": "What's the soil type at 22.5726° N, 88.3639° E?",
    "chat_history": [],
    "documents": [],
    # ... other fields
}

# Run
result = land_analysis_graph.invoke(inputs)
print(result["final_answer"])
```

## Project Structure

```
terramind-langgraph/
├── src/
│   ├── config/          # Configuration settings
│   ├── rag/             # RAG pipeline
│   ├── chains/          # LLM chains (graders, generator)
│   ├── graph/           # LangGraph workflow
│   ├── tools/           # External tools (weather, roads, etc.)
│   └── utils/           # Utilities (coordinate parsing, formatting)
├── tests/               # Unit tests
├── main.py              # Main application
└── requirements.txt     # Dependencies
```

## Key Components

### 1. Document Grader
Evaluates relevance of retrieved documents to the query.

### 2. Hallucination Grader
Checks if generated answers are grounded in source documents.

### 3. Answer Grader
Validates if the answer adequately addresses the user's question.

### 4. Generator
Produces comprehensive land analysis responses with:
- Location context and coordinates
- Numeric data with units
- Pros and cons analysis
- Housing recommendations (when applicable)

## Example Queries

- "What is the best location for tea gardening?"
- "Analyze the soil at coordinates 22.5726° N, 88.3639° E"
- "Is this location suitable for construction: 23.5, 87.2?"
- "What's the flood risk at these coordinates?"

## Configuration

Modify `src/config/settings.py` to adjust:
- LLM model
- Embedding model
- Retrieval parameters
- Vector store settings
- Retry limits

## Adding New Tools

1. Create tool module in `src/tools/`
2. Add tool invocation in `src/graph/nodes.py`
3. Update the generator prompt to handle tool results

## Testing

```bash
pytest tests/
```

## Self-RAG Workflow

The system implements a self-correcting workflow:

1. **Retrieval**: Fetches relevant documents from vector store
2. **Grading**: Validates document relevance
3. **Generation**: Creates answer using documents
4. **Hallucination Check**: Ensures answer is grounded in facts
5. **Answer Check**: Validates answer quality
6. **Retry Logic**: Regenerates if checks fail (max 3 retries)

## License

MIT License

## Acknowledgments

- Built with LangChain and LangGraph
- Uses Ollama for local LLM inference
- Chroma for vector storage