# race-mechanics

A local question-answering assistant for Uma Musume (global) skills and race
mechanics, running entirely on your own PC.

The language model never does the maths. Questions are answered in three steps:

1. **Understand** the question in code: skill names, CM number, running style,
   stamina / recovery values (fuzzy matched, typo tolerant).
2. **Compute** every number with deterministic calculators (skill trigger
   windows per course, acceleration ratings, the stamina / HP model) and
   **retrieve** the relevant passages from a curated mechanics knowledge pack.
3. **Phrase** the answer with one call to a local model (Ollama), which is told
   to use only numbers from that context and to say so when it doesn't know.

Status: early development. See the issues and milestones for the plan.
