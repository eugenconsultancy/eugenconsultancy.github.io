from django.db import models
from students.models import Student
# Remove: from teachers.models import Teacher
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg, Sum, Count

class Subject(models.Model):
    SUBJECT_CATEGORIES = (
        ('humanities', 'Humanities'),
        ('creative_arts', 'Creative Arts'),
        ('technical', 'Technical Subjects'),
        ('sciences', 'Sciences'),
        ('languages', 'Languages'),
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=20, choices=SUBJECT_CATEGORIES)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['category', 'name']

class Mark(models.Model):
    GRADE_CHOICES = (
        ('A', 'A (Excellent)'),
        ('B', 'B (Very Good)'),
        ('C', 'C (Good)'),
        ('D', 'D (Satisfactory)'),
        ('E', 'E (Sufficient)'),
        ('F', 'F (Fail)'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    # Use string reference instead of direct import
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, related_name='marks_given')
    
    # Marks components
    cat1_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    cat2_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    main_exam_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Calculated fields
    total_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES)
    
    term = models.CharField(max_length=20)  # e.g., "Term 1 2024"
    academic_year = models.CharField(max_length=20)
    
    comments = models.TextField(blank=True)
    date_entered = models.DateField(auto_now_add=True)
    last_modified = models.DateField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', 'term', 'student']
        unique_together = ['student', 'subject', 'term', 'academic_year']
    
    def save(self, *args, **kwargs):
        # Calculate total score (CAT1: 20%, CAT2: 20%, Main Exam: 60%)
        cat1 = self.cat1_score or 0
        cat2 = self.cat2_score or 0
        main_exam = self.main_exam_score or 0
        
        self.total_score = (cat1 * 0.2) + (cat2 * 0.2) + (main_exam * 0.6)
        
        # Determine grade
        if self.total_score >= 80:
            self.grade = 'A'
        elif self.total_score >= 70:
            self.grade = 'B'
        elif self.total_score >= 60:
            self.grade = 'C'
        elif self.total_score >= 50:
            self.grade = 'D'
        elif self.total_score >= 40:
            self.grade = 'E'
        else:
            self.grade = 'F'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student} - {self.subject} - {self.total_score}% ({self.grade})"

class StudentReport(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reports')
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    
    # Overall performance
    average_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    overall_grade = models.CharField(max_length=1, choices=Mark.GRADE_CHOICES)
    class_position = models.PositiveIntegerField()
    total_students = models.PositiveIntegerField()
    
    # Comments
    teacher_comment = models.TextField(blank=True)
    principal_comment = models.TextField(blank=True)
    
    # Attendance
    days_present = models.PositiveIntegerField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.student} - {self.term} {self.academic_year}"
    
    class Meta:
        ordering = ['-academic_year', 'term', 'student']


    # Add this at the end of marks/models.py, before the closing of the file

