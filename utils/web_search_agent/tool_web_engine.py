import os
import json
import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import serpapi
import re

from search_engine_parser.core.engines.google import Search as GoogleSearch
from search_engine_parser.core.engines.bing import Search as BingSearch
from search_engine_parser.core.engines.yahoo import Search as YahooSearch

from utils.tool_retriever_embed import WebRetriever, EmbeddingMatcher
from typing_extensions import Annotated
from typing import List, Dict, Any, Optional, Annotated
import tiktoken

class WebBrowser:
    def __init__(self, max_browser_length=-1):
        self.retriever = EmbeddingMatcher(chunk_size=500, chunk_overlap=50, topk=10)
        self.search_engine = SerperSearchEngine()
        self.max_browser_length = max_browser_length

    async def searching(self, query: Annotated[str, "要搜索的查询内容"]) -> str:
        """
        使用搜索引擎查询信息并返回结果
        """
        try:
            return await self.search_engine.engine_search(query, engine='google', search_num=10, web_parse=False)
        except Exception as e:
            print(f"Error searching: {str(e)}")
            return f"Error searching: {str(e)}"

    async def browsing(self, query: Annotated[str, "用于内容筛选的查询字符串"], url: Annotated[str, "要浏览的网页URL"]) -> str:
        """
        浏览特定URL的详细内容并提取相关信息
        """
        try:
            content = await self.browsing_url(url)
            output_content = []
            if len(tiktoken.encoding_for_model("gpt-4o").encode(content))>50000 and len(query)>0:
                output_content = self.retriever.match_docs(user_input=query, docs=content)
            elif len(content)>self.max_browser_length and len(query)==0 and self.max_browser_length>0:
                return json.dumps({'Input Query': query, 'Search URL': url, 'Search Result': content[:self.max_browser_length]}, ensure_ascii=False)
            else:
                return json.dumps({'Input Query': query, 'Search URL': url, 'Search Result': content}, ensure_ascii=False)
            
            output_dict = {
                'Input Query': query,
                'Search URL': url,
                'Search Result': '\n'.join([f"## chunk {i+1}:\n{chunk}" for i, chunk in enumerate(output_content)])
            }

            return json.dumps(output_dict, ensure_ascii=False)
        except Exception as e:
            print(f"Error browsing URL {url}: {str(e)}")
            return json.dumps({'Input Query': query, 'Search URL': url, 'Search Result': 'Error browsing URL'}, ensure_ascii=False)
    
    async def parallel_browsing(
        self, 
        query: Annotated[str, "用于内容筛选的查询字符串"],
        urls: Annotated[List[str], "要并行浏览的网页URL列表"],
        max_parallel: Annotated[int, "最大并行处理数量"] = 3
    ) -> str:
        """
        并行浏览多个URL的详细内容并提取相关信息
        return: 包含每个URL内容的字典列表
        """
        results = []
        
        try:
            # 将URL列表分成多个批次，每批最多max_parallel个
            for i in range(0, len(urls), max_parallel):
                batch = urls[i:i + max_parallel]
                tasks = [self.browsing(query, url) for url in batch]
                
                # 并行执行当前批次的所有任务
                batch_results = await asyncio.gather(*tasks)
                
                # 将JSON字符串解析为字典对象
                parsed_results = [json.loads(result) for result in batch_results]
                results.extend(parsed_results)
            
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            print(f"Error parallel browsing: {str(e)}")
            return f"Error parallel browsing: {str(e)}"

    async def test_browsing(self, query: Annotated[str, "用于内容筛选的查询字符串"], url: Annotated[str, "要浏览的网页URL"]):
        """
        浏览特定URL的详细内容并提取相关信息
        """
        content = await self.browsing_url(url)
        
        content_clean = await self.search_engine._clean_content(content)
        
        return content, content_clean


    async def browsing_url(self, url):
        if "r.jina.ai" not in url:
            url = "https://r.jina.ai/"+url

        if os.getenv("JINA_API_KEY"):
            headers = {
                'Authorization': "Bearer "+os.getenv("JINA_API_KEY",''),
                'X-Engine': 'direct',
                'X-Return-Format': 'markdown',
                "X-Timeout": "10"       
            }
        else:
            headers = None
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                content = await response.read()

        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        
        content = await self.search_engine._clean_content(content)

        return content

