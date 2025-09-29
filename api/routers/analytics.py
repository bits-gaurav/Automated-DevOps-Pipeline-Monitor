from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dateutil import parser
import logging
from collections import defaultdict

from core.github_client import github_client
from core.config import settings
from models.analytics import (
    AnalyticsOverview,
    TrendData,
    MTTRAnalysis,
    PerformanceMetrics,
    WorkflowComparison,
    BuildTrends,
    FailureAnalysis,
    TimeSeriesData
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    lookback_days: int = Query(default=7, ge=1, le=30, description="Lookback period in days")
):
    """Get comprehensive analytics overview"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        # Filter completed runs for analysis
        completed_runs = [r for r in ci_cd_runs if r.get("status") == "completed"]
        
        if not completed_runs:
            return AnalyticsOverview(
                total_builds=0,
                success_rate=0.0,
                failure_rate=0.0,
                average_duration_minutes=0.0,
                mttr_minutes=0.0,
                builds_per_day=0.0,
                most_active_branch="",
                most_active_author="",
                period_days=lookback_days,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Basic metrics
        successful_runs = [r for r in completed_runs if r.get("conclusion") == "success"]
        failed_runs = [r for r in completed_runs if r.get("conclusion") in ["failure", "timed_out"]]
        
        success_rate = (len(successful_runs) / len(completed_runs)) * 100
        failure_rate = 100 - success_rate
        
        # Duration analysis
        durations = []
        for run in completed_runs:
            duration = _calculate_duration(run)
            if duration > 0:
                durations.append(duration / 60.0)  # Convert to minutes
        
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # MTTR calculation
        mttr = _calculate_mttr(completed_runs)
        
        # Activity analysis
        branch_counts = defaultdict(int)
        author_counts = defaultdict(int)
        
        for run in completed_runs:
            branch = run.get("head_branch", "unknown")
            branch_counts[branch] += 1
            
            commit_info = run.get("head_commit", {})
            author = commit_info.get("author", {}).get("name", "unknown")
            author_counts[author] += 1
        
        most_active_branch = max(branch_counts.items(), key=lambda x: x[1])[0] if branch_counts else ""
        most_active_author = max(author_counts.items(), key=lambda x: x[1])[0] if author_counts else ""
        
        builds_per_day = len(completed_runs) / lookback_days
        
        return AnalyticsOverview(
            total_builds=len(completed_runs),
            success_rate=round(success_rate, 2),
            failure_rate=round(failure_rate, 2),
            average_duration_minutes=round(avg_duration, 2),
            mttr_minutes=round(mttr, 2),
            builds_per_day=round(builds_per_day, 2),
            most_active_branch=most_active_branch,
            most_active_author=most_active_author,
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics overview: {str(e)}")

@router.get("/trends", response_model=BuildTrends)
async def get_build_trends(
    lookback_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days"),
    granularity: str = Query(default="daily", regex="^(hourly|daily|weekly)$", description="Data granularity")
):
    """Get build trends over time"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        # Group runs by time period
        time_series = _group_runs_by_time(ci_cd_runs, granularity)
        
        success_trend = []
        failure_trend = []
        duration_trend = []
        
        for period, period_runs in time_series.items():
            completed_runs = [r for r in period_runs if r.get("status") == "completed"]
            
            if completed_runs:
                successful = len([r for r in completed_runs if r.get("conclusion") == "success"])
                failed = len([r for r in completed_runs if r.get("conclusion") in ["failure", "timed_out"]])
                
                # Calculate average duration for the period
                durations = []
                for run in completed_runs:
                    duration = _calculate_duration(run)
                    if duration > 0:
                        durations.append(duration / 60.0)
                
                avg_duration = sum(durations) / len(durations) if durations else 0.0
                
                success_trend.append(TimeSeriesData(timestamp=period, value=successful))
                failure_trend.append(TimeSeriesData(timestamp=period, value=failed))
                duration_trend.append(TimeSeriesData(timestamp=period, value=round(avg_duration, 2)))
            else:
                success_trend.append(TimeSeriesData(timestamp=period, value=0))
                failure_trend.append(TimeSeriesData(timestamp=period, value=0))
                duration_trend.append(TimeSeriesData(timestamp=period, value=0.0))
        
        return BuildTrends(
            success_trend=success_trend,
            failure_trend=failure_trend,
            duration_trend=duration_trend,
            granularity=granularity,
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting build trends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch build trends: {str(e)}")

@router.get("/mttr", response_model=MTTRAnalysis)
async def get_mttr_analysis(
    lookback_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days")
):
    """Get Mean Time To Recovery (MTTR) analysis"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        completed_runs = [r for r in ci_cd_runs if r.get("status") == "completed"]
        completed_runs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        
        # Calculate MTTR for different time periods
        mttr_overall = _calculate_mttr(completed_runs)
        
        # Calculate MTTR by week
        weekly_mttr = []
        current_date = datetime.now(timezone.utc)
        
        for week in range(4):  # Last 4 weeks
            week_start = current_date - timedelta(weeks=week+1)
            week_end = current_date - timedelta(weeks=week)
            
            week_runs = []
            for run in completed_runs:
                run_time = parser.isoparse(run.get("updated_at", ""))
                if week_start <= run_time <= week_end:
                    week_runs.append(run)
            
            week_mttr = _calculate_mttr(week_runs)
            weekly_mttr.append(TimeSeriesData(
                timestamp=week_start.isoformat(),
                value=round(week_mttr, 2)
            ))
        
        # Failure incidents analysis
        failure_incidents = []
        failed_runs = [r for r in completed_runs if r.get("conclusion") in ["failure", "timed_out"]]
        
        for failure in failed_runs[:10]:  # Last 10 failures
            # Find next successful run after this failure
            failure_time = parser.isoparse(failure.get("updated_at", ""))
            recovery_time = None
            
            for run in completed_runs:
                if run.get("conclusion") == "success":
                    run_time = parser.isoparse(run.get("updated_at", ""))
                    if run_time > failure_time:
                        recovery_time = run_time
                        break
            
            recovery_minutes = 0
            if recovery_time:
                recovery_minutes = (recovery_time - failure_time).total_seconds() / 60
            
            failure_incidents.append({
                "failure_id": failure.get("id"),
                "failure_time": failure.get("updated_at"),
                "recovery_time": recovery_time.isoformat() if recovery_time else None,
                "recovery_minutes": round(recovery_minutes, 2),
                "branch": failure.get("head_branch"),
                "commit_sha": failure.get("head_sha", "")[:7]
            })
        
        return MTTRAnalysis(
            overall_mttr_minutes=round(mttr_overall, 2),
            weekly_mttr=weekly_mttr,
            failure_incidents=failure_incidents,
            total_failures=len(failed_runs),
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting MTTR analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch MTTR analysis: {str(e)}")

@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    lookback_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days")
):
    """Get detailed performance metrics and bottleneck analysis"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        completed_runs = [r for r in ci_cd_runs if r.get("status") == "completed"]
        
        # Duration analysis
        durations = []
        for run in completed_runs:
            duration = _calculate_duration(run)
            if duration > 0:
                durations.append(duration / 60.0)  # Convert to minutes
        
        if not durations:
            return PerformanceMetrics(
                average_duration_minutes=0.0,
                median_duration_minutes=0.0,
                p95_duration_minutes=0.0,
                fastest_build_minutes=0.0,
                slowest_build_minutes=0.0,
                duration_trend=[],
                bottlenecks=[],
                period_days=lookback_days,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        durations.sort()
        
        avg_duration = sum(durations) / len(durations)
        median_duration = durations[len(durations) // 2]
        p95_index = int(len(durations) * 0.95)
        p95_duration = durations[p95_index] if p95_index < len(durations) else durations[-1]
        
        # Duration trend over time
        duration_trend = _get_duration_trend(completed_runs, lookback_days)
        
        # Identify bottlenecks (slowest builds)
        bottlenecks = []
        runs_with_duration = [(r, _calculate_duration(r) / 60.0) for r in completed_runs]
        runs_with_duration.sort(key=lambda x: x[1], reverse=True)
        
        for run, duration in runs_with_duration[:5]:  # Top 5 slowest
            bottlenecks.append({
                "build_id": run.get("id"),
                "duration_minutes": round(duration, 2),
                "branch": run.get("head_branch"),
                "commit_sha": run.get("head_sha", "")[:7],
                "completed_at": run.get("updated_at"),
                "url": run.get("html_url")
            })
        
        return PerformanceMetrics(
            average_duration_minutes=round(avg_duration, 2),
            median_duration_minutes=round(median_duration, 2),
            p95_duration_minutes=round(p95_duration, 2),
            fastest_build_minutes=round(min(durations), 2),
            slowest_build_minutes=round(max(durations), 2),
            duration_trend=duration_trend,
            bottlenecks=bottlenecks,
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch performance metrics: {str(e)}")

@router.get("/failures", response_model=FailureAnalysis)
async def get_failure_analysis(
    lookback_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days")
):
    """Get detailed failure analysis and patterns"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        ci_cd_runs = github_client.filter_ci_cd_runs(runs)
        
        completed_runs = [r for r in ci_cd_runs if r.get("status") == "completed"]
        failed_runs = [r for r in completed_runs if r.get("conclusion") in ["failure", "timed_out"]]
        
        # Failure patterns by branch
        branch_failures = defaultdict(int)
        branch_totals = defaultdict(int)
        
        for run in completed_runs:
            branch = run.get("head_branch", "unknown")
            branch_totals[branch] += 1
            if run.get("conclusion") in ["failure", "timed_out"]:
                branch_failures[branch] += 1
        
        failure_by_branch = []
        for branch, total in branch_totals.items():
            failures = branch_failures[branch]
            failure_rate = (failures / total) * 100 if total > 0 else 0
            failure_by_branch.append({
                "branch": branch,
                "total_builds": total,
                "failures": failures,
                "failure_rate": round(failure_rate, 2)
            })
        
        failure_by_branch.sort(key=lambda x: x["failure_rate"], reverse=True)
        
        # Failure patterns by author
        author_failures = defaultdict(int)
        author_totals = defaultdict(int)
        
        for run in completed_runs:
            commit_info = run.get("head_commit", {})
            author = commit_info.get("author", {}).get("name", "unknown")
            author_totals[author] += 1
            if run.get("conclusion") in ["failure", "timed_out"]:
                author_failures[author] += 1
        
        failure_by_author = []
        for author, total in author_totals.items():
            failures = author_failures[author]
            failure_rate = (failures / total) * 100 if total > 0 else 0
            failure_by_author.append({
                "author": author,
                "total_builds": total,
                "failures": failures,
                "failure_rate": round(failure_rate, 2)
            })
        
        failure_by_author.sort(key=lambda x: x["failure_rate"], reverse=True)
        
        # Recent failures with details
        recent_failures = []
        for failure in failed_runs[:10]:  # Last 10 failures
            commit_info = failure.get("head_commit", {})
            recent_failures.append({
                "build_id": failure.get("id"),
                "conclusion": failure.get("conclusion"),
                "branch": failure.get("head_branch"),
                "commit_sha": failure.get("head_sha", "")[:7],
                "commit_message": commit_info.get("message", "").split('\n')[0][:100],
                "author": commit_info.get("author", {}).get("name", "Unknown"),
                "failed_at": failure.get("updated_at"),
                "duration_minutes": round(_calculate_duration(failure) / 60.0, 2),
                "url": failure.get("html_url")
            })
        
        # Failure trend over time
        failure_trend = _get_failure_trend(completed_runs, lookback_days)
        
        return FailureAnalysis(
            total_failures=len(failed_runs),
            failure_rate=round((len(failed_runs) / len(completed_runs)) * 100, 2) if completed_runs else 0,
            failure_by_branch=failure_by_branch[:10],  # Top 10
            failure_by_author=failure_by_author[:10],  # Top 10
            recent_failures=recent_failures,
            failure_trend=failure_trend,
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting failure analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch failure analysis: {str(e)}")

@router.get("/workflows/comparison", response_model=WorkflowComparison)
async def get_workflow_comparison(
    lookback_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days")
):
    """Compare performance across different workflows"""
    try:
        lookback_minutes = lookback_days * 24 * 60
        runs = github_client.get_recent_runs(lookback_minutes=lookback_minutes)
        
        # Group by workflow name
        workflow_stats = defaultdict(lambda: {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "durations": []
        })
        
        for run in runs:
            if run.get("status") == "completed":
                workflow_name = run.get("name", "Unknown")
                stats = workflow_stats[workflow_name]
                
                stats["total_runs"] += 1
                
                conclusion = run.get("conclusion")
                if conclusion == "success":
                    stats["successful_runs"] += 1
                elif conclusion in ["failure", "timed_out"]:
                    stats["failed_runs"] += 1
                
                duration = _calculate_duration(run)
                if duration > 0:
                    stats["durations"].append(duration / 60.0)
        
        # Convert to comparison format
        workflow_comparisons = []
        for workflow_name, stats in workflow_stats.items():
            if stats["total_runs"] > 0:
                success_rate = (stats["successful_runs"] / stats["total_runs"]) * 100
                avg_duration = sum(stats["durations"]) / len(stats["durations"]) if stats["durations"] else 0
                
                workflow_comparisons.append({
                    "workflow_name": workflow_name,
                    "total_runs": stats["total_runs"],
                    "success_rate": round(success_rate, 2),
                    "average_duration_minutes": round(avg_duration, 2),
                    "successful_runs": stats["successful_runs"],
                    "failed_runs": stats["failed_runs"]
                })
        
        # Sort by total runs (most active first)
        workflow_comparisons.sort(key=lambda x: x["total_runs"], reverse=True)
        
        return WorkflowComparison(
            workflows=workflow_comparisons,
            period_days=lookback_days,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow comparison: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch workflow comparison: {str(e)}")

# Helper functions

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

def _calculate_mttr(runs: List[Dict]) -> float:
    """Calculate Mean Time To Recovery in minutes"""
    if not runs:
        return 0.0
    
    # Sort runs by time
    runs.sort(key=lambda x: x.get("updated_at", ""))
    
    recovery_times = []
    
    for i, run in enumerate(runs):
        if run.get("conclusion") in ["failure", "timed_out"]:
            failure_time = parser.isoparse(run.get("updated_at", ""))
            
            # Find next successful run
            for j in range(i + 1, len(runs)):
                next_run = runs[j]
                if next_run.get("conclusion") == "success":
                    success_time = parser.isoparse(next_run.get("updated_at", ""))
                    recovery_minutes = (success_time - failure_time).total_seconds() / 60
                    recovery_times.append(recovery_minutes)
                    break
    
    return sum(recovery_times) / len(recovery_times) if recovery_times else 0.0

def _group_runs_by_time(runs: List[Dict], granularity: str) -> Dict[str, List[Dict]]:
    """Group runs by time period"""
    time_groups = defaultdict(list)
    
    for run in runs:
        try:
            run_time = parser.isoparse(run.get("updated_at", ""))
            
            if granularity == "hourly":
                period_key = run_time.strftime("%Y-%m-%d %H:00:00")
            elif granularity == "daily":
                period_key = run_time.strftime("%Y-%m-%d")
            elif granularity == "weekly":
                # Get Monday of the week
                monday = run_time - timedelta(days=run_time.weekday())
                period_key = monday.strftime("%Y-%m-%d")
            else:
                period_key = run_time.strftime("%Y-%m-%d")
            
            time_groups[period_key].append(run)
        except Exception:
            continue
    
    return time_groups

def _get_duration_trend(runs: List[Dict], lookback_days: int) -> List[TimeSeriesData]:
    """Get duration trend over time"""
    # Group runs by day
    daily_groups = _group_runs_by_time(runs, "daily")
    
    trend_data = []
    current_date = datetime.now(timezone.utc).date()
    
    for i in range(lookback_days):
        date = current_date - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        day_runs = daily_groups.get(date_str, [])
        
        if day_runs:
            durations = []
            for run in day_runs:
                duration = _calculate_duration(run)
                if duration > 0:
                    durations.append(duration / 60.0)
            
            avg_duration = sum(durations) / len(durations) if durations else 0.0
        else:
            avg_duration = 0.0
        
        trend_data.append(TimeSeriesData(
            timestamp=date_str,
            value=round(avg_duration, 2)
        ))
    
    return list(reversed(trend_data))  # Chronological order

def _get_failure_trend(runs: List[Dict], lookback_days: int) -> List[TimeSeriesData]:
    """Get failure trend over time"""
    # Group runs by day
    daily_groups = _group_runs_by_time(runs, "daily")
    
    trend_data = []
    current_date = datetime.now(timezone.utc).date()
    
    for i in range(lookback_days):
        date = current_date - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        day_runs = daily_groups.get(date_str, [])
        failure_count = len([r for r in day_runs if r.get("conclusion") in ["failure", "timed_out"]])
        
        trend_data.append(TimeSeriesData(
            timestamp=date_str,
            value=failure_count
        ))
    
    return list(reversed(trend_data))  # Chronological order
