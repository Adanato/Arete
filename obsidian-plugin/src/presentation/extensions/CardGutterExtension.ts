import { EditorView, gutter, GutterMarker, Decoration, DecorationSet } from '@codemirror/view';
import { RangeSetBuilder, StateField, StateEffect } from '@codemirror/state';
import { ProblematicCard } from '@application/services/StatsService';

interface CardRange {
	index: number;
	startLine: number;
	endLine: number;
	nid: number | null;
}

interface ParseResult {
	ranges: CardRange[];
	frontmatterEndLine: number | null;
	hasCards: boolean;
}

// Effect to trigger card highlight
export const highlightCardEffect = StateEffect.define<{ cardIndex: number } | null>();

// Line decoration for highlighting
const highlightDecoration = Decoration.line({ class: 'arete-card-highlight' });

// Skip to bottom button marker
class SkipToBottomMarker extends GutterMarker {
	targetLine: number;
	view: EditorView;

	constructor(targetLine: number, view: EditorView) {
		super();
		this.targetLine = targetLine;
		this.view = view;
	}

	toDOM() {
		const marker = document.createElement('div');
		marker.className = 'arete-skip-button';
		marker.innerHTML = '↓';
		marker.title = 'Skip to end of frontmatter';

		marker.addEventListener('click', (e) => {
			e.preventDefault();
			e.stopPropagation();
			// Clear any card highlight
			this.view.dispatch({
				effects: highlightCardEffect.of(null),
			});
			// Scroll so the frontmatter end line is at the top
			const line = this.view.state.doc.line(this.targetLine + 1);
			this.view.dispatch({
				effects: EditorView.scrollIntoView(line.from, { y: 'start' }),
			});
		});

		return marker;
	}
}

// Custom gutter marker for cards
class CardGutterMarker extends GutterMarker {
	index: number;
	isStart: boolean;
	isEnd: boolean;
	lineIndex: number;
	totalLines: number;
	stats: ProblematicCard | null;
	onClick: () => void;

	constructor(
		index: number,
		isStart: boolean,
		isEnd: boolean,
		lineIndex: number,
		totalLines: number,
		stats: ProblematicCard | null,
		onClick: () => void,
	) {
		super();
		this.index = index;
		this.isStart = isStart;
		this.isEnd = isEnd;
		this.lineIndex = lineIndex;
		this.totalLines = totalLines;
		this.stats = stats;
		this.onClick = onClick;
	}

