/**
 * DependencyEditorView - Sidebar panel for editing card dependencies.
 *
 * Shows requires/related lists for the current card and allows
 * adding/removing dependencies via fuzzy search.
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
import { CardNode } from '@/domain/graph/types';
import { CardSearchModal } from '@/presentation/modals/CardSearchModal';

export const DEPENDENCY_EDITOR_VIEW_TYPE = 'arete-dependency-editor';

export class DependencyEditorView extends ItemView {
	plugin: AretePlugin;
	private resolver: DependencyResolver;
	private contentContainer: HTMLElement | null = null;
	private currentCardId: string | null = null;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
		this.resolver = new DependencyResolver(this.app, plugin.settings);
	}

	getViewType(): string {
		return DEPENDENCY_EDITOR_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Dependencies';
	}

	getIcon(): string {
		return 'git-branch';
	}

	async onOpen(): Promise<void> {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-dependency-editor');

		// Header
		const header = container.createDiv({ cls: 'arete-dep-header' });
		header.createEl('h4', { text: 'Card Dependencies' });

		const refreshBtn = header.createDiv({ cls: 'arete-dep-refresh-btn' });
		setIcon(refreshBtn, 'refresh-cw');
		refreshBtn.setAttribute('title', 'Rebuild graph');
		refreshBtn.addEventListener('click', () => this.rebuildGraph());

		// Content
		this.contentContainer = container.createDiv({ cls: 'arete-dep-content' });

		// Initial build
		await this.rebuildGraph();

		// Register events
		this.registerEvent(
			this.app.workspace.on('active-leaf-change', () => {
				this.refresh();
			}),
		);

		this.registerEvent(
			this.app.vault.on('modify', (file) => {
				if (file instanceof TFile && file.extension === 'md') {
					this.resolver.invalidateFile(file);
				}
			}),
		);
	}

	async onClose(): Promise<void> {
		// Cleanup
	}

	private async rebuildGraph(): Promise<void> {
		new Notice('Building dependency graph...');
		await this.resolver.buildGraph();
		new Notice('Dependency graph built.');
		this.refresh();
	}

	private refresh(): void {
		if (!this.contentContainer) return;
		this.contentContainer.empty();

		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) {
			this.contentContainer.createDiv({
				cls: 'arete-dep-empty',
				text: 'No active file',
			});
			return;
		}

		// Get current card from active file's frontmatter
		const cache = this.app.metadataCache.getFileCache(activeFile);
		const cards = cache?.frontmatter?.cards;

		if (!cards || !Array.isArray(cards) || cards.length === 0) {
			this.contentContainer.createDiv({
				cls: 'arete-dep-empty',
				text: 'No cards in this file',
			});
			return;
		}

		// Use first card with an ID (or allow selection in future)
		const cardWithId = cards.find((c: Record<string, unknown>) => c.id);
		if (!cardWithId) {
			this.contentContainer.createDiv({
				cls: 'arete-dep-empty',
				text: 'No cards with Arete ID',
			});
			return;
		}

		this.currentCardId = cardWithId.id;
		this.renderDependencies(cardWithId);
	}

	private renderDependencies(card: Record<string, unknown>): void {
		if (!this.contentContainer) return;

		const cardId = card.id as string;
		const deps = (card.deps as { requires?: string[]; related?: string[] }) || {};
		const requires = deps.requires || [];
		const related = deps.related || [];

		// Card info
		const cardInfo = this.contentContainer.createDiv({ cls: 'arete-dep-card-info' });
		cardInfo.createDiv({ cls: 'arete-dep-card-title', text: String(card.id).slice(0, 20) });

		// Requires section
		this.renderDepSection(
			'Prerequisites (requires)',
			requires,
			'requires',
			cardId,
		);

		// Related section
		this.renderDepSection(
			'Related',
			related,
			'related',
			cardId,
		);

		// Diagnostics
		this.renderDiagnostics(cardId, requires, related);
	}

	private renderDepSection(
		title: string,
		ids: string[],
		type: 'requires' | 'related',
		cardId: string,
	): void {
		if (!this.contentContainer) return;

		const section = this.contentContainer.createDiv({ cls: 'arete-dep-section' });

		const header = section.createDiv({ cls: 'arete-dep-section-header' });
		header.createSpan({ text: title });

		const addBtn = header.createDiv({ cls: 'arete-dep-add-btn' });
		setIcon(addBtn, 'plus');
		addBtn.setAttribute('title', `Add ${type}`);
		addBtn.addEventListener('click', () => this.openSearchModal(type, cardId));

		const list = section.createDiv({ cls: 'arete-dep-list' });

		if (ids.length === 0) {
			list.createDiv({ cls: 'arete-dep-empty-list', text: 'None' });
			return;
		}

		for (const depId of ids) {
			const item = list.createDiv({ cls: 'arete-dep-item' });

			// Try to resolve the node
			const node = this.resolver.getAllCards().find((n) => n.id === depId);

			const label = item.createDiv({ cls: 'arete-dep-item-label' });
			if (node) {
				label.createSpan({ text: node.title.slice(0, 40) });
				label.createSpan({ cls: 'arete-dep-item-id', text: depId.slice(0, 12) });

				// Click to navigate
				item.addEventListener('click', () => {
					const file = this.app.vault.getAbstractFileByPath(node.filePath);
					if (file instanceof TFile) {
						this.app.workspace.getLeaf().openFile(file);
					}
				});
			} else {
				label.createSpan({ cls: 'arete-dep-missing', text: `⚠ ${depId}` });
			}

			// Remove button
			const removeBtn = item.createDiv({ cls: 'arete-dep-remove-btn' });
			setIcon(removeBtn, 'x');
			removeBtn.addEventListener('click', (e) => {
				e.stopPropagation();
				this.removeDependency(cardId, depId, type);
			});
		}
	}

	private renderDiagnostics(
		cardId: string,
		requires: string[],
		related: string[],
	): void {
		if (!this.contentContainer) return;

		const allCards = this.resolver.getAllCards();
		const missing = [...requires, ...related].filter(
			(id) => !allCards.find((c) => c.id === id),
		);

		const localGraph = this.resolver.getLocalGraph(cardId);
		const cycles = localGraph?.cycles || [];

		if (missing.length === 0 && cycles.length === 0) return;

		const diag = this.contentContainer.createDiv({ cls: 'arete-dep-diagnostics' });
		diag.createDiv({ cls: 'arete-dep-diag-header', text: 'Diagnostics' });

		if (missing.length > 0) {
			const warn = diag.createDiv({ cls: 'arete-dep-diag-item mod-warning' });
			setIcon(warn, 'alert-triangle');
			warn.createSpan({ text: `${missing.length} missing dependencies` });
		}

		if (cycles.length > 0) {
			const cycleWarn = diag.createDiv({ cls: 'arete-dep-diag-item mod-cycle' });
			setIcon(cycleWarn, 'refresh-cw');
			cycleWarn.createSpan({ text: `${cycles.length} cycle(s) detected` });
		}
	}

	private openSearchModal(type: 'requires' | 'related', cardId: string): void {
		const modal = new CardSearchModal(
			this.app,
			this.resolver,
			cardId,
			async (selectedId) => {
				await this.addDependency(cardId, selectedId, type);
			},
		);
		modal.open();
	}

	private async addDependency(
		cardId: string,
		depId: string,
		type: 'requires' | 'related',
	): Promise<void> {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (!frontmatter.cards) return;

			const card = frontmatter.cards.find(
				(c: Record<string, unknown>) => c.id === cardId,
			);
			if (!card) return;

			if (!card.deps) card.deps = {};
			if (!card.deps[type]) card.deps[type] = [];

			if (!card.deps[type].includes(depId)) {
				card.deps[type].push(depId);
			}
		});

		new Notice(`Added ${type}: ${depId.slice(0, 12)}...`);
		this.refresh();
	}

	private async removeDependency(
		cardId: string,
		depId: string,
		type: 'requires' | 'related',
	): Promise<void> {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (!frontmatter.cards) return;

			const card = frontmatter.cards.find(
				(c: Record<string, unknown>) => c.id === cardId,
			);
			if (!card || !card.deps || !card.deps[type]) return;

			const idx = card.deps[type].indexOf(depId);
			if (idx !== -1) {
				card.deps[type].splice(idx, 1);
			}
		});

		new Notice(`Removed ${type}: ${depId.slice(0, 12)}...`);
		this.refresh();
	}
}
