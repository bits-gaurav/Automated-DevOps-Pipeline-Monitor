from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dateutil import parser
import logging

from core.github_client import github_client
from core.config import settings
from models.pipeline import (
    PipelineOverview, 
    PipelineStatus, 
    QueueStatus, 
    RecentDeployment,
    PipelineMetrics
)

logger = logging.getLogger(__name__)
router = APIRouter()

def calculate_success_rate(runs: List[Dict]) -> float:
    """Calculate success rate from workflow runs"""
    if not runs:
        return 0.0
    
    completed_runs = [r for r in runs if r.get("status") == "completed"]
    if not completed_runs:
        return 0.0
    
    successful_runs = [r for r in completed_runs if r.get("conclusion") == "success"]
    return round((len(successful_runs) / len(completed_runs)) * 100, 2)

def get_pipeline_status(runs: List[Dict]) -> str:
    """Determine overall pipeline status"""
    if not runs:
        return "idle"
    
    # Check for any running workflows
    running_runs = [r for r in runs if r.get("status") in ["in_progress", "queued"]]
    if running_runs:
        return "running"
    
    # Check most recent completed run
    completed_runs = [r for r in runs if r.get("status") == "completed"]
    if completed_runs:
        # Sort by updated_at to get most recent
        completed_runs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        latest_run = completed_runs[0]
        
        conclusion = latest_run.get("conclusion")
        if conclusion == "success":
            return "success"
        elif conclusion in ["failure", "timed_out"]:
            return "failed"
        elif conclusion == "cancelled":
            return "cancelled"
    
    return "idle"

