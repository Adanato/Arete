/**
 * QueueBuilderView - Build dependency-aware study queues
 *
 * Allows users to:
 * 1. Select a deck to filter due cards
 * 2. Configure queue parameters (depth, max cards)
 * 3. Preview the queue with prerequisites marked
 * 4. Send the queue to Anki as a filtered deck
 */

import { ItemView, WorkspaceLeaf, setIcon, Notice } from 'obsidian';
import type AretePlugin from '@/main';

export const QUEUE_BUILDER_VIEW_TYPE = 'arete-queue-builder';

interface QueueCard {
	position: number;
	id: string;
	title: string;
	file: string;
	isPrereq: boolean;
}

interface QueueResult {
	deck: string;
	dueCount: number;
	totalWithPrereqs: number;
	queue: QueueCard[];
}

export class QueueBuilderView extends ItemView {
	plugin: AretePlugin;
	private selectedDeck: string | null = null;
	private depth = 2;
	private maxCards = 50;
	private queueResult: QueueResult | null = null;
	private isLoading = false;
	private decks: string[] = [];

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType(): string {
		return QUEUE_BUILDER_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Arete Queue Builder';
	}

	getIcon(): string {
		return 'list-ordered';
	}

	async onOpen(): Promise<void> {
		await this.loadDecks();
		this.render();
	}

	async loadDecks(): Promise<void> {
		try {
			this.decks = await this.plugin.areteClient.getDeckNames();
		} catch (e) {
			console.error('[QueueBuilder] Failed to load decks:', e);
			this.decks = [];
		}
	}

	render(): void {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-queue-builder');
		container.style.padding = '1rem';

		// Header
		const header = container.createEl('h2', { text: 'Queue Builder' });
		header.style.marginTop = '0';

		// Description
		container.createEl('p', {
			text: 'Build a study queue that includes prerequisite cards before your due cards.',
			cls: 'setting-item-description',
		});

		// Controls section
		const controls = container.createDiv({ cls: 'arete-queue-controls' });
		controls.style.display = 'flex';
		controls.style.flexDirection = 'column';
		controls.style.gap = '1rem';
		controls.style.marginBottom = '1rem';
		controls.style.padding = '1rem';
		controls.style.background = 'var(--background-secondary)';
		controls.style.borderRadius = '8px';

		// Deck selector
		this.renderDeckSelector(controls);

		// Depth control
		this.renderDepthControl(controls);

		// Max cards control
		this.renderMaxCardsControl(controls);

		// Build button
		const buildBtn = controls.createEl('button', {
			text: this.isLoading ? 'Building...' : 'Build Queue',
			cls: 'mod-cta',
		});
		buildBtn.disabled = this.isLoading;
		buildBtn.onclick = () => this.buildQueue();

		// Results section
		if (this.queueResult) {
			this.renderQueuePreview(container, this.queueResult);
		}
	}

	renderDeckSelector(container: HTMLElement): void {
		const row = container.createDiv({ cls: 'setting-item' });
		row.createDiv({ text: 'Deck Filter', cls: 'setting-item-name' });

		const select = row.createEl('select');
		select.style.marginLeft = 'auto';

		// All decks option
		const allOpt = select.createEl('option', { value: '', text: 'All Decks' });
		if (!this.selectedDeck) allOpt.selected = true;

		// Deck options
		this.decks.forEach((deck) => {
			const opt = select.createEl('option', { value: deck, text: deck });
			if (this.selectedDeck === deck) opt.selected = true;
		});

		select.onchange = () => {
			this.selectedDeck = select.value || null;
		};
	}

	renderDepthControl(container: HTMLElement): void {
		const row = container.createDiv({ cls: 'setting-item' });
		row.createDiv({ text: 'Prerequisite Depth', cls: 'setting-item-name' });

		const input = row.createEl('input', { type: 'number' });
		input.style.width = '60px';
		input.style.marginLeft = 'auto';
		input.value = String(this.depth);
		input.min = '1';
		input.max = '5';

		input.onchange = () => {
			this.depth = parseInt(input.value) || 2;
		};
	}

