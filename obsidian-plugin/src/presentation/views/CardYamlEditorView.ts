import {
	ItemView,
	WorkspaceLeaf,
	MarkdownView,
	Menu,
	setIcon,
	MarkdownRenderer,
	Notice,
	requestUrl,
} from 'obsidian';
import { EditorView, lineNumbers, keymap } from '@codemirror/view';
import { EditorState, Annotation } from '@codemirror/state';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { yaml } from '@codemirror/lang-yaml';
import type AretePlugin from '@/main';
import { ProblematicCard, AnkiCardStats } from '@application/services/StatsService';

export const YAML_EDITOR_VIEW_TYPE = 'arete-yaml-editor';

interface CardData {
	[key: string]: any;
}

// Annotation to prevent infinite sync loops
const syncAnnotation = Annotation.define<boolean>();

// ─────────────────────────────────────────────────────────────
// Enums & Interfaces
// ─────────────────────────────────────────────────────────────

enum ViewMode {
	Source = 'source',
	Fields = 'fields',
	Preview = 'preview',
}

export class CardYamlEditorView extends ItemView {
	plugin: AretePlugin;
	private editorView: EditorView | null = null;
	private indexContainer: HTMLElement | null = null;
	private editorContainer: HTMLElement | null = null;
	private fieldEditorContainer: HTMLElement | null = null;
	private previewContainer: HTMLElement | null = null;
	private toolbarContainer: HTMLElement | null = null;

	private currentCardIndex = 0;
	private cards: CardData[] = [];

	private currentFilePath: string | null = null;
	private isUpdatingFromMain = false;
	private viewMode: ViewMode = ViewMode.Fields; // Default to Fields as requested "Card Edit Mode"
	private syncDebounceTimer: ReturnType<typeof setTimeout> | null = null;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType() {
		return 'arete-yaml-editor';
	}

	getDisplayText() {
		return 'Card Editor';
	}

	getIcon() {
		return 'file-code';
	}

	async onOpen() {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-yaml-editor-container');

		// Create split layout
		this.indexContainer = container.createDiv({ cls: 'arete-yaml-index' });

		const rightPanel = container.createDiv({ cls: 'arete-yaml-editor-panel' });

		// Toolbar
		this.toolbarContainer = rightPanel.createDiv({ cls: 'arete-editor-toolbar' });

		// Containers for different modes

		// 1. Source Mode (CodeMirror)
		this.editorContainer = rightPanel.createDiv({ cls: 'arete-yaml-editor-wrapper' });
		this.editorContainer.style.overflow = 'auto';

		// 2. Field Mode (Inputs)
		this.fieldEditorContainer = rightPanel.createDiv({ cls: 'arete-field-editor' });
		this.fieldEditorContainer.hide();

		// 3. Preview Mode (Rendered)
		this.previewContainer = rightPanel.createDiv({ cls: 'arete-preview-container' });
		this.previewContainer.hide();

		// Initial render
		await this.loadCards();
		this.renderIndex();
		this.renderToolbar();
		this.createEditor();
		this.setViewMode(this.viewMode);

		// Register events for sync
		this.registerEvent(
			this.app.workspace.on('active-leaf-change', () => {
				this.handleActiveFileChange();
			}),
		);

		this.registerEvent(
			this.app.vault.on('modify', (file) => {
				const activeFile = this.app.workspace.getActiveFile();
				if (activeFile && activeFile.path === file.path && !this.isUpdatingFromMain) {
					this.syncFromMain();
				}
			}),
		);

		// Keyboard navigation on index
		this.indexContainer?.addEventListener('keydown', (e) => this.handleKeyNavigation(e));
	}

	async onClose() {
		if (this.editorView) {
			this.editorView.destroy();
			this.editorView = null;
		}
		if (this.syncDebounceTimer) {
			clearTimeout(this.syncDebounceTimer);
		}
	}

	private async loadCards() {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) {
			this.cards = [];
			this.currentFilePath = null;
			return;
		}

		// Only reset index if file changed
		if (this.currentFilePath !== activeFile.path) {
			this.currentCardIndex = 0;
			this.currentFilePath = activeFile.path;
		}

