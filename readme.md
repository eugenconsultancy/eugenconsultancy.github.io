Here are Git Bash terminal commands to undo recent edits in your project:

## Option 1: Undo last 5-10 commits (if you've committed them)

```bash
# See last 10 commits first
git log --oneline -10

# Undo last 5 commits (keep changes locally)
git reset --soft HEAD~5

# Undo last 10 commits (keep changes locally)
git reset --soft HEAD~10

# Undo last 5 commits (DESTROY changes - careful!)
git reset --hard HEAD~5

# Undo last 10 commits (DESTROY changes - careful!)
git reset --hard HEAD~10
```

## Option 2: Undo uncommitted changes in specific files

```bash
# Check which files have changes
git status

# Undo changes in a specific file
git checkout -- path/to/file.py

# Undo changes in multiple specific files
git checkout -- accounts/templates/accounts/base.html
git checkout -- school_a/settings.py
git checkout -- marks/models.py

# Undo all uncommitted changes (careful!)
git checkout -- .

# Or use restore command (Git 2.23+)
git restore path/to/file.py
```

## Option 3: Stash changes temporarily

```bash
# Save all uncommitted changes to stash
git stash

# See list of stashes
git stash list

# Apply the last stash back
git stash pop

# Apply specific stash (stash@{2} means 3rd stash)
git stash apply stash@{2}

# Drop a stash (delete it)
git stash drop stash@{0}
```

## Option 4: Find and revert specific changes

```bash
# Find what changed in last 5 commits
git diff HEAD~5 HEAD

# Create a reverse patch for last 5 commits
git diff HEAD~5 HEAD > changes.patch
git apply -R changes.patch

# Interactive revert (choose which changes to undo)
git add -p
```

## Option 5: Reset to specific commit

```bash
# First, find the commit hash you want to go back to
git log --oneline --graph -20

# Copy the commit hash you want to return to
# Then reset to that commit (keeps changes)
git reset --soft <commit-hash>

# Or reset to that commit (destroys changes)
git reset --hard <commit-hash>
```

## Option 6: Safe approach - Create backup first

```bash
# Create a backup branch first (RECOMMENDED)
git branch backup-before-undo-$(date +%Y%m%d-%H%M%S)

# Check which branch you're on
git branch

# Now you can safely undo changes
git reset --soft HEAD~5

# If you mess up, go back to backup
git checkout backup-branch-name
```

## Option 7: Most likely what you need (undo recent file edits)

```bash
# 1. First, check what you changed recently
git status

# 2. If you want to undo ALL recent uncommitted changes:
git stash

# 3. Or selectively undo files:
git checkout -- accounts/templates/accounts/base.html
git checkout -- marks/views.py
git checkout -- marks/models.py

# 4. To see what you're about to undo:
git diff
```

## Option 8: Smart undo for specific number of edits

```bash
# Custom function to undo N edits
undo_edits() {
    if [ -z "$1" ]; then
        echo "Usage: undo_edits <number>"
        echo "Example: undo_edits 5"
        return 1
    fi
    
    echo "Creating backup branch..."
    git branch "backup-undo-$1-$(date +%s)"
    
    echo "Undoing last $1 commits..."
    git reset --soft HEAD~$1
    
    echo "Done! Changes are preserved locally."
    echo "Run 'git status' to see unstaged changes."
    echo "Run 'git reset --hard HEAD~$1' to DESTROY changes."
}

# Add this to your .bashrc or run directly
# Then use: undo_edits 5
```

## Quick Recovery Commands:

```bash
# If you accidentally did hard reset and want to recover:
git reflog
# Find the commit before the reset, then:
git reset --hard HEAD@{1}

# To completely discard all local changes and commits:
git fetch origin
git reset --hard origin/main  # or origin/master, origin/develop
```

## **SAFEST APPROACH - Step by step:**

```bash
# 1. First, make sure you don't lose work
git stash
# or
git add .
git commit -m "Backup before undo"

# 2. Check your recent history
git log --oneline -10

# 3. Decide how many commits to undo
# For 5 commits (keeps changes):
git reset --soft HEAD~5

# 4. Review what's left
git status

# 5. If you want to keep some changes, commit them:
git add .
git commit -m "Saved important changes"

# 6. If you want to discard everything:
git reset --hard
```

