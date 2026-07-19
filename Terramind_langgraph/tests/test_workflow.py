# tests/test_workflow.py
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.graph.workflow import land_analysis_graph
from src.graph.state import GraphState

class TestWorkflow:
    """Test the LangGraph workflow"""

    @pytest.fixture
    def basic_state(self):
        """Create a basic state for testing"""
        return {
            "question": "What is the best location for tea gardening?",
            "chat_history": [],
            "documents": [],
            "generation": "",
            "coordinates": {},
            "location_context": {},
            "tool_results": {},
            "relevance_score": "",
            "hallucination_score": "",
            "answer_score": "",
            "retry_count": 0,
            "web_search_needed": False,
            "final_answer": ""
        }

    def test_workflow_completion(self, basic_state):
        """Test that workflow completes successfully"""
        result = land_analysis_graph.invoke(basic_state)

        # Check that we got a final answer
        assert "final_answer" in result or "generation" in result
        assert len(result.get("final_answer", result.get("generation", ""))) > 0

    def test_workflow_with_coordinates(self):
        """Test workflow with coordinate query"""
        state = {
            "question": "What's the soil at 22.5726° N, 88.3639° E?",
            "chat_history": [],
            "documents": [],
            "generation": "",
            "coordinates": {},
            "location_context": {},
            "tool_results": {},
            "relevance_score": "",
            "hallucination_score": "",
            "answer_score": "",
            "retry_count": 0,
            "web_search_needed": False,
            "final_answer": ""
        }

        result = land_analysis_graph.invoke(state)

        # Should have processed coordinates
        assert result.get("coordinates") or "22.5726" in str(result.get("generation", ""))

    def test_workflow_retry_logic(self):
        """Test that retry logic works"""
        state = {
            "question": "Analyze this location",
            "chat_history": [],
            "documents": [],
            "generation": "",
            "coordinates": {},
            "location_context": {},
            "tool_results": {},
            "relevance_score": "",
            "hallucination_score": "",
            "answer_score": "",
            "retry_count": 0,
            "web_search_needed": False,
            "final_answer": ""
        }

        result = land_analysis_graph.invoke(state)

        # Check that retry count was tracked
        assert "retry_count" in result
        assert result["retry_count"] >= 0

class TestGraphNodes:
    """Test individual graph nodes"""

    def test_coordinate_extraction(self):
        """Test coordinate extraction from queries"""
        from src.utils.coordinate_parser import extract_coordinates

        # Test various formats
        queries = [
            "What's at 22.5726° N, 88.3639° E?",
            "Analyze 22.5726, 88.3639",
            "lat: 22.5726, lon: 88.3639"
        ]

        for query in queries:
            coords = extract_coordinates(query)
            assert coords is not None
            assert "latitude" in coords
            assert "longitude" in coords
            assert abs(coords["latitude"] - 22.5726) < 0.001

    def test_coordinate_validation(self):
        """Test coordinate validation"""
        from src.utils.coordinate_parser import validate_coordinates

        # Valid coordinates
        assert validate_coordinates(22.5726, 88.3639) == True
        assert validate_coordinates(0, 0) == True
        assert validate_coordinates(-90, -180) == True
        assert validate_coordinates(90, 180) == True

        # Invalid coordinates
        assert validate_coordinates(100, 50) == False
        assert validate_coordinates(50, 200) == False
        assert validate_coordinates(-100, 50) == False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])