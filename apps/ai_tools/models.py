import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json

class AIToolUsageLog(models.Model):
    """
    Log all AI tool usage for audit and compliance
    """
    
    class ToolType(models.TextChoices):
        OUTLINE_HELPER = 'outline_helper', 'Outline Helper'
        GRAMMAR_CHECKER = 'grammar_checker', 'Grammar Checker'
        CITATION_FORMATTER = 'citation_formatter', 'Citation Formatter'
        PARAPHRASING_TOOL = 'paraphrasing_tool', 'Paraphrasing Tool'
        THESIS_GENERATOR = 'thesis_generator', 'Thesis Statement Generator'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_tool_usage'
    )
    
    tool_type = models.CharField(max_length=50, choices=ToolType.choices)
    
    # Input and output
    input_text = models.TextField()
    output_text = models.TextField()
    parameters = models.JSONField(default=dict, blank=True)
    
    # Metadata
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Compliance flags
    has_disclaimer = models.BooleanField(default=True)
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_ai_outputs'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Tool Usage Log"
        verbose_name_plural = "AI Tool Usage Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'tool_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['session_id']),
        ]
        permissions = [
            ('can_review_ai_output', 'Can review AI tool outputs'),
            ('can_export_ai_logs', 'Can export AI tool usage logs'),
        ]

    def __str__(self):
        return f"{self.get_tool_type_display()} - {self.user} - {self.created_at}"

    def mark_reviewed(self, reviewer):
        """Mark the output as reviewed"""
        self.is_reviewed = True
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()


class AIToolConfiguration(models.Model):
    """
    Configuration for AI tools (tokens, limits, etc.)
    """
    
    tool_type = models.CharField(
        max_length=50,
        choices=AIToolUsageLog.ToolType.choices,
        unique=True
    )
    
    # Usage limits
    daily_limit_per_user = models.PositiveIntegerField(
        default=10,
        help_text="Maximum uses per user per day"
    )
    max_input_length = models.PositiveIntegerField(
        default=5000,
        help_text="Maximum input characters"
    )
    max_output_length = models.PositiveIntegerField(
        default=2000,
        help_text="Maximum output characters"
    )
    
    # AI Parameters
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        help_text="Creativity/randomness (0.0-2.0)"
    )
    max_tokens = models.PositiveIntegerField(default=500)
    
    # Safety controls
    content_filter_enabled = models.BooleanField(default=True)
    plagiarism_check_enabled = models.BooleanField(default=True)
    require_review = models.BooleanField(
        default=False,
        help_text="Require admin review before showing to user"
    )
    
    # Status
    is_enabled = models.BooleanField(default=True)
    maintenance_message = models.TextField(blank=True)
    
    # Audit
    last_modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        verbose_name = "AI Tool Configuration"
        verbose_name_plural = "AI Tool Configurations"
        ordering = ['tool_type']

    def __str__(self):
        return f"{self.get_tool_type_display()} Configuration"


class AIToolTemplate(models.Model):
    """
    Templates for different types of academic writing
    """
    
    class TemplateType(models.TextChoices):
        ESSAY = 'essay', 'Essay'
        RESEARCH_PAPER = 'research_paper', 'Research Paper'
        THESIS = 'thesis', 'Thesis/Dissertation'
        LITERATURE_REVIEW = 'literature_review', 'Literature Review'
        CASE_STUDY = 'case_study', 'Case Study'
        LAB_REPORT = 'lab_report', 'Lab Report'
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=50, choices=TemplateType.choices)
    
    # FIXED: Replaced ArrayField with JSONField for SQLite compatibility
    sections = models.JSONField(
        default=list, 
        help_text="List of section names for this template type"
    )
    
    # Guidelines
    guidelines = models.TextField(help_text="General guidelines for this type")
    common_mistakes = models.TextField(blank=True, help_text="Common mistakes to avoid")
    
    # FIXED: Replaced ArrayField with JSONField for SQLite compatibility
    recommended_sources = models.JSONField(
        blank=True,
        default=list,
        help_text="Recommended sources or databases"
    )
    
    # Examples
    example_outline = models.TextField(blank=True)
    example_thesis = models.TextField(blank=True)
    
    # Metadata
    academic_level = models.CharField(
        max_length=50,
        choices=[
            ('high_school', 'High School'),
            ('undergraduate', 'Undergraduate'),
            ('graduate', 'Graduate'),
            ('phd', 'PhD'),
        ],
        default='undergraduate'
    )
    
    word_count_range = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., 1500-2000 words"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Tool Template"
        verbose_name_plural = "AI Tool Templates"
        ordering = ['template_type', 'academic_level']
        unique_together = ['template_type', 'academic_level']

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class CitationStyle(models.Model):
    """
    Supported citation styles
    """
    
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    
    # Examples
    book_example = models.TextField(help_text="Example citation for a book")
    journal_example = models.TextField(help_text="Example citation for a journal article")
    website_example = models.TextField(help_text="Example citation for a website")
    
    # Rules
    rules = models.JSONField(default=dict, help_text="Formatting rules in JSON format")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Citation Style"
        verbose_name_plural = "Citation Styles"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class WritingFeedback(models.Model):
    """
    AI-generated writing feedback
    """
    
    class FeedbackType(models.TextChoices):
        GRAMMAR = 'grammar', 'Grammar'
        STYLE = 'style', 'Writing Style'
        STRUCTURE = 'structure', 'Structure'
        CLARITY = 'clarity', 'Clarity'
        COHERENCE = 'coherence', 'Coherence'
        ARGUMENT = 'argument', 'Argument Strength'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='writing_feedback'
    )
    
    feedback_type = models.CharField(max_length=50, choices=FeedbackType.choices)
    
    # Text being analyzed
    original_text = models.TextField()
    
    # FIXED: Replaced ArrayField with JSONField for SQLite compatibility
    issues_found = models.JSONField(
        blank=True,
        default=list
    )
    
    suggestions = models.TextField()
    corrected_text = models.TextField(blank=True)
    
    # Scores
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        null=True,
        blank=True
    )
    
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.8
    )
    
    # Metadata
    word_count = models.PositiveIntegerField()
    reading_time = models.PositiveIntegerField(help_text="Estimated reading time in minutes")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Writing Feedback"
        verbose_name_plural = "Writing Feedback"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'feedback_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_feedback_type_display()} Feedback - {self.user}"


