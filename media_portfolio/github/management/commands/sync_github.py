import requests
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

# Fix imports - use full path with the project name prefix
from media_portfolio.github.models import GitHubRepo, GitHubSyncLog
from media_portfolio.projects.models import Project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync GitHub repositories and update project stats'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='GitHub username')
        parser.add_argument('--token', type=str, help='GitHub API token (for higher rate limits)')

    def handle(self, *args, **options):
        username = options['username']
        token = options.get('token')
        
        self.stdout.write(f"Syncing GitHub repositories for {username}...")
        
        sync_log = GitHubSyncLog.objects.create(status='in_progress')
        
        try:
            repos = self.fetch_github_repos(username, token)
            
            created_count = 0
            updated_count = 0
            
            for repo_data in repos:
                # Skip forks if desired
                if repo_data.get('fork'):
                    continue
                
                # Create or update repo record
                repo, created = GitHubRepo.objects.update_or_create(
                    full_name=repo_data['full_name'],
                    defaults={
                        'name': repo_data['name'],
                        'description': repo_data['description'] or '',
                        'html_url': repo_data['html_url'],
                        'clone_url': repo_data['clone_url'],
                        'homepage': repo_data['homepage'] or '',
                        'stars_count': repo_data['stargazers_count'],
                        'forks_count': repo_data['forks_count'],
                        'watchers_count': repo_data['watchers_count'],
                        'open_issues_count': repo_data['open_issues_count'],
                        'primary_language': repo_data['language'] or '',
                        'created_at_github': datetime.fromisoformat(repo_data['created_at'].replace('Z', '+00:00')),
                        'updated_at_github': datetime.fromisoformat(repo_data['updated_at'].replace('Z', '+00:00')),
                        'pushed_at_github': datetime.fromisoformat(repo_data['pushed_at'].replace('Z', '+00:00')),
                    }
                )
                
                # Fetch languages
                if repo_data.get('languages_url'):
                    languages = self.fetch_languages(repo_data['languages_url'], token)
                    repo.languages = languages
                    repo.save(update_fields=['languages'])
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
                # Update related project
                self.update_project_from_repo(repo_data)
            
            sync_log.repos_created = created_count
            sync_log.repos_updated = updated_count
            sync_log.status = 'success'
            sync_log.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully synced {created_count} new repos, updated {updated_count} repos"
            ))
            
        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            
            self.stdout.write(self.style.ERROR(f"Error syncing repos: {str(e)}"))

    def fetch_github_repos(self, username, token=None):
        """Fetch repositories from GitHub API"""
        url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
        
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        
        all_repos = []
        page = 1
        
        while True:
            try:
                response = requests.get(f"{url}&page={page}", headers=headers, timeout=30)
                response.raise_for_status()
                
                repos = response.json()
                if not repos:
                    break
                
                all_repos.extend(repos)
                page += 1
            except Exception as e:
                logger.error(f"Error fetching page {page}: {str(e)}")
                break
        
        return all_repos

    def fetch_languages(self, languages_url, token=None):
        """Fetch languages for a repository"""
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        
        try:
            response = requests.get(languages_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching languages: {str(e)}")
            return {}

    def update_project_from_repo(self, repo_data):
        """Update project stats from GitHub data"""
        # Try to find project by GitHub URL
        projects = Project.objects.filter(github_url__icontains=repo_data['full_name'])
        
        for project in projects:
            project.stars_count = repo_data['stargazers_count']
            project.forks_count = repo_data['forks_count']
            project.last_github_sync = timezone.now()
            
            # Update technical stack if empty
            if not project.technical_stack and repo_data.get('language'):
                project.technical_stack = [repo_data['language']]
            
            project.save(update_fields=['stars_count', 'forks_count', 'last_github_sync', 'technical_stack'])
            
            logger.info(f"Updated project {project.title} with GitHub stats")