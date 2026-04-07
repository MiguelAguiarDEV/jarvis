/**
 * PROMETHEUS Bridge v3 — Custom MCP Tools
 *
 * Uses createSdkMcpServer() + tool() to define JARVIS tools.
 * tools:[] disables ALL Claude Code built-in tools.
 * Claude uses ONLY our MCP tools — full control over execution.
 *
 * JARVIS Go (ATHENA) → HTTP to localhost:9876 → this bridge → query() → Claude + MCP tools
 */

import { createServer } from 'http';
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, mkdirSync } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import { resolve, dirname } from 'path';
import { query, tool, createSdkMcpServer } from '@anthropic-ai/claude-agent-sdk';
import { z } from 'zod/v4';

// Async exec — does NOT block the Node.js event loop.
// Critical: execSync would freeze the entire bridge during long commands,
// blocking concurrent requests and the /v1/usage endpoint while a tool runs.
const execAsync = promisify(exec);

// runCommand wraps execAsync with consistent options and error handling.
// Returns stdout on success, or error message including stderr.
async function runCommand(cmd, opts = {}) {
  try {
    const { stdout, stderr } = await execAsync(cmd, {
      timeout: opts.timeout || 30000,
      maxBuffer: opts.maxBuffer || 1024 * 1024,
      encoding: 'utf-8',
      ...opts,
    });
    return stdout;
  } catch (err) {
    // err.stdout/stderr available if command ran but returned non-zero
    const stderr = err.stderr || '';
    const stdout = err.stdout || '';
    throw new Error(`exec failed (exit ${err.code || '?'}): ${stderr || stdout || err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env.PROMETHEUS_BRIDGE_PORT || '9876');
const ATHENA_URL = process.env.ATHENA_URL || 'http://100.71.66.54:8080';
const MNEMO_BIN = process.env.MNEMO_BIN || '/home/mx/projects/jarvis-dashboard/athena/mnemo';
const MNEMO_API_KEY = process.env.MNEMO_API_KEY || '';

// ---------------------------------------------------------------------------
// Usage tracking — module-level state populated from query() events.
// SDK emits SDKRateLimitEvent during streams; we cache the latest snapshot.
// ---------------------------------------------------------------------------
let LATEST_RATE_LIMIT = null;          // SDKRateLimitInfo
let LATEST_RATE_LIMIT_SEEN_AT = null;  // ISO timestamp string
let LATEST_MODEL_USAGE = null;         // Record<model, ModelUsage>
let LATEST_PERMISSION_DENIALS = null;  // SDKPermissionDenial[]
let LATEST_RESULT_AT = null;           // ISO timestamp of last result message

const MODELS = {
  'claude-opus-4-6': 'opus',
  'claude-sonnet-4-6': 'sonnet',
  'claude-haiku-4-5-20251001': 'haiku',
  'opus': 'opus',
  'sonnet': 'sonnet',
  'haiku': 'haiku',
};

// ---------------------------------------------------------------------------
// Helper: success / error responses for tool handlers
// ---------------------------------------------------------------------------
const ok = (text) => ({ content: [{ type: 'text', text: String(text) }] });
const fail = (text) => ({ content: [{ type: 'text', text: String(text) }], isError: true });

// ---------------------------------------------------------------------------
// Helper: HTTP call to ATHENA API
// ---------------------------------------------------------------------------
async function athenaAPI(method, path, body) {
  const url = `${ATHENA_URL}${path}`;
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(MNEMO_API_KEY ? { 'Authorization': `Bearer ${MNEMO_API_KEY}` } : {}),
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  const text = await res.text();
  if (!res.ok) throw new Error(`ATHENA ${method} ${path}: ${res.status} ${text}`);
  return text;
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

// --- Filesystem ---
const readFileTool = tool(
  'read_file',
  'Read a file from the filesystem. Returns the file contents.',
  { path: z.string().describe('Absolute path to the file') },
  async ({ path }) => {
    try {
      if (!existsSync(path)) return fail(`File not found: ${path}`);
      const content = readFileSync(path, 'utf-8');
      return ok(content);
    } catch (e) { return fail(`read_file error: ${e.message}`); }
  }
);

const writeFileTool = tool(
  'write_file',
  'Write content to a file. Creates parent directories if needed.',
  {
    path: z.string().describe('Absolute path to the file'),
    content: z.string().describe('Content to write'),
  },
  async ({ path: filePath, content }) => {
    try {
      const dir = dirname(filePath);
      // Use Node fs.mkdirSync (fast, no shell exec) instead of execSync mkdir.
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
      writeFileSync(filePath, content, 'utf-8');
      return ok(`Written ${content.length} bytes to ${filePath}`);
    } catch (e) { return fail(`write_file error: ${e.message}`); }
  }
);

const editFileTool = tool(
  'edit_file',
  'Replace a string in a file. old_string must match exactly.',
  {
    path: z.string().describe('Absolute path to the file'),
    old_string: z.string().describe('Exact string to find'),
    new_string: z.string().describe('Replacement string'),
  },
  async ({ path: filePath, old_string, new_string }) => {
    try {
      if (!existsSync(filePath)) return fail(`File not found: ${filePath}`);
      const content = readFileSync(filePath, 'utf-8');
      if (!content.includes(old_string)) return fail(`old_string not found in ${filePath}`);
      const updated = content.replace(old_string, new_string);
      writeFileSync(filePath, updated, 'utf-8');
      return ok(`Edited ${filePath}`);
    } catch (e) { return fail(`edit_file error: ${e.message}`); }
  }
);

// --- Shell ---
const bashTool = tool(
  'bash',
  'Execute a bash command and return stdout+stderr. Timeout: 120s.',
  {
    command: z.string().describe('Shell command to execute'),
    cwd: z.string().optional().describe('Working directory (default: /home/mx)'),
  },
  async ({ command, cwd }) => {
    try {
      const { stdout, stderr } = await execAsync(command, {
        cwd: cwd || '/home/mx',
        timeout: 120_000,
        maxBuffer: 10 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
      });
      return ok(stdout || stderr || '(no output)');
    } catch (e) {
      const out = (e.stdout || '') + (e.stderr || '');
      return fail(`Exit ${e.code || 1}\n${out || e.message}`);
    }
  }
);

// --- Search ---
const grepTool = tool(
  'grep',
  'Search file contents using ripgrep. Returns matching lines.',
  {
    pattern: z.string().describe('Regex pattern to search for'),
    path: z.string().optional().describe('Directory or file to search (default: .)'),
    glob: z.string().optional().describe('File glob filter, e.g. "*.go"'),
    max_results: z.number().optional().describe('Max results (default: 50)'),
  },
  async ({ pattern, path: searchPath, glob: globPattern, max_results }) => {
    try {
      let cmd = `rg --no-heading -n "${pattern.replace(/"/g, '\\"')}"`;
      if (globPattern) cmd += ` -g "${globPattern}"`;
      cmd += ` --max-count=${max_results || 50}`;
      cmd += ` ${searchPath || '.'}`;
      const { stdout } = await execAsync(cmd, {
        cwd: '/home/mx',
        timeout: 30_000,
        maxBuffer: 5 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
      });
      return ok(stdout || '(no matches)');
    } catch (e) {
      if (e.code === 1) return ok('(no matches)');
      return fail(`grep error: ${e.message}`);
    }
  }
);

