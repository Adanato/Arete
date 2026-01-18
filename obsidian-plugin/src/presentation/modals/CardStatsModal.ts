/**
 * Card Stats Modal - Displays detailed FSRS metrics for a single card.
 * 
 * This modal is shared between DashboardView and CardYamlEditorView.
 */

import { App, Modal, setIcon } from 'obsidian';
import type { AnkiCardStats } from '@/domain/stats';

export class CardStatsModal extends Modal {
	card: AnkiCardStats;

	constructor(app: App, card: AnkiCardStats) {
		super(app);
		this.card = card;
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.empty();
		contentEl.addClass('arete-stats-modal');

		contentEl.createEl('h2', { text: 'Card Memory Insights' }).style.marginBottom = '1.5rem';
		
		const c = this.card;

		// --- Section 1: Memory State ---
		// Note: Backend provides difficulty as 0-1 scale, but we display as 1-10
		const displayDifficulty = c.difficulty != null ? c.difficulty * 10 : null;
		this.renderSection(contentEl, 'Memory State', [
			{ label: 'Difficulty (1-10)', value: displayDifficulty != null ? displayDifficulty.toFixed(1) : '-', color: displayDifficulty != null && displayDifficulty > 7 ? 'var(--color-orange)' : undefined },
			{ label: 'Stability', value: c.stability != null ? `${c.stability.toFixed(1)} days` : '-', color: c.stability != null && c.stability < 7 ? 'var(--color-orange)' : undefined },
			{ label: 'Retrievability', value: c.retrievability != null ? `${(c.retrievability * 100).toFixed(1)}%` : '-', color: c.retrievability != null && c.retrievability < 0.85 ? 'var(--color-red)' : undefined }
		]);


		// --- Section 2: Learning Dynamics (Plausible Metrics) ---
		this.renderSection(contentEl, 'Learning Dynamics', [
			{ 
				label: 'Interval Growth', 
				value: c.intervalGrowth != null ? `${c.intervalGrowth.toFixed(2)}x` : 'N/A',
				color: c.intervalGrowth != null && c.intervalGrowth < 1.2 ? 'var(--color-orange)' : undefined 
			},
			{ 
				label: 'Press Fatigue (Hard%)', 
				value: c.pressFatigue != null ? `${(c.pressFatigue * 100).toFixed(0)}%` : 'N/A',
				color: c.pressFatigue != null && c.pressFatigue > 0.3 ? 'var(--color-red)' : undefined
			},
			{ 
				label: 'Schedule Adherence', 
				value: c.scheduleAdherence != null ? `${(c.scheduleAdherence * 100).toFixed(1)}%` : 'N/A' 
			},
			{ 
				label: 'Days Overdue', 
				value: c.daysOverdue != null ? `${c.daysOverdue}d` : '-',
				color: c.daysOverdue != null && c.daysOverdue > 7 ? 'var(--color-red)' : undefined
			}
		]);

		// --- Section 3: Review History ---
		this.renderSection(contentEl, 'Review History', [
			{ label: 'Total Lapses', value: c.lapses != null ? c.lapses : '0', color: c.lapses != null && c.lapses > 5 ? 'var(--color-red)' : undefined },
			{ label: 'Lapse Rate', value: c.lapseRate != null ? `${(c.lapseRate * 100).toFixed(1)}%` : '-' },
			{ label: 'Total Reps', value: c.reps != null ? c.reps : '0' },
			{ label: 'Avg Time', value: c.averageTime ? `${(c.averageTime / 1000).toFixed(1)}s` : '-' }
		]);

		// Answer Distribution Details
		if (c.answerDistribution) {
			const distHeader = contentEl.createEl('h3', { text: 'Rating Distribution' });
			distHeader.style.margin = '1rem 0 0.5rem 0';
			distHeader.style.fontSize = '1em';
			
			const distTable = contentEl.createDiv({ cls: 'arete-modal-dist' });
			distTable.style.display = 'flex';
			distTable.style.gap = '0.5rem';
			distTable.style.marginBottom = '1.5rem';

			const ratings = [
				{ label: 'Again', key: 1, color: 'var(--color-red)' },
				{ label: 'Hard', key: 2, color: 'var(--color-orange)' },
				{ label: 'Good', key: 3, color: 'var(--color-green)' },
				{ label: 'Easy', key: 4, color: 'var(--color-blue)' }
			];

			ratings.forEach(r => {
				const box = distTable.createDiv();
				box.style.flex = '1';
				box.style.padding = '8px';
				box.style.background = 'var(--background-secondary)';
				box.style.borderRadius = '4px';
				box.style.textAlign = 'center';
				box.createDiv({ text: r.label }).style.fontSize = '0.7em';
				box.createDiv({ text: (c.answerDistribution![r.key] || 0).toString() }).style.fontWeight = 'bold';
			});
		}

		// Flags section
		if (c.isOverlearning) {
			const alert = contentEl.createDiv({ cls: 'arete-alert' });
			alert.style.background = 'rgba(var(--color-yellow-rgb), 0.1)';
			alert.style.padding = '10px';
			alert.style.borderRadius = '5px';
			alert.style.marginTop = '1rem';
			alert.style.border = '1px solid var(--color-yellow)';
			const title = alert.createDiv({ cls: 'arete-alert-title' });
			setIcon(title.createSpan(), 'zap');
			title.createSpan({ text: ' Overlearning Detected' }).style.fontWeight = 'bold';
			alert.createDiv({ text: 'This card is being reviewed significantly before its FSRS-recommended due date with high retrievability. Consider increasing your desired retention or following the schedule more strictly.', cls: 'arete-alert-body' }).style.fontSize = '0.85em';
		}

		// Footer
		const footer = contentEl.createDiv();
		footer.style.marginTop = '2rem';
		footer.style.textAlign = 'right';
		const closeBtn = footer.createEl('button', { text: 'Close' });
		closeBtn.onclick = () => this.close();
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}

	private renderSection(container: HTMLElement, title: string, stats: { label: string, value: string | number, color?: string }[]) {
		const section = container.createDiv({ cls: 'arete-modal-section' });
		section.style.marginBottom = '1.2rem';
		
		const h3 = section.createEl('h3', { text: title });
		h3.style.margin = '0 0 0.6rem 0';
		h3.style.fontSize = '0.9em';
		h3.style.textTransform = 'uppercase';
		h3.style.letterSpacing = '1px';
		h3.style.color = 'var(--text-accent)';
		h3.style.borderBottom = '1px solid var(--background-modifier-border)';
		h3.style.paddingBottom = '4px';

		const grid = section.createDiv();
		grid.style.display = 'grid';
		grid.style.gridTemplateColumns = '1fr 1fr';
		grid.style.gap = '0.8rem 1.5rem';

		stats.forEach(s => {
			const sub = grid.createDiv();
			const labelEl = sub.createDiv({ text: s.label });
			labelEl.style.fontSize = '0.75em';
			labelEl.style.color = 'var(--text-muted)';
			
			const valEl = sub.createDiv({ text: s.value.toString() });
			valEl.style.fontSize = '1.1em';
			valEl.style.fontWeight = '600';
			if (s.color) valEl.style.color = s.color;
		});
	}
}
