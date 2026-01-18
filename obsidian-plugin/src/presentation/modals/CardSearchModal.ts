/**
 * CardSearchModal - Fuzzy search modal for finding cards to add as dependencies.
 */

import { App, FuzzySuggestModal } from 'obsidian';
import { DependencyResolver } from '@/application/services/DependencyResolver';
import { CardNode } from '@/domain/graph/types';

export class CardSearchModal extends FuzzySuggestModal<CardNode> {
	private resolver: DependencyResolver;
	private excludeId: string;
	private onSelect: (cardId: string) => void;

	constructor(
		app: App,
		resolver: DependencyResolver,
		excludeId: string,
		onSelect: (cardId: string) => void,
	) {
		super(app);
		this.resolver = resolver;
		this.excludeId = excludeId;
		this.onSelect = onSelect;

		this.setPlaceholder('Search for a card...');
	}

	getItems(): CardNode[] {
		return this.resolver
			.getAllCards()
			.filter((card) => card.id !== this.excludeId);
	}

	getItemText(item: CardNode): string {
		return `${item.title} (${item.id.slice(0, 12)})`;
	}

	onChooseItem(item: CardNode, evt: MouseEvent | KeyboardEvent): void {
		this.onSelect(item.id);
	}

	renderSuggestion(item: { item: CardNode; match: { score: number; matches: unknown[] } }, el: HTMLElement): void {
		const container = el.createDiv({ cls: 'arete-card-suggestion' });

		const title = container.createDiv({ cls: 'arete-card-suggestion-title' });
		title.setText(item.item.title.slice(0, 60));

		const meta = container.createDiv({ cls: 'arete-card-suggestion-meta' });
		meta.createSpan({ text: item.item.id.slice(0, 16), cls: 'arete-card-suggestion-id' });
		meta.createSpan({ text: ' • ' });
		meta.createSpan({ text: item.item.filePath.split('/').pop() || '', cls: 'arete-card-suggestion-file' });
	}
}
