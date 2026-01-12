import { ItemView, WorkspaceLeaf, TFile, Notice, setIcon, App, MarkdownView, Menu, MarkdownRenderer, Component } from 'obsidian';

export const CARD_VIEW_TYPE = 'arete-card-view';

interface CardData {
    [key: string]: any;
}

export class CardView extends ItemView {
    previewMode: boolean = false;
    
    constructor(leaf: WorkspaceLeaf) {
        super(leaf);
    }

    getViewType() {
        return CARD_VIEW_TYPE;
    }

    getDisplayText() {
        return 'Card Viewer';
    }

    getIcon() {
        return 'sheets-in-box';
    }

    async onOpen() {
        const container = this.containerEl.children[1];
        container.empty();
        container.createEl('h4', { text: 'Card Viewer' });
        
        this.render();

        // Register event to update view when active file changes
        this.registerEvent(this.app.workspace.on('active-leaf-change', this.onActiveLeafChange.bind(this)));
        // Register event for file modification (to refresh if edited elsewhere)
        this.registerEvent(this.app.vault.on('modify', this.onFileModify.bind(this)));
    }

    async onClose() {
        // Cleanup if needed
    }

    onActiveLeafChange() {
        this.render();
    }

    onFileModify(file: TFile) {
        const activeFile = this.app.workspace.getActiveFile();
        if (activeFile && activeFile.path === file.path) {
            this.render();
        }
    }