class SerperSearchEngine:
    """
    A class to perform searches using the Serper API and web scraping techniques.
    """

    def __init__(self, chunk_size=4000, chunk_overlap=400):
        """
        Initialize the SerperSearchEngine with the API key.
        """
        self.Serper_API_KEY = os.environ['Serper_API_KEY']
        self.google_serper_url = "https://google.serper.dev/search"
        self.retriever = WebRetriever(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def google_search(
            self, 
            query: Annotated[str, "The search query"], 
            max_results: Annotated[int, "The maximum number of results to retrieve"] = 100,
         ) -> List[Dict[str, str]]:
        """
        Perform a Google search using the Serper API and retrieve multiple pages of results.

        Returns:
            A list of search results, each containing title, snippet, and link.
        """
        headers = {
            'X-API-KEY': os.environ['Serper_API_KEY'],
            'Content-Type': 'application/json'
        }
        
        all_results = []
        
        for page in range(1):
            payload = {
                'q': query,
                'gl': 'us',
                'hl': 'en',
                'num': max_results,  # Request 10 results per page
            }

            try:
                response = requests.post(self.google_serper_url, headers=headers, json=payload)
                response.raise_for_status()
                results = response.json()

                organic_results = [result for result in results.get('organic', [{}])]

                page_results = [
                    {
                        "title": result.get("title"),
                        "snippet": result.get("snippet"),
                        "link": result.get("link"),
                        # 'published': result.get('published', ''),
                        # 'authors': [author['name'] for author in result.get('authors', [])],
                    }
                    for result in organic_results
                ]
                
                all_results.extend(page_results)
            except Exception as e:
                print(f"Error fetching search results for page {page + 1}: {str(e)}")
                break  # Stop if we encounter an error            
        
        return all_results

    def _scrape_search_results(self, url: Annotated[str, "The search URL"], engine: Annotated[str, "The search engine ('bing' or 'yahoo')"]) -> List[Dict[str, str]]:
        """
        Scrape search results from Bing or Yahoo.

        Args:
            url: The search URL.
            engine: The search engine ('bing' or 'yahoo').

        Returns:
            A list of search results, each containing title, snippet, and link.
        """
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        if engine == 'bing':
            for item in soup.select('#b_results .b_algo'):
                title = item.select_one('h2 a')
                snippet = item.select_one('.b_caption p')
                if title and snippet:
                    results.append({
                        'title': title.text,
                        'snippet': snippet.text,
                        'link': title['href']
                    })
        elif engine == 'yahoo':
            for item in soup.select('div.algo'):
                title = item.select_one('h3 a')
                snippet = item.select_one('.compText')
                if title and snippet:
                    results.append({
                        'title': title.text,
                        'snippet': snippet.text,
                        'link': title['href']
                    })

        return results  # Limit to first 5 results

    def bing_search(self, query: Annotated[str, "The search query"]) -> List[Dict[str, str]]:
        """
        Perform a Bing search by scraping the results.

        Args:
            query: The search query.

        Returns:
            A list of search results, each containing title, snippet, and link.
        """
        url = f"https://www.bing.com/search?q={query}"
        return self._scrape_search_results(url, 'bing')

    def yahoo_search(self, query: Annotated[str, "The search query"]) -> List[Dict[str, str]]:
        """
        Perform a Yahoo search by scraping the results.

        Args:
            query: The search query.

        Returns:
            A list of search results, each containing title, snippet, and link.
        """
        url = f"https://search.yahoo.com/search?p={query}"
        return self._scrape_search_results(url, 'yahoo')
    
    async def _clean_content(self, content: str) -> str:
        # Remove URLs
        content = re.sub(r'http[s]?://\S+', '', content)
        
        # Remove Markdown links
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        
        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)

        # 移除图片标记（保留alt文本）
        content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', content)

        # 移除HTML注释
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)        
        
        # 移除导航类列表
        content = re.sub(r'^\s*[-*]\s+(Home|About|Contact|Menu|Search|Privacy Policy|Terms of Service)\s*$', '', content, flags=re.MULTILINE | re.IGNORECASE)
        
        # 移除常见页脚信息
        content = re.sub(r'Copyright © \d{4}.*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'All rights reserved\.?', '', content, flags=re.IGNORECASE)
        
        # 移除社交媒体相关文本
        content = re.sub(r'(Follow|Like|Share|Subscribe).*(Facebook|Twitter|Instagram|LinkedIn|YouTube).*', '', content, flags=re.IGNORECASE)
        
        # Remove empty lines and extra whitespace
        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Remove very short lines (likely navigation items)
        content = '\n'.join(line for line in content.split('\n') if len(line.split()) > 2)
        
        return content.strip()

    async def _parse_content_async(self, res):
        try:
            content = await WebBrowser().browsing(query='', url=res['link'])
            # Convert bytes to string if content is in bytes format
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            # print(f"content: {content}", flush=True)
            res['content'] = await self._clean_content(content)
        except Exception as e:
            print(f"Error parsing content for {res['link']}: {str(e)}")
            res['content'] = ""
        return res

    async def _enrich_results_async(self, results):
        tasks = [self._parse_content_async(res) for res in results]
        return await asyncio.gather(*tasks)
    
    async def engine_search(self, query, engine='google', search_num=10, web_parse=True, url_filter=None):
        engine = engine.lower()
        if engine == 'google' or 1:
            results = self.google_search(query, max_results=search_num*2)
        elif engine == 'bing':
            results = self.bing_search(query)
        elif engine == 'mix':
            results = self.bing_search(query) + self.google_search(query, max_results=search_num*2)
        else:
            results = self.yahoo_search(query)
        
        if url_filter:
            results = [res for res in results if res['link'] not in url_filter]
        
        results = results[:min(search_num, len(results))]
        
        if web_parse:
            results = await self._enrich_results_async(results)
            print(f"results: {results}", flush=True)
            results = self.retriever.retrieve_relevant_chunks(results, query, k=search_num)
        return json.dumps(results, ensure_ascii=False)

    async def search(self, query: Annotated[str, "The search query"], engine: Annotated[str, "The search engine to use"] = 'google') -> List[Dict[str, str]]:
        """
        Perform a search using the specified engine and enrich results with web content.

        Args:
            query: The search query.
            engine: The search engine to use ('google', 'bing', or 'yahoo').

        Returns:
            A list of search results, each containing title, snippet, link, and content.
        """
        return await self.engine_search(query, engine)
