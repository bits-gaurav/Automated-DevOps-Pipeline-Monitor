# DevOps Pipeline Monitor API

A comprehensive FastAPI service that provides REST APIs for monitoring CI/CD pipelines, builds, analytics, and notifications. This API service is designed to work with your separate dashboard UI.

## Features

### 🚀 Pipeline Overview
- **Live Status**: Real-time pipeline status and queue information
- **Success/Failure Rates**: Visual indicators with historical data
- **Recent Deployments**: Latest deployment history with commit details
- **Current Builds**: Active build monitoring with progress tracking

### 🔧 Build Management
- **Build History**: Paginated build list with filtering options
- **Detailed Build Info**: Complete build details including jobs and steps
- **Build Logs**: Download and view build logs (full workflow or specific jobs)
- **Build Actions**: Rerun and cancel builds (with appropriate permissions)
- **Rollback History**: Track deployment rollbacks and recovery

### 📊 Analytics & Metrics
- **Performance Metrics**: Duration analysis, bottleneck identification
- **Success/Failure Trends**: Time-series data for trend analysis
- **MTTR Analysis**: Mean Time To Recovery with incident tracking
- **Workflow Comparison**: Compare performance across different workflows
- **Failure Analysis**: Detailed failure patterns by branch and author

### 🔔 Notifications & Alerts
- **Rule Management**: Create, update, delete notification rules
- **Multi-channel Support**: Slack integration with extensible architecture
- **Notification History**: Track all sent notifications with status
- **Real-time Alerts**: WebSocket-based real-time notifications
- **Test Notifications**: Send test messages to verify integrations

### ⚡ Real-time Updates
- **WebSocket Support**: Live updates for pipeline status changes
- **Event Subscriptions**: Subscribe to specific event types
- **Connection Management**: Robust connection handling with reconnection

## API Endpoints

### Pipeline Overview
- `GET /api/v1/pipeline/overview` - Comprehensive pipeline overview
- `GET /api/v1/pipeline/status` - Detailed pipeline status
- `GET /api/v1/pipeline/metrics` - Pipeline performance metrics
- `GET /api/v1/pipeline/recent` - Recent pipeline activity

### Build Management
- `GET /api/v1/builds/` - List builds with pagination and filtering
- `GET /api/v1/builds/{build_id}` - Get detailed build information
- `GET /api/v1/builds/{build_id}/logs` - Download build logs
- `GET /api/v1/builds/{build_id}/jobs/{job_id}/logs` - Get parsed job logs
- `POST /api/v1/builds/{build_id}/rerun` - Rerun a build
- `POST /api/v1/builds/{build_id}/cancel` - Cancel a running build
- `GET /api/v1/builds/history/rollbacks` - Get rollback history

### Analytics & Metrics
- `GET /api/v1/analytics/overview` - Analytics overview
- `GET /api/v1/analytics/trends` - Build trends over time
- `GET /api/v1/analytics/mttr` - MTTR analysis
- `GET /api/v1/analytics/performance` - Performance metrics
- `GET /api/v1/analytics/failures` - Failure analysis
- `GET /api/v1/analytics/workflows/comparison` - Workflow comparison

### Notifications
- `GET /api/v1/notifications/rules` - List notification rules
- `POST /api/v1/notifications/rules` - Create notification rule
- `PUT /api/v1/notifications/rules/{rule_id}` - Update notification rule
- `DELETE /api/v1/notifications/rules/{rule_id}` - Delete notification rule
- `GET /api/v1/notifications/history` - Notification history
- `POST /api/v1/notifications/slack/send` - Send Slack notification
- `GET /api/v1/notifications/settings` - Get notification settings
- `GET /api/v1/notifications/status` - Notification system status
- `POST /api/v1/notifications/test/slack` - Test Slack integration

### WebSocket
- `WS /ws` - WebSocket endpoint for real-time updates

