"""
Citation Formatter Service
Formats citations in various academic styles
⚠️ This is an ASSISTIVE tool only - verify all citations manually
"""
import re
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import json

from ..models import AIToolUsageLog, CitationStyle, AIToolConfiguration


class CitationFormatterService:
    """Service for formatting citations in academic styles"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        
        # Common publication types
        self.publication_types = {
            'book': 'Book',
            'journal': 'Journal Article',
            'website': 'Website',
            'conference': 'Conference Paper',
            'thesis': 'Thesis/Dissertation',
            'report': 'Report',
            'newspaper': 'Newspaper Article',
            'chapter': 'Book Chapter',
        }
    
    def format_citation(
        self,
        citation_data: Dict,
        style: str = 'apa',
        output_format: str = 'text',
        user=None,
        session_id: str = ''
    ) -> Dict:
        """
        Format a citation in the specified style
        
        Args:
            citation_data: Dictionary containing citation information
            style: Citation style (apa, mla, chicago, harvard, ieee)
            output_format: Output format (text, html, bibtex)
            user: User requesting the formatting
            session_id: Session ID for tracking
        
        Returns:
            Dictionary containing formatted citation and metadata
        """
        # Validate citation data
        validation_result = self._validate_citation_data(citation_data)
        if not validation_result['valid']:
            return {
                'error': validation_result['message'],
                'disclaimer': self._get_disclaimer(),
            }
        
        # Get citation style
        citation_style = self._get_citation_style(style)
        if not citation_style:
            return {
                'error': f'Citation style "{style}" not found',
                'disclaimer': self._get_disclaimer(),
            }
        
        # Format citation based on publication type
        publication_type = citation_data.get('publication_type', 'book').lower()
        formatted_citation = self._format_by_type(
            citation_data, 
            publication_type, 
            citation_style, 
            output_format
        )
        
        # Generate bibliography entry if requested
        bibliography_entry = None
        if output_format == 'bibtex':
            bibliography_entry = self._generate_bibtex_entry(citation_data, publication_type)
        
        # Generate in-text citation
        in_text_citation = self._generate_in_text_citation(citation_data, citation_style)
        
        # Log usage
        if user and user.is_authenticated:
            self._log_usage(
                user=user,
                tool_type='citation_formatter',
                input_text=json.dumps(citation_data, indent=2),
                output_text=formatted_citation,
                parameters={
                    'style': style,
                    'output_format': output_format,
                    'publication_type': publication_type,
                },
                session_id=session_id
            )
        
        return {
            'formatted_citation': formatted_citation,
            'in_text_citation': in_text_citation,
            'bibliography_entry': bibliography_entry,
            'style_used': citation_style.name,
            'publication_type': self.publication_types.get(publication_type, 'Unknown'),
            'validation_warnings': validation_result['warnings'],
            'disclaimer': self._get_disclaimer(),
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'style': style,
                'format': output_format,
            }
        }
    
    def batch_format_citations(
        self,
        citations_list: List[Dict],
        style: str = 'apa',
        output_format: str = 'text',
        sort_by: str = 'author',
        user=None,
        session_id: str = ''
    ) -> Dict:
        """
        Format multiple citations at once
        
        Args:
            citations_list: List of citation dictionaries
            style: Citation style
            output_format: Output format
            sort_by: Field to sort by (author, year, title)
            user: User requesting the formatting
            session_id: Session ID for tracking
        
        Returns:
            Dictionary containing formatted citations and bibliography
        """
        if not citations_list:
            return {
                'error': 'No citations provided',
                'disclaimer': self._get_disclaimer(),
            }
        
        # Limit batch size
        max_batch_size = 20
        if len(citations_list) > max_batch_size:
            citations_list = citations_list[:max_batch_size]
        
        formatted_citations = []
        bibliography_entries = []
        
        for citation_data in citations_list:
            result = self.format_citation(
                citation_data,
                style,
                output_format,
                user=None,  # Don't log individual citations in batch
                session_id=session_id
            )
            
            if 'error' not in result:
                formatted_citations.append({
                    'original_data': citation_data,
                    'formatted': result['formatted_citation'],
                    'in_text': result['in_text_citation'],
                })
                
                if result['bibliography_entry']:
                    bibliography_entries.append(result['bibliography_entry'])
        
        # Sort citations
        formatted_citations = self._sort_citations(formatted_citations, sort_by)
        
        # Generate bibliography
        bibliography = None
        if bibliography_entries and output_format == 'bibtex':
            bibliography = self._generate_bibtex_bibliography(bibliography_entries)
        elif formatted_citations:
            bibliography = self._generate_text_bibliography(formatted_citations, style)
        
        # Log batch usage
        if user and user.is_authenticated:
            self._log_usage(
                user=user,
                tool_type='citation_formatter',
                input_text=json.dumps(citations_list, indent=2),
                output_text=json.dumps(formatted_citations, indent=2),
                parameters={
                    'style': style,
                    'output_format': output_format,
                    'sort_by': sort_by,
                    'batch_size': len(citations_list),
                },
                session_id=session_id
            )
        
        return {
            'citations': formatted_citations,
            'bibliography': bibliography,
            'total_count': len(formatted_citations),
            'style_used': style,
            'disclaimer': self._get_disclaimer(),
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'style': style,
                'format': output_format,
                'sorted_by': sort_by,
            }
        }
    
    def _validate_citation_data(self, data: Dict) -> Dict:
        """Validate citation data"""
        
        required_fields_by_type = {
            'book': ['authors', 'title', 'year', 'publisher'],
            'journal': ['authors', 'title', 'journal', 'year', 'volume'],
            'website': ['title', 'url', 'access_date'],
            'conference': ['authors', 'title', 'conference', 'year'],
            'thesis': ['author', 'title', 'year', 'institution'],
            'report': ['authors', 'title', 'year', 'institution'],
            'newspaper': ['author', 'title', 'newspaper', 'date'],
            'chapter': ['authors', 'title', 'book_title', 'year', 'publisher'],
        }
        
        publication_type = data.get('publication_type', 'book').lower()
        required_fields = required_fields_by_type.get(publication_type, ['authors', 'title', 'year'])
        
        missing_fields = []
        warnings = []
        
        # Check required fields
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)
        
        # Validate authors
        if 'authors' in data:
            authors = data['authors']
            if isinstance(authors, str):
                # Try to parse author string
                parsed_authors = self._parse_authors_string(authors)
                if not parsed_authors:
                    warnings.append("Authors field format may be incorrect")
        
        # Validate dates
        if 'year' in data:
            year = data['year']
            if not str(year).isdigit() or len(str(year)) != 4:
                warnings.append(f"Year '{year}' may not be valid")
        
        if 'access_date' in data:
            access_date = data['access_date']
            if not re.match(r'\d{4}-\d{2}-\d{2}', access_date):
                warnings.append("Access date should be in YYYY-MM-DD format")
        
        # Validate URLs
        if 'url' in data:
            url = data['url']
            if not url.startswith(('http://', 'https://')):
                warnings.append("URL should start with http:// or https://")
        
        # Validate page numbers
        if 'pages' in data:
            pages = data['pages']
            if not re.match(r'\d+(-\d+)?', str(pages)):
                warnings.append("Pages format should be like '123' or '123-145'")
        
        valid = len(missing_fields) == 0
        
        return {
            'valid': valid,
            'message': f"Missing required fields: {', '.join(missing_fields)}" if missing_fields else '',
            'warnings': warnings,
        }
    
    def _get_citation_style(self, style: str) -> Optional[CitationStyle]:
        """Get citation style configuration"""
        
        cache_key = f"citation_style_{style}"
        
        citation_style = cache.get(cache_key)
        if not citation_style:
            try:
                citation_style = CitationStyle.objects.get(
                    abbreviation__iexact=style,
                    is_active=True
                )
                cache.set(cache_key, citation_style, self.cache_timeout)
            except CitationStyle.DoesNotExist:
                # Try to create default styles if they don't exist
                citation_style = self._create_default_style(style)
        
        return citation_style
    
    def _format_by_type(
        self,
        data: Dict,
        pub_type: str,
        style: CitationStyle,
        output_format: str
    ) -> str:
        """Format citation based on publication type"""
        
        formatter_methods = {
            'book': self._format_book_citation,
            'journal': self._format_journal_citation,
            'website': self._format_website_citation,
            'conference': self._format_conference_citation,
            'thesis': self._format_thesis_citation,
            'report': self._format_report_citation,
            'newspaper': self._format_newspaper_citation,
            'chapter': self._format_chapter_citation,
        }
        
        formatter = formatter_methods.get(pub_type, self._format_generic_citation)
        
        formatted = formatter(data, style)
        
        # Convert to requested format
        if output_format == 'html':
            formatted = self._convert_to_html(formatted)
        elif output_format == 'bibtex':
            formatted = self._generate_bibtex_entry(data, pub_type)
        
        return formatted
    
    def _format_book_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format book citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        edition = data.get('edition', '')
        year = data.get('year', '')
        publisher = data.get('publisher', '')
        city = data.get('city', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year). Title of book (Edition). Publisher.
            citation = f"{authors} ({year}). {title}"
            if edition:
                citation += f" ({edition} ed.)"
            citation += f". {publisher}."
            if city:
                citation += f" {city}."
        
        elif style_name == 'mla':
            # MLA: Author. Title of Book. Edition, Publisher, Year.
            citation = f"{authors}. {title}."
            if edition:
                citation += f" {edition} ed.,"
            citation += f" {publisher}, {year}."
        
        elif style_name == 'chicago':
            # Chicago: Author. Year. Title of Book. Edition. City: Publisher.
            citation = f"{authors}. {year}. {title}."
            if edition:
                citation += f" {edition} ed."
            if city:
                citation += f" {city}: {publisher}."
            else:
                citation += f" {publisher}."
        
        else:
            # Generic format
            citation = f"{authors}. ({year}). {title}. {publisher}."
        
        return citation
    
    def _format_journal_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format journal article citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        journal = data.get('journal', '')
        year = data.get('year', '')
        volume = data.get('volume', '')
        issue = data.get('issue', '')
        pages = data.get('pages', '')
        doi = data.get('doi', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year). Title of article. Journal, Volume(Issue), Pages. DOI
            citation = f"{authors} ({year}). {title}. {journal}, {volume}"
            if issue:
                citation += f"({issue})"
            citation += f", {pages}."
            if doi:
                citation += f" https://doi.org/{doi}"
        
        elif style_name == 'mla':
            # MLA: Author. "Title of Article." Journal, vol. Volume, no. Issue, Year, pp. Pages.
            citation = f'{authors}. "{title}." {journal}, vol. {volume}'
            if issue:
                citation += f", no. {issue}"
            citation += f", {year}, pp. {pages}."
        
        elif style_name == 'chicago':
            # Chicago: Author. Year. "Title of Article." Journal Volume (Issue): Pages.
            citation = f'{authors}. {year}. "{title}." {journal} {volume}'
            if issue:
                citation += f" ({issue})"
            citation += f": {pages}."
        
        else:
            # Generic format
            citation = f"{authors}. ({year}). {title}. {journal}, {volume}, {pages}."
        
        return citation
    
    def _format_website_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format website citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        website = data.get('website', '')
        url = data.get('url', '')
        access_date = data.get('access_date', '')
        publication_date = data.get('publication_date', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year, Month Day). Title of webpage. Website. URL
            date_part = publication_date if publication_date else access_date
            citation = f"{authors} ({date_part}). {title}. {website}. {url}"
        
        elif style_name == 'mla':
            # MLA: Author. "Title of Webpage." Website, Date, URL.
            citation = f'{authors}. "{title}." {website}, {publication_date}, {url}.'
            if access_date:
                citation += f" Accessed {access_date}."
        
        elif style_name == 'chicago':
            # Chicago: Author. "Title of Webpage." Website. Date. URL.
            citation = f'{authors}. "{title}." {website}. {publication_date}. {url}.'
        
        else:
            # Generic format
            citation = f"{authors}. ({publication_date}). {title}. {website}. Retrieved {access_date} from {url}"
        
        return citation
    
    def _format_conference_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format conference paper citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        conference = data.get('conference', '')
        year = data.get('year', '')
        location = data.get('location', '')
        pages = data.get('pages', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year, Month). Title of paper. In Proceedings of Conference (pp. Pages). Location.
            citation = f"{authors} ({year}). {title}. In Proceedings of {conference} (pp. {pages}). {location}."
        
        elif style_name == 'ieee':
            # IEEE: A. A. Author, "Title of paper," in Proc. Conference, Location, Year, pp. Pages.
            citation = f'{authors}, "{title}," in Proc. {conference}, {location}, {year}, pp. {pages}.'
        
        else:
            # Generic format
            citation = f"{authors}. ({year}). {title}. In {conference} (pp. {pages}). {location}."
        
        return citation
    
    def _format_thesis_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format thesis/dissertation citation"""
        
        author = self._format_authors(data.get('author', ''), style)
        title = data.get('title', '')
        year = data.get('year', '')
        institution = data.get('institution', '')
        thesis_type = data.get('type', 'Doctoral dissertation')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year). Title of dissertation [Doctoral dissertation, Institution]. Database.
            citation = f"{author} ({year}). {title} [{thesis_type}, {institution}]."
        
        elif style_name == 'mla':
            # MLA: Author. Title of Dissertation. Year. Institution, Thesis type.
            citation = f"{author}. {title}. {year}. {institution}, {thesis_type}."
        
        else:
            # Generic format
            citation = f"{author}. ({year}). {title}. {thesis_type}, {institution}."
        
        return citation
    
    def _format_report_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format report citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        year = data.get('year', '')
        institution = data.get('institution', '')
        report_number = data.get('report_number', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year). Title of report (Report No. XXX). Institution.
            citation = f"{authors} ({year}). {title}"
            if report_number:
                citation += f" (Report No. {report_number})"
            citation += f". {institution}."
        
        else:
            # Generic format
            citation = f"{authors}. ({year}). {title}. {institution}."
            if report_number:
                citation += f" Report No. {report_number}."
        
        return citation
    
    def _format_newspaper_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format newspaper article citation"""
        
        author = self._format_authors(data.get('author', ''), style)
        title = data.get('title', '')
        newspaper = data.get('newspaper', '')
        date = data.get('date', '')
        pages = data.get('pages', '')
        url = data.get('url', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year, Month Day). Title of article. Newspaper, Pages.
            citation = f"{author} ({date}). {title}. {newspaper}, {pages}."
            if url:
                citation += f" {url}"
        
        elif style_name == 'mla':
            # MLA: Author. "Title of Article." Newspaper, Date, pp. Pages.
            citation = f'{author}. "{title}." {newspaper}, {date}, pp. {pages}.'
            if url:
                citation += f" {url}."
        
        else:
            # Generic format
            citation = f"{author}. ({date}). {title}. {newspaper}, {pages}."
        
        return citation
    
    def _format_chapter_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format book chapter citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        book_authors = self._format_authors(data.get('book_authors', ''), style)
        book_title = data.get('book_title', '')
        year = data.get('year', '')
        publisher = data.get('publisher', '')
        pages = data.get('pages', '')
        edition = data.get('edition', '')
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Author, A. A. (Year). Title of chapter. In A. Editor (Ed.), Title of book (pp. Pages). Publisher.
            citation = f"{authors} ({year}). {title}. In {book_authors} (Ed.), {book_title} (pp. {pages}). {publisher}."
        
        elif style_name == 'chicago':
            # Chicago: Author. Year. "Title of Chapter." In Title of Book, edited by Editor, Pages. City: Publisher.
            citation = f'{authors}. {year}. "{title}." In {book_title}, edited by {book_authors}, {pages}. {publisher}.'
        
        else:
            # Generic format
            citation = f"{authors}. ({year}). {title}. In {book_authors} (Ed.), {book_title} (pp. {pages}). {publisher}."
        
        return citation
    
    def _format_generic_citation(self, data: Dict, style: CitationStyle) -> str:
        """Format generic citation"""
        
        authors = self._format_authors(data.get('authors', ''), style)
        title = data.get('title', '')
        year = data.get('year', '')
        publication = data.get('publication', '')
        
        return f"{authors}. ({year}). {title}. {publication}."
    
    def _format_authors(self, authors_input, style: CitationStyle) -> str:
        """Format authors according to style"""
        
        if not authors_input:
            return ""
        
        # Parse authors
        authors = self._parse_authors_string(authors_input)
        if not authors:
            return authors_input
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            # APA: Last, F. M., Last, F. M., & Last, F. M.
            formatted = []
            for i, author in enumerate(authors):
                if i == len(authors) - 1 and len(authors) > 1:
                    formatted.append(f"& {author['last']}, {author['first'][0]}.")
                else:
                    formatted.append(f"{author['last']}, {author['first'][0]}.")
            
            return ", ".join(formatted)
        
        elif style_name == 'mla':
            # MLA: Last, First, and First Last.
            if len(authors) == 1:
                return f"{authors[0]['last']}, {authors[0]['first']}."
            elif len(authors) == 2:
                return f"{authors[0]['last']}, {authors[0]['first']}, and {authors[1]['first']} {authors[1]['last']}."
            else:
                return f"{authors[0]['last']}, {authors[0]['first']}, et al."
        
        elif style_name == 'chicago':
            # Chicago: First Last, First Last, and First Last.
            formatted = []
            for i, author in enumerate(authors):
                if i == len(authors) - 1 and len(authors) > 1:
                    formatted.append(f"and {author['first']} {author['last']}")
                else:
                    formatted.append(f"{author['first']} {author['last']}")
            
            return ", ".join(formatted)
        
        else:
            # Generic: Last, F.
            formatted = []
            for author in authors:
                formatted.append(f"{author['last']}, {author['first'][0]}.")
            
            return ", ".join(formatted)
    
    def _parse_authors_string(self, authors_str: str) -> List[Dict]:
        """Parse authors string into structured format"""
        
        if not authors_str:
            return []
        
        # Try different formats
        authors = []
        
        # Format: "Last, First" or "Last, First; Last, First"
        if ';' in authors_str or ',' in authors_str:
            parts = authors_str.split(';') if ';' in authors_str else [authors_str]
            
            for part in parts:
                part = part.strip()
                if ',' in part:
                    last, first = part.split(',', 1)
                    authors.append({
                        'first': first.strip(),
                        'last': last.strip(),
                    })
                else:
                    # Try to split by space
                    name_parts = part.split()
                    if len(name_parts) >= 2:
                        authors.append({
                            'first': ' '.join(name_parts[:-1]),
                            'last': name_parts[-1],
                        })
        else:
            # Format: "First Last and First Last"
            and_parts = authors_str.split(' and ')
            for part in and_parts:
                name_parts = part.split()
                if len(name_parts) >= 2:
                    authors.append({
                        'first': ' '.join(name_parts[:-1]),
                        'last': name_parts[-1],
                    })
        
        return authors
    
    def _generate_in_text_citation(self, data: Dict, style: CitationStyle) -> str:
        """Generate in-text citation"""
        
        authors = self._parse_authors_string(data.get('authors', data.get('author', '')))
        year = data.get('year', '')
        
        if not authors:
            title = data.get('title', '')
            if len(title) > 20:
                title = title[:20] + '...'
            return f'("{title}", {year})' if year else f'("{title}")'
        
        style_name = style.abbreviation.lower()
        
        if style_name == 'apa':
            if len(authors) == 1:
                return f"({authors[0]['last']}, {year})"
            elif len(authors) == 2:
                return f"({authors[0]['last']} & {authors[1]['last']}, {year})"
            else:
                return f"({authors[0]['last']} et al., {year})"
        
        elif style_name == 'mla':
            if len(authors) == 1:
                return f"({authors[0]['last']})"
            elif len(authors) == 2:
                return f"({authors[0]['last']} and {authors[1]['last']})"
            else:
                return f"({authors[0]['last']} et al.)"
        
        else:
            if len(authors) == 1:
                return f"({authors[0]['last']}, {year})"
            else:
                return f"({authors[0]['last']} et al., {year})"
    
    def _generate_bibtex_entry(self, data: Dict, pub_type: str) -> str:
        """Generate BibTeX entry"""
        
        bibtex_types = {
            'book': 'book',
            'journal': 'article',
            'website': 'misc',
            'conference': 'inproceedings',
            'thesis': 'phdthesis',
            'report': 'techreport',
            'newspaper': 'article',
            'chapter': 'incollection',
        }
        
        entry_type = bibtex_types.get(pub_type, 'misc')
        
        # Generate citation key
        authors = self._parse_authors_string(data.get('authors', data.get('author', '')))
        year = data.get('year', '')
        
        if authors and year:
            citation_key = f"{authors[0]['last']}{year}"
        else:
            citation_key = f"unknown{hash(str(data)) % 10000}"
        
        # Build BibTeX entry
        lines = [f"@{entry_type}{{{citation_key},"]
        
        fields = [
            ('author', data.get('authors', data.get('author', ''))),
            ('title', data.get('title', '')),
            ('year', data.get('year', '')),
            ('journal', data.get('journal', '')),
            ('booktitle', data.get('book_title', data.get('conference', ''))),
            ('publisher', data.get('publisher', '')),
            ('volume', data.get('volume', '')),
            ('number', data.get('issue', '')),
            ('pages', data.get('pages', '')),
            ('url', data.get('url', '')),
            ('doi', data.get('doi', '')),
            ('institution', data.get('institution', '')),
            ('edition', data.get('edition', '')),
        ]
        
        for key, value in fields:
            if value:
                lines.append(f"  {key} = {{{value}}},")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def _generate_bibtex_bibliography(self, entries: List[str]) -> str:
        """Generate complete BibTeX bibliography"""
        
        return "\n\n".join(entries)
    
    def _generate_text_bibliography(self, citations: List[Dict], style: str) -> str:
        """Generate formatted bibliography in text format"""
        
        lines = [f"References ({style.upper()} Style)", "=" * 40, ""]
        
        for i, citation in enumerate(citations, 1):
            lines.append(f"{i}. {citation['formatted']}")
            lines.append("")  # Blank line between entries
        
        return "\n".join(lines)
    
    def _convert_to_html(self, text: str) -> str:
        """Convert citation to HTML format"""
        
        # Simple HTML conversion
        html = text.replace('\n', '<br>')
        
        # Italicize titles
        import re
        html = re.sub(r'"([^"]+)"', r'<em>\1</em>', html)
        
        # Make URLs clickable
        html = re.sub(
            r'(https?://[^\s]+)',
            r'<a href="\1" target="_blank">\1</a>',
            html
        )
        
        return html
    
    def _sort_citations(self, citations: List[Dict], sort_by: str) -> List[Dict]:
        """Sort citations by specified field"""
        
        if not citations:
            return citations
        
        def get_sort_key(citation):
            data = citation['original_data']
            
            if sort_by == 'author':
                authors = self._parse_authors_string(data.get('authors', data.get('author', '')))
                if authors:
                    return authors[0]['last'].lower()
                return ''
            
            elif sort_by == 'year':
                return data.get('year', '0000')
            
            elif sort_by == 'title':
                return data.get('title', '').lower()
            
            return ''
        
        return sorted(citations, key=get_sort_key)
    
    def _create_default_style(self, style: str) -> Optional[CitationStyle]:
        """Create default citation style if it doesn't exist"""
        
        default_styles = {
            'apa': {
                'name': 'APA 7th Edition',
                'abbreviation': 'APA',
                'book_example': 'Author, A. A. (2023). Title of book. Publisher.',
                'journal_example': 'Author, A. A. (2023). Title of article. Journal, 12(3), 45-67.',
                'website_example': 'Author, A. A. (2023, January 15). Title of webpage. Website. https://example.com',
            },
            'mla': {
                'name': 'MLA 9th Edition',
                'abbreviation': 'MLA',
                'book_example': 'Author, First. Title of Book. Publisher, 2023.',
                'journal_example': 'Author, First. "Title of Article." Journal, vol. 12, no. 3, 2023, pp. 45-67.',
                'website_example': 'Author, First. "Title of Webpage." Website, 15 Jan. 2023, https://example.com.',
            },
            'chicago': {
                'name': 'Chicago Manual of Style',
                'abbreviation': 'Chicago',
                'book_example': 'Author, First. 2023. Title of Book. City: Publisher.',
                'journal_example': 'Author, First. 2023. "Title of Article." Journal 12 (3): 45-67.',
                'website_example': 'Author, First. 2023. "Title of Webpage." Website. https://example.com.',
            },
        }
        
        style_data = default_styles.get(style.lower())
        if not style_data:
            return None
        
        try:
            citation_style = CitationStyle.objects.create(
                name=style_data['name'],
                abbreviation=style_data['abbreviation'],
                book_example=style_data['book_example'],
                journal_example=style_data['journal_example'],
                website_example=style_data['website_example'],
                rules={},
                is_active=True,
            )
            return citation_style
        except Exception:
            return None
    
    def _get_disclaimer(self) -> str:
        """Get disclaimer for citation formatting"""
        
        return (
            "⚠️ IMPORTANT: This citation is AI-generated and must be verified. "
            "You must:\n"
            "1. Check against official style guides\n"
            "2. Verify all information is accurate\n"
            "3. Ensure proper formatting for your specific requirements\n"
            "4. Consult with your instructor if unsure\n"
            "This tool is for assistance only - you are responsible for final citation accuracy."
        )
    
    def _log_usage(
        self,
        user,
        tool_type: str,
        input_text: str,
        output_text: str,
        parameters: Dict,
        session_id: str = ''
    ) -> None:
        """Log AI tool usage"""
        
        # Get IP address from request if available
        ip_address = None
        if hasattr(user, '_request'):
            request = getattr(user, '_request', None)
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0]
                else:
                    ip_address = request.META.get('REMOTE_ADDR')
        
        AIToolUsageLog.objects.create(
            user=user,
            tool_type=tool_type,
            input_text=input_text[:5000],  # Limit input length
            output_text=output_text[:5000],  # Limit output length
            parameters=parameters,
            session_id=session_id,
            ip_address=ip_address,
            has_disclaimer=True,
        )