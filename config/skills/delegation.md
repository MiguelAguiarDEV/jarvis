---
name: delegation
description: "Sub-agent delegation via OpenCode serve. Trigger: delegate, run code, execute in project."
always: false
triggers: ["delegate", "delegar", "ejecutar", "opencode", "sub-agent"]
---

# Sub-Agent Delegation

For actual work (analyze code, fix bugs, read files, investigate): delegate.

Format: [DELEGATE] {"task":"description","project":"optional project name"}

The sub-agent can read files, run commands, and make changes. Results return to you.
Only delegate work needing file/code access -- not simple questions.
