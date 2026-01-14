import { ItemView, WorkspaceLeaf, setIcon, Notice, MarkdownView, TFile, Menu } from 'obsidian';
import AretePlugin from '@/main';
import { ConceptStats, ProblematicCard } from '@application/services/StatsService';
import { BrokenReference } from '@application/services/LinkCheckerService';
import { LeechCard } from '@application/services/LeechService';

export const DASHBOARD_VIEW_TYPE = 'arete-stats-view'; // Keep ID for compatibility

interface DeckTreeNode {
	name: string;
	fullName: string;
	concepts: ConceptStats[];
	children: Record<string, DeckTreeNode>;
	totalProblematic: number;
	totalCards: number;
	totalLapses: number;
	sumDifficulty: number;
	countDifficulty: number;
}

type DashboardTab = 'overview' | 'leeches' | 'integrity';

export class DashboardView extends ItemView {
	plugin: AretePlugin;
	activeTab: DashboardTab = 'overview';
	
	// Overview State
	expandedConcepts: Set<string>;
	expandedDecks: Set<string>;
	overviewMode: 'hierarchy' | 'leaderboard' = 'hierarchy';

	// Integrity State
	brokenRefs: BrokenReference[] | null = null;
	isScanning = false;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
		this.expandedDecks = new Set(this.plugin.settings.ui_expanded_decks || []);
		this.expandedConcepts = new Set(this.plugin.settings.ui_expanded_concepts || []);
	}

	getViewType() {
		return DASHBOARD_VIEW_TYPE;
	}

	getDisplayText() {
		return 'Arete Dashboard';
	}

	getIcon() {
		return 'layout-dashboard';
	}

	async onOpen() {
		this.render();
	}

	async render() {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-dashboard-container');
		
		// Use flex column for full height
		container.style.display = 'flex';
		container.style.flexDirection = 'column';
		container.style.height = '100%';
		container.style.overflow = 'hidden';

		this.renderHeader(container as HTMLElement);
		this.renderTabs(container as HTMLElement);
		
		const contentEl = container.createDiv({ cls: 'arete-dashboard-content' });
		contentEl.style.flex = '1';
		contentEl.style.overflowY = 'auto';
		contentEl.style.padding = '1rem';

		switch (this.activeTab) {
			case 'overview':
				this.renderOverview(contentEl);
				break;
			case 'leeches':
				await this.renderLeeches(contentEl);
				break;
			case 'integrity':
				this.renderIntegrity(contentEl);
				break;
		}
	}

	renderHeader(container: HTMLElement) {
		const header = container.createDiv({ cls: 'arete-dashboard-header' });
		header.style.padding = '1rem';
		header.style.borderBottom = '1px solid var(--background-modifier-border)';
		header.style.display = 'flex';
		header.style.justifyContent = 'space-between';
		header.style.alignItems = 'center';
		header.style.background = 'var(--background-secondary)';

		const titleMsg = header.createEl('h3', { text: 'Arete Dashboard' });
		titleMsg.style.margin = '0 auto 0 0'; // Left align

		// Global Stats (Quick Summary)
		const stats = this.plugin.statsService.getCache();
		// naive global aggregation
		let totalCards = 0;
		let totalLeeches = 0;
		Object.values(stats.concepts).forEach(c => {
			totalCards += c.totalCards;
			// For now, let's say leeches are cards with > 8 lapses OR manually tagged
			// Actually we can count problematic cards from cache
			totalLeeches += c.problematicCardsCount; 
		});

		const statsGroup = header.createDiv({ cls: 'arete-header-stats' });
		statsGroup.style.display = 'flex';
		statsGroup.style.gap = '1rem';
		statsGroup.style.fontSize = '0.9em';
		statsGroup.style.color = 'var(--text-muted)';

		statsGroup.createSpan({ text: `${totalCards} Cards` });
		
		const leechSpan = statsGroup.createSpan({ text: `${totalLeeches} Issues` });
		if (totalLeeches > 0) leechSpan.style.color = 'var(--color-red)';

		// Refresh Button
		const refreshBtn = header.createEl('button', { cls: 'arete-icon-btn' });
		setIcon(refreshBtn, 'refresh-cw');
		refreshBtn.title = 'Sync & Refresh Stats';
		refreshBtn.onclick = async () => {
			refreshBtn.addClass('arete-spin');
			await this.plugin.statsService.refreshStats();
			await this.plugin.saveStats();
			this.render();
			refreshBtn.removeClass('arete-spin');
		};
	}

	renderTabs(container: HTMLElement) {
		const tabBar = container.createDiv({ cls: 'arete-tab-bar' });
		tabBar.style.display = 'flex';
		tabBar.style.gap = '2px';
		tabBar.style.padding = '0 1rem';
		tabBar.style.background = 'var(--background-secondary)';
		tabBar.style.borderBottom = '1px solid var(--background-modifier-border)';

		const tabs: {id: DashboardTab, label: string, icon: string}[] = [
			{ id: 'overview', label: 'Overview', icon: 'bar-chart-2' },
			{ id: 'leeches', label: 'Leeches', icon: 'flame' },
			{ id: 'integrity', label: 'Integrity', icon: 'link' },
		];

		tabs.forEach(tab => {
			const btn = tabBar.createDiv({ cls: 'arete-tab-btn' });
			btn.style.padding = '8px 16px';
			btn.style.cursor = 'pointer';
			btn.style.borderBottom = '2px solid transparent';
			btn.style.display = 'flex';
			btn.style.gap = '6px';
			btn.style.alignItems = 'center';
			btn.style.fontSize = '0.9em';
			btn.style.fontWeight = '500';
			btn.style.color = 'var(--text-muted)';

			if (this.activeTab === tab.id) {
				btn.style.borderBottomColor = 'var(--interactive-accent)';
				btn.style.color = 'var(--text-normal)';
				btn.addClass('is-active');
			}

			const iconSpan = btn.createSpan();
			setIcon(iconSpan, tab.icon);
			btn.createSpan({ text: tab.label });

			btn.onclick = () => {
				this.activeTab = tab.id;
				this.render();
			};
		});
	}

	// --- 1. OVERVIEW TAB (Logic adapted from StatisticsView) ---
	renderOverview(container: HTMLElement) {
		// View Switcher (Hierarchy vs Leaderboard)
		const controls = container.createDiv({ cls: 'arete-overview-controls' });
		controls.style.display = 'flex';
		controls.style.justifyContent = 'flex-end';
		controls.style.marginBottom = '1rem';
		controls.style.gap = '0.5rem';

		const viewSelect = controls.createEl('select');
		const optHierarchy = viewSelect.createEl('option', { text: 'Folder View', value: 'hierarchy' });
		const optLeaderboard = viewSelect.createEl('option', { text: 'Worst Concepts', value: 'leaderboard' });
		if (this.overviewMode === 'hierarchy') optHierarchy.selected = true;
		else optLeaderboard.selected = true;
		
		viewSelect.onchange = () => {
			this.overviewMode = viewSelect.value as any;
			this.render();
		};

		const concepts = Object.values(this.plugin.statsService.getCache().concepts);
		if (concepts.length === 0) {
			this.renderEmptyState(container, 'No statistics available. Please sync.');
			return;
		}

		if (this.overviewMode === 'hierarchy') {
			const rootNode = this.buildDeckTree(concepts);
			const sortedDeckKeys = Object.keys(rootNode.children).sort();
			sortedDeckKeys.forEach((key) => {
				this.renderDeckNode(container, rootNode.children[key], 0);
			});
			if (rootNode.concepts.length > 0) {
				rootNode.concepts.sort((a, b) => b.score - a.score);
				rootNode.concepts.forEach((c) => this.renderConceptRow(container, c));
			}
		} else {
			// Leaderboard
			const sorted = [...concepts].sort((a, b) => b.score - a.score);
			sorted.forEach(c => this.renderConceptRow(container, c));
		}
	}

	// --- 2. LEECHES TAB ---
	async renderLeeches(container: HTMLElement) {
		const leeches = this.plugin.leechService.getLeeches(this.plugin.statsService.getCache());
		
		if (leeches.length === 0) {
			this.renderEmptyState(container, 'No leeches found! Your deck is healthy.');
			return;
		}

		const table = container.createEl('table', { cls: 'arete-leech-table' });
		table.style.width = '100%';
		table.style.borderCollapse = 'collapse';
		
		const thead = table.createEl('thead');
		const headerRow = thead.createEl('tr');
		['Card (Front)', 'Difficulty', 'Lapses', 'Actions'].forEach(text => {
			headerRow.createEl('th', { text }).style.textAlign = 'left';
		});

		const tbody = table.createEl('tbody');
		leeches.forEach(leech => {
			const row = tbody.createEl('tr');
			row.style.borderBottom = '1px solid var(--background-modifier-border)';
			
			// Front
			const cellFront = row.createEl('td');
			cellFront.style.padding = '8px';
			// Truncate
			const frontDiv = cellFront.createDiv();
			frontDiv.style.maxWidth = '300px';
			frontDiv.style.overflow = 'hidden';
			frontDiv.style.textOverflow = 'ellipsis';
			frontDiv.style.whiteSpace = 'nowrap';
			frontDiv.style.cursor = 'pointer';
			frontDiv.style.fontWeight = '500';
			frontDiv.textContent = leech.front.replace(/<[^>]*>?/gm, '');
			frontDiv.title = leech.front;
			frontDiv.onclick = () => this.goToCard(leech.filePath, leech.front);

			// Diff/Ease (use 'issue' precalc or raw)
			const cellDiff = row.createEl('td');
			cellDiff.textContent = leech.ease ? `${(leech.ease/10).toFixed(0)}% Ease` : (leech.difficulty != null ? `${(leech.difficulty*100).toFixed(0)}% Diff` : '-');
			
			// Lapses
			const cellLapses = row.createEl('td');
			cellLapses.textContent = leech.lapses.toString();
			if (leech.lapses > 10) cellLapses.style.color = 'var(--color-red)';

			// Actions
			const cellActions = row.createEl('td');
			cellActions.style.display = 'flex';
			cellActions.style.gap = '0.5rem';

			const btnSuspend = cellActions.createEl('button', { text: 'Suspend' });
			btnSuspend.style.fontSize = '0.8em';
			btnSuspend.onclick = async () => {
				btnSuspend.textContent = '...';
				const success = await this.plugin.leechService.suspendCard(leech.cardId);
				if (success) {
					new Notice('Card suspended.');
					row.style.opacity = '0.5';
					btnSuspend.textContent = 'Suspended';
					btnSuspend.disabled = true;
				} else {
					new Notice('Failed to suspend card.');
					btnSuspend.textContent = 'Suspend';
				}
			};
		});
	}

	// --- 3. INTEGRITY TAB ---
	renderIntegrity(container: HTMLElement) {
		const actionArea = container.createDiv();
		actionArea.style.padding = '1rem';
		actionArea.style.background = 'var(--background-secondary-alt)';
		actionArea.style.marginBottom = '1rem';
		actionArea.style.borderRadius = '8px';
		actionArea.style.textAlign = 'center';


		const desc = actionArea.createDiv();
		desc.style.marginBottom = '1rem';
		desc.style.color = 'var(--text-muted)';
		desc.style.fontSize = '0.9em';
		desc.innerHTML = `
			<p style="margin-bottom: 0.5rem;">Scans your synced files to find <b>broken wikilinks</b> and <b>missing images</b>.</p>
			<p style="margin: 0;">Use this to ensure your Anki cards don't show broken media or dead links.</p>
		`;

		const checkBtn = actionArea.createEl('button', { cls: 'mod-cta', text: 'Run Integrity Check' });
		if (this.isScanning) {
			checkBtn.disabled = true;
			checkBtn.textContent = 'Scanning Vault...';
		}

		checkBtn.onclick = async () => {
			this.isScanning = true;
			this.render(); // Update button state
			try {
				// Only scan synced files? No, scan all for simplicity as per plan
				// Actually user requested "Scan Anki cards".
				// We can filter by concept paths from stats service to be safe
				const relevantPaths = Object.keys(this.plugin.statsService.getCache().concepts);
				let targetFiles: TFile[] = [];
				if (relevantPaths.length > 0) {
					targetFiles = relevantPaths
						.map(p => this.app.vault.getAbstractFileByPath(p))
						.filter(f => f instanceof TFile) as TFile[];
				} else {
					// Fallback if no stats
					targetFiles = this.app.vault.getMarkdownFiles();
				}

				this.brokenRefs = await this.plugin.linkCheckerService.checkIntegrity(targetFiles);
				new Notice(`Integrity check complete. Found ${this.brokenRefs.length} issues.`);
			} catch (e) {
				console.error(e);
				new Notice('Integrity check failed.');
			} finally {
				this.isScanning = false;
				this.render();
			}
		};

		if (this.brokenRefs) {
			if (this.brokenRefs.length === 0) {
				this.renderSuccess(container, 'No broken links or missing images found!');
			} else {
				const list = container.createDiv();
				
				this.brokenRefs.forEach(ref => {
					const item = list.createDiv();
					item.style.padding = '0.5rem';
					item.style.borderBottom = '1px solid var(--background-modifier-border)';
					item.style.display = 'flex';
					item.style.justifyContent = 'space-between';
					item.style.alignItems = 'center';

					const left = item.createDiv();
					const fileLink = left.createSpan({ text: ref.sourceFile.basename, cls: 'arete-clickable' });
					fileLink.style.fontWeight = 'bold';
					fileLink.onclick = () => this.app.workspace.getLeaf().openFile(ref.sourceFile);

					left.createSpan({ text: ` → ` });
					const targetSpan = left.createSpan({ text: ref.linkPath });
					targetSpan.style.color = 'var(--color-red)';
					// Tooltip for original text (debug aid)
					targetSpan.title = `Original text: "${ref.linkText}"`;

					const right = item.createDiv();
					right.style.display = 'flex';
					right.style.alignItems = 'center';
					right.style.gap = '8px';

					// Show original text if it differs significantly from linkPath
					if (ref.type !== 'invalid-yaml' && ref.linkText !== `[[${ref.linkPath}]]` && ref.linkText !== ref.linkPath) {
						const span = right.createSpan({ text: `"${ref.linkText}"`});
						span.style.fontSize = '0.8em';
						span.style.color = 'var(--text-muted)';
					}

					const typeBadge = right.createSpan({ text: ref.type.toUpperCase() });
					typeBadge.style.fontSize = '0.7em';
					typeBadge.style.padding = '2px 4px';
					typeBadge.style.borderRadius = '4px';
					
					if (ref.type === 'invalid-yaml') {
						typeBadge.style.background = 'var(--color-red)';
						typeBadge.style.color = 'var(--text-on-accent)';
						typeBadge.title = 'Obsidian failed to parse frontmatter. Check for syntax errors.';
					} else {
						typeBadge.style.background = 'var(--background-modifier-border)';
					}

					// Navigation Badge/Button
					const gotoBtn = right.createSpan({ cls: 'arete-icon-btn' });
					setIcon(gotoBtn, 'external-link');
					gotoBtn.title = 'Go to location';
					gotoBtn.style.cursor = 'pointer';
					gotoBtn.style.marginLeft = '8px';
					gotoBtn.onclick = (e) => {
						e.stopPropagation();
						this.goToIssue(ref.sourceFile, ref.linkText);
					};
				});
			}
		}
	}

	// --- Helpers ---
	renderEmptyState(container: HTMLElement, message: string) {
		const empty = container.createDiv({ cls: 'arete-empty-state' });
		empty.style.textAlign = 'center';
		empty.style.padding = '3rem';
		empty.style.color = 'var(--text-muted)';
		setIcon(empty.createDiv(), 'search');
		empty.createDiv({ text: message }).style.marginTop = '1rem';
	}

	renderSuccess(container: HTMLElement, message: string) {
		const box = container.createDiv();
		box.style.padding = '2rem';
		box.style.textAlign = 'center';
		box.style.color = 'var(--color-green)';
		setIcon(box.createDiv(), 'check-circle');
		box.createDiv({ text: message }).style.marginTop = '1rem';
	}

	// ... [Re-use buildDeckTree, renderDeckNode, renderConceptRow from StatisticsView]
	// To save space in this response, I'm assuming those methods are copied or refactored.
	// For this task, I will include abbreviated versions or copy them fully.
	// Since I cannot "inherit" them easily without mixins, I will copy them for now.
	
	buildDeckTree(concepts: ConceptStats[]): DeckTreeNode {
		/* ... Same as StatisticsView ... */
		const root: DeckTreeNode = { name: 'Root', fullName: '', concepts: [], children: {}, totalProblematic: 0, totalCards: 0, totalLapses: 0, sumDifficulty: 0, countDifficulty: 0 };
		concepts.forEach((c) => {
			const deckName = c.primaryDeck || 'Default';
			const parts = deckName.split('::');
			let currentNode = root;
			let currentPath = '';
			parts.forEach((part) => {
				currentPath = currentPath ? `${currentPath}::${part}` : part;
				if (!currentNode.children[part]) {
					currentNode.children[part] = { name: part, fullName: currentPath, concepts: [], children: {}, totalProblematic: 0, totalCards: 0, totalLapses: 0, sumDifficulty: 0, countDifficulty: 0 };
				}
				currentNode = currentNode.children[part];
			});
			currentNode.concepts.push(c);
		});
		this.aggregateTree(root);
		return root;
	}

	aggregateTree(node: DeckTreeNode) {
		node.concepts.forEach((c) => {
			node.totalProblematic += c.problematicCardsCount;
			node.totalCards += c.totalCards;
			node.totalLapses += c.totalLapses;
			if (this.plugin.settings.stats_algorithm === 'fsrs' && c.averageDifficulty) {
				if (c.difficultyCount) { node.sumDifficulty += c.averageDifficulty * c.difficultyCount; node.countDifficulty += c.difficultyCount; }
			}
		});
		Object.values(node.children).forEach((child) => {
			this.aggregateTree(child);
			node.totalProblematic += child.totalProblematic;
			node.totalCards += child.totalCards;
			node.totalLapses += child.totalLapses;
			node.sumDifficulty += child.sumDifficulty;
			node.countDifficulty += child.countDifficulty;
		});
	}

	renderDeckNode(container: HTMLElement, node: DeckTreeNode, depth: number) {
		const deckContainer = container.createDiv();
		const header = deckContainer.createDiv();
		header.style.padding = `8px 16px 8px ${8 + depth * 16}px`;
		header.style.cursor = 'pointer';
		header.style.display = 'flex';
		header.style.alignItems = 'center';
		header.style.borderBottom = '1px solid var(--background-modifier-border)';
		// Highlight if issues
		if(node.totalProblematic > 0) header.style.background = 'rgba(var(--color-red-rgb), 0.05)';

		const icon = header.createSpan();
		icon.style.marginRight = '8px';
		const isExpanded = this.expandedDecks.has(node.fullName);
		setIcon(icon, isExpanded ? 'chevron-down' : 'chevron-right');

		const title = header.createSpan({ text: node.name });
		title.style.fontWeight = '600';
		
		const statsContainer = header.createDiv({ cls: 'arete-deck-stats' });
		statsContainer.style.marginLeft = 'auto';
		statsContainer.style.display = 'flex';
		statsContainer.style.gap = '16px';
		statsContainer.style.fontSize = '0.9em';
		statsContainer.style.color = 'var(--text-muted)';
		
		// 1. Difficulty (Avg)
		const avgDiff = node.countDifficulty ? (node.sumDifficulty / node.countDifficulty) : 0;
		if (avgDiff > 0) {
			const diffSpan = statsContainer.createSpan({ text: `${(avgDiff * 100).toFixed(0)}% Diff` });
			if (avgDiff > 0.6) diffSpan.style.color = 'var(--color-orange)';
		}
		
		// 2. Lapses (Avg) - User Requested
		const avgLapse = node.totalCards > 0 ? (node.totalLapses / node.totalCards) : 0;
		const lapseSpan = statsContainer.createSpan({ text: `${avgLapse.toFixed(1)} Lap. Avg` });
		if (avgLapse > 2) lapseSpan.style.color = 'var(--color-red)';

		// 3. Issues (Total)
		const badge = statsContainer.createSpan({ text: `${node.totalProblematic} Issues`, cls: 'arete-badge' });
		if (node.totalProblematic > 0) badge.style.color = 'var(--color-red)';

		const content = deckContainer.createDiv();
		if(!isExpanded) content.style.display = 'none';

		header.onclick = async () => {
			if(this.expandedDecks.has(node.fullName)) this.expandedDecks.delete(node.fullName);
			else this.expandedDecks.add(node.fullName);
			await this.plugin.saveSettings();
			this.render(); // Crude re-render
		};

		if(isExpanded) {
			// Concepts
			node.concepts.forEach(c => {
				const rowWrapper = content.createDiv();
				rowWrapper.style.paddingLeft = `${24 + depth * 16}px`;
				this.renderConceptRow(rowWrapper, c);
			});
			// Children
			Object.values(node.children).forEach(child => this.renderDeckNode(content, child, depth + 1));
		}
	}

	renderConceptRow(container: HTMLElement, concept: ConceptStats) {
		const row = container.createDiv();
		row.style.display = 'flex';
		row.style.justifyContent = 'space-between';
		row.style.alignItems = 'center';
		row.style.padding = '6px 8px';
		row.style.borderBottom = '1px solid var(--background-modifier-border)';
		
		const leftGroup = row.createDiv();
		leftGroup.style.display = 'flex';
		leftGroup.style.alignItems = 'center';
		leftGroup.style.gap = '8px';
		leftGroup.style.flex = '1';

		// Expand Toggle for Card Stats
		const expandBtn = leftGroup.createSpan({ cls: 'arete-icon-btn' });
		expandBtn.style.cursor = 'pointer';
		expandBtn.title = 'Show individual cards';
		const isExpanded = this.expandedConcepts.has(concept.filePath);
		setIcon(expandBtn, isExpanded ? 'chevron-down' : 'chevron-right');
		
		expandBtn.onclick = async (e) => {
			e.stopPropagation();
			if (isExpanded) this.expandedConcepts.delete(concept.filePath);
			else this.expandedConcepts.add(concept.filePath);
			await this.plugin.saveSettings();
			this.render();
		};

		const name = leftGroup.createSpan({ text: concept.fileName, cls: 'arete-clickable' });
		name.style.fontWeight = '500';
		name.onclick = () => this.openFile(concept.filePath);

		const statsContainer = row.createDiv();
		statsContainer.style.display = 'flex';
		statsContainer.style.gap = '16px';
		statsContainer.style.fontSize = '0.85em';
		statsContainer.style.color = 'var(--text-muted)';
		statsContainer.style.marginRight = '8px';

		// 1. Card Count
		statsContainer.createSpan({ text: `${concept.totalCards} cards` });

		// 2. FSRS Difficulty
		if (this.plugin.settings.stats_algorithm === 'fsrs' && concept.averageDifficulty) {
			const dVal = concept.averageDifficulty;
			const dSpan = statsContainer.createSpan({ text: `${(dVal * 100).toFixed(0)}% Diff` });
			if (dVal > 0.6) dSpan.style.color = 'var(--color-orange)';
		}

		// 3. Lapses
		if (concept.totalLapses > 0) {
			const lSpan = statsContainer.createSpan({ text: `${concept.totalLapses} Lapses` });
			if (concept.totalLapses > 5) lSpan.style.color = 'var(--color-red)';
		}

		// 4. Issues
		if (concept.problematicCardsCount > 0) {
			const iSpan = statsContainer.createSpan({ text: `${concept.problematicCardsCount} Issues` });
			iSpan.style.color = 'var(--color-red)';
			iSpan.style.fontWeight = 'bold';
		}

		// --- Render Card Details if Expanded ---
		if (isExpanded) {
			const cardList = container.createDiv();
			cardList.style.background = 'var(--background-primary-alt)';
			cardList.style.borderBottom = '1px solid var(--background-modifier-border)';
			
			// Get all cards for this concept
			// cardStats is indexed by number (cardId), but confusingly generic typing might make keys strings
			const cards = Object.values(concept.cardStats); 
			
			if (cards.length === 0) {
				cardList.createDiv({ text: 'No card stats synced.' }).style.padding = '8px 32px';
			} else {
				// Header
				const header = cardList.createDiv();
				header.style.display = 'flex';
				header.style.padding = '4px 8px 4px 48px';
				header.style.fontSize = '0.75em';
				header.style.color = 'var(--text-muted)';
				header.style.borderBottom = '1px solid var(--background-modifier-border)';
				
				const h1 = header.createSpan({ text: 'Card Question' });
				h1.style.flex = '1';
				const h2 = header.createSpan({ text: 'Difficulty' });
				h2.style.width = '80px';
				const h3 = header.createSpan({ text: 'Lapses' });
				h3.style.width = '60px'; // Fixed width instead of flex

				cards.sort((a,b) => b.lapses - a.lapses).forEach(card => {
					const cRow = cardList.createDiv();
					cRow.style.display = 'flex';
					cRow.style.alignItems = 'center';
					cRow.style.padding = '4px 8px 4px 48px';
					cRow.style.fontSize = '0.8em';
					cRow.style.borderBottom = '1px solid var(--background-modifier-border)';
					cRow.style.cursor = 'pointer';

					// Hover effect
					cRow.addEventListener('mouseenter', () => cRow.style.backgroundColor = 'var(--background-modifier-hover)');
					cRow.addEventListener('mouseleave', () => cRow.style.backgroundColor = 'transparent');

					cRow.onclick = (e) => { 
						e.stopPropagation();
						if (card.front) this.goToCard(concept.filePath, card.front);
					};

					const frontText = card.front ? card.front.replace(/<[^>]*>?/gm, '') : `#${card.cardId}`;
					const qSpan = cRow.createSpan({ text: frontText });
					qSpan.title = frontText;
					qSpan.style.flex = '1';
					qSpan.style.whiteSpace = 'nowrap';
					qSpan.style.overflow = 'hidden';
					qSpan.style.textOverflow = 'ellipsis';
					qSpan.style.marginRight = '16px';
					qSpan.style.fontFamily = card.front ? 'var(--font-interface)' : 'monospace';
					
					const diff = card.difficulty !== undefined ? `${(card.difficulty*100).toFixed(0)}%` 
							   : (card.ease ? `${(card.ease/10).toFixed(0)}% Ease` : '-');
					const dSpan = cRow.createSpan({ text: diff });
					dSpan.style.width = '80px';
					dSpan.style.flexShrink = '0';
					if (card.difficulty && card.difficulty > 0.6) dSpan.style.color = 'var(--color-orange)';

					const laps = cRow.createSpan({ text: card.lapses.toString() });
					laps.style.width = '60px';
					laps.style.flexShrink = '0';
					if (card.lapses > 5) laps.style.color = 'var(--color-red)';
				});
			}
		}
	}

	async openFile(filePath: string) {
		const file = this.app.vault.getAbstractFileByPath(filePath);
		if (file instanceof TFile) await this.app.workspace.getLeaf().openFile(file);
	}

	async goToCard(filePath: string, frontText: string) {
		await this.openFile(filePath);
		const view = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (view) {
			const editor = view.editor;
			const content = editor.getValue();
			// Improved robust finding: normalize newlines and spaces
			const cleanFront = frontText.trim().replace(/\s+/g, ' '); 
			// This is still hard because Markdown vs HTML in Anki. 
			// Naive search for now.
			const index = content.indexOf(frontText.split('\n')[0]); // Try finding first line
			if (index >= 0) {
				const pos = editor.offsetToPos(index);
				editor.setCursor(pos);
				editor.scrollIntoView({ from: pos, to: pos }, true);
			}
		}
	}

	async goToIssue(file: TFile, searchText: string) {
		await this.app.workspace.getLeaf().openFile(file);
		const view = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (view) {
			const editor = view.editor;
			const content = editor.getValue();
			// Remove context prefix like "Card #1: " if present
			const cleanText = searchText.replace(/^Card #\d+: /, '');
			const index = content.indexOf(cleanText);
			if (index >= 0) {
				const pos = editor.offsetToPos(index);
				editor.setCursor(pos);
				editor.scrollIntoView({ from: pos, to: pos }, true);
				// Highlight selection
				editor.setSelection(pos, editor.offsetToPos(index + cleanText.length));
			} else {
				new Notice(`Could not automatically find text: "${cleanText.substring(0, 20)}..."`);
			}
		}
	}
}
