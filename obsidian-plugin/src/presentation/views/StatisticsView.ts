import { ItemView, WorkspaceLeaf, setIcon, Notice, MarkdownView, TFile } from 'obsidian';
import AretePlugin from '@/main';
import { ConceptStats, ProblematicCard } from '@application/services/StatsService';

export const STATS_VIEW_TYPE = 'arete-stats-view';

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

export class StatisticsView extends ItemView {
	plugin: AretePlugin;
	expandedConcepts: Set<string>;
	expandedDecks: Set<string>;
	currentViewMode: 'hierarchy' | 'leaderboard' = 'hierarchy'; // Default to Hierarchy

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
		// Initialize from settings or empty
		this.expandedDecks = new Set(this.plugin.settings.ui_expanded_decks || []);
		this.expandedConcepts = new Set(this.plugin.settings.ui_expanded_concepts || []);
	}

	getViewType() {
		return STATS_VIEW_TYPE;
	}

	getDisplayText() {
		return 'Arete Statistics';
	}

	getIcon() {
		return 'bar-chart-2';
	}

	async onOpen() {
		this.render();
	}

	async render() {
		const container = this.containerEl.children[1];
		container.empty();

		// Title & Header
		const header = container.createDiv({ cls: 'arete-stats-header' });
		header.style.display = 'flex';
		header.style.justifyContent = 'space-between';
		header.style.alignItems = 'center';
		header.style.marginBottom = '1rem';
		header.style.padding = '0 1rem';
		header.style.flexWrap = 'wrap';
		header.style.gap = '10px';

		const leftGroup = header.createDiv({ cls: 'arete-header-left' });
		leftGroup.style.display = 'flex';
		leftGroup.style.alignItems = 'center';
		leftGroup.style.gap = '10px';

		const headerTitle = leftGroup.createEl('h4', { text: 'Problematic Concepts' });
		headerTitle.style.margin = '0';

		// View Switcher
		const viewSelect = leftGroup.createEl('select');
		viewSelect.style.padding = '4px';
		viewSelect.style.borderRadius = '4px';
		viewSelect.style.borderColor = 'var(--background-modifier-border)';
		
		const optHierarchy = viewSelect.createEl('option', { text: 'Hierarchy', value: 'hierarchy' });
		const optLeaderboard = viewSelect.createEl('option', { text: 'Leaderboard', value: 'leaderboard' });
		
		if (this.currentViewMode === 'hierarchy') optHierarchy.selected = true;
		else optLeaderboard.selected = true;

		viewSelect.onchange = () => {
			this.currentViewMode = viewSelect.value as 'hierarchy' | 'leaderboard';
			this.render();
		};

		// Controls Group (Right)
		const rightGroup = header.createDiv({ cls: 'arete-header-right' });


		// Collapse All Button
		const collapseBtn = rightGroup.createEl('button', { cls: 'arete-icon-btn' });
		setIcon(collapseBtn, 'chevrons-right'); // Use appropriate icon
		collapseBtn.title = 'Collapse All Headers';
		collapseBtn.onclick = async () => {
			this.expandedDecks.clear();
			// Optionally keep concepts open? or clear them too? Usually collapse all means decks.
			// Let's clear decks only for now as concepts are leaf node details.
			// User asked "header expand randomly... collapse all".
			await this.saveState();
			this.render();
		};
		
		const refreshBtn = rightGroup.createEl('button', { cls: 'arete-icon-btn' });
		setIcon(refreshBtn, 'refresh-cw');
		refreshBtn.title = 'Refresh Stats from Anki';
		refreshBtn.onclick = async () => {
			new Notice('Refreshing stats...');
			refreshBtn.addClass('arete-spin');
			try {
				await this.plugin.statsService.refreshStats();
				await this.plugin.saveStats(); // Persist to disk
				this.render();
				new Notice('Stats refreshed.');
			} catch (e) {
				new Notice('Failed to refresh stats.');
				console.error(e);
			} finally {
				refreshBtn.removeClass('arete-spin');
			}
		};

		// Last Updated
		const lastFetched = this.plugin.statsService.getCache().lastFetched;
		if (lastFetched > 0) {
			const dateStr = new Date(lastFetched).toLocaleString();
			const lastUpdated = container.createDiv({ 
				text: `Last updated: ${dateStr}`, 
				cls: 'arete-muted'
			});
			lastUpdated.style.fontSize = '0.8em';
			lastUpdated.style.padding = '0 1rem';
			lastUpdated.style.marginBottom = '1rem';
		}

		// Data List
		const concepts = Object.values(this.plugin.statsService.getCache().concepts);
		
		if (concepts.length === 0) {
			const listContainer = container.createDiv({ cls: 'arete-stats-list' });
			const empty = listContainer.createDiv({ cls: 'arete-empty-state' });
			empty.style.textAlign = 'center';
			empty.style.padding = '2rem';
			empty.createEl('p', { text: 'No stats data found.' });
			empty.createEl('p', { text: 'Make sure Anki is running and click Refresh.' });
			return;
		}

		const listContainer = container.createDiv({ cls: 'arete-stats-list' });

		if (this.currentViewMode === 'hierarchy') {
			// Hierarchy View
			const rootNode = this.buildDeckTree(concepts);
			const sortedDeckKeys = Object.keys(rootNode.children).sort();
			sortedDeckKeys.forEach(key => {
				this.renderDeckNode(listContainer, rootNode.children[key], 0);
			});
			if (rootNode.concepts.length > 0) {
				rootNode.concepts.sort((a,b) => b.score - a.score);
				rootNode.concepts.forEach(c => this.renderConceptRow(listContainer, c));
			}
		} else {
			// Leaderboard View (Flat)
			// Filter out perfect concepts? Or show all?
			// Usually leaderboard shows problematic ones first.
			const sortedConcepts = [...concepts].sort((a, b) => b.score - a.score);
			
			// Maybe only show top 50 or those with bad score?
			// Let's show all for now, maybe filter score > 0?
			// "Problematic Concepts" implies filtering, but let's show all sorted.
			
			if (sortedConcepts.every(c => c.problematicCardsCount === 0)) {
				listContainer.createDiv({ text: "Great job! No problematic concepts found.", cls: "arete-success-message" });
			}

			sortedConcepts.forEach(c => {
				// Only show if score > 0 to declutter? user request didn't specify.
				// Let's show all so they can see "Green" status too.
				this.renderConceptRow(listContainer, c);
			});
		}
	}

	buildDeckTree(concepts: ConceptStats[]): DeckTreeNode {
		const root: DeckTreeNode = { 
			name: 'Root', 
			fullName: '', 
			concepts: [], 
			children: {}, 
			totalProblematic: 0,
			totalCards: 0,
			totalLapses: 0,
			sumDifficulty: 0,
			countDifficulty: 0
		};

		concepts.forEach(c => {
			const deckName = c.primaryDeck || 'Default';
			const parts = deckName.split('::');
			
			let currentNode = root;
			let currentPath = '';

			parts.forEach((part, index) => {
				const isLast = index === parts.length - 1;
				currentPath = currentPath ? `${currentPath}::${part}` : part;
				// Clean parsing logic if deck starts with :: (which shouldn't happen) or empty

				if (!currentNode.children[part]) {
					currentNode.children[part] = {
						name: part,
						fullName: currentPath,
						concepts: [],
						children: {},
						totalProblematic: 0,
						totalCards: 0,
						totalLapses: 0,
						sumDifficulty: 0,
						countDifficulty: 0
					};
				}
				currentNode = currentNode.children[part];
				// currentNode.totalProblematic += c.problematicCardsCount; // propagation REMOVED, doing post-aggregation
			});

			// Assign concept to the leaf node
			currentNode.concepts.push(c);
		});

		this.aggregateTree(root);
		return root;
	}

	aggregateTree(node: DeckTreeNode) {
		// Base case: aggregate local concepts
		node.concepts.forEach(c => {
			node.totalProblematic += c.problematicCardsCount;
			node.totalCards += c.totalCards;
			node.totalLapses += c.totalLapses;
			
			if (this.plugin.settings.stats_algorithm === 'fsrs' && c.averageDifficulty !== null && c.averageDifficulty !== undefined) {
				// Approximate sum from average
				if (c.difficultyCount) {
					node.sumDifficulty += c.averageDifficulty * c.difficultyCount;
					node.countDifficulty += c.difficultyCount;
				}
			}
		});

		// Recursive case: aggregate children
		Object.values(node.children).forEach(child => {
			this.aggregateTree(child);
			node.totalProblematic += child.totalProblematic;
			node.totalCards += child.totalCards;
			node.totalLapses += child.totalLapses;
			node.sumDifficulty += child.sumDifficulty;
			node.countDifficulty += child.countDifficulty;
		});
	}

	renderDeckNode(container: HTMLElement, node: DeckTreeNode, depth: number) {
		const deckContainer = container.createDiv({ cls: 'arete-deck-group' });
		
		// Deck Header
		const header = deckContainer.createDiv({ cls: 'arete-deck-header' });
		header.style.display = 'flex';
		header.style.alignItems = 'center';
		header.style.padding = '0.5rem 1rem';
		header.style.paddingLeft = `${0.5 + (depth * 1.5)}rem`; // Indentation
		header.style.backgroundColor = 'var(--background-secondary)';
		header.style.borderBottom = '1px solid var(--background-modifier-border)';
		header.style.cursor = 'pointer';

		// Expand Icon
		const icon = header.createSpan({ cls: 'arete-icon' });
		icon.style.marginRight = '0.5rem';
		

		// Initial State
		// REMOVED: if (depth < 1) ... logic. We rely on persistent state now.
		let isExpanded = this.expandedDecks.has(node.fullName);
		setIcon(icon, isExpanded ? 'chevron-down' : 'chevron-right');

		// Name & Count
		header.createSpan({ text: `${node.name} ` });
		
		// Aggregated Stats Info
		const statsInfo = header.createSpan({ cls: 'arete-muted' });
		statsInfo.style.fontSize = '0.7em';
		statsInfo.style.marginLeft = '1rem';
		statsInfo.style.marginRight = 'auto'; // Push badge to end

		// Calculate Avg
		let avgDiffText = '';
		if (this.plugin.settings.stats_algorithm === 'fsrs') {
			if (node.countDifficulty > 0) {
				const avg = Math.round((node.sumDifficulty / node.countDifficulty) * 100);
				avgDiffText = `Avg Diff: ${avg}% • `;
			} else {
				avgDiffText = `Avg Diff: N/A • `;
			}
		}

		statsInfo.setText(`${avgDiffText}${node.totalProblematic}/${node.totalCards} Bad`);

		if (node.totalProblematic > 0) {
			const badge = header.createSpan({ text: `${node.totalProblematic}`, cls: 'arete-badge' });
			// badge.style.marginLeft = 'auto'; // handled by flex or margin-right of statsInfo?
			// keeping margin-left auto ensuring right alignment
			badge.style.marginLeft = '0.5rem'; 
			badge.style.backgroundColor = node.totalProblematic > 5 ? 'var(--color-red)' : 'var(--color-orange)';
			badge.style.color = 'var(--text-on-accent)';
			badge.style.padding = '2px 6px';
			badge.style.borderRadius = '10px';
			badge.style.fontSize = '0.8em';
		} else {
			const badge = header.createSpan({ text: `0`, cls: 'arete-badge' });
			badge.style.marginLeft = '0.5rem';
			badge.style.backgroundColor = 'var(--color-green)';
			badge.style.color = 'var(--text-on-accent)';
			badge.style.padding = '2px 6px';
			badge.style.borderRadius = '10px';
			badge.style.fontSize = '0.8em';
		}


		// Content Container for Children/Concepts
		const contentContainer = deckContainer.createDiv();
		if (!isExpanded) {
			contentContainer.style.display = 'none';
		}

		// Click Handler: Toggle DOM Only
		header.onclick = async (e) => {
			e.stopPropagation();
			isExpanded = !isExpanded;
			
			if (isExpanded) {
				this.expandedDecks.add(node.fullName);
				contentContainer.style.display = 'block';
				setIcon(icon, 'chevron-down');
			} else {
				this.expandedDecks.delete(node.fullName);
				contentContainer.style.display = 'none';
				setIcon(icon, 'chevron-right');
			}
			await this.saveState();
		};

		// Render Content (Always render to DOM, control visibility via CSS)
		// 1. Concepts
		if (node.concepts.length > 0) {
			const conceptsDiv = contentContainer.createDiv();
			node.concepts.sort((a,b) => b.score - a.score);
			node.concepts.forEach(c => {
				const wrapper = conceptsDiv.createDiv();
				wrapper.style.paddingLeft = `${1.5 * (depth + 1)}rem`;
				this.renderConceptRow(wrapper, c);
			});
		}

		// 2. Children (Subdecks)
		const childKeys = Object.keys(node.children).sort();
		childKeys.forEach(key => {
			this.renderDeckNode(contentContainer, node.children[key], depth + 1);
		});
	}

	renderConceptRow(container: HTMLElement, concept: ConceptStats) {
		const row = container.createDiv({ cls: 'arete-stat-row' });
		row.style.borderBottom = '1px solid var(--background-modifier-border)';
		row.style.padding = '0.5rem 1rem';

		// Summary Line
		const summary = row.createDiv({ cls: 'arete-stat-summary' });
		summary.style.display = 'flex';
		summary.style.justifyContent = 'space-between';
		summary.style.alignItems = 'center';
		summary.style.cursor = 'pointer';
		
		// Left: Title + Score Bar
		const left = summary.createDiv();
		
		// Title
		const titleLine = left.createDiv();
		const titleLink = titleLine.createSpan({ cls: 'arete-stat-title', text: concept.fileName });
		titleLink.style.fontWeight = 'bold';
		titleLink.style.marginRight = '0.5rem';
		
		// Clickable Title
		titleLink.addClass('arete-clickable');
		titleLink.onclick = (e) => {
			e.stopPropagation();
			this.openFile(concept.filePath);
		};

		// Score Indicator
		const scoreColor = this.getScoreColor(concept.score);
		const scoreBadge = titleLine.createSpan({ 
			text: `${(concept.score * 100).toFixed(0)}% Bad`,
			cls: 'arete-badge' 
		});
		scoreBadge.style.backgroundColor = scoreColor;
		scoreBadge.style.color = 'var(--text-on-accent)';
		scoreBadge.style.fontSize = '0.7em';
		scoreBadge.style.padding = '2px 6px';
		scoreBadge.style.borderRadius = '4px';
		scoreBadge.style.marginLeft = '8px';

		// Stats Text
		const statsLine = left.createDiv({ cls: 'arete-muted' });
		statsLine.style.fontSize = '0.8em';


		let metricLabel = '';
		if (this.plugin.settings.stats_algorithm === 'fsrs') {
			if (concept.averageDifficulty !== null && concept.averageDifficulty !== undefined) {
				metricLabel = `Avg Diff: ${(concept.averageDifficulty * 100).toFixed(0)}%`;
			} else {
				metricLabel = `Avg Diff: N/A`;
			}
		} else {
			metricLabel = `Avg Ease: ${(concept.averageEase / 10).toFixed(0)}%`;
		}

		statsLine.setText(
			`${concept.problematicCardsCount}/${concept.totalCards} Problematic • ${metricLabel} • Lapses: ${concept.totalLapses}`
		);

		// Right: Expand chevron
		const right = summary.createDiv();
		const chevron = right.createSpan({ cls: 'arete-icon' });
		const isExpanded = this.expandedConcepts.has(concept.filePath);
		setIcon(chevron, isExpanded ? 'chevron-down' : 'chevron-right');

		// Toggle Expand
		summary.onclick = async () => {
			if (this.expandedConcepts.has(concept.filePath)) {
				this.expandedConcepts.delete(concept.filePath);
			} else {
				this.expandedConcepts.add(concept.filePath);
			}
			await this.saveState();
			this.render(); // Re-render to show details
		};

		// Details Section
		if (isExpanded) {
			const details = row.createDiv({ cls: 'arete-stat-details' });
			details.style.marginTop = '0.5rem';
			details.style.paddingLeft = '1rem';
			details.style.borderLeft = '2px solid var(--background-modifier-border-hover)';

			if (concept.problematicCards.length === 0) {
				details.createDiv({ text: 'No problematic cards found.', cls: 'arete-muted' });
			} else {
				concept.problematicCards.forEach(card => {
					this.renderCardDetail(details, card, concept.filePath);
				});
			}
		}
	}

	renderCardDetail(container: HTMLElement, card: ProblematicCard, filePath: string) {
		const cardRow = container.createDiv({ cls: 'arete-card-detail-row' });
		cardRow.style.padding = '4px 0';
		cardRow.style.fontSize = '0.9em';
		cardRow.style.display = 'flex';
		cardRow.style.justifyContent = 'space-between';
		cardRow.style.borderBottom = '1px solid var(--background-primary)'; // Subtle separator

		const info = cardRow.createDiv();
		info.style.overflow = 'hidden';
		info.style.textOverflow = 'ellipsis';
		info.style.whiteSpace = 'nowrap';
		info.style.maxWidth = '70%';
		info.style.cursor = 'pointer';
		
		// Clean front text
		const frontClean = card.front.replace(/<[^>]*>?/gm, '');
		const text = info.createSpan({ text: frontClean });
		text.title = frontClean; // Tooltip for full text

		// Click to navigate to card
		info.onclick = () => {
			this.goToCard(filePath, card.front);
		};

		const meta = cardRow.createDiv({ cls: 'arete-danger' });
		meta.setText(card.issue);
		meta.style.fontSize = '0.8em';
	}

	getScoreColor(score: number): string {
		if (score > 0.5) return 'var(--color-red)';
		if (score > 0.2) return 'var(--color-orange)';
		return 'var(--color-green)';
	}

	async openFile(filePath: string) {
		const file = this.app.vault.getAbstractFileByPath(filePath);
		if (file instanceof TFile) {
			const leaf = this.app.workspace.getLeaf(false);
			await leaf.openFile(file);
		} else {
			new Notice('File not found.');
		}
	}

	async goToCard(filePath: string, frontText: string) {
		await this.openFile(filePath);
		
		const view = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (view) {
			const editor = view.editor;
			const content = editor.getValue();
			const index = content.indexOf(frontText); // Very naive, frontText might be partial or formatted
			
			if (index >= 0) {
				const pos = editor.offsetToPos(index);
				editor.setCursor(pos);
				editor.scrollIntoView({ from: pos, to: pos }, true);
			} else {
				new Notice('Could not locate card text exact match.');
			}
		}
	}

	async saveState() {
		this.plugin.settings.ui_expanded_decks = Array.from(this.expandedDecks);
		this.plugin.settings.ui_expanded_concepts = Array.from(this.expandedConcepts);
		await this.plugin.saveSettings();
	}
}