**Important:** Use `--soft` to keep your changes locally, use `--hard` only if you're sure you want to permanently delete changes. Always create a backup branch first!


accounts/base.html - UPDATE THIS LINE:
Find this line (around line 94):

html
{% if 'student_performance_detail' in request.resolver_match.url_name %}
Change to:

html
{% if student_id and 'student_performance_detail' in request.resolver_match.url_name %}
Find these lines (around lines 103-111):

html
<li class="nav-item">
    {% if user.student and user.student.id %}
    <a class="nav-link {% if 'student_performance_detail' in request.resolver_match.url_name %}active{% endif %}" 
       href="{% url 'student_performance_detail' user.student.id %}"
       title="View your performance trends and analytics">
        <i class="fas fa-chart-line"></i> Performance Trends
    </a>
    {% else %}
    <a class="nav-link disabled" href="#"
       title="Student profile not found. Please contact administration.">
        <i class="fas fa-chart-line"></i> Performance Trends
    </a>
    {% endif %}
</li>
Change to:

html
<li class="nav-item">
    {% if user.has_student_profile and user.student_profile.id %}
    <a class="nav-link {% if 'student_performance_detail' in request.resolver_match.url_name %}active{% endif %}" 
       href="{% url 'student_performance_detail' user.student_profile.id %}"
       title="View your performance trends and analytics">
        <i class="fas fa-chart-line"></i> Performance Trends
    </a>
    {% else %}
    <a class="nav-link disabled" href="#"
       title="Student profile not found. Please contact administration.">
        <i class="fas fa-chart-line"></i> Performance Trends
    </a>
    {% endif %}
</li>
Find this line (around line 254):

html
{% if user.student and user.student.id %}
Change to:

html
{% if user.has_student_profile and user.student_profile.id %}
Find this line (around line 271):

html
{% if user.student and user.student.id %}
Change to:

html
{% if user.has_student_profile and user.student_profile.id %}
















# **School Administration System - Project Overview**

## **🎯 What It Does**

This is a **comprehensive school management system** built with Django that handles:
- **Student management** (admissions, profiles, academic records)
- **Teacher management** (assignments, qualifications, classes)
- **Academic management** (subjects, marks, grading, reports)
- **Financial management** (fee structures, payments, M-Pesa integration)
- **Communication system** (messages, notifications, announcements)
- **Performance analytics** (trend analysis, reporting, dashboards)

## **🛠️ How It Works**

### **Architecture:**
```
┌─────────────────────────────────────────────────────┐
│         School Administration System                │
├─────────────────────────────────────────────────────┤
│  Frontend: Bootstrap 5 + Custom CSS + Font Awesome  │
│  Backend: Django 5.2 + Django Unfold (Admin Theme)  │
│  Database: SQLite3 (Development)                    │
│  Authentication: Custom User Model with 3 roles     │
│  Payment: M-Pesa API Integration                    │
└─────────────────────────────────────────────────────┘
```

### **Core Components:**

1. **Custom User Model** (`accounts.User`):
   - 3 roles: Admin, Teacher, Student
   - Role-based permissions and dashboards
   - Profile management for each role

2. **Multi-App Structure:**
   - `accounts`: Authentication & user management
   - `students`: Student profiles and management
   - `teachers`: Teacher profiles and management  
   - `marks`: Academic records and performance tracking
   - `payments`: Financial management with M-Pesa
   - `school_messages`: Communication system

3. **Database Design:**
   ```python
   User → Student/Teacher (OneToOne)
   Student → Marks (OneToMany)
   Teacher → Subjects (ManyToMany)
   Subject → Marks (ForeignKey)
   Student → Payments (OneToMany)
   ```

## **✨ Key Features & Functions**

### **1. User Role Features:**

#### **Admin Users:**
- ✅ Full system control
- ✅ Student/Teacher management
- ✅ Fee structure setup
- ✅ Financial reports
- ✅ Performance analytics dashboard
- ✅ System configuration
- ✅ Message broadcasting

#### **Teacher Users:**
- ✅ Class management
- ✅ Mark entry and editing
- ✅ Student performance tracking
- ✅ Communication with students
- ✅ Attendance tracking
- ✅ Grade analysis

#### **Student Users:**
- ✅ View academic results
- ✅ Performance trend analysis
- ✅ Fee payment tracking
- ✅ Message system
- ✅ Profile management
- ✅ Academic progress monitoring

