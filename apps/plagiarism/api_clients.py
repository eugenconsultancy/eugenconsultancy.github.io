"""
API clients for external plagiarism detection services.
"""
import requests
from django.conf import settings
from django.core.exceptions import ValidationError
import logging
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)


class BasePlagiarismClient:
    """Base class for plagiarism detection clients."""
    
    def __init__(self):
        self.name = "base"
        self.timeout = 30
    
    def check_plagiarism(self, text: str, **kwargs) -> Dict[str, Any]:
        """Check text for plagiarism."""
        raise NotImplementedError
    
    def validate_credentials(self) -> bool:
        """Validate API credentials."""
        raise NotImplementedError


class CopyscapeClient(BasePlagiarismClient):
    """Client for Copyscape API."""
    
    def __init__(self):
        super().__init__()
        self.name = "copyscape"
        self.api_key = settings.COPYSCAPE_API_KEY
        self.base_url = "https://www.copyscape.com/api/"
    
    def validate_credentials(self) -> bool:
        """Validate Copyscape credentials."""
        try:
            params = {
                'k': self.api_key,
                'u': settings.COPYSCAPE_USERNAME,
                'o': 'balance'
            }
            response = requests.get(
                f"{self.base_url}",
                params=params,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Copyscape credential validation failed: {str(e)}")
            return False
    
    def check_plagiarism(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Check text using Copyscape.
        
        Args:
            text: Text to check
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with results
        """
        if not self.validate_credentials():
            raise ValidationError("Invalid Copyscape credentials")
        
        try:
            # Prepare parameters
            params = {
                'k': self.api_key,
                'u': settings.COPYSCAPE_USERNAME,
                'o': 'csearch',
                'e': 'UTF-8',
                't': text[:50000],  # Copyscape limit
                'c': kwargs.get('comparison_count', 10)
            }
            
            # Make request
            response = requests.post(
                self.base_url,
                data=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse response
            result = self._parse_response(response.text)
            
            return {
                'success': True,
                'source': self.name,
                'result': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Copyscape API error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'source': self.name
            }
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Copyscape XML response."""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(response_text)
            result = {
                'matches': [],
                'querywords': 0,
                'count': 0
            }
            
            # Parse matches
            for item in root.findall('.//result'):
                match = {
                    'url': item.find('url').text if item.find('url') is not None else '',
                    'title': item.find('title').text if item.find('title') is not None else '',
                    'words': int(item.find('words').text) if item.find('words') is not None else 0,
                    'percent': float(item.find('percent').text) if item.find('percent') is not None else 0.0
                }
                result['matches'].append(match)
            
            # Get counts
            count_elem = root.find('.//count')
            if count_elem is not None:
                result['count'] = int(count_elem.text)
            
            querywords_elem = root.find('.//querywords')
            if querywords_elem is not None:
                result['querywords'] = int(querywords_elem.text)
            
            return result
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse Copyscape response: {str(e)}")
            return {'error': 'Failed to parse response', 'matches': []}


class TurnitinClient(BasePlagiarismClient):
    """Client for Turnitin API (simplified example)."""
    
    def __init__(self):
        super().__init__()
        self.name = "turnitin"
        self.api_key = settings.TURNITIN_API_KEY
        self.base_url = settings.TURNITIN_BASE_URL
    
    def validate_credentials(self) -> bool:
        """Validate Turnitin credentials."""
        # Implementation depends on Turnitin API
        return bool(self.api_key)
    
    def check_plagiarism(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Check text using Turnitin (simplified).
        
        Note: This is a simplified example. Actual Turnitin
        integration would require proper authentication and
        submission workflow.
        """
        try:
            # This is a simplified example
            # Actual implementation would involve:
            # 1. Creating submission
            # 2. Checking status
            # 3. Retrieving report
            
            # Simulate API call
            time.sleep(2)  # Simulate processing
            
            # Mock response for demonstration
            result = {
                'similarity': 12.5,
                'matches': [
                    {
                        'source': 'Academic Database',
                        'similarity': 8.2,
                        'url': 'https://example.com/source1'
                    }
                ],
                'word_count': len(text.split()),
                'character_count': len(text)
            }
            
            return {
                'success': True,
                'source': self.name,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Turnitin check error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'source': self.name
            }


class InternalScannerClient(BasePlagiarismClient):
    """Internal plagiarism scanner using text comparison algorithms."""
    
    def __init__(self):
        super().__init__()
        self.name = "internal"
        # Load known sources database
        self.known_sources = self._load_known_sources()
    
    def _load_known_sources(self) -> list:
        """Load known sources for comparison."""
        # In production, this would load from database or external source
        return []
    
    def validate_credentials(self) -> bool:
        """Internal scanner always available."""
        return True
    
    def check_plagiarism(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Internal plagiarism check using text comparison.
        
        This is a basic implementation using n-gram comparison.
        """
        try:
            from difflib import SequenceMatcher
            import re
            
            # Clean text
            cleaned_text = re.sub(r'\s+', ' ', text).strip()
            words = cleaned_text.split()
            
            if not words:
                return {
                    'success': True,
                    'source': self.name,
                    'result': {
                        'similarity': 0.0,
                        'matches': [],
                        'word_count': 0,
                        'character_count': 0
                    }
                }
            
            # Basic n-gram analysis
            n = 6  # n-gram size
            text_ngrams = self._extract_ngrams(cleaned_text.lower(), n)
            
            matches = []
            total_similarity = 0
            
            # Compare with known sources
            for source in self.known_sources:
                source_ngrams = self._extract_ngrams(source['content'].lower(), n)
                common = len(text_ngrams.intersection(source_ngrams))
                total = len(text_ngrams)
                
                if total > 0 and common > 0:
                    similarity = (common / total) * 100
                    if similarity > 1.0:  # Only report significant matches
                        matches.append({
                            'source': source['title'],
                            'similarity': round(similarity, 2),
                            'url': source.get('url', '')
                        })
                        total_similarity += similarity
            
            # Calculate overall similarity
            overall_similarity = min(total_similarity, 100.0)
            
            result = {
                'similarity': round(overall_similarity, 2),
                'matches': matches,
                'word_count': len(words),
                'character_count': len(text)
            }
            
            return {
                'success': True,
                'source': self.name,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Internal scanner error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'source': self.name
            }
    
    def _extract_ngrams(self, text: str, n: int) -> set:
        """Extract n-grams from text."""
        words = text.split()
        ngrams = set()
        
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i + n])
            ngrams.add(ngram)
        
        return ngrams


class PlagiarismClientFactory:
    """Factory for creating plagiarism detection clients."""
    
    @staticmethod
    def get_client(source: str) -> BasePlagiarismClient:
        """
        Get plagiarism detection client for specified source.
        
        Args:
            source: Source name (copyscape, turnitin, internal, etc.)
            
        Returns:
            BasePlagiarismClient instance
            
        Raises:
            ValueError: If source is not supported
        """
        clients = {
            'copyscape': CopyscapeClient,
            'turnitin': TurnitinClient,
            'internal': InternalScannerClient,
        }
        
        client_class = clients.get(source.lower())
        if not client_class:
            raise ValueError(f"Unsupported plagiarism source: {source}")
        
        return client_class()
    
    @staticmethod
    def get_available_clients() -> list:
        """Get list of available plagiarism detection clients."""
        available = []
        
        # Check Copyscape
        try:
            client = CopyscapeClient()
            if client.validate_credentials():
                available.append('copyscape')
        except:
            pass
        
        # Check Turnitin
        try:
            client = TurnitinClient()
            if client.validate_credentials():
                available.append('turnitin')
        except:
            pass
        
        # Internal scanner is always available
        available.append('internal')
        
        return available