    async render() {
        const container = this.containerEl.children[1];
        container.empty();

        const activeFile = this.app.workspace.getActiveFile();
        if (!activeFile) {
            container.createEl('p', { text: 'No active file.' });
            return;
        }

        const cache = this.app.metadataCache.getFileCache(activeFile);
        if (!cache || !cache.frontmatter || !cache.frontmatter.cards) {
            container.createEl('p', { text: 'No cards found in frontmatter.' });
            const btn = container.createEl('button', { text: 'Initialize Cards' });
            btn.onclick = async () => {
                 await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
                    if (!frontmatter.cards) frontmatter.cards = [];
                 });
                 this.render();
            };
            return;
        }

        const cards: CardData[] = cache.frontmatter.cards;
        
        // Header with title and toggle button
        const headerContainer = container.createDiv({ cls: 'arete-header-container' });
        headerContainer.style.display = 'flex';
        headerContainer.style.justifyContent = 'space-between';
        headerContainer.style.alignItems = 'center';
        headerContainer.style.marginBottom = '10px';
        
        headerContainer.createEl('h3', { text: `${activeFile.basename} (${cards.length} cards)` });
        
        const toggleBtn = headerContainer.createEl('button', { 
            text: this.previewMode ? '✏️ Edit' : '👁️ Preview' 
        });
        toggleBtn.onclick = () => {
            this.previewMode = !this.previewMode;
            this.render();
        };

        const listContainer = container.createDiv({ cls: 'arete-card-list' });

        cards.forEach((card, index) => {
            const cardEl = listContainer.createDiv({ cls: 'arete-card-item' });
            cardEl.style.border = '1px solid var(--background-modifier-border)';
            cardEl.style.padding = '10px';
            cardEl.style.marginBottom = '10px';
            cardEl.style.borderRadius = '5px';

            // Fields - only show user-editable fields, not internal IDs
            // User requested ID to be visible. Hid only nid/cid/internal stuff.
            const HIDDEN_FIELDS = ['nid', 'cid', 'model', 'deck', 'tags']; 
            const allKeys = Object.keys(card);
            
            // Filter out internal fields
            let keys = allKeys.filter(k => !HIDDEN_FIELDS.includes(k.toLowerCase()));
            
            // If no front/back found, add them as empty defaults
            const hasContent = keys.some(k => k.toLowerCase() === 'front' || k.toLowerCase() === 'back');
            if (!hasContent) {
                if (!keys.some(k => k.toLowerCase() === 'front')) keys.push('front');
                if (!keys.some(k => k.toLowerCase() === 'back')) keys.push('back');
            }
            
            // Remove duplicates (case-insensitive)
            const seenLower = new Set<string>();
            const uniqueKeys = keys.filter(k => {
                const lower = k.toLowerCase();
                if (seenLower.has(lower)) return false;
                seenLower.add(lower);
                return true;
            });

            // Card Header (Title + Actions)
            // Use details/summary for accordion effect
            const details = cardEl.createEl('details');
            details.open = false; // Default closed
            
            const summary = details.createEl('summary');
            summary.style.display = 'flex';
            summary.style.justifyContent = 'space-between';
            summary.style.alignItems = 'center';
            summary.style.cursor = 'pointer';
            summary.style.padding = '5px 0';
            summary.style.outline = 'none';

            const summaryTitle = summary.createSpan();
            const frontText = card['front'] || card['Front'] || 'New Card';
            const previewText = frontText.length > 50 ? frontText.substring(0, 50) + '...' : frontText;
            summaryTitle.setText(`Card ${index + 1}: ${previewText}`);
            summaryTitle.style.fontWeight = 'bold';
            
            const deleteBtn = summary.createEl('button', { text: '🗑️' });
            deleteBtn.onclick = async (e) => {
                e.preventDefault();
                e.stopPropagation(); 
                await this.deleteCard(index);
            };

            const contentDiv = details.createDiv({ cls: 'arete-card-content' });
            contentDiv.style.marginTop = '10px';
            contentDiv.style.paddingLeft = '10px';
            contentDiv.style.borderLeft = '2px solid var(--background-modifier-border)';

            const actionsContainer = contentDiv.createDiv({ cls: 'arete-card-actions' });
            actionsContainer.style.display = 'flex';
            actionsContainer.style.gap = '10px';
            actionsContainer.style.marginBottom = '10px';

            const gotoBtn = actionsContainer.createEl('button', { text: '📍 Go to YAML' });
            gotoBtn.style.fontSize = '0.8em';
            gotoBtn.onclick = () => {
                this.scrollToCard(index);
            };

            if (card['nid']) {
                const ankiBtn = actionsContainer.createEl('button', { text: `🔗 Anki: ${card['nid']}` });
                ankiBtn.style.fontSize = '0.8em';
                ankiBtn.title = 'Open in Anki Browser';
                ankiBtn.onclick = async () => {
                    await this.openInAnki(card['nid']);
                };
            }

            uniqueKeys.forEach(key => {
                const fieldContainer = contentDiv.createDiv({ cls: 'arete-card-field' });
                fieldContainer.style.marginBottom = '5px';
                
                const label = fieldContainer.createEl('label', { text: key });
                label.style.display = 'block';
                label.style.fontSize = '0.8em';
                label.style.color = 'var(--text-muted)';
                
                if (this.previewMode) {
                    const previewContainer = fieldContainer.createDiv({ cls: 'arete-preview' });
                    previewContainer.style.padding = '5px';
                    previewContainer.style.minHeight = '30px';
                    previewContainer.style.backgroundColor = 'var(--background-secondary)';
                    previewContainer.style.borderRadius = '4px';
                    
                    const content = card[key] || '*empty*';
                    MarkdownRenderer.render(
                        this.app,
                        content,
                        previewContainer,
                        activeFile.path,
                        this
                    );
                } else {
                    const input = fieldContainer.createEl('textarea');
                    input.value = card[key] || '';
                    input.style.width = '100%';
                    input.rows = 3;
                    
                    input.onblur = async () => {
                         await this.updateCard(index, key, input.value);
                    };
                }
            });
        });

        const addBtn = container.createEl('button', { text: '➕ Add New Card' });
        addBtn.style.width = '100%';
        addBtn.onclick = async () => {
            await this.addCard();
        };
    }

    async updateCard(index: number, key: string, value: string) {
        const activeFile = this.app.workspace.getActiveFile();
        if(!activeFile) return;

        await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
            if (frontmatter.cards && frontmatter.cards[index]) {
                frontmatter.cards[index][key] = value;
            }
        });
    }

    async addCard() {
        const activeFile = this.app.workspace.getActiveFile();
        if(!activeFile) return;

        await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
           if (!frontmatter.cards) frontmatter.cards = [];
           frontmatter.cards.push({ front: '', back: '' });
        });
    }

    async deleteCard(index: number) {
        const activeFile = this.app.workspace.getActiveFile();
        if(!activeFile) return;

        await this.app.fileManager.processFrontMatter(activeFile, (frontmatter) => {
             if (frontmatter.cards) {
                 frontmatter.cards.splice(index, 1);
             }
        });
    }

    async openInAnki(nid: number | string) {
        try {
            const response = await fetch('http://127.0.0.1:8765', {
                method: 'POST',
                body: JSON.stringify({
                    action: 'guiBrowse',
                    version: 6,
                    params: {
                        query: `nid:${nid}`
                    }
                })
            });
            const result = await response.json();
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
        if(!activeFile) return;

        const leaf = this.app.workspace.getMostRecentLeaf();
        if (leaf && leaf.view instanceof MarkdownView) {
            const editor = leaf.view.editor;
            const fileContent = editor.getValue();
            
            const lines = fileContent.split('\n');
            let cardsStartLine = -1;
            
            for(let i=0; i<lines.length; i++) {
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
            
            for(let i=cardsStartLine + 1; i<lines.length; i++) {
                const line = lines[i];
                if (line.trim().startsWith('-')) {
                    cardCount++;
                    if (cardCount === index) {
                        targetLine = i;
                        break;
                    }
                }
                if (line.trim() === '---' || (line.trim().length > 0 && !line.startsWith(' ') && !line.startsWith('-'))) {
                     break;
                }
            }

            editor.setCursor({ line: targetLine, ch: 0 });
            editor.scrollIntoView({ from: { line: targetLine, ch: 0}, to: { line: targetLine, ch: 0 } }, true);
        }
    }
}
