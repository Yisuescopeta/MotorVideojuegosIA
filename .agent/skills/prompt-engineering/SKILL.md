---
name: prompt-engineering
description: Design effective prompts for LLMs. This skill provides patterns and techniques to get the best results from AI models. Use it when writing prompts for features, agents, or tools.
license: MIT
---

# Prompt Engineering Patterns

## Core Principles

### 1. Clarity & Context
- **Explicit Instructions**: Be specific. "Write a short summary" is worse than "Write a 50-word summary".
- **Context Loading**: Provide necessary background info (schema, previous conversation, constraints) before the task.

### 2. Chain of Thought (CoT)
- **"Let's think step by step"**: Encourage the model to reason before answering.
- **Structure**: Ask for a plan or outline before the final code/text.

### 3. Few-Shot Learning
- **Examples**: Provide 2-3 examples of input -> desired output. This is the most powerful way to align style and format.
    - User: "Convert this to JSON."
    - Assistant: "..." (Bad)
    - User: "Convert this to JSON. Example: Input 'Name: John', Output {'name': 'John'}. Input 'Name: Jane'..." (Good)

### 4. Separation of Concerns
- **Delimiters**: Use `"""`, `---`, or XML tags `<data>` to separate instructions from input data.
    - "Summarize the text below wrapped in <text> tags."

## Advanced Patterns

### The "Persona" Pattern
"Act as a Senior Engineer..." sets the tone and expectation of competence.

### The "Refinement" Pattern
- Ask the model to critique its own work. "Generate a solution, then criticize it, then provide a better solution."

### The "Template" Pattern
- Force a specific output format. "Return ONLY a JSON object with fields { error: bool, message: string }."

## Common Pitfalls
- **Negative Constraints**: "Don't do X" is often ignored. Rephrase as "Do Y instead."
- **Ambiguity**: "Fix the code" -> "Fix the NullPointerException in line 45".
