import requests
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.core.cache import cache
import feedparser  # Make sure to install: pip install feedparser

from media_portfolio.blog.models import BlogPost, BlogSyncLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync blog posts from Dev.to API'

    def add_arguments(self, parser):
        parser.add_argument('--source', type=str, default='devto', help='Source to sync (devto/medium)')
        parser.add_argument('--username', type=str, required=True, help='Username for the source')
        parser.add_argument('--limit', type=int, default=10, help='Number of posts to fetch')

    def handle(self, *args, **options):
        source = options['source']
        username = options['username']
        limit = options['limit']
        
        self.stdout.write(f"Syncing {source} posts for user {username}...")
        
        sync_log = BlogSyncLog.objects.create(
            source=source,
            status='in_progress'
        )
        
        try:
            if source == 'devto':
                posts_created, posts_updated = self.sync_devto(username, limit)
            elif source == 'medium':
                posts_created, posts_updated = self.sync_medium(username, limit)
            else:
                raise ValueError(f"Unsupported source: {source}")
            
            sync_log.posts_created = posts_created
            sync_log.posts_updated = posts_updated
            sync_log.status = 'success'
            sync_log.save()
            
            # Clear cache
            cache.delete('latest_blog_posts')
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully synced {posts_created} new posts, updated {posts_updated} posts"
            ))
            
        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            
            self.stdout.write(self.style.ERROR(f"Error syncing posts: {str(e)}"))

    def sync_devto(self, username, limit):
        """Sync posts from Dev.to API"""
        url = f"https://dev.to/api/articles?username={username}&per_page={limit}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            posts = response.json()
            created_count = 0
            updated_count = 0
            
            for post_data in posts:
                # Generate slug
                slug = slugify(post_data['title'])[:350]
                
                # Parse date
                published_at = datetime.fromisoformat(post_data['published_at'].replace('Z', '+00:00'))
                
                # Create or update
                post, created = BlogPost.objects.update_or_create(
                    external_id=str(post_data['id']),
                    defaults={
                        'title': post_data['title'],
                        'slug': slug,
                        'source': 'devto',
                        'external_url': post_data['url'],
                        'excerpt': post_data['description'] or '',
                        'cover_image': post_data['cover_image'] or '',
                        'author_name': post_data['user']['name'],
                        'published_at': published_at,
                        'read_time_minutes': post_data['reading_time_minutes'],
                        'reactions_count': post_data['positive_reactions_count'],
                        'comments_count': post_data['comments_count'],
                        'is_published': True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            return created_count, updated_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching from Dev.to: {str(e)}")
            raise

    def sync_medium(self, username, limit):
        """Sync posts from Medium RSS feed"""
        url = f"https://medium.com/feed/@{username}"
        
        try:
            feed = feedparser.parse(url)
            
            created_count = 0
            updated_count = 0
            
            for entry in feed.entries[:limit]:
                # Generate slug
                slug = slugify(entry.title)[:350]
                
                # Parse date
                published_at = datetime(*entry.published_parsed[:6])
                published_at = timezone.make_aware(published_at)
                
                # Extract cover image (if available)
                cover_image = ''
                if hasattr(entry, 'media_content') and entry.media_content:
                    cover_image = entry.media_content[0].get('url', '')
                
                # Create or update
                post, created = BlogPost.objects.update_or_create(
                    external_id=entry.id,
                    defaults={
                        'title': entry.title,
                        'slug': slug,
                        'source': 'medium',
                        'external_url': entry.link,
                        'excerpt': entry.get('summary', '')[:300],
                        'cover_image': cover_image,
                        'author_name': username,
                        'published_at': published_at,
                        'read_time_minutes': len(entry.get('content', [{'value': ''}])[0]['value'].split()) // 200,
                        'is_published': True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            return created_count, updated_count
            
        except Exception as e:
            logger.error(f"Error fetching from Medium: {str(e)}")
            raise