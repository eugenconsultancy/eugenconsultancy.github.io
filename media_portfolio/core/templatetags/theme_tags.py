from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def theme_class(context, light_class='light', dark_class='dark'):
    """
    Returns appropriate class based on theme preference
    Usage: {% theme_class 'bg-light' 'bg-dark' %}
    """
    request = context.get('request')
    if request and request.session.get('theme') == 'dark':
        return dark_class
    elif request and request.session.get('theme') == 'light':
        return light_class
    return ''  # System preference - handled by CSS


@register.simple_tag(takes_context=True)
def theme_attr(context, light_attr, dark_attr):
    """
    Returns appropriate attribute based on theme preference
    """
    request = context.get('request')
    if request and request.session.get('theme') == 'dark':
        return dark_attr
    elif request and request.session.get('theme') == 'light':
        return light_attr
    return ''


@register.inclusion_tag('core/theme_switcher.html', takes_context=True)
def theme_switcher(context):
    """
    Render theme switcher component
    """
    request = context.get('request')
    return {
        'current_theme': request.session.get('theme', 'system') if request else 'system',
    }


@register.filter
def theme_image(image_light, image_dark, theme='light'):
    """
    Returns appropriate image URL based on theme
    Usage: {{ image_light|theme_image:image_dark }}
    """
    return image_dark if theme == 'dark' else image_light


@register.simple_tag
def theme_styles():
    """
    Returns CSS for theme support
    """
    css = """
    <style>
        /* Light theme (default) */
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --border-color: #dee2e6;
            --link-color: #0d6efd;
            --link-hover: #0a58ca;
            --card-bg: #ffffff;
            --card-shadow: 0 4px 6px rgba(0,0,0,0.1);
            --navbar-bg: #f8f9fa;
            --footer-bg: #f8f9fa;
            --input-bg: #ffffff;
            --input-border: #ced4da;
            --btn-primary: #0d6efd;
            --btn-primary-hover: #0b5ed7;
        }

        /* Dark theme */
        [data-theme="dark"] {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --text-primary: #e9ecef;
            --text-secondary: #adb5bd;
            --border-color: #2d3748;
            --link-color: #9d4edd;
            --link-hover: #c77dff;
            --card-bg: #16213e;
            --card-shadow: 0 4px 20px rgba(106, 76, 156, 0.3);
            --navbar-bg: #0f3460;
            --footer-bg: #0f3460;
            --input-bg: #1a1a2e;
            --input-border: #2d3748;
            --btn-primary: #6a4c9c;
            --btn-primary-hover: #7d5fb0;
        }

        /* System preference detection */
        @media (prefers-color-scheme: dark) {
            :root:not([data-theme="light"]) {
                --bg-primary: #1a1a2e;
                --bg-secondary: #16213e;
                --text-primary: #e9ecef;
                --text-secondary: #adb5bd;
                --border-color: #2d3748;
                --link-color: #9d4edd;
                --link-hover: #c77dff;
                --card-bg: #16213e;
                --card-shadow: 0 4px 20px rgba(106, 76, 156, 0.3);
                --navbar-bg: #0f3460;
                --footer-bg: #0f3460;
                --input-bg: #1a1a2e;
                --input-border: #2d3748;
                --btn-primary: #6a4c9c;
                --btn-primary-hover: #7d5fb0;
            }
        }

        /* Apply variables */
        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        .navbar {
            background-color: var(--navbar-bg) !important;
            border-bottom: 1px solid var(--border-color);
        }

        .footer {
            background-color: var(--footer-bg) !important;
            border-top: 1px solid var(--border-color);
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            box-shadow: var(--card-shadow);
        }

        a {
            color: var(--link-color);
        }

        a:hover {
            color: var(--link-hover);
        }

        .btn-primary {
            background-color: var(--btn-primary);
            border-color: var(--btn-primary);
        }

        .btn-primary:hover {
            background-color: var(--btn-primary-hover);
            border-color: var(--btn-primary-hover);
        }

        .form-control, .form-select {
            background-color: var(--input-bg);
            border-color: var(--input-border);
            color: var(--text-primary);
        }

        .form-control:focus, .form-select:focus {
            background-color: var(--input-bg);
            color: var(--text-primary);
        }

        .text-muted {
            color: var(--text-secondary) !important;
        }

        hr {
            border-color: var(--border-color);
        }

        /* Smooth transitions */
        * {
            transition: background-color 0.3s ease, 
                        border-color 0.3s ease, 
                        box-shadow 0.3s ease,
                        color 0.3s ease;
        }
    </style>
    """
    return mark_safe(css)