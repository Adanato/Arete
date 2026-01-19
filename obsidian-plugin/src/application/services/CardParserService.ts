import { parseYaml } from 'obsidian';

export interface CardRange {
	index: number;
	startLine: number;
	endLine: number;
	nid: number | null;
	cid: number | null;
}

export interface ParseResult {
	ranges: CardRange[];
	frontmatterEndLine: number | null;
	hasCards: boolean;
}

export class CardParserService {
	/**
	 * Parses a document string to find card ranges and their IDs.
	 * This is the primary logic for identifying cards in a note.
	 */
	static parseCards(docText: string): ParseResult {
		const docLines = docText.split('\n');
		const ranges: CardRange[] = [];
		let frontmatterEndLine: number | null = null;
		let inCards = false;
		let cardsBaseIndent = -1;

		// Find frontmatter end
		if (docLines[0] === '---') {
			for (let i = 1; i < docLines.length; i++) {
				if (docLines[i] === '---') {
					frontmatterEndLine = i;
					break;
				}
			}
		}

		for (let i = 1; i < docLines.length; i++) {
			const line = docLines[i];
			const trimmed = line.trim();

			// Stop at frontmatter end if we are in it
			if (line === '---' && frontmatterEndLine !== null && i === frontmatterEndLine) {
                // We reached the end of frontmatter
                break; 
            }
			if (!trimmed) continue;

			if (!inCards) {
				if (trimmed === 'cards:' || trimmed.startsWith('cards:')) {
					inCards = true;
				}
				continue;
			}

			const indent = line.search(/\S/);
			if (trimmed.startsWith('- ')) {
				if (cardsBaseIndent === -1) cardsBaseIndent = indent;
				if (indent === cardsBaseIndent) {
					const startLine = i;
					let endLine = i;

					// Find end of this card block
					for (let j = i + 1; j < docLines.length; j++) {
						const nl = docLines[j];
						const nt = nl.trim();
						if (nl === '---' && frontmatterEndLine !== null) {
							endLine = j - 1;
							break;
						}
						if (!nt) {
							endLine = j;
							continue;
						}
						const ni = nl.search(/\S/);
						// New card item or decreased indent means block ended
						if (ni === cardsBaseIndent && nt.startsWith('- ')) {
							endLine = j - 1;
							break;
						}
						if (ni < cardsBaseIndent) {
							endLine = j - 1;
							break;
						}
						endLine = j;
					}

					const block = docLines.slice(startLine, endLine + 1).join('\n');
					let nid: number | null = null;
					let cid: number | null = null;

					try {
						// Attempt precise extraction with parseYaml
						// We normalize the block to be a valid single-mapping YAML
						const cleanBlock = block.replace(/^\s*-/, ' ');
						const data = parseYaml(cleanBlock);
						if (data && typeof data === 'object') {
							const rawNid = data.nid ?? data.NID;
							const rawCid = data.cid ?? data.CID;

							if (rawNid !== undefined && rawNid !== null) {
								nid = typeof rawNid === 'string' ? parseInt(rawNid) : Number(rawNid);
							}
							if (rawCid !== undefined && rawCid !== null) {
								cid = typeof rawCid === 'string' ? parseInt(rawCid) : Number(rawCid);
							}
						}
					} catch (e) {
						// Fallback to regex if parseYaml fails
						const nidMatch = block.match(/['"]?(?:nid|NID)['"]?\s*:\s*['"]?(\d+)/i);
						if (nidMatch) nid = parseInt(nidMatch[1]);
						const cidMatch = block.match(/['"]?(?:cid|CID)['"]?\s*:\s*['"]?(\d+)/i);
						if (cidMatch) cid = parseInt(cidMatch[1]);
					}

					ranges.push({
						index: ranges.length,
						startLine,
						endLine: this.findLastContentLine(docLines, startLine, endLine),
						nid: isNaN(Number(nid)) ? null : nid,
						cid: isNaN(Number(cid)) ? null : cid,
					});
					i = endLine;
				}
			} else if (indent < cardsBaseIndent && trimmed.length > 0) {
				inCards = false;
			}
		}

		return {
			ranges,
			frontmatterEndLine,
			hasCards: ranges.length > 0,
		};
	}

	/**
	 * Helper: Find last non-blank line in a range
	 */
	private static findLastContentLine(
		lines: string[],
		startLine: number,
		endLine: number,
	): number {
		for (let i = endLine; i >= startLine; i--) {
			if (lines[i].trim().length > 0) {
				return i;
			}
		}
		return startLine;
	}
}
