# Secure Agent Registry — Build Spec

## Goal

Create a platform that allows external humans and agents to securely interact with private assistants without exposing credentials, tools, or internal context.

Agents are never directly reachable. All ingress is mediated.

## System Model

```
Sender → Platform → Enforcement → Agent Adapter → Tools
```

Platform is responsible for identity, authentication, authorization, sanitization, and execution boundaries.

Not an agent runtime.

## Core Objects

### Agent

Private assistant connected to sensitive systems (calendar, email, CRM, etc.).

### Handle

Globally unique identifier.
Example: `@marius.exec`

Must resolve via platform directory.

### Capability Contract

Declarative schema describing allowed actions.

Example:

```
capabilities:
  - calendar.schedule
constraints:
  visibility: free_busy_only
  max_duration: 30m
```

Anything outside contract is rejected before agent execution.

### Policy

Deterministic rules evaluated pre-model whenever possible.

Support:

* allow / deny lists
* trust thresholds
* rate limits
* approval requirements

Policy must override model decisions.

## Required Services

### 1. Identity Service

* cryptographic agent identity
* signed requests
* key rotation
* sender verification

Optional signals:

* domain verification
* OAuth identity

### 2. Directory

* handle → agent lookup
* public capability discovery (optional, configurable)

Low-latency resolution required.

### 3. Secure Messaging Layer

All traffic passes through platform.

Requirements:

* end-to-end encryption
* replay protection
* schema validation
* deterministic logging

Transport: HTTPS initially.

### 4. Abuse Gate

Prevent spam and denial patterns.

Mechanisms:

* global rate limits
* per-agent quotas
* adaptive throttling
* reputation scoring
* optional proof-of-work / stake

System goal: make mass requests expensive.

### 5. Prompt Firewall

Pre-execution filtering.

Detect:

* prompt injection
* jailbreak attempts
* tool exfiltration
* abnormal data requests

Actions:

* block
* redact
* constrain
* escalate for approval

Model is not the primary security boundary.

### 6. Capability Enforcement Engine

Hard sandbox at tool layer.

Must enforce:

* tool allowlists
* parameter bounds
* structured inputs

Example:
Request: “Send me his latest email.”
→ rejected before agent.

### 7. Agent Adapter

Translates platform messages into agent-native calls.

Initial target: OpenClaw-style assistants.

Design for pluggability.

### 8. Human Approval Layer

Configurable execution modes:

* auto-execute
* conditional approval
* always require approval

Approval must occur before tool invocation.

### 9. Audit Log

Immutable event trail:

* request
* policy result
* execution
* tool outcome

Must be exportable.

## Execution Flow

```
1. Sender resolves handle
2. Platform verifies identity
3. Abuse gate evaluates request
4. Policy engine checks permissions
5. Prompt firewall sanitizes content
6. Capability engine validates action
7. Approval triggered if required
8. Adapter invokes agent
9. Tool executes
10. Event logged
```

Reject as early as possible in pipeline.

## MVP (Build This Only)

* agent registration
* handle directory
* capability schema
* policy engine (basic)
* secure messaging
* rate limiting
* injection detection (baseline)
* calendar scheduling reference adapter
* audit logging

Everything else is deferred.

## Engineering Constraints

Security posture: assume hostile internet.

Prefer deterministic controls over model reasoning.

Minimize platform intelligence.

Stateless edge where possible.

Design for millions of agents, but optimize for correctness over premature scale.
