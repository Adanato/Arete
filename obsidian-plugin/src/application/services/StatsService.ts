import { App, TFile, Notice } from 'obsidian';
import { AretePluginSettings } from '@/domain/settings';
import { AreteClient } from '@/infrastructure/arete/AreteClient';

export interface AnkiCardStats {
	cardId: number;
	noteId: number;
	lapses: number;
	ease: number; // Factor (SM-2)
	difficulty?: number; // FSRS Difficulty (0-1 approx, scaled)
	deckName: string;
	interval: number;
	due: number; // Epoch
	reps: number;
	averageTime: number; // ms
	front?: string; // Content from Obsidian
}

export interface ProblematicCard {
	front: string;
	back: string;
	cardId: number;
	noteId: number;
	lapses: number;
	ease: number;
	difficulty?: number;
	deckName: string;
	issue: string; // e.g. "High Lapses (5)" or "Ease Hell (130%)"
}

export interface ConceptStats {
	filePath: string;
	fileName: string;
	primaryDeck: string;
	totalCards: number;
	problematicCardsCount: number;
	problematicCards: ProblematicCard[];
	cardStats: Record<number, AnkiCardStats>; // New: Store all stats by Note ID
	averageEase: number;
	averageDifficulty: number | null; // Null if no FSRS data found
	difficultyCount?: number; // Internal tracking
	totalLapses: number;
	score: number; // 0.0 to 1.0 (Problematic Ratio)
	lastUpdated: number;
}

export interface StatsCache {
	concepts: Record<string, ConceptStats>; // Keyed by filePath
	lastFetched: number;
}

export class StatsService {
	app: App;
	settings: AretePluginSettings;
	cache: StatsCache;
	private client: AreteClient;

	constructor(app: App, settings: AretePluginSettings, initialCache?: StatsCache) {
		this.app = app;
		this.settings = settings;
		this.cache = initialCache || { concepts: {}, lastFetched: 0 };
		this.client = new AreteClient(settings);
	}

	getCache(): StatsCache {
		return this.cache;
	}

