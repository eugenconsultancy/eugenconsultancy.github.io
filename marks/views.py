from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages  # Change from school_messages to messages
from django.db.models import Avg, Sum
from .models import Mark, Subject, StudentReport
from .forms import MarkForm, MarkUpdateForm, SubjectForm, StudentReportForm
from students.models import Student
from teachers.models import Teacher
from django.http import JsonResponse
from .analytics import StudentPerformanceAnalyzer

def is_admin(user):
    return user.is_authenticated and user.is_admin()

def is_teacher(user):
    return user.is_authenticated and user.is_teacher()

@login_required
@user_passes_test(is_admin)
def subject_list(request):
    subjects = Subject.objects.all()
    return render(request, 'marks/subject_list.html', {'subjects': subjects})

@login_required
@user_passes_test(is_admin)
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully!')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'marks/subject_form.html', {'form': form, 'title': 'Add Subject'})

@login_required
def mark_list(request):
    if request.user.is_admin():
        marks = Mark.objects.all()
    elif request.user.is_teacher():
        try:
            teacher = Teacher.objects.get(user=request.user)
            marks = Mark.objects.filter(
                student__grade__in=teacher.get_classes_list()
            )
        except Teacher.DoesNotExist:
            marks = Mark.objects.none()
    else:
        marks = Mark.objects.none()
    
    return render(request, 'marks/mark_list.html', {'marks': marks})

@login_required
@user_passes_test(is_teacher)
def mark_create(request):
    try:
        teacher = Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = MarkForm(request.POST, teacher=teacher)
        if form.is_valid():
            mark = form.save(commit=False)
            mark.teacher = teacher
            mark.save()
            messages.success(request, f'Marks for {mark.student} added successfully!')
            return redirect('mark_list')
    else:
        form = MarkForm(teacher=teacher)
    
    return render(request, 'marks/mark_form.html', {'form': form, 'title': 'Add Marks'})

@login_required
@user_passes_test(is_teacher)
def mark_update(request, pk):
    mark = get_object_or_404(Mark, pk=pk)
    
    # Check if teacher can edit this mark
    if request.user != mark.teacher.user and not request.user.is_admin():
        messages.error(request, 'You are not authorized to edit these marks.')
        return redirect('mark_list')
    
    if request.method == 'POST':
        form = MarkUpdateForm(request.POST, instance=mark)
        if form.is_valid():
            form.save()
            messages.success(request, 'Marks updated successfully!')
            return redirect('mark_list')
    else:
        form = MarkUpdateForm(instance=mark)
    
    return render(request, 'marks/mark_form.html', {'form': form, 'title': 'Update Marks'})

@login_required
def student_results(request):
    if request.user.is_student():
        try:
            student = Student.objects.get(user=request.user)
            marks = Mark.objects.filter(student=student)
            
            # Calculate statistics
            if marks.exists():
                average_score = marks.aggregate(Avg('total_score'))['total_score__avg']
                total_subjects = marks.count()
                passed_subjects = marks.filter(grade__in=['A', 'B', 'C', 'D', 'E']).count()
            else:
                average_score = 0
                total_subjects = 0
                passed_subjects = 0
            
            # Get reports
            reports = StudentReport.objects.filter(student=student)
            
            return render(request, 'marks/student_results.html', {
                'student': student,
                'marks': marks,
                'average_score': average_score,
                'total_subjects': total_subjects,
                'passed_subjects': passed_subjects,
                'reports': reports,
            })
        except Student.DoesNotExist:
            messages.error(request, 'Student profile not found.')
            return redirect('dashboard')
    else:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_admin)
def student_report_create(request):
    if request.method == 'POST':
        form = StudentReportForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student report created successfully!')
            return redirect('dashboard')
    else:
        form = StudentReportForm()
    
    return render(request, 'marks/report_form.html', {'form': form, 'title': 'Create Student Report'})

@login_required
def student_performance_analytics(request):
    """Main analytics dashboard"""
    if not (request.user.is_admin() or request.user.is_teacher()):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    students = Student.objects.all()
    analyzer = StudentPerformanceAnalyzer()
    
    # Get top performers
    top_performers = []
    for student in students[:10]:  # Limit to 10 for performance
        marks = Mark.objects.filter(student=student)
        if marks.exists():
            avg = marks.aggregate(Avg('total_score'))['total_score__avg']
            top_performers.append({
                'student': student,
                'average_score': avg,
                'total_subjects': marks.count()
            })
    
    # Sort by average score
    top_performers.sort(key=lambda x: x['average_score'] or 0, reverse=True)
    
    # Get term-wise statistics
    term_stats = []
    terms = Mark.objects.values('term', 'academic_year').distinct().order_by('-academic_year', 'term')
    
    for term in terms[:5]:  # Last 5 terms
        term_marks = Mark.objects.filter(
            term=term['term'],
            academic_year=term['academic_year']
        )
        if term_marks.exists():
            avg = term_marks.aggregate(Avg('total_score'))['total_score__avg']
            term_stats.append({
                'term': term['term'],
                'year': term['academic_year'],
                'average_score': avg,
                'total_marks': term_marks.count()
            })
    
    return render(request, 'marks/analytics_dashboard.html', {
        'top_performers': top_performers[:5],
        'term_stats': term_stats,
        'total_students': students.count(),
        'total_marks': Mark.objects.count()
    })

