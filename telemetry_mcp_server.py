#!/usr/bin/env python3
"""
Telemetry MCP Server - Proof of Concept
========================================

This MCP server demonstrates how LLM agents can access internal corporate
telemetry data for monitoring and alerting on SLI metrics such as CPU usage,
memory consumption, and error rates.

In a production environment, this server would connect to:
- Time-series databases (InfluxDB, Prometheus, TimescaleDB)
- APM tools (Datadog, New Relic, Dynatrace)
- Cloud monitoring services (CloudWatch, Azure Monitor, Google Cloud Monitoring)
- Internal Kafka streams for real-time metrics

Architecture Pattern:
    [Infrastructure] → Kafka → Stream Processing → Time-series DB
                                                          ↓
                                                    MCP Server
                                                          ↓
                                                    [LLM Agent]

Requirements:
    pip install mcp fastmcp
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("telemetry-api")

# ============================================================================
# SIMULATED DATA LAYER
# In production, these would be replaced with actual database queries
# ============================================================================

def generate_sample_metrics(
    service: str,
    metric_type: str,
    hours: int = 24
) -> List[Dict]:
    """
    Simulate time-series metrics data.

    In production, this would query:
    - InfluxDB: SELECT mean(value) FROM metrics WHERE service='...'
    - Prometheus: rate(metric_name[5m])
    - CloudWatch: GetMetricStatistics
    """
    data_points = []
    base_time = datetime.utcnow() - timedelta(hours=hours)

    # Baseline values with realistic variations
    baselines = {
        "cpu": 45.0,      # CPU percentage
        "memory": 65.0,   # Memory percentage
        "error_rate": 0.5 # Errors per second
    }

    base_value = baselines.get(metric_type, 50.0)

    for i in range(hours * 12):  # 5-minute intervals
        timestamp = base_time + timedelta(minutes=i * 5)

        # Add realistic variation
        variation = random.uniform(-10, 10)
        # Add occasional spike (simulate incidents)
        if random.random() < 0.05:  # 5% chance of spike
            variation += random.uniform(20, 40)

        value = max(0, min(100, base_value + variation))

        data_points.append({
            "timestamp": timestamp.isoformat(),
            "service": service,
            "metric": metric_type,
            "value": round(value, 2),
            "unit": "%" if metric_type != "error_rate" else "errors/sec"
        })

    return data_points


def get_service_list() -> List[str]:
    """Return list of monitored services."""
    return [
        "api-gateway",
        "auth-service",
        "payment-processor",
        "user-service",
        "notification-service",
        "database-primary",
        "database-replica",
        "cache-redis"
    ]


def calculate_sli_compliance(
    service: str,
    metric: str,
    threshold: float,
    time_window_hours: int = 24
) -> Dict:
    """
    Calculate SLI compliance for a service.

    SLI (Service Level Indicator) measures actual service performance.
    Example: 99.9% of requests should complete under 200ms.

    In production, this would query pre-aggregated SLI data from:
    - Prometheus Alertmanager
    - Custom SLI calculation pipelines
    - APM tools with SLO tracking
    """
    metrics = generate_sample_metrics(service, metric, time_window_hours)

    if metric == "error_rate":
        # For error rate, we want values BELOW threshold (lower is better)
        compliant_points = sum(1 for m in metrics if m["value"] <= threshold)
    else:
        # For CPU/memory, we want values BELOW threshold
        compliant_points = sum(1 for m in metrics if m["value"] <= threshold)

    total_points = len(metrics)
    compliance_percentage = (compliant_points / total_points) * 100

    # Determine SLO status (Service Level Objective is the target)
    slo_target = 99.0  # 99% compliance target
    status = "HEALTHY" if compliance_percentage >= slo_target else "DEGRADED"

    return {
        "service": service,
        "metric": metric,
        "threshold": threshold,
        "time_window_hours": time_window_hours,
        "compliance_percentage": round(compliance_percentage, 2),
        "slo_target": slo_target,
        "status": status,
        "compliant_measurements": compliant_points,
        "total_measurements": total_points
    }


# ============================================================================
# MCP TOOLS - Actions that LLM agents can invoke
# ============================================================================

@mcp.tool()
def get_current_metrics(service: str) -> Dict:
    """
    Get current (latest) telemetry metrics for a specific service.

    Args:
        service: Name of the service to query (e.g., 'api-gateway')

    Returns:
        Dictionary with current CPU, memory, and error rate metrics

    Security Note: In production, this tool would:
    - Validate user has permission to view this service's metrics
    - Apply row-level security based on user's team/department
    - Log the access for audit purposes
    - Rate limit requests to prevent abuse
    """
    if service not in get_service_list():
        return {
            "error": f"Service '{service}' not found",
            "available_services": get_service_list()
        }

    # Simulate fetching latest metrics
    cpu_data = generate_sample_metrics(service, "cpu", hours=1)[-1]
    memory_data = generate_sample_metrics(service, "memory", hours=1)[-1]
    error_data = generate_sample_metrics(service, "error_rate", hours=1)[-1]

    return {
        "service": service,
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {
            "cpu_percent": cpu_data["value"],
            "memory_percent": memory_data["value"],
            "error_rate": error_data["value"]
        },
        "status": "OK" if cpu_data["value"] < 80 and memory_data["value"] < 85 else "WARNING"
    }


@mcp.tool()
def query_historical_metrics(
    service: str,
    metric_type: str,
    hours: int = 24
) -> Dict:
    """
    Query historical telemetry data for analysis and troubleshooting.

    Args:
        service: Service name to query
        metric_type: Type of metric ('cpu', 'memory', 'error_rate')
        hours: Number of hours of history to retrieve (default: 24)

    Returns:
        Time-series data with statistics

    Use Case: Root cause analysis during incident investigations
    Example: "Show me CPU usage for api-gateway over the last 6 hours"

    Production Implementation:
    - Query time-series database with indexed lookups
    - Apply downsampling for long time ranges to reduce data volume
    - Use connection pooling for database efficiency
    """
    if service not in get_service_list():
        return {"error": f"Service '{service}' not found"}

    valid_metrics = ["cpu", "memory", "error_rate"]
    if metric_type not in valid_metrics:
        return {"error": f"Invalid metric type. Choose from: {valid_metrics}"}

    # Validate time range (prevent excessive queries)
    if hours > 168:  # 1 week
        return {"error": "Maximum time range is 168 hours (1 week)"}

    data_points = generate_sample_metrics(service, metric_type, hours)

    # Calculate statistics
    values = [d["value"] for d in data_points]

    return {
        "service": service,
        "metric": metric_type,
        "time_range_hours": hours,
        "data_points": len(data_points),
        "statistics": {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2),
            "current": round(values[-1], 2)
        },
        "samples": data_points[-12:],  # Last hour (12 x 5-min intervals)
        "note": "Full dataset available via download_metrics resource"
    }


@mcp.tool()
def check_sli_compliance(
    service: str,
    metric: str,
    threshold: float,
    time_window_hours: int = 24
) -> Dict:
    """
    Check Service Level Indicator (SLI) compliance against defined thresholds.

    Args:
        service: Service to check
        metric: Metric to evaluate ('cpu', 'memory', 'error_rate')
        threshold: Maximum acceptable value
        time_window_hours: Evaluation period (default: 24)

    Returns:
        SLI compliance report with status and recommendations

    SLI Context:
    - SLI: Quantitative measure of service level (e.g., "95% of requests < 200ms")
    - SLO: Target value for SLI (e.g., "99% compliance")
    - SLA: Business agreement with consequences for SLO violations

    Example Usage:
    - "Is api-gateway meeting its 80% CPU SLI target?"
    - "Check if error rate is within our 0.1% SLO"
    """
    if service not in get_service_list():
        return {"error": f"Service '{service}' not found"}

    result = calculate_sli_compliance(service, metric, threshold, time_window_hours)

    # Add recommendations
    if result["status"] == "DEGRADED":
        result["recommendations"] = [
            "Review recent deployments for performance regressions",
            "Check for increased traffic patterns",
            "Analyze error logs for root cause",
            "Consider scaling resources if sustained degradation"
        ]
    else:
        result["recommendations"] = ["Service is operating within SLO targets"]

    return result


@mcp.tool()
def list_services() -> Dict:
    """
    List all services being monitored with their current health status.

    Returns:
        List of services with real-time health indicators

    Production Enhancement:
    - Integration with service discovery (Consul, etcd, Kubernetes API)
    - Health check aggregation from multiple sources
    - Dependency graph visualization data
    """
    services_status = []

    for service in get_service_list():
        current = get_current_metrics(service)
        services_status.append({
            "name": service,
            "status": current.get("status", "UNKNOWN"),
            "cpu": current["metrics"]["cpu_percent"],
            "memory": current["metrics"]["memory_percent"],
            "error_rate": current["metrics"]["error_rate"]
        })

    return {
        "total_services": len(services_status),
        "healthy": sum(1 for s in services_status if s["status"] == "OK"),
        "warning": sum(1 for s in services_status if s["status"] == "WARNING"),
        "services": services_status
    }


@mcp.tool()
def detect_anomalies(
    service: str,
    metric: str,
    sensitivity: float = 2.0
) -> Dict:
    """
    Detect anomalies in telemetry data using statistical analysis.

    Args:
        service: Service to analyze
        metric: Metric to check for anomalies
        sensitivity: Standard deviations for anomaly detection (default: 2.0)

    Returns:
        List of detected anomalies with timestamps and severity

    Algorithm: Simple statistical outlier detection
    Production: Would use ML models (Prophet, LSTM, Isolation Forest)

    Integration Point:
    - In real implementation, this would connect to Kafka streams
    - Process metrics in real-time using Flink/Kafka Streams
    - Generate alerts via PagerDuty/Opsgenie when anomalies detected
    """
    if service not in get_service_list():
        return {"error": f"Service '{service}' not found"}

    # Get 24 hours of data
    data_points = generate_sample_metrics(service, metric, hours=24)
    values = [d["value"] for d in data_points]

    # Calculate statistics
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std_dev = variance ** 0.5

    # Detect anomalies
    threshold_upper = mean + (sensitivity * std_dev)
    threshold_lower = mean - (sensitivity * std_dev)

    anomalies = []
    for point in data_points:
        value = point["value"]
        if value > threshold_upper or value < threshold_lower:
            severity = "HIGH" if abs(value - mean) > 3 * std_dev else "MEDIUM"
            anomalies.append({
                "timestamp": point["timestamp"],
                "value": value,
                "deviation": round(abs(value - mean) / std_dev, 2),
                "severity": severity
            })

    return {
        "service": service,
        "metric": metric,
        "analysis_period_hours": 24,
        "baseline_mean": round(mean, 2),
        "baseline_std_dev": round(std_dev, 2),
        "threshold_upper": round(threshold_upper, 2),
        "threshold_lower": round(threshold_lower, 2),
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies[-10:] if anomalies else []  # Last 10 anomalies
    }


# ============================================================================
# MCP RESOURCES - Data sources that agents can read
# ============================================================================

@mcp.resource("telemetry://services/{service}/metrics/{metric}")
def get_metric_resource(service: str, metric: str) -> str:
    """
    Resource providing access to telemetry data via URI pattern.

    MCP Resources are application-controlled (not model-controlled).
    The host application decides when to fetch resources and include them
    in the agent's context.

    URI Pattern: telemetry://services/{service}/metrics/{metric}

    Example URIs:
    - telemetry://services/api-gateway/metrics/cpu
    - telemetry://services/database-primary/metrics/memory
    """
    if service not in get_service_list():
        return f"Error: Service '{service}' not found"

    data = generate_sample_metrics(service, metric, hours=1)
    latest = data[-1]

    return f"""Service: {service}
