# Reliability Engineering Quest Evidence

This document maps the current Curtain implementation to the Reliability Engineering quest tiers and links the supporting documentation for each tier.

## Bronze Evidence

Bronze is about proving the service works before shipping: unit tests, automated CI checks, and a health endpoint.

Below are the GitHub Actions CI logs showing passing tests after every push.
![Reliability CI Logs](../docs/images/reliability/bronze_reliable_githubactions.png)

Below is an image of pytest running and completing the project test suite.
![Reliability Unit and Integration tests](../docs/images/reliability/bronze_reliable_pytest.png)

Below is image evidence of a working `GET /health` endpoint.
![Reliability Health Endpoint](../docs/images/reliability/bronze_reliable_health_endpoint.png)

Relevant docs:

- [../README.md](../README.md) documents how to run the test suite and verify the service health endpoint.
- [../docs/API_EXAMPLES.md](../docs/API_EXAMPLES.md) includes a simple `GET /health` example for endpoint verification.

## Silver Evidence

Silver is about stopping bad code from reaching production: coverage, integration testing, blocked deploys, and documented error handling.

Below is the coverage report showing coverage above the required threshold.
![Reliability Test Coverage](../docs/images/reliability/reliable_test_coverage.png)

Below is a screenshot of GitHub Actions blocking deployment due to a failed test.
![Failed Test Blocked Deploy](../docs/images/reliability/silver_reliable_deploy_block_fail_test.png)

Relevant docs:

- [../docs/ERROR_HANDELING.md](../docs/ERROR_HANDELING.md) explains the current 404, 422, and 500 error behavior and the JSON error shapes returned by the app.
- [../docs/API_EXAMPLES.md](../docs/API_EXAMPLES.md) shows request and response examples that support API-level integration testing.
- [../README.md](../README.md) documents the pytest and coverage commands used to verify the suite locally and in Docker.

## Gold Evidence

Gold is about graceful failure under bad inputs, survivability when processes die, and explicit failure-mode documentation.

We will show the live demos in the submission demo video:

- killing the app container and watching Docker restart it because the compose services use `restart: always`
- sending bad inputs and observing clean JSON error responses instead of stack traces

Relevant docs:

- [../docs/FAILURE_MODES.md](../docs/FAILURE_MODES.md) documents what happens when dependencies fail, inputs are invalid, or containers crash.
- [../docs/ERROR_HANDELING.md](../docs/ERROR_HANDELING.md) documents the graceful JSON error behavior for invalid requests and unhandled exceptions.
- [../docs/RUNBOOK.md](../docs/RUNBOOK.md) explains the operational checks and recovery steps used when the service or one of its instances fails.
