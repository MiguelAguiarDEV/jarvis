---
name: delegation
description: "Sub-agent delegation via OpenCode serve. Trigger: delegate work, run code, execute in project."
always: false
triggers: ["delegate", "delegar", "ejecutar", "opencode", "sub-agent"]
---

# Sub-Agent Delegation

When the user asks you to do actual work (analyze code, fix bugs, read files, investigate issues), delegate to a sub-agent.

To delegate work: [DELEGATE] {"task":"description of what to do","project":"optional project name"}

The sub-agent can read files, run commands, and make changes. You will receive the results.
Do NOT delegate simple questions or conversations -- only actual work that needs file/code access.