Metric: {metric}
Current Value: {latest['value']} {latest['unit']}
Timestamp: {latest['timestamp']}
Status: {'NORMAL' if latest['value'] < 80 else 'ELEVATED'}

Last Hour Trend:
{chr(10).join(f"  {d['timestamp']}: {d['value']}" for d in data[-6:])}
"""


@mcp.resource("telemetry://sli-report")
def get_sli_report() -> str:
    """
    Generate comprehensive SLI compliance report for all services.

    This resource provides a high-level overview that can be included
    in the agent's context for answering questions about overall
    system health.

    Production Usage:
    - Scheduled report generation (daily/weekly)
    - Executive dashboards
    - Compliance documentation for audits
    """
    report_lines = [
        "=" * 60,
        "SLI COMPLIANCE REPORT",
        f"Generated: {datetime.utcnow().isoformat()}",
        "=" * 60,
        ""
    ]

    total_healthy = 0
    total_degraded = 0

    for service in get_service_list():
        cpu_sli = calculate_sli_compliance(service, "cpu", 80.0, 24)

        report_lines.append(f"Service: {service}")
        report_lines.append(f"  CPU SLI: {cpu_sli['compliance_percentage']}% (Target: 99%)")
        report_lines.append(f"  Status: {cpu_sli['status']}")
        report_lines.append("")

        if cpu_sli['status'] == "HEALTHY":
            total_healthy += 1
        else:
            total_degraded += 1

    report_lines.extend([
        "=" * 60,
        f"Summary: {total_healthy} healthy, {total_degraded} degraded",
        "=" * 60
    ])

    return "\n".join(report_lines)


# ============================================================================
# SECURITY & PRODUCTION CONSIDERATIONS
# ============================================================================

"""
Production Security Implementation:

