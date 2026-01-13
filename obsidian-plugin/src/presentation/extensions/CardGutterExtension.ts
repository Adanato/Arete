import { EditorView, gutter, GutterMarker, Decoration, DecorationSet } from '@codemirror/view';
import { RangeSetBuilder, StateField, StateEffect } from '@codemirror/state';

interface CardRange {
	index: number;
	startLine: number;
	endLine: number;
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
	onClick: () => void;

	constructor(index: number, isStart: boolean, isEnd: boolean, onClick: () => void) {
		super();
		this.index = index;
		this.isStart = isStart;
		this.isEnd = isEnd;
		this.onClick = onClick;
	}

	toDOM() {
		const marker = document.createElement('div');
		marker.className = 'arete-gutter-marker';
		marker.dataset.cardIndex = String(this.index);

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
			marker.appendChild(badge);
		}

		// Add the colored bar
		const bar = document.createElement('div');
		bar.className = 'arete-gutter-bar';
		marker.appendChild(bar);

		// Hover handlers to highlight all markers of the same card
		marker.addEventListener('mouseenter', () => {
			document.querySelectorAll(`.arete-gutter-marker[data-card-index="${this.index}"]`).forEach((el) => {
				el.classList.add('arete-gutter-hover');
			});
		});
		
		marker.addEventListener('mouseleave', () => {
			document.querySelectorAll(`.arete-gutter-marker[data-card-index="${this.index}"]`).forEach((el) => {
				el.classList.remove('arete-gutter-hover');
			});
		});

		marker.addEventListener('click', (e) => {
			e.preventDefault();
			e.stopPropagation();
			
			// Remove active class from all gutter markers
			document.querySelectorAll('.arete-gutter-marker.arete-gutter-active').forEach((el) => {
				el.classList.remove('arete-gutter-active');
			});
			
			// Add active class to all markers of this card
			document.querySelectorAll(`.arete-gutter-marker[data-card-index="${this.index}"]`).forEach((el) => {
				el.classList.add('arete-gutter-active');
			});
			
			this.onClick();
		});

		return marker;
	}
}

// Parse YAML to find card ranges and frontmatter end
function parseCardRanges(text: string): ParseResult {
	const lines = text.split('\n');
	const ranges: CardRange[] = [];
	let frontmatterEndLine: number | null = null;

	let inFrontmatter = false;
	let inCards = false;
	let currentCard: { startLine: number; index: number } | null = null;
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
					endLine: i - 1,
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
		// Matches: "- model:", "  - model:", "- Front:", etc.
		if (
			trimmed.startsWith('- ') &&
			(trimmed.includes('model:') || trimmed.includes('Front:') || trimmed.includes('front:'))
		) {
			// Close previous card
			if (currentCard) {
				ranges.push({
					index: currentCard.index,
					startLine: currentCard.startLine,
					endLine: i - 1,
				});
			}
			// Start new card
			currentCard = { startLine: i, index: cardIndex };
			cardIndex++;
		}

		// Detect end of cards section (a new top-level key, not indented continuation)
		// This is tricky - we stop when we hit a line that's a new YAML key at root level
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
				endLine: i - 1,
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
		// Keep existing decorations if no effect
		return decorations;
	},
	provide: (f) => EditorView.decorations.from(f),
});

// Create the gutter extension
export function createCardGutter(onCardClick: (cardIndex: number) => void) {
	return [
		cardRangesField,
		cardHighlightField,
		gutter({
			class: 'arete-card-gutter',
			markers: (view) => {
				const result = view.state.field(cardRangesField);
				const builder = new RangeSetBuilder<GutterMarker>();

				// Add skip-to-bottom button on line 1 if there are cards
				if (result.hasCards && result.frontmatterEndLine !== null) {
					const firstLine = view.state.doc.line(1);
					builder.add(
						firstLine.from,
						firstLine.from,
						new SkipToBottomMarker(result.frontmatterEndLine, view),
					);
				}

				// Add card markers
				for (const range of result.ranges) {
					for (let lineNum = range.startLine; lineNum <= range.endLine; lineNum++) {
						if (lineNum >= view.state.doc.lines) break;

						const line = view.state.doc.line(lineNum + 1); // 1-indexed
						const isStart = lineNum === range.startLine;
						const isEnd = lineNum === range.endLine;

						builder.add(
							line.from,
							line.from,
							new CardGutterMarker(range.index, isStart, isEnd, () =>
								onCardClick(range.index),
							),
						);
					}
				}

				return builder.finish();
			},
		}),
	];
}
