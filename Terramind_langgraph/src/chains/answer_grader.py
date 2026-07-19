from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel, Field
from src.config.llm_provider import get_llm

llm = get_llm()

class GradeAnswer(BaseModel):
    binary_score: bool = Field(
        description="Answer addresses the question, 'yes' or 'no'"
    )

structured_llm_parser = llm.with_structured_output(GradeAnswer)

system = """You are a grader assessing whether an answer addresses / resolves a land analysis question.

For geospatial and land analysis queries, check if the answer provides:
- Relevant location context and coordinates (if applicable)
- Numeric data with proper units (measurements, scores, percentages)
- Clear analysis of land characteristics
- Pros and cons based on geospatial data
- Actionable recommendations or assessments

Give a binary score 'yes' or 'no'. 'Yes' means that the answer resolves the question comprehensively.

Return your response as JSON matching this schema:
{{"binary_score": 'yes' or 'no'}}

Example: {{"binary_score": "yes"}}"""

answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "User question: \n\n {question} \n\n LLM generation: {generation}"),
    ]
)

answer_grader: RunnableSequence = answer_prompt | structured_llm_parser