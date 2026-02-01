from rest_framework import serializers
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.core.exceptions import ValidationError
import re


class OutlineRequestSerializer(serializers.Serializer):
    """Serializer for outline helper requests"""
    
    topic = serializers.CharField(
        required=True,
        max_length=200,
        min_length=10,
        validators=[MinLengthValidator(10), MaxLengthValidator(200)],
        help_text="Topic of the paper (10-200 characters)"
    )
    
    template_type = serializers.ChoiceField(
        choices=[
            ('essay', 'Essay'),
            ('research_paper', 'Research Paper'),
            ('thesis', 'Thesis/Dissertation'),
            ('literature_review', 'Literature Review'),
            ('case_study', 'Case Study'),
            ('lab_report', 'Lab Report'),
        ],
        default='essay',
        required=False,
        help_text="Type of academic paper"
    )
    
    academic_level = serializers.ChoiceField(
        choices=[
            ('high_school', 'High School'),
            ('undergraduate', 'Undergraduate'),
            ('graduate', 'Graduate'),
            ('phd', 'PhD'),
        ],
        default='undergraduate',
        required=False,
        help_text="Academic level"
    )
    
    word_count_target = serializers.IntegerField(
        min_value=300,
        max_value=10000,
        default=1500,
        required=False,
        help_text="Target word count (300-10000)"
    )
    
    def validate_topic(self, value):
        """Validate topic is appropriate"""
        # Check for inappropriate content
        inappropriate_terms = [
            'cheat', 'plagiarize', 'buy essay', 'pay someone',
            'academic dishonesty', 'contract cheating'
        ]
        
        topic_lower = value.lower()
        for term in inappropriate_terms:
            if term in topic_lower:
                raise ValidationError(
                    "Topic appears to request academic dishonesty. "
                    "Please provide a legitimate academic topic."
                )
        
        return value


class GrammarCheckSerializer(serializers.Serializer):
    """Serializer for grammar checker requests"""
    
    text = serializers.CharField(
        required=True,
        min_length=10,
        max_length=5000,
        validators=[MinLengthValidator(10), MaxLengthValidator(5000)],
        help_text="Text to check (10-5000 characters)"
    )
    
    check_type = serializers.ChoiceField(
        choices=[
            ('grammar', 'Grammar Only'),
            ('style', 'Style Only'),
            ('clarity', 'Clarity Only'),
            ('all', 'All Checks'),
        ],
        default='all',
        required=False,
        help_text="Type of check to perform"
    )
    
    academic_level = serializers.ChoiceField(
        choices=[
            ('high_school', 'High School'),
            ('undergraduate', 'Undergraduate'),
            ('graduate', 'Graduate'),
            ('phd', 'PhD'),
        ],
        default='undergraduate',
        required=False,
        help_text="Academic level for style suggestions"
    )
    
    def validate_text(self, value):
        """Validate text content"""
        if len(value.strip()) < 10:
            raise ValidationError("Text must be at least 10 characters")
        
        # Check for obviously inappropriate content
        inappropriate_patterns = [
            r'\b(cheat|plagiar|buy.*essay|pay.*write|academic.*dishonest)\b',
        ]
        
        text_lower = value.lower()
        for pattern in inappropriate_patterns:
            if re.search(pattern, text_lower):
                raise ValidationError(
                    "Text appears to request or promote academic dishonesty."
                )
        
        return value


class CitationFormatSerializer(serializers.Serializer):
    """Serializer for single citation formatting requests"""
    
    citation_data = serializers.DictField(
        required=True,
        help_text="Citation data dictionary"
    )
    
    style = serializers.CharField(
        max_length=20,
        default='apa',
        required=False,
        help_text="Citation style (apa, mla, chicago, etc.)"
    )
    
    output_format = serializers.ChoiceField(
        choices=[
            ('text', 'Plain Text'),
            ('html', 'HTML'),
            ('bibtex', 'BibTeX'),
        ],
        default='text',
        required=False,
        help_text="Output format"
    )
    
    def validate_citation_data(self, value):
        """Validate citation data"""
        required_fields = ['title']
        
        for field in required_fields:
            if field not in value or not value[field]:
                raise ValidationError(f"Citation data must include '{field}'")
        
        # Validate authors/author field
        if 'authors' not in value and 'author' not in value:
            raise ValidationError("Citation data must include 'authors' or 'author'")
        
        # Validate year if present
        if 'year' in value and value['year']:
            year = str(value['year'])
            if not year.isdigit() or len(year) != 4:
                raise ValidationError("Year must be a 4-digit number")
        
        # Validate URL if present
        if 'url' in value and value['url']:
            url = value['url']
            if not url.startswith(('http://', 'https://')):
                raise ValidationError("URL must start with http:// or https://")
        
        return value


class BatchCitationSerializer(serializers.Serializer):
    """Serializer for batch citation formatting requests"""
    
    citations = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        min_length=1,
        max_length=20,
        help_text="List of citation data dictionaries (1-20)"
    )
    
    style = serializers.CharField(
        max_length=20,
        default='apa',
        required=False,
        help_text="Citation style (apa, mla, chicago, etc.)"
    )
    
    output_format = serializers.ChoiceField(
        choices=[
            ('text', 'Plain Text'),
            ('html', 'HTML'),
            ('bibtex', 'BibTeX'),
        ],
        default='text',
        required=False,
        help_text="Output format"
    )
    
    sort_by = serializers.ChoiceField(
        choices=[
            ('author', 'Author'),
            ('year', 'Year'),
            ('title', 'Title'),
        ],
        default='author',
        required=False,
        help_text="Field to sort citations by"
    )
    
    batch = serializers.BooleanField(
        default=True,
        required=False,
        help_text="Indicates this is a batch request"
    )
    
    def validate_citations(self, value):
        """Validate list of citations"""
        if len(value) > 20:
            raise ValidationError("Maximum 20 citations per batch request")
        
        # Validate each citation
        for i, citation in enumerate(value):
            try:
                # Reuse single citation validation
                serializer = CitationFormatSerializer(data={'citation_data': citation})
                if not serializer.is_valid():
                    raise ValidationError(f"Citation {i+1}: {serializer.errors}")
            except Exception as e:
                raise ValidationError(f"Citation {i+1}: {str(e)}")
        
        return value