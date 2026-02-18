from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Teacher
from .forms import TeacherForm
from students.models import Student
from accounts.models import User

def is_admin(user):
    return user.is_authenticated and user.is_admin()

@login_required
@user_passes_test(is_admin)
def teacher_list(request):
    teachers = Teacher.objects.all()
    return render(request, 'teachers/teacher_list.html', {'teachers': teachers})

@login_required
@user_passes_test(is_admin)
def teacher_detail(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    return render(request, 'teachers/teacher_detail.html', {'teacher': teacher})

@login_required
@user_passes_test(is_admin)
def teacher_create(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = form.save()
            messages.success(request, f'Teacher {teacher.user.get_full_name()} created successfully!')
            return redirect('teacher_list')
    else:
        form = TeacherForm()
    return render(request, 'teachers/teacher_form.html', {'form': form, 'title': 'Add Teacher'})

@login_required
@user_passes_test(is_admin)
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, f'Teacher {teacher.user.get_full_name()} updated successfully!')
            return redirect('teacher_list')
    else:
        form = TeacherForm(instance=teacher)
    return render(request, 'teachers/teacher_form.html', {'form': form, 'title': 'Update Teacher'})

@login_required
def teacher_students(request):
    if not request.user.is_teacher():
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    try:
        teacher = Teacher.objects.get(user=request.user)
        assigned_students = teacher.get_assigned_students()
        return render(request, 'teachers/teacher_students.html', {
            'teacher': teacher,
            'students': assigned_students
        })
    except Teacher.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('dashboard')
    

@login_required
@user_passes_test(is_admin)
def teacher_passwords_view(request):
    """Admin view to see all teacher passwords"""
    teachers = Teacher.objects.select_related('user').all()
    
    # Create a list with password information
    teachers_with_passwords = []
    for teacher in teachers:
        teachers_with_passwords.append({
            'teacher': teacher,
            'username': teacher.user.username,
            'password_display': '********',  # Placeholder - in reality would show actual
            'email': teacher.user.email,
            'employee_id': teacher.employee_id,
        })
    
    return render(request, 'teachers/teacher_passwords.html', {
        'teachers': teachers_with_passwords
    })