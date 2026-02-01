#!/bin/bash

# EBWriting Platform Setup Script
# This script sets up the development environment

set -e

echo "🚀 Starting EBWriting Platform Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

print_status "Python is installed: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed. Please install pip."
    exit 1
fi

print_status "pip is installed: $(pip3 --version)"

# Check if Docker is installed (optional)
if command -v docker &> /dev/null; then
    print_status "Docker is installed: $(docker --version)"
else
    print_warning "Docker is not installed. Some features may not work."
fi

# Check if Docker Compose is installed (optional)
if command -v docker-compose &> /dev/null; then
    print_status "Docker Compose is installed: $(docker-compose --version)"
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install requirements
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env file..."
    cat > .env << 'EOF'
# Django Settings
DEBUG=True
SECRET_KEY=django-insecure-dev-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=ebwriting_dev
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Email (Development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=587
EMAIL_USE_TLS=True

# Security
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False

# Platform Settings
PLATFORM_FEE_PERCENTAGE=20
ESCROW_HOLD_PERIOD=7
MAX_REVISION_COUNT=3
WRITER_APPROVAL_REQUIRED=True

# File Upload
MAX_FILE_SIZE_MB=10
ALLOWED_FILE_TYPES=pdf,jpg,jpeg,png,doc,docx

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# AWS S3 (optional - for production)
USE_S3=False
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=

# ClamAV (optional - for virus scanning)
ENABLE_VIRUS_SCAN=False
CLAMAV_HOST=localhost
CLAMAV_PORT=3310
EOF
    print_status ".env file created. Please review and update settings as needed."
else
    print_status ".env file already exists"
fi

# Create media directories
print_status "Creating media directories..."
mkdir -p media/writer_documents
mkdir -p media/order_files
mkdir -p media/generated_docs
mkdir -p media/profile_pictures
mkdir -p media/data_exports
mkdir -p logs

# Set permissions
chmod -R 755 media/
chmod -R 755 logs/

# Check if PostgreSQL is running
if command -v pg_isready &> /dev/null; then
    if pg_isready -q; then
        print_status "PostgreSQL is running"
    else
        print_warning "PostgreSQL is not running. Please start PostgreSQL before running migrations."
    fi
else
    print_warning "pg_isready not found. Cannot check PostgreSQL status."
fi

# Run migrations
print_status "Running database migrations..."
python manage.py migrate

# Create superuser if none exists
print_status "Checking for superuser..."
if ! python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(is_superuser=True).exists())" | grep -q "True"; then
    print_status "Creating superuser..."
    python manage.py createsuperuser
else
    print_status "Superuser already exists"
fi

# Setup permissions
print_status "Setting up default permissions..."
python manage.py setup_permissions

# Setup retention rules
print_status "Setting up data retention rules..."
python manage.py setup_retention_rules

# Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput

# Create initial data (optional)
print_status "Creating initial data..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()

# Create test client if not exists
if not User.objects.filter(email='client@example.com').exists():
    client = User.objects.create_user(
        email='client@example.com',
        password='testpass123',
        user_type='client',
        first_name='Test',
        last_name='Client',
        terms_accepted=True,
        privacy_policy_accepted=True
    )
    print('Test client created: client@example.com / testpass123')

# Create test writer if not exists
if not User.objects.filter(email='writer@example.com').exists():
    writer = User.objects.create_user(
        email='writer@example.com',
        password='testpass123',
        user_type='writer',
        first_name='Test',
        last_name='Writer',
        terms_accepted=True,
        privacy_policy_accepted=True
    )
    print('Test writer created: writer@example.com / testpass123')
"

print_status "🌐 Setup complete!"
echo ""
echo "================================================"
echo "          EBWriting Platform Ready!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Start the development server:"
echo "   python manage.py runserver"
echo ""
echo "2. Or use Docker Compose:"
echo "   docker-compose up -d"
echo ""
echo "3. Access the admin panel:"
echo "   http://localhost:8000/admin/"
echo ""
echo "Test credentials:"
echo "   Admin: Use the superuser you created"
echo "   Client: client@example.com / testpass123"
echo "   Writer: writer@example.com / testpass123"
echo ""
echo "For security, change the SECRET_KEY in .env for production!"
echo "================================================"