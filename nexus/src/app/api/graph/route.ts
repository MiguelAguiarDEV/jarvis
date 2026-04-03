import { NextRequest, NextResponse } from "next/server";
import { engramFetch } from "@/lib/engram";
import fs from "fs";
import path from "path";

const KB_ROOT = process.env.KB_ROOT || "/home/mx/personal-knowledgebase";

const KB_DIRS = [
  "docs/research",
  "docs/learned",
  "docs/ideas",
  "docs/decisions",
  "journal/daily",
];

// Map directory prefixes to topic connections
const DIR_TOPICS: Record<string, string> = {
  "docs/research": "research",
  "docs/learned": "learned",
  "docs/ideas": "ideas",
  "docs/decisions": "decisions",
  "journal/daily": "journal",
};

// Map filename prefixes to project connections
const FILE_PROJECT_PATTERNS: [RegExp, string][] = [
  [/^jarvis-/, "jarvis-dashboard"],
  [/^discord-/, "discord-bot"],
  [/^homelab/, "homelab"],
];

interface DocNode {
  id: string;
  type: string;
  label: string;
  data?: Record<string, string>;
}

interface DocEdge {
  source: string;
  target: string;
  type: string;
}

function scanMarkdownFiles(): { nodes: DocNode[]; edges: DocEdge[] } {
  const nodes: DocNode[] = [];
  const edges: DocEdge[] = [];
  const topicNodes = new Set<string>();

  for (const dir of KB_DIRS) {
    const fullDir = path.join(KB_ROOT, dir);
    if (!fs.existsSync(fullDir)) continue;

    let files: string[];
    try {
      files = fs.readdirSync(fullDir).filter((f) => f.endsWith(".md"));
    } catch {
      continue;
    }

    const topicName = DIR_TOPICS[dir] || dir;
    const topicId = `topic:${topicName}`;

    // Add topic node if not already added
    if (!topicNodes.has(topicId)) {
      topicNodes.add(topicId);
      nodes.push({
        id: topicId,
        type: "topic",
        label: topicName,
      });
    }

    for (const file of files) {
      const basename = file.replace(/\.md$/, "");
      const nodeId = `doc:${dir}/${basename}`;

      nodes.push({
        id: nodeId,
        type: "document",
        label: basename,
        data: {
          path: `${dir}/${file}`,
          directory: dir,
        },
      });

      // Connect to directory topic
      edges.push({
        source: nodeId,
        target: topicId,
        type: "in_directory",
      });

      // Connect to project if filename matches
      for (const [pattern, project] of FILE_PROJECT_PATTERNS) {
        if (pattern.test(basename)) {
          const projectId = `project:${project}`;
          // Ensure project node exists (may already come from engram)
          if (!topicNodes.has(projectId)) {
            topicNodes.add(projectId);
            nodes.push({
              id: projectId,
              type: "project",
              label: project,
            });
          }
          edges.push({
            source: nodeId,
            target: projectId,
            type: "relates_to",
          });
          break;
        }
      }
    }
  }

  return { nodes, edges };
}

export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get("project") || "";
  const maxNodes = req.nextUrl.searchParams.get("max_nodes") || "500";

  try {
    // Fetch mnemo graph data
    const data = await engramFetch<{
      nodes: DocNode[];
      edges: DocEdge[];
    }>(
      `/api/graph?project=${encodeURIComponent(project)}&max_nodes=${maxNodes}`
    );

    // Scan KB markdown files
    let kbData: { nodes: DocNode[]; edges: DocEdge[] } = {
      nodes: [],
      edges: [],
    };
    try {
      kbData = scanMarkdownFiles();
    } catch {
      // KB not accessible -- continue with mnemo data only
    }

    // Merge: deduplicate nodes by ID (mnemo takes priority)
    const existingIds = new Set((data.nodes || []).map((n) => n.id));
    const mergedNodes = [
      ...(data.nodes || []),
      ...kbData.nodes.filter((n) => !existingIds.has(n.id)),
    ];

    // Connect KB topic nodes to matching mnemo topic nodes
    const extraEdges: DocEdge[] = [];
    const mnemoTopics = (data.nodes || [])
      .filter((n) => n.type === "topic")
      .map((n) => ({ id: n.id, label: n.label?.toLowerCase() }));

    for (const kbNode of kbData.nodes) {
      if (kbNode.type === "topic") {
        // Check if engram has a matching topic
        const match = mnemoTopics.find(
          (t) => t.label === kbNode.label?.toLowerCase()
        );
        if (match && match.id !== kbNode.id) {
          // Redirect edges from kbNode.id to match.id
          for (const edge of kbData.edges) {
            if (edge.target === kbNode.id) {
              edge.target = match.id;
            }
            if (edge.source === kbNode.id) {
              edge.source = match.id;
            }
          }
          // Remove the duplicate topic node
          const idx = mergedNodes.findIndex((n) => n.id === kbNode.id);
          if (idx !== -1) mergedNodes.splice(idx, 1);
        }
      }
    }

    const mergedEdges = [
      ...(data.edges || []),
      ...kbData.edges,
      ...extraEdges,
    ];

    return NextResponse.json({
      nodes: mergedNodes,
      edges: mergedEdges,
    });
  } catch (err) {
    return NextResponse.json(
      { nodes: [], edges: [], error: String(err) },
      { status: 502 }
    );
  }
}
