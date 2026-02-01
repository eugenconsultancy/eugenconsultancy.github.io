"""
Grammar Checker Service
Provides grammar, style, and clarity suggestions
⚠️ This is an ASSISTIVE tool only - human review is essential
"""
import re
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import json
import language_tool_python

from ..models import AIToolUsageLog, WritingFeedback, AIToolConfiguration


class GrammarCheckerService:
    """Service for checking grammar and writing style"""
    
    def __init__(self):
        self.tool = language_tool_python.LanguageTool('en-US')
        self.cache_timeout = 1800  # 30 minutes
        
        # Custom rules for academic writing
        self.academic_rules = [
            {
                'name': 'passive_voice',
                'pattern': r'\b(am|is|are|was|were|be|being|been)\s+\w+ed\b',
                'message': 'Consider using active voice for stronger writing',
                'suggestion': 'Rewrite sentence with subject performing the action'
            },
            {
                'name': 'contractions',
                'pattern': r"\b(can't|don't|won't|isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|shouldn't|couldn't|wouldn't)\b",
                'message': 'Avoid contractions in formal academic writing',
                'suggestion': 'Use full forms (cannot, do not, will not, etc.)'
            },
            {
                'name': 'informal_phrases',
                'pattern': r'\b(a lot of|got to|gonna|wanna|kind of|sort of|pretty much)\b',
                'message': 'Use more formal academic language',
                'suggestion': 'Replace with formal equivalents (many, must, going to, want to, somewhat, approximately)'
            },
            {
                'name': 'first_person_informal',
                'pattern': r'\b(I think|I believe|I feel|in my opinion)\b',
                'message': 'Consider removing first-person statements for more objective tone',
                'suggestion': 'Present arguments as facts supported by evidence'
            },
        ]
    
    def check_text(
        self,
        text: str,
        check_type: str = 'grammar',
        academic_level: str = 'undergraduate',
        user=None,
        session_id: str = ''
    ) -> Dict:
        """
        Check text for grammar, style, and clarity issues
        
        Args:
            text: The text to check
            check_type: Type of check (grammar, style, clarity, all)
            academic_level: Academic level for style suggestions
            user: User requesting the check
            session_id: Session ID for tracking
        
        Returns:
            Dictionary containing issues and suggestions
        """
        if not text or len(text.strip()) < 10:
            return {
                'error': 'Text must be at least 10 characters',
                'disclaimer': self._get_disclaimer(),
            }
        
        # Limit text length
        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length]
        
        # Perform checks
        results = {
            'grammar_issues': [],
            'style_issues': [],
            'clarity_issues': [],
            'overall_score': 0,
            'word_count': len(text.split()),
            'reading_level': '',
            'suggestions': [],
            'corrected_text': text,
        }
        
        if check_type in ['grammar', 'all']:
            grammar_results = self._check_grammar(text)
            results['grammar_issues'] = grammar_results['issues']
            results['corrected_text'] = grammar_results['corrected_text']
            results['overall_score'] += grammar_results['score'] * 0.4
        
        if check_type in ['style', 'all']:
            style_results = self._check_style(text, academic_level)
            results['style_issues'] = style_results['issues']
            results['overall_score'] += style_results['score'] * 0.3
        
        if check_type in ['clarity', 'all']:
            clarity_results = self._check_clarity(text)
            results['clarity_issues'] = clarity_results['issues']
            results['reading_level'] = clarity_results['reading_level']
            results['overall_score'] += clarity_results['score'] * 0.3
        
        # Calculate overall score (0-10)
        results['overall_score'] = min(10, max(0, results['overall_score']))
        
        # Generate overall suggestions
        results['suggestions'] = self._generate_suggestions(results)
        
        # Log usage
        if user and user.is_authenticated:
            self._log_usage(
                user=user,
                tool_type='grammar_checker',
                input_text=text,
                output_text=json.dumps(results, indent=2),
                parameters={
                    'check_type': check_type,
                    'academic_level': academic_level,
                },
                session_id=session_id
            )
            
            # Save feedback if user wants to track improvements
            if check_type == 'all':
                self._save_feedback(
                    user=user,
                    text=text,
                    results=results,
                    feedback_type='grammar'
                )
        
        results['disclaimer'] = self._get_disclaimer()
        results['metadata'] = {
            'generated_at': timezone.now().isoformat(),
            'check_type': check_type,
            'academic_level': academic_level,
        }
        
        return results
    
    def _check_grammar(self, text: str) -> Dict:
        """Check for grammar and spelling errors"""
        
        # Use LanguageTool for grammar checking
        matches = self.tool.check(text)
        
        issues = []
        corrected_text = text
        
        for match in matches[:20]:  # Limit to 20 issues
            issue = {
                'type': match.ruleId,
                'message': match.message,
                'suggestion': match.replacements[0] if match.replacements else '',
                'context': match.context,
                'offset': match.offset,
                'length': match.errorLength,
                'category': match.category,
            }
            issues.append(issue)
        
        # Apply corrections
        corrected_text = self.tool.correct(text)
        
        # Calculate score (higher is better)
        score = 10
        if len(text.split()) > 0:
            error_density = len(issues) / len(text.split())
            score = max(0, 10 - (error_density * 20))
        
        return {
            'issues': issues,
            'corrected_text': corrected_text,
            'score': score,
        }
    
    def _check_style(self, text: str, academic_level: str) -> Dict:
        """Check for academic writing style issues"""
        
        issues = []
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        for rule in self.academic_rules:
            matches = re.finditer(rule['pattern'], text, re.IGNORECASE)
            for match in matches:
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end]
                
                issue = {
                    'type': rule['name'],
                    'message': rule['message'],
                    'suggestion': rule['suggestion'],
                    'context': f"...{context}...",
                    'matched_text': match.group(),
                }
                issues.append(issue)
        
        # Check sentence length
        long_sentences = []
        for i, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            if word_count > 30:  # Long sentence threshold
                long_sentences.append({
                    'sentence_index': i + 1,
                    'word_count': word_count,
                    'suggestion': 'Consider breaking into shorter sentences for clarity'
                })
        
        if long_sentences:
            issues.append({
                'type': 'sentence_length',
                'message': f'Found {len(long_sentences)} very long sentences',
                'suggestion': 'Aim for sentences under 30 words for better readability',
                'details': long_sentences,
            })
        
        # Check paragraph length (approximate)
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        long_paragraphs = []
        
        for i, paragraph in enumerate(paragraphs):
            word_count = len(paragraph.split())
            if word_count > 200:  # Long paragraph threshold
                long_paragraphs.append({
                    'paragraph_index': i + 1,
                    'word_count': word_count,
                    'suggestion': 'Consider breaking into shorter paragraphs'
                })
        
        if long_paragraphs:
            issues.append({
                'type': 'paragraph_length',
                'message': f'Found {len(long_paragraphs)} very long paragraphs',
                'suggestion': 'Aim for paragraphs under 200 words for better readability',
                'details': long_paragraphs,
            })
        
        # Check transition words
        transition_words = [
            'however', 'therefore', 'moreover', 'furthermore', 'consequently',
            'nevertheless', 'nonetheless', 'in addition', 'on the other hand'
        ]
        
        found_transitions = []
        for word in transition_words:
            if word in text.lower():
                found_transitions.append(word)
        
        if not found_transitions and len(sentences) > 5:
            issues.append({
                'type': 'transitions',
                'message': 'Few transition words found',
                'suggestion': 'Use transition words to improve flow between ideas',
                'examples': transition_words[:5],
            })
        
        # Calculate style score (higher is better)
        score = 10
        if len(sentences) > 0:
            issues_per_sentence = len(issues) / len(sentences)
            score = max(0, 10 - (issues_per_sentence * 5))
        
        return {
            'issues': issues,
            'score': score,
        }
    
    def _check_clarity(self, text: str) -> Dict:
        """Check for clarity and readability issues"""
        
        issues = []
        
        # Calculate readability scores
        flesch_score = self._calculate_flesch_score(text)
        
        # Determine reading level
        reading_level = self._get_reading_level(flesch_score)
        
        # Check for jargon/complex terms
        complex_terms = self._find_complex_terms(text)
        if complex_terms:
            issues.append({
                'type': 'complex_terms',
                'message': f'Found {len(complex_terms)} potentially complex terms',
                'suggestion': 'Define technical terms or use simpler alternatives',
                'terms': complex_terms,
            })
        
        # Check for nominalizations
        nominalizations = self._find_nominalizations(text)
        if nominalizations:
            issues.append({
                'type': 'nominalizations',
                'message': 'Consider using verb forms for stronger writing',
                'suggestion': 'Replace nouns derived from verbs with the verb forms',
                'examples': nominalizations[:5],
            })
        
        # Check for vague language
        vague_words = ['thing', 'stuff', 'aspect', 'factor', 'element']
        found_vague = []
        
        for word in vague_words:
            if re.search(rf'\b{word}s?\b', text, re.IGNORECASE):
                found_vague.append(word)
        
        if found_vague:
            issues.append({
                'type': 'vague_language',
                'message': 'Consider using more specific terms',
                'suggestion': 'Replace vague words with precise descriptions',
                'words': found_vague,
            })
        
        # Check for redundant phrases
        redundant_phrases = [
            (r'\babsolutely\s+essential\b', 'essential'),
            (r'\badvance\s+planning\b', 'planning'),
            (r'\bbasic\s+fundamentals\b', 'fundamentals'),
            (r'\bend\s+result\b', 'result'),
            (r'\bfuture\s+plans\b', 'plans'),
        ]
        
        found_redundant = []
        for pattern, replacement in redundant_phrases:
            if re.search(pattern, text, re.IGNORECASE):
                found_redundant.append({
                    'phrase': pattern.replace(r'\b', '').replace(r'\s+', ' '),
                    'suggestion': replacement,
                })
        
        if found_redundant:
            issues.append({
                'type': 'redundancy',
                'message': 'Found redundant phrases',
                'suggestion': 'Remove unnecessary words',
                'phrases': found_redundant,
            })
        
        # Calculate clarity score
        score = flesch_score / 10  # Convert to 0-10 scale
        
        return {
            'issues': issues,
            'reading_level': reading_level,
            'score': min(10, score),
        }
    
    def _calculate_flesch_score(self, text: str) -> float:
        """Calculate Flesch Reading Ease score"""
        import re
        
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0
        
        words = text.split()
        syllables = sum(self._count_syllables(word) for word in words)
        
        if len(words) == 0 or len(sentences) == 0:
            return 0
        
        words_per_sentence = len(words) / len(sentences)
        syllables_per_word = syllables / len(words)
        
        # Flesch Reading Ease formula
        score = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
        
        return max(0, min(100, score))
    
    def _count_syllables(self, word: str) -> int:
        """Approximate syllable count"""
        word = word.lower()
        count = 0
        
        if word.endswith('e'):
            word = word[:-1]
        
        vowels = 'aeiouy'
        prev_char_was_vowel = False
        
        for char in word:
            if char in vowels:
                if not prev_char_was_vowel:
                    count += 1
                prev_char_was_vowel = True
            else:
                prev_char_was_vowel = False
        
        return max(1, count)
    
    def _get_reading_level(self, flesch_score: float) -> str:
        """Get reading level from Flesch score"""
        
        if flesch_score >= 90:
            return 'Very Easy (5th grade)'
        elif flesch_score >= 80:
            return 'Easy (6th grade)'
        elif flesch_score >= 70:
            return 'Fairly Easy (7th grade)'
        elif flesch_score >= 60:
            return 'Standard (8th-9th grade)'
        elif flesch_score >= 50:
            return 'Fairly Difficult (10th-12th grade)'
        elif flesch_score >= 30:
            return 'Difficult (College)'
        else:
            return 'Very Difficult (Graduate)'
    
    def _find_complex_terms(self, text: str) -> List[str]:
        """Find potentially complex terms"""
        
        # Common academic/complex terms
        complex_terms = [
            'paradigm', 'heuristic', 'epistemology', 'ontology', 'methodology',
            'theoretical', 'framework', 'discourse', 'narrative', 'phenomenon',
            'quantitative', 'qualitative', 'empirical', 'substantiate',
            'conceptualize', 'problematize', 'deconstruct', 'contextualize'
        ]
        
        found = []
        for term in complex_terms:
            if re.search(rf'\b{term}s?\b', text, re.IGNORECASE):
                found.append(term)
        
        return found
    
    def _find_nominalizations(self, text: str) -> List[str]:
        """Find nominalizations (nouns derived from verbs)"""
        
        patterns = [
            (r'\b(\w+tion)s?\b', ['tion']),
            (r'\b(\w+ment)s?\b', ['ment']),
            (r'\b(\w+ance)s?\b', ['ance']),
            (r'\b(\w+ence)s?\b', ['ence']),
            (r'\b(\w+ity)s?\b', ['ity']),
        ]
        
        nominalizations = []
        for pattern, suffixes in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                word = match.group(1)
                # Check if there's a verb form
                for suffix in suffixes:
                    if word.endswith(suffix):
                        stem = word[:-len(suffix)]
                        # Simple check for verb form
                        verb_forms = [stem, stem + 'e', stem[:-1] if stem.endswith('t') else stem]
                        nominalizations.append({
                            'nominalization': word,
                            'possible_verb': verb_forms[0] + 'ate' if stem.endswith('c') else verb_forms[0]
                        })
                        break
        
        return nominalizations[:10]  # Limit results
    
    def _generate_suggestions(self, results: Dict) -> List[str]:
        """Generate overall writing suggestions"""
        
        suggestions = []
        
        # Grammar suggestions
        if results['grammar_issues']:
            error_count = len(results['grammar_issues'])
            if error_count > 10:
                suggestions.append(f"Focus on fixing {error_count} grammar errors first")
            elif error_count > 0:
                suggestions.append(f"Review and correct {error_count} grammar issues")
        
        # Style suggestions
        if results['style_issues']:
            style_issue_count = len(results['style_issues'])
            if style_issue_count > 5:
                suggestions.append("Improve academic style by addressing informal language")
        
        # Clarity suggestions
        if results['clarity_issues']:
            clarity_issue_count = len(results['clarity_issues'])
            if clarity_issue_count > 3:
                suggestions.append("Enhance clarity by simplifying complex sentences")
        
        # Reading level suggestion
        reading_level = results.get('reading_level', '')
        if 'Difficult' in reading_level or 'College' in reading_level:
            suggestions.append("Consider simplifying language for better readability")
        
        # Score-based suggestions
        score = results.get('overall_score', 0)
        if score < 6:
            suggestions.append("Significant improvements needed in writing quality")
        elif score < 8:
            suggestions.append("Good foundation - focus on refining style and clarity")
        else:
            suggestions.append("Well-written - minor polishing would make it excellent")
        
        # Word count suggestion
        word_count = results.get('word_count', 0)
        if word_count < 200:
            suggestions.append("Consider developing your ideas more fully")
        elif word_count > 1000:
            suggestions.append("Ensure all content is relevant and concise")
        
        return suggestions
    
    def _save_feedback(
        self,
        user,
        text: str,
        results: Dict,
        feedback_type: str = 'grammar'
    ) -> None:
        """Save writing feedback for user tracking"""
        
        # Calculate reading time (assuming 200 words per minute)
        word_count = len(text.split())
        reading_time = max(1, word_count // 200)
        
        WritingFeedback.objects.create(
            user=user,
            feedback_type=feedback_type,
            original_text=text[:5000],  # Limit length
            issues_found=[issue.get('type', '') for issue in results.get('grammar_issues', [])[:10]],
            suggestions='\n'.join(results.get('suggestions', [])[:5]),
            corrected_text=results.get('corrected_text', '')[:5000],
            score=results.get('overall_score', 0),
            word_count=word_count,
            reading_time=reading_time,
        )
    
    def _get_disclaimer(self) -> str:
        """Get disclaimer for grammar checking"""
        
        return (
            "⚠️ IMPORTANT: This grammar check is AI-assisted and may have errors. "
            "You must:\n"
            "1. Review all suggestions carefully\n"
            "2. Consider context and meaning\n"
            "3. Make final decisions based on your writing goals\n"
            "4. Have a human review important documents\n"
            "This tool is for assistance only - it does not replace careful proofreading."
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