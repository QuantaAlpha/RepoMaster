import json
from typing import List, Dict, Annotated, Optional, Any
from src.utils.agent_gpt4 import AzureGPT4Chat
from src.utils.tools_util import display, get_output_handler
from src.utils.web_search_agent.tool_web_engine import SerperSearchEngine
from streamlit_extras.colored_header import colored_header
from src.utils.web_search_agent.prompt_web_search import (
    SYSTEM_MESSAGE_HAS_SUFFICIENT_INFO,
    SYSTEM_MESSAGE_GENERATE_ANSWER,
    SYSTEM_MESSAGE_IMPROVE_QUERY
)
import streamlit as st
from datetime import datetime
import asyncio
import concurrent.futures

class WebSearchAgent:
    def __init__(self):
        self.search_engine = SerperSearchEngine(chunk_size=8000, chunk_overlap=400)
        self.max_iterations = 2

    def display_search_results(self, search_results: List[Dict[str, str]], show_content=True):
        out_context = []
        for i, result in enumerate(search_results, 1):
            text_dict = {}
            text_dict[f'Source {i}'] = ""
            text_dict['Title'] = result['title']
            text_dict['Link'] = result['link']
            text_dict['Snippet'] = result['snippet']
            if result.get('content',''):
                text_dict['Content'] = result['content']

            if show_content and st is not None:
                try:
                    title = result['title']
                    if len(title) > 50:
                        title = title[:47] + "..."

                    with st.expander(f"**Link:** {title}\n[{result['link']}]({result['link']})"):
                        st.markdown("\n\n".join([f"**{key}:** {value}" for key, value in text_dict.items()]))
                except:
                    pass
            
            out_context.append(text_dict)
            
        return out_context

    async def _web_search(self, query: str) -> tuple[list, str]:
        output_handler = get_output_handler()
        all_search_results = []

        for iteration in range(self.max_iterations):
            display(f"🔍 Web Search Iteration {iteration + 1}/N", output_handler=output_handler)
            display(f"📝 Query: {query}", output_handler=output_handler)
            
            with st.spinner("🌐 Searching the web..."):
                search_results = await self.search_engine.engine_search(query, url_filter=[res['link'] for res in all_search_results])
                search_results = json.loads(search_results)
                print(f"search_results: {search_results}", flush=True)
                all_search_results += search_results

                self.display_search_results(search_results)
            
            context = self._prepare_context(all_search_results)
            display(f"📊 Context: {len(context)} characters | {len(search_results)} results", output_handler=output_handler)
            
            has_sufficient_info = self._has_sufficient_information(query, context)
            display(f"✅ Sufficient Information: {'Yes' if has_sufficient_info else 'No'}", output_handler=output_handler)
            
            if has_sufficient_info:
                display("🎯 Search completed successfully", output_handler=output_handler)
                return all_search_results, context
            
            prev_query = query
            query = self._improve_query(query, context)
            display(f"🔄 Refined Query: {query}", output_handler=output_handler)
            display("---", output_handler=output_handler)
        
        display("⚠️ Max iterations reached. Generating answer with available information.", output_handler=output_handler)
        return all_search_results, context

    def _prepare_context(self, search_results: List[Dict[str, str]]) -> str:
        """Prepare context from search results."""
        return "\n\n".join([
            f"Title: {result['title']}\nSnippet: {result['snippet']}\nContent: {result['content']}..."
            for result in search_results
        ])

    def _has_sufficient_information(self, query: str, context: str) -> bool:
        """Check if there's enough information to answer the query."""
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE_HAS_SUFFICIENT_INFO},
            {"role": "user", "content": f"Query: {query}\n\nSearch Results:\n{context}\n\nIs there enough information to answer the query?"}
        ]
        
        response = AzureGPT4Chat().chat_with_message(messages)
        
        return 'yes' in response.strip().lower()

    def _improve_query(self, query: str, context: str) -> str:
        """Suggest an improved search query using Think on Graph (ToG) approach."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE_IMPROVE_QUERY.format(current_time=current_time)},
            {"role": "user", "content": f"Initial Query: {query}\n\nSearch Results:\n{context}\n\nImproved query:"}
        ]
        
        response = AzureGPT4Chat().chat_with_message(messages)
        
        return response    

    def _generate_answer(self, query: str, context: str) -> str:
        """Generate an answer based on the query and context."""
    
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE_GENERATE_ANSWER},
            {"role": "user", "content": f"Query: {query}\n\nSearch Results:\n{context}\n\nAnswer:"}
        ]
        
        response = AzureGPT4Chat().chat_with_message(messages)
        
        return response

    def web_agent_answer(self, query: Annotated[str, "The initial search query"]) -> str:
        """
        Perform a web search and generate an answer using an Agent-based approach.

        This Function should be called in an Agent scenario when:
        1. The Agent lacks sufficient information to answer the query directly.
        2. The query requires up-to-date information that might not be in the Agent's training data.
        3. The query is about current events, recent developments, or time-sensitive information.
        4. The Agent needs to verify or fact-check information from external sources.
        5. The query requires comprehensive research or data from multiple sources.

        Returns:
            A string containing the generated answer based on web search results.
        """

        # with st.chat_message('web_search'):
        with st.chat_message("assistant", avatar="🔷"):
            colored_header(label="Web Search", description="", color_name="violet-70")
            
            search_results, answer = self._web_search(query)
            search_content = self.display_search_results(search_results, show_content=False)
            
        return json.dumps(search_content, ensure_ascii=False)
    
    async def a_web_agent_answer(self, query: Annotated[str, "The initial search query"]) -> str:
        """
        Perform a web search and generate an answer using an Agent-based approach.

        This Function should be called in an Agent scenario when:
        1. The Agent lacks sufficient information to answer the query directly.
        2. The query requires up-to-date information that might not be in the Agent's training data.
        3. The query is about current events, recent developments, or time-sensitive information.
        4. The Agent needs to verify or fact-check information from external sources.
        5. The query requires comprehensive research or data from multiple sources.

        Returns:
            A string containing the generated answer based on web search results.
        """
        try:
            # Execute synchronous function directly in the current event loop
            with st.chat_message("assistant", avatar="🔷"):
                colored_header(label="Web Search", description="", color_name="violet-70")
                
                search_results, answer = await self._web_search(query)
                search_content = self.display_search_results(search_results, show_content=False)
                
            return json.dumps(search_content, ensure_ascii=False)
            
        except Exception as e:
            print(f"Error in a_web_agent_answer: {str(e)}")
            return "[]"

    def _deduplicate_results(self, new_results: List[Dict], existing_results: List[Dict]) -> List[Dict]:
        """Deduplication based on semantics and URL"""
        # Implementation requires connecting to embedding model to calculate similarity
        return [res for res in new_results if not any(self._is_similar(res, exist) for exist in existing_results)]
    
    def _sort_results_by_relevance(self, query: str, results: List[Dict]) -> List[Dict]:
        """Sorting based on query relevance"""
        # Implementation requires combining keyword matching and semantic relevance scoring
        return sorted(results, key=lambda x: self._relevance_score(query, x), reverse=True)
    
    def _calculate_confidence(self, query: str, context: str) -> float:
        """Calculate answer confidence (0-1)"""
        messages = [
            {"role": "system", "content": "Rate confidence in answering (0-1) based on:"},
            {"role": "user", "content": f"Query: {query}\nContext: {context[:3000]}"}
        ]
        return float(AzureGPT4Chat().chat_with_message(messages).strip())


if __name__ == "__main__":
    web_search_agent = WebSearchAgent()
    query = "More reasons why the public supports Kamala Harris in the 2024 US election"
    answer = web_search_agent.web_agent_answer(query)
    print(f"Answer: {answer}")  