@login_required
def student_performance_detail(request, student_id):
    """Detailed performance analysis for a specific student"""
    if not (request.user.is_admin() or request.user.is_teacher() or 
           (request.user.is_student() and str(request.user.student.id) == str(student_id))):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    analyzer = StudentPerformanceAnalyzer(student_id)
    analysis = analyzer.generate_trend_analysis(student_id)
    
    if not analysis:
        messages.warning(request, 'Insufficient data for performance analysis.')
        return redirect('student_results')
    
    return render(request, 'marks/student_performance_detail.html', {
        'analysis': analysis,
        'student': analysis['student'],
        'has_comparisons': len(analysis['comparisons']) > 0
    })

@login_required
def term_comparison_analytics(request):
    """Compare performance across terms"""
    if not (request.user.is_admin() or request.user.is_teacher()):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    terms = Mark.objects.values('term', 'academic_year').distinct().order_by('-academic_year', 'term')
    selected_term1 = request.GET.get('term1')
    selected_term2 = request.GET.get('term2')
    
    comparison_data = None
    if selected_term1 and selected_term2:
        # Parse terms
        term1_parts = selected_term1.split('|')
        term2_parts = selected_term2.split('|')
        
        if len(term1_parts) == 2 and len(term2_parts) == 2:
            term1, year1 = term1_parts
            term2, year2 = term2_parts
            
            # Get marks for both terms
            marks_term1 = Mark.objects.filter(term=term1, academic_year=year1)
            marks_term2 = Mark.objects.filter(term=term2, academic_year=year2)
            
            if marks_term1.exists() and marks_term2.exists():
                avg1 = marks_term1.aggregate(Avg('total_score'))['total_score__avg']
                avg2 = marks_term2.aggregate(Avg('total_score'))['total_score__avg']
                
                comparison_data = {
                    'term1': {'term': term1, 'year': year1, 'average': avg1, 'count': marks_term1.count()},
                    'term2': {'term': term2, 'year': year2, 'average': avg2, 'count': marks_term2.count()},
                    'difference': avg2 - avg1,
                    'percentage_change': ((avg2 - avg1) / avg1 * 100) if avg1 > 0 else 0
                }
    
    return render(request, 'marks/term_comparison.html', {
        'terms': terms,
        'comparison_data': comparison_data,
        'selected_term1': selected_term1,
        'selected_term2': selected_term2
    })

@login_required
@user_passes_test(lambda u: u.is_admin())
def generate_performance_trends(request):
    """Generate and save performance trends for all students"""
    from .models import PerformanceTrend  # Import the model
    
    if request.method == 'POST':
        analyzer = StudentPerformanceAnalyzer()
        students = Student.objects.all()
        generated_count = 0
        
        # Get filters from form
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        
        for student in students:
            # Apply filters if specified - call with correct number of arguments
            analysis = analyzer.generate_trend_analysis(student.id)
            
            # Apply filters manually after getting analysis
            if analysis and analysis['has_multiple_terms']:
                # Filter by academic year if specified
                if academic_year:
                    # Check if student has marks in the specified year
                    has_marks_in_year = Mark.objects.filter(
                        student=student, 
                        academic_year=academic_year
                    ).exists()
                    if not has_marks_in_year:
                        continue
                
                # Filter by term if specified
                if term:
                    # Check if student has marks in the specified term
                    has_marks_in_term = Mark.objects.filter(
                        student=student,
                        term=term
                    ).exists()
                    if not has_marks_in_term:
                        continue
                
                # Save or update trend analysis
                try:
                    # Check if trend already exists
                    trend, created = PerformanceTrend.objects.update_or_create(
                        student=student,
                        term=analysis['latest_term'],
                        academic_year=analysis['latest_year'],
                        defaults={
                            'average_score': analysis['average_scores'][-1] if analysis['average_scores'] else 0,
                            'previous_average': analysis['average_scores'][-2] if len(analysis['average_scores']) > 1 else None,
                            'trend': analysis['trend'],
                            'percentage_change': analysis.get('percentage_change', 0),
                            'strongest_subject': analysis.get('strongest_subject'),
                            'weakest_subject': analysis.get('weakest_subject'),
                            'most_improved_subject': analysis.get('most_improved_subject'),
                            'analysis': analysis.get('analysis_text', ''),
                            'recommendations': analysis.get('recommendations', '')
                        }
                    )
                    generated_count += 1
                except Exception as e:
                    print(f"Error generating trend for {student}: {e}")
        
        messages.success(request, f'Generated performance trends for {generated_count} students.')
        return redirect('student_performance_analytics')
    
    # GET request - show form
    # Get statistics for display
    total_students = Student.objects.count()
    
    # Count students with marks
    students_with_marks = Student.objects.filter(marks__isnull=False).distinct().count()
    
    # Count students with multiple terms
    students_multiple_terms = 0
    for student in Student.objects.all():
        term_count = Mark.objects.filter(student=student).values('term', 'academic_year').distinct().count()
        if term_count > 1:
            students_multiple_terms += 1
    
    # Count existing trends
    trends_generated = PerformanceTrend.objects.count()
    
    # Get unique academic years
    academic_years = Mark.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    return render(request, 'marks/generate_trends.html', {
        'total_students': total_students,
        'students_with_marks': students_with_marks,
        'students_multiple_terms': students_multiple_terms,
        'trends_generated': trends_generated,
        'academic_years': academic_years,
    })