/**
 * PROMETHEUS Bridge — Claude Agent SDK
 *
 * Uses @anthropic-ai/claude-agent-sdk query() to call Claude.
 * This bypasses all OAuth rate limits because it IS Claude Code internally.
 *
 * JARVIS Go → HTTP to localhost:9876 → this bridge → query() → Claude
 */

import { createServer } from 'http';
import { query } from '@anthropic-ai/claude-agent-sdk';

const PORT = parseInt(process.env.PROMETHEUS_BRIDGE_PORT || '9876');

const MODELS = {
  'claude-opus-4-6': 'opus',
  'claude-sonnet-4-6': 'sonnet',
  'claude-haiku-4-5-20251001': 'haiku',
  'opus': 'opus',
  'sonnet': 'sonnet',
  'haiku': 'haiku',
};

const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'prometheus-bridge' }));
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

    // NOTE: Tool definitions are NOT injected into the bridge prompt.
    // Tools are managed by the ATHENA orchestrator's own tool-call loop.
    // The bridge only handles text-in → text-out via claude-agent-sdk query().

    console.log(`[bridge] ${model} | msgs:${request.messages?.length||0}`);

    let responseText = '';
    let totalCost = 0;
    let inputTokens = 0;
    let outputTokens = 0;

    for await (const msg of query({
      prompt: prompt.trim(),
      options: { model, systemPrompt: systemPrompt || undefined }
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

    // Build Anthropic Messages API format response
    const content = [{ type: 'text', text: responseText }];
    let stopReason = 'end_turn';

    // Detect tool_use in response
    const toolMatch = responseText.match(/\{"tool_use"\s*:\s*(\{[\s\S]*?\})\s*\}/);
    if (toolMatch) {
      try {
        const toolData = JSON.parse(toolMatch[0]).tool_use;
        content.splice(0, content.length, {
          type: 'tool_use',
          id: `toolu_${Date.now()}_${Math.random().toString(36).slice(2,8)}`,
          name: toolData.name,
          input: toolData.input,
        });
        stopReason = 'tool_use';
      } catch {}
    }

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      id: `msg_${Date.now()}`,
      type: 'message',
      role: 'assistant',
      content,
      model: request.model || 'claude-opus-4-6',
      stop_reason: stopReason,
      usage: { input_tokens: inputTokens, output_tokens: outputTokens },
    }));

  } catch (error) {
    console.error('[bridge] error:', error.message);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ type: 'error', error: { type: 'bridge_error', message: error.message } }));
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[bridge] PROMETHEUS bridge on 0.0.0.0:${PORT}`);
  console.log(`[bridge] Using @anthropic-ai/claude-agent-sdk query()`);
});
