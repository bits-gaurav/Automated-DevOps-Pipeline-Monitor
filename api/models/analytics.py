from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class TimeSeriesData(BaseModel):
    """Time series data point"""
    timestamp: str
    value: float

class TrendData(BaseModel):
    """Trend data over time"""
    period: str
    success_count: int
    failure_count: int
    average_duration_minutes: float

class AnalyticsOverview(BaseModel):
    """Comprehensive analytics overview"""
    total_builds: int
    success_rate: float
    failure_rate: float
    average_duration_minutes: float
    mttr_minutes: float
    builds_per_day: float
    most_active_branch: str
    most_active_author: str
    period_days: int
    timestamp: str

class BuildTrends(BaseModel):
    """Build trends over time"""
    success_trend: List[TimeSeriesData]
    failure_trend: List[TimeSeriesData]
    duration_trend: List[TimeSeriesData]
    granularity: str
    period_days: int
    timestamp: str

class MTTRAnalysis(BaseModel):
    """Mean Time To Recovery analysis"""
    overall_mttr_minutes: float
    weekly_mttr: List[TimeSeriesData]
    failure_incidents: List[Dict[str, Any]]
    total_failures: int
    period_days: int
    timestamp: str

class PerformanceMetrics(BaseModel):
    """Detailed performance metrics"""
    average_duration_minutes: float
    median_duration_minutes: float
    p95_duration_minutes: float
    fastest_build_minutes: float
    slowest_build_minutes: float
    duration_trend: List[TimeSeriesData]
    bottlenecks: List[Dict[str, Any]]
    period_days: int
    timestamp: str

class FailureAnalysis(BaseModel):
    """Failure analysis and patterns"""
    total_failures: int
    failure_rate: float
    failure_by_branch: List[Dict[str, Any]]
    failure_by_author: List[Dict[str, Any]]
    recent_failures: List[Dict[str, Any]]
    failure_trend: List[TimeSeriesData]
    period_days: int
    timestamp: str

class WorkflowComparison(BaseModel):
    """Workflow performance comparison"""
    workflows: List[Dict[str, Any]]
    period_days: int
    timestamp: str