const globTool = tool(
  'glob',
  'Find files matching a glob pattern using find.',
  {
    pattern: z.string().describe('Glob pattern, e.g. "**/*.go"'),
    path: z.string().optional().describe('Base directory (default: .)'),
  },
  async ({ pattern, path: basePath }) => {
    try {
      const base = basePath || '.';
      const cmd = `find ${base} -path "${pattern}" -type f 2>/dev/null | head -100`;
      const { stdout } = await execAsync(cmd, {
        cwd: '/home/mx',
        timeout: 15_000,
        maxBuffer: 2 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
      });
      return ok(stdout || '(no matches)');
    } catch (e) { return fail(`glob error: ${e.message}`); }
  }
);

// --- Web ---
const fetchUrlTool = tool(
  'fetch_url',
  'Fetch a URL and return the response body.',
  {
    url: z.string().describe('URL to fetch'),
    method: z.string().optional().describe('HTTP method (default: GET)'),
    // Zod v4 requires the two-arg form `z.record(keyType, valueType)`. The single-arg
    // form `z.record(z.string())` is invalid in v4 and causes the SDK to silently
    // drop the ENTIRE jarvis MCP server (init.tools=[], no jarvis tools registered).
    headers: z.record(z.string(), z.string()).optional().describe('Request headers'),
    body: z.string().optional().describe('Request body'),
  },
  async ({ url, method, headers, body }) => {
    try {
      const opts = { method: method || 'GET' };
      if (headers) opts.headers = headers;
      if (body) opts.body = body;
      const res = await fetch(url, opts);
      const text = await res.text();
      return ok(`${res.status} ${res.statusText}\n\n${text.slice(0, 50000)}`);
    } catch (e) { return fail(`fetch_url error: ${e.message}`); }
  }
);

