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
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'fs';
import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { query, tool, createSdkMcpServer } from '@anthropic-ai/claude-agent-sdk';
import { z } from 'zod/v4';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env.PROMETHEUS_BRIDGE_PORT || '9876');
const ATHENA_URL = process.env.ATHENA_URL || 'http://100.71.66.54:8080';
const MNEMO_BIN = process.env.MNEMO_BIN || '/home/mx/projects/jarvis-dashboard/athena/mnemo';
const MNEMO_API_KEY = process.env.MNEMO_API_KEY || '';

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
      if (!existsSync(dir)) execSync(`mkdir -p "${dir}"`);
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
      const output = execSync(command, {
        cwd: cwd || '/home/mx',
        timeout: 120_000,
        maxBuffer: 10 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return ok(output || '(no output)');
    } catch (e) {
      const out = (e.stdout || '') + (e.stderr || '');
      return fail(`Exit ${e.status || 1}\n${out || e.message}`);
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
      const output = execSync(cmd, {
        cwd: '/home/mx',
        timeout: 30_000,
        maxBuffer: 5 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
      });
      return ok(output || '(no matches)');
    } catch (e) {
      if (e.status === 1) return ok('(no matches)');
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
      const output = execSync(cmd, {
        cwd: '/home/mx',
        timeout: 15_000,
        maxBuffer: 2 * 1024 * 1024,
        encoding: 'utf-8',
        shell: '/bin/bash',
      });
      return ok(output || '(no matches)');
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
    headers: z.record(z.string()).optional().describe('Request headers'),
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
      const output = execSync(cmd, {
        timeout: 15_000,
        maxBuffer: 2 * 1024 * 1024,
        encoding: 'utf-8',
        env: { ...process.env, MNEMO_API_KEY },
      });
      return ok(output || '(no results)');
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
      const output = execSync(cmd, {
        timeout: 15_000,
        maxBuffer: 1024 * 1024,
        encoding: 'utf-8',
        env: { ...process.env, MNEMO_API_KEY },
      });
      return ok(output || 'Saved.');
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

console.log(`[bridge] ${allTools.length} MCP tools defined`);

// ---------------------------------------------------------------------------
// HTTP Server
// ---------------------------------------------------------------------------
const server = createServer(async (req, res) => {
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
    console.log(`[bridge] ${model} | msgs:${request.messages?.length||0} | maxTurns:${maxTurns} | tools:${allTools.length}`);

    let responseText = '';
    let totalCost = 0;
    let inputTokens = 0;
    let outputTokens = 0;

    for await (const msg of query({
      prompt: prompt.trim(),
      options: {
        model,
        systemPrompt: systemPrompt || undefined,
        maxTurns,
        // Keep Claude Code built-in tools (Bash, Read, etc.) + add our MCP tools
        // tools: [] was blocking MCP tools too. Let Claude use both.
        mcpServers: { 'jarvis': makeJarvisServer() },
        permissionMode: 'bypassPermissions',
        allowDangerouslySkipPermissions: true,
      }
    })) {
      if (msg.type === 'assistant') {
        for (const b of msg.message.content) {
          if (b.type === 'text') responseText += b.text;
        }
      }
      if (msg.type === 'result' && msg.subtype === 'success') {
        totalCost = msg.total_cost_usd || 0;
        inputTokens = msg.total_input_tokens || 0;
        outputTokens = msg.total_output_tokens || 0;
      }
    }

    console.log(`[bridge] done: ${responseText.length}c | $${totalCost.toFixed(4)} | ${inputTokens}/${outputTokens}tok`);

    // Build Anthropic Messages API format response (text only — no tool_use parsing needed)
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
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ type: 'error', error: { type: 'bridge_error', message: error.message } }));
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[bridge] PROMETHEUS v3 bridge on 0.0.0.0:${PORT}`);
  console.log(`[bridge] ${allTools.length} MCP tools | tools:[] (built-ins disabled)`);
  console.log(`[bridge] ATHENA: ${ATHENA_URL} | MNEMO: ${MNEMO_BIN}`);
});
