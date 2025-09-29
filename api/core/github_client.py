import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from dateutil import parser
import logging

from core.config import settings

logger = logging.getLogger(__name__)

class GitHubClient:
    """GitHub API client for fetching workflow and repository data"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.repo_url = f"{self.base_url}/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}"
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to GitHub API"""
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    def get_workflow_runs(self, per_page: int = 50, page: int = 1, status: Optional[str] = None) -> Dict:
        """Get workflow runs with pagination"""
        params = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        
        url = f"{self.repo_url}/actions/runs"
        return self._make_request(url, params)
    
    def get_workflow_run(self, run_id: int) -> Dict:
        """Get specific workflow run details"""
        url = f"{self.repo_url}/actions/runs/{run_id}"
        return self._make_request(url)
    
    def get_workflow_run_jobs(self, run_id: int) -> Dict:
        """Get jobs for a specific workflow run"""
        url = f"{self.repo_url}/actions/runs/{run_id}/jobs"
        return self._make_request(url)
    
    def get_workflow_run_logs(self, run_id: int) -> bytes:
        """Get logs for a specific workflow run"""
        url = f"{self.repo_url}/actions/runs/{run_id}/logs"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch logs for run {run_id}: {e}")
            raise
    
    def get_job_logs(self, job_id: int) -> bytes:
        """Get logs for a specific job"""
        url = f"{self.repo_url}/actions/jobs/{job_id}/logs"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch logs for job {job_id}: {e}")
            raise
    
    def get_workflows(self) -> Dict:
        """Get all workflows in the repository"""
        url = f"{self.repo_url}/actions/workflows"
        return self._make_request(url)
    
    def get_workflow(self, workflow_id: int) -> Dict:
        """Get specific workflow details"""
        url = f"{self.repo_url}/actions/workflows/{workflow_id}"
        return self._make_request(url)
    
    def get_repository_info(self) -> Dict:
        """Get repository information"""
        return self._make_request(self.repo_url)
    
    def get_commits(self, per_page: int = 30, page: int = 1, since: Optional[str] = None) -> List[Dict]:
        """Get repository commits"""
        params = {"per_page": per_page, "page": page}
        if since:
            params["since"] = since
        
        url = f"{self.repo_url}/commits"
        response = self._make_request(url, params)
        return response if isinstance(response, list) else response.get("commits", [])
    
    def get_commit(self, sha: str) -> Dict:
        """Get specific commit details"""
        url = f"{self.repo_url}/commits/{sha}"
        return self._make_request(url)
    
    def get_branches(self) -> List[Dict]:
        """Get repository branches"""
        url = f"{self.repo_url}/branches"
        return self._make_request(url)
    
    def get_pull_requests(self, state: str = "all", per_page: int = 30) -> List[Dict]:
        """Get pull requests"""
        params = {"state": state, "per_page": per_page}
        url = f"{self.repo_url}/pulls"
        return self._make_request(url, params)
    
    def filter_ci_cd_runs(self, runs: List[Dict], exclude_monitor: bool = True) -> List[Dict]:
        """Filter runs to exclude monitor workflows and other non-CI/CD workflows"""
        filtered_runs = []
        
        for run in runs:
            workflow_name = run.get("name", "").lower()
            
            # Skip monitor workflows if requested
            if exclude_monitor and any(keyword in workflow_name for keyword in ["monitor", "analytics"]):
                continue
            
            filtered_runs.append(run)
        
        return filtered_runs
    
    def get_recent_runs(self, lookback_minutes: int = 60, exclude_monitor: bool = True) -> List[Dict]:
        """Get recent workflow runs within the specified lookback period"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        
        # Fetch multiple pages to ensure we get enough recent runs
        all_runs = []
        page = 1
        
        while page <= 5:  # Limit to 5 pages to avoid excessive API calls
            response = self.get_workflow_runs(per_page=100, page=page)
            runs = response.get("workflow_runs", [])
            
            if not runs:
                break
            
            # Filter by time
            recent_runs = []
            for run in runs:
                updated_at = run.get("updated_at")
                if updated_at:
                    try:
                        run_time = parser.isoparse(updated_at)
                        if run_time >= cutoff_time:
                            recent_runs.append(run)
                    except Exception:
                        continue
            
            all_runs.extend(recent_runs)
            
            # If we got fewer runs than requested, we've reached the end
            if len(runs) < 100:
                break
            
            page += 1
        
        # Filter CI/CD runs
        if exclude_monitor:
            all_runs = self.filter_ci_cd_runs(all_runs, exclude_monitor=True)
        
        return all_runs

# Global GitHub client instance
github_client = GitHubClient()
