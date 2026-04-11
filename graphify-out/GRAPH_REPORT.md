# Graph Report - /root/.claude  (2026-04-11)

## Corpus Check
- Corpus is ~13,836 words - fits in a single context window. You may not need a graph.

## Summary
- 52 nodes · 54 edges · 7 communities detected
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Graphify Pipeline` - 12 edges
2. `Step 4: Build Graph, Cluster, Analyze` - 8 edges
3. `Session Start Hook Skill` - 6 edges
4. `Step 3B: Semantic Extraction (Parallel Subagents)` - 6 edges
5. `Step 3: Extract Entities and Relationships` - 5 edges
6. `Graphify Skill` - 4 edges
7. `Step B0: Check Extraction Cache` - 3 edges
8. `Step B2: Dispatch All Subagents in Single Message` - 3 edges
9. `Step 6: Generate Obsidian Vault + HTML` - 3 edges
10. `Graphify Extraction Subagent` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Graphify Skill` --semantically_similar_to--> `Session Start Hook Skill`  [INFERRED] [semantically similar]
  .claude/skills/graphify/SKILL.md → .claude/skills/session-start-hook/SKILL.md
- `Graphify Extraction Subagent` --implements--> `Tool Result: bk8bnqaol (Subagent Prompt Template)`  [INFERRED]
  .claude/skills/graphify/SKILL.md → .claude/projects/-home-user-Sacred-mirror/f55af55a-340d-49b7-ad6b-cefde128a054/tool-results/bk8bnqaol.txt
- `Graphify Skill Trigger` --references--> `Graphify Skill`  [EXTRACTED]
  .claude/CLAUDE.md → .claude/skills/graphify/SKILL.md
- `Tool Result: bk8bnqaol (Subagent Prompt Template)` --references--> `Edge Confidence Classification (EXTRACTED/INFERRED/AMBIGUOUS)`  [EXTRACTED]
  .claude/projects/-home-user-Sacred-mirror/f55af55a-340d-49b7-ad6b-cefde128a054/tool-results/bk8bnqaol.txt → .claude/skills/graphify/SKILL.md

## Hyperedges (group relationships)
- **Graphify Three Core Outputs** — graphify_output_html, graphify_output_json, graphify_output_report [EXTRACTED 1.00]
- **Core Extraction Pipeline: AST + Semantic + Merge** — graphify_step3a_ast, graphify_step3b_semantic, graphify_step3c_merge [EXTRACTED 1.00]
- **Three Key Graphify Capabilities Beyond Claude Alone** — graphify_persistent_graph, graphify_audit_trail, graphify_community_detection [EXTRACTED 1.00]

## Communities

### Community 0 - "Skills & Triggers"
Cohesion: 0.17
Nodes (12): Graphify Skill Trigger, Graphify Skill, Session Start Hook Skill, Andrej Karpathy /raw Folder Workflow, Async Mode for Hooks, Dependency Installation in Hook, Hook Environment Variables, Rationale: Hook Must Be Idempotent (+4 more)

### Community 1 - "Pipeline & Outputs"
Cohesion: 0.17
Nodes (12): Obsidian Vault Export, Interactive HTML Output, Graphify Pipeline, Step 1: Ensure Graphify Installed, Step 2.5: Transcribe Video/Audio, Step 2: Detect Files, Step 5: Label Communities, Step 6: Generate Obsidian Vault + HTML (+4 more)

### Community 2 - "Extraction & Caching"
Cohesion: 0.22
Nodes (10): Rationale: Cache Semantic Results to Save Tokens, Rationale: Parallelize AST + Semantic to Save Time, Step 3: Extract Entities and Relationships, Step 3A: AST Structural Extraction, Step B0: Check Extraction Cache, Step B1: Split Files Into Chunks, Step B3: Collect, Cache and Merge Results, Step 3B: Semantic Extraction (Parallel Subagents) (+2 more)

### Community 3 - "Graph Quality & Audit"
Cohesion: 0.25
Nodes (9): Honest Audit Trail, Edge Confidence Classification (EXTRACTED/INFERRED/AMBIGUOUS), Graphify Extraction Subagent, MCP stdio Server, Persistent Graph (graph.json), Rationale: Use general-purpose Subagent Type for Write Access, Step B2: Dispatch All Subagents in Single Message, Step 7d: MCP Server (+1 more)

### Community 4 - "Analysis & Visualization"
Cohesion: 0.33
Nodes (7): Community Detection, God Nodes (High-Degree Hub Nodes), GraphRAG-ready JSON Output, GRAPH_REPORT.md Output, Rationale: Directed Graph Flag Preserves Edge Direction, Step 4: Build Graph, Cluster, Analyze, Surprising Connections (Cross-Community Bridges)

### Community 5 - "SVG Export"
Cohesion: 1.0
Nodes (1): Step 7b: SVG Export

### Community 6 - "GraphML Export"
Cohesion: 1.0
Nodes (1): Step 7c: GraphML Export

## Knowledge Gaps
- **30 isolated node(s):** `Graphify Skill Trigger`, `Step 1: Ensure Graphify Installed`, `Step 2: Detect Files`, `Step B1: Split Files Into Chunks`, `Step B3: Collect, Cache and Merge Results` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `SVG Export`** (1 nodes): `Step 7b: SVG Export`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `GraphML Export`** (1 nodes): `Step 7c: GraphML Export`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Graphify Pipeline` connect `Pipeline & Outputs` to `Skills & Triggers`, `Extraction & Caching`, `Analysis & Visualization`?**
  _High betweenness centrality (0.709) - this node is a cross-community bridge._
- **Why does `Step 4: Build Graph, Cluster, Analyze` connect `Analysis & Visualization` to `Pipeline & Outputs`, `Graph Quality & Audit`?**
  _High betweenness centrality (0.345) - this node is a cross-community bridge._
- **Why does `Graphify Skill` connect `Skills & Triggers` to `Pipeline & Outputs`?**
  _High betweenness centrality (0.343) - this node is a cross-community bridge._
- **What connects `Graphify Skill Trigger`, `Step 1: Ensure Graphify Installed`, `Step 2: Detect Files` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._