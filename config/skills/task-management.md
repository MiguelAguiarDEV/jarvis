---
name: task-management
description: "Task CRUD operations via markers. Trigger: create, list, complete, or manage tasks."
always: false
triggers: ["task", "tarea", "crear", "completar", "listar", "pendiente", "todo"]
---

# Task Management

You can manage tasks. When the user asks you to do something that requires tracking, create a task.

Available task actions (use these exact JSON formats in your response):
- To create a task, include: [TASK:CREATE] {"title":"...","description":"...","project":"...","priority":"medium"}
- To list tasks, include: [TASK:LIST] {"status":"open","limit":10}
- To complete a task, include: [TASK:DONE] {"id":123}

Always confirm task actions with the user in your response text.
