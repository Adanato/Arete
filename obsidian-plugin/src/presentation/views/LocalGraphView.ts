/**
 * LocalGraphView - Physics-based dependency graph utilizing D3.js
 *
 * Replaces the static column view with an interactive force-directed graph
 * that mimics Obsidian's native graph view behavior.
 */

import { ItemView, WorkspaceLeaf, setIcon, Notice, TFile } from 'obsidian';
import * as d3 from 'd3';
import type AretePlugin from '@/main';
import { DependencyResolver } from '@/application/services/DependencyResolver';
import { LocalGraphResult } from '@/domain/graph/types';

export const LOCAL_GRAPH_VIEW_TYPE = 'arete-local-graph';

interface GraphNode extends d3.SimulationNodeDatum {
	id: string;
	title: string;
	group: 'center' | 'prereq' | 'dependent' | 'related';
	filePath: string;
	lineNumber: number;
	radius?: number;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
	source: string | GraphNode;
	target: string | GraphNode;
	type: 'requires' | 'related';
}

export class LocalGraphView extends ItemView {
	plugin: AretePlugin;
	private resolver: DependencyResolver;
	private container: HTMLElement;
	private depth = 2;
	private showRelated = true;
	private simulation: d3.Simulation<GraphNode, GraphLink> | null = null;
	private svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
		this.resolver = plugin.dependencyResolver;
	}

	getViewType(): string {
		return LOCAL_GRAPH_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Arete Local Graph';
	}

	getIcon(): string {
		return 'network';
	}

	async onOpen(): Promise<void> {
		this.container = this.containerEl.children[1] as HTMLElement;
		this.container.empty();
		this.container.addClass('arete-local-graph-d3');
		this.container.style.display = 'flex';
		this.container.style.flexDirection = 'column';
		this.container.style.height = '100%';
		this.container.style.overflow = 'hidden';

		this.renderToolbar();

		const graphDiv = this.container.createDiv({ cls: 'arete-graph-canvas' });
		graphDiv.style.flex = '1';
		graphDiv.style.overflow = 'hidden'; // SVG handles scroll via zoom
		graphDiv.style.position = 'relative';

		// Initial graph build
		await this.refresh();

		// Register events
		this.registerEvent(
			this.app.workspace.on('active-leaf-change', () => {
				this.refresh();
			}),
		);
		// Update on resize
		this.registerEvent(
			this.app.workspace.on('resize', () => {
				this.refresh();
			}),
		);
	}

	renderToolbar() {
		const toolbar = this.container.createDiv({ cls: 'arete-graph-toolbar' });
		toolbar.style.padding = '8px';
		toolbar.style.borderBottom = '1px solid var(--background-modifier-border)';
		toolbar.style.display = 'flex';
		toolbar.style.gap = '10px';
		toolbar.style.alignItems = 'center';

		// Refresh Button
		const refreshBtn = toolbar.createDiv({ cls: 'clickable-icon' });
		setIcon(refreshBtn, 'refresh-cw');
		refreshBtn.setAttribute('title', 'Rebuild Graph');
		refreshBtn.addEventListener('click', () => {
			this.resolver.buildGraph().then(() => this.refresh());
		});

		// Related Toggle
		const relatedToggle = toolbar.createDiv({
			cls: 'clickable-icon' + (this.showRelated ? ' is-active' : ''),
		});
		setIcon(relatedToggle, 'link');
		relatedToggle.setAttribute('title', 'Toggle Related Links');
		if (this.showRelated) relatedToggle.style.color = 'var(--interactive-accent)';
		relatedToggle.addEventListener('click', () => {
			this.showRelated = !this.showRelated;
			if (this.showRelated) relatedToggle.style.color = 'var(--interactive-accent)';
			else relatedToggle.style.color = '';
			this.refresh();
		});

		// Depth Select
		const depthLabel = toolbar.createSpan({ text: 'Depth:' });
		depthLabel.style.fontSize = '0.8em';
		const depthSelect = toolbar.createEl('select');
		[1, 2, 3, 4].forEach((d) => {
			const opt = depthSelect.createEl('option', { value: String(d), text: String(d) });
			if (d === this.depth) opt.selected = true;
		});
		depthSelect.addEventListener('change', () => {
			this.depth = parseInt(depthSelect.value);
			this.refresh();
		});
	}

	// ... inside LocalGraphView class
	private centeredCardId: string | null = null;
	// ...

	async refresh() {
		console.log('[Arete Graph] Refreshing...');
		const canvas = this.container.querySelector('.arete-graph-canvas') as HTMLElement;
		if (!canvas) {
			console.error('[Arete Graph] No canvas element found');
			return;
		}

		// 1. Get Data
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) {
			console.log('[Arete Graph] No active file');
			this.renderEmpty(canvas, 'No active file');
			return;
		}
		console.log('[Arete Graph] Active file:', activeFile.path);

		const cache = this.app.metadataCache.getFileCache(activeFile);
		const cards = cache?.frontmatter?.cards;
		
		if (!cards || !Array.isArray(cards) || cards.length === 0) {
			console.log('[Arete Graph] No cards found in frontmatter');
			this.renderEmpty(canvas, 'No Arete cards found in this file.');
			return;
		}
		console.log('[Arete Graph] Found cards:', cards.length);

		// determine center card:
		let targetCardId = this.centeredCardId;
		
		// Verify if targetCardId still exists in file
		const cardExists = targetCardId && cards.find((c: any) => c.id === targetCardId);
		
		if (!cardExists) {
			const firstCard = cards.find((c: any) => c.id);
			if (firstCard) {
				targetCardId = firstCard.id;
				this.centeredCardId = targetCardId;
				console.log('[Arete Graph] Defaulting to first card:', targetCardId);
			}
		}

		if (!targetCardId) {
			console.log('[Arete Graph] No valid card ID found');
			this.renderEmpty(canvas, 'No valid cards found.');
			return;
		}

		// Force rebuild graph to ensure fresh data
		await this.resolver.buildGraph();
		
		// Use resolver to get structured data
		const localGraph = this.resolver.getLocalGraph(targetCardId, this.depth);
		if (!localGraph) {
			this.renderEmpty(canvas, 'Graph parsing failed or empty.');
			return;
		}

		// 2. Transform Data for D3
		const { nodes, links } = this.transformData(localGraph);
		console.log(`[Arete Graph] Transformed: ${nodes.length} nodes, ${links.length} links`);

		// 3. Render D3
		this.renderD3Graph(canvas, nodes, links);
	}

	renderEmpty(container: HTMLElement, msg: string) {
		container.empty();
		container.createDiv({
			text: msg,
			cls: 'arete-graph-empty-msg',
		}).style.padding = '20px';
	}
	
	// Helper to transform LocalGraphResult to D3 format
	transformData(graph: LocalGraphResult): { nodes: GraphNode[]; links: GraphLink[] } {
		const nodes: Map<string, GraphNode> = new Map();
		const links: GraphLink[] = [];

		// Helper to add node
		const addNode = (
			nodeData: any,
			group: 'center' | 'prereq' | 'dependent' | 'related',
		) => {
			if (!nodes.has(nodeData.id)) {
				nodes.set(nodeData.id, {
					id: nodeData.id,
					title: nodeData.title,
					group,
					filePath: nodeData.filePath,
					lineNumber: nodeData.lineNumber,
					radius: group === 'center' ? 8 : 5,
				});
			}
		};

		// 1. Add All Nodes
		addNode(graph.center, 'center');
		
		graph.prerequisites.forEach((n) => addNode(n, 'prereq'));
		graph.dependents.forEach((n) => addNode(n, 'dependent'));

		if (this.showRelated) {
			graph.related.forEach((n) => addNode(n, 'related'));
		}

		// 2. Add Links from Graph Data
		// The resolver now provides valid edges for the subgraph
		if (graph.links) {
			graph.links.forEach((edge) => {
				// Only add link if both nodes are in the graph (e.g. might be hidden related)
				if (nodes.has(edge.fromId) && nodes.has(edge.toId)) {
					// Filter related links if hidden
					if (!this.showRelated && edge.type === 'related') return;

					links.push({
						source: edge.fromId,
						target: edge.toId,
						type: edge.type,
					});
				}
			});
		} else {
			// Fallback for types safety if links missing (shouldn't happen with new resolver)
			console.warn('[Arete Graph] No links provided by resolver, graph may look disconnected.');
		}

		return {
			nodes: Array.from(nodes.values()),
			links,
		};
	}

	renderD3Graph(container: HTMLElement, nodes: GraphNode[], links: GraphLink[]) {
		container.empty();
		const width = container.clientWidth;
		const height = container.clientHeight;

		const svg = d3
			.select(container)
			.append('svg')
			.attr('width', '100%')
			.attr('height', '100%')
			.attr('viewBox', [0, 0, width, height]);
		
		this.svg = svg;
		const g = svg.append('g');

		// Zoom
		const zoom = d3.zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.1, 4])
			.on('zoom', (event) => g.attr('transform', event.transform));
		svg.call(zoom);

		// Simulation
		this.simulation = d3.forceSimulation(nodes)
			.force('link', d3.forceLink(links).id((d: any) => d.id).distance(150))
			.force('charge', d3.forceManyBody().strength(-600))
			.force('center', d3.forceCenter(width / 2, height / 2))
			.force('collide', d3.forceCollide().radius(40));

		// Arrows
		svg.append('defs').append('marker')
			.attr('id', 'arrow').attr('viewBox', '0 -5 10 10')
			.attr('refX', 20).attr('refY', 0)
			.attr('markerWidth', 6).attr('markerHeight', 6)
			.attr('orient', 'auto')
			.append('path').attr('d', 'M0,-5L10,0L0,5')
			.attr('fill', 'var(--text-muted)');

		// Links
		const link = g.append('g').selectAll('line')
			.data(links).join('line')
			.attr('stroke', 'var(--text-muted)')
			.attr('stroke-opacity', 0.6)
			.attr('stroke-width', (d) => (d.type === 'requires' ? 2 : 1))
			.attr('stroke-dasharray', (d) => (d.type === 'related' ? '4 4' : null))
			.attr('marker-end', (d) => (d.type === 'requires' ? 'url(#arrow)' : null));

		// Drag
		const dragBehavior = d3.drag<any, any>()
			.on('start', (event, d) => {
				if (!event.active) this.simulation?.alphaTarget(0.3).restart();
				d.fx = d.x; d.fy = d.y;
			})
			.on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
			.on('end', (event, d) => {
				if (!event.active) this.simulation?.alphaTarget(0);
				d.fx = null; d.fy = null;
			});

		// Nodes
		const node = g.append('g').selectAll('circle')
			.data(nodes).join('circle')
			.attr('r', (d) => d.group === 'center' ? 10 : 6)
			.attr('fill', (d) => {
				if (d.group === 'center') return 'var(--interactive-accent)';
				if (d.group === 'prereq') return 'var(--text-normal)';
				return 'var(--text-muted)';
			})
			.attr('stroke', 'var(--background-primary)')
			.attr('stroke-width', 2)
			.style('cursor', 'pointer')
			.call(dragBehavior);

		// Labels
		const labels = g.append('g').selectAll('text')
			.data(nodes).join('text')
			.text((d) => d.title.length > 25 ? d.title.slice(0, 23) + '...' : d.title)
			.attr('font-size', '10px')
			.attr('dx', 15).attr('dy', 4)
			.attr('fill', 'var(--text-muted)')
			.style('pointer-events', 'none');

		// Click Interaction
		node.on('click', async (event, d) => {
			event.stopPropagation(); // prevent zoom click
			
			// If node is in same file, re-center graph
			const activeFile = this.app.workspace.getActiveFile();
			if (activeFile && d.filePath === activeFile.path) {
				console.log('[Arete] Switching graph center to:', d.id);
				this.centeredCardId = d.id;
				this.refresh();
			} else {
				// Navigate to different file
				await this.openFile(d.filePath);
			}
		});

		node.append('title').text((d) => `${d.title}\n(${d.id})`);

		this.simulation.on('tick', () => {
			link.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
				.attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
			node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
			labels.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y);
		});
	}

	drag(simulation: d3.Simulation<GraphNode, GraphLink>) {
		function dragstarted(event: any, d: any) {
			if (!event.active) simulation.alphaTarget(0.3).restart();
			d.fx = d.x;
			d.fy = d.y;
		}

		function dragged(event: any, d: any) {
			d.fx = event.x;
			d.fy = event.y;
		}

		function dragended(event: any, d: any) {
			if (!event.active) simulation.alphaTarget(0);
			d.fx = null;
			d.fy = null;
		}

		return d3
			.drag()
			.on('start', dragstarted)
			.on('drag', dragged)
			.on('end', dragended);
	}

	async openFile(filePath: string) {
		const file = this.app.vault.getAbstractFileByPath(filePath);
		if (file instanceof TFile) {
			await this.app.workspace.getLeaf().openFile(file);
		}
	}

	async onClose() {
		if (this.simulation) this.simulation.stop();
	}
}
