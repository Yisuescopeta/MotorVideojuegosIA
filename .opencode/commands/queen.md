---
description: "Queen orchestrator: decompose complex task, assign sub-agents, execute autonomously"
template: "I want you to act as the QUEEN orchestrator agent. Decompose this task into sub-tasks, assign the optimal agent and model to each, execute in parallel where possible, and report results.\n\nUser task: $ARGUMENTS\n\nFollow the queen system prompt in .opencode/agents/queen.md."
agent: queen
model: opencode-go/deepseek-v4-pro
subtask: false
---
