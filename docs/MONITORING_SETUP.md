# Monitoring & Alerting Setup Guide

## Overview

The Finance Feedback Engine includes automated monitoring and health check workflows that run continuously to ensure system reliability. This guide explains how the monitoring system works and how to configure it properly.

## Monitoring Workflow

The monitoring system (`monitoring-alerts.yml`) provides:

- **Health Checks**: Production and staging endpoint monitoring
- **Performance Monitoring**: API response time analysis
- **Security Monitoring**: SSL certificate expiration, vulnerability scanning
- **Dependency Monitoring**: Outdated packages and security advisories
- **Automated Alerting**: GitHub Issues created for critical failures

## Scheduled Runs

The monitoring workflow runs:
- **Every 15 minutes** for health checks (scheduled cron job)
- **On-demand** via manual workflow dispatch
- **Daily** for security and dependency scans

## Configuration

### Required GitHub Secrets

To enable production monitoring, configure these secrets in your repository settings:

```
Settings → Secrets and variables → Actions → Repository secrets
```

**Production Environment:**
- `PROD_URL`: Production API endpoint (e.g., `https://api.example.com`)
- `PROD_HOST`: Production server hostname for deployments

**Staging Environment:**
- `STAGING_URL`: Staging API endpoint (e.g., `https://staging.example.com`)
- `STAGING_HOST`: Staging server hostname for deployments

**Optional:**
- `REDIS_URL`: Redis connection string for service checks
- `AWS_ACCESS_KEY_ID`: For backup monitoring
- `AWS_SECRET_ACCESS_KEY`: For backup monitoring

### Alert Behavior

The monitoring system is designed to avoid false alarms:

#### Alerts are ONLY created when:
1. ✅ Running on `main` or `production` branch
2. ✅ Valid production URL is configured (not example.com)
3. ✅ Health check actually fails (not skipped)
4. ✅ Triggered by scheduled run (cron), not manual runs on feature branches

#### Alerts are NOT created when:
- ❌ Running on feature/development branches
- ❌ Production URL not configured (defaults to example.com)
- ❌ Health check is skipped due to missing configuration
- ❌ Manual workflow dispatch for testing

## Health Check Endpoints

The monitoring workflow expects these endpoints to be available:

### Production/Staging API
- **Endpoint**: `GET /health`
- **Expected Response**: HTTP 200
- **Response Format**: JSON with health status

Example response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-29T16:00:00Z",
  "uptime_seconds": 3600,
  "portfolio_balance": 10000.00,
  "circuit_breakers": {
    "alpha_vantage": {
      "state": "CLOSED",
      "failure_count": 0
    }
  },
  "components": {
    "platform": {"status": "healthy"},
    "data_provider": {"status": "healthy"},
    "decision_store": {"status": "healthy"}
  }
}
```

## Testing the Monitoring System

### Manual Workflow Dispatch

You can test the monitoring system manually:

1. Go to **Actions** tab in GitHub
2. Select **Monitoring & Alerting** workflow
3. Click **Run workflow**
4. Choose check type:
   - `health`: Test health checks only
   - `performance`: Test performance monitoring
   - `security`: Test security scanning
   - `all`: Run all checks

### Local Health Check Testing

Test your health endpoint locally:

```bash
# Start the API server
python main.py serve --port 8000

# In another terminal, test the health endpoint
curl http://localhost:8000/health

# Expected: HTTP 200 with JSON response
```

## Troubleshooting

### Issue: False alarms on feature branches

**Solution**: This is now fixed. The workflow skips alert creation on non-production branches.

### Issue: Alerts for unconfigured endpoints

**Solution**: Configure `PROD_URL` and `STAGING_URL` secrets, or the workflow will skip checks with a warning instead of creating alerts.

### Issue: Health check always fails

**Symptoms**:
- HTTP 000 or connection timeout
- Service not reachable

**Solutions**:
1. Verify the service is running: `systemctl status finance-feedback-engine`
2. Check firewall rules allow traffic on port 8000
3. Verify DNS resolution: `nslookup your-domain.com`
4. Test endpoint manually: `curl -v https://your-domain.com/health`

### Issue: SSL certificate warnings

**Symptoms**:
- Workflow warns about certificate expiration

**Solutions**:
1. Renew SSL certificate: `certbot renew`
2. Verify certificate validity: `openssl s_client -connect your-domain.com:443`
3. Check auto-renewal cron job: `systemctl status certbot.timer`

## Monitoring Summary Report

After each run, the workflow generates a summary showing:
- Status of each check (success/failure/skipped)
- Configuration status (which secrets are set)
- Current branch being monitored
- Next scheduled check time
- Important notes about alert behavior

## Disabling Monitoring

To temporarily disable scheduled monitoring:

1. Edit `.github/workflows/monitoring-alerts.yml`
2. Comment out or remove the cron schedule:
```yaml
# on:
#   schedule:
#     - cron: '*/15 * * * *'
```
3. Manual workflow dispatch will still work

## Best Practices

1. **Always configure production secrets** before merging monitoring workflows to main
2. **Test health endpoints locally** before deployment
3. **Monitor the workflow runs** in Actions tab to catch issues early
4. **Set up notification channels** (Slack, email) for GitHub Issues with `alert` label
5. **Review and close** automated issues after resolving problems
6. **Keep health endpoints lightweight** - they run every 15 minutes

## Integration with Deployment

The monitoring system integrates with deployment workflows:

1. **deploy.yml** performs health checks after deployment
2. **monitoring-alerts.yml** continuously monitors deployed services
3. **backup-automation.yml** verifies backup storage

## Metrics Collected

The monitoring system tracks:
- **Availability**: Uptime percentage over time
- **Response Time**: API endpoint latency
- **Error Rate**: HTTP 5xx responses
- **Certificate Validity**: Days until SSL expiration
- **Dependency Health**: Outdated packages count
- **Security Advisories**: Open vulnerability count

## Future Enhancements

Planned improvements:
- Slack/Teams webhook notifications
- Prometheus metrics export
- Grafana dashboard integration
- Custom alert rules
- Multi-region health checks
- Historical trend analysis

## Support

For questions or issues:
- Open a GitHub Issue with label `monitoring`
- Check workflow logs in Actions tab
- Review `docs/WORKFLOW_AUTOMATION_GUIDE.md`

---

**Last Updated**: 2025-12-29
**Version**: 1.1.0
