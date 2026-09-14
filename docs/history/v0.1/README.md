# eTPS — Effective Tokens Per Second
**A quality-adjusted throughput metric for local AI inference.**

> Spec v0.1 | Author: Joshua Holliday / True Vector Media | License: MIT

---

## The Problem With Raw TPS

Raw tokens per second tells you how fast a model generates tokens. It doesn't tell you whether those tokens were useful.

A model that generates 80 TPS but hallucinates, requires correction rounds, and reconstructs context every session may deliver *less* value than a 25 TPS model with persistent memory and high first-pass accuracy.

Marketing TOPS numbers have the same problem. Intel's 99 platform TOPS sounds better than AMD's 80 — until you realize 77 of Intel's TOPS come from the GPU running at full power draw, while AMD's NPU delivers AI inference at a fraction of the thermal cost. The number obscures more than it reveals.

**eTPS fixes this.** It measures effective progress toward a useful answer, not raw generation speed.

---

## The Formula

```
eTPS = TPS_raw × Efficiency × Quality × Continuity
```

| Component | Measures | Range |
|---|---|---|
| **TPS_raw** | Raw token generation speed | Hardware dependent |
| **Efficiency** | Token waste ratio (corrections, reconstruction, refusals) | 0.0 – 1.0 |
| **Quality** | Answer correctness, hallucination penalties, task completion | 0.1 – 1.0 |
| **Continuity** | Context retention across multi-turn sessions | 0.0 – 1.0 |

**Key design decision:** Efficiency and Quality are independent axes. Correction rounds affect Quality only. Token waste affects Efficiency only. The same event is never penalized twice.

---

## What eTPS Penalizes

- Hallucinations (confirmed)
- Correction rounds required to reach a usable answer
- Context reconstruction — re-explaining facts the model should already know
- Task failure
- Unprompted refusals on valid tasks

## What eTPS Rewards

- First-pass accuracy
- Context retention across turns
- Efficient token use
- Session continuity

---

## Complementary Metrics

eTPS is designed to work alongside two companion metrics:

**Raw TPS** — baseline generation speed. eTPS without TPS_raw context is incomplete.

**SEIT (Sustained Effective Inference Throughput)** — power-normalized sustained throughput:

```
SEIT = (Sustained TPS × Quality Factor) / Watts
```

SEIT exposes thermal efficiency under load — the gap between peak and sustained eTPS reveals throttling, memory pressure, and system stability. This is where platform TOPS marketing claims collapse under real-world conditions.

---

## Repo Structure

```
eTPS/
├── scorer.py           # Core formula — pure math, no I/O, fully testable
├── logger.py           # SQLite persistence — WAL mode, versioned schema
├── task_validator.py   # First benchmark task — run against live endpoint
├── CLAUDE.md           # Claude Code context file
└── README.md
```

---

## Quick Start

```bash
# 1. Install dependency
pip install openai

# 2. Validate the scorer (no API needed)
python scorer.py

# 3. Validate the logger (no API needed)
python logger.py

# 4. Run your first benchmark (requires local inference endpoint)
python task_validator.py \
  --base-url http://localhost:1234/v1 \
  --model your-model-name \
  --runs 3
```

Compatible with any OpenAI-compatible local inference server — LM Studio, Ollama, vLLM, llama.cpp server.

---

## Hardware Declaration

All published benchmark results require a full hardware declaration:

| Field | Required | Notes |
|---|---|---|
| CPU model | Yes | |
| GPU / iGPU | Yes | |
| VRAM (GB) | If applicable | |
| RAM (GB) | Yes | |
| RAM channels | Yes | Single vs dual channel materially affects iGPU inference |
| NPU TOPS | If applicable | |
| Cooling | Yes | Active / passive / sustained thermal state |
| Backend + version | Yes | llama.cpp, LM Studio, Ollama, etc. |
| Model + quantization | Yes | |
| MTP enabled | Yes | |
| Memory system | Yes | none / vector_store / other |

Results without full hardware declaration are not eligible for the public leaderboard.

---

## User Data and Community

eTPS is built to be more than a personal benchmark tool. The goal is a growing dataset of real-world inference performance across diverse hardware configurations — valuable for:

- Individual users tracking performance over time
- Hardware comparison across configurations
- Researchers studying local inference efficiency
- The broader AI community building on an open, reproducible standard

Submitted benchmark results contribute to a shared dataset. Aggregate, anonymized hardware and performance data helps drive spec development and community tooling. A registered profile (coming in v0.2) enables persistent history, public leaderboard presence, and hardware trend tracking over time.

---

## Spec Versioning

Penalty constants and formula structure are locked per spec version. Changing weights after publication invalidates prior comparisons. All results include a `spec_version` field.

Current: `v0.1` (pre-release — methodology validation phase)

First public release: `v1.0` (pending first reproducible benchmark results)

---

## Citation

```
Holliday, J. (2026). eTPS: Effective Tokens Per Second —
A Quality-Adjusted Throughput Metric for Local AI Inference.
True Vector Media. https://effectivetps.com/spec/v1
```

---

## Contributing

Benchmark result submissions, methodology feedback, and task corpus contributions welcome via GitHub Issues and Pull Requests.

See [CONTRIBUTING.md](CONTRIBUTING.md) for submission format and result validation requirements.

---

## Links

- Spec document: [effectivetps.com](https://effectivetps.com) *(coming soon)*
- True Vector Media: [truevectormedia.com](https://truevectormedia.com)
- Author: Joshua Holliday / [@axendo79](https://github.com/axendo79)

---

*eTPS is complementary to raw TPS, not a replacement. Both numbers matter. Neither alone tells the full story.*
