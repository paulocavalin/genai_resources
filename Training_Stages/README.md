# LLM Training Stages

An interactive, self-contained HTML animation that walks through the three major stages of training a Large Language Model.

## How to open

Just open `llm_training.html` directly in any modern browser — no server or dependencies required.

## Controls

| Control | Description |
|---|---|
| **Stage tabs** | Jump directly to Pre-training, SFT, or RLHF |
| **Play / Pause** | Halt or resume all animations |
| **Progress bar** | Shows time remaining before auto-advancing to the next stage (18s per stage) |

Stages cycle automatically and loop back to Stage 1.

---

## Stages

### Stage 1 — Pre-training (Self-supervised Learning)

The foundation of every LLM. The model is exposed to a massive corpus of raw text and learns to predict the next token at each position.

**What the animation shows:**
- A live token stream feeding raw corpus text into the model
- A transformer block diagram (Input Embeddings → Multi-Head Attention → Add & Norm → FFN → Softmax) with blinking activity indicators
- A next-token prediction cycle: the model receives a context, a token is masked, the model predicts it, and the actual token is revealed — cycling through multiple examples
- A loss curve that draws on screen and a live Loss/Step counter ticking downward as training progresses

**Key concepts:** Tokenization, Next Token Prediction, Gradient Descent, Unsupervised corpus

---

### Stage 2 — Supervised Fine-tuning (SFT)

After pre-training, the model is fine-tuned on a smaller, curated dataset of (instruction, response) pairs to align it with desired behaviour.

**What the animation shows:**
- Instruction/response pairs sliding in sequentially, colour-coded by role (blue = instruction, teal = target response)
- A side-by-side contrast between pre-training (raw web data, high volume, lower quality) and SFT (curated pairs, lower volume, high quality)
- A weight grid where individual cells light up as gradient descent updates the model parameters

**Key concepts:** Instruction tuning, Cross-entropy Loss, Curated data, Fine-tuned Weights

---

### Stage 3 — RLHF (Reinforcement Learning from Human Feedback)

The final alignment stage. The model learns from human preferences rather than fixed labels.

**What the animation shows:**
- **Panel 1 — Generation:** the policy model produces multiple ranked response candidates (A, B, C) for the same prompt
- **Panel 2 — Human ranking:** a human rater panel provides thumbs up/down feedback and a preference strength signal
- **Panel 3 — Reward model + PPO:** a reward model scores new outputs and a PPO (Proximal Policy Optimization) update is applied, including a KL Divergence penalty bar to prevent the policy from drifting too far from the SFT baseline
- A policy improvement chart showing reward scores climbing across four RLHF iterations from the SFT baseline

**Key concepts:** Policy Model, Reward Model, Human Preference, PPO, KL Divergence

---

## Visual design

Matches the dark theme used across this project (`agentic_flow.html`):

| Token | Colour |
|---|---|
| Background | `#0f1117` / `#1a1d27` |
| Borders | `#2e3248` |
| Blue (instructions) | `#3b82f6` |
| Purple (model) | `#a855f7` |
| Teal (responses) | `#10b981` |
| Amber (warnings) | `#f59e0b` |
| Cyan (scores) | `#06b6d4` |
