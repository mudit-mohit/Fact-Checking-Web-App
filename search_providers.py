import os
from typing import List, Optional
from dataclasses import dataclass
import requests


@dataclass
class SearchResult:
    """Standardized search result"""
    title: str
    url: str
    snippet: str
    source: str = "Tavily"
    relevance_score: Optional[float] = None
    published_date: Optional[str] = None


class TavilySearch:
    """
    Tavily Search API - Optimized for LLM retrieval and fact-checking
    Get free API key: https://app.tavily.com/home
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('TAVILY_API_KEY')
        self.base_url = "https://api.tavily.com/search"
        
        if not self.api_key:
            raise ValueError(
                "Tavily API key is required. "
                "Set TAVILY_API_KEY environment variable or pass it via constructor."
            )
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search using Tavily API"""
        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False
            }
            
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('results', [])[:max_results]:
                result = SearchResult(
                    title=item.get('title', 'No title'),
                    url=item.get('url', ''),
                    snippet=item.get('content', 'No content'),
                    relevance_score=item.get('score')
                )
                results.append(result)
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Tavily search error: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error during Tavily search: {e}")
            return []


class SearchClient:
    """
    Simplified client that only uses Tavily
    """
    
    def __init__(self):
        self.search = TavilySearch()
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        print(f"  Searching with Tavily...")
        results = self.search.search(query, max_results)
        
        if results:
            print(f"  ✓ Found {len(results)} results from Tavily")
        else:
            print("  ✗ No results from Tavily")
            
        return results


# Convenience functions
def search_web(query: str, max_results: int = 5) -> List[SearchResult]:
    """Quick search function using only Tavily"""
    client = SearchClient()
    return client.search(query, max_results)


def format_results_for_llm(results: List[SearchResult]) -> str:
    """Format search results for LLM consumption"""
    if not results:
        return "No search results found."
    
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"""
Result {i}:
Title: {result.title}
Source: {result.url}
Content: {result.snippet}
""")
    
    return "\n".join(formatted)


# Main execution for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python search_providers.py <search_query>")
        print("\nExample: python search_providers.py 'Tesla revenue 2024'")
        print("\nSet TAVILY_API_KEY environment variable:")
        print("  set TAVILY_API_KEY=your-key-here")
        sys.exit(1)
    
    query = ' '.join(sys.argv[1:])
    
    try:
        print("\n" + "="*60)
        print("SEARCHING WITH TAVILY ONLY")
        print("="*60 + "\n")
        
        results = search_web(query, max_results=5)
        
        if results:
            print(f"\n{'='*60}")
            print(f"RESULTS ({len(results)} found)")
            print(f"{'='*60}\n")
            
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.title}")
                print(f"   URL: {result.url}")
                print(f"   Snippet: {result.snippet[:150]}...")
                if result.relevance_score:
                    print(f"   Relevance: {result.relevance_score:.2f}")
                print()
        else:
            print("No results found.")
    
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)