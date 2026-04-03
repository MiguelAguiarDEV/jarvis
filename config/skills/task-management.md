---
name: task-management
description: "Task CRUD via markers. Trigger: create, list, complete, manage tasks."
always: false
triggers: ["task", "tarea", "crear", "completar", "listar", "pendiente", "todo"]
---

# Task Management

Create tasks when user requests require tracking.

Actions (use exact JSON):
- Create: [TASK:CREATE] {"title":"...","description":"...","project":"...","priority":"medium"}
- List: [TASK:LIST] {"status":"open","limit":10}
- Complete: [TASK:DONE] {"id":123}

Confirm each action in your response.