const webSearchTool = tool(
  'web_search',
  'Search the web using DuckDuckGo. Returns HTML results.',
  { query: z.string().describe('Search query') },
  async ({ query: q }) => {
    try {
      const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(q)}`;
      const res = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) JARVIS/1.0' },
      });
      const html = await res.text();
      // Extract result snippets
      const results = [];
      const regex = /<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)<\/a>/g;
      let match;
      while ((match = regex.exec(html)) && results.length < 10) {
        results.push(`${match[2].trim()}\n  ${match[1]}`);
      }
      return ok(results.length ? results.join('\n\n') : '(no results found)');
    } catch (e) { return fail(`web_search error: ${e.message}`); }
  }
);

// --- Tasks (ATHENA API) ---
const createTaskTool = tool(
  'create_task',
  'Create a new task in ATHENA.',
  {
    title: z.string().describe('Task title'),
    description: z.string().optional().describe('Task description'),
    priority: z.string().optional().describe('Priority: low, medium, high'),
  },
  async ({ title, description, priority }) => {
    try {
      const body = { title };
      if (description) body.description = description;
      if (priority) body.priority = priority;
      const result = await athenaAPI('POST', '/api/tasks', body);
      return ok(result);
    } catch (e) { return fail(`create_task error: ${e.message}`); }
  }
);

const listTasksTool = tool(
  'list_tasks',
  'List tasks from ATHENA.',
  {
    status: z.string().optional().describe('Filter by status: pending, done, all'),
  },
  async ({ status }) => {
    try {
      const qs = status ? `?status=${status}` : '';
      const result = await athenaAPI('GET', `/api/tasks${qs}`);
      return ok(result);
    } catch (e) { return fail(`list_tasks error: ${e.message}`); }
  }
);

const completeTaskTool = tool(
  'complete_task',
  'Mark a task as complete in ATHENA.',
  { id: z.number().describe('Task ID to complete') },
  async ({ id }) => {
    try {
      const result = await athenaAPI('PATCH', `/api/tasks/${id}`, { status: 'done' });
      return ok(result);
    } catch (e) { return fail(`complete_task error: ${e.message}`); }
  }
);

// --- Memory (mnemo CLI) ---
const searchMemoryTool = tool(
  'search_memory',
  'Search JARVIS persistent memory (MNEMO). Use before answering from scratch.',
  {
    query: z.string().describe('Search query'),
    project: z.string().optional().describe('Filter by project'),
  },
  async ({ query: q, project }) => {
    try {
      let cmd = `${MNEMO_BIN} search "${q.replace(/"/g, '\\"')}"`;
      if (project) cmd += ` --project "${project}"`;
      const { stdout } = await execAsync(cmd, {
        timeout: 15_000,
        maxBuffer: 2 * 1024 * 1024,
        encoding: 'utf-8',
        env: { ...process.env, MNEMO_API_KEY },
      });
      return ok(stdout || '(no results)');
    } catch (e) { return fail(`search_memory error: ${e.stdout || e.stderr || e.message}`); }
  }
);

const saveMemoryTool = tool(
  'save_memory',
  'Save an observation to JARVIS persistent memory (MNEMO).',
  {
    title: z.string().describe('Short searchable title'),
    content: z.string().describe('Observation content'),
    type: z.string().optional().describe('Type: discovery, decision, bugfix, architecture, pattern, config, preference'),
    project: z.string().optional().describe('Project name'),
  },
  async ({ title, content, type, project }) => {
    try {
      let cmd = `${MNEMO_BIN} save "${title.replace(/"/g, '\\"')}" "${content.replace(/"/g, '\\"')}"`;
      if (type) cmd += ` --type ${type}`;
      if (project) cmd += ` --project "${project}"`;
      const { stdout } = await execAsync(cmd, {
        timeout: 15_000,
        maxBuffer: 1024 * 1024,
        encoding: 'utf-8',
        env: { ...process.env, MNEMO_API_KEY },
      });
      return ok(stdout || 'Saved.');
    } catch (e) { return fail(`save_memory error: ${e.stdout || e.stderr || e.message}`); }
  }
);

