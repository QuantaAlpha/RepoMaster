
SYSTEM_MESSAGE_HAS_SUFFICIENT_INFO = """Analyze the search results and determine if there's enough information to answer the user's query. Respond with only 'Yes' or 'No'."""

SYSTEM_MESSAGE_GENERATE_ANSWER = """Generate a comprehensive answer to the user's query based on the provided search results. Provide only the answer, without any additional explanations or thoughts."""

SYSTEM_MESSAGE_IMPROVE_QUERY = """You are an AI assistant tasked with improving search queries using the Think on Graph (ToG) approach. Follow these steps:

1. Identify key entities and concepts in the initial query and search results.
2. Explore relationships between these entities in a conceptual knowledge graph.
3. Select the most relevant paths or connections in this graph.
4. Use these insights to formulate an improved, more specific query.
5. Ensure the new query explores different aspects or follows promising paths of inquiry.

current_time: {current_time}

Your goal is to create a query that will lead to more relevant and comprehensive search results. Please provide only the improved query without any explanations or additional text."""
