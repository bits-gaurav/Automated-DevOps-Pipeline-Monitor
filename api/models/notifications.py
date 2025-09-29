from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class NotificationRule(BaseModel):
    """Notification rule configuration"""
    id: int
    name: str
    description: str
    trigger_events: List[str]  # e.g., ["build_failed", "deployment_success"]
    conditions: List[Dict[str, Any]]  # e.g., [{"type": "branch", "value": "main"}]
    channels: List[str]  # e.g., ["slack", "email"]
    enabled: bool
    created_at: str
    updated_at: str

class CreateNotificationRule(BaseModel):
    """Create notification rule request"""
    name: str
    description: str
    trigger_events: List[str]
    conditions: List[Dict[str, Any]]
    channels: List[str]
    enabled: bool = True

class UpdateNotificationRule(BaseModel):
    """Update notification rule request"""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_events: Optional[List[str]] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    channels: Optional[List[str]] = None
    enabled: Optional[bool] = None

class NotificationHistory(BaseModel):
    """Notification history entry"""
    id: int
    rule_id: Optional[int]
    channel: str
    recipient: str
    message: str
    status: str  # sent, failed, pending
    sent_at: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SlackNotification(BaseModel):
    """Slack notification payload"""
    text: str
    blocks: Optional[List[Dict[str, Any]]] = None
    channel: Optional[str] = None
    rule_id: Optional[int] = None

class NotificationSettings(BaseModel):
    """Notification system settings"""
    slack_enabled: bool
    email_enabled: bool
    webhook_enabled: bool
    default_channels: List[str]
    rate_limit_per_hour: int
    retry_attempts: int
    retry_delay_seconds: int

class NotificationStatus(BaseModel):
    """Notification system status"""
    overall_status: str  # healthy, degraded, unhealthy
    active_rules: int
    total_rules: int
    recent_notifications_count: int
    successful_notifications_count: int
    failed_notifications_count: int
    slack_status: str  # healthy, degraded, unhealthy, not_configured
    email_status: str  # healthy, degraded, unhealthy, not_configured
    last_notification_at: Optional[str]
    timestamp: str
