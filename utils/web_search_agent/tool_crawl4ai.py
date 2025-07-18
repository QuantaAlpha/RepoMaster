from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import List, Dict, Any, Optional
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

@dataclass
class CrawlerOptions:
    """爬虫配置选项"""
    use_js: bool = False
    use_screenshot: bool = False
    use_pdf: bool = False
    scan_full_page: bool = True
    exclude_external: bool = True
    semaphore_count: int = 2

class CrawlerMode(Enum):
    """爬虫模式枚举"""
    BASIC = "basic"
    FULL = "full"
    CUSTOM = "custom"

class WebCrawlerManager:
    def __init__(self, headless: bool = True):
        """
        初始化爬虫管理器
        
        Args:
            headless (bool): 是否使用无头模式，默认True
        """
        self.browser_config = BrowserConfig(
            headless=headless,
            viewport_width=1920,
            viewport_height=1080,
            user_agent_mode="random",
        )
        
        # 预定义的配置模式
        self.config_modes = {
            CrawlerMode.BASIC: CrawlerOptions(),
            CrawlerMode.FULL: CrawlerOptions(
                use_js=True,
                use_screenshot=True,
                use_pdf=True
            ),
            CrawlerMode.CUSTOM: None  # 将通过 set_custom_options 设置
        }
        
        self.current_mode = CrawlerMode.BASIC
        self.crawler: Optional[AsyncWebCrawler] = None

    def _create_crawler_config(self, options: CrawlerOptions) -> CrawlerRunConfig:
        """根据选项创建爬虫配置"""
        config = {
            "cache_mode": "memory",
            "scroll_delay": 0.5,
            "excluded_tags": ["script", "style"],
        }
        
        if options.scan_full_page:
            config["scan_full_page"] = True
        
        if options.exclude_external:
            config["exclude_external_links"] = True
            
        if options.use_screenshot:
            config["screenshot"] = True
            
        if options.use_pdf:
            config["pdf"] = True
            
        if options.use_js:
            config["js_code"] = [
                "window.scrollTo(0, document.body.scrollHeight);",
                "document.querySelectorAll('.show-more-button').forEach(btn => btn.click());"
            ]
        
        return CrawlerRunConfig(**config)

    def set_mode(self, mode: CrawlerMode) -> None:
        """设置爬虫模式"""
        self.current_mode = mode

    def set_custom_options(self, options: CrawlerOptions) -> None:
        """设置自定义配置选项"""
        self.config_modes[CrawlerMode.CUSTOM] = options

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        await self.crawler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.crawler:
            await self.crawler.__aexit__(exc_type, exc_val, exc_tb)

    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """爬取单个URL"""
        options = self.config_modes[self.current_mode]
        run_cfg = self._create_crawler_config(options)
        
        if not self.crawler:
            raise RuntimeError("Crawler not initialized. Use async with context manager.")
            
        result = await self.crawler.arun(url, run_config=run_cfg)
        return self._process_result(result, url)

    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """爬取多个URL"""
        options = self.config_modes[self.current_mode]
        run_cfg = self._create_crawler_config(options)
        
        if not self.crawler:
            raise RuntimeError("Crawler not initialized. Use async with context manager.")
            
        results = await self.crawler.arun_many(
            urls,
            run_config=run_cfg,
            semaphore_count=options.semaphore_count
        )
        return [self._process_result(result, url) for url, result in zip(urls, results)]

    @staticmethod
    def _process_result(result, url: str) -> Dict[str, Any]:
        """处理爬取结果"""
        if not result.success:
            return {"success": False, "url": url, "error": result.error_message}
        
        return {
            "success": True,
            "url": url,
            "content_length": len(result.cleaned_html),
            "extracted_content": result.extracted_content,
            "internal_links": result.links.get("internal", []) if result.links else [],
            "images": result.media.get("images", []) if result.media else [],
            "screenshot_size": len(result.screenshot) if result.screenshot else 0,
            "pdf_size": len(result.pdf) if result.pdf else 0,
            "markdown": result.markdown
        }

async def crawl_url(url: str | List[str]) -> Dict[str, Any]:
    async with WebCrawlerManager() as crawler:
        # 使用基础模式
        crawler.set_mode(CrawlerMode.BASIC)
        if isinstance(url, list):
            results = await crawler.crawl_urls(url)
        else:
            results = await crawler.crawl_url(url)
        if isinstance(results, list):
            return [res["markdown"] for res in results]
        else:
            return results["markdown"]
    
# 使用示例
async def main():
    
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/aapl-20220924.htm"
    
    res = await crawl_url([url, url])
    import pdb; pdb.set_trace()
    exit()
    
    async with WebCrawlerManager() as crawler:
        # 使用基础模式
        crawler.set_mode(CrawlerMode.BASIC)
        result = await crawler.crawl_url(url)
        print(result)
        
        # 使用完整功能模式
        crawler.set_mode(CrawlerMode.FULL)
        urls = [url, url]
        results = await crawler.crawl_urls(urls)
        for result in results:
            print(result)
            
        # 使用自定义模式
        custom_options = CrawlerOptions(
            use_screenshot=True,
            exclude_external=False
        )
        crawler.set_custom_options(custom_options)
        crawler.set_mode(CrawlerMode.CUSTOM)
        result = await crawler.crawl_url(url)
        print(result)

if __name__ == "__main__":
    asyncio.run(main())