		const cache = this.app.metadataCache.getFileCache(activeFile);
		if (cache?.frontmatter?.cards && Array.isArray(cache.frontmatter.cards)) {
			this.cards = cache.frontmatter.cards;
		} else {
			this.cards = [];
		}

		// Ensure currentCardIndex is valid
		if (this.currentCardIndex >= this.cards.length) {
			this.currentCardIndex = Math.max(0, this.cards.length - 1);
		}
	}

	private handleActiveFileChange() {
		// loadCards now handles the logic of whether to reset index or not
		this.loadCards().then(() => {
			this.renderIndex();
			this.refreshActiveView();
		});
	}

	private refreshActiveView() {
		this.renderToolbar(); // Ensure toolbar stats update when card changes
		if (this.viewMode === ViewMode.Source) {
			this.updateEditorContent();
		} else if (this.viewMode === ViewMode.Fields) {
			this.renderFieldEditor();
		} else if (this.viewMode === ViewMode.Preview) {
			this.renderPreview();
		}
	}

	// ─────────────────────────────────────────────────────────────
	// Index Sidebar
	// ─────────────────────────────────────────────────────────────

	private renderIndex() {
		if (!this.indexContainer) return;
		this.indexContainer.empty();

		const activeFile = this.app.workspace.getActiveFile();

		// Header
		const header = this.indexContainer.createDiv({ cls: 'arete-yaml-index-header' });
		header.createSpan({ text: `${this.cards.length}`, cls: 'arete-yaml-index-count' });

		// Card list
		const listContainer = this.indexContainer.createDiv({ cls: 'arete-yaml-index-list' });
		listContainer.setAttribute('tabindex', '0'); // For keyboard nav

		this.cards.forEach((card, index) => {
			const item = listContainer.createDiv({
				cls: 'arete-yaml-index-item',
				attr: {
					'data-index': String(index),
					draggable: 'true',
				},
			});

			// Status indicator
			const hasWarning = this.getCardWarning(index);
			if (hasWarning) {
				item.addClass('has-warning');
				const warningIcon = item.createSpan({ cls: 'arete-yaml-index-warning' });
				setIcon(warningIcon, 'alert-triangle');
			}

			// Card number
			item.createSpan({ text: `${index + 1}`, cls: 'arete-yaml-index-number' });

			// Active state
			if (index === this.currentCardIndex) {
				item.addClass('is-active');
			}

			// Tooltip with front preview
			const frontText = card['front'] || card['Front'] || '';
			if (frontText) {
				item.setAttribute(
					'title',
					frontText.substring(0, 50) + (frontText.length > 50 ? '...' : ''),
				);
			}

			// Click handler
			item.addEventListener('click', () => {
				this.selectCard(index, true);
			});

			// Right-click context menu
			item.addEventListener('contextmenu', (e) => this.showCardContextMenu(e, index));

			// Drag handlers
			item.addEventListener('dragstart', (e) => this.handleDragStart(e, index));
			item.addEventListener('dragover', (e) => this.handleDragOver(e));
			item.addEventListener('drop', (e) => this.handleDrop(e, index));
			item.addEventListener('dragend', () => this.handleDragEnd());
		});

		// Add button
		const addBtn = this.indexContainer.createDiv({ cls: 'arete-yaml-index-add' });
		setIcon(addBtn, 'plus');
		addBtn.setAttribute('title', 'Add new card');
		addBtn.addEventListener('click', () => this.addCard());
	}

	private getCardWarning(index: number): ProblematicCard | null {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile || !this.plugin.statsService) return null;

		const stats = this.plugin.statsService.getCache().concepts[activeFile.path];
		if (!stats?.problematicCards) return null;

		const card = this.cards[index];
		if (!card?.nid) return null;

		return stats.problematicCards.find((c) => c.noteId === card.nid) || null;
	}

	private showCardContextMenu(e: MouseEvent, index: number) {
		e.preventDefault();
		const menu = new Menu();

		menu.addItem((item) => {
			item.setTitle('Delete Card')
				.setIcon('trash-2')
				.onClick(() => this.deleteCard(index));
		});

		menu.showAtMouseEvent(e);
	}

	// ─────────────────────────────────────────────────────────────
	// Toolbar & Preview
	// ─────────────────────────────────────────────────────────────

	public renderToolbar() {
		if (!this.toolbarContainer) return;
		this.toolbarContainer.empty();

		// LEFT: Stats
		const leftGroup = this.toolbarContainer.createDiv({ cls: 'arete-toolbar-group' });

		const card = this.cards[this.currentCardIndex];
		const nid = card?.nid ? parseInt(card.nid) : card?.id ? parseInt(card.id) : null;
		const cid = card?.cid ? parseInt(card.cid) : null;

		if (nid || cid) {
			// Get full concept stats
			const filePath = this.currentFilePath;
			const conceptStats = filePath
				? this.plugin.statsService.getCache().concepts[filePath]
				: null;

			// Priority Lookup: CID > NID
			let stats = null;
			let lookupSource = 'none';

			if (conceptStats?.cardStats) {
				if (cid && conceptStats.cardStats[cid]) {
					stats = conceptStats.cardStats[cid];
					lookupSource = 'cid';
				} else if (nid && conceptStats.cardStats[nid]) {
					stats = conceptStats.cardStats[nid];
					lookupSource = 'nid';
				}
			}

			if (this.plugin.settings.debug_mode) {
				console.log(
					`[Arete Toolbar] Card ${this.currentCardIndex + 1}: Found via ${lookupSource}`,
					stats ? `(Diff: ${stats.difficulty})` : '(No Stats)',
				);
			}

			if (stats) {
				const statsContainer = leftGroup.createDiv({ cls: 'arete-toolbar-stats' });

				// Stats Badge (Based on Config)
				const algo = this.plugin.settings.stats_algorithm;

				let badgeAdded = false;

				if (algo === 'fsrs') {
					// FSRS mode
					if (stats.difficulty !== undefined && stats.difficulty !== null) {
						const diff = Math.round(stats.difficulty * 100);
						// FSRS Difficulty
						let cls = 'arete-stat-badge';
						if (stats.difficulty > 0.9)
							cls += ' mod-warning'; // Red
						else if (stats.difficulty > 0.5)
							cls += ' mod-orange'; // Orange
						else cls += ' mod-success'; // Green (Easy)

						statsContainer.createDiv({
							cls: cls,
							text: `D: ${diff}%`,
							attr: { title: `FSRS Difficulty: ${diff}%` },
						});
					} else {
						// Null difficulty - show ?
						statsContainer.createDiv({
							cls: 'arete-stat-badge mod-muted',
							text: `D: ?`,
							attr: { title: 'FSRS Difficulty not available (new or unsynced card)' },
						});
					}
					badgeAdded = true;
				} else if (algo === 'sm2' || stats.ease !== undefined) {
					// SM2 (Fallback if FSRS missing or SM2 selected)
					const ease = Math.round(stats.ease / 10);
					statsContainer.createDiv({
						cls: 'arete-stat-badge',
						text: `E: ${ease}%`,
						attr: { title: `SM-2 Ease: ${ease}%` },
					});
					badgeAdded = true;
				}

				// Lapses
				if (stats.lapses > 0) {
					// Lapses
					if (stats.lapses > 0) {
						let lapseCls = 'arete-stat-badge';
						if (stats.lapses > 5) lapseCls += ' mod-warning';
						else lapseCls += ' mod-orange';

						statsContainer.createDiv({
							cls: lapseCls,
							text: `${stats.lapses}L`,
							attr: { title: `Lapses: ${stats.lapses}` },
						});
						badgeAdded = true;
					}
					badgeAdded = true;
				}

				// Due
				if (stats.due) {
					const dueDate = new Date(stats.due * 1000); // Anki uses seconds
					const now = new Date();
					const diffDays = Math.ceil(
						(dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
					);
					let dueText = '';
					if (diffDays < 0) dueText = `${Math.abs(diffDays)}d ago`;
					else if (diffDays === 0) dueText = 'Today';
					else dueText = `${diffDays}d`;

					statsContainer.createDiv({
						cls: 'arete-stat-badge mod-muted',
						text: dueText,
						attr: { title: `Due: ${dueDate.toLocaleDateString()}` },
					});
					badgeAdded = true;
				}

				if (!badgeAdded) {
					statsContainer.createDiv({
						cls: 'arete-stat-badge mod-muted',
						text: 'No Data',
						attr: { title: 'Stats object found but values are empty/undefined' },
					});
				}
			} else {
				// Stats not found in cache
				leftGroup.createDiv({
					cls: 'arete-stat-badge mod-muted',
					text: 'No Stats',
					attr: {
						title: `Stats not found for NID ${nid}. Try running "Arete: Refresh Anki Stats"`,
					},
				});
				console.log('[Arete] Stats miss for NID:', nid);
			}
		} else {
			// No NID
			// Do nothing or show "Unlinked"?
			// leftGroup.createDiv({ text: 'Unlinked', cls: 'arete-stat-badge mod-muted' });
		}

		// CENTER: Navigation
		const centerGroup = this.toolbarContainer.createDiv({ cls: 'arete-toolbar-group' });

		// Go to YAML in Note
		const yamlBtn = centerGroup.createDiv({
			cls: 'arete-toolbar-btn',
			attr: { title: 'Go to YAML in Note' },
		});
		setIcon(yamlBtn, 'file-text');
		yamlBtn.addEventListener('click', () => this.scrollToCard(this.currentCardIndex));

		// Open in Anki
		const ankiBtn = centerGroup.createDiv({
			cls: 'arete-toolbar-btn',
			attr: { title: 'Open in Anki' },
		});
		setIcon(ankiBtn, 'external-link');
		ankiBtn.addEventListener('click', () => this.openInAnki(this.currentCardIndex));

		// RIGHT: View Mode Toggle
		const rightGroup = this.toolbarContainer.createDiv({ cls: 'arete-toolbar-group' });

		// Fields Mode Button (Edit Card)
		const fieldsBtn = rightGroup.createDiv({
			cls: `arete-toolbar-btn ${this.viewMode === ViewMode.Fields ? 'is-active' : ''}`,
			attr: { title: 'Card Edit Mode' },
		});
		setIcon(fieldsBtn, 'pencil');
		fieldsBtn.addEventListener('click', () => this.setViewMode(ViewMode.Fields));

		// Source Mode Button (YAML)
		const sourceBtn = rightGroup.createDiv({
			cls: `arete-toolbar-btn ${this.viewMode === ViewMode.Source ? 'is-active' : ''}`,
			attr: { title: 'Source Mode (YAML)' },
		});
		setIcon(sourceBtn, 'code');
		sourceBtn.addEventListener('click', () => this.setViewMode(ViewMode.Source));

		// Preview Mode Button
		const previewBtn = rightGroup.createDiv({
			cls: `arete-toolbar-btn ${this.viewMode === ViewMode.Preview ? 'is-active' : ''}`,
			attr: { title: 'Preview Mode' },
		});
		setIcon(previewBtn, 'eye');
		previewBtn.addEventListener('click', () => this.setViewMode(ViewMode.Preview));
	}

	private setViewMode(mode: ViewMode) {
		this.viewMode = mode;

		// Hide all
		this.editorContainer?.style.setProperty('display', 'none');
		this.fieldEditorContainer?.hide();
		this.previewContainer?.hide();

		// Show active
		if (mode === ViewMode.Source) {
			this.editorContainer?.style.setProperty('display', 'block');
			// Refresh content if needed - usually synchronized
			this.updateEditorContent();
		} else if (mode === ViewMode.Fields) {
			this.fieldEditorContainer?.show();
			this.renderFieldEditor();
		} else if (mode === ViewMode.Preview) {
			this.previewContainer?.show();
			this.renderPreview();
		}

		this.renderToolbar();
	}

	// ─────────────────────────────────────────────────────────────
	// Field Editor Logic
	// ─────────────────────────────────────────────────────────────

	private renderFieldEditor() {
		if (!this.fieldEditorContainer) return;
		this.fieldEditorContainer.empty();

		if (this.currentCardIndex < 0 || this.currentCardIndex >= this.cards.length) {
			this.fieldEditorContainer.createEl('p', { text: 'No card selected' });
			return;
		}

		const card = this.cards[this.currentCardIndex];

		// Model Badge
		const model = card['model'] || card['Model'] || 'Basic';
		this.fieldEditorContainer.createDiv({
			cls: 'arete-field-model-badge',
			text: String(model),
		});

		// Determine fields based on model
		// For now, support Basic (Front/Back) and Cloze (Text/Extra) generically
		// Any other keys in the card object (excluding nid, cid, model) are fields

		const hiddenKeys = ['nid', 'cid', 'id', 'model', 'tags'];

		// Helper to render field
		const renderField = (key: string, label: string) => {
			const group = this.fieldEditorContainer!.createDiv({ cls: 'arete-field-group' });
			group.createEl('label', { cls: 'arete-field-label', text: label });

			const value = card[key] || '';
			const textarea = group.createEl('textarea', {
				cls: 'arete-field-input',
				text: String(value),
			});

			// Auto-resize textarea to fit content
			const autoResize = () => {
				textarea.style.height = 'auto';
				textarea.style.height = textarea.scrollHeight + 'px';
			};

			// Initial resize
			setTimeout(autoResize, 0);

			// Auto-save on input (debounced could be better, but 'change' is safe for now)
			// 'input' event for real-time feel, debounced
			let debounceTimer: ReturnType<typeof setTimeout>;
			textarea.addEventListener('input', () => {
				autoResize();
				clearTimeout(debounceTimer);
				debounceTimer = setTimeout(() => {
					this.updateCardField(this.currentCardIndex, key, textarea.value);
				}, 500);
			});
		};

		// specific order for common models
		if (String(model).toLowerCase().includes('cloze')) {
			renderField('Text', 'Text');
			renderField('Extra', 'Extra');
		} else {
			// Basic and others
			// Try to find Front/Back case-insensitively
			const frontKey = Object.keys(card).find((k) => k.toLowerCase() === 'front') || 'Front';
			const backKey = Object.keys(card).find((k) => k.toLowerCase() === 'back') || 'Back';

			renderField(frontKey, 'Front');
			renderField(backKey, 'Back');
		}

		// Render other fields? Maybe too cluttered for now.
		// User asked for "just looks at the fields not the entire card yaml code"
		// Start with core fields.
	}

	private async updateCardField(index: number, key: string, value: string) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		// Update local state immediately to keep UI in sync
		if (this.cards[index]) {
			this.cards[index][key] = value;
		}

		// Set flag to prevent syncFromMain from triggering a re-render (which kills focus)
		this.isUpdatingFromMain = true;

		try {
			await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
				if (frontmatter.cards && frontmatter.cards[index]) {
					frontmatter.cards[index][key] = value;
				}
			});
		} finally {
			// Reset flag after delay to allow 'modify' event to pass
			setTimeout(() => {
				this.isUpdatingFromMain = false;
			}, 300);
		}
	}

	private async renderPreview() {
		if (!this.previewContainer) return;
		this.previewContainer.empty();

		if (this.currentCardIndex < 0 || this.currentCardIndex >= this.cards.length) {
			this.previewContainer.createEl('p', { text: 'No card selected' });
			return;
		}

		const card = this.cards[this.currentCardIndex];
		const activeFile = this.app.workspace.getActiveFile();
		const path = activeFile ? activeFile.path : '';

		// Front
		const frontSection = this.previewContainer.createDiv({ cls: 'arete-preview-section' });
		frontSection.createDiv({ cls: 'arete-preview-label', text: 'Front' });
		const frontContent = frontSection.createDiv({
			cls: 'arete-preview-content markdown-rendered',
		});
		const frontText = card['front'] || card['Front'] || '';
		await MarkdownRenderer.render(this.app, frontText, frontContent, path, this);

		// Back
		const backSection = this.previewContainer.createDiv({ cls: 'arete-preview-section' });
		backSection.createDiv({ cls: 'arete-preview-label', text: 'Back' });
		const backContent = backSection.createDiv({
			cls: 'arete-preview-content markdown-rendered',
		});
		const backText = card['back'] || card['Back'] || '';
		await MarkdownRenderer.render(this.app, backText, backContent, path, this);

		// Metadata
		if (card.nid || card.id) {
			const metaSection = this.previewContainer.createDiv({ cls: 'arete-preview-section' });
			metaSection.createDiv({ cls: 'arete-preview-label', text: 'Metadata' });
			const metaContent = metaSection.createDiv({ cls: 'arete-preview-content' });
			metaContent.createEl('code', { text: `NID: ${card.nid || card.id}` });
		}
	}

	private async openInAnki(index: number) {
		if (index < 0 || index >= this.cards.length) return;
		const card = this.cards[index];
		const nid = card.nid || card.id;

		if (!nid) {
			new Notice('Card has no Note ID (nid/id). Sync it first?');
			return;
		}

		try {
			// Using AnkiConnect guiBrowse
			const response = await requestUrl({
				url: 'http://127.0.0.1:8765',
				method: 'POST',
				body: JSON.stringify({
					action: 'guiBrowse',
					version: 6,
					params: { query: `nid:${nid}` },
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

	private scrollToCard(index: number) {
		const leaf = this.app.workspace.getMostRecentLeaf();
		if (leaf && leaf.view instanceof MarkdownView) {
			const editor = leaf.view.editor;
			const fileContent = editor.getValue();

			// This is a naive scroll implementation.
			// For robustness, ideally we reuse the parser logic from CardGutterExtension
			// But simple grep-like search works for now as in CardView.ts

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
			editor.focus();
		} else {
			new Notice('Main editor not found to scroll to.');
		}
	}

	// ─────────────────────────────────────────────────────────────
	// Drag & Drop Reordering
	// ─────────────────────────────────────────────────────────────

	private draggedIndex: number | null = null;

	private handleDragStart(e: DragEvent, index: number) {
		this.draggedIndex = index;
		const target = e.target as HTMLElement;
		target.addClass('is-dragging');
		e.dataTransfer?.setData('text/plain', String(index));
	}

	private handleDragOver(e: DragEvent) {
		e.preventDefault();
		const target = e.target as HTMLElement;
		const item = target.closest('.arete-yaml-index-item') as HTMLElement;
		if (item) {
			// Remove previous indicators
			this.indexContainer
				?.querySelectorAll('.drag-over')
				.forEach((el) => el.removeClass('drag-over'));
			item.addClass('drag-over');
		}
	}

	private handleDrop(e: DragEvent, toIndex: number) {
		e.preventDefault();
		if (this.draggedIndex !== null && this.draggedIndex !== toIndex) {
			this.reorderCards(this.draggedIndex, toIndex);
		}
		this.handleDragEnd();
	}

	private handleDragEnd() {
		this.draggedIndex = null;
		this.indexContainer?.querySelectorAll('.is-dragging, .drag-over').forEach((el) => {
			el.removeClass('is-dragging');
			el.removeClass('drag-over');
		});
	}

	// ─────────────────────────────────────────────────────────────
	// Keyboard Navigation
	// ─────────────────────────────────────────────────────────────

	private handleKeyNavigation(e: KeyboardEvent) {
		if (e.key === 'ArrowUp') {
			e.preventDefault();
			if (this.currentCardIndex > 0) {
				this.selectCard(this.currentCardIndex - 1, true);
			}
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (this.currentCardIndex < this.cards.length - 1) {
				this.selectCard(this.currentCardIndex + 1, true);
			}
		}
	}

	// ─────────────────────────────────────────────────────────────
	// CodeMirror Editor
	// ─────────────────────────────────────────────────────────────

	private createEditor() {
		if (!this.editorContainer) return;
		this.editorContainer.empty();

		const content = this.extractCardYaml(this.currentCardIndex);

		const startState = EditorState.create({
			doc: content,
			extensions: [
				yaml(),
				lineNumbers(),
				history(),
				keymap.of([...defaultKeymap, ...historyKeymap]),
				EditorView.lineWrapping,
				EditorView.updateListener.of((update) => {
					if (update.docChanged) {
						const isSync = update.transactions.some((tr) =>
							tr.annotation(syncAnnotation),
						);
						if (!isSync) {
							this.debouncedSyncToMain();
						}
					}
				}),
				EditorView.theme({
					'&': { minHeight: '100px' },
					'.cm-scroller': { overflow: 'visible' },
				}),
			],
		});

		this.editorView = new EditorView({
			state: startState,
			parent: this.editorContainer,
		});
	}

	private updateEditorContent() {
		if (!this.editorView) return;

		const content = this.extractCardYaml(this.currentCardIndex);
		const currentContent = this.editorView.state.doc.toString();

		if (content !== currentContent) {
			this.editorView.dispatch({
				changes: { from: 0, to: this.editorView.state.doc.length, insert: content },
				annotations: syncAnnotation.of(true),
			});
		}
	}

	private extractCardYaml(index: number): string {
		if (index < 0 || index >= this.cards.length) {
			return '# No card selected\n';
		}

		const card = this.cards[index];
		const lines: string[] = [];

		// Convert card object to YAML format
		for (const [key, value] of Object.entries(card)) {
			if (typeof value === 'string' && value.includes('\n')) {
				// Multi-line string
				lines.push(`${key}: |`);
				value.split('\n').forEach((line) => lines.push(`  ${line}`));
			} else if (Array.isArray(value)) {
				// Array
				lines.push(`${key}:`);
				value.forEach((item) => lines.push(`  - ${item}`));
			} else if (value !== undefined && value !== null) {
				// Simple value
				const strValue = String(value);
				// Quote strings that need it
				if (strValue.includes(':') || strValue.includes('#') || strValue.startsWith('"')) {
					lines.push(`${key}: "${strValue.replace(/"/g, '\\"')}"`);
				} else {
					lines.push(`${key}: ${strValue}`);
				}
			}
		}

		return lines.join('\n') + '\n';
	}

	private parseYamlToCard(yamlContent: string): CardData {
		const card: CardData = {};
		const lines = yamlContent.split('\n');
		let currentKey: string | null = null;
		let currentValue: string[] = [];
		let isMultiline = false;
		let isArray = false;

		const saveCurrentKey = () => {
			if (currentKey) {
				if (isArray) {
					card[currentKey] = currentValue;
				} else if (isMultiline) {
					card[currentKey] = currentValue.join('\n');
				}
				currentKey = null;
				currentValue = [];
				isMultiline = false;
				isArray = false;
			}
		};

		for (const line of lines) {
			const trimmed = line.trim();
			if (!trimmed || trimmed.startsWith('#')) continue;

			// Check for new key
			const keyMatch = line.match(/^(\w+):\s*(.*)/);
			if (keyMatch && !line.startsWith('  ')) {
				saveCurrentKey();
				const key = keyMatch[1];
				const value = keyMatch[2].trim();

				if (value === '|') {
					// Multi-line string
					currentKey = key;
					isMultiline = true;
				} else if (value === '') {
					// Possibly an array
					currentKey = key;
					isArray = true;
				} else {
					// Simple value
					let parsedValue: any = value;
					// Remove quotes if present
					if (value.startsWith('"') && value.endsWith('"')) {
						parsedValue = value.slice(1, -1).replace(/\\"/g, '"');
					} else if (!isNaN(Number(value))) {
						parsedValue = Number(value);
					}
					card[key] = parsedValue;
				}
			} else if (currentKey && line.startsWith('  ')) {
				// Continuation line
				const content = line.substring(2);
				if (isArray && content.startsWith('- ')) {
					currentValue.push(content.substring(2));
				} else {
					currentValue.push(content);
				}
			}
		}

		saveCurrentKey();
		return card;
	}

	// ─────────────────────────────────────────────────────────────
	// Sync Logic
	// ─────────────────────────────────────────────────────────────

	private debouncedSyncToMain() {
		if (this.syncDebounceTimer) {
			clearTimeout(this.syncDebounceTimer);
		}
		this.syncDebounceTimer = setTimeout(() => this.syncToMain(), 300);
	}

	private async syncToMain() {
		if (!this.editorView) return;
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		const yamlContent = this.editorView.state.doc.toString();
		const updatedCard = this.parseYamlToCard(yamlContent);

		this.isUpdatingFromMain = true;
		try {
			await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
				if (frontmatter.cards && frontmatter.cards[this.currentCardIndex]) {
					frontmatter.cards[this.currentCardIndex] = updatedCard;
				}
			});
		} finally {
			// Small delay before allowing sync from main again
			setTimeout(() => {
				this.isUpdatingFromMain = false;
			}, 100);
		}
	}

	private async syncFromMain() {
		await this.loadCards();
		this.renderIndex();
		this.refreshActiveView();
	}

	// ─────────────────────────────────────────────────────────────
	// Card Operations
	// ─────────────────────────────────────────────────────────────

	selectCard(index: number, requestFocus = false) {
		if (index < 0 || index >= this.cards.length) return;

		// 1. Update visual selection without full re-render if possible
		if (this.indexContainer) {
			const prevActive = this.indexContainer.querySelector(
				`.arete-yaml-index-item[data-index="${this.currentCardIndex}"]`,
			);
			if (prevActive) prevActive.removeClass('is-active');

			const newActive = this.indexContainer.querySelector(
				`.arete-yaml-index-item[data-index="${index}"]`,
			);
			if (newActive) {
				newActive.addClass('is-active');
				if (requestFocus) {
					// We need to focus the ITEM itself or the container?
					// The container has tabindex=0, but maybe we want to keep focus on container
					// and just visually select.
					// Actually, let's keep focus on the list container to capture arrow keys.
					const list = this.indexContainer.querySelector(
						'.arete-yaml-index-list',
					) as HTMLElement;
					if (list) list.focus();
					newActive.scrollIntoView({ block: 'nearest' });
				}
			} else {
				// If new active element not found (e.g. initial load), might need render
				// But usually selectCard comes after render.
			}
		}

		this.currentCardIndex = index;
		// Do NOT call renderIndex() here, it kills focus!

		this.refreshActiveView();

		// Sync with main editor highlight
		this.plugin.highlightCardLines(index);
	}

	// Called externally from main.ts when gutter is clicked
	focusCard(cardIndex: number) {
		if (cardIndex >= 0 && cardIndex < this.cards.length) {
			this.currentCardIndex = cardIndex;
			this.renderIndex();
			this.refreshActiveView();
		}
	}

	async addCard() {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (!frontmatter.cards) frontmatter.cards = [];
			frontmatter.cards.push({ front: '', back: '' });
		});

		// Select the new card
		await this.loadCards();
		this.currentCardIndex = this.cards.length - 1;
		this.renderIndex();
		this.refreshActiveView();
	}

	async deleteCard(index: number) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (frontmatter.cards) {
				frontmatter.cards.splice(index, 1);
			}
		});

		await this.loadCards();
		if (this.currentCardIndex >= this.cards.length) {
			this.currentCardIndex = Math.max(0, this.cards.length - 1);
		}
		this.renderIndex();
		this.refreshActiveView();
	}

	async reorderCards(fromIndex: number, toIndex: number) {
		const activeFile = this.app.workspace.getActiveFile();
		if (!activeFile) return;

		await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
			if (frontmatter.cards) {
				const [removed] = frontmatter.cards.splice(fromIndex, 1);
				frontmatter.cards.splice(toIndex, 0, removed);
			}
		});

		// Update current index if affected
		if (this.currentCardIndex === fromIndex) {
			this.currentCardIndex = toIndex;
		} else if (fromIndex < this.currentCardIndex && toIndex >= this.currentCardIndex) {
			this.currentCardIndex--;
		} else if (fromIndex > this.currentCardIndex && toIndex <= this.currentCardIndex) {
			this.currentCardIndex++;
		}

		await this.loadCards();
		this.renderIndex();
		this.refreshActiveView();
	}
}
