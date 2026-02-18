# marks/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Subject, Mark, StudentReport, PerformanceTrend

@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ('name', 'code', 'get_category_display', 'description_short')
    list_filter = ('category',)
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'

@admin.register(Mark)
class MarkAdmin(ModelAdmin):
    list_display = ('student_info', 'subject_name', 'term_year', 'total_score', 'grade_display', 'teacher_name')
    list_filter = ('grade', 'term', 'academic_year', 'subject')
    search_fields = (
        'student__user__username', 
        'student__user__first_name', 
        'student__user__last_name',
        'subject__name',
        'teacher__user__username'
    )
    readonly_fields = ('total_score', 'grade', 'date_entered', 'last_modified')
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'teacher', 'subject')
        }),
        ('Assessment Scores', {
            'fields': ('cat1_score', 'cat2_score', 'main_exam_score')
        }),
        ('Term Information', {
            'fields': ('term', 'academic_year')
        }),
        ('Calculated Fields', {
            'fields': ('total_score', 'grade'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('comments',)
        }),
        ('Timestamps', {
            'fields': ('date_entered', 'last_modified'),
            'classes': ('collapse',)
        }),
    )
    
    def student_info(self, obj):
        return f"{obj.student.user.get_full_name()} ({obj.student.admission_number})"
    student_info.short_description = 'Student'
    
    def subject_name(self, obj):
        return obj.subject.name
    subject_name.short_description = 'Subject'
    
    def term_year(self, obj):
        return f"{obj.term} {obj.academic_year}"
    term_year.short_description = 'Term/Year'
    
    def grade_display(self, obj):
        return obj.get_grade_display()
    grade_display.short_description = 'Grade'
    
    def teacher_name(self, obj):
        return obj.teacher.user.get_full_name() if obj.teacher else 'N/A'
    teacher_name.short_description = 'Teacher'

@admin.register(StudentReport)
class StudentReportAdmin(ModelAdmin):
    list_display = ('student_info', 'term_year', 'average_score', 'overall_grade_display', 'class_position_info', 'date_created_display')
    list_filter = ('term', 'academic_year', 'overall_grade')
    search_fields = (
        'student__user__username',
        'student__user__first_name',
        'student__user__last_name',
        'teacher_comment',
        'principal_comment'
    )
    readonly_fields = ('date_created', 'date_modified')
    fieldsets = (
        ('Student Information', {
            'fields': ('student',)
        }),
        ('Term Information', {
            'fields': ('term', 'academic_year')
        }),
        ('Performance Metrics', {
            'fields': (
                'average_score', 'overall_grade', 
                'class_position', 'total_students',
                'days_present', 'total_days'
            )
        }),
        ('Comments', {
            'fields': ('teacher_comment', 'principal_comment'),
            'classes': ('wide',)
        }),
        ('Timestamps', {
            'fields': ('date_created', 'date_modified'),
            'classes': ('collapse',)
        }),
    )
    
    def student_info(self, obj):
        return f"{obj.student.user.get_full_name()} ({obj.student.admission_number})"
    student_info.short_description = 'Student'
    
    def term_year(self, obj):
        return f"{obj.term} {obj.academic_year}"
    term_year.short_description = 'Term/Year'
    
    def overall_grade_display(self, obj):
        return obj.get_overall_grade_display()
    overall_grade_display.short_description = 'Overall Grade'
    
    def class_position_info(self, obj):
        return f"{obj.class_position}/{obj.total_students}"
    class_position_info.short_description = 'Position'
    
    def date_created_display(self, obj):
        return obj.date_created.strftime('%Y-%m-%d')
    date_created_display.short_description = 'Created'

@admin.register(PerformanceTrend)
class PerformanceTrendAdmin(ModelAdmin):
    list_display = ('student_name_display', 'term_year', 'current_average', 'trend_display', 'performance_level_display', 'date_generated_display')
    list_filter = ('trend', 'trend_direction', 'academic_year', 'term')
    search_fields = (
        'student__user__username',
        'student__user__first_name',
        'student__user__last_name',
        'analysis_summary',
        'recommendations'
    )
    readonly_fields = (
        'date_generated', 'last_updated', 
        'score_change', 'percentage_change', 'pass_rate',
        'current_term_average', 'previous_term_average', 'overall_average'
    )
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'term', 'academic_year')
        }),
        ('Performance Metrics', {
            'fields': (
                'current_term_average', 'previous_term_average', 'overall_average',
                'score_change', 'percentage_change'
            )
        }),
        ('Trend Analysis', {
            'fields': ('trend', 'trend_direction')
        }),
        ('Subject Analysis', {
            'fields': (
                'strongest_subject', 'strongest_subject_score',
                'weakest_subject', 'weakest_subject_score',
                'most_improved_subject', 'improvement_amount'
            ),
            'classes': ('collapse',)
        }),
        ('Grade Distribution', {
            'fields': (
                'grade_a_count', 'grade_b_count', 'grade_c_count',
                'grade_d_count', 'grade_e_count', 'grade_f_count',
                'subjects_passed', 'total_subjects', 'pass_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Analysis & Recommendations', {
            'fields': (
                'strengths', 'weaknesses', 'analysis_summary',
                'recommendations', 'action_items'
            ),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('is_active', 'generated_by', 'date_generated', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    def student_name_display(self, obj):
        return obj.student_name if hasattr(obj, 'student_name') else obj.student.user.get_full_name()
    student_name_display.short_description = 'Student'
    
    def term_year(self, obj):
        return f"{obj.term} {obj.academic_year}"
    term_year.short_description = 'Term/Year'
    
    def current_average(self, obj):
        return f"{obj.current_term_average:.1f}"
    current_average.short_description = 'Avg Score'
    
    def trend_display(self, obj):
        icon, label = obj.trend_indicator
        return f"{icon} {label}"
    trend_display.short_description = 'Trend'
    
    def performance_level_display(self, obj):
        return obj.performance_level if hasattr(obj, 'performance_level') else 'N/A'
    performance_level_display.short_description = 'Level'
    
    def date_generated_display(self, obj):
        return obj.date_generated.strftime('%Y-%m-%d')
    date_generated_display.short_description = 'Generated'
    
    # Custom actions
    actions = ['regenerate_analysis', 'mark_as_inactive']
    
    @admin.action(description='Regenerate trend analysis')
    def regenerate_analysis(self, request, queryset):
        from .analytics import StudentPerformanceAnalyzer
        
        updated_count = 0
        for trend in queryset:
            analyzer = StudentPerformanceAnalyzer()
            analysis = analyzer.generate_trend_analysis(trend.student.id)
            if analysis:
                updated_count += 1
        
        self.message_user(request, f'Regenerated analysis for {updated_count} trend records.')
    
    @admin.action(description='Mark selected as inactive')
    def mark_as_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Marked {updated} trend records as inactive.')