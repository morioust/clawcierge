Best pattern: agent makes an outbound, long-lived connection to the platform. No inbound ports, no “expose my OpenClaw to the web” nonsense. The platform becomes the rendezvous + enforcement point.

Registration + reachability (minimal moving parts)

1) Agent bootstrap (one-time)
	•	Operator logs into platform UI.
	•	Creates agent + handle.
	•	Platform issues:
	•	agent_id
	•	agent credentials (pick one):
	•	mTLS client cert (best), or
	•	signed JWT via OIDC client creds, or
	•	an agent API key (worst; fine for MVP)
	•	optional: capability_contract upload + policy.

2) Agent “dials out” and stays connected

Agent starts a persistent session:
	•	Authenticate (mTLS preferred).
	•	Register capabilities hash/version.
	•	Keepalive + reconnect with backoff.
	•	Platform can now push inbound requests over that same channel.

So reachability = reverse tunnel semantics, but implemented at app layer.

⸻

Protocol choice: what you should use

If you want “don’t reinvent wheel” + strong defaults:

gRPC over HTTP/2 with bidirectional streaming + mTLS
	•	It’s basically the canonical “control plane talks to agents” protocol.
	•	Bi-di streaming gives you:
	•	server → agent push
	•	agent → server responses/events
	•	multiplexing, backpressure, retries
	•	Schemas via protobuf (less ambiguity than JSON).
	•	Plays well with Envoy, ALBs/NLBs (check your infra).

This is the closest thing to “obvious” here.

If you want simplest infra compatibility:

WebSocket (WSS)
	•	Also fine for MVP.
	•	Bi-directional, works everywhere, easy in JS/Python.
	•	You’ll implement more yourself (framing, retries, schema discipline).

If you ask “just open HTTPS streaming?”

If you mean SSE: it’s server → client only, so you still need POSTs back. Awkward for request/response + ack + cancellation.
If you mean HTTP/2 streaming: that’s basically reinventing gRPC poorly unless you adopt gRPC.

So: SSE = no, “raw HTTPS streaming” = use gRPC instead.

⸻

Concrete wire model (what actually flows)

Single long-lived stream per agent

AgentStream(agent_id, auth) returns a bi-di stream of envelopes:
	•	Platform → Agent:
	•	RequestReceived {request_id, sender_id, message, constraints, required_action_schema}
	•	CancelRequest {request_id}
	•	PolicyUpdate {policy_version}
	•	Agent → Platform:
	•	Ack {request_id}
	•	ProposedAction {request_id, action_type, params} (structured)
	•	ActionResult {request_id, status, metadata}
	•	Heartbeat {}

Key detail: agent should never execute “raw user prompt.” It executes structured actions after platform enforcement.

⸻

Auth: what to pick
	•	mTLS for the agent channel (strong, simple once set up).
	•	Layer OIDC/JWT inside if you want per-message claims.
	•	If you want battle-tested identity plumbing for services: SPIFFE/SPIRE (optional, later).

⸻

TL;DR recommendation
	•	MVP: WebSocket + JWT (fast to ship, works everywhere).
	•	“Best” / long-term: gRPC bi-di streaming over HTTP/2 + mTLS.

If you tell me your deployment target (AWS ALB/NLB? Cloudflare? Tailscale? Fly.io?), I’ll pick the exact variant that won’t fight your load balancer.