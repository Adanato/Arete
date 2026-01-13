import {
	ItemView,
	WorkspaceLeaf,
	TFile,
	Notice,
	setIcon,
	App,
	MarkdownView,
	Menu,
	MarkdownRenderer,
	Component,
	requestUrl,
} from 'obsidian';
import type AretePlugin from '@/main';

export const CARD_VIEW_TYPE = 'arete-card-view';

interface CardData {
	[key: string]: any;
}

export class CardView extends ItemView {
	previewMode = false;
	expandedIndices: Set<number> = new Set();
	activeCardIndex: number | null = null;
	plugin: AretePlugin;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType() {
		return CARD_VIEW_TYPE;
	}

	getDisplayText() {
		return 'Card Viewer';
	}

	getIcon() {
		return 'layout-list';
	}

	async onOpen() {
		const container = this.containerEl.children[1];
		container.empty();
		container.createEl('h4', { text: 'Card Viewer' });

		// Initial Render
		this.render();

		// Register event to update view when active file changes
		this.registerEvent(
			this.app.workspace.on('active-leaf-change', () => {
				this.render();
			}),
		);
		// Register event for file modification (to refresh if edited elsewhere)
		this.registerEvent(
			this.app.vault.on('modify', (file) => {
				const activeFile = this.app.workspace.getActiveFile();
				if (activeFile && activeFile.path === file.path) {
					this.render();
				}
			}),
		);
	}

	async onClose() {
		// Cleanup if needed
	}

	async render() {
		const container = this.containerEl.children[1];
		// We re-render fully to ensure consistency, but state is preserved in this.expandedIndices
		container.empty();

		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) {
			container.createEl('p', { text: 'No active file.' });
			return;
		}

