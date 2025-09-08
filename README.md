# Automated DevOps Pipeline Monitor

A comprehensive CI/CD pipeline monitoring solution with automated failure detection, Slack notifications, analytics, and auto-rollback capabilities.

## 🚀 Quick Start

### Prerequisites

1. **GitHub Repository** with Actions enabled
2. **Slack Workspace** with incoming webhook configured
3. **GitHub Container Registry (GHCR)** access

### 1. Repository Setup

1. Fork or clone this repository
2. Enable GitHub Actions in repository settings
3. Ensure GitHub Container Registry is accessible

### 2. Slack Webhook Setup

1. Go to your Slack workspace
2. Create a new app or use existing one
3. Enable Incoming Webhooks
4. Create webhook URL(s) for your desired channel(s)
5. Copy webhook URLs to GitHub secrets

### 3. Configure Secrets

Add the following secrets in your GitHub repository (`Settings > Secrets and variables > Actions`):

#### Required Secrets:
```bash
SLACK_WEBHOOK_URL          # Main Slack webhook for failure or success alerts channel

SLACK_ANALYTICS_WEBHOOK_URL # Webhook for workflow analytics channel
```

#### Optional Variables:
```bash
FAIL_HEALTHCHECK          # Set to 'true' to test failure scenarios
```

## 🧪 Testing the System

### Test 1: Successful Pipeline

1. **Set success mode:**
   ```python
   # In app/app.py, line 17
   FORCE_FAILURE = False
   ```

2. **Commit and push to main branch:**
   ```bash
   git add .
   git commit -m "test: successful pipeline"
   git push origin main
   ```

3. **Expected results:**
   - ✅ CI phase completes (build + health check)
   - ✅ Deploy phase completes (push to GHCR + health check)
   - ✅ Slack notification for successful deployment
   - ✅ Analytics posted to Slack with success metrics

### Test 2: Failed Pipeline with Auto-Rollback

1. **Set failure mode:**
   ```python
   # In app/app.py, line 17
   FORCE_FAILURE = True
   ```

2. **Commit and push to main branch:**
   ```bash
   git add .
   git commit -m "test: pipeline failure and rollback"
   git push origin main
   ```

3. **Expected results:**
   - ✅ CI phase completes
   - ✅ Deploy phase pushes new image
   - ❌ Post-deploy health check fails
   - 🔄 Auto-rollback to previous image
   - 🚨 Slack notification for failed deployment
   - 📊 Failure analytics posted to Slack

## 🔍 Troubleshooting

### Common Issues

#### 1. "No CI/CD runs found to analyze"
- **Cause:** Monitor is running before any workflows complete
- **Solution:** Wait for at least one workflow to complete, or check workflow names

#### 2. "Slack webhook error"
- **Cause:** Invalid webhook URL or network issues
- **Solution:** Verify webhook URL in Slack app settings

#### 3. "Permission denied" for GHCR
- **Cause:** Insufficient permissions for GitHub Container Registry
- **Solution:** Ensure `packages: write` permission in workflow

#### 4. Rollback fails with "No :previous tag"
- **Cause:** First deployment has no previous version
- **Solution:** This is expected behavior; rollback only works after second deployment