class PerformanceTrend(models.Model):
    TREND_CHOICES = (
        ('improving', 'Improving'),
        ('declining', 'Declining'),
        ('stable', 'Stable'),
        ('fluctuating', 'Fluctuating'),
        ('significant_improvement', 'Significant Improvement'),
        ('significant_decline', 'Significant Decline'),
        ('gradual_improvement', 'Gradual Improvement'),
        ('gradual_decline', 'Gradual Decline'),
    )
    
    TREND_DIRECTION_CHOICES = (
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='performance_trends')
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    
    # Performance metrics
    current_term_average = models.DecimalField(max_digits=5, decimal_places=2)
    previous_term_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    overall_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Trend analysis
    trend = models.CharField(max_length=30, choices=TREND_CHOICES, default='stable')
    trend_direction = models.CharField(max_length=10, choices=TREND_DIRECTION_CHOICES, default='neutral')
    
    # Change metrics
    score_change = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, 
                                       help_text="Absolute change in average score")
    percentage_change = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text="Percentage change from previous term")
    
    # Subject analysis
    strongest_subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, 
                                         related_name='as_strongest_subject')
    strongest_subject_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    weakest_subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='as_weakest_subject')
    weakest_subject_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    most_improved_subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='as_most_improved')
    improvement_amount = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Performance indicators
    subjects_passed = models.PositiveIntegerField(default=0)
    total_subjects = models.PositiveIntegerField(default=0)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Grade distribution
    grade_a_count = models.PositiveIntegerField(default=0)
    grade_b_count = models.PositiveIntegerField(default=0)
    grade_c_count = models.PositiveIntegerField(default=0)
    grade_d_count = models.PositiveIntegerField(default=0)
    grade_e_count = models.PositiveIntegerField(default=0)
    grade_f_count = models.PositiveIntegerField(default=0)
    
    # Analysis and recommendations
    strengths = models.TextField(blank=True, help_text="Key strengths observed")
    weaknesses = models.TextField(blank=True, help_text="Areas needing improvement")
    analysis_summary = models.TextField(blank=True, help_text="Overall performance analysis")
    
    recommendations = models.TextField(blank=True, help_text="Recommendations for improvement")
    action_items = models.TextField(blank=True, help_text="Specific action items")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    generated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    date_generated = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', 'term', 'student']
        unique_together = ['student', 'term', 'academic_year']
        verbose_name = "Performance Trend"
        verbose_name_plural = "Performance Trends"
        indexes = [
            models.Index(fields=['student', 'trend']),
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['trend_direction', 'date_generated']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.term} {self.academic_year} ({self.get_trend_display()})"
    
    @property
    def student_name(self):
        return self.student.full_name
    
    @property
    def performance_level(self):
        """Determine performance level based on average score"""
        if self.current_term_average >= 80:
            return 'Excellent'
        elif self.current_term_average >= 70:
            return 'Very Good'
        elif self.current_term_average >= 60:
            return 'Good'
        elif self.current_term_average >= 50:
            return 'Satisfactory'
        elif self.current_term_average >= 40:
            return 'Sufficient'
        else:
            return 'Needs Improvement'
    
    @property
    def trend_indicator(self):
        """Get trend indicator with icon"""
        indicators = {
            'improving': ('📈', 'Improving'),
            'declining': ('📉', 'Declining'),
            'stable': ('➡️', 'Stable'),
            'fluctuating': ('📊', 'Fluctuating'),
            'significant_improvement': ('🚀', 'Significant Improvement'),
            'significant_decline': ('⚠️', 'Significant Decline'),
            'gradual_improvement': ('↗️', 'Gradual Improvement'),
            'gradual_decline': ('↘️', 'Gradual Decline'),
        }
        return indicators.get(self.trend, ('➡️', 'Stable'))
    
    @property
    def trend_color(self):
        """Get CSS class for trend color"""
        if self.trend_direction == 'positive':
            return 'text-success'
        elif self.trend_direction == 'negative':
            return 'text-danger'
        else:
            return 'text-secondary'
    
    @property
    def trend_badge_class(self):
        """Get Bootstrap badge class for trend"""
        if self.trend_direction == 'positive':
            return 'badge bg-success'
        elif self.trend_direction == 'negative':
            return 'badge bg-danger'
        else:
            return 'badge bg-secondary'
    
    def calculate_pass_rate(self):
        """Calculate pass rate based on subjects passed"""
        if self.total_subjects > 0:
            self.pass_rate = (self.subjects_passed / self.total_subjects) * 100
        else:
            self.pass_rate = 0
    
    def update_from_marks(self, marks_queryset):
        """Update trend data from marks queryset"""
        if not marks_queryset.exists():
            return False
        
        # Calculate average score
        avg_score = marks_queryset.aggregate(avg=Avg('total_score'))['avg']
        self.current_term_average = avg_score or 0
        
        # Count subjects and passed subjects
        self.total_subjects = marks_queryset.count()
        self.subjects_passed = marks_queryset.filter(grade__in=['A', 'B', 'C', 'D', 'E']).count()
        
        # Calculate pass rate
        self.calculate_pass_rate()
        
        # Count grades
        self.grade_a_count = marks_queryset.filter(grade='A').count()
        self.grade_b_count = marks_queryset.filter(grade='B').count()
        self.grade_c_count = marks_queryset.filter(grade='C').count()
        self.grade_d_count = marks_queryset.filter(grade='D').count()
        self.grade_e_count = marks_queryset.filter(grade='E').count()
        self.grade_f_count = marks_queryset.filter(grade='F').count()
        
        # Find strongest and weakest subjects
        subject_scores = {}
        for mark in marks_queryset.select_related('subject'):
            subject_scores[mark.subject] = mark.total_score
        
        if subject_scores:
            strongest = max(subject_scores.items(), key=lambda x: x[1])
            weakest = min(subject_scores.items(), key=lambda x: x[1])
            
            self.strongest_subject = strongest[0]
            self.strongest_subject_score = strongest[1]
            self.weakest_subject = weakest[0]
            self.weakest_subject_score = weakest[1]
        
        self.save()
        return True
    
    def compare_with_previous(self, previous_trend):
        """Compare with previous term trend"""
        if not previous_trend:
            return
        
        self.previous_term_average = previous_trend.current_term_average
        
        # Calculate changes
        self.score_change = self.current_term_average - previous_trend.current_term_average
        
        if previous_trend.current_term_average > 0:
            self.percentage_change = (self.score_change / previous_trend.current_term_average) * 100
        else:
            self.percentage_change = 0
        
        # Determine trend direction
        if self.percentage_change > 10:
            self.trend = 'significant_improvement'
            self.trend_direction = 'positive'
        elif self.percentage_change > 2:
            self.trend = 'gradual_improvement'
            self.trend_direction = 'positive'
        elif self.percentage_change > -2:
            self.trend = 'stable'
            self.trend_direction = 'neutral'
        elif self.percentage_change > -10:
            self.trend = 'gradual_decline'
            self.trend_direction = 'negative'
        else:
            self.trend = 'significant_decline'
            self.trend_direction = 'negative'
        
        # Generate analysis
        self.generate_analysis(previous_trend)
        self.save()
    
    def generate_analysis(self, previous_trend=None):
        """Generate analysis and recommendations"""
        analysis_parts = []
        recommendation_parts = []
        
        # Performance level analysis
        performance_level = self.performance_level
        analysis_parts.append(f"Performance Level: {performance_level}")
        
        # Trend analysis
        if self.trend_direction == 'positive':
            analysis_parts.append(f"Performance is improving ({self.percentage_change:+.1f}% change)")
        elif self.trend_direction == 'negative':
            analysis_parts.append(f"Performance needs attention ({self.percentage_change:+.1f}% change)")
        else:
            analysis_parts.append("Performance is stable")
        
        # Subject analysis
        if self.strongest_subject:
            analysis_parts.append(f"Strongest subject: {self.strongest_subject.name} ({self.strongest_subject_score}%)")
            recommendation_parts.append(f"Maintain excellence in {self.strongest_subject.name}")
        
        if self.weakest_subject:
            analysis_parts.append(f"Area needing improvement: {self.weakest_subject.name} ({self.weakest_subject_score}%)")
            recommendation_parts.append(f"Focus on improving {self.weakest_subject.name}")
        
        # Pass rate analysis
        if self.pass_rate >= 80:
            analysis_parts.append(f"Excellent pass rate: {self.pass_rate:.1f}%")
        elif self.pass_rate >= 60:
            analysis_parts.append(f"Good pass rate: {self.pass_rate:.1f}%")
        else:
            analysis_parts.append(f"Pass rate needs improvement: {self.pass_rate:.1f}%")
            recommendation_parts.append("Increase focus on subjects with lower grades")
        
        # Grade distribution analysis
        if self.grade_a_count > 0:
            analysis_parts.append(f"Achieved {self.grade_a_count} A grade(s)")
        
        if self.grade_f_count > 0:
            analysis_parts.append(f"Has {self.grade_f_count} subject(s) requiring attention")
            recommendation_parts.append("Seek additional help for subjects with F grades")
        
        # Overall recommendations
        if self.trend_direction == 'positive':
            recommendation_parts.append("Continue current study habits and routines")
        elif self.trend_direction == 'negative':
            recommendation_parts.append("Review and adjust study strategies")
            recommendation_parts.append("Consider seeking tutoring for challenging subjects")
        
        recommendation_parts.append("Regularly review progress and set achievable goals")
        
        self.analysis_summary = "\n".join(analysis_parts)
        self.recommendations = "\n".join(recommendation_parts)
        
        # Generate action items
        action_items = []
        if self.trend_direction == 'negative':
            action_items.append("Schedule meeting with subject teachers")
            action_items.append("Create weekly study plan")
            action_items.append("Join study groups for challenging subjects")
        else:
            action_items.append("Set higher academic goals")
            action_items.append("Participate in advanced topics")
            action_items.append("Help peers who are struggling")
        
        if self.grade_f_count > 0:
            action_items.append("Request extra classes for failed subjects")
        
        self.action_items = "\n".join(action_items)