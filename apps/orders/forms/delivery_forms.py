from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator

class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget to allow multiple file selection in ClearableFileInput."""
    allow_multiple_selected = True

class DeliveryForm(forms.Form):
    """Form for delivering completed work."""
    
    files = forms.FileField(
        label=_('Completed work files'),
        # Use our custom widget here to fix the ValueError
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': '.pdf,.doc,.docx,.zip,.rar',
        }),
        required=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'zip', 'rar']
            )
        ],
        help_text=_(
            'Upload your completed work. '
            'You can upload multiple files. '
            'Maximum file size: 20MB per file.'
        ),
    )
    
    notes = forms.CharField(
        label=_('Delivery notes (optional)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any notes for the client about your delivery...',
        }),
        required=False,
        max_length=1000,
        help_text=_('Optional notes to accompany your delivery'),
    )
    
    checklist = forms.JSONField(
        label=_('Quality checklist'),
        required=False,
        widget=forms.HiddenInput(),  # Will be handled by JavaScript
        help_text=_('Internal quality assurance checklist'),
    )
    
    confirm_completion = forms.BooleanField(
        label=_('I confirm this work is complete and ready for client review'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm completion before delivering.')
        },
    )
    
    confirm_originality = forms.BooleanField(
        label=_('I confirm this work is original and plagiarism-free'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm the work is original.')
        },
    )
    
    confirm_instructions = forms.BooleanField(
        label=_('I confirm I have followed all client instructions'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm you followed all instructions.')
        },
    )
    
    def clean_files(self):
        """Validate uploaded files."""
        # Note: When multiple=True, you must use .getlist() 
        # but in Django Forms, files are usually passed as a list 
        # if the widget supports it.
        files = self.files.getlist('files') if hasattr(self.files, 'getlist') else self.cleaned_data.get('files')
        
        # Handle cases where it might return a single file or list
        if not isinstance(files, list):
            files = [files] if files else []

        if not files:
            raise forms.ValidationError(_('At least one file is required.'))
        
        # Check total file size (max 100MB for all files)
        max_total_size = 100 * 1024 * 1024  # 100MB
        total_size = sum(f.size for f in files)
        
        if total_size > max_total_size:
            raise forms.ValidationError(
                _('Total file size exceeds 100MB limit.')
            )
        
        # Check individual file sizes (max 20MB per file)
        max_file_size = 20 * 1024 * 1024  # 20MB
        for file in files:
            if file.size > max_file_size:
                raise forms.ValidationError(
                    _('File "%(filename)s" exceeds 20MB limit.') % 
                    {'filename': file.name}
                )
        
        return files

# ... rest of the file (RevisionResponseForm and DeliveryChecklistForm) remains the same


class RevisionResponseForm(forms.Form):
    """Form for responding to revision requests."""
    
    response = forms.ChoiceField(
        label=_('Your response'),
        choices=[
            ('accept', 'Accept Revision Request'),
            ('clarify', 'Request Clarification'),
            ('dispute', 'Dispute Revision Request'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text=_('Choose how you want to respond to this revision request'),
    )
    
    notes = forms.CharField(
        label=_('Response notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Add your response notes here...',
        }),
        required=False,
        max_length=2000,
        help_text=_('Explain your response to the client'),
    )
    
    clarification_questions = forms.CharField(
        label=_('Clarification questions (if requesting clarification)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'What specific clarification do you need from the client?',
        }),
        required=False,
        max_length=1000,
    )
    
    dispute_reason = forms.CharField(
        label=_('Dispute reason (if disputing the request)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explain why you believe this revision request is unreasonable...',
        }),
        required=False,
        max_length=1000,
    )
    
    estimated_completion = forms.DateTimeField(
        label=_('Estimated completion time (if accepting)'),
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        required=False,
        help_text=_('When you expect to complete the revisions'),
    )
    
    def clean(self):
        """Validate revision response."""
        cleaned_data = super().clean()
        response = cleaned_data.get('response')
        
        if response == 'clarify' and not cleaned_data.get('clarification_questions'):
            raise forms.ValidationError({
                'clarification_questions': _('Clarification questions are required when requesting clarification.')
            })
        
        if response == 'dispute' and not cleaned_data.get('dispute_reason'):
            raise forms.ValidationError({
                'dispute_reason': _('Dispute reason is required when disputing a revision request.')
            })
        
        if response == 'accept' and not cleaned_data.get('estimated_completion'):
            raise forms.ValidationError({
                'estimated_completion': _('Estimated completion time is required when accepting a revision request.')
            })
        
        return cleaned_data


class DeliveryChecklistForm(forms.Form):
    """Form for delivery checklist."""
    
    formatting_correct = forms.BooleanField(
        label=_('Formatting follows specified style'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    structure_proper = forms.BooleanField(
        label=_('Document has proper structure'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    page_count_met = forms.BooleanField(
        label=_('Page count requirement met'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    word_count_met = forms.BooleanField(
        label=_('Word count requirement met'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    instructions_followed = forms.BooleanField(
        label=_('All client instructions followed'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    topic_adherence = forms.BooleanField(
        label=_('Document stays on topic'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    argument_coherence = forms.BooleanField(
        label=_('Arguments are coherent'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    sources_cited = forms.BooleanField(
        label=_('Required sources are cited'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    citation_proper = forms.BooleanField(
        label=_('Citations follow specified style'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    plagiarism_free = forms.BooleanField(
        label=_('Document is plagiarism-free'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    grammar_correct = forms.BooleanField(
        label=_('Grammar and spelling are correct'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    language_appropriate = forms.BooleanField(
        label=_('Language is appropriate for academic level'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    additional_files = forms.BooleanField(
        label=_('All required additional files included'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    
    review_notes = forms.CharField(
        label=_('Additional review notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any additional notes about the delivery...',
        }),
        required=False,
        max_length=1000,
    )
    
    def clean(self):
        """Validate checklist - require all critical items for final submission."""
        cleaned_data = super().clean()
        
        # Critical items that must be checked for final delivery
        critical_items = [
            'instructions_followed',
            'plagiarism_free',
            'grammar_correct',
        ]
        
        for item in critical_items:
            if not cleaned_data.get(item):
                self.add_error(
                    item,
                    _('This is a critical requirement that must be met.')
                )
        
        return cleaned_data