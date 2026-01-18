/**
 * LocalGraphView - Visual dependency graph centered on current card.
 *
 * Layout:
 * - Prerequisites (left) → Selected Card (center) → Dependents (right)
 * - Dotted lines for related edges
 * - Solid arrows for requires edges
 */

import {
	ItemView,
	WorkspaceLeaf,
	setIcon,
	Notice,
	TFile,
} from 'obsidian';
import type AretePlugin from '@/main';
import { DependencyResolver } from '@/application/services/DependencyResolver';
import { CardNode, LocalGraphResult } from '@/domain/graph/types';

export const LOCAL_GRAPH_VIEW_TYPE = 'arete-local-graph';

export class LocalGraphView extends ItemView {
	plugin: AretePlugin;
	private resolver: DependencyResolver;
	private graphContainer: HTMLElement | null = null;
	private currentCardId: string | null = null;
	private showRelated: boolean = true;
	private depth: number = 2;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
		this.resolver = new DependencyResolver(this.app, plugin.settings);
	}

	getViewType(): string {
		return LOCAL_GRAPH_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Dependency Graph';
	}

	getIcon(): string {
		return 'network';
	}

	async onOpen(): Promise<void> {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-local-graph');

		// Toolbar
		const toolbar = container.createDiv({ cls: 'arete-graph-toolbar' });

		const refreshBtn = toolbar.createDiv({ cls: 'arete-graph-btn' });
		setIcon(refreshBtn, 'refresh-cw');
		refreshBtn.setAttribute('title', 'Rebuild graph');
		refreshBtn.addEventListener('click', () => this.rebuildGraph());

		const relatedToggle = toolbar.createDiv({
			cls: 'arete-graph-btn' + (this.showRelated ? ' is-active' : ''),
		});
		setIcon(relatedToggle, 'link');
		relatedToggle.setAttribute('title', 'Toggle related');
		relatedToggle.addEventListener('click', () => {
			this.showRelated = !this.showRelated;
			relatedToggle.toggleClass('is-active', this.showRelated);
			this.refresh();
		});

		const depthSelect = toolbar.createEl('select', { cls: 'arete-graph-depth' });
		for (let d = 1; d <= 4; d++) {
			const opt = depthSelect.createEl('option', { value: String(d), text: `Depth: ${d}` });
			if (d === this.depth) opt.selected = true;
		}
		depthSelect.addEventListener('change', () => {
			this.depth = parseInt(depthSelect.value);
			this.refresh();
		});

		// Graph container
		this.graphContainer = container.createDiv({ cls: 'arete-graph-container' });

		// Build graph
		await this.rebuildGraph();

		// Register events
		this.registerEvent(
			this.app.workspace.on('active-leaf-change', () => {
				this.refresh();
			}),
		);
	}

	async onClose(): Promise<void> {
		// Cleanup
	}

	private async rebuildGraph(): Promise<void> {
		await this.resolver.buildGraph();
		this.refresh();
	}

	private refresh(): void {
		if (!this.graphContainer) return;
		this.graphContainer.empty();

		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) {
			this.showEmpty('No active file');
			return;
		}

		// Get current card ID
		const cache = this.app.metadataCache.getFileCache(activeFile);
		const cards = cache?.frontmatter?.cards;

		if (!cards || !Array.isArray(cards)) {
			this.showEmpty('No cards in file');
			return;
		}

		const cardWithId = cards.find((c: Record<string, unknown>) => c.id);
		if (!cardWithId) {
			this.showEmpty('No cards with Arete ID');
			return;
		}

		this.currentCardId = cardWithId.id;
		const localGraph = this.resolver.getLocalGraph(this.currentCardId, this.depth);

		if (!localGraph) {
			this.showEmpty('Card not in graph');
			return;
		}

		this.renderGraph(localGraph);
	}

	private showEmpty(message: string): void {
		if (!this.graphContainer) return;
		this.graphContainer.createDiv({ cls: 'arete-graph-empty', text: message });
	}

	private renderGraph(graph: LocalGraphResult): void {
		if (!this.graphContainer) return;

		// Create three-column layout
		const layout = this.graphContainer.createDiv({ cls: 'arete-graph-layout' });

		// Left column: Prerequisites
		const leftCol = layout.createDiv({ cls: 'arete-graph-column arete-graph-prereqs' });
		leftCol.createDiv({ cls: 'arete-graph-column-title', text: 'Prerequisites' });
		this.renderNodes(leftCol, graph.prerequisites, 'prereq');

		// Center column: Current card
		const centerCol = layout.createDiv({ cls: 'arete-graph-column arete-graph-center' });
		this.renderCenterNode(centerCol, graph.center, graph.cycles);

		// Right column: Dependents
		const rightCol = layout.createDiv({ cls: 'arete-graph-column arete-graph-dependents' });
		rightCol.createDiv({ cls: 'arete-graph-column-title', text: 'Dependents' });
		this.renderNodes(rightCol, graph.dependents, 'dependent');

		// Related (below if enabled)
		if (this.showRelated && graph.related.length > 0) {
			const relatedSection = this.graphContainer.createDiv({ cls: 'arete-graph-related' });
			relatedSection.createDiv({ cls: 'arete-graph-column-title', text: 'Related' });
			const relatedNodes = relatedSection.createDiv({ cls: 'arete-graph-related-nodes' });
			this.renderNodes(relatedNodes, graph.related, 'related');
		}
	}

	private renderNodes(
		container: HTMLElement,
		nodes: CardNode[],
		type: 'prereq' | 'dependent' | 'related',
	): void {
		if (nodes.length === 0) {
			container.createDiv({ cls: 'arete-graph-empty-nodes', text: 'None' });
			return;
		}

		for (const node of nodes) {
			const nodeEl = container.createDiv({
				cls: `arete-graph-node arete-graph-node-${type}`,
			});

			nodeEl.createDiv({
				cls: 'arete-graph-node-title',
				text: node.title.slice(0, 30) + (node.title.length > 30 ? '...' : ''),
			});

			nodeEl.createDiv({
				cls: 'arete-graph-node-id',
				text: node.id.slice(0, 12),
			});

			// Click to navigate
			nodeEl.addEventListener('click', () => {
				const file = this.app.vault.getAbstractFileByPath(node.filePath);
				if (file instanceof TFile) {
					this.app.workspace.getLeaf().openFile(file);
				}
			});

			// Hover preview
			nodeEl.setAttribute('title', `${node.title}\n${node.filePath}:${node.lineNumber}`);
		}
	}

	private renderCenterNode(
		container: HTMLElement,
		node: CardNode,
		cycles: string[][],
	): void {
		const nodeEl = container.createDiv({ cls: 'arete-graph-node arete-graph-node-center' });

		if (cycles.length > 0) {
			nodeEl.addClass('has-cycle');
			const cycleIcon = nodeEl.createDiv({ cls: 'arete-graph-cycle-icon' });
			setIcon(cycleIcon, 'alert-triangle');
			cycleIcon.setAttribute('title', 'Part of a cycle (co-requisite)');
		}

		nodeEl.createDiv({
			cls: 'arete-graph-node-title',
			text: node.title.slice(0, 40),
		});

		nodeEl.createDiv({
			cls: 'arete-graph-node-id',
			text: node.id.slice(0, 16),
		});

		nodeEl.createDiv({
			cls: 'arete-graph-node-file',
			text: node.filePath.split('/').pop() || '',
		});
	}
}
