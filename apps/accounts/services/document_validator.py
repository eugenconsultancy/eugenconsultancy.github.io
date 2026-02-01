import hashlib
import magic
import os
from typing import Dict, Tuple, Optional
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class DocumentValidator:
    """Service for validating and processing writer documents."""
    
    # Whitelist of allowed MIME types
    ALLOWED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'application/msword': ['.doc'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    }
    
    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
    
    @classmethod
    def validate_file(cls, file_obj) -> Dict:
        """
        Validate uploaded document file.
        
        Args:
            file_obj: Django UploadedFile object
            
        Returns:
            Dict containing validation results and file metadata
            
        Raises:
            ValidationError: If file fails validation
        """
        # Get file size
        file_size = file_obj.size
        
        # Validate file size
        if file_size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                _('File size exceeds maximum allowed size of 10MB.')
            )
        
        if file_size == 0:
            raise ValidationError(_('File is empty.'))
        
        # Read first 2048 bytes for MIME type detection
        file_content = file_obj.read(2048)
        file_obj.seek(0)  # Reset file pointer
        
        # Detect MIME type
        mime_type = magic.from_buffer(file_content, mime=True)
        
        # Validate MIME type
        if mime_type not in cls.ALLOWED_MIME_TYPES:
            raise ValidationError(
                _('File type not allowed. Allowed types: PDF, JPG, PNG, DOC, DOCX.')
            )
        
        # Validate file extension
        filename = file_obj.name.lower()
        allowed_extensions = cls.ALLOWED_MIME_TYPES[mime_type]
        
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise ValidationError(
                _('File extension does not match detected MIME type.')
            )
        
        # Generate file hash
        file_hash = cls._generate_file_hash(file_obj)
        
        return {
            'mime_type': mime_type,
            'file_size': file_size,
            'file_hash': file_hash,
            'original_filename': file_obj.name,
            'is_valid': True,
        }
    
    @classmethod
    def _generate_file_hash(cls, file_obj) -> str:
        """Generate SHA-256 hash of file content."""
        sha256_hash = hashlib.sha256()
        
        # Read file in chunks for memory efficiency
        for chunk in iter(lambda: file_obj.read(4096), b''):
            sha256_hash.update(chunk)
        
        file_obj.seek(0)  # Reset file pointer
        return sha256_hash.hexdigest()
    
    @classmethod
    def virus_scan_file(cls, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Scan file for viruses using ClamAV.
        
        Args:
            file_path: Path to the file to scan
            
        Returns:
            Tuple of (is_clean, scan_result_message)
        """
        try:
            import pyclamd
            
            # Initialize ClamAV connection
            cd = pyclamd.ClamdAgnostic()
            
            # Test connection
            if not cd.ping():
                return False, "ClamAV daemon not reachable"
            
            # Scan file
            scan_result = cd.scan_file(file_path)
            
            if scan_result is None:
                return True, "File is clean"
            else:
                # File is infected
                virus_name = scan_result.get(file_path, {}).get('reason', 'Unknown virus')
                return False, f"Virus detected: {virus_name}"
                
        except ImportError:
            # ClamAV not installed, log warning but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("ClamAV not installed. Skipping virus scan.")
            return True, "Virus scan skipped (ClamAV not configured)"
        
        except Exception as e:
            # Log error but don't block file upload
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Virus scan failed: {str(e)}")
            return False, f"Scan failed: {str(e)}"
    
    @classmethod
    def is_safe_filename(cls, filename: str) -> bool:
        """
        Check if filename is safe (no path traversal attempts).
        
        Args:
            filename: Original filename
            
        Returns:
            True if filename is safe
        """
        # Normalize path
        normalized = os.path.normpath(filename)
        
        # Check for path traversal
        if normalized.startswith('..') or '\\' in normalized or '//' in normalized:
            return False
        
        # Check for null bytes
        if '\x00' in filename:
            return False
        
        # Check for directory traversal in filename
        if '/' in filename or '\\' in filename:
            return False
        
        return True
    
    @classmethod
    def get_allowed_extensions(cls) -> list:
        """Get list of allowed file extensions."""
        extensions = []
        for mime_exts in cls.ALLOWED_MIME_TYPES.values():
            extensions.extend(mime_exts)
        return list(set(extensions))