### System
- `GET /` - API information
- `GET /health` - Health check endpoint

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# GitHub Configuration
GITHUB_TOKEN=your_github_token_here
GITHUB_OWNER=your_github_username
GITHUB_REPO=your_repository_name

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
SLACK_ANALYTICS_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/ANALYTICS/WEBHOOK
```

### 2. Using Docker (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### 3. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or run directly
python -m uvicorn main:app --reload
```

### 4. Production Deployment

For production deployment with nginx:

```bash
# Run with production profile (includes nginx)
docker-compose --profile production up -d
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub personal access token | `ghp_xxxxxxxxxxxx` |
| `GITHUB_OWNER` | GitHub repository owner | `your-username` |
| `GITHUB_REPO` | GitHub repository name | `your-repo` |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | `https://hooks.slack.com/...` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_ANALYTICS_WEBHOOK_URL` | Separate webhook for analytics | Same as `SLACK_WEBHOOK_URL` |
| `REGISTRY` | Container registry URL | `ghcr.io` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `["http://localhost:3000"]` |
| `CACHE_TTL` | Cache TTL in seconds | `300` |
| `DEFAULT_PAGE_SIZE` | Default pagination size | `20` |
| `MAX_PAGE_SIZE` | Maximum pagination size | `100` |

## GitHub Token Permissions

Your GitHub token needs the following permissions:
- `actions:read` - Read workflow runs and jobs
- `contents:read` - Read repository content
- `metadata:read` - Read repository metadata

## Integration with Your Dashboard

This API is designed to work with your separate dashboard UI. Here are the key integration points:

### 1. Real-time Updates
Connect to the WebSocket endpoint for live updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

// Subscribe to specific events
ws.send(JSON.stringify({
  type: 'subscribe',
  events: ['pipeline', 'builds', 'notifications']
}));

// Handle incoming updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update your dashboard UI based on data.type
};
```

### 2. API Integration
Use the REST endpoints to fetch data for your dashboard:

```javascript
// Get pipeline overview
const overview = await fetch('/api/v1/pipeline/overview').then(r => r.json());

// Get recent builds
const builds = await fetch('/api/v1/builds?page=1&per_page=10').then(r => r.json());

// Get analytics
const analytics = await fetch('/api/v1/analytics/overview?lookback_days=7').then(r => r.json());
```

### 3. Error Handling
All API responses follow a consistent error format:

```json
{
  "error": {
    "message": "Error description",
    "type": "ErrorType",
    "details": {},
    "timestamp": "2025-09-29T11:27:51+05:30",
    "path": "/api/v1/endpoint"
  }
}
```

## API Documentation

Once the service is running, you can access:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Monitoring and Logging

### Health Checks
The API includes comprehensive health checks:
- Container health check via `/health` endpoint
- Docker Compose health check configuration
- Service dependency monitoring

### Logging
Structured logging is implemented throughout:
- Request/response logging
- Error tracking with context
- Performance monitoring
- WebSocket connection tracking

### Metrics
Key metrics are available through the analytics endpoints:
- API response times
- GitHub API rate limit usage
- WebSocket connection counts
- Notification delivery rates

## Security Considerations

- **Authentication**: Currently uses GitHub token authentication
- **CORS**: Configurable CORS origins for dashboard integration
- **Rate Limiting**: Respects GitHub API rate limits
- **Input Validation**: Comprehensive request validation
- **Error Handling**: Secure error responses without sensitive data exposure

## Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**
   - Monitor rate limit headers in responses
   - Implement exponential backoff for retries
   - Consider using GitHub App authentication for higher limits

2. **WebSocket Connection Issues**
   - Check firewall settings for WebSocket traffic
   - Verify CORS configuration for WebSocket origins
   - Monitor connection lifecycle in logs

3. **Slack Integration Problems**
   - Verify webhook URL format and permissions
   - Test with `/api/v1/notifications/test/slack` endpoint
   - Check Slack app configuration and scopes

### Debug Mode

Enable debug logging by setting log level:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or modify logging configuration in main.py
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the troubleshooting section
3. Check existing GitHub issues
4. Create a new issue with detailed information