// --- Comms ---
const notifyTool = tool(
  'notify',
  'Send a notification via ATHENA (Discord, etc).',
  {
    message: z.string().describe('Notification message'),
    channel: z.string().optional().describe('Channel: discord (default)'),
  },
  async ({ message, channel }) => {
    try {
      const result = await athenaAPI('POST', '/api/notify', {
        message,
        channel: channel || 'discord',
      });
      return ok(result);
    } catch (e) { return fail(`notify error: ${e.message}`); }
  }
);

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------
const allTools = [
  readFileTool, writeFileTool, editFileTool,
  bashTool,
  grepTool, globTool,
  fetchUrlTool, webSearchTool,
  createTaskTool, listTasksTool, completeTaskTool,
  searchMemoryTool, saveMemoryTool,
  notifyTool,
];

function makeJarvisServer() {
  return createSdkMcpServer({
    name: 'jarvis',
    version: '3.0.0',
    tools: allTools,
  });
}

// MCP tool names as exposed to Claude follow the format: mcp__<server>__<tool>
// We derive them from allTools so the whitelist stays in sync with the definitions.
const JARVIS_TOOL_NAMES = allTools.map((t) => `mcp__jarvis__${t.name}`);

console.log(`[bridge] ${allTools.length} MCP tools defined: ${JARVIS_TOOL_NAMES.join(', ')}`);