### **2. Academic Management:**

#### **Marks System:**
- **CAT 1** (20%), **CAT 2** (20%), **Main Exam** (60%)
- **Automatic grade calculation** (A-F grading system)
- **Term-wise organization**
- **Subject categorization** (Sciences, Humanities, etc.)
- **Performance trend analysis**

#### **Performance Analytics:**
- **Student trend analysis** (improving/declining/stable)
- **Term comparison tools**
- **Subject-wise performance**
- **Automated report generation**
- **Visual dashboards**

### **3. Financial Management:**

#### **Payment System:**
- **Fee structure management**
- **M-Pesa integration** (Lipa Na M-Pesa)
- **Payment tracking**
- **Receipt generation**
- **Financial reports**
- **Payment reminders**

### **4. Communication System:**

#### **Messaging:**
- **Internal messaging** between users
- **Notifications system**
- **Holiday notices**
- **Announcements**
- **Read receipts**
- **Inbox/Outbox organization**

### **5. Reporting & Analytics:**

#### **Reports Generated:**
- **Student academic reports**
- **Class performance reports**
- **Financial statements**
- **Attendance reports**
- **Teacher performance**
- **System usage analytics**

## **🚀 Technical Implementation**

### **Django Apps Structure:**
```
school_a_project/
├── accounts/          # Authentication & users
├── students/          # Student management
├── teachers/          # Teacher management
├── marks/            # Academic records
├── payments/         # Financial system
├── school_messages/  # Communication
└── school_a/         # Main project settings
```

### **Key Models:**
- **`Student`**: Academic records, classes, parent info
- **`Teacher`**: Qualifications, subjects, classes taught
- **`Subject`**: Course catalog with categories
- **`Mark`**: Academic performance with auto-grading
- **`Payment`**: Financial transactions with M-Pesa
- **`Message`**: Communication between users
- **`PerformanceTrend`**: Analytics and trend tracking

### **Custom Features Implemented:**

1. **Dynamic Navigation**: Role-based menu system
2. **Auto-Grading**: Automatic grade calculation based on scores
3. **Performance Analysis**: Trend detection algorithms
4. **M-Pesa Integration**: Real-time payment processing
5. **Responsive Design**: Mobile-friendly interface
6. **Real-time Notifications**: Unread message counters
7. **Data Visualization**: Performance charts and graphs

## **📊 Current Status**

### **✅ Completed:**
- User authentication system
- Student/Teacher profiles
- Marks entry and calculation
- Basic financial management
- Messaging system
- Performance analytics
- Admin interface with Unfold
- Responsive frontend design
- Sample data population

### **🔄 In Progress:**
- Advanced analytics features
- M-Pesa production integration
- Report generation system
- Bulk operations
- Export functionalities

### **📋 Todo/Planned:**
- Attendance tracking system
- Exam scheduling
- Library management
- Inventory management
- Parent portal
- Mobile app
- API for third-party integrations

## **⚡ Production Scaling Guide**

### **Phase 1: Immediate Production Deployment**

#### **1. Database Migration:**
```bash
# Switch from SQLite to PostgreSQL
pip install psycopg2-binary

# Update settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'school_db',
        'USER': 'school_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

#### **2. Security Enhancements:**
```python
# In settings.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# HTTPS settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Production secret key
SECRET_KEY = os.getenv('SECRET_KEY', 'generate-strong-key-here')
```

#### **3. Static Files & Media:**
```python
# Use WhiteNoise for static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# In production, use CDN or S3
# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = 'school-system-bucket'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

### **Phase 2: Performance Optimization**

#### **1. Caching:**
```python
# Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session engine
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

#### **2. Database Optimization:**
```python
# Add database indexes
class Meta:
    indexes = [
        models.Index(fields=['student', 'term']),
        models.Index(fields=['created_at']),
    ]

# Use database connection pooling
DATABASE_POOL_CLASS = 'sqlalchemy.pool.QueuePool'
```

#### **3. Async Tasks (Celery):**
```bash
# Install Celery
pip install celery redis

# Create celery.py
# Configure for background tasks:
# - Email sending
# - Report generation
# - Payment processing
# - Notification delivery
```

### **Phase 3: Scalability Enhancements**

#### **1. Load Balancing:**
```nginx
# Nginx configuration for load balancing
upstream school_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://school_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### **2. Database Sharding Strategy:**
```python
# Student data by year/school
# Payments by term/year
# Messages by user groups
```

