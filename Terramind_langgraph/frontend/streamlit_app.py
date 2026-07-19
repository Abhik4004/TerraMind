# frontend/streamlit_app.py
"""
Streamlit UI for TerraMind LangGraph Land Analysis System
"""
import streamlit as st
import requests
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="TerraMind - Land Analysis AI",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E7D32;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E7D32;
    }
    .source-card {
        background-color: #e8f5e9;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stChatMessage {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_count" not in st.session_state:
    st.query_count = 0

# API Helper Functions
def make_api_request(endpoint: str, method: str = "GET", data: Dict = None):
    """Make API request with error handling"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def query_land_analysis(query: str, session_id: str = None, use_cache: bool = True):
    """Query the land analysis API"""
    data = {
        "query": query,
        "session_id": session_id,
        "use_cache": use_cache
    }
    return make_api_request("/api/query", method="POST", data=data)

def get_cache_stats():
    """Get cache statistics"""
    return make_api_request("/api/cache/stats")

def get_health():
    """Get system health"""
    return make_api_request("/api/health")

def get_tools():
    """Get available tools"""
    return make_api_request("/api/tools")

def clear_cache(cache_type: str = None):
    """Clear cache"""
    endpoint = "/api/cache/clear"
    if cache_type:
        endpoint += f"?cache_type={cache_type}"
    return make_api_request(endpoint, method="POST")

# Sidebar
with st.sidebar:
    st.markdown("## 🌍 TerraMind")
    st.markdown("### AI-Powered Land Analysis")

    st.markdown("---")

    # System Health
    st.markdown("### 📊 System Status")
    health = get_health()
    if health:
        status_color = "🟢" if health["status"] == "healthy" else "🟡"
        st.markdown(f"{status_color} **Status:** {health['status'].capitalize()}")
        st.markdown(f"📦 Vector Store: {'✓' if health['vector_store_ready'] else '✗'}")
        st.markdown(f"💾 Cache: {'✓' if health['cache_operational'] else '✗'}")
        st.markdown(f"🤖 LLM: {'✓' if health['llm_available'] else '✗'}")
        st.markdown(f"⏱️ Uptime: {health['uptime_seconds']/60:.1f} min")

    st.markdown("---")

    # Cache Statistics
    st.markdown("### 💾 Cache Statistics")
    cache_stats = get_cache_stats()
    if cache_stats:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Response", cache_stats["response_cache"])
            st.metric("Embedding", cache_stats["embedding_cache"])
        with col2:
            st.metric("Tool", cache_stats["tool_cache"])
            st.metric("Size (MB)", f"{cache_stats['total_size_mb']:.2f}")

        # Cache controls
        if st.button("🗑️ Clear All Cache"):
            result = clear_cache()
            if result:
                st.success(f"Cleared {result.get('message', 'cache')}")
                st.rerun()

    st.markdown("---")

    # Session Info
    st.markdown("### 💬 Session")
    if st.session_state.session_id:
        st.markdown(f"**ID:** `{st.session_state.session_id[:8]}...`")
        st.markdown(f"**Messages:** {len(st.session_state.messages)}")
        if st.button("🔄 New Session"):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()
    else:
        st.markdown("*No active session*")

    st.markdown("---")

    # Settings
    st.markdown("### ⚙️ Settings")
    use_cache = st.checkbox("Use Cache", value=True, help="Use cached responses when available")
    show_sources = st.checkbox("Show Sources", value=True, help="Display source attribution")
    show_tools = st.checkbox("Show Tools", value=True, help="Display tools used")

# Main Content
st.markdown('<div class="main-header">🌍 TerraMind Land Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Geospatial Intelligence with Self-RAG</div>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "🔧 Tools", "📊 Analytics", "📚 Documentation"])

# Tab 1: Chat Interface
with tab1:
    # Example queries
    st.markdown("### 💡 Example Queries")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🌱 Best for tea gardening?"):
            st.session_state.example_query = "What is the best location for tea gardening?"
    with col2:
        if st.button("🏗️ Construction suitability"):
            st.session_state.example_query = "Analyze land at 22.5726° N, 88.3639° E for construction"
    with col3:
        if st.button("🌦️ Weather & roads"):
            st.session_state.example_query = "What's the weather and road network at 23.5, 87.2?"

    st.markdown("---")

    # Chat display
    st.markdown("### 💬 Conversation")
    chat_container = st.container()

    with chat_container:
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]

            with st.chat_message(role):
                st.markdown(content)

                # Show metadata for assistant messages
                if role == "assistant" and "metadata" in message:
                    meta = message["metadata"]

                    # Processing info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        cache_icon = "⚡" if meta.get("from_cache") else "🔄"
                        st.caption(f"{cache_icon} {meta.get('processing_time', 0):.2f}s")
                    with col2:
                        if meta.get("tools_used"):
                            st.caption(f"🔧 {len(meta['tools_used'])} tools")
                    with col3:
                        if meta.get("sources"):
                            st.caption(f"📄 {len(meta['sources'])} sources")

                    # Show tools if enabled
                    if show_tools and meta.get("tools_used"):
                        with st.expander("🔧 Tools Used"):
                            for tool in meta["tools_used"]:
                                st.markdown(f"- `{tool}`")

                    # Show sources if enabled
                    if show_sources and meta.get("sources"):
                        with st.expander("📚 Sources"):
                            for idx, source in enumerate(meta["sources"], 1):
                                source_type = source.get("type", "unknown")
                                st.markdown(f"**{idx}. {source_type.capitalize()}**")

                                if source_type == "document":
                                    st.markdown(f"- File: `{source.get('metadata', {}).get('source', 'N/A')}`")
                                    relevance = source.get('relevance_score')
                                    if relevance is not None:
                                        st.markdown(f"- Relevance: {relevance:.2f}")
                                elif source_type == "tool":
                                    st.markdown(f"- Tool: `{source.get('tool_name')}`")
                                    st.markdown(f"- Status: {'✓' if source.get('success') else '✗'}")

    # Chat input
    if "example_query" in st.session_state:
        default_query = st.session_state.example_query
        del st.session_state.example_query
    else:
        default_query = ""

    user_query = st.chat_input("Ask about land analysis, soil types, weather, construction suitability...",
                               key="chat_input")

    if default_query:
        user_query = default_query

    if user_query:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_query})

        # Display user message
        with st.chat_message("user"):
            st.markdown(user_query)

        # Get response from API
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = query_land_analysis(
                    user_query,
                    session_id=st.session_state.session_id,
                    use_cache=use_cache
                )

                if response:
                    # Update session ID
                    if not st.session_state.session_id:
                        st.session_state.session_id = response["session_id"]

                    # Display answer
                    st.markdown(response["answer"])

                    # Store message with metadata
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "metadata": {
                            "tools_used": response.get("tools_used", []),
                            "sources": response.get("sources", []),
                            "from_cache": response.get("from_cache", False),
                            "processing_time": response.get("processing_time", 0)
                        }
                    })

                    st.rerun()
                else:
                    st.error("Failed to get response from API")

# Tab 2: Tools
with tab2:
    st.markdown("### 🔧 Available Tools")
    st.markdown("The system can automatically select and use these tools based on your query:")

    tools = get_tools()
    if tools:
        for tool in tools:
            with st.expander(f"**{tool['name']}**"):
                st.markdown(f"**Description:** {tool['description']}")
                st.markdown("**Use Cases:**")
                for use_case in tool['use_cases']:
                    st.markdown(f"- {use_case}")

    st.markdown("---")

    st.markdown("### 🎯 Tool Selection Test")
    test_query = st.text_input("Enter a query to see which tools would be selected:")

    if st.button("Test Tool Selection") and test_query:
        result = make_api_request(f"/api/tools/select?query={test_query}", method="POST")
        if result:
            st.markdown(f"**Query:** {result['query']}")
            st.markdown(f"**Selected Tools:** `{', '.join(result['selected_tools'])}`")
            st.markdown(f"**Reasoning:** {result['reasoning']}")
            st.markdown(f"**Requires Coordinates:** {result['requires_coordinates']}")

# Tab 3: Analytics
with tab3:
    st.markdown("### 📊 System Analytics")

    col1, col2, col3, col4 = st.columns(4)

    if cache_stats:
        with col1:
            st.metric("Total Cache Entries", cache_stats["total_entries"])
        with col2:
            st.metric("Response Cache", cache_stats["response_cache"])
        with col3:
            st.metric("Embedding Cache", cache_stats["embedding_cache"])
        with col4:
            st.metric("Cache Size (MB)", f"{cache_stats['total_size_mb']:.2f}")

    # Cache distribution chart
    if cache_stats and cache_stats["total_entries"] > 0:
        st.markdown("### 📈 Cache Distribution")

        cache_data = {
            "Type": ["Response", "Embedding", "Tool"],
            "Count": [
                cache_stats["response_cache"],
                cache_stats["embedding_cache"],
                cache_stats["tool_cache"]
            ]
        }

        fig = px.pie(cache_data, values="Count", names="Type",
                     title="Cache Entry Distribution",
                     color_discrete_sequence=px.colors.sequential.Greens)
        st.plotly_chart(fig, use_container_width=True)

    # Session history
    if st.session_state.messages:
        st.markdown("### 📜 Session History")

        # Create dataframe
        history_data = []
        for idx, msg in enumerate(st.session_state.messages):
            if msg["role"] == "assistant" and "metadata" in msg:
                meta = msg["metadata"]
                history_data.append({
                    "Query #": idx // 2 + 1,
                    "From Cache": "✓" if meta.get("from_cache") else "✗",
                    "Processing Time (s)": f"{meta.get('processing_time', 0):.2f}",
                    "Tools Used": len(meta.get("tools_used", [])),
                    "Sources": len(meta.get("sources", []))
                })

        if history_data:
            df = pd.DataFrame(history_data)
            st.dataframe(df, use_container_width=True)

            # Performance chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["Query #"],
                y=df["Processing Time (s)"].astype(float),
                marker_color=['green' if x == "✓" else 'blue' for x in df["From Cache"]],
                text=df["From Cache"],
                textposition='auto'
            ))
            fig.update_layout(
                title="Query Processing Time",
                xaxis_title="Query Number",
                yaxis_title="Time (seconds)",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

# Tab 4: Documentation
with tab4:
    st.markdown("### 📚 Documentation")

    st.markdown("""
    ## How to Use TerraMind
    
    ### 🎯 Query Types
    
    **1. General Land Analysis**
    - "What is the best location for tea gardening?"
    - "Analyze soil conditions for agriculture"
    
    **2. Location-Specific Queries**
    - "What's the soil type at 22.5726° N, 88.3639° E?"
    - "Is 23.5, 87.2 suitable for construction?"
    
    **3. Weather & Climate**
    - "What's the weather at coordinates X, Y?"
    - "Compare climate between two locations"
    
    **4. Infrastructure**
    - "Analyze road network at location X"
    - "What's the connectivity of this area?"
    
    **5. Risk Assessment**
    - "What's the flood risk at these coordinates?"
    - "Assess construction risks for this land"
    
    ### 🔍 Features
    
    - **⚡ Smart Caching**: Instant responses for repeated queries
    - **🤖 AI Tool Selection**: Automatically selects relevant tools
    - **📊 Self-RAG**: Ensures grounded, high-quality answers
    - **📚 Source Attribution**: Full transparency on data sources
    - **💬 Session Memory**: Maintains conversation context
    
    ### 🎨 Tips
    
    1. **Be Specific**: Include coordinates for location-specific queries
    2. **Use Cache**: Leave cache enabled for faster responses
    3. **Check Sources**: Review sources for data transparency
    4. **Clear Sessions**: Start new session for unrelated topics
    
    ### 🔧 API Endpoints
    
    - `POST /api/query` - Submit analysis query
    - `GET /api/cache/stats` - Get cache statistics
    - `GET /api/tools` - List available tools
    - `GET /api/health` - System health check
    
    ### 📞 Support
    
    For issues or questions, check the system logs or contact support.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; padding: 1rem;">
    TerraMind v1.0.0 | Powered by LangGraph + Self-RAG | Built with Streamlit
</div>
""", unsafe_allow_html=True)

# Auto-refresh health status every 30 seconds
if st.session_state.get("auto_refresh", False):
    import time
    time.sleep(30)
    st.rerun()