class UserAILimits(models.Model):
    """
    Track AI tool usage limits per user
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_limits'
    )
    
    # Daily usage counts
    outline_helper_used_today = models.PositiveIntegerField(default=0)
    grammar_checker_used_today = models.PositiveIntegerField(default=0)
    citation_formatter_used_today = models.PositiveIntegerField(default=0)
    paraphrasing_tool_used_today = models.PositiveIntegerField(default=0)
    thesis_generator_used_today = models.PositiveIntegerField(default=0)
    
    # Date tracking
    last_reset_date = models.DateField(auto_now_add=True)
    
    # Total usage
    total_uses = models.PositiveIntegerField(default=0)
    
    # Flags
    is_restricted = models.BooleanField(
        default=False,
        help_text="User is restricted from using AI tools"
    )
    
    restriction_reason = models.TextField(blank=True)
    restricted_until = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User AI Limits"
        verbose_name_plural = "User AI Limits"
    
    def __str__(self):
        return f"AI Limits - {self.user}"
    
    def reset_daily_counts(self):
        """Reset daily usage counts if it's a new day"""
        today = timezone.now().date()
        
        if self.last_reset_date < today:
            self.outline_helper_used_today = 0
            self.grammar_checker_used_today = 0
            self.citation_formatter_used_today = 0
            self.paraphrasing_tool_used_today = 0
            self.thesis_generator_used_today = 0
            self.last_reset_date = today
            self.save()
    
    def can_use_tool(self, tool_type):
        """Check if user can use a specific tool"""
        from .services.limit_service import AILimitService
        return AILimitService.can_user_use_tool(self.user, tool_type)
    
    def increment_usage(self, tool_type):
        """Increment usage for a specific tool"""
        field_map = {
            'outline_helper': 'outline_helper_used_today',
            'grammar_checker': 'grammar_checker_used_today',
            'citation_formatter': 'citation_formatter_used_today',
            'paraphrasing_tool': 'paraphrasing_tool_used_today',
            'thesis_generator': 'thesis_generator_used_today',
        }
        
        if tool_type in field_map:
            setattr(self, field_map[tool_type], getattr(self, field_map[tool_type]) + 1)
            self.total_uses += 1
            self.save()


class GrammarCheckRequest(models.Model):
    """
    Model for grammar check requests
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='grammar_check_requests'
    )
    
    input_text = models.TextField()
    language = models.CharField(max_length=10, default='en')
    suggestions = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Grammar Check - {self.user} - {self.created_at}"


class CitationRequest(models.Model):
    """
    Model for citation formatting requests
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='citation_requests'
    )
    
    citation_style = models.CharField(max_length=50)
    source_data = models.JSONField()
    formatted_citation = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Citation - {self.user} - {self.created_at}"


class OutlineRequest(models.Model):
    """
    Model for outline generation requests
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='outline_requests'
    )
    
    topic = models.CharField(max_length=255)
    outline_type = models.CharField(max_length=50)
    generated_outline = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Outline - {self.user} - {self.created_at}"