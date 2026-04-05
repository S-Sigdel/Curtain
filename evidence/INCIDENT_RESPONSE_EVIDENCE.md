# Incident Response Quest Evidence
We have completed the incident response quest up to the Gold level. This document captures the evidence for each level and demonstrates the incident response measures implemented in our system.

## Bronze Evidence
Below is a screenshot of the JSON logs produced by this program. These logs are not limited to these commands; this is only a small example from a larger sample.
![Incident Response Logs](../docs/images/incident_response/Bronze_incident_JSON_logs.png)

To view logs without SSH see the instructions on: [./docs/OBSERVABILITY.md](../docs/OBSERVABILITY.md)

Below is a screenshot of the metrics page.
![Metrics Page](../docs/images/incident_response/Bronze_incident_metrics.png)


## Silver Evidence
We will show the live demo in our project submission video, where we receive the alert in our Discord server.

Below is a screenshot of the alert logic configuration located in [./monitoring/alerts.yml](../monitoring/alerts.yml).
![Alert Config](../docs/images/incident_response/Silver_Incident_alert_logic.png)


## Gold Evidence
Below is a screenshot of our Grafana dashboard while we were simulating users with `k6`.
![Grafana Dashboard](../docs/images/incident_response/Gold_incident_dashboard_grafana.png)

Runbook: [./docs/RUNBOOK.md](../docs/RUNBOOK.md)

### How do we find the root cause of a problem using the Grafana dashboard?
We can use the Grafana dashboard to spot failure patterns first, such as collapsed traffic, dropped saturation, and a spike in error rate. Next, we correlate those time windows with application and container logs to identify which service started failing first. We also compare latency, error rate, and resource usage panels together to confirm whether the issue is caused by traffic load, code behavior, or infrastructure limits.

Also refer to [./docs/DIAGNOST_ERRORS.md](../docs/DIAGNOST_ERRORS.md) for more information.