	toDOM() {
		const marker = document.createElement('div');
		marker.className = 'arete-gutter-marker';
		marker.dataset.cardIndex = String(this.index);
		marker.style.position = 'relative';
		marker.style.height = '100%';
		marker.style.width = '100%';
		marker.style.minWidth = '20px';

		if (this.isStart) {
			marker.classList.add('arete-gutter-start');
		}
		if (this.isEnd) {
			marker.classList.add('arete-gutter-end');
		}

		// Add index badge only on the first line
		if (this.isStart) {
			const badge = document.createElement('span');
			badge.className = 'arete-gutter-badge';
			badge.textContent = String(this.index + 1);

			badge.style.position = 'absolute';
			badge.style.top = '0';
			badge.style.right = '6px';
			badge.style.fontSize = '9px';
			badge.style.lineHeight = '10px';
			badge.style.fontWeight = 'bold';
			badge.style.zIndex = '2';
			marker.appendChild(badge);

			// Add Stats Text if available
			if (this.stats) {
				const statsDiv = document.createElement('div');
				statsDiv.className = 'arete-gutter-stats';

				statsDiv.style.position = 'absolute';
				statsDiv.style.bottom = '1px';
				statsDiv.style.right = '6px';
				statsDiv.style.fontSize = '8px';
				statsDiv.style.lineHeight = '8px';
				statsDiv.style.fontWeight = 'bold';
				statsDiv.style.textAlign = 'right';
				statsDiv.style.zIndex = '2';

				let text = '';
				let color = 'var(--text-muted)';

				if (this.stats.difficulty && this.stats.difficulty > 0) {
					const diff = Math.round(this.stats.difficulty * 100);
					text = `${diff}%`;
					if (this.stats.difficulty > 0.9) color = 'var(--color-red)';
					else if (this.stats.difficulty > 0.5) color = 'var(--color-orange)';
				} else if (this.stats.lapses > 0) {
					text = `${this.stats.lapses}L`;
					if (this.stats.lapses > 5) color = 'var(--color-red)';
					else color = 'var(--color-orange)';
				} else {
					text = `${Math.round(this.stats.ease / 10)}%`;
				}

				statsDiv.textContent = text;
				statsDiv.style.color = color;
				statsDiv.title = this.stats.issue;
				marker.appendChild(statsDiv);
			}
		}

		// Add the colored bar
		const bar = document.createElement('div');
		bar.className = 'arete-gutter-bar';

		bar.style.position = 'absolute';
		bar.style.right = '0';
		bar.style.top = '0';
		bar.style.width = '3px';
		bar.style.height = '100%';
		bar.style.marginTop = '-1px';
		bar.style.paddingBottom = '1px';

		bar.style.transition = 'width 0.15s ease-out, box-shadow 0.15s ease-out';

		// Color Logic: Solid color for all lines, fade-out gradient on last line only
		let barColor = 'var(--interactive-accent)';
		let shadowColor = 'var(--interactive-accent)';

		if (
			this.stats &&
			(this.stats.lapses > 5 || (this.stats.difficulty && this.stats.difficulty > 0.9))
		) {
			barColor = 'var(--color-red)';
			shadowColor = 'var(--color-red)';
		} else if (this.stats && this.stats.difficulty && this.stats.difficulty > 0.5) {
			barColor = 'var(--color-orange)';
			shadowColor = 'var(--color-orange)';
		}

		// Last line: fade from solid color to transparent
		if (this.isEnd) {
			bar.style.background = `linear-gradient(to bottom, ${barColor}, transparent)`;
		} else {
			bar.style.backgroundColor = barColor;
		}

		marker.appendChild(bar);

		// Helper to update all segments of this card
		const setCardState = (hover: boolean, active: boolean) => {
			document
				.querySelectorAll(`.arete-gutter-marker[data-card-index="${this.index}"]`)
				.forEach((el) => {
					const b = el.querySelector('.arete-gutter-bar') as HTMLElement;
					if (hover) el.classList.add('arete-gutter-hover');
					else el.classList.remove('arete-gutter-hover');

					if (active) el.classList.add('arete-gutter-active');

					const isActive = el.classList.contains('arete-gutter-active');
					const isHover = el.classList.contains('arete-gutter-hover');

					if (isActive || isHover) {
						if (b) {
							b.style.width = '6px';
							b.style.boxShadow = `0 0 10px ${shadowColor}`;
							b.style.zIndex = '10';
						}
					} else {
						if (b) {
							b.style.width = '3px';
							b.style.boxShadow = 'none';
							b.style.zIndex = '0';
						}
					}
				});
		};

		marker.addEventListener('mouseenter', () => setCardState(true, false));
		marker.addEventListener('mouseleave', () => setCardState(false, false));

		marker.addEventListener('click', (e) => {
			e.preventDefault();
			e.stopPropagation();
			document.querySelectorAll('.arete-gutter-marker.arete-gutter-active').forEach((el) => {
				el.classList.remove('arete-gutter-active');
				const b = el.querySelector('.arete-gutter-bar') as HTMLElement;
				if (b) {
					b.style.width = '3px';
					b.style.boxShadow = 'none';
				}
			});
			setCardState(true, true);
			this.onClick();
		});

		return marker;
	}
}

// Helper: Find last non-blank line in a range
function findLastContentLine(lines: string[], startLine: number, endLine: number): number {
	for (let i = endLine; i >= startLine; i--) {
		if (lines[i].trim().length > 0) {
			return i;
		}
	}
	return startLine; // Fallback to start if all blank
}

