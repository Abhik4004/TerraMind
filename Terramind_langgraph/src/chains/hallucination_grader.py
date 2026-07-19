from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from src.config.llm_provider import get_llm

llm = get_llm()

class GradeHallucination(BaseModel):
    """Binary score for hallucination present in generation answer"""
    binary_score: str = Field(
        description="Answer is grounded in the facts, 'yes' or 'no'"
    )

parser = JsonOutputParser(pydantic_object=GradeHallucination)

system = """You are a grader assessing whether an LLM generation is grounded in a set of retrieved geospatial facts.

Score 'yes' if the generation:
- Uses information consistent with the provided facts (soil types, terrain, weather, land use)
- Does not invent locations, coordinates, or measurements that directly contradict the source
- Makes reasonable inferences from the available data

Score 'no' only if the generation makes specific factual claims that directly contradict the source documents, or invents data that is clearly not present anywhere in the facts.

Do NOT score 'no' simply because the facts are sparse or incomplete — a reasonable answer based on partial data is still grounded.

Return ONLY valid JSON: {{"binary_score": "yes"}} or {{"binary_score": "no"}}"""

hallucination_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "Set of facts: \n\n {documents} \n\n LLM generation: {generation}"),
    ]
)

hallucination_grader = hallucination_prompt | llm | parser