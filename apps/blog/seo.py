"""
SEO optimization utilities for blog content
"""
import re
from typing import Dict, List, Tuple, Optional
from django.utils.html import strip_tags
from django.conf import settings
from django.core.cache import cache
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
import json


class SEOAnalyzer:
    """Analyze and optimize content for SEO"""
    
    def __init__(self, content: str, title: str = "", meta_description: str = ""):
        self.content = content
        self.title = title
        self.meta_description = meta_description
        self.plain_text = strip_tags(content)
        self.word_count = len(self.plain_text.split())
        
    def calculate_readability(self) -> float:
        """
        Calculate Flesch Reading Ease score
        Returns score between 0-100 (higher = easier to read)
        """
        sentences = re.split(r'[.!?]+', self.plain_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0
        
        total_sentences = len(sentences)
        total_words = len(self.plain_text.split())
        total_syllables = sum(self._count_syllables(word) for word in self.plain_text.split())
        
        if total_words == 0 or total_sentences == 0:
            return 0
        
        words_per_sentence = total_words / total_sentences
        syllables_per_word = total_syllables / total_words
        
        # Flesch Reading Ease formula
        score = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
        
        return max(0, min(100, round(score, 2)))
    
    def analyze_keyword_density(self, keywords: List[str] = None) -> Dict:
        """
        Analyze keyword density and placement
        """
        if keywords is None:
            # Extract potential keywords from title and content
            keywords = self._extract_potential_keywords()
        
        result = {
            'keywords': {},
            'density_warnings': [],
            'placement_issues': []
        }
        
        content_lower = self.plain_text.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Count occurrences
            count = content_lower.count(keyword_lower)
            density = (count / self.word_count * 100) if self.word_count > 0 else 0
            
            result['keywords'][keyword] = {
                'count': count,
                'density': round(density, 2),
                'in_title': keyword_lower in self.title.lower(),
                'in_first_paragraph': self._check_first_paragraph(keyword_lower),
                'in_meta_description': keyword_lower in self.meta_description.lower()
            }
            
            # Check density warnings
            if density > 3:
                result['density_warnings'].append(
                    f"'{keyword}' density ({density}%) might be too high"
                )
            elif density < 0.5 and count > 0:
                result['density_warnings'].append(
                    f"'{keyword}' density ({density}%) might be too low"
                )
        
        return result
    
    def check_heading_structure(self) -> Dict:
        """
        Analyze HTML heading structure
        """
        soup = BeautifulSoup(self.content, 'html.parser')
        
        headings = {
            'h1': soup.find_all('h1'),
            'h2': soup.find_all('h2'),
            'h3': soup.find_all('h3'),
            'h4': soup.find_all('h4'),
            'h5': soup.find_all('h5'),
            'h6': soup.find_all('h6'),
        }
        
        issues = []
        recommendations = []
        
        # Check for multiple H1s
        if len(headings['h1']) > 1:
            issues.append("Multiple H1 tags found")
            recommendations.append("Use only one H1 tag per page")
        
        # Check heading hierarchy
        if headings['h2'] and not headings['h1']:
            issues.append("H2 found without H1")
            recommendations.append("Add an H1 tag before using H2")
        
        if headings['h3'] and not headings['h2']:
            issues.append("H3 found without H2")
            recommendations.append("Ensure proper heading hierarchy")
        
        # Check heading lengths
        for tag_name, tag_list in headings.items():
            for heading in tag_list:
                text = heading.get_text().strip()
                if len(text) > 70:
                    issues.append(f"{tag_name.upper()} too long: '{text[:50]}...'")
                    recommendations.append(f"Keep {tag_name.upper()} under 70 characters")
        
        return {
            'counts': {k: len(v) for k, v in headings.items()},
            'issues': issues,
            'recommendations': recommendations,
            'headings': [
                {'tag': tag.name, 'text': tag.get_text()[:100]}
                for tag_list in headings.values()
                for tag in tag_list
            ]
        }
    
    def analyze_meta_tags(self) -> Dict:
        """
        Analyze meta title and description
        """
        issues = []
        recommendations = []
        
        # Title analysis
        title_len = len(self.title)
        if title_len < 30:
            issues.append(f"Title too short ({title_len} chars)")
            recommendations.append("Aim for 50-60 characters")
        elif title_len > 60:
            issues.append(f"Title too long ({title_len} chars)")
            recommendations.append("Keep title under 60 characters")
        
        # Meta description analysis
        meta_len = len(self.meta_description)
        if meta_len < 120:
            issues.append(f"Meta description too short ({meta_len} chars)")
            recommendations.append("Aim for 150-160 characters")
        elif meta_len > 160:
            issues.append(f"Meta description too long ({meta_len} chars)")
            recommendations.append("Keep meta description under 160 characters")
        
        return {
            'title_length': title_len,
            'meta_description_length': meta_len,
            'issues': issues,
            'recommendations': recommendations
        }
    
    def check_internal_linking(self, internal_urls: List[str]) -> Dict:
        """
        Check internal linking opportunities
        """
        soup = BeautifulSoup(self.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        internal_links = []
        external_links = []
        
        for link in links:
            href = link['href']
            parsed = urlparse(href)
            
            if parsed.netloc in ['', settings.DOMAIN_NAME] or href.startswith('/'):
                internal_links.append({
                    'text': link.get_text()[:50],
                    'href': href,
                    'follow': 'nofollow' not in link.get('rel', [])
                })
            else:
                external_links.append({
                    'text': link.get_text()[:50],
                    'href': href,
                    'follow': 'nofollow' not in link.get('rel', [])
                })
        
        issues = []
        recommendations = []
        
        if len(internal_links) < 2:
            issues.append("Low internal linking")
            recommendations.append("Add more internal links to related content")
        
        return {
            'internal_links_count': len(internal_links),
            'external_links_count': len(external_links),
            'internal_links': internal_links[:10],  # Limit for response
            'external_links': external_links[:10],
            'issues': issues,
            'recommendations': recommendations
        }
    
    def generate_recommendations(self) -> List[str]:
        """
        Generate SEO recommendations based on analysis
        """
        recommendations = []
        
        # Readability
        readability = self.calculate_readability()
        if readability < 60:
            recommendations.append(
                f"Improve readability (score: {readability}/100). "
                "Use shorter sentences and simpler words."
            )
        
        # Keyword analysis
        keyword_result = self.analyze_keyword_density()
        for warning in keyword_result['density_warnings']:
            recommendations.append(warning)
        
        # Heading structure
        heading_result = self.check_heading_structure()
        recommendations.extend(heading_result['recommendations'])
        
        # Meta tags
        meta_result = self.analyze_meta_tags()
        recommendations.extend(meta_result['recommendations'])
        
        # Content length
        if self.word_count < 300:
            recommendations.append("Content is too short. Aim for at least 300 words.")
        elif self.word_count > 2000:
            recommendations.append("Consider breaking up long content into multiple posts.")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _count_syllables(self, word: str) -> int:
        """Approximate syllable count for a word"""
        word = word.lower()
        count = 0
        
        # Remove final 'e'
        if word.endswith('e'):
            word = word[:-1]
        
        # Count vowel groups
        vowels = 'aeiouy'
        prev_char_was_vowel = False
        
        for char in word:
            if char in vowels:
                if not prev_char_was_vowel:
                    count += 1
                prev_char_was_vowel = True
            else:
                prev_char_was_vowel = False
        
        # Ensure at least one syllable
        return max(1, count)
    
    def _extract_potential_keywords(self) -> List[str]:
        """Extract potential keywords from title and content"""
        # Simple keyword extraction - can be enhanced with NLP
        words = re.findall(r'\b\w{4,}\b', self.title.lower())
        
        # Add common academic terms
        academic_terms = [
            'essay', 'writing', 'research', 'paper', 'thesis',
            'academic', 'university', 'college', 'study', 'assignment'
        ]
        
        keywords = list(set(words[:5] + academic_terms[:3]))
        return [k for k in keywords if len(k) > 3][:8]  # Limit to 8 keywords
    
    def _check_first_paragraph(self, keyword: str) -> bool:
        """Check if keyword appears in first paragraph"""
        soup = BeautifulSoup(self.content, 'html.parser')
        first_p = soup.find('p')
        
        if first_p:
            return keyword in first_p.get_text().lower()
        return False


class SEOSitemapGenerator:
    """Generate SEO-friendly sitemaps"""
    
    @staticmethod
    def generate_blog_sitemap(posts) -> str:
        """Generate XML sitemap for blog posts"""
        from django.contrib.sitemaps import Sitemap
        from django.contrib.sites.models import Site
        
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}"
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add blog posts
        for post in posts:
            if post.is_published():
                url = f"{base_url}{post.get_absolute_url()}"
                lastmod = post.updated_at.strftime('%Y-%m-%d')
                
                xml.append('  <url>')
                xml.append(f'    <loc>{url}</loc>')
                xml.append(f'    <lastmod>{lastmod}</lastmod>')
                xml.append(f'    <changefreq>monthly</changefreq>')
                xml.append(f'    <priority>0.7</priority>')
                xml.append('  </url>')
        
        # Add categories
        from .models import BlogCategory
        categories = BlogCategory.objects.filter(is_active=True)
        
        for category in categories:
            url = f"{base_url}{category.get_absolute_url()}"
            
            xml.append('  <url>')
            xml.append(f'    <loc>{url}</loc>')
            xml.append(f'    <changefreq>weekly</changefreq>')
            xml.append(f'    <priority>0.5</priority>')
            xml.append('  </url>')
        
        xml.append('</urlset>')
        
        return '\n'.join(xml)
    
    @staticmethod
    def generate_robots_txt() -> str:
        """Generate robots.txt file"""
        from django.contrib.sites.models import Site
        
        current_site = Site.objects.get_current()
        
        lines = [
            "User-agent: *",
            "Allow: /",
            "",
            f"Sitemap: https://{current_site.domain}/sitemap.xml",
            "",
            "# Development/Staging blocks",
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /api/",
            "Disallow: /media/private/",
            "",
            "# Crawl delay to be respectful",
            "Crawl-delay: 2"
        ]
        
        return '\n'.join(lines)


class OpenGraphGenerator:
    """Generate Open Graph meta tags for social sharing"""
    
    @staticmethod
    def generate_for_post(post) -> Dict:
        """Generate Open Graph tags for a blog post"""
        from django.contrib.sites.models import Site
        
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}"
        
        return {
            'og:type': 'article',
            'og:title': post.title,
            'og:description': post.excerpt,
            'og:url': f"{base_url}{post.get_absolute_url()}",
            'og:site_name': 'EBWriting - Academic Assistance',
            'og:published_time': post.published_at.isoformat() if post.published_at else None,
            'og:modified_time': post.updated_at.isoformat(),
            'og:author': post.author.get_full_name() if post.author else 'EBWriting Team',
            'article:section': post.category.name if post.category else 'Academic Writing',
            'article:tag': [tag.name for tag in post.tags.all()][:5],
            'og:image': post.featured_image.url if post.featured_image else f"{base_url}/static/img/og-default.jpg",
            'og:image:width': '1200',
            'og:image:height': '630',
        }
    
    @staticmethod
    def generate_twitter_card(post) -> Dict:
        """Generate Twitter Card meta tags"""
        from django.contrib.sites.models import Site
        
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}"
        
        return {
            'twitter:card': 'summary_large_image',
            'twitter:site': '@EBWriting',
            'twitter:creator': f"@{post.author.username}" if post.author else '@EBWriting',
            'twitter:title': post.title,
            'twitter:description': post.excerpt[:200],
            'twitter:image': post.featured_image.url if post.featured_image else f"{base_url}/static/img/twitter-default.jpg",
        }