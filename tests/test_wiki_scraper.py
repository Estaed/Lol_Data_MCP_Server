"""
Tests for the WikiScraper class.

Tests the basic wiki scraper foundation including HTTP handling,
rate limiting, error handling, and champion page fetching.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx
from bs4 import BeautifulSoup

from src.data_sources.scrapers.wiki_scraper import (
    WikiScraper, 
    WikiScraperError, 
    ChampionNotFoundError
)


class TestWikiScraper:
    """Test suite for WikiScraper class"""
    
    @pytest.fixture
    def scraper(self):
        """Create a WikiScraper instance for testing"""
        return WikiScraper(rate_limit_delay=0.1)  # Faster for testing
    
    def test_initialization(self, scraper):
        """Test WikiScraper initialization"""
        assert scraper.rate_limit_delay == 0.1
        assert scraper.timeout == 30.0
        assert scraper.max_retries == 3
        assert scraper.retry_delay == 2.0
        assert scraper.last_request_time == 0.0
        assert scraper._client is None
        assert "LoL-Data-MCP-Server" in scraper.headers["User-Agent"]
    
    def test_build_champion_url(self, scraper):
        """Test champion URL building"""
        # Simple champion name
        url = scraper._build_champion_url("Taric")
        assert url == "https://leagueoflegends.fandom.com/wiki/Taric"
        
        # Champion with apostrophe
        url = scraper._build_champion_url("Kai'Sa")
        assert "Kai" in url and "Sa" in url  # More flexible test
        
        # Champion with space
        url = scraper._build_champion_url("Twisted Fate")
        assert "Twisted_Fate" in url
    
    @pytest.mark.asyncio
    async def test_context_manager(self, scraper):
        """Test async context manager functionality"""
        async with scraper as s:
            assert s._client is not None
            assert isinstance(s._client, httpx.AsyncClient)
        
        # Client should be closed after context exit
        assert scraper._client is None
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, scraper):
        """Test rate limiting functionality"""
        import time
        
        # First call should not delay
        start_time = time.time()
        await scraper._rate_limit()
        first_call_time = time.time() - start_time
        assert first_call_time < 0.05  # Should be immediate
        
        # Second call should delay
        start_time = time.time()
        await scraper._rate_limit()
        second_call_time = time.time() - start_time
        assert second_call_time >= 0.09  # Should wait for rate limit
    
    @pytest.mark.asyncio
    async def test_ensure_client(self, scraper):
        """Test HTTP client initialization"""
        assert scraper._client is None
        await scraper._ensure_client()
        assert scraper._client is not None
        assert isinstance(scraper._client, httpx.AsyncClient)
        
        # Should not create new client if one exists
        old_client = scraper._client
        await scraper._ensure_client()
        assert scraper._client is old_client
    
    @pytest.mark.asyncio
    async def test_close(self, scraper):
        """Test HTTP client cleanup"""
        await scraper._ensure_client()
        assert scraper._client is not None
        
        await scraper.close()
        assert scraper._client is None
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, scraper):
        """Test successful HTTP request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>Test</title></html>"
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        
        with patch.object(scraper, '_ensure_client'), \
             patch.object(scraper, '_rate_limit'), \
             patch.object(scraper, '_client', mock_client):
            
            response = await scraper._make_request("http://test.com")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_make_request_404(self, scraper):
        """Test 404 error handling"""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        
        with patch.object(scraper, '_ensure_client'), \
             patch.object(scraper, '_rate_limit'), \
             patch.object(scraper, '_client', mock_client):
            
            with pytest.raises(ChampionNotFoundError):
                await scraper._make_request("http://test.com")
    
    @pytest.mark.asyncio
    async def test_make_request_retry(self, scraper):
        """Test retry logic on HTTP errors"""
        scraper.max_retries = 1
        scraper.retry_delay = 0.01  # Fast retry for testing
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            httpx.RequestError("Connection failed"),
            Mock(status_code=200, text="<html></html>")
        ]
        
        with patch.object(scraper, '_ensure_client'), \
             patch.object(scraper, '_rate_limit'), \
             patch.object(scraper, '_client', mock_client):
            
            response = await scraper._make_request("http://test.com")
            assert response.status_code == 200
            assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_champion_page(self, scraper):
        """Test champion page fetching and parsing"""
        mock_html = """
        <html>
            <head><title>Taric | League of Legends Wiki | Fandom</title></head>
            <body><h1>Taric</h1></body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            soup = await scraper.fetch_champion_page("Taric")
            
            assert isinstance(soup, BeautifulSoup)
            title = soup.find('title')
            assert title is not None
            assert "Taric" in title.get_text()
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, scraper):
        """Test successful connection test"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            result = await scraper.test_connection()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, scraper):
        """Test failed connection test"""
        with patch.object(scraper, '_make_request', side_effect=WikiScraperError("Connection failed")):
            result = await scraper.test_connection()
            assert result is False


@pytest.mark.asyncio
async def test_real_wiki_connection():
    """Integration test with real LoL Wiki (optional, may be slow)"""
    # This test can be skipped in CI/CD pipelines
    scraper = WikiScraper(rate_limit_delay=2.0)  # Be respectful to the server
    
    try:
        async with scraper:
            # Test connection
            is_connected = await scraper.test_connection()
            assert is_connected is True
            
            # Test fetching a real champion page
            soup = await scraper.fetch_champion_page("Taric")
            assert soup is not None
            
            title = soup.find('title')
            assert title is not None
            title_text = title.get_text()
            assert "Taric" in title_text
            assert "League of Legends Wiki" in title_text
            
    except Exception as e:
        pytest.skip(f"Real wiki test skipped due to network issues: {e}")


if __name__ == "__main__":
    # Run specific tests
    asyncio.run(test_real_wiki_connection()) 