1. AUTHENTICATION & AUTHORIZATION
   - OAuth 2.1 with PKCE for user authentication
   - Service account tokens for agent-to-server communication
   - Role-Based Access Control (RBAC):
     * DevOps: Full access to all services
     * Developers: Access only to their team's services
     * Read-only: Metrics viewing only, no tool invocation

2. AUDIT LOGGING
   from datetime import datetime

   def audit_log(user_id: str, action: str, resource: str, result: str):
       log_entry = {
           "timestamp": datetime.utcnow().isoformat(),
           "user_id": user_id,
           "action": action,
           "resource": resource,
           "result": result,
           "ip_address": request.remote_addr,
           "session_id": session.id
       }
       # Send to SIEM (Splunk, ELK, Datadog)
       siem_client.log(log_entry)

3. RATE LIMITING
   from functools import wraps
   from time import time

   request_counts = {}

   def rate_limit(max_requests: int, window_seconds: int):
       def decorator(func):
           @wraps(func)
           def wrapper(*args, **kwargs):
               user_id = get_current_user_id()
               now = time()

               if user_id not in request_counts:
                   request_counts[user_id] = []

               # Remove old requests outside window
               request_counts[user_id] = [
                   t for t in request_counts[user_id]
                   if now - t < window_seconds
               ]

               if len(request_counts[user_id]) >= max_requests:
                   raise RateLimitExceeded(
                       f"Max {max_requests} requests per {window_seconds}s"
                   )

               request_counts[user_id].append(now)
               return func(*args, **kwargs)
           return wrapper
       return decorator

   # Apply to tools:
   # @rate_limit(max_requests=100, window_seconds=60)
   # @mcp.tool()
   # def query_historical_metrics(...):