		const cache = this.app.metadataCache.getFileCache(activeFile);
		if (!cache || !cache.frontmatter || !cache.frontmatter.cards) {
			const emptyState = container.createDiv({ cls: 'arete-empty-state' });
			emptyState.style.textAlign = 'center';
			emptyState.style.padding = '2rem';

			emptyState.createEl('p', { text: 'No cards found in frontmatter.' });
			const btn = emptyState.createEl('button', {
				cls: 'arete-primary-btn arete-text-btn',
				text: 'Initialize Cards',
			});
			btn.onclick = async () => {
				await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
					if (!frontmatter.cards) frontmatter.cards = [];
				});
				this.render();
			};
			return;
		}

		const cards: CardData[] = cache.frontmatter.cards;

		// Header
		const headerContainer = container.createDiv({ cls: 'arete-header-container' });

		const title = headerContainer.createEl('h3', { text: `${activeFile.basename}` });
		title.createSpan({ text: ` (${cards.length})`, cls: 'arete-muted' });
		title.style.margin = '0';

		const toggleBtn = headerContainer.createEl('button', { cls: 'arete-icon-btn' });
		setIcon(toggleBtn, this.previewMode ? 'pencil' : 'eye');
		toggleBtn.createSpan({ text: this.previewMode ? 'Edit' : 'Preview' });
		toggleBtn.onclick = () => {
			this.previewMode = !this.previewMode;
			// Note: We intentionally keep expandedIndices when toggling modes
			this.render();
		};

		const listContainer = container.createDiv({ cls: 'arete-card-list' });

		// We assume 1 model per file usually, or per card.
		// For efficiency, we can prefetch if model is uniform, but here we do it per card safely.

		for (let index = 0; index < cards.length; index++) {
			const card = cards[index];
			const cardEl = listContainer.createDiv({ cls: 'arete-card-item' });

			const HIDDEN_FIELDS = ['nid', 'cid', 'model', 'deck', 'tags'];
			const allKeys = Object.keys(card);
			const keys = allKeys.filter((k) => !HIDDEN_FIELDS.includes(k.toLowerCase()));

			const details = cardEl.createEl('details');

			// State Preservation
			if (this.expandedIndices.has(index)) {
				details.open = true;
			}

			details.ontoggle = () => {
				if (details.open) {
					this.expandedIndices.add(index);
				} else {
					this.expandedIndices.delete(index);
				}
			};

			const summary = details.createEl('summary');

			const summaryTitle = summary.createSpan({ cls: 'arete-card-title' });
			const frontText =
				card['front'] || card['Front'] || (keys.length > 0 ? card[keys[0]] : 'New Card');
			const previewText =
				typeof frontText === 'string' && frontText.length > 50
					? frontText.substring(0, 50) + '...'
					: frontText;
			summaryTitle.setText(`${index + 1}. ${previewText}`);

			// Delete Action
			const deleteBtn = summary.createEl('button', {
				cls: 'arete-icon-btn',
				attr: { 'aria-label': 'Delete Card' },
			});
			setIcon(deleteBtn, 'trash-2');
			deleteBtn.onclick = async (e) => {
				e.preventDefault();
				e.stopPropagation();
				await this.deleteCard(index);
			};

			const contentDiv = details.createDiv({ cls: 'arete-card-content' });

			// Actions Bar
			const actionsContainer = contentDiv.createDiv({ cls: 'arete-card-actions' });

			const gotoBtn = actionsContainer.createEl('button', { cls: 'arete-text-btn' });
			setIcon(gotoBtn, 'map-pin');
			gotoBtn.createSpan({ text: 'YAML' });
			gotoBtn.onclick = () => {
				// Set active card highlight in sidebar
				this.setActiveCard(index);
				// Trigger highlight in editor
				this.plugin.highlightCardLines(index);
				this.scrollToCard(index);
			};

			if (card['nid']) {
				const ankiBtn = actionsContainer.createEl('button', { cls: 'arete-text-btn' });
				setIcon(ankiBtn, 'link');
				ankiBtn.createSpan({ text: `${card['nid']}` });
				ankiBtn.title = 'Open in Anki Browser';
				ankiBtn.onclick = async () => {
					await this.openInAnki(card['nid']);
				};
			}

			// Render Logic: Preview Mode
			if (this.previewMode) {
				const fields = { ...card }; // Clone
				const isObsidianMode = this.plugin.settings.renderer_mode === 'obsidian';

				// Helper to find value case-insensitively
				const getField = (name: string) => {
					const key = Object.keys(fields).find(
						(k) => k.toLowerCase() === name.toLowerCase(),
					);
					return key ? fields[key] : '';
				};

				const renderContainer = contentDiv.createDiv({ cls: 'arete-preview-container' });
				renderContainer.style.display = 'flex';
				renderContainer.style.flexDirection = 'column';
				renderContainer.style.gap = '16px';
				renderContainer.style.padding = '16px';

				const rendererLabel = isObsidianMode ? 'Obsidian' : 'Anki';

				// Front
				const frontDiv = renderContainer.createDiv({ cls: 'arete-preview-side' });
				frontDiv.createEl('strong', { text: `Front Preview (${rendererLabel} Mode)` });
				const frontContentDiv = frontDiv.createDiv({ cls: 'arete-preview-content' });

				// Back
				const backDiv = renderContainer.createDiv({ cls: 'arete-preview-side' });
				backDiv.createEl('strong', { text: `Back Preview (${rendererLabel} Mode)` });
				const backContentDiv = backDiv.createDiv({ cls: 'arete-preview-content' });

				if (isObsidianMode) {
					// OBSIDIAN MODE: Direct MarkdownRenderer on card fields (no templates, no Shadow DOM)
					// This properly renders Markdown + LaTeX using Obsidian's native renderer
					const frontText = getField('front') || '*Empty Front*';
					const backText = getField('back') || '*Empty Back*';

					await MarkdownRenderer.render(
						this.app,
						frontText,
						frontContentDiv,
						activeFile.path,
						this,
					);

					await MarkdownRenderer.render(
						this.app,
						backText,
						backContentDiv,
						activeFile.path,
						this,
					);
				} else {
					// ANKI MODE: Use templates with Shadow DOM for CSS isolation
					const modelName = card['model'] || card['Model'] || 'Basic';

					// Replace content divs with shadow hosts
					frontContentDiv.empty();
					backContentDiv.empty();
					const shadowFront = frontContentDiv.attachShadow({ mode: 'open' });
					const shadowBack = backContentDiv.attachShadow({ mode: 'open' });

					try {
						console.log(
							`[Arete] Attempting to render Anki preview for model: ${modelName}`,
						);
						const frontResult = await this.plugin.templateRenderer.render(
							modelName,
							'Front',
							fields,
						);
						const backResult = await this.plugin.templateRenderer.render(
							modelName,
							'Back',
							fields,
						);

						const injectStyles = (root: ShadowRoot, css: string) => {
							const style = document.createElement('style');
							style.textContent = css;
							root.appendChild(style);
						};

						if (frontResult) {
							injectStyles(shadowFront, frontResult.css);
							const wrapper = document.createElement('div');
							wrapper.className = 'card';
							wrapper.innerHTML = frontResult.html;
							shadowFront.appendChild(wrapper);
						} else {
							shadowFront.innerHTML = '<p><em>Template not found</em></p>';
						}

						if (backResult) {
							injectStyles(shadowBack, backResult.css);
							const wrapper = document.createElement('div');
							wrapper.className = 'card';
							wrapper.innerHTML = backResult.html;
							shadowBack.appendChild(wrapper);
						} else {
							shadowBack.innerHTML = '<p><em>Template not found</em></p>';
						}
					} catch (e) {
						console.warn('Failed to render Anki preview', e);
						shadowFront.innerHTML = '<p><em>Error loading template</em></p>';
						shadowBack.innerHTML = '<p><em>Error loading template</em></p>';
					}
				}
			} else {
				// EDIT MODE
				const seenLower = new Set<string>();
				const uniqueKeys = keys.filter((k) => {
					const lower = k.toLowerCase();
					if (seenLower.has(lower)) return false;
					seenLower.add(lower);
					return true;
				});

				uniqueKeys.forEach((key) => {
					const fieldContainer = contentDiv.createDiv({ cls: 'arete-card-field' });
					fieldContainer.createEl('label', { text: key });

					const input = fieldContainer.createEl('textarea');
					input.value = card[key] || '';
					input.rows = 3;

					input.onblur = async () => {
						await this.updateCard(index, key, input.value);
					};
				});
			}
		}

		const addBtn = container.createEl('button', { cls: 'arete-primary-btn arete-text-btn' });
		addBtn.style.width = '100%';
		addBtn.style.justifyContent = 'center';
		addBtn.style.marginTop = '1rem';
		setIcon(addBtn, 'plus');
		addBtn.createSpan({ text: 'Add New Card' });
		addBtn.onclick = async () => {
			await this.addCard();
		};
	}

	async updateCard(index: number, key: string, value: string) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (frontmatter.cards && frontmatter.cards[index]) {
				frontmatter.cards[index][key] = value;
			}
		});
	}

	async addCard() {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (!frontmatter.cards) frontmatter.cards = [];
			frontmatter.cards.push({ front: '', back: '' });
		});
	}

	async deleteCard(index: number) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (frontmatter.cards) {
				frontmatter.cards.splice(index, 1);
			}
		});
	}

	async openInAnki(nid: number | string) {
		const url = this.plugin.settings.anki_connect_url || 'http://127.0.0.1:8765';
		try {
			const response = await requestUrl({
				url: url,
				method: 'POST',
				body: JSON.stringify({
					action: 'guiBrowse',
					version: 6,
					params: {
						query: `nid:${nid}`,
					},
				}),
			});

			const result = response.json;
			if (result.error) {
				new Notice(`Anki Error: ${result.error}`);
			} else {
				new Notice('Opened in Anki Browser');
			}
		} catch (e) {
			new Notice('Failed to connect to Anki. Is it running with AnkiConnect?');
			console.error(e);
		}
	}

	async scrollToCard(index: number) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		const leaf = this.app.workspace.getMostRecentLeaf();
		if (leaf && leaf.view instanceof MarkdownView) {
			const editor = leaf.view.editor;
			const fileContent = editor.getValue();

			const lines = fileContent.split('\n');
			let cardsStartLine = -1;

			for (let i = 0; i < lines.length; i++) {
				if (lines[i].trim().startsWith('cards:')) {
					cardsStartLine = i;
					break;
				}
			}

			if (cardsStartLine === -1) {
				new Notice('Could not find "cards" list in YAML.');
				return;
			}

			let cardCount = -1;
			let targetLine = cardsStartLine;

			for (let i = cardsStartLine + 1; i < lines.length; i++) {
				const line = lines[i];
				if (line.trim().startsWith('-')) {
					cardCount++;
					if (cardCount === index) {
						targetLine = i;
						break;
					}
				}
				if (
					line.trim() === '---' ||
					(line.trim().length > 0 && !line.startsWith(' ') && !line.startsWith('-'))
				) {
					break;
				}
			}

			editor.setCursor({ line: targetLine, ch: 0 });
			editor.scrollIntoView(
				{ from: { line: targetLine, ch: 0 }, to: { line: targetLine, ch: 0 } },
				true,
			);
		}
	}

	// Set the active card (visual highlight in sidebar)
	setActiveCard(index: number | null) {
		this.activeCardIndex = index;
		// Update visual state
		const container = this.containerEl.querySelector('.arete-card-list');
		if (!container) return;

		// Remove active class from all cards
		container.querySelectorAll('.arete-card-item').forEach((el) => {
			el.classList.remove('arete-card-active');
		});

		// Add active class to selected card
		if (index !== null) {
			const cardEls = container.querySelectorAll('.arete-card-item');
			if (cardEls[index]) {
				cardEls[index].classList.add('arete-card-active');
			}
		}
	}
}
