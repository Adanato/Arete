import { EditorView, gutter, GutterMarker, Decoration, DecorationSet } from '@codemirror/view';
import { RangeSetBuilder, StateField, StateEffect } from '@codemirror/state';
import type { AnkiCardStats } from '@/domain/stats';

interface CardRange {
	index: number;
	startLine: number;
	endLine: number;
	nid: number | null;
	cid: number | null;
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
	stats: AnkiCardStats | null;
	algorithm: 'fsrs' | 'sm2';
	onClick: () => void;

	constructor(
		index: number,
		isStart: boolean,
		isEnd: boolean,
		lineIndex: number,
		totalLines: number,
		stats: AnkiCardStats | null,
		algorithm: 'fsrs' | 'sm2',
		onClick: () => void,
	) {
		super();
		this.index = index;
		this.isStart = isStart;
		this.isEnd = isEnd;
		this.lineIndex = lineIndex;
		this.totalLines = totalLines;
		this.stats = stats;
		this.algorithm = algorithm;
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

		// 1. Setup Container for Info (Index + Stats)
		// We use a single container at the top-right to stack items vertically
		if (this.isStart) {
			const infoContainer = document.createElement('div');
			infoContainer.style.position = 'absolute';
			infoContainer.style.top = '0';
			infoContainer.style.right = '6px';
			infoContainer.style.display = 'flex';
			infoContainer.style.flexDirection = 'column';
			infoContainer.style.alignItems = 'flex-end';
			infoContainer.style.gap = '2px'; // 2px vertical spacing
			infoContainer.style.zIndex = '2';
			infoContainer.style.pointerEvents = 'none'; // Pass clicks to marker

			// Index Badge
			const badge = document.createElement('span');
			badge.className = 'arete-gutter-badge';
			badge.textContent = String(this.index + 1);
			badge.style.fontSize = '9px';
			badge.style.lineHeight = '10px';
			badge.style.fontWeight = 'bold';
			badge.style.color = 'var(--text-muted)';
			badge.style.position = 'static'; // Reset absolute as it's flex now
			infoContainer.appendChild(badge);

			// Stats (if available)
			if (this.stats) {
				// Difficulty
				let diffText = '';
				let diffColor = 'var(--text-muted)';

				if (this.algorithm === 'fsrs') {
					if (
						this.stats.difficulty !== undefined &&
						this.stats.difficulty !== null &&
						this.stats.difficulty > 0
					) {
						// difficulty is already 1-10 scale from backend
						diffText = `${this.stats.difficulty.toFixed(1)}`;
						if (this.stats.difficulty > 9) diffColor = 'var(--color-red)';
						else if (this.stats.difficulty > 5) diffColor = 'var(--color-orange)';
						else diffColor = 'var(--color-green)';
					} else {
						diffText = 'D:?';
					}
				} else {
					if (this.stats.ease && this.stats.ease > 0) {
						diffText = `E:${Math.round(this.stats.ease / 10)}%`;
					} else {
						diffText = 'E:?';
					}
				}

				const diffSpan = document.createElement('span');
				diffSpan.textContent = diffText;
				diffSpan.style.fontSize = '8px';
				diffSpan.style.lineHeight = '9px';
				diffSpan.style.fontWeight = 'bold';
				diffSpan.style.color = diffColor;
				infoContainer.appendChild(diffSpan);

				// Lapses
				if (this.stats.lapses > 0) {
					const lapseSpan = document.createElement('span');
					lapseSpan.textContent = `${this.stats.lapses}L`;
					lapseSpan.style.fontSize = '8px';
					lapseSpan.style.lineHeight = '9px';
					lapseSpan.style.fontWeight = 'bold';

					let lapseColor = 'var(--color-orange)';
					if (this.stats.lapses > 5) lapseColor = 'var(--color-red)';
					lapseSpan.style.color = lapseColor;

					infoContainer.appendChild(lapseSpan);
				}

				// Tooltip on the container or marker
				const tooltipLines = [];
				if (this.stats.difficulty)
					tooltipLines.push(`Difficulty: ${this.stats.difficulty.toFixed(1)}/10`);
				if (this.stats.ease)
					tooltipLines.push(`Ease: ${Math.round(this.stats.ease / 10)}%`);
				if (this.stats.lapses) tooltipLines.push(`Lapses: ${this.stats.lapses}`);
				marker.title = tooltipLines.join('\n');
			}

			marker.appendChild(infoContainer);
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

		// Color logic
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

		// Last line: fade
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
	let currentCard: {
		startLine: number;
		index: number;
		nid: number | null;
		cid: number | null;
	} | null = null;
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
					cid: currentCard.cid,
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
					cid: currentCard.cid,
				});
			}
			// Start new card
			currentCard = { startLine: i, index: cardIndex, nid: null, cid: null };
			cardIndex++;
		}

		// Parse NID and CID in current card
		if (currentCard) {
			const nidMatch = trimmed.match(/^nid:\s*['"]?(\d+)['"]?/);
			if (nidMatch) {
				currentCard.nid = parseInt(nidMatch[1]);
			}
			const cidMatch = trimmed.match(/^cid:\s*['"]?(\d+)['"]?/);
			if (cidMatch) {
				currentCard.cid = parseInt(cidMatch[1]);
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
				cid: currentCard.cid,
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
	getCardStats: (nid: number | null, cid: number | null) => AnkiCardStats | null = () => null,
	algorithm: 'fsrs' | 'sm2' = 'fsrs',
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

						// Try to get stats using CID or NID
						let stats = null;
						if (range.nid || range.cid) {
							stats = getCardStats(range.nid, range.cid);
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
								algorithm,
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