@router.get("/overview", response_model=PipelineOverview)
async def get_pipeline_overview(
    lookback_minutes: int = Query(default=60, ge=1, le=1440, description="Lookback period in minutes")
):
    """Get comprehensive pipeline overview with live status and metrics"""
    try:
        # Get recent workflow runs
        recent_runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        
        # Get all recent runs for queue analysis (including in-progress)
        all_recent_response = github_client.get_workflow_runs(per_page=50)
        all_runs = all_recent_response.get("workflow_runs", [])
        
        # Filter CI/CD runs
        ci_cd_runs = github_client.filter_ci_cd_runs(recent_runs)
        all_ci_cd_runs = github_client.filter_ci_cd_runs(all_runs)
        
        # Calculate metrics
        success_rate = calculate_success_rate(ci_cd_runs)
        failure_rate = 100 - success_rate if ci_cd_runs else 0
        
        # Get pipeline status
        status = get_pipeline_status(all_ci_cd_runs[:10])  # Use recent 10 runs for status
        
        # Queue analysis
        queued_runs = [r for r in all_ci_cd_runs if r.get("status") == "queued"]
        in_progress_runs = [r for r in all_ci_cd_runs if r.get("status") == "in_progress"]
        
        queue_status = QueueStatus(
            queued_count=len(queued_runs),
            running_count=len(in_progress_runs),
            estimated_wait_time=len(queued_runs) * 5  # Rough estimate: 5 min per queued job
        )
        
        # Recent deployments (successful runs on main branch)
        deployment_runs = [
            r for r in ci_cd_runs 
            if r.get("conclusion") == "success" 
            and r.get("head_branch") == "main"
        ][:5]
        
        recent_deployments = []
        for run in deployment_runs:
            commit_info = run.get("head_commit", {})
            recent_deployments.append(RecentDeployment(
                id=run.get("id"),
                commit_sha=run.get("head_sha", "")[:7],
                commit_message=commit_info.get("message", "").split('\n')[0][:100],
                author=commit_info.get("author", {}).get("name", "Unknown"),
                deployed_at=run.get("updated_at"),
                status="success",
                duration_seconds=_calculate_duration(run)
            ))
        
        # Build current status info
        current_build = None
        if in_progress_runs:
            latest_run = in_progress_runs[0]
            current_build = {
                "id": latest_run.get("id"),
                "name": latest_run.get("name"),
                "status": latest_run.get("status"),
                "branch": latest_run.get("head_branch"),
                "commit_sha": latest_run.get("head_sha", "")[:7],
                "started_at": latest_run.get("run_started_at"),
                "url": latest_run.get("html_url")
            }
        
        return PipelineOverview(
            status=status,
            success_rate=success_rate,
            failure_rate=failure_rate,
            queue_status=queue_status,
            recent_deployments=recent_deployments,
            current_build=current_build,
            total_runs_analyzed=len(ci_cd_runs),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting pipeline overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pipeline overview: {str(e)}")

@router.get("/status", response_model=PipelineStatus)
async def get_pipeline_status_detailed():
    """Get detailed pipeline status with current running jobs"""
    try:
        # Get recent runs
        response = github_client.get_workflow_runs(per_page=20)
        runs = github_client.filter_ci_cd_runs(response.get("workflow_runs", []))
        
        # Analyze current state
        running_runs = [r for r in runs if r.get("status") == "in_progress"]
        queued_runs = [r for r in runs if r.get("status") == "queued"]
        
        # Get the most recent completed run for last status
        completed_runs = [r for r in runs if r.get("status") == "completed"]
        last_run_status = None
        if completed_runs:
            last_run = completed_runs[0]
            last_run_status = {
                "conclusion": last_run.get("conclusion"),
                "completed_at": last_run.get("updated_at"),
                "duration_seconds": _calculate_duration(last_run)
            }
        
        overall_status = get_pipeline_status(runs)
        
        return PipelineStatus(
            overall_status=overall_status,
            running_jobs=len(running_runs),
            queued_jobs=len(queued_runs),
            last_run_status=last_run_status,
            active_branches=[r.get("head_branch") for r in running_runs + queued_runs],
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pipeline status: {str(e)}")

@router.get("/metrics", response_model=PipelineMetrics)
async def get_pipeline_metrics(
    lookback_minutes: int = Query(default=1440, ge=60, le=10080, description="Lookback period in minutes")
):
    """Get pipeline performance metrics"""
    try:
        # Get runs within lookback period
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        # Filter completed runs for metrics
        completed_runs = [r for r in ci_cd_runs if r.get("status") == "completed"]
        
        if not completed_runs:
            return PipelineMetrics(
                total_runs=0,
                success_count=0,
                failure_count=0,
                success_rate=0.0,
                average_duration_minutes=0.0,
                fastest_build_minutes=0.0,
                slowest_build_minutes=0.0,
                builds_per_day=0.0,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Calculate metrics
        successful_runs = [r for r in completed_runs if r.get("conclusion") == "success"]
        failed_runs = [r for r in completed_runs if r.get("conclusion") in ["failure", "timed_out"]]
        
        # Duration calculations
        durations = []
        for run in completed_runs:
            duration = _calculate_duration(run)
            if duration > 0:
                durations.append(duration / 60.0)  # Convert to minutes
        
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        fastest_build = min(durations) if durations else 0.0
        slowest_build = max(durations) if durations else 0.0
        
        # Builds per day calculation
        days = lookback_minutes / (24 * 60)
        builds_per_day = len(completed_runs) / days if days > 0 else 0.0
        
        return PipelineMetrics(
            total_runs=len(completed_runs),
            success_count=len(successful_runs),
            failure_count=len(failed_runs),
            success_rate=calculate_success_rate(completed_runs),
            average_duration_minutes=round(avg_duration, 2),
            fastest_build_minutes=round(fastest_build, 2),
            slowest_build_minutes=round(slowest_build, 2),
            builds_per_day=round(builds_per_day, 2),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting pipeline metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pipeline metrics: {str(e)}")

@router.get("/recent")
async def get_recent_activity(
    limit: int = Query(default=10, ge=1, le=50, description="Number of recent activities to return")
):
    """Get recent pipeline activity"""
    try:
        response = github_client.get_workflow_runs(per_page=limit * 2)  # Get more to filter
        runs = github_client.filter_ci_cd_runs(response.get("workflow_runs", []))
        
        recent_activities = []
        for run in runs[:limit]:
            commit_info = run.get("head_commit", {})
            activity = {
                "id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "branch": run.get("head_branch"),
                "commit_sha": run.get("head_sha", "")[:7],
                "commit_message": commit_info.get("message", "").split('\n')[0][:100],
                "author": commit_info.get("author", {}).get("name", "Unknown"),
                "started_at": run.get("run_started_at"),
                "updated_at": run.get("updated_at"),
                "duration_seconds": _calculate_duration(run),
                "url": run.get("html_url")
            }
            recent_activities.append(activity)
        
        return {
            "activities": recent_activities,
            "total_count": len(recent_activities),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent activity: {str(e)}")

def _calculate_duration(run: Dict) -> int:
    """Calculate run duration in seconds"""
    try:
        started_at = run.get("run_started_at")
        updated_at = run.get("updated_at")
        
        if not started_at or not updated_at:
            return 0
        
        start_time = parser.isoparse(started_at)
        end_time = parser.isoparse(updated_at)
        
        return int((end_time - start_time).total_seconds())
    except Exception:
        return 0