#### **3. Microservices Architecture (Future):**
```
┌─────────────────────────────────────────────────────┐
│               API Gateway                           │
├─────────────────────────────────────────────────────┤
│  Auth Service  │  Academic Service │  Finance Service│
│  User Service  │  Messaging Service│  Analytics Service│
└─────────────────────────────────────────────────────┘
```

### **Phase 4: Monitoring & Maintenance**

#### **1. Monitoring Setup:**
```bash
# Install monitoring tools
pip install django-debug-toolbar
pip install sentry-sdk

# Configure Sentry for error tracking
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()]
)
```

#### **2. Backup Strategy:**
```bash
# Automated database backups
0 2 * * * pg_dump school_db > /backups/school_$(date +\%Y\%m\%d).sql

# Media files backup to S3/Cloud Storage
0 3 * * * aws s3 sync /media s3://backup-bucket/media/
```

#### **3. Logging Configuration:**
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
```

### **Phase 5: Advanced Features**

#### **1. Mobile Application:**
```bash
# Use Django REST Framework for API
pip install djangorestframework
pip install django-cors-headers

# Create mobile API endpoints
# Use React Native/Flutter for mobile app
```

#### **2. Advanced Analytics:**
```python
# Machine learning for predictive analytics
pip install scikit-learn pandas

# Features:
# - Dropout prediction
# - Performance forecasting
# - Resource optimization
```

#### **3. Integration Ecosystem:**
```
Integrations to add:
- SMS Gateway (Twilio, Africa's Talking)
- Email Service (SendGrid, Mailgun)
- Government Education Portal APIs
- Payment Gateways (Stripe, PayPal)
- Cloud Storage (AWS S3, Google Cloud)
- Calendar Integration (Google Calendar)
```

## **📈 Performance Metrics to Track**

1. **System Metrics:**
   - Response time (< 200ms)
   - Uptime (> 99.9%)
   - Concurrent users support
   - Database query performance

2. **Business Metrics:**
   - Student enrollment rate
   - Payment collection rate
   - Teacher-student ratio
   - System adoption rate

3. **User Metrics:**
   - Login frequency
   - Feature usage patterns
   - Support tickets
   - User satisfaction

## **🔧 Deployment Checklist**

### **Pre-Deployment:**
- [ ] Database migrated to PostgreSQL
- [ ] Environment variables configured
- [ ] SSL certificate installed
- [ ] Backup system in place
- [ ] Monitoring tools configured
- [ ] Load testing completed

### **Post-Deployment:**
- [ ] Regular security audits
- [ ] Performance monitoring
- [ ] User training conducted
- [ ] Support system established
- [ ] Regular updates scheduled

## **🎯 Success Indicators**

1. **Technical Success:**
   - System handles 1000+ concurrent users
   - 99.9% uptime
   - < 2 second page load times

2. **Business Success:**
   - 80%+ user adoption rate
   - 30% reduction in administrative tasks
   - Improved student performance tracking
   - Faster payment processing

3. **User Success:**
   - High satisfaction scores
   - Reduced manual errors
   - Improved communication
   - Easy access to information

## **🚨 Emergency Procedures**

1. **Database Recovery:**
   ```bash
   # Restore from backup
   psql school_db < backup_file.sql
   
   # Point-in-time recovery
   pg_restore --dbname=school_db backup_file.dump
   ```

2. **Rollback Procedure:**
   ```bash
   # Git-based rollback
   git checkout previous-stable-tag
   python manage.py migrate
   ```

3. **Disaster Recovery:**
   - Hot standby database
   - Geographic redundancy
   - Automated failover

## **💡 Pro Tips for Scaling**

1. **Start with:** PostgreSQL + Gunicorn + Nginx
2. **Add caching early:** Redis for sessions and frequently accessed data
3. **Use CDN:** For static assets to reduce server load
4. **Implement queueing:** Celery for background tasks
5. **Monitor everything:** Set up alerts for critical metrics
6. **Regular backups:** Automated and tested recovery procedures
7. **Security first:** Regular updates and security patches
8. **Document everything:** Especially custom business logic

This system is production-ready with the current features and can scale to support thousands of users with proper infrastructure planning. The modular design allows for easy addition of new features and integration with external systems.