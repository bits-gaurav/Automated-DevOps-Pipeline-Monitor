from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
import requests
import json

from core.github_client import github_client
from core.config import settings
from models.notifications import (
    NotificationRule,
    NotificationHistory,
    SlackNotification,
    NotificationSettings,
    NotificationStatus,
    CreateNotificationRule,
    UpdateNotificationRule
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage for notification rules (in production, use a database)
notification_rules = []
notification_history = []

@router.get("/rules", response_model=List[NotificationRule])
async def get_notification_rules():
    """Get all notification rules"""
    return notification_rules

@router.post("/rules", response_model=NotificationRule)
async def create_notification_rule(rule: CreateNotificationRule):
    """Create a new notification rule"""
    try:
        new_rule = NotificationRule(
            id=len(notification_rules) + 1,
            name=rule.name,
            description=rule.description,
            trigger_events=rule.trigger_events,
            conditions=rule.conditions,
            channels=rule.channels,
            enabled=rule.enabled,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        notification_rules.append(new_rule)
        
        logger.info(f"Created notification rule: {new_rule.name}")
        return new_rule
        
    except Exception as e:
        logger.error(f"Error creating notification rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification rule: {str(e)}")

@router.put("/rules/{rule_id}", response_model=NotificationRule)
async def update_notification_rule(rule_id: int, rule_update: UpdateNotificationRule):
    """Update an existing notification rule"""
    try:
        # Find the rule
        rule_index = None
        for i, rule in enumerate(notification_rules):
            if rule.id == rule_id:
                rule_index = i
                break
        
        if rule_index is None:
            raise HTTPException(status_code=404, detail="Notification rule not found")
        
        # Update the rule
        existing_rule = notification_rules[rule_index]
        updated_rule = NotificationRule(
            id=existing_rule.id,
            name=rule_update.name if rule_update.name is not None else existing_rule.name,
            description=rule_update.description if rule_update.description is not None else existing_rule.description,
            trigger_events=rule_update.trigger_events if rule_update.trigger_events is not None else existing_rule.trigger_events,
            conditions=rule_update.conditions if rule_update.conditions is not None else existing_rule.conditions,
            channels=rule_update.channels if rule_update.channels is not None else existing_rule.channels,
            enabled=rule_update.enabled if rule_update.enabled is not None else existing_rule.enabled,
            created_at=existing_rule.created_at,
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        notification_rules[rule_index] = updated_rule
        
        logger.info(f"Updated notification rule: {updated_rule.name}")
        return updated_rule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update notification rule: {str(e)}")

@router.delete("/rules/{rule_id}")
async def delete_notification_rule(rule_id: int):
    """Delete a notification rule"""
    try:
        # Find and remove the rule
        rule_index = None
        for i, rule in enumerate(notification_rules):
            if rule.id == rule_id:
                rule_index = i
                break
        
        if rule_index is None:
            raise HTTPException(status_code=404, detail="Notification rule not found")
        
        deleted_rule = notification_rules.pop(rule_index)
        
        logger.info(f"Deleted notification rule: {deleted_rule.name}")
        return {"message": "Notification rule deleted successfully", "rule_id": rule_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete notification rule: {str(e)}")

@router.get("/history", response_model=List[NotificationHistory])
async def get_notification_history(
    limit: int = Query(default=50, ge=1, le=200, description="Number of notifications to return"),
    channel: Optional[str] = Query(default=None, description="Filter by channel type"),
    status: Optional[str] = Query(default=None, description="Filter by status")
):
    """Get notification history"""
    try:
        filtered_history = notification_history.copy()
        
        # Apply filters
        if channel:
            filtered_history = [n for n in filtered_history if n.channel == channel]
        
        if status:
            filtered_history = [n for n in filtered_history if n.status == status]
        
        # Sort by timestamp (newest first) and limit
        filtered_history.sort(key=lambda x: x.sent_at, reverse=True)
        
        return filtered_history[:limit]
        
    except Exception as e:
        logger.error(f"Error getting notification history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch notification history: {str(e)}")

@router.post("/slack/send")
async def send_slack_notification(notification: SlackNotification):
    """Send a Slack notification"""
    try:
        webhook_url = settings.SLACK_WEBHOOK_URL
        if not webhook_url:
            raise HTTPException(status_code=400, detail="Slack webhook URL not configured")
        
        # Prepare Slack payload
        payload = {
            "text": notification.text,
            "blocks": notification.blocks if notification.blocks else []
        }
        
        # Send to Slack
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        
        # Record in history
        history_entry = NotificationHistory(
            id=len(notification_history) + 1,
            rule_id=notification.rule_id,
            channel="slack",
            recipient=notification.channel or "default",
            message=notification.text,
            status="sent",
            sent_at=datetime.now(timezone.utc).isoformat(),
            metadata={"webhook_response": response.status_code}
        )
        
        notification_history.append(history_entry)
        
        logger.info(f"Slack notification sent successfully")
        return {"message": "Slack notification sent", "status": "sent", "notification_id": history_entry.id}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Slack notification: {e}")
        
        # Record failed attempt
        history_entry = NotificationHistory(
            id=len(notification_history) + 1,
            rule_id=notification.rule_id,
            channel="slack",
            recipient=notification.channel or "default",
            message=notification.text,
            status="failed",
            sent_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e),
            metadata={"error_type": "webhook_error"}
        )
        
        notification_history.append(history_entry)
        
        raise HTTPException(status_code=500, detail=f"Failed to send Slack notification: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error sending Slack notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send Slack notification: {str(e)}")

@router.get("/settings", response_model=NotificationSettings)
async def get_notification_settings():
    """Get current notification settings"""
    return NotificationSettings(
        slack_enabled=bool(settings.SLACK_WEBHOOK_URL),
        email_enabled=False,  # Not implemented yet
        webhook_enabled=True,
        default_channels=["slack"],
        rate_limit_per_hour=60,
        retry_attempts=3,
        retry_delay_seconds=300
    )

@router.put("/settings")
async def update_notification_settings(settings_update: Dict[str, Any] = Body(...)):
    """Update notification settings"""
    try:
        # In a real implementation, this would update persistent settings
        logger.info(f"Notification settings update requested: {settings_update}")
        
        return {
            "message": "Notification settings updated",
            "settings": settings_update,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating notification settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update notification settings: {str(e)}")

@router.get("/status", response_model=NotificationStatus)
async def get_notification_status():
    """Get notification system status"""
    try:
        # Check recent notifications
        recent_notifications = [n for n in notification_history if 
                             datetime.fromisoformat(n.sent_at.replace('Z', '+00:00')) > 
                             datetime.now(timezone.utc) - timedelta(hours=1)]
        
        successful_notifications = [n for n in recent_notifications if n.status == "sent"]
        failed_notifications = [n for n in recent_notifications if n.status == "failed"]
        
        # Test Slack connectivity
        slack_status = "healthy"
        if settings.SLACK_WEBHOOK_URL:
            try:
                # Simple connectivity test (you might want to use a different approach)
                test_response = requests.head("https://hooks.slack.com", timeout=5)
                if test_response.status_code >= 400:
                    slack_status = "degraded"
            except:
                slack_status = "unhealthy"
        else:
            slack_status = "not_configured"
        
        return NotificationStatus(
            overall_status="healthy" if slack_status in ["healthy", "not_configured"] else "degraded",
            active_rules=len([r for r in notification_rules if r.enabled]),
            total_rules=len(notification_rules),
            recent_notifications_count=len(recent_notifications),
            successful_notifications_count=len(successful_notifications),
            failed_notifications_count=len(failed_notifications),
            slack_status=slack_status,
            email_status="not_configured",
            last_notification_at=recent_notifications[0].sent_at if recent_notifications else None,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch notification status: {str(e)}")

@router.post("/test/slack")
async def test_slack_notification():
    """Send a test Slack notification"""
    try:
        test_notification = SlackNotification(
            text="🧪 Test notification from DevOps Pipeline Monitor API",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*🧪 Test Notification*\n\nThis is a test message from the DevOps Pipeline Monitor API to verify Slack integration is working correctly."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Sent at:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ],
            rule_id=0,
            channel="test"
        )
        
        return await send_slack_notification(test_notification)
        
    except Exception as e:
        logger.error(f"Error sending test Slack notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")

@router.post("/process/pipeline-event")
async def process_pipeline_event(event_data: Dict[str, Any] = Body(...)):
    """Process a pipeline event and trigger appropriate notifications"""
    try:
        event_type = event_data.get("type", "unknown")
        build_data = event_data.get("build", {})
        
        logger.info(f"Processing pipeline event: {event_type}")
        
        # Find matching notification rules
        triggered_rules = []
        for rule in notification_rules:
            if not rule.enabled:
                continue
            
            # Check if event type matches
            if event_type in rule.trigger_events:
                # Check conditions (simplified logic)
                conditions_met = True
                for condition in rule.conditions:
                    condition_type = condition.get("type")
                    condition_value = condition.get("value")
                    
                    if condition_type == "branch" and build_data.get("branch") != condition_value:
                        conditions_met = False
                        break
                    elif condition_type == "status" and build_data.get("status") != condition_value:
                        conditions_met = False
                        break
                
                if conditions_met:
                    triggered_rules.append(rule)
        
        # Send notifications for triggered rules
        notifications_sent = []
        for rule in triggered_rules:
            for channel in rule.channels:
                if channel == "slack":
                    # Create Slack notification
                    slack_notification = SlackNotification(
                        text=f"Pipeline event: {event_type}",
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*Pipeline Event: {event_type}*\n\n{rule.description}"
                                }
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Rule:* {rule.name} | *Branch:* {build_data.get('branch', 'N/A')} | *Status:* {build_data.get('status', 'N/A')}"
                                    }
                                ]
                            }
                        ],
                        rule_id=rule.id,
                        channel="automated"
                    )
                    
                    try:
                        result = await send_slack_notification(slack_notification)
                        notifications_sent.append({
                            "rule_id": rule.id,
                            "channel": channel,
                            "status": "sent",
                            "notification_id": result.get("notification_id")
                        })
                    except Exception as e:
                        logger.error(f"Failed to send notification for rule {rule.id}: {e}")
                        notifications_sent.append({
                            "rule_id": rule.id,
                            "channel": channel,
                            "status": "failed",
                            "error": str(e)
                        })
        
        return {
            "event_type": event_type,
            "triggered_rules": len(triggered_rules),
            "notifications_sent": notifications_sent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing pipeline event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process pipeline event: {str(e)}")

# Initialize with some default notification rules
def initialize_default_rules():
    """Initialize with some default notification rules"""
    if not notification_rules:
        default_rules = [
            NotificationRule(
                id=1,
                name="Build Failures",
                description="Notify on build failures",
                trigger_events=["build_failed", "build_timeout"],
                conditions=[{"type": "branch", "value": "main"}],
                channels=["slack"],
                enabled=True,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            ),
            NotificationRule(
                id=2,
                name="Deployment Success",
                description="Notify on successful deployments",
                trigger_events=["deployment_success"],
                conditions=[{"type": "branch", "value": "main"}],
                channels=["slack"],
                enabled=True,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            )
        ]
        
        notification_rules.extend(default_rules)

# Initialize default rules when module loads
initialize_default_rules()
