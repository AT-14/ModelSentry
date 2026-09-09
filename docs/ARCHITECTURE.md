# ModelSentry architecture and threat model

## Business deployment

The buyer is a government AI-platform or security-operations team operating
proprietary prediction APIs. ModelSentry replaces manual log review and augments
basic rate limiting with stateful, model-aware evidence.

```mermaid
flowchart LR
    C[API client] -->|image + API key| G[FastAPI gateway]
    G --> V[Protected CNN]
    V -->|label, confidence, embedding| M[Stateful monitor]
    M --> R[Risk and acquisition score]
    R --> P{Policy}
    P -->|low| A[Allow]
    P -->|suspicious| O[Observe / remove probabilities]
    P -->|high| T[Throttle]
    P -->|critical| B[Block]
    M --> S[(SQLite evidence)]
    S --> D[Analyst dashboard]
```

## Attack sequence

```mermaid
sequenceDiagram
    participant X as Extractor
    participant API as Protected API
    participant M as ModelSentry
    participant S as Surrogate
    X->>API: Carefully selected query
    API->>M: Input embedding + internal output
    M->>M: Update rolling per-key evidence
    API-->>X: Label / probabilities while allowed
    X->>S: Add input-output training pair
    X->>API: Boundary-seeking query
    M->>API: Throttle or block after persistent evidence
    API-->>X: Restricted or denied response
```

## Detection signals

| Signal | Security interpretation |
|---|---|
| Query rate | Sustained or accelerated harvesting |
| Embedding diversity | Broad exploration of the input domain |
| Sequential distance | Structured perturbation or search behavior |
| Boundary frequency | Concentration on information-rich uncertain outputs |
| Class coverage | Systematic exploration of output behavior |
| Acquisition proxy | Novelty multiplied by boundary value and output richness |

Each signal is converted to an empirical percentile using benign reference
traffic. Enforcement requires persistent, simultaneous extremes rather than one
unusual request.

## Security assumptions

| Assumption | Included |
|---|---|
| Black-box access to owned API | Yes |
| Returned hard labels or probabilities | Yes |
| Different surrogate architecture | Yes |
| Direct weight or database access | No |
| Account rotation / Sybil coordination | Future work |
| Production traffic drift | Future work |

## Privacy boundary

The monitor requires embeddings and output statistics but does not need to retain
raw images. A production implementation should encrypt telemetry, isolate tenants,
apply retention limits, and restrict analyst access.
