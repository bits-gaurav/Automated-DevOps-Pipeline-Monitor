from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class BuildSummary(BaseModel):
    """Summary information for a build"""
    id: int
    run_number: int
    name: str
    status: str
    conclusion: Optional[str]
    branch: str
    commit_sha: str
    commit_message: str
    author: str
    started_at: Optional[str]
    updated_at: Optional[str]
    duration_seconds: int
    url: str

class BuildStep(BaseModel):
    """Individual step within a job"""
    name: str
    status: str
    conclusion: Optional[str]
    number: int
    started_at: Optional[str]
    completed_at: Optional[str]

class BuildJob(BaseModel):
    """Job within a build"""
    id: int
    name: str
    status: str
    conclusion: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    runner_name: Optional[str]
    runner_group_name: Optional[str]
    steps: List[BuildStep]
    url: str

class CommitInfo(BaseModel):
    """Commit information"""
    sha: str
    message: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    timestamp: Optional[str]
    url: str

class BuildDetail(BaseModel):
    """Detailed build information"""
    id: int
    run_number: int
    name: str
    status: str
    conclusion: Optional[str]
    branch: str
    event: str
    workflow_id: int
    jobs: List[BuildJob]
    commit: CommitInfo
    started_at: Optional[str]
    updated_at: Optional[str]
    duration_seconds: int
    url: str
    cancel_url: Optional[str]
    rerun_url: Optional[str]
    logs_url: str

class PaginatedBuilds(BaseModel):
    """Paginated builds response"""
    builds: List[BuildSummary]
    page: int
    per_page: int
    total_count: int
    has_next: bool
    timestamp: str

class LogEntry(BaseModel):
    """Individual log entry"""
    timestamp: Optional[str]
    level: str
    step: Optional[str]
    message: str

class BuildLog(BaseModel):
    """Build logs response"""
    build_id: int
    job_id: int
    logs: List[LogEntry]
    total_lines: int
    timestamp: str