4. DATA CLASSIFICATION
   - Public: Service names, metric types
   - Internal: Aggregated statistics
   - Confidential: Detailed metrics, error messages
   - Restricted: Security-related metrics, access logs

   Apply field-level masking based on user role.

5. INTEGRATION WITH KAFKA (Hybrid Architecture)

   from confluent_kafka import Consumer, Producer

   # Real-time metrics consumer
   kafka_consumer = Consumer({
       'bootstrap.servers': 'kafka-broker:9092',
       'group.id': 'mcp-telemetry-server',
       'auto.offset.reset': 'latest'
   })

   kafka_consumer.subscribe(['telemetry-metrics'])

   # Process real-time data
   def process_kafka_stream():
       while True:
           msg = kafka_consumer.poll(1.0)
           if msg is None:
               continue

           # Parse metric
           metric_data = json.loads(msg.value())

           # Update real-time cache (Redis)
           redis_client.setex(
               f"metric:{metric_data['service']}:{metric_data['type']}",
               300,  # 5 minute TTL
               json.dumps(metric_data)
           )

   # MCP tools query cached data for low-latency access
   # Kafka handles continuous high-volume ingestion
   # MCP provides on-demand agent access

6. ERROR HANDLING
   - Never expose internal error details to agents
   - Log full error traces internally
   - Return user-friendly error messages
   - Implement circuit breakers for downstream services

7. PERFORMANCE OPTIMIZATION
   - Connection pooling for database queries
   - Redis caching for frequently accessed metrics
   - Async I/O for concurrent tool invocations
   - Query result pagination for large datasets
   - Compression for large responses

8. MONITORING THE MONITOR
   - Track MCP server's own metrics (request rate, latency, errors)
   - Alert on server degradation
   - Maintain high availability (99.9%+ uptime SLO)
   - Load balancing across multiple MCP server instances
"""

# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    # In production, this would be deployed as:
    # - Docker container on Kubernetes
    # - AWS Lambda with HTTP transport
    # - Long-running process managed by systemd

    print("Starting Telemetry MCP Server...")
    print("Available tools:")
    print("  - get_current_metrics: Get latest metrics for a service")
    print("  - query_historical_metrics: Query time-series data")
    print("  - check_sli_compliance: Verify SLI/SLO compliance")
    print("  - list_services: List all monitored services")
    print("  - detect_anomalies: Identify metric anomalies")
    print("\nAvailable resources:")
    print("  - telemetry://services/{service}/metrics/{metric}")
    print("  - telemetry://sli-report")
    print("\nServer ready. Connect using MCP client (Claude Desktop, etc.)")

    # Start server
    mcp.run()
