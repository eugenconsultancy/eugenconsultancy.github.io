# marks/analytics.py
from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from datetime import datetime
from .models import Mark, Student, Subject, PerformanceTrend

class StudentPerformanceAnalyzer:
    def __init__(self, student_id=None):
        self.student_id = student_id
    
    def get_student_term_performance(self, student, term, year):
        """Get student performance for specific term"""
        marks = Mark.objects.filter(
            student=student,
            term=term,
            academic_year=year
        ).select_related('subject')
        
        if not marks.exists():
            return None
        
        # Calculate statistics
        average_score = marks.aggregate(avg=Avg('total_score'))['avg']
        grade_distribution = marks.values('grade').annotate(count=Count('id')).order_by('grade')
        
        # Subject-wise performance
        subject_scores = {}
        for mark in marks:
            subject_scores[mark.subject.name] = {
                'score': float(mark.total_score),
                'grade': mark.grade,
                'grade_label': mark.get_performance_label()
            }
        
        return {
            'term': term,
            'year': year,
            'average_score': float(average_score),
            'total_subjects': marks.count(),
            'grade_distribution': list(grade_distribution),
            'subject_scores': subject_scores
        }
    
    def compare_term_performance(self, student, current_term_data, previous_term_data):
        """Compare performance between two terms"""
        if not current_term_data or not previous_term_data:
            return None
        
        current_avg = current_term_data['average_score']
        previous_avg = previous_term_data['average_score']
        
        # Calculate percentage change
        if previous_avg > 0:
            percentage_change = ((current_avg - previous_avg) / previous_avg) * 100
        else:
            percentage_change = 0
        
        # Determine trend
        if percentage_change > 5:
            trend = 'improving'
            trend_direction = 'positive'
        elif percentage_change < -5:
            trend = 'declining'
            trend_direction = 'negative'
        else:
            trend = 'stable'
            trend_direction = 'neutral'
        
        # Compare subject performance
        subject_comparison = {}
        for subject_name, current_data in current_term_data['subject_scores'].items():
            prev_data = previous_term_data['subject_scores'].get(subject_name)
            if prev_data:
                subject_change = current_data['score'] - prev_data['score']
                subject_comparison[subject_name] = {
                    'current_score': current_data['score'],
                    'previous_score': prev_data['score'],
                    'change': subject_change,
                    'percentage_change': (subject_change / prev_data['score'] * 100) if prev_data['score'] > 0 else 0,
                    'current_grade': current_data['grade'],
                    'previous_grade': prev_data['grade']
                }
        
        # Find strongest/weakest subjects
        if subject_comparison:
            strongest_subject = max(subject_comparison.items(), key=lambda x: x[1]['current_score'])[0]
            weakest_subject = min(subject_comparison.items(), key=lambda x: x[1]['current_score'])[0]
            most_improved = max(subject_comparison.items(), key=lambda x: x[1]['change'])[0]
        else:
            strongest_subject = weakest_subject = most_improved = None
        
        return {
            'current_term': current_term_data,
            'previous_term': previous_term_data,
            'average_change': current_avg - previous_avg,
            'percentage_change': percentage_change,
            'trend': trend,
            'trend_direction': trend_direction,
            'subject_comparison': subject_comparison,
            'strongest_subject': strongest_subject,
            'weakest_subject': weakest_subject,
            'most_improved_subject': most_improved
        }
    
    def generate_trend_analysis(self, student_id, terms=None):
        """Generate comprehensive trend analysis for a student"""
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return None
        
        # Get all marks for the student
        all_marks = Mark.objects.filter(student=student).order_by('academic_year', 'term')
        
        if not all_marks.exists():
            return None
        
        # Group by term and year
        term_performances = {}
        for mark in all_marks:
            key = f"{mark.term} {mark.academic_year}"
            if key not in term_performances:
                term_performances[key] = []
            term_performances[key].append(mark)
        
        # Calculate performance for each term
        performances = []
        term_keys = sorted(term_performances.keys())
        
        for i, term_key in enumerate(term_keys):
            marks = term_performances[term_key]
            avg_score = sum(m.total_score for m in marks) / len(marks)
            
            performance = {
                'term_key': term_key,
                'term': marks[0].term,
                'year': marks[0].academic_year,
                'average_score': float(avg_score),
                'subject_count': len(marks),
                'subjects': {m.subject.name: float(m.total_score) for m in marks},
                'grades': {m.subject.name: m.grade for m in marks}
            }
            
            performances.append(performance)
        
        # Generate comparisons
        comparisons = []
        for i in range(1, len(performances)):
            current = performances[i]
            previous = performances[i-1]
            
            comparison = self.compare_term_performance(student, current, previous)
            if comparison:
                comparisons.append({
                    'comparison': comparison,
                    'current_term': current['term_key'],
                    'previous_term': previous['term_key']
                })
        
        # Overall analysis
        if len(performances) >= 2:
            first_term = performances[0]['average_score']
            last_term = performances[-1]['average_score']
            overall_change = last_term - first_term
            overall_percentage = (overall_change / first_term * 100) if first_term > 0 else 0
            
            if overall_percentage > 10:
                overall_trend = 'Significantly Improving'
            elif overall_percentage > 0:
                overall_trend = 'Gradually Improving'
            elif overall_percentage < -10:
                overall_trend = 'Significantly Declining'
            elif overall_percentage < 0:
                overall_trend = 'Gradually Declining'
            else:
                overall_trend = 'Stable'
        else:
            overall_change = 0
            overall_percentage = 0
            overall_trend = 'Insufficient Data'
        
        return {
            'student': student,
            'performances': performances,
            'comparisons': comparisons,
            'overall_change': overall_change,
            'overall_percentage': overall_percentage,
            'overall_trend': overall_trend,
            'has_multiple_terms': len(performances) > 1
        }