// Parse YAML to find card ranges and frontmatter end
function parseCardRanges(text: string): ParseResult {
	const lines = text.split('\n');
	const ranges: CardRange[] = [];
	let frontmatterEndLine: number | null = null;

	let inFrontmatter = false;
	let inCards = false;
	let currentCard: { startLine: number; index: number; nid: number | null } | null = null;
	let cardIndex = 0;

	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		const trimmed = line.trim();

		// Detect frontmatter boundaries
		if (i === 0 && trimmed === '---') {
			inFrontmatter = true;
			continue;
		}
		if (inFrontmatter && trimmed === '---') {
			// End of frontmatter
			frontmatterEndLine = i;
			if (currentCard) {
				ranges.push({
					index: currentCard.index,
					startLine: currentCard.startLine,
					endLine: findLastContentLine(lines, currentCard.startLine, i - 1),
					nid: currentCard.nid,
				});
			}
			break;
		}

		if (!inFrontmatter) continue;

		// Detect cards: key
		if (trimmed === 'cards:' || trimmed.startsWith('cards:')) {
			inCards = true;
			continue;
		}

		if (!inCards) continue;

		// Detect new card (starts with "- " possibly with leading whitespace)
		if (
			trimmed.startsWith('- ') &&
			(trimmed.includes('model:') || trimmed.includes('Front:') || trimmed.includes('front:'))
		) {
			// Close previous card
			if (currentCard) {
				ranges.push({
					index: currentCard.index,
					startLine: currentCard.startLine,
					endLine: findLastContentLine(lines, currentCard.startLine, i - 1),
					nid: currentCard.nid,
				});
			}
			// Start new card
			currentCard = { startLine: i, index: cardIndex, nid: null };
			cardIndex++;
		}

		// Parse NID in current card
		if (currentCard) {
			const nidMatch = trimmed.match(/^nid:\s*['"]?(\d+)['"]?/);
			if (nidMatch) {
				currentCard.nid = parseInt(nidMatch[1]);
			}
		}

		// Detect end of cards section
		if (
			inCards &&
			currentCard &&
			!line.startsWith(' ') &&
			!line.startsWith('-') &&
			trimmed.includes(':') &&
			trimmed.length > 0
		) {
			ranges.push({
				index: currentCard.index,
				startLine: currentCard.startLine,
				endLine: findLastContentLine(lines, currentCard.startLine, i - 1),
				nid: currentCard.nid,
			});
			currentCard = null;
			inCards = false;
		}
	}

	return {
		ranges,
		frontmatterEndLine,
		hasCards: ranges.length > 0,
	};
}

// State field to track card ranges
const cardRangesField = StateField.define<ParseResult>({
	create(state) {
		return parseCardRanges(state.doc.toString());
	},
	update(result, tr) {
		if (tr.docChanged) {
			return parseCardRanges(tr.state.doc.toString());
		}
		return result;
	},
});

// State field to track highlighted card decorations
const cardHighlightField = StateField.define<DecorationSet>({
	create() {
		return Decoration.none;
	},
	update(decorations, tr) {
		// Check for highlight effect
		for (const e of tr.effects) {
			if (e.is(highlightCardEffect)) {
				if (e.value === null) {
					// Clear highlight
					return Decoration.none;
				}

				const cardIndex = e.value.cardIndex;
				const result = tr.state.field(cardRangesField);
				const range = result.ranges.find((r) => r.index === cardIndex);

				if (range) {
					const builder = new RangeSetBuilder<Decoration>();
					for (let lineNum = range.startLine; lineNum <= range.endLine; lineNum++) {
						if (lineNum >= tr.state.doc.lines) break;
						const line = tr.state.doc.line(lineNum + 1);
						builder.add(line.from, line.from, highlightDecoration);
					}
					return builder.finish();
				}
				return Decoration.none;
			}
		}
		return decorations;
	},
	provide: (f) => EditorView.decorations.from(f),
});

// Create the gutter extension
export function createCardGutter(
	onCardClick: (cardIndex: number) => void,
	getCardStats: (nid: number) => ProblematicCard | null = () => null,
) {
	return [
		cardRangesField,
		cardHighlightField,
		gutter({
			class: 'arete-card-gutter',
			markers: (view) => {
				const result = view.state.field(cardRangesField);
				const builder = new RangeSetBuilder<GutterMarker>();

				if (result.hasCards && result.frontmatterEndLine !== null) {
					const firstLine = view.state.doc.line(1);
					builder.add(
						firstLine.from,
						firstLine.from,
						new SkipToBottomMarker(result.frontmatterEndLine, view),
					);
				}

				for (const range of result.ranges) {
					for (let lineNum = range.startLine; lineNum <= range.endLine; lineNum++) {
						if (lineNum >= view.state.doc.lines) break;

						const line = view.state.doc.line(lineNum + 1); // 1-indexed
						const isStart = lineNum === range.startLine;
						const isEnd = lineNum === range.endLine;
						const totalLines = range.endLine - range.startLine + 1;
						const lineIndex = lineNum - range.startLine;

						// Fix: Pass stats to ALL lines so the bar color is consistent opacity/gradient
						let stats = null;
						if (range.nid) {
							stats = getCardStats(range.nid);
						}

						builder.add(
							line.from,
							line.from,
							new CardGutterMarker(
								range.index,
								isStart,
								isEnd,
								lineIndex,
								totalLines,
								stats,
								() => onCardClick(range.index),
							),
						);
					}
				}

				return builder.finish();
			},
		}),
	];
}
