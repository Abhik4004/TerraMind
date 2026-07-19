# src/tools/tool_selector.py
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from src.config.settings import settings
from src.config.llm_provider import get_llm

class ToolSelection(BaseModel):
    """Schema for tool selection output"""
    selected_tools: List[str] = Field(
        description="List of tool names that should be used to answer the query"
    )
    reasoning: str = Field(
        description="Brief explanation of why these tools were selected"
    )
    requires_coordinates: bool = Field(
        description="Whether the query requires coordinate extraction"
    )

class ToolSelector:
    """
    Intelligent tool selector that analyzes queries and selects appropriate tools.
    """

    AVAILABLE_TOOLS = {
        "query_geospatial_index": {
            "description": "Query the geospatial vector database for land characteristics, soil data, terrain info",
            "use_for": ["soil analysis", "land characteristics", "terrain data", "construction suitability", "general geospatial queries"]
        },
        "get_weather_data": {
            "description": "Get current weather data for specific coordinates",
            "use_for": ["weather conditions", "temperature", "precipitation", "humidity", "current weather"]
        },
        "get_recent_weather_data": {
            "description": "Get historical weather data for a location",
            "use_for": ["weather history", "climate patterns", "seasonal data", "past weather"]
        },
        "get_weather_comparison": {
            "description": "Compare weather between multiple locations",
            "use_for": ["weather comparison", "climate comparison", "location comparison"]
        },
        "get_road_network_data": {
            "description": "Get road network information for a location",
            "use_for": ["road data", "connectivity", "accessibility", "infrastructure"]
        },
        "get_detailed_road_network_data": {
            "description": "Get detailed road network metrics and analysis",
            "use_for": ["detailed road analysis", "road density", "intersection analysis", "transportation planning"]
        },
        "compare_road_networks": {
            "description": "Compare road networks between locations",
            "use_for": ["road comparison", "infrastructure comparison", "connectivity comparison"]
        },
        "get_road_types_analysis": {
            "description": "Analyze distribution and types of roads",
            "use_for": ["road types", "road classification", "highway analysis", "street analysis"]
        },
        "analyze_flood_risk": {
            "description": "Assess flood risk for a location",
            "use_for": ["flood risk", "water hazards", "drainage analysis", "elevation data"]
        },
        "analyze_construction_suitability": {
            "description": "Evaluate land suitability for construction",
            "use_for": ["construction", "building", "development", "land use planning"]
        },
        "get_pollution_data": {
            "description": "Get pollution and air quality data",
            "use_for": ["pollution", "air quality", "environmental health", "AQI"]
        }
    }

    def __init__(self):
        self.llm = get_llm(temperature=0)
        self.parser = JsonOutputParser(pydantic_object=ToolSelection)

        # Build tool descriptions for prompt
        tools_desc = "\n".join([
            f"- {name}: {info['description']}\n  Use for: {', '.join(info['use_for'])}"
            for name, info in self.AVAILABLE_TOOLS.items()
        ])

        system_prompt = f"""You are an intelligent tool selection agent for a geospatial land analysis system.

AVAILABLE TOOLS:
{tools_desc}

Your task is to analyze the user's query and select the most appropriate tools to answer it.

SELECTION RULES:
1. For general land/soil queries without coordinates → select "query_geospatial_index"
2. For weather-related queries with coordinates → select weather tools
3. For road/infrastructure queries with coordinates → select road network tools
4. For construction queries → select "query_geospatial_index" and "analyze_construction_suitability"
5. For risk assessment → select appropriate risk analysis tools
6. You can select MULTIPLE tools if the query requires it
7. Always select "query_geospatial_index" as a baseline unless the query is purely about weather/roads

COORDINATE DETECTION:
- Set requires_coordinates=true if the query mentions specific coordinates, locations, or "at this location"
- Set requires_coordinates=false for general queries like "what is best for tea gardening"

Return your response as JSON:
{{{{
    "selected_tools": ["tool1", "tool2"],
    "reasoning": "explanation",
    "requires_coordinates": true/false
}}}}"""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Query: {query}\n\nSelect the appropriate tools.")
        ])

        self.chain = self.prompt | self.llm | self.parser

    def select_tools(self, query: str, coordinates: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Select appropriate tools for a given query.

        Args:
            query: User's question
            coordinates: Extracted coordinates if available

        Returns:
            Dictionary with selected tools and reasoning
        """
        try:
            result = self.chain.invoke({"query": query})

            # If coordinates are provided, ensure coordinate-based tools are included
            if coordinates and result.get("requires_coordinates"):
                selected = result["selected_tools"]

                # Add weather tools if query mentions weather
                if any(word in query.lower() for word in ["weather", "temperature", "rain", "climate"]):
                    if "get_weather_data" not in selected:
                        selected.append("get_weather_data")

                # Add road tools if query mentions roads/infrastructure
                if any(word in query.lower() for word in ["road", "infrastructure", "connectivity", "access"]):
                    if "get_road_network_data" not in selected:
                        selected.append("get_road_network_data")

            return {
                "selected_tools": result["selected_tools"],
                "reasoning": result["reasoning"],
                "requires_coordinates": result["requires_coordinates"],
                "coordinate_available": coordinates is not None
            }

        except Exception as e:
            print(f"Error in tool selection: {e}")
            # Fallback to default tool
            return {
                "selected_tools": ["query_geospatial_index"],
                "reasoning": "Fallback to default geospatial query tool",
                "requires_coordinates": False,
                "coordinate_available": False
            }

    def get_tool_description(self, tool_name: str) -> str:
        """Get description of a specific tool."""
        return self.AVAILABLE_TOOLS.get(tool_name, {}).get("description", "Unknown tool")

    def list_all_tools(self) -> List[str]:
        """List all available tools."""
        return list(self.AVAILABLE_TOOLS.keys())


# Global tool selector instance
tool_selector = ToolSelector()


# Test function
if __name__ == "__main__":
    print("Testing Tool Selector")
    print("="*80)

    test_queries = [
        "What is the best location for tea gardening?",
        "What's the weather at 22.5726° N, 88.3639° E?",
        "Analyze the road network at coordinates 23.5, 87.2",
        "Is this location suitable for construction: 22.57, 88.36?",
        "Compare weather and road conditions at two locations"
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = tool_selector.select_tools(query)
        print(f"Selected tools: {result['selected_tools']}")
        print(f"Reasoning: {result['reasoning']}")
        print(f"Requires coordinates: {result['requires_coordinates']}")
        print("-" * 80)

    print("\n" + "="*80)