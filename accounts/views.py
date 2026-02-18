from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from .forms import LoginForm
from school_messages.models import Notification
from marks.models import Mark
from students.models import Student
from teachers.models import Teacher

def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        # Redirect based on user role for better UX
        if request.user.is_admin():
            messages.info(request, 'Welcome back, Administrator!')
        elif request.user.is_teacher():
            messages.info(request, 'Welcome back, Teacher!')
        elif request.user.is_student():
            messages.info(request, 'Welcome back, Student!')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Custom welcome messages based on role
                    if user.is_admin():
                        messages.success(request, f'Welcome Administrator {user.username}!')
                    elif user.is_teacher():
                        messages.success(request, f'Welcome Teacher {user.username}!')
                    elif user.is_student():
                        messages.success(request, f'Welcome Student {user.username}!')
                    else:
                        messages.success(request, f'Welcome back, {user.username}!')
                    
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Your account is inactive. Please contact administration.')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    """Handle user logout"""
    username = request.user.username
    logout(request)
    messages.info(request, f'Goodbye {username}! You have been logged out successfully.')
    return redirect('login')

@login_required
def dashboard(request):
    """Main dashboard view - shows different content based on user role"""
    user = request.user
    
    # Get unread notifications count
    unread_count = Notification.objects.filter(user=user, is_read=False).count()
    
    # Initialize context variables
    context = {
        'user': user,
        'unread_count': unread_count,
        'has_student_profile': False,
        'has_teacher_profile': False,
        'dashboard_title': 'Dashboard',
    }
    
    # STUDENT DASHBOARD DATA
    if user.is_student():
        context['dashboard_title'] = 'Student Dashboard'
        
        if user.has_student_profile():
            try:
                student_profile = user.get_student_profile()
                context['has_student_profile'] = True
                context['student_profile'] = student_profile
                context['student_id'] = student_profile.id
                
                # Student's class information
                context['grade_section'] = f"{student_profile.grade}{student_profile.section}"
                context['admission_number'] = student_profile.admission_number
                
                # Get student's subjects
                if student_profile.subjects:
                    subjects_list = [s.strip() for s in student_profile.subjects.split(',')]
                    context['subjects_list'] = subjects_list
                    context['subjects_count'] = len(subjects_list)
                
                # Get academic performance data
                marks = Mark.objects.filter(student=student_profile)
                
                if marks.exists():
                    # Calculate overall average
                    total_score = sum(mark.total_score for mark in marks)
                    average_score = total_score / marks.count()
                    context['overall_average'] = round(average_score, 2)
                    
                    # Get latest term marks
                    latest_marks = marks.order_by('-academic_year', '-term')
                    if latest_marks.exists():
                        latest_term = latest_marks.first()
                        context['latest_term'] = f"{latest_term.term} {latest_term.academic_year}"
                        
                        # Calculate latest term average
                        term_marks = marks.filter(
                            term=latest_term.term, 
                            academic_year=latest_term.academic_year
                        )
                        if term_marks.exists():
                            term_total = sum(mark.total_score for mark in term_marks)
                            term_average = term_total / term_marks.count()
                            context['latest_term_average'] = round(term_average, 2)
                    
                    # Count subjects with marks
                    subjects_with_marks = marks.values('subject').distinct().count()
                    context['subjects_with_marks'] = subjects_with_marks
                    
                    # Get grade distribution
                    grade_counts = {
                        'A': marks.filter(grade='A').count(),
                        'B': marks.filter(grade='B').count(),
                        'C': marks.filter(grade='C').count(),
                        'D': marks.filter(grade='D').count(),
                        'E': marks.filter(grade='E').count(),
                        'F': marks.filter(grade='F').count(),
                    }
                    context['grade_counts'] = grade_counts
                    
                    # Calculate pass rate (A-E are passing grades)
                    total_marks = marks.count()
                    passing_marks = marks.filter(grade__in=['A', 'B', 'C', 'D', 'E']).count()
                    if total_marks > 0:
                        context['pass_rate'] = round((passing_marks / total_marks) * 100, 1)
                    
                else:
                    context['no_marks_message'] = 'No academic records available yet.'
                    context['overall_average'] = 'N/A'
                
            except Exception as e:
                context['error_message'] = 'Error loading student data. Please try again later.'
                print(f"Error in student dashboard: {e}")
        else:
            context['warning_message'] = 'Student profile not found. Please contact administration.'
            messages.warning(request, 'Student profile not found. Please contact administration.')
    
    # TEACHER DASHBOARD DATA
    elif user.is_teacher():
        context['dashboard_title'] = 'Teacher Dashboard'
        
        if user.has_teacher_profile():
            try:
                teacher_profile = user.get_teacher_profile()
                context['has_teacher_profile'] = True
                context['teacher_profile'] = teacher_profile
                
                # Teacher's professional information
                context['department'] = teacher_profile.department
                context['employee_id'] = teacher_profile.employee_id
                context['qualification'] = teacher_profile.qualification
                context['experience'] = teacher_profile.experience
                
                # Get assigned subjects
                assigned_subjects = teacher_profile.assigned_subjects.all()
                context['assigned_subjects'] = assigned_subjects
                context['assigned_subjects_count'] = assigned_subjects.count()
                
                # Get classes taught
                if teacher_profile.classes:
                    classes_list = [c.strip() for c in teacher_profile.classes.split(',')]
                    context['classes_taught'] = classes_list
                    context['classes_count'] = len(classes_list)
                
                # Get subjects taught
                if teacher_profile.subjects:
                    subjects_list = [s.strip() for s in teacher_profile.subjects.split(',')]
                    context['subjects_taught'] = subjects_list
                    context['subjects_taught_count'] = len(subjects_list)
                
                # Get teacher's marks given (for statistics)
                marks_given = teacher_profile.marks_given.all()
                context['marks_given_count'] = marks_given.count()
                
                # Get recent marks given
                recent_marks = marks_given.order_by('-date_entered')[:10]
                context['recent_marks'] = recent_marks
                
            except Exception as e:
                context['error_message'] = 'Error loading teacher data. Please try again later.'
                print(f"Error in teacher dashboard: {e}")
        else:
            context['warning_message'] = 'Teacher profile not found. Please contact administration.'
            messages.warning(request, 'Teacher profile not found. Please contact administration.')
    
    # ADMIN DASHBOARD DATA
    elif user.is_admin():
        context['dashboard_title'] = 'Admin Dashboard'
        
        try:
            # System statistics
            total_students = Student.objects.count()
            total_teachers = Teacher.objects.count()
            total_users = user.__class__.objects.count()
            active_users = user.__class__.objects.filter(is_active=True).count()
            
            context['total_students'] = total_students
            context['total_teachers'] = total_teachers
            context['total_users'] = total_users
            context['active_users'] = active_users
            
            # Get recent student registrations
            recent_students = Student.objects.select_related('user').order_by('-created_at')[:5]
            context['recent_students'] = recent_students
            
            # Get recent teacher registrations
            recent_teachers = Teacher.objects.select_related('user').order_by('-created_at')[:5]
            context['recent_teachers'] = recent_teachers
            
            # Get users by role
            student_users = user.__class__.objects.filter(role='student').count()
            teacher_users = user.__class__.objects.filter(role='teacher').count()
            admin_users = user.__class__.objects.filter(role='admin').count()
            
            context['student_users'] = student_users
            context['teacher_users'] = teacher_users
            context['admin_users'] = admin_users
            
            # Get system alerts (placeholder for future features)
            context['system_alerts'] = []
            
        except Exception as e:
            context['error_message'] = 'Error loading system statistics.'
            print(f"Error in admin dashboard: {e}")
    
    # FALLBACK FOR OTHER ROLES
    else:
        context['dashboard_title'] = 'User Dashboard'
        context['info_message'] = 'Welcome to your dashboard.'
    
    # Determine template based on user role
    if user.is_admin():
        template = 'accounts/admin_dashboard.html'
    elif user.is_teacher():
        template = 'accounts/teacher_dashboard.html'
    elif user.is_student():
        template = 'accounts/student_dashboard.html'
    else:
        template = 'accounts/dashboard.html'
    
    return render(request, template, context)