	renderMaxCardsControl(container: HTMLElement): void {
		const row = container.createDiv({ cls: 'setting-item' });
		row.createDiv({ text: 'Max Cards', cls: 'setting-item-name' });

		const input = row.createEl('input', { type: 'number' });
		input.style.width = '60px';
		input.style.marginLeft = 'auto';
		input.value = String(this.maxCards);
		input.min = '10';
		input.max = '200';

		input.onchange = () => {
			this.maxCards = parseInt(input.value) || 50;
		};
	}

	async buildQueue(): Promise<void> {
		this.isLoading = true;
		this.render();

		try {
			// Call backend to build queue
			const result = await this.plugin.areteClient.buildStudyQueue(
				this.selectedDeck,
				this.depth,
				this.maxCards,
			);

			this.queueResult = result;
			new Notice(`Queue built: ${result.totalWithPrereqs} cards`);
		} catch (e) {
			console.error('[QueueBuilder] Failed to build queue:', e);
			new Notice('Failed to build queue. Check console for details.');
		} finally {
			this.isLoading = false;
			this.render();
		}
	}

	renderQueuePreview(container: HTMLElement, result: QueueResult): void {
		const section = container.createDiv({ cls: 'arete-queue-preview' });

		// Summary
		const summary = section.createDiv();
		summary.style.marginBottom = '1rem';
		summary.style.padding = '0.5rem';
		summary.style.background = 'var(--background-primary-alt)';
		summary.style.borderRadius = '4px';

		summary.createEl('strong', { text: `${result.deck}` });
		summary.createSpan({
			text: ` — ${result.dueCount} due, ${result.totalWithPrereqs} total with prereqs`,
		});

		// Send to Anki button
		const sendBtn = section.createEl('button', { text: 'Send to Anki' });
		sendBtn.style.marginBottom = '1rem';
		sendBtn.onclick = () => this.sendToAnki();

		// Queue list
		const list = section.createDiv({ cls: 'arete-queue-list' });
		list.style.maxHeight = '400px';
		list.style.overflowY = 'auto';

		result.queue.forEach((card) => {
			const item = list.createDiv({ cls: 'arete-queue-item' });
			item.style.display = 'flex';
			item.style.alignItems = 'center';
			item.style.padding = '8px';
			item.style.borderBottom = '1px solid var(--background-modifier-border)';

			// Position badge
			const pos = item.createSpan({ text: String(card.position) });
			pos.style.width = '30px';
			pos.style.fontWeight = 'bold';
			pos.style.color = card.isPrereq ? 'var(--text-accent)' : 'var(--text-normal)';

			// Prereq indicator
			if (card.isPrereq) {
				const prereqBadge = item.createSpan({ text: 'PREREQ' });
				prereqBadge.style.fontSize = '0.7em';
				prereqBadge.style.padding = '2px 4px';
				prereqBadge.style.background = 'var(--interactive-accent)';
				prereqBadge.style.color = 'var(--text-on-accent)';
				prereqBadge.style.borderRadius = '4px';
				prereqBadge.style.marginRight = '8px';
			}

			// Card title
			const title = item.createSpan({ text: card.title });
			title.style.flex = '1';
			title.style.overflow = 'hidden';
			title.style.textOverflow = 'ellipsis';
			title.style.whiteSpace = 'nowrap';
			title.style.cursor = 'pointer';

			title.onclick = () => this.openFile(card.file);
		});
	}

	async sendToAnki(): Promise<void> {
		if (!this.queueResult) return;

		try {
			await this.plugin.areteClient.createQueueDeck(this.queueResult.queue.map((c) => c.id));
			new Notice('Queue sent to Anki!');
		} catch (e) {
			console.error('[QueueBuilder] Failed to send to Anki:', e);
			new Notice('Failed to create Anki deck.');
		}
	}

	async openFile(filePath: string): Promise<void> {
		const file = this.app.vault.getAbstractFileByPath(filePath);
		if (file) {
			await this.app.workspace.getLeaf().openFile(file as any);
		}
	}
}
