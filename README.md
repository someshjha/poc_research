# Research Lifecycle Assistant — real implementation

This is the real, running version of the [mock demo](https://someshjha.com/poc_physics_research_assistant/)
and its [write-up](https://someshjha.com/ai-research-assistant-physics-math.html): a
physics/math research assistant that walks a research question through six
real stages — literature retrieval, hypothesis/derivation, multi-provider
model comparison, numerical simulation, peer review, and write-up — backed
by live services running on a local [kind](https://kind.sigs.k8s.io/)
(Kubernetes-in-Docker) cluster.

Nothing here is mock data:

- **Literature** is fetched live from the public arXiv API and embedded
  locally with Ollama (`nomic-embed-text`), then stored and searched with
  `pgvector`.
- **Derivation, comparison, review, and write-up** are real calls to
  whichever models you configure — OpenAI, Anthropic, Google Gemini, xAI
  (Grok), and/or local Ollama models. No key for a provider just means it
  shows up as "not configured" in the UI instead of crashing anything else.
- **Simulation** is a real `numpy` diagonalization of the perturbed quantum
  harmonic oscillator Hamiltonian — not a canned number.
- The six stages are orchestrated as a **LangGraph `StateGraph`** (see
  `services/orchestrator/app/graph.py`), one node per stage, run through
  `astream()` so each stage's real output is persisted as it completes.

## Architecture

```
                     ┌──────────────┐
   browser  ───────▶ │ nginx ingress │
                     └──────┬───────┘
                            │
          ┌─────────────────┼───────────────────┐
          ▼                 ▼                    ▼
   ┌─────────────┐  ┌───────────────┐   ┌─────────────────┐
   │  frontend   │  │  orchestrator │──▶│     gateway      │
   │ (static UI) │  │ (LangGraph,   │   │ (OpenAI/Anthropic│
   └─────────────┘  │  FastAPI)     │   │  /Google/xAI/    │
                     └──────┬────────┘   │  Ollama adapters)│
                            │            └─────────┬────────┘
                 ┌──────────┼───────────┐          │
                 ▼          ▼           ▼          ▼
          ┌───────────┐ ┌─────────┐ ┌────────┐ ┌────────┐
          │ retrieval │ │simulation│ │postgres│ │ Ollama │
          │(arXiv +   │ │ (numpy   │ │+pgvector│ (host or │
          │ pgvector) │ │  physics)│ │        │  in-cluster)
          └───────────┘ └─────────┘ └────────┘ └────────┘
```

Every service is a small FastAPI app; the frontend is static HTML/JS served
by nginx. Nothing here needs a build step beyond `docker build`.

## Prerequisites

- Docker
- [`kind`](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- `kubectl`
- [Ollama](https://ollama.com), running locally, with at least one chat
  model and the `nomic-embed-text` embedding model pulled:
  ```bash
  ollama pull llama3.2:1b
  ollama pull nomic-embed-text
  ```

Real hosted providers (OpenAI, Anthropic, Google, xAI) are optional — the
system runs fully locally on Ollama alone. Add API keys later to unlock
each one.

## Run it

```bash
./scripts/up.sh
```

This creates a `kind` cluster named `research`, installs the nginx ingress
controller, builds and loads all five images into the cluster, and applies
the manifests in `k8s/`. Once it finishes, open **http://localhost:8081**.

By default the gateway and retrieval services reach your host machine's
Ollama at `http://host.docker.internal:11434` (works out of the box on
Docker Desktop for macOS/Windows). If that doesn't resolve on your setup,
deploy Ollama inside the cluster instead:

```bash
kubectl apply -f k8s/ollama-optional.yaml
# then edit k8s/configmap.yaml: OLLAMA_BASE_URL: "http://ollama:11434"
kubectl apply -f k8s/configmap.yaml
kubectl rollout restart deployment/gateway deployment/retrieval -n research
# pull a model inside the cluster's Ollama pod:
kubectl exec -n research deploy/ollama -- ollama pull llama3.2:1b
kubectl exec -n research deploy/ollama -- ollama pull nomic-embed-text
```

### Adding hosted provider keys

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
# edit k8s/secret.yaml and fill in the keys you have
kubectl apply -f k8s/secret.yaml
kubectl rollout restart deployment/gateway -n research
```

`k8s/secret.yaml` is gitignored — never commit real keys.

**If a hosted provider mysteriously 404s or hits the wrong host** when
running a service directly (outside `kind`/Docker), check your shell for a
pre-existing `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` / `GOOGLE_BASE_URL`.
Some local tools (including Claude's own desktop app) export
`ANTHROPIC_BASE_URL` in their environment for their own use, and it will
silently override this project's default (`.../v1`) if it's already set in
your shell — `env -u ANTHROPIC_BASE_URL` before running the service, or
unset it, if requests fail with an empty 404. This can't happen inside the
`kind` deployment, since pods don't inherit your shell's environment.

### Tear down

```bash
./scripts/down.sh
```

## Services

| Service        | Path                       | What it does |
|----------------|----------------------------|---------------|
| `gateway`      | `services/gateway`         | Unified `/v1/generate` and `/v1/compare` across OpenAI, Anthropic, Google, xAI, and Ollama |
| `retrieval`    | `services/retrieval`       | `/v1/ingest` (arXiv → embed → pgvector), `/v1/search` |
| `simulation`   | `services/simulation`      | `/v1/simulate` — real numerical diagonalization of H = H0 + λx⁴ |
| `orchestrator` | `services/orchestrator`    | LangGraph pipeline tying the six stages together, session state in Postgres |
| `frontend`     | `frontend/`                | Static UI: pick a question, models, and simulation parameters, then run and watch each stage fill in |

## Observability

Every run records exactly what the pipeline did — not a summary reconstructed
afterward, but a trace built as each LangGraph node executes: which service
it called, the exact request it sent, the exact response it got back, the
latency, and any error. This is stored as part of the session's state (see
`trace` in `services/orchestrator/app/graph.py`) and surfaced in the
frontend's **07 · Observability** tab, where every call can be expanded to
inspect the full prompt and response.

Two real bugs surfaced this way during testing against live provider keys:

- **Anthropic returning 0 characters with no error.** `claude-opus-5` has
  extended thinking on by default; with a short `max_tokens` budget it spent
  the entire budget "thinking" and returned zero answer text — a `200 OK`
  with an empty result, which would have been silently wrong without a trace
  showing the exact response. Fixed by disabling thinking for this
  assistant's plain-answer use case (`ANTHROPIC_THINKING=true` to opt back
  in), since raising `max_tokens` alone didn't help — thinking has no
  separate budget cap.
- **A full run finishing on the backend but never reaching the browser.** A
  six-stage run with several real hosted-model calls routinely takes 60-90+
  seconds; nginx ingress-nginx's default 60s `proxy-read-timeout` was cutting
  the connection mid-run, so the orchestrator finished and persisted the
  result, but the browser's request had already been dropped. Fixed by
  raising the timeout on the ingress (see `k8s/ingress.yaml`).

Both were found by reading the trace / reproducing against real keys, not by
inspection of the code — which is the point of building this in from day one
rather than adding "observability" as an afterthought.

## A note on model quality

The derivation, review, and write-up stages send their prompts to whatever
model you pick — including small local Ollama models (1-4B parameters).
Those are fast and need no API key, but a synthesis-heavy prompt like the
write-up stage (which asks the model to combine the derivation, simulation,
citations, and reviewer notes into a coherent section) can be genuinely too
much for a 1B model, sometimes producing near-empty output. That's a real
property of the model, not a bug in the pipeline — pick a larger local model
(e.g. `qwen3:8b`) or a hosted provider for the derivation/review/write-up
stages if you want stronger results; the small models are still fine for a
fast end-to-end smoke test of the pipeline itself.

## Local development without kind

Each service is a plain FastAPI app and can be run directly:

```bash
cd services/gateway
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
OLLAMA_BASE_URL=http://localhost:11434 .venv/bin/uvicorn app.main:app --port 8000
```

Point `RETRIEVAL_URL` / `SIMULATION_URL` / `GATEWAY_URL` / `DATABASE_URL`
env vars at wherever the other services are running (`docker run
pgvector/pgvector:pg16` works for Postgres).

## Relationship to the mock demo

The [mock demo](https://someshjha.com/poc_physics_research_assistant/) in
`someshjha.github.io` proved out the six-stage UI shape with fabricated
data. This repo replaces every fabricated piece with a real service, one
stage at a time, while keeping that same shape — see the write-up's
["Path to a real implementation"](https://someshjha.com/ai-research-assistant-physics-math.html)
section for the design reasoning behind each choice.
