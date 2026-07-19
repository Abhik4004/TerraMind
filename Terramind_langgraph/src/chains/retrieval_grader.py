from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from src.config.llm_provider import get_llm

llm = get_llm()

class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""

    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )

parser = PydanticOutputParser(pydantic_object=GradeDocuments)

system = """You are a grader assessing relevance of a retrieved geospatial document to a user question.

For land analysis queries, check if the document contains:
- Geographic coordinates or location data relevant to the question
- Soil information, terrain data, or land characteristics
- Weather patterns, climate data, or environmental conditions
- Infrastructure data (roads, buildings, utilities)
- Risk assessments (flooding, pollution, hazards)
- Any geospatial properties or measurements related to the query

If the document contains keyword(s) or semantic meaning related to the question, grade it as relevant.
Give a binary score 'yes' or 'no' to indicate whether the document is relevant to the question.

{format_instructions}"""

grade_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "Retrieved document: \n\n {document} \n\n User Question: {question}"),
    ],
)

grade_prompt = grade_prompt.partial(
    format_instructions=parser.get_format_instructions()
)

retrieval_grader = grade_prompt | llm | parser