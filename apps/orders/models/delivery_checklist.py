from django.db import models
from django.utils.translation import gettext_lazy as _


class DeliveryChecklist(models.Model):
    """Checklist for order delivery quality assurance."""
    
    order = models.OneToOneField(
        'Order',
        on_delete=models.CASCADE,
        related_name='delivery_checklist',
        verbose_name=_('order')
    )
    
    # Formatting & Structure
    formatting_correct = models.BooleanField(
        _('formatting correct'),
        default=False,
        help_text=_('Document follows specified formatting style')
    )
    
    structure_proper = models.BooleanField(
        _('structure proper'),
        default=False,
        help_text=_('Document has proper structure (introduction, body, conclusion)')
    )
    
    page_count_met = models.BooleanField(
        _('page count met'),
        default=False,
        help_text=_('Document meets required page count')
    )
    
    word_count_met = models.BooleanField(
        _('word count met'),
        default=False,
        help_text=_('Document meets required word count')
    )
    
    # Content Quality
    instructions_followed = models.BooleanField(
        _('instructions followed'),
        default=False,
        help_text=_('All client instructions have been followed')
    )
    
    topic_adherence = models.BooleanField(
        _('topic adherence'),
        default=False,
        help_text=_('Document stays on topic and addresses all requirements')
    )
    
    argument_coherence = models.BooleanField(
        _('argument coherence'),
        default=False,
        help_text=_('Arguments are coherent and logically presented')
    )
    
    # Academic Standards
    sources_cited = models.BooleanField(
        _('sources cited'),
        default=False,
        help_text=_('Required number of sources are cited')
    )
    
    citation_proper = models.BooleanField(
        _('citation proper'),
        default=False,
        help_text=_('Citations follow specified style correctly')
    )
    
    plagiarism_free = models.BooleanField(
        _('plagiarism free'),
        default=False,
        help_text=_('Document has been checked for plagiarism')
    )
    
    # Language & Grammar
    grammar_correct = models.BooleanField(
        _('grammar correct'),
        default=False,
        help_text=_('Grammar and spelling are correct')
    )
    
    language_appropriate = models.BooleanField(
        _('language appropriate'),
        default=False,
        help_text=_('Language is appropriate for academic level')
    )
    
    # Additional Files
    additional_files = models.BooleanField(
        _('additional files included'),
        default=False,
        help_text=_('All required additional files are included')
    )
    
    # Review & Approval
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_checklists',
        verbose_name=_('reviewed by')
    )
    
    review_notes = models.TextField(
        _('review notes'),
        blank=True,
        help_text=_('Additional notes from quality review')
    )
    
    passed_quality_check = models.BooleanField(
        _('passed quality check'),
        default=False,
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('delivery checklist')
        verbose_name_plural = _('delivery checklists')
    
    def __str__(self):
        return f'Checklist for Order #{self.order.order_number}'
    
    @property
    def completion_percentage(self):
        """Calculate checklist completion percentage."""
        fields = [
            'formatting_correct', 'structure_proper', 'page_count_met',
            'word_count_met', 'instructions_followed', 'topic_adherence',
            'argument_coherence', 'sources_cited', 'citation_proper',
            'plagiarism_free', 'grammar_correct', 'language_appropriate',
            'additional_files',
        ]
        
        total = len(fields)
        completed = sum(1 for field in fields if getattr(self, field))
        
        return (completed / total) * 100 if total > 0 else 0
    
    @property
    def is_complete(self):
        """Check if all checklist items are complete."""
        return self.completion_percentage == 100
    
    @property
    def critical_items_missing(self):
        """Get list of critical items that are missing."""
        critical_fields = [
            ('instructions_followed', 'Instructions followed'),
            ('plagiarism_free', 'Plagiarism free'),
            ('grammar_correct', 'Grammar correct'),
        ]
        
        missing = []
        for field, display_name in critical_fields:
            if not getattr(self, field):
                missing.append(display_name)
        
        return missing
    
    def reset(self):
        """Reset all checklist items to False."""
        fields = [
            'formatting_correct', 'structure_proper', 'page_count_met',
            'word_count_met', 'instructions_followed', 'topic_adherence',
            'argument_coherence', 'sources_cited', 'citation_proper',
            'plagiarism_free', 'grammar_correct', 'language_appropriate',
            'additional_files', 'passed_quality_check'
        ]
        
        for field in fields:
            setattr(self, field, False)
        
        self.reviewed_by = None
        self.review_notes = ''
        self.save()