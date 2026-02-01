"""
Outline Helper Service
Generates structured outlines for academic papers
⚠️ This is an ASSISTIVE tool only - not a full paper generator
"""
import re
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import json

from ..models import AIToolUsageLog, AIToolTemplate, AIToolConfiguration


class OutlineHelperService:
    """Service for generating academic paper outlines"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    def generate_outline(
        self,
        topic: str,
        template_type: str = 'essay',
        academic_level: str = 'undergraduate',
        word_count_target: int = 1500,
        user=None,
        session_id: str = ''
    ) -> Dict:
        """
        Generate an outline for an academic paper
        
        Args:
            topic: The topic of the paper
            template_type: Type of paper (essay, research_paper, etc.)
            academic_level: Academic level (high_school, undergraduate, etc.)
            word_count_target: Target word count
            user: User requesting the outline
            session_id: Session ID for tracking
        
        Returns:
            Dictionary containing outline and metadata
        """
        # Get template
        template = self._get_template(template_type, academic_level)
        
        # Generate outline structure
        outline = self._generate_outline_structure(topic, template, word_count_target)
        
        # Add guidance
        guidance = self._generate_guidance(topic, template, academic_level, word_count_target)
        
        # Log usage
        if user and user.is_authenticated:
            self._log_usage(
                user=user,
                tool_type='outline_helper',
                input_text=topic,
                output_text=json.dumps(outline, indent=2),
                parameters={
                    'template_type': template_type,
                    'academic_level': academic_level,
                    'word_count_target': word_count_target,
                },
                session_id=session_id
            )
        
        return {
            'outline': outline,
            'guidance': guidance,
            'template_used': template.name,
            'disclaimer': self._get_disclaimer(),
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'word_count_target': word_count_target,
                'estimated_sections': len(outline.get('sections', [])),
            }
        }
    
    def _get_template(self, template_type: str, academic_level: str) -> AIToolTemplate:
        """Get the appropriate template"""
        cache_key = f"ai_outline_template_{template_type}_{academic_level}"
        
        template = cache.get(cache_key)
        if not template:
            try:
                template = AIToolTemplate.objects.get(
                    template_type=template_type,
                    academic_level=academic_level,
                    is_active=True
                )
                cache.set(cache_key, template, self.cache_timeout)
            except AIToolTemplate.DoesNotExist:
                # Fallback to default template
                template = AIToolTemplate.objects.filter(
                    template_type=template_type,
                    is_active=True
                ).first()
                
                if not template:
                    # Create a basic template if none exists
                    template = self._create_default_template(template_type, academic_level)
        
        return template
    
    def _generate_outline_structure(
        self,
        topic: str,
        template: AIToolTemplate,
        word_count_target: int
    ) -> Dict:
        """Generate the outline structure"""
        
        # Calculate section word counts
        section_word_counts = self._calculate_section_word_counts(
            template.sections,
            word_count_target
        )
        
        # Generate section details
        sections = []
        for i, section_name in enumerate(template.sections):
            section = {
                'section_number': i + 1,
                'title': section_name,
                'suggested_word_count': section_word_counts.get(section_name, 0),
                'guidance': self._get_section_guidance(section_name, template.template_type),
                'key_points': self._generate_key_points(topic, section_name),
                'suggested_structure': self._get_section_structure(section_name),
            }
            
            # Add specific elements for certain sections
            if section_name.lower() == 'introduction':
                section['thesis_statement'] = self._generate_thesis_statement_prompt(topic)
                section['hook_suggestions'] = self._generate_hook_suggestions(topic)
            
            elif section_name.lower() == 'conclusion':
                section['restatement_prompt'] = f"Restate your thesis about {topic} in new words"
                section['implications'] = self._generate_implications_prompt(topic)
            
            sections.append(section)
        
        return {
            'topic': topic,
            'template_type': template.template_type,
            'academic_level': template.academic_level,
            'total_target_words': word_count_target,
            'sections': sections,
            'timeline_suggestions': self._generate_timeline_suggestions(len(sections)),
        }
    
    def _generate_guidance(
        self,
        topic: str,
        template: AIToolTemplate,
        academic_level: str,
        word_count_target: int
    ) -> Dict:
        """Generate guidance for writing the paper"""
        
        return {
            'general_guidelines': template.guidelines,
            'common_mistakes': template.common_mistakes,
            'research_suggestions': self._generate_research_suggestions(topic),
            'writing_tips': self._get_writing_tips(academic_level),
            'citation_advice': self._get_citation_advice(template.template_type),
            'plagiarism_warnings': self._get_plagiarism_warnings(),
            'time_management': self._get_time_management_tips(word_count_target),
        }
    
    def _calculate_section_word_counts(
        self,
        sections: List[str],
        total_words: int
    ) -> Dict[str, int]:
        """Calculate suggested word counts for each section"""
        
        # Default distribution for common section types
        distribution = {
            'introduction': 0.15,  # 15%
            'literature_review': 0.25,  # 25%
            'methodology': 0.20,  # 20%
            'analysis': 0.25,  # 25%
            'conclusion': 0.10,  # 10%
            'abstract': 0.05,  # 5%
        }
        
        # Default for sections not in distribution
        default_ratio = 0.15
        
        section_counts = {}
        remaining_sections = []
        
        # Assign known sections
        for section in sections:
            section_lower = section.lower().replace(' ', '_')
            
            if section_lower in distribution:
                section_counts[section] = int(total_words * distribution[section_lower])
            else:
                remaining_sections.append(section)
        
        # Distribute remaining words among other sections
        assigned_words = sum(section_counts.values())
        remaining_words = total_words - assigned_words
        
        if remaining_sections and remaining_words > 0:
            words_per_section = remaining_words // len(remaining_sections)
            for section in remaining_sections:
                section_counts[section] = words_per_section
        
        return section_counts
    
    def _get_section_guidance(self, section_name: str, template_type: str) -> str:
        """Get guidance for a specific section"""
        
        guidance_map = {
            'introduction': (
                "Start with a hook to engage the reader. "
                "Provide background context. "
                "Clearly state your thesis/research question. "
                "Outline the structure of your paper."
            ),
            'literature_review': (
                "Summarize existing research. "
                "Identify gaps in the literature. "
                "Show how your work builds on previous studies. "
                "Critically analyze sources, don't just list them."
            ),
            'methodology': (
                "Describe your research design clearly. "
                "Explain participant selection (if applicable). "
                "Detail data collection methods. "
                "Discuss validity and reliability measures."
            ),
            'analysis': (
                "Present your findings clearly. "
                "Use appropriate data visualization. "
                "Interpret results in context. "
                "Address unexpected findings."
            ),
            'conclusion': (
                "Restate your main findings. "
                "Discuss implications of your research. "
                "Acknowledge limitations. "
                "Suggest directions for future research."
            ),
        }
        
        section_lower = section_name.lower()
        for key, guidance in guidance_map.items():
            if key in section_lower:
                return guidance
        
        return f"Develop this section to support your overall argument about the topic."
    
    def _generate_key_points(self, topic: str, section_name: str) -> List[str]:
        """Generate key points for a section"""
        
        # This would typically use AI, but for now we'll provide generic prompts
        prompts = [
            f"How does this relate to {topic}?",
            "What evidence supports your points?",
            "Are there counterarguments to consider?",
            "How does this connect to other sections?",
            "What is the significance of this point?",
        ]
        
        return prompts[:3]  # Return first 3 prompts
    
    def _get_section_structure(self, section_name: str) -> List[str]:
        """Get suggested structure for a section"""
        
        structures = {
            'introduction': [
                "Hook/Opening Statement",
                "Background/Context",
                "Thesis Statement",
                "Roadmap of Paper"
            ],
            'body': [
                "Topic Sentence",
                "Evidence/Examples",
                "Analysis/Explanation",
                "Transition to Next Point"
            ],
            'conclusion': [
                "Restate Thesis",
                "Summarize Main Points",
                "Discuss Implications",
                "Final Thought/Call to Action"
            ],
        }
        
        section_lower = section_name.lower()
        if 'intro' in section_lower:
            return structures['introduction']
        elif 'conclu' in section_lower:
            return structures['conclusion']
        else:
            return structures['body']
    
    def _generate_thesis_statement_prompt(self, topic: str) -> str:
        """Generate a prompt for creating a thesis statement"""
        
        prompts = [
            f"Develop a clear, arguable thesis about {topic}",
            f"What is your main argument regarding {topic}?",
            f"Formulate a specific claim about {topic} that you will support with evidence",
            f"Create a thesis that addresses both what and why about {topic}",
        ]
        
        return prompts[0]
    
    def _generate_hook_suggestions(self, topic: str) -> List[str]:
        """Generate suggestions for essay hooks"""
        
        return [
            f"Start with a surprising statistic about {topic}",
            f"Begin with a relevant quote about {topic}",
            f"Open with a thought-provoking question about {topic}",
            f"Start with a brief anecdote related to {topic}",
            f"Begin with a common misconception about {topic}",
        ]
    
    def _generate_implications_prompt(self, topic: str) -> str:
        """Generate prompt for discussing implications"""
        
        return (
            f"Discuss the broader implications of your findings about {topic}. "
            f"Consider practical applications, theoretical contributions, "
            f"and directions for future research."
        )
    
    def _generate_research_suggestions(self, topic: str) -> List[str]:
        """Generate research suggestions for the topic"""
        
        return [
            f"Search academic databases for recent studies on {topic}",
            f"Look for literature reviews about {topic} to understand the field",
            f"Check government or organization reports about {topic}",
            f"Find statistical data related to {topic} from reliable sources",
            f"Look for opposing viewpoints on {topic} to strengthen your argument",
        ]
    
    def _get_writing_tips(self, academic_level: str) -> List[str]:
        """Get writing tips for the academic level"""
        
        tips = {
            'high_school': [
                "Use clear, straightforward language",
                "Define any technical terms you use",
                "Support each point with evidence",
                "Use transition words between paragraphs",
                "Proofread for spelling and grammar errors",
            ],
            'undergraduate': [
                "Demonstrate critical thinking in your analysis",
                "Use academic sources to support your arguments",
                "Follow proper citation guidelines",
                "Address counterarguments",
                "Maintain formal academic tone",
            ],
            'graduate': [
                "Engage deeply with theoretical frameworks",
                "Demonstrate original contribution to the field",
                "Use specialized terminology appropriately",
                "Provide extensive literature review",
                "Discuss methodological rigor",
            ],
        }
        
        return tips.get(academic_level, tips['undergraduate'])
    
    def _get_citation_advice(self, template_type: str) -> str:
        """Get citation advice based on paper type"""
        
        advice = {
            'essay': "Use in-text citations for quotes and paraphrases. Include a Works Cited or References page.",
            'research_paper': "Use a consistent citation style (APA, MLA, Chicago). Cite all sources, including data and statistics.",
            'literature_review': "Cite extensively to show breadth of reading. Use citation managers to organize sources.",
            'lab_report': "Cite methods and protocols. Reference previous studies that used similar methodologies.",
        }
        
        return advice.get(template_type, "Use appropriate citations for all sources you reference.")
    
    def _get_plagiarism_warnings(self) -> List[str]:
        """Get plagiarism warnings"""
        
        return [
            "Always cite your sources properly",
            "Use quotation marks for direct quotes",
            "Paraphrase in your own words and still cite",
            "Don't copy from other students' work",
            "Use plagiarism detection tools before submission",
        ]
    
    def _get_time_management_tips(self, word_count: int) -> List[str]:
        """Get time management tips based on word count"""
        
        # Estimate hours needed (assuming 250 words/hour for drafting)
        estimated_hours = word_count / 250
        
        return [
            f"Allocate approximately {estimated_hours:.1f} hours for drafting",
            "Schedule time for research and reading",
            "Leave time for multiple revisions",
            "Get feedback from peers or instructors",
            "Proofread carefully before submission",
        ]
    
    def _generate_timeline_suggestions(self, num_sections: int) -> Dict:
        """Generate timeline suggestions for completing the paper"""
        
        days_per_section = 2  # Average days per section
        total_days = num_sections * days_per_section
        
        return {
            'research_phase': f"Days 1-{int(total_days * 0.3)}",
            'outlining_phase': f"Days {int(total_days * 0.3) + 1}-{int(total_days * 0.4)}",
            'drafting_phase': f"Days {int(total_days * 0.4) + 1}-{int(total_days * 0.8)}",
            'revision_phase': f"Days {int(total_days * 0.8) + 1}-{total_days}",
            'total_estimated_days': total_days,
        }
    
    def _create_default_template(
        self,
        template_type: str,
        academic_level: str
    ) -> AIToolTemplate:
        """Create a default template if none exists"""
        
        default_templates = {
            'essay': {
                'name': 'Standard Essay Template',
                'sections': ['Introduction', 'Body Paragraph 1', 'Body Paragraph 2', 
                           'Body Paragraph 3', 'Conclusion'],
                'guidelines': 'Develop a clear argument with evidence in each paragraph.',
            },
            'research_paper': {
                'name': 'Research Paper Template',
                'sections': ['Abstract', 'Introduction', 'Literature Review', 
                           'Methodology', 'Results', 'Discussion', 'Conclusion'],
                'guidelines': 'Follow the IMRaD structure with clear methodology and analysis.',
            },
        }
        
        default = default_templates.get(
            template_type,
            default_templates['essay']
        )
        
        template = AIToolTemplate.objects.create(
            name=default['name'],
            template_type=template_type,
            academic_level=academic_level,
            sections=default['sections'],
            guidelines=default['guidelines'],
            is_active=True,
        )
        
        return template
    
    def _get_disclaimer(self) -> str:
        """Get disclaimer for AI-generated content"""
        
        return (
            "⚠️ IMPORTANT: This outline is AI-assisted and should be used as a starting point only. "
            "You must:\n"
            "1. Conduct your own research\n"
            "2. Develop original arguments\n"
            "3. Write all content yourself\n"
            "4. Properly cite all sources\n"
            "5. Review with your instructor if required\n"
            "This tool is for assistance only - it does not write your paper for you."
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