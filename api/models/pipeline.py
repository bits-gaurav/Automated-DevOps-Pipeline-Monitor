from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QueueStatus(BaseModel):
    """Queue status information"""
    queued_count: int
    running_count: int
    estimated_wait_time: int  # in minutes

class RecentDeployment(BaseModel):
    """Recent deployment information"""
    id: int
    commit_sha: str
    commit_message: str
    author: str
    deployed_at: str
    status: str
    duration_seconds: int

class PipelineOverview(BaseModel):
    """Comprehensive pipeline overview"""
    status: str  # idle, running, success, failed, cancelled
    success_rate: float
    failure_rate: float
    queue_status: QueueStatus
    recent_deployments: List[RecentDeployment]
    current_build: Optional[Dict[str, Any]]
    total_runs_analyzed: int
    timestamp: str

class PipelineStatus(BaseModel):
    """Detailed pipeline status"""
    overall_status: str
    running_jobs: int
    queued_jobs: int
    last_run_status: Optional[Dict[str, Any]]
    active_branches: List[str]
    timestamp: str

class PipelineMetrics(BaseModel):
    """Pipeline performance metrics"""
    total_runs: int
    success_count: int
    failure_count: int
    success_rate: float
    average_duration_minutes: float
    fastest_build_minutes: float
    slowest_build_minutes: float
    builds_per_day: float
    timestamp: str
