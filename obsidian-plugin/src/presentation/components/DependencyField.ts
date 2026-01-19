import { App, TFile, setIcon, Menu } from 'obsidian';

export interface Dependency {
    type: 'file' | 'card';
    value: string; // basename or card ID
    label?: string; // Display text
}

export class DependencyField {
    private container: HTMLElement;
    private app: App;
    private dependencies: Dependency[] = [];
    private onChange: (deps: string[]) => void;
    
    private inputEl: HTMLInputElement;
    private resultsEl: HTMLElement;
    private listEl: HTMLElement;

    private selectedIndex = 0;
    private currentMatches: TFile[] = [];

    constructor(
        container: HTMLElement, 
        app: App, 
        initialValues: string[], 
        onChange: (deps: string[]) => void
    ) {
        this.container = container;
        this.app = app;
        this.onChange = onChange;
        
        // Parse initial values
        this.dependencies = initialValues.map(val => ({
            type: val.startsWith('arete_') ? 'card' : 'file',
            value: val,
            label: val // We'll resolve labels later
        }));

        this.render();
    }

    private render() {
        this.container.addClass('arete-dependency-field');
        
        // Selected items list
        this.listEl = this.container.createDiv({ cls: 'arete-dep-list' });
        this.renderList();

        // Input wrapper
        const inputWrapper = this.container.createDiv({ cls: 'arete-dep-input-wrapper' });
        
        this.inputEl = inputWrapper.createEl('input', {
            type: 'text',
            cls: 'arete-dep-input',
            attr: { placeholder: 'Search concepts...' }
        });

        this.resultsEl = inputWrapper.createDiv({ cls: 'arete-dep-results suggestion-container' });
        this.resultsEl.hide();

        // Events
        this.inputEl.addEventListener('input', () => this.handleInput());
        this.inputEl.addEventListener('blur', () => {
             // Delay select to allow click
             setTimeout(() => this.resultsEl.hide(), 200);
        });
        this.inputEl.addEventListener('focus', () => this.handleInput());
        
        // Keyboard Nav
        this.inputEl.addEventListener('keydown', (e) => this.handleKeydown(e));
    }

    private handleKeydown(e: KeyboardEvent) {
        if (!this.resultsEl.isShown()) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex + 1) % this.currentMatches.length;
            this.renderResults();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex - 1 + this.currentMatches.length) % this.currentMatches.length;
            this.renderResults();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (this.currentMatches[this.selectedIndex]) {
                this.selectFile(this.currentMatches[this.selectedIndex]);
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            this.resultsEl.hide();
        }
    }

    private renderList() {
        this.listEl.empty();
        this.dependencies.forEach((dep, index) => {
            const chip = this.listEl.createDiv({ cls: 'arete-dep-chip' });
            if (dep.type === 'card') chip.addClass('is-card');
            
            // Icon
            const iconSpan = chip.createSpan({ cls: 'arete-dep-icon' });
            setIcon(iconSpan, dep.type === 'card' ? 'id-card' : 'file-text');

            // Text
            chip.createSpan({ text: dep.label || dep.value, cls: 'arete-dep-text' });

            // Actions for File type (Drill down)
            if (dep.type === 'file') {
                 const expandBtn = chip.createDiv({ cls: 'arete-dep-action' });
                 setIcon(expandBtn, 'chevron-down');
                 expandBtn.addEventListener('click', (e) => {
                     e.stopPropagation();
                     this.showDrillDownMenu(dep, index, e);
                 });
            }

            // Remove
            const removeBtn = chip.createDiv({ cls: 'arete-dep-remove' });
            setIcon(removeBtn, 'x');
            removeBtn.addEventListener('click', () => {
                this.dependencies.splice(index, 1);
                this.update();
            });
        });
    }

    private handleInput() {
        const query = this.inputEl.value.toLowerCase();
        
        if (!query) {
            this.resultsEl.hide();
            return;
        }

        const files = this.app.vault.getMarkdownFiles();
        // Fuzzyish search (simple substring for now, or startswith + includes)
        // Sort by length or startswith for relevance
        this.currentMatches = files.filter(f => f.basename.toLowerCase().includes(query))
            .sort((a, b) => {
                 const aStart = a.basename.toLowerCase().startsWith(query);
                 const bStart = b.basename.toLowerCase().startsWith(query);
                 if (aStart && !bStart) return -1;
                 if (!aStart && bStart) return 1;
                 return a.basename.length - b.basename.length;
            })
            .slice(0, 10);

        if (this.currentMatches.length > 0) {
            this.selectedIndex = 0;
            this.resultsEl.show();
            this.renderResults();
        } else {
            this.resultsEl.hide();
        }
    }

    private renderResults() {
        this.resultsEl.empty();
        this.currentMatches.forEach((file, index) => {
            const item = this.resultsEl.createDiv({ 
                cls: 'arete-dep-result-item suggestion-item' + (index === this.selectedIndex ? ' is-selected' : '') 
            });
            
            // Icon
            const icon = item.createSpan({ cls: 'suggestion-icon' });
            setIcon(icon, 'file-text');

            // Content
            item.createSpan({ text: file.basename, cls: 'suggestion-content' });
            
            if (index === this.selectedIndex) {
                // Ensure visible scroll (optional for now as list is short)
                item.scrollIntoView({ block: 'nearest' });
            }

            item.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                const allItems = this.resultsEl.querySelectorAll('.arete-dep-result-item');
                allItems.forEach(el => el.removeClass('is-selected'));
                item.addClass('is-selected');
            });

            item.addEventListener('click', () => {
                this.selectFile(file);
            });
        });
    }

    private selectFile(file: TFile) {
        this.addDependency('file', file.basename);
        this.inputEl.value = '';
        this.resultsEl.hide();
    }

    private addDependency(type: 'file' | 'card', value: string) {
        if (this.dependencies.find(d => d.value === value)) return;
        
        this.dependencies.push({ type, value, label: value });
        this.update();
    }

    private update() {
        this.renderList();
        this.onChange(this.dependencies.map(d => d.value));
    }

    private showDrillDownMenu(dep: Dependency, index: number, e: MouseEvent) {
        // Find file
        const file = this.app.vault.getAbstractFileByPath(`${dep.value}.md`) as TFile;
        // Or search by basename if path not exact
        const files = this.app.vault.getMarkdownFiles().filter(f => f.basename === dep.value);
        const targetFile = files[0];

        if (!targetFile) {
            new Menu().addItem(i => i.setTitle('File not found').setDisabled(true)).showAtMouseEvent(e);
            return;
        }

        const cache = this.app.metadataCache.getFileCache(targetFile);
        const cards = cache?.frontmatter?.cards || [];

        if (!Array.isArray(cards) || cards.length === 0) {
            new Menu().addItem(i => i.setTitle('No cards in file').setDisabled(true)).showAtMouseEvent(e);
            return;
        }

        const menu = new Menu();
        menu.addItem(i => i.setTitle(`Select cards from ${dep.value}`).setIsLabel(true));

        cards.forEach((card: any) => {
            if (!card.id) return;
            const title = card.id; // Or fields.Front
            
            menu.addItem(item => {
                item.setTitle(title)
                    .setIcon('id-card')
                    .onClick(() => {
                        this.addDependency('card', card.id);
                         // Remove file dependency on drill-down selection? 
                         // Optional, but might be cleaner. For now keep additive.
                    });
            });
        });

        menu.showAtMouseEvent(e);
    }
}
