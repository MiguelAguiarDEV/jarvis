"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { GraphNode } from "@/lib/mnemo";

const NODE_COLORS: Record<string, string> = {
  session: "#6a9dc8",
  observation: "#5ab87a",
  project: "#e8b84a",
  topic: "#9a7ac8",
  document: "#c87a6a",
};

const NODE_SHAPES: Record<string, string> = {
  session: "ellipse",
  observation: "ellipse",
  project: "diamond",
  topic: "round-rectangle",
  document: "round-rectangle",
};

interface SelectedNode {
  id: string;
  type: string;
  label: string;
  data?: Record<string, string>;
}

interface SessionObservation {
  id: number;
  title: string;
  type: string;
  content: string;
  project?: string;
  topic_key?: string;
  created_at: string;
}

interface PhysicsConfig {
  gravity: number;
  repulsion: number;
  repulsionRange: number;
  springLength: number;
  springK: number;
  damping: number;
}

const DEFAULT_PHYSICS: PhysicsConfig = {
  gravity: 0.001,
  repulsion: 1500,
  repulsionRange: 200,
  springLength: 80,
  springK: 0.008,
  damping: 0.82,
};

// Simple spring-based physics simulation for continuous force-directed behavior
function startPhysicsSimulation(cy: any, configRef: { current: PhysicsConfig }) {
  let animFrame: number | null = null;
  let running = true;
  let dragging: string | null = null;

  cy.on("grab", "node", (evt: any) => {
    dragging = evt.target.id();
  });

  cy.on("free", "node", () => {
    dragging = null;
  });

  const MIN_VELOCITY = 0.05;

  // Initialize velocities
  const velocities: Record<string, { vx: number; vy: number }> = {};
  cy.nodes().forEach((node: any) => {
    velocities[node.id()] = { vx: 0, vy: 0 };
  });

  function tick() {
    if (!running) return;

    const nodes = cy.nodes();
    const centerX = cy.width() / 2;
    const centerY = cy.height() / 2;

    // Calculate forces
    const forces: Record<string, { fx: number; fy: number }> = {};
    nodes.forEach((node: any) => {
      forces[node.id()] = { fx: 0, fy: 0 };
    });

    const cfg = configRef.current;

    // Node-node repulsion — only within range
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const posA = a.position();
        const posB = b.position();
        const dx = posB.x - posA.x;
        const dy = posB.y - posA.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist > cfg.repulsionRange) continue;
        const force = cfg.repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        forces[a.id()].fx -= fx;
        forces[a.id()].fy -= fy;
        forces[b.id()].fx += fx;
        forces[b.id()].fy += fy;
      }
    }

    // Edge spring forces (Hooke's law)
    cy.edges().forEach((edge: any) => {
      const src = edge.source();
      const tgt = edge.target();
      const posS = src.position();
      const posT = tgt.position();
      const dx = posT.x - posS.x;
      const dy = posT.y - posS.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const displacement = dist - cfg.springLength;
      const force = cfg.springK * displacement;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      forces[src.id()].fx += fx;
      forces[src.id()].fy += fy;
      forces[tgt.id()].fx -= fx;
      forces[tgt.id()].fy -= fy;
    });

    // Gravity — always pulls gently toward origin
    nodes.forEach((node: any) => {
      const pos = node.position();
      forces[node.id()].fx += -pos.x * cfg.gravity;
      forces[node.id()].fy += -pos.y * cfg.gravity;
    });

    // Apply forces
    let totalKineticEnergy = 0;
    nodes.forEach((node: any) => {
      const id = node.id();
      if (id === dragging) return; // Skip dragged node

      if (!velocities[id]) velocities[id] = { vx: 0, vy: 0 };

      velocities[id].vx = (velocities[id].vx + forces[id].fx) * cfg.damping;
      velocities[id].vy = (velocities[id].vy + forces[id].fy) * cfg.damping;

      const speed = Math.sqrt(
        velocities[id].vx * velocities[id].vx +
          velocities[id].vy * velocities[id].vy
      );
      totalKineticEnergy += speed;

      if (speed > MIN_VELOCITY) {
        const pos = node.position();
        node.position({
          x: pos.x + velocities[id].vx,
          y: pos.y + velocities[id].vy,
        });
      }
    });

    // When dragging, apply forces to connected nodes to create pull effect
    if (dragging) {
      const draggedNode = cy.getElementById(dragging);
      if (draggedNode.length) {
        draggedNode.connectedEdges().forEach((edge: any) => {
          const other =
            edge.source().id() === dragging ? edge.target() : edge.source();
          const otherId = other.id();
          const posD = draggedNode.position();
          const posO = other.position();
          const dx = posD.x - posO.x;
          const dy = posD.y - posO.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const displacement = dist - cfg.springLength;
          if (displacement > 0) {
            const pullForce = cfg.springK * displacement * 0.3;
            if (!velocities[otherId])
              velocities[otherId] = { vx: 0, vy: 0 };
            velocities[otherId].vx += (dx / dist) * pullForce;
            velocities[otherId].vy += (dy / dist) * pullForce;
          }
        });
      }
    }

    animFrame = requestAnimationFrame(tick);
  }

  animFrame = requestAnimationFrame(tick);

  return () => {
    running = false;
    if (animFrame) cancelAnimationFrame(animFrame);
  };
}

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<any>(null);
  const cleanupPhysicsRef = useRef<(() => void) | null>(null);
  const [selected, setSelected] = useState<SelectedNode | null>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [nodeContent, setNodeContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [sessionObs, setSessionObs] = useState<SessionObservation[]>([]);
  const [expandedObs, setExpandedObs] = useState<Set<number>>(new Set());
  const [showControls, setShowControls] = useState(false);
  const [physics, setPhysics] = useState<PhysicsConfig>({ ...DEFAULT_PHYSICS });
  const physicsRef = useRef<PhysicsConfig>({ ...DEFAULT_PHYSICS });

  // Fetch content when a node is selected
  useEffect(() => {
    if (!selected) { setNodeContent(null); setSessionObs([]); setExpandedObs(new Set()); return; }
    setNodeContent(null);
    setSessionObs([]);
    setExpandedObs(new Set());
    setContentLoading(true);

    if (selected.type === "document" && selected.data?.path) {
      fetch(`/api/doc-content?path=${encodeURIComponent(selected.data.path)}`)
        .then((r) => r.ok ? r.text() : null)
        .then((text) => { setNodeContent(text); setContentLoading(false); })
        .catch(() => setContentLoading(false));
    } else if (selected.type === "observation" && selected.id.startsWith("observation:")) {
      const obsId = selected.id.replace("observation:", "");
      fetch(`/api/observation/${obsId}`)
        .then((r) => r.ok ? r.json() : null)
        .then((data) => { setNodeContent(data?.content ?? null); setContentLoading(false); })
        .catch(() => setContentLoading(false));
    } else if (selected.type === "session" && selected.id.startsWith("session:")) {
      const sessId = selected.id.replace("session:", "");
      fetch(`/api/sessions/${encodeURIComponent(sessId)}/observations`)
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (data?.observations) {
            setSessionObs(data.observations);
          }
          setContentLoading(false);
        })
        .catch(() => setContentLoading(false));
    } else {
      setContentLoading(false);
    }
  }, [selected]);

  const updatePhysics = useCallback((key: keyof PhysicsConfig, value: number) => {
    setPhysics((prev) => {
      const next = { ...prev, [key]: value };
      physicsRef.current = next;
      return next;
    });
  }, []);

  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);

  const handleZoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const handleZoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const togglePhysics = useCallback(() => {
    setPhysicsEnabled((prev) => {
      const next = !prev;
      if (next && cyRef.current) {
        cleanupPhysicsRef.current = startPhysicsSimulation(cyRef.current, physicsRef);
      } else if (cleanupPhysicsRef.current) {
        cleanupPhysicsRef.current();
        cleanupPhysicsRef.current = null;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    let destroyed = false;

    async function init() {
      const [cytoscape, fcoseModule] = await Promise.all([
        import("cytoscape").then((m) => m.default),
        import("cytoscape-fcose").then((m) => m.default).catch(() => null),
      ]);

      if (fcoseModule) {
        cytoscape.use(fcoseModule);
      }

      const res = await fetch("/api/graph?max_nodes=500");
      const data = await res.json();

      if (destroyed || !containerRef.current) return;

      setNodeCount(data.nodes?.length ?? 0);
      setEdgeCount(data.edges?.length ?? 0);
      setLoading(false);

      if (!data.nodes?.length) return;

      // Filter edges to only include those with existing nodes
      const nodeIds = new Set(
        (data.nodes || []).map((n: GraphNode) => n.id)
      );
      const validEdges = (data.edges || []).filter(
        (e: { source: string; target: string }) =>
          e.source !== e.target && nodeIds.has(e.source) && nodeIds.has(e.target)
      );

      const cy = cytoscape({
        container: containerRef.current,
        elements: [
          ...(data.nodes || []).map((n: GraphNode) => ({
            data: { id: n.id, label: n.label, type: n.type, ...n.data },
          })),
          ...validEdges.map(
            (e: { source: string; target: string; type: string }) => ({
              data: { source: e.source, target: e.target, type: e.type },
            })
          ),
        ],
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              "font-size": "8px",
              "font-family": "monospace",
              color: "#a09080",
              "text-outline-color": "#1a0d0a",
              "text-outline-width": 1.2,
              "text-valign": "bottom",
              "text-margin-y": 5,
              "text-max-width": "80px",
              "text-wrap": "ellipsis",
              width: 12,
              height: 12,
              "border-width": 1.5,
              "border-color": "#3a2820",
              "transition-property":
                "width, height, border-width, border-color, background-color",
              "transition-duration": "0.15s",
            } as any,
          },
          ...Object.entries(NODE_COLORS).map(([type, color]) => ({
            selector: `node[type="${type}"]`,
            style: {
              "background-color": color,
              shape: NODE_SHAPES[type] || "ellipse",
            },
          })),
          {
            selector: "node[type='project']",
            style: {
              width: 22,
              height: 22,
              "font-size": "10px",
              "font-weight": "bold",
              color: "#e8b84a",
              "border-width": 2,
              "border-color": "#e8b84a",
              "text-margin-y": 7,
            } as any,
          },
          {
            selector: "node[type='topic']",
            style: {
              width: 16,
              height: 16,
              "font-size": "9px",
              color: "#9a7ac8",
              "border-color": "#9a7ac8",
            } as any,
          },
          {
            selector: "node[type='document']",
            style: {
              width: 14,
              height: 14,
              "font-size": "8px",
              color: "#c87a6a",
              "border-color": "#c87a6a",
            } as any,
          },
          {
            selector: "edge",
            style: {
              width: 0.8,
              "line-color": "#3a2820",
              "curve-style": "haystack",
              "haystack-radius": 0.5,
              opacity: 0.35,
              "transition-property": "opacity, width, line-color",
              "transition-duration": "0.15s",
            } as any,
          },
          {
            selector: "edge[type='has_topic']",
            style: { "line-color": "#8a6ab4", opacity: 0.25 } as any,
          },
          {
            selector: "edge[type='in_directory']",
            style: {
              "line-color": "#c87a6a",
              opacity: 0.3,
              "line-style": "dashed",
            } as any,
          },
          // Hover effects
          {
            selector: "node:active",
            style: {
              "overlay-opacity": 0.08,
              "overlay-color": "#e8b84a",
            } as any,
          },
          // Selected node glow
          {
            selector: "node:selected",
            style: {
              "border-width": 3,
              "border-color": "#e8b84a",
              width: 20,
              height: 20,
              "overlay-opacity": 0.15,
              "overlay-color": "#e8b84a",
              "overlay-padding": 6,
            } as any,
          },
          // Highlight connected edges on select
          {
            selector: "edge.highlighted",
            style: {
              opacity: 0.85,
              width: 1.5,
              "line-color": "#e8b84a",
            } as any,
          },
          {
            selector: "node.neighbor",
            style: {
              "border-width": 2,
              "border-color": "#e8b84a",
              opacity: 1,
            } as any,
          },
          {
            selector: "node.dimmed",
            style: {
              opacity: 0.15,
            } as any,
          },
          {
            selector: "edge.dimmed",
            style: {
              opacity: 0.05,
            } as any,
          },
        ],
        layout: fcoseModule
          ? ({
              name: "fcose",
              animate: true,
              animationDuration: 800,
              fit: true,
              padding: 40,
              nodeRepulsion: 8000,
              idealEdgeLength: 90,
              edgeElasticity: 0.2,
              gravity: 0.4,
              gravityRange: 1.5,
              numIter: 2500,
              quality: "default",
              nodeSeparation: 60,
              randomize: true,
            } as any)
          : ({
              name: "cose",
              animate: true,
              animationDuration: 800,
              fit: true,
              padding: 40,
              nodeRepulsion: () => 8000,
              idealEdgeLength: () => 90,
              edgeElasticity: () => 0.2,
              gravity: 0.4,
              numIter: 2000,
              nodeOverlap: 30,
              refresh: 20,
            } as any),
        minZoom: 0.05,
        maxZoom: 6,
        wheelSensitivity: 2.5,
      });

      cyRef.current = cy;
      if (typeof window !== "undefined") (window as any).__cy = cy;

      // Start continuous physics after initial layout settles
      cy.one("layoutstop", () => {
        cleanupPhysicsRef.current = startPhysicsSimulation(cy, physicsRef);
      });

      // Node selection: highlight neighbors, dim rest
      cy.on("tap", "node", (evt: any) => {
        const node = evt.target;
        setSelected({
          id: node.id(),
          type: node.data("type"),
          label: node.data("label"),
          data: node.data(),
        });

        // Highlight neighborhood
        cy.elements().removeClass("highlighted neighbor dimmed");
        const neighborhood = node.closedNeighborhood();
        cy.elements().not(neighborhood).addClass("dimmed");
        node.connectedEdges().addClass("highlighted");
        node.neighborhood("node").addClass("neighbor");
      });

      cy.on("tap", (evt: any) => {
        if (evt.target === cy) {
          setSelected(null);
          cy.elements().removeClass("highlighted neighbor dimmed");
        }
      });

      // Edge hover effect
      cy.on("mouseover", "edge", (evt: any) => {
        if (!evt.target.hasClass("dimmed")) {
          evt.target.style({ opacity: 0.8, width: 1.5 });
        }
      });
      cy.on("mouseout", "edge", (evt: any) => {
        if (!evt.target.hasClass("highlighted")) {
          evt.target.removeStyle("opacity width");
        }
      });

      // Node hover: show full label
      cy.on("mouseover", "node", (evt: any) => {
        evt.target.style({ "text-max-width": "200px" });
      });
      cy.on("mouseout", "node", (evt: any) => {
        evt.target.removeStyle("text-max-width");
      });
    }

    init();
    return () => {
      destroyed = true;
      try { cleanupPhysicsRef.current?.(); } catch {}
      try { cyRef.current?.destroy(); } catch {}
      cyRef.current = null;
    };
  }, []);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-kicker">GRAPH // NODE MAPPING</div>
          <h2 className="page-title">Knowledge Graph</h2>
        </div>
        <div
          style={{
            display: "flex",
            gap: "var(--space-3)",
            alignItems: "center",
          }}
        >
          <span className="badge badge-amber">{nodeCount} NODES</span>
          <span className="badge badge-muted">{edgeCount} EDGES</span>
        </div>
      </div>

      <div className="graph-container" style={{ flex: 1 }}>
        <div style={{ width: "100%", height: "100%" }}>
          <div ref={containerRef} style={{ width: "100%", height: "100%" }} suppressHydrationWarning />
        </div>

        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-3)",
            }}
          >
            <div className="empty-label loading-pulse">LOADING GRAPH...</div>
            <div style={{ width: 200 }}>
              <div
                className="hex-stream"
                style={{
                  justifyContent: "center",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-dim)",
                  gap: "var(--space-2)",
                }}
              >
                <span>NODE</span>
                <span>MAPPING</span>
                <span>IN</span>
                <span>PROGRESS</span>
              </div>
            </div>
          </div>
        )}

        {/* Zoom controls */}
        <div className="graph-controls">
          <button
            className="graph-control-btn"
            onClick={handleZoomIn}
            title="Zoom in"
          >
            +
          </button>
          <button
            className="graph-control-btn"
            onClick={handleZoomOut}
            title="Zoom out"
          >
            -
          </button>
          <button
            className="graph-control-btn"
            onClick={handleFit}
            title="Fit to view"
          >
            [ ]
          </button>
          <button
            className={`graph-control-btn ${physicsEnabled ? "active" : ""}`}
            onClick={togglePhysics}
            title={physicsEnabled ? "Pause physics" : "Resume physics"}
          >
            {physicsEnabled ? "||" : ">>"}
          </button>
          <button
            className={`graph-control-btn ${showControls ? "active" : ""}`}
            onClick={() => setShowControls(!showControls)}
            title="Physics settings"
          >
            &#9881;
          </button>
        </div>

        {/* Physics sliders panel */}
        {showControls && (
          <div style={{
            position: "absolute",
            top: "var(--space-3)",
            left: "var(--space-3)",
            width: 220,
            background: "var(--bg-panel)",
            border: "1px solid var(--border)",
            padding: "var(--space-3)",
            zIndex: 20,
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-2)",
          }}>
            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", letterSpacing: "0.15em", textTransform: "uppercase" }}>
              PHYSICS CONFIG
            </div>
            {([
              { key: "gravity" as const, label: "GRAVITY", min: 0, max: 0.01, step: 0.0001 },
              { key: "repulsion" as const, label: "REPULSION", min: 0, max: 5000, step: 50 },
              { key: "repulsionRange" as const, label: "REP. RANGE", min: 50, max: 1000, step: 10 },
              { key: "springLength" as const, label: "SPRING LEN", min: 20, max: 300, step: 5 },
              { key: "springK" as const, label: "SPRING K", min: 0, max: 0.05, step: 0.001 },
              { key: "damping" as const, label: "DAMPING", min: 0.5, max: 0.99, step: 0.01 },
            ]).map(({ key, label, min, max, step }) => (
              <div key={key}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                  <span>{label}</span>
                  <span style={{ color: "var(--accent-amber)", fontVariantNumeric: "tabular-nums" }}>
                    {physics[key] < 1 ? physics[key].toFixed(4) : physics[key].toFixed(0)}
                  </span>
                </div>
                <input
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={physics[key]}
                  onChange={(e) => updatePhysics(key, parseFloat(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--accent-amber)", height: 4, cursor: "pointer" }}
                />
              </div>
            ))}
            <button
              onClick={() => {
                setPhysics({ ...DEFAULT_PHYSICS });
                physicsRef.current = { ...DEFAULT_PHYSICS };
              }}
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                padding: "var(--space-1) var(--space-2)",
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
              }}
            >
              RESET DEFAULTS
            </button>
          </div>
        )}

        <div className="graph-legend">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="legend-item">
              <div className="legend-dot" style={{ background: color }} />
              <span>{type.toUpperCase()}</span>
            </div>
          ))}
        </div>

        {selected && (
          <div className="detail-panel">
            <button className="panel-close" onClick={() => setSelected(null)}>
              [ESC]
            </button>
            <div
              style={{
                fontSize: "var(--font-size-xs)",
                color: "var(--text-dim)",
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                marginBottom: "var(--space-2)",
              }}
            >
              ┌ {selected.type}
            </div>
            <div
              style={{
                fontSize: "var(--font-size-base)",
                color: "var(--accent-amber)",
                fontWeight: 600,
                marginBottom: "var(--space-4)",
              }}
            >
              {selected.label}
            </div>
            {selected.data &&
              Object.entries(selected.data)
                .filter(
                  ([k]) =>
                    !["id", "label", "type"].includes(k) && selected.data![k]
                )
                .map(([key, value]) => (
                  <div key={key} style={{ marginBottom: "var(--space-3)" }}>
                    <div
                      style={{
                        fontSize: "var(--font-size-xs)",
                        color: "var(--text-dim)",
                        letterSpacing: "0.1em",
                        textTransform: "uppercase",
                      }}
                    >
                      {key}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--font-size-sm)",
                        color: "var(--text-secondary)",
                        marginTop: 2,
                      }}
                    >
                      {String(value)}
                    </div>
                  </div>
                ))}
            {/* Content preview */}
            {contentLoading && (
              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)" }} className="loading-pulse">
                Loading content...
              </div>
            )}
            {nodeContent && (
              <div style={{ marginTop: "var(--space-3)" }}>
                <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-dim)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "var(--space-1)" }}>
                  CONTENT
                </div>
                <pre style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-secondary)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  maxHeight: 600,
                  overflowY: "auto",
                  background: "var(--bg-root)",
                  padding: "var(--space-2)",
                  border: "1px solid var(--border-subtle)",
                }}>
                  {nodeContent}
                </pre>
              </div>
            )}
            {/* Session observations */}
            {sessionObs.length > 0 && (
              <div style={{ marginTop: "var(--space-3)" }}>
                <div style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-dim)",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  marginBottom: "var(--space-2)",
                }}>
                  OBSERVATIONS ({sessionObs.length})
                </div>
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-2)",
                  maxHeight: 600,
                  overflowY: "auto",
                }}>
                  {sessionObs.map((obs) => {
                    const isExpanded = expandedObs.has(obs.id);
                    return (
                      <div
                        key={obs.id}
                        style={{
                          background: "var(--bg-root)",
                          border: "1px solid var(--border-subtle)",
                          padding: "var(--space-2)",
                          cursor: "pointer",
                        }}
                        onClick={() => {
                          setExpandedObs((prev) => {
                            const next = new Set(prev);
                            if (next.has(obs.id)) {
                              next.delete(obs.id);
                            } else {
                              next.add(obs.id);
                            }
                            return next;
                          });
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-2)" }}>
                          <div style={{
                            fontSize: "var(--font-size-xs)",
                            color: "#e8b84a",
                            fontWeight: 600,
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}>
                            {obs.title}
                          </div>
                          <div style={{
                            fontSize: "10px",
                            color: "var(--text-dim)",
                            textTransform: "uppercase",
                            letterSpacing: "0.1em",
                            flexShrink: 0,
                          }}>
                            {obs.type}
                          </div>
                        </div>
                        {obs.topic_key && (
                          <div style={{ fontSize: "10px", color: "#9a7ac8", marginTop: 2 }}>
                            {obs.topic_key}
                          </div>
                        )}
                        <pre style={{
                          fontSize: "var(--font-size-xs)",
                          color: "var(--text-secondary)",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          marginTop: "var(--space-1)",
                          maxHeight: isExpanded ? "none" : 60,
                          overflow: "hidden",
                          lineHeight: 1.4,
                        }}>
                          {isExpanded ? obs.content : obs.content.slice(0, 200)}
                          {!isExpanded && obs.content.length > 200 ? "..." : ""}
                        </pre>
                        {obs.content.length > 200 && (
                          <div style={{
                            fontSize: "10px",
                            color: "var(--text-dim)",
                            marginTop: 2,
                            textTransform: "uppercase",
                            letterSpacing: "0.1em",
                          }}>
                            {isExpanded ? "COLLAPSE" : "EXPAND"}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {selected.type === "session" && !contentLoading && sessionObs.length === 0 && (
              <div style={{
                marginTop: "var(--space-3)",
                fontSize: "var(--font-size-xs)",
                color: "var(--text-dim)",
                fontStyle: "italic",
              }}>
                No observations in this session
              </div>
            )}
            <div
              style={{
                marginTop: "var(--space-4)",
                fontSize: "var(--font-size-xs)",
                color: "var(--text-dim)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              ID: {selected.id}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