	async refreshStats(): Promise<ConceptStats[]> {
		const files = this.app.vault.getMarkdownFiles();
		const nidMap = new Map<
			number,
			{ file: TFile; index: number; front: string; back: string }
		>();
		const filesWithCards: Map<string, TFile> = new Map();
		const conceptMap: Record<string, ConceptStats> = {};
		const conceptDeckCounts: Record<string, Record<string, number>> = {}; // filePath -> { deckName: count }

		// 1. Scan Vault
		for (const file of files) {
			const cache = this.app.metadataCache.getFileCache(file);
			if (cache?.frontmatter?.cards) {
				const cards = cache.frontmatter.cards;
				const yamlDeck = cache.frontmatter.deck; // Custom YAML field

				if (Array.isArray(cards) && cards.length > 0) {
					// Initialize map entry with YAML deck if present
					filesWithCards.set(file.path, file);
					conceptMap[file.path] = {
						filePath: file.path,
						fileName: file.name,
						primaryDeck: yamlDeck || 'Unknown', // Prioritize YAML
						totalCards: 0,
						problematicCardsCount: 0,
						problematicCards: [],
						cardStats: {}, // Init empty
						averageEase: 0,
						averageDifficulty: null, // Init as null
						difficultyCount: 0, // NEW: Track valid difficulty
						totalLapses: 0,
						score: 0,
						lastUpdated: Date.now(),
					};
					conceptDeckCounts[file.path] = {};

					cards.forEach((card: any, index: number) => {
						if (!card) return; // Skip null/malformed cards
						if (card.nid) {
							const nid = parseInt(card.nid);
							if (!isNaN(nid)) {
								nidMap.set(nid, {
									file,
									index,
									front: card.front || card.Front || 'Unknown',
									back: card.back || card.Back || '',
								});
							}
						}
					});
				}
			}
		}

		if (nidMap.size === 0) {
			new Notice('No linked Anki cards found in vault.');
			return [];
		}

		// 2. Fetch from Anki
		const nids = Array.from(nidMap.keys());
		const cardStats = await this.fetchAnkiCardStats(nids);

		// 3. Process fetched stats
		for (const stat of cardStats) {
			const meta = nidMap.get(stat.noteId);
			if (!meta) continue;

			const concept = conceptMap[meta.file.path];
			if (!concept) continue;

			// Store by Card ID (Precise)
			stat.front = meta.front;
			concept.cardStats[stat.cardId] = stat;

			// Store by Note ID (Fallback/Merged) - handle multiple cards per Note ID
			const existing = concept.cardStats[stat.noteId];
			if (existing) {
				let replace = false;

				// 1. FSRS Difficulty: Prefer defined, then higher
				if (this.settings.stats_algorithm === 'fsrs') {
					if (stat.difficulty !== undefined) {
						if (existing.difficulty === undefined) replace = true;
						else if (stat.difficulty > existing.difficulty) replace = true;
					}
				}
				// 2. SM-2 Ease: Prefer Lower (harder)
				else {
					if (stat.ease < existing.ease) replace = true;
				}

				// 3. Lapses: If stats are equal/comparable, prefer higher lapses
				if (!replace && stat.lapses > existing.lapses) {
					if (this.settings.stats_algorithm === 'fsrs') {
						// Only override if difficulty logic didn't already decide (e.g. both undefined or equal)
						if (stat.difficulty === existing.difficulty) replace = true;
					} else {
						// Only override if ease is equal
						if (stat.ease === existing.ease) replace = true;
					}
				}

				if (replace) {
					concept.cardStats[stat.noteId] = stat;
				}
			} else {
				concept.cardStats[stat.noteId] = stat;
			}

			concept.totalCards++;
			concept.totalLapses += stat.lapses;
			// Accumulate metrics
			concept.averageEase += stat.ease;
			if (stat.difficulty !== undefined && stat.difficulty !== null) {
				// If averageDifficulty is null, initialize it to 0 before adding
				if (concept.averageDifficulty === null) {
					concept.averageDifficulty = 0;
				}
				concept.averageDifficulty += stat.difficulty;
				concept.difficultyCount = (concept.difficultyCount || 0) + 1;
			}

			// Track Deck (pick primary later if not set by YAML)
			const deck = stat.deckName || 'Default';
			if (!conceptDeckCounts[meta.file.path][deck]) {
				conceptDeckCounts[meta.file.path][deck] = 0;
			}
			conceptDeckCounts[meta.file.path][deck]++;

			// Check if problematic
			let isProblematic = false;
			const issues: string[] = [];

			// Common: Lapses
			if (stat.lapses >= this.settings.stats_lapse_threshold) {
				isProblematic = true;
				issues.push(`Lapses: ${stat.lapses}`);
			}

			// Algo Specific
			if (this.settings.stats_algorithm === 'fsrs') {
				if (
					stat.difficulty !== undefined &&
					stat.difficulty > this.settings.stats_difficulty_threshold
				) {
					isProblematic = true;
					issues.push(`Diff: ${(stat.difficulty * 100).toFixed(0)}%`);
				}
			} else {
				// SM-2
				if (stat.ease < this.settings.stats_ease_threshold) {
					isProblematic = true;
					issues.push(`Ease: ${(stat.ease / 10).toFixed(0)}%`);
				}
			}

			if (isProblematic) {
				concept.problematicCardsCount++;
				concept.problematicCards.push({
					front: meta.front,
					back: meta.back,
					cardId: stat.cardId,
					noteId: stat.noteId,
					lapses: stat.lapses,
					ease: stat.ease,
					difficulty: stat.difficulty,
					deckName: deck,
					issue: issues.join(', '),
				});
			}
		}

		// Finalize Averages, Scores, and Primary Deck
		const results: ConceptStats[] = [];
		for (const key in conceptMap) {
			const c = conceptMap[key];
			if (c.totalCards > 0) {
				c.averageEase = Math.round(c.averageEase / c.totalCards);

				if (c.difficultyCount && c.difficultyCount > 0) {
					c.averageDifficulty = parseFloat(
						(c.averageDifficulty! / c.difficultyCount).toFixed(2),
					);
				} else {
					c.averageDifficulty = null; // Explicitly null if no valid difficulty stats
				}

				c.score = c.problematicCardsCount / c.totalCards;

				// Determine Primary Deck if not already set by YAML
				if (c.primaryDeck === 'Unknown') {
					const decks = conceptDeckCounts[key];
					let maxCount = 0;
					let primary = 'Unknown';
					for (const deck in decks) {
						if (decks[deck] > maxCount) {
							maxCount = decks[deck];
							primary = deck;
						}
					}
					c.primaryDeck = primary;
				}
			}
			results.push(c);
		}

		// Update Cache
		this.cache.concepts = conceptMap;
		this.cache.lastFetched = Date.now();

		return results.sort((a, b) => b.score - a.score); // Sort by problematic score desc
	}

	async fetchAnkiCardStats(nids: number[]): Promise<AnkiCardStats[]> {
		try {
			const data = await this.client.invoke('/anki/stats', { nids });

			if (Array.isArray(data)) {
				// Map snake_case (Python) to camelCase (TS)
				return data.map((d: any) => ({
					cardId: d.card_id,
					noteId: d.note_id,
					lapses: d.lapses,
					ease: d.ease,
					difficulty: d.difficulty,
					deckName: d.deck_name,
					interval: d.interval,
					due: d.due,
					reps: d.reps,
					averageTime: d.average_time,
					front: d.front,
				}));
			} else {
				console.warn('[Arete] Unexpected stats response format:', data);
			}
		} catch (e) {
			console.warn('[Arete] Failed to fetch stats via AreteClient:', e);
			new Notice('Failed to fetch stats from Arete.');
		}

		return [];
	}
}
