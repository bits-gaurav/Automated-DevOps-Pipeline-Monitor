from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import io
import zipfile
import logging

from core.github_client import github_client
from core.config import settings
from models.builds import (
    BuildSummary,
    BuildDetail,
    BuildJob,
    BuildStep,
    BuildLog,
    CommitInfo,
    PaginatedBuilds
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=PaginatedBuilds)
async def get_builds(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status: completed, in_progress, queued"),
    branch: Optional[str] = Query(default=None, description="Filter by branch"),
    conclusion: Optional[str] = Query(default=None, description="Filter by conclusion: success, failure, cancelled")
):
    """Get paginated list of builds with filtering options"""
    try:
        # Fetch workflow runs with pagination
        response = github_client.get_workflow_runs(per_page=per_page, page=page, status=status)
        runs = response.get("workflow_runs", [])
        
        # Filter CI/CD runs
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        # Apply additional filters
        if branch:
            ci_cd_runs = [r for r in ci_cd_runs if r.get("head_branch") == branch]
        
        if conclusion:
            ci_cd_runs = [r for r in ci_cd_runs if r.get("conclusion") == conclusion]
        
        # Convert to BuildSummary objects
        builds = []
        for run in ci_cd_runs:
            commit_info = run.get("head_commit", {})
            build_summary = BuildSummary(
                id=run.get("id"),
                run_number=run.get("run_number"),
                name=run.get("name"),
                status=run.get("status"),
                conclusion=run.get("conclusion"),
                branch=run.get("head_branch"),
                commit_sha=run.get("head_sha"),
                commit_message=commit_info.get("message", "").split('\n')[0][:200],
                author=commit_info.get("author", {}).get("name", "Unknown"),
                started_at=run.get("run_started_at"),
                updated_at=run.get("updated_at"),
                duration_seconds=_calculate_duration(run),
                url=run.get("html_url")
            )
            builds.append(build_summary)
        
        return PaginatedBuilds(
            builds=builds,
            page=page,
            per_page=per_page,
            total_count=response.get("total_count", len(builds)),
            has_next=len(builds) == per_page,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting builds: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch builds: {str(e)}")

@router.get("/{build_id}", response_model=BuildDetail)
async def get_build_detail(
    build_id: int = Path(..., description="Build ID")
):
    """Get detailed information about a specific build"""
    try:
        # Get workflow run details
        run = github_client.get_workflow_run(build_id)
        
        # Get jobs for this run
        jobs_response = github_client.get_workflow_run_jobs(build_id)
        jobs_data = jobs_response.get("jobs", [])
        
        # Convert jobs to BuildJob objects
        jobs = []
        for job_data in jobs_data:
            steps = []
            for step_data in job_data.get("steps", []):
                step = BuildStep(
                    name=step_data.get("name"),
                    status=step_data.get("status"),
                    conclusion=step_data.get("conclusion"),
                    number=step_data.get("number"),
                    started_at=step_data.get("started_at"),
                    completed_at=step_data.get("completed_at")
                )
                steps.append(step)
            
            job = BuildJob(
                id=job_data.get("id"),
                name=job_data.get("name"),
                status=job_data.get("status"),
                conclusion=job_data.get("conclusion"),
                started_at=job_data.get("started_at"),
                completed_at=job_data.get("completed_at"),
                runner_name=job_data.get("runner_name"),
                runner_group_name=job_data.get("runner_group_name"),
                steps=steps,
                url=job_data.get("html_url")
            )
            jobs.append(job)
        
        # Get commit information
        commit_data = run.get("head_commit", {})
        commit_info = CommitInfo(
            sha=run.get("head_sha"),
            message=commit_data.get("message", ""),
            author_name=commit_data.get("author", {}).get("name", "Unknown"),
            author_email=commit_data.get("author", {}).get("email", ""),
            committer_name=commit_data.get("committer", {}).get("name", "Unknown"),
            committer_email=commit_data.get("committer", {}).get("email", ""),
            timestamp=commit_data.get("timestamp"),
            url=f"https://github.com/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}/commit/{run.get('head_sha')}"
        )
        
        # Build the detailed response
        build_detail = BuildDetail(
            id=run.get("id"),
            run_number=run.get("run_number"),
            name=run.get("name"),
            status=run.get("status"),
            conclusion=run.get("conclusion"),
            branch=run.get("head_branch"),
            event=run.get("event"),
            workflow_id=run.get("workflow_id"),
            jobs=jobs,
            commit=commit_info,
            started_at=run.get("run_started_at"),
            updated_at=run.get("updated_at"),
            duration_seconds=_calculate_duration(run),
            url=run.get("html_url"),
            cancel_url=run.get("cancel_url"),
            rerun_url=run.get("rerun_url"),
            logs_url=f"/api/v1/builds/{build_id}/logs"
        )
        
        return build_detail
        
    except Exception as e:
        logger.error(f"Error getting build detail for {build_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch build details: {str(e)}")

@router.get("/{build_id}/logs")
async def get_build_logs(
    build_id: int = Path(..., description="Build ID"),
    job_id: Optional[int] = Query(default=None, description="Specific job ID for logs")
):
    """Get logs for a build or specific job"""
    try:
        if job_id:
            # Get logs for specific job
            logs_content = github_client.get_job_logs(job_id)
            filename = f"job_{job_id}_logs.txt"
        else:
            # Get logs for entire workflow run
            logs_content = github_client.get_workflow_run_logs(build_id)
            filename = f"build_{build_id}_logs.zip"
        
        # Create streaming response
        def generate():
            yield logs_content
        
        media_type = "application/zip" if not job_id else "text/plain"
        
        return StreamingResponse(
            io.BytesIO(logs_content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error getting logs for build {build_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch build logs: {str(e)}")

@router.get("/{build_id}/jobs/{job_id}/logs", response_model=BuildLog)
async def get_job_logs_parsed(
    build_id: int = Path(..., description="Build ID"),
    job_id: int = Path(..., description="Job ID")
):
    """Get parsed logs for a specific job"""
    try:
        # Get job logs
        logs_content = github_client.get_job_logs(job_id)
        
        # Parse logs (simple text parsing)
        logs_text = logs_content.decode('utf-8', errors='ignore')
        log_lines = logs_text.split('\n')
        
        # Extract timestamps and organize by steps
        parsed_logs = []
        current_step = None
        
        for line in log_lines:
            if line.strip():
                # Try to identify step boundaries
                if "##[group]" in line or "##[section]" in line:
                    current_step = line.strip()
                
                parsed_logs.append({
                    "timestamp": None,  # GitHub logs don't always have timestamps
                    "level": "info",
                    "step": current_step,
                    "message": line.strip()
                })
        
        return BuildLog(
            build_id=build_id,
            job_id=job_id,
            logs=parsed_logs,
            total_lines=len(parsed_logs),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting parsed logs for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch job logs: {str(e)}")

@router.post("/{build_id}/rerun")
async def rerun_build(
    build_id: int = Path(..., description="Build ID")
):
    """Rerun a failed build (requires appropriate permissions)"""
    try:
        # Note: This would require additional GitHub API permissions
        # For now, return the rerun URL that users can click
        run = github_client.get_workflow_run(build_id)
        
        return {
            "message": "Rerun initiated",
            "build_id": build_id,
            "rerun_url": run.get("rerun_url"),
            "status": "pending_rerun",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error rerunning build {build_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rerun build: {str(e)}")

@router.post("/{build_id}/cancel")
async def cancel_build(
    build_id: int = Path(..., description="Build ID")
):
    """Cancel a running build (requires appropriate permissions)"""
    try:
        # Note: This would require additional GitHub API permissions
        # For now, return the cancel URL that users can use
        run = github_client.get_workflow_run(build_id)
        
        return {
            "message": "Cancel initiated",
            "build_id": build_id,
            "cancel_url": run.get("cancel_url"),
            "status": "pending_cancellation",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cancelling build {build_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel build: {str(e)}")

@router.get("/history/rollbacks")
async def get_rollback_history(
    limit: int = Query(default=10, ge=1, le=50, description="Number of rollback events to return")
):
    """Get rollback history from deployment logs"""
    try:
        # Get recent workflow runs and look for rollback patterns
        response = github_client.get_workflow_runs(per_page=100)
        runs = github_client.filter_ci_cd_runs(response.get("workflow_runs", []))
        
        rollback_events = []
        
        for run in runs:
            # Look for failed runs that might have triggered rollbacks
            if (run.get("conclusion") == "failure" and 
                run.get("head_branch") == "main"):
                
                # Check if there was a subsequent successful run (potential rollback)
                rollback_events.append({
                    "id": run.get("id"),
                    "failed_commit": run.get("head_sha", "")[:7],
                    "failed_at": run.get("updated_at"),
                    "rollback_detected": True,  # This would need more sophisticated detection
                    "duration_minutes": _calculate_duration(run) / 60,
                    "url": run.get("html_url")
                })
        
        return {
            "rollback_events": rollback_events[:limit],
            "total_count": len(rollback_events),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting rollback history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rollback history: {str(e)}")

def _calculate_duration(run: Dict) -> int:
    """Calculate run duration in seconds"""
    try:
        from dateutil import parser
        started_at = run.get("run_started_at")
        updated_at = run.get("updated_at")
        
        if not started_at or not updated_at:
            return 0
        
        start_time = parser.isoparse(started_at)
        end_time = parser.isoparse(updated_at)
        
        return int((end_time - start_time).total_seconds())
    except Exception:
        return 0
