from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Student
from .forms import StudentForm
from accounts.models import User
from teachers.models import Teacher

def is_admin(user):
    return user.is_authenticated and user.is_admin()

def is_teacher(user):
    return user.is_authenticated and user.is_teacher()

@login_required
@user_passes_test(is_admin)
def student_list(request):
    students = Student.objects.all()
    return render(request, 'students/student_list.html', {'students': students})

@login_required
@user_passes_test(is_admin)
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'students/student_detail.html', {'student': student})

@login_required
@user_passes_test(is_admin)
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save()  # Now returns only student
            messages.success(request, f'Student {student.user.get_full_name()} created successfully!')
            
            # Store generated password in session (it's in student.generated_password)
            if hasattr(student, 'generated_password'):
                messages.info(request, f'Generated password: {student.generated_password}')
                
            return redirect('student_list')
    else:
        form = StudentForm()
    return render(request, 'students/student_form.html', {'form': form, 'title': 'Add Student'})

@login_required
@user_passes_test(is_admin)
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f'Student {student.user.get_full_name()} updated successfully!')
            return redirect('student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'students/student_form.html', {'form': form, 'title': 'Update Student'})

@login_required
def student_profile(request):
    try:
        student = Student.objects.get(user=request.user)
        return render(request, 'students/student_detail.html', {'student': student})
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_teacher)
def teacher_student_list(request):
    """View for teachers to see their students with passwords"""
    if not request.user.is_teacher():
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    try:
        teacher = Teacher.objects.get(user=request.user)
        
        # Get students based on teacher's assigned classes
        assigned_students = teacher.get_assigned_students()
        
        return render(request, 'teachers/student_list_with_passwords.html', {
            'teacher': teacher,
            'students': assigned_students
        })
    except Teacher.DoesNotExist:
        messages.error(request, 'Teacher profile not found.')
        return redirect('dashboard')