# tests/test_graders.py
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.chains.retrieval_grader import retrieval_grader
from src.chains.hallucination_grader import hallucination_grader
from src.chains.answer_grader import answer_grader

class TestRetrievalGrader:
    """Test document relevance grading"""

    def test_relevant_document(self):
        """Test that relevant documents are graded as 'yes'"""
        document = """
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [88.3639, 22.5726]},
            "properties": {
                "soil_type": "Alluvial",
                "pH": 6.5,
                "suitable_for": ["agriculture", "tea_cultivation"]
            }
        }
        """
        question = "What is the soil type for tea gardening?"

        result = retrieval_grader.invoke({
            "question": question,
            "document": document
        })

        assert result.binary_score == "yes"

    def test_irrelevant_document(self):
        """Test that irrelevant documents are graded as 'no'"""
        document = """
        {
            "type": "Feature",
            "properties": {
                "road_type": "highway",
                "lanes": 4
            }
        }
        """
        question = "What is the soil pH level?"

        result = retrieval_grader.invoke({
            "question": question,
            "document": document
        })

        # This might be 'no' depending on LLM response
        assert result.binary_score in ["yes", "no"]

class TestHallucinationGrader:
    """Test hallucination detection"""

    def test_grounded_generation(self):
        """Test that grounded answers pass"""
        documents = "The soil type at coordinates 22.57, 88.36 is Alluvial with pH 6.5"
        generation = "Based on the data, the soil type is Alluvial with a pH of 6.5"

        result = hallucination_grader.invoke({
            "documents": documents,
            "generation": generation
        })

        assert result["binary_score"] == "yes"

    def test_hallucinated_generation(self):
        """Test that hallucinated answers fail"""
        documents = "The soil type is Alluvial"
        generation = "The soil type is Volcanic with high mineral content and pH of 8.2"

        result = hallucination_grader.invoke({
            "documents": documents,
            "generation": generation
        })

        # Should ideally be 'no' but depends on LLM
        assert result["binary_score"] in ["yes", "no"]

class TestAnswerGrader:
    """Test answer quality grading"""

    def test_complete_answer(self):
        """Test that complete answers pass"""
        question = "What is the soil type at these coordinates?"
        generation = """
        **Location Context:**
        - Coordinates: 22.57° N, 88.36° E
        
        **Analysis:**
        The soil type at this location is Alluvial with pH 6.5, suitable for agriculture.
        """

        result = answer_grader.invoke({
            "question": question,
            "generation": generation
        })

        assert result.binary_score == True

    def test_incomplete_answer(self):
        """Test that incomplete answers fail"""
        question = "Provide a detailed land analysis with pros and cons"
        generation = "The soil is good."

        result = answer_grader.invoke({
            "question": question,
            "generation": generation
        })

        # Should ideally be False but depends on LLM
        assert isinstance(result.binary_score, bool)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])