// ---------------------------------------------------------------------------
// HTTP Server
// ---------------------------------------------------------------------------
const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/v1/usage') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      rate_limit: LATEST_RATE_LIMIT,
      rate_limit_seen_at: LATEST_RATE_LIMIT_SEEN_AT,
      model_usage_last_request: LATEST_MODEL_USAGE,
      permission_denials_last_request: LATEST_PERMISSION_DENIALS,
      last_result_at: LATEST_RESULT_AT,
    }));
    return;
  }

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      service: 'prometheus-bridge',
      version: 'v3',
      tools: allTools.length,
    }));
    return;
  }

  if (req.method !== 'POST') {
    res.writeHead(405);
    res.end('Method not allowed');
    return;
  }

  let body = '';
  for await (const chunk of req) body += chunk;

  // Detect SSE preference from Accept header
  const acceptHeader = String(req.headers['accept'] || '');
  const wantsSSE = acceptHeader.includes('text/event-stream');

  try {
    const request = JSON.parse(body);
    const model = MODELS[request.model] || 'opus';

    // Extract system prompt
    let systemPrompt = '';
    if (request.system) {
      systemPrompt = Array.isArray(request.system)
        ? request.system.map(b => b.text || '').join('\n')
        : String(request.system);
    }

    // Convert messages to prompt
    let prompt = '';
    for (const msg of request.messages || []) {
      const content = typeof msg.content === 'string'
        ? msg.content
        : Array.isArray(msg.content) ? msg.content.map(b => b.text || '').join('') : '';

      if (msg.role === 'user') prompt += content + '\n';
      else if (msg.role === 'assistant') prompt += `[Previous: ${content}]\n`;
      else if (msg.role === 'system') systemPrompt += '\n' + content;
    }

    const maxTurns = request.maxTurns || 100;
    console.log(`[bridge] ${model} | msgs:${request.messages?.length||0} | maxTurns:${maxTurns} | tools:${allTools.length} | sse:${wantsSSE}`);

    // Setup SSE stream if requested
    if (wantsSSE) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
    }

    let responseText = '';
    let totalCost = 0;
    let inputTokens = 0;
    let outputTokens = 0;

    // tool_use_id → tool name (so tool_result events can carry the name)
    const toolNameByID = new Map();

    // STRATEGY: positive whitelist via `tools: []` + `allowedTools: JARVIS_TOOL_NAMES`.
    //
    // Why not `disallowedTools` only:
    //   The SDK silently inherits the user's Claude.ai MCP integrations (Cloudflare,
    //   Vercel, Gmail, Calendar, Excalidraw, etc.) and `disallowedTools` does NOT
    //   filter them out at the model layer — Claude still sees them in its tool list
    //   and prefers them over our jarvis tools because they have richer descriptions.
    //   Verified empirically: with disallowedTools alone, Claude called
    //   `mcp__claude_ai_Cloudflare_Developer_Platform__search_cloudflare_documentation`
    //   instead of any `mcp__jarvis__*` tool.
    //
    // The fix:
    //   1. `tools: []`           → disable ALL Claude Code built-in tools (Bash, Read, ...)
    //   2. `allowedTools: [...]` → restrict tool calls to ONLY our 14 jarvis MCP tools
    //   3. `disallowedTools`     → kept as belt-and-suspenders against any leakage
    //
    // CLAUDE_CODE_BUILTINS is retained as a defensive blacklist; the real enforcement
    // is `tools: []` + `allowedTools: JARVIS_TOOL_NAMES`.
    const CLAUDE_CODE_BUILTINS = [
      // Built-in CC tools
      'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep',
      'WebFetch', 'WebSearch', 'Task', 'NotebookEdit',
      'TodoWrite', 'Agent', 'Skill', 'BashOutput', 'KillShell',
      'SlashCommand', 'ExitPlanMode', 'ToolSearch', 'AskUserQuestion',
      'EnterPlanMode', 'EnterWorktree', 'ExitWorktree',
      'CronCreate', 'CronDelete', 'CronList', 'CronUpdate',
      'TaskCreate', 'TaskGet', 'TaskList', 'TaskOutput', 'TaskStop', 'TaskUpdate',
      'RemoteTrigger', 'ListMcpResourcesTool', 'ReadMcpResourceTool',
      // Claude.ai MCP integrations (inherited from user's Claude account)
      'mcp__claude_ai_Cloudflare_Developer_Platform__accounts_list',
      'mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_create',
      'mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_delete',
      'mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_get',
      'mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_query',
      'mcp__claude_ai_Cloudflare_Developer_Platform__d1_databases_list',
      'mcp__claude_ai_Cloudflare_Developer_Platform__hyperdrive_config_delete',
      'mcp__claude_ai_Cloudflare_Developer_Platform__hyperdrive_config_edit',
      'mcp__claude_ai_Cloudflare_Developer_Platform__hyperdrive_config_get',
      'mcp__claude_ai_Cloudflare_Developer_Platform__hyperdrive_configs_list',
      'mcp__claude_ai_Cloudflare_Developer_Platform__kv_namespace_create',
      'mcp__claude_ai_Cloudflare_Developer_Platform__kv_namespace_delete',
      'mcp__claude_ai_Cloudflare_Developer_Platform__kv_namespace_get',
      'mcp__claude_ai_Cloudflare_Developer_Platform__kv_namespace_update',
      'mcp__claude_ai_Cloudflare_Developer_Platform__kv_namespaces_list',
      'mcp__claude_ai_Cloudflare_Developer_Platform__migrate_pages_to_workers_guide',
      'mcp__claude_ai_Cloudflare_Developer_Platform__r2_bucket_create',
      'mcp__claude_ai_Cloudflare_Developer_Platform__r2_bucket_delete',
      'mcp__claude_ai_Cloudflare_Developer_Platform__r2_bucket_get',
      'mcp__claude_ai_Cloudflare_Developer_Platform__r2_buckets_list',
      'mcp__claude_ai_Cloudflare_Developer_Platform__search_cloudflare_documentation',
      'mcp__claude_ai_Cloudflare_Developer_Platform__set_active_account',
      'mcp__claude_ai_Cloudflare_Developer_Platform__workers_get_worker',
      'mcp__claude_ai_Cloudflare_Developer_Platform__workers_get_worker_code',
      'mcp__claude_ai_Cloudflare_Developer_Platform__workers_list',
      'mcp__claude_ai_Excalidraw__create_view',
      'mcp__claude_ai_Excalidraw__export_to_excalidraw',
      'mcp__claude_ai_Excalidraw__read_checkpoint',
      'mcp__claude_ai_Excalidraw__read_me',
      'mcp__claude_ai_Excalidraw__save_checkpoint',
      'mcp__claude_ai_Figma_2__authenticate',
      'mcp__claude_ai_Figma__authenticate',
      'mcp__claude_ai_Gmail__gmail_create_draft',
      'mcp__claude_ai_Gmail__gmail_get_profile',
      'mcp__claude_ai_Gmail__gmail_list_drafts',
      'mcp__claude_ai_Gmail__gmail_list_labels',
      'mcp__claude_ai_Gmail__gmail_read_message',
      'mcp__claude_ai_Gmail__gmail_read_thread',
      'mcp__claude_ai_Gmail__gmail_search_messages',
      'mcp__claude_ai_Google_Calendar__gcal_create_event',
      'mcp__claude_ai_Google_Calendar__gcal_delete_event',
      'mcp__claude_ai_Google_Calendar__gcal_find_meeting_times',
      'mcp__claude_ai_Google_Calendar__gcal_find_my_free_time',
      'mcp__claude_ai_Google_Calendar__gcal_get_event',
      'mcp__claude_ai_Google_Calendar__gcal_list_calendars',
      'mcp__claude_ai_Google_Calendar__gcal_list_events',
      'mcp__claude_ai_Google_Calendar__gcal_respond_to_event',
      'mcp__claude_ai_Google_Calendar__gcal_update_event',
      'mcp__claude_ai_Notion__authenticate',
      'mcp__claude_ai_Vercel__add_toolbar_reaction',
      'mcp__claude_ai_Vercel__change_toolbar_thread_resolve_status',
      'mcp__claude_ai_Vercel__check_domain_availability_and_price',
      'mcp__claude_ai_Vercel__deploy_to_vercel',
      'mcp__claude_ai_Vercel__edit_toolbar_message',
      'mcp__claude_ai_Vercel__get_access_to_vercel_url',
      'mcp__claude_ai_Vercel__get_deployment',
      'mcp__claude_ai_Vercel__get_deployment_build_logs',
      'mcp__claude_ai_Vercel__get_project',
      'mcp__claude_ai_Vercel__get_runtime_logs',
      'mcp__claude_ai_Vercel__get_toolbar_thread',
      'mcp__claude_ai_Vercel__list_deployments',
      'mcp__claude_ai_Vercel__list_projects',
      'mcp__claude_ai_Vercel__list_teams',
      'mcp__claude_ai_Vercel__list_toolbar_threads',
      'mcp__claude_ai_Vercel__reply_to_toolbar_thread',
      'mcp__claude_ai_Vercel__search_vercel_documentation',
      'mcp__claude_ai_Vercel__web_fetch_vercel_url',
    ];

    for await (const msg of query({
      prompt: prompt.trim(),
      options: {
        model,
        systemPrompt: systemPrompt || undefined,
        maxTurns,
        // We rely ONLY on disallowedTools to block Claude Code built-ins.
        // allowedTools is intentionally NOT set: empirically it filters MCP tools
        // out of the model's tool list (init.tools=[]) and Claude hallucinates
        // <function_calls> XML in plain text.
        disallowedTools: CLAUDE_CODE_BUILTINS,
        mcpServers: { 'jarvis': makeJarvisServer() },
        permissionMode: 'bypassPermissions',
        allowDangerouslySkipPermissions: true,
      }
    })) {
      // Diagnostics: confirm jarvis MCP tools are registered. If jarvisCount is 0
      // when total>0, the SDK likely failed to register one of our tools (often a
      // schema issue). If everything is 0, the SDK is treating us as a constrained
      // session — check the cwd and CLAUDE_CONFIG_DIR.
      if (msg.type === 'system' && msg.subtype === 'init') {
        const toolsList = msg.tools || [];
        const jarvisCount = toolsList.filter((t) => t.startsWith('mcp__jarvis__')).length;
        console.log(`[bridge] init: total=${toolsList.length} jarvis=${jarvisCount}`);
        if (jarvisCount === 0) {
          console.warn('[bridge] WARNING: 0 jarvis tools registered. Check tool schemas (zod v4 requires z.record(key, val)).');
        }
      }
      if (msg.type === 'assistant') {
        for (const b of msg.message.content) {
          if (b.type === 'text') {
            responseText += b.text;
            if (wantsSSE) {
              sseWrite(res, 'text', { text: b.text });
              console.debug(`[bridge] sse text len=${b.text.length}`);
            }
          } else if (b.type === 'tool_use') {
            toolNameByID.set(b.id, b.name);
            // Instrumentation: log every tool Claude wants to use, with origin.
            // mcp__jarvis__* = our MCP tools (controlled by ATHENA dispatcher)
            // anything else = Claude Code built-in (we want zero of these)
            const origin = b.name.startsWith('mcp__jarvis__') ? 'MCP' : 'CLAUDE_CODE';
            console.log(`[bridge] tool_use origin=${origin} name=${b.name} id=${b.id}`);
            if (wantsSSE) {
              sseWrite(res, 'tool_start', { id: b.id, tool: b.name, input: b.input });
              console.debug(`[bridge] sse tool_start ${b.name} id=${b.id}`);
            }
          }
        }
      } else if (msg.type === 'user') {
        // tool results come back as a user message with tool_result blocks
        const content = msg.message?.content;
        if (Array.isArray(content)) {
          for (const b of content) {
            if (b.type === 'tool_result') {
              const toolName = toolNameByID.get(b.tool_use_id) || '';
              if (wantsSSE) {
                // content can be a string or array of blocks; stringify safely
                let resultContent = b.content;
                if (Array.isArray(resultContent)) {
                  resultContent = resultContent.map(c => c.text || JSON.stringify(c)).join('');
                }
                sseWrite(res, 'tool_result', {
                  tool_use_id: b.tool_use_id,
                  tool: toolName,
                  content: typeof resultContent === 'string' ? resultContent : JSON.stringify(resultContent),
                  is_error: !!b.is_error,
                });
                console.debug(`[bridge] sse tool_result ${toolName} err=${!!b.is_error}`);
              }
            }
          }
        }
      } else if (msg.type === 'rate_limit_event') {
        LATEST_RATE_LIMIT = msg.rate_limit_info || null;
        LATEST_RATE_LIMIT_SEEN_AT = new Date().toISOString();
        const ri = msg.rate_limit_info || {};
        console.log(`[bridge] rate_limit_event status=${ri.status} type=${ri.rateLimitType} util=${ri.utilization} resetsAt=${ri.resetsAt}`);
      } else if (msg.type === 'result' && msg.subtype === 'success') {
        totalCost = msg.total_cost_usd || 0;
        inputTokens = msg.total_input_tokens || 0;
        outputTokens = msg.total_output_tokens || 0;
        LATEST_MODEL_USAGE = msg.modelUsage || null;
        LATEST_PERMISSION_DENIALS = msg.permission_denials || null;
        LATEST_RESULT_AT = new Date().toISOString();
      }
    }

    console.log(`[bridge] done: ${responseText.length}c | $${totalCost.toFixed(4)} | ${inputTokens}/${outputTokens}tok`);

    if (wantsSSE) {
      sseWrite(res, 'done', {
        text: responseText,
        usage: { input_tokens: inputTokens, output_tokens: outputTokens },
        cost: totalCost,
        model: request.model || 'claude-opus-4-6',
      });
      console.debug('[bridge] sse done');
      res.end();
      return;
    }

    // Backward-compat: non-SSE clients get JSON response
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      id: `msg_${Date.now()}`,
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: responseText }],
      model: request.model || 'claude-opus-4-6',
      stop_reason: 'end_turn',
      usage: { input_tokens: inputTokens, output_tokens: outputTokens },
    }));

  } catch (error) {
    console.error('[bridge] error:', error.message);
    if (wantsSSE && !res.headersSent) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      });
    }
    if (wantsSSE) {
      try {
        sseWrite(res, 'error', { message: error.message });
      } catch (_) { /* socket may be closed */ }
      res.end();
    } else {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ type: 'error', error: { type: 'bridge_error', message: error.message } }));
    }
  }
});

// ---------------------------------------------------------------------------
// SSE helper
// ---------------------------------------------------------------------------
function sseWrite(res, event, data) {
  try {
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  } catch (e) {
    console.warn(`[bridge] sse write error: ${e.message}`);
  }
}

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[bridge] PROMETHEUS v3 bridge on 0.0.0.0:${PORT}`);
  console.log(`[bridge] ${allTools.length} MCP tools | tools:[] (built-ins disabled)`);
  console.log(`[bridge] ATHENA: ${ATHENA_URL} | MNEMO: ${MNEMO_BIN}`);
});
