import { App, TFile } from 'obsidian';
import { AnkiConnectRepository } from '../../infrastructure/anki/AnkiConnectRepository';
import { StatsCache, ProblematicCard, ConceptStats } from './StatsService';

export interface LeechCard extends ProblematicCard {
	filePath: string;
	fileName: string;
	deck: string;
}

export class LeechService {
	private app: App;
	private ankiRepo: AnkiConnectRepository;

	constructor(app: App, ankiRepo: AnkiConnectRepository) {
		this.app = app;
		this.ankiRepo = ankiRepo;
	}

	/**
	 * Flattens the StatsCache into a list of specific Leech cards, sorted by severity (lapses).
	 */
	getLeeches(cache: StatsCache): LeechCard[] {
		const leeches: LeechCard[] = [];
		const concepts = Object.values(cache.concepts);

		for (const concept of concepts) {
			if (concept.problematicCards && concept.problematicCards.length > 0) {
				for (const card of concept.problematicCards) {
					// Optionally filter further? For now, we trust 'problematicCards' logic from StatsService
					// which already picks high lapses / low ease.
					leeches.push({
						...card,
						filePath: concept.filePath,
						fileName: concept.fileName,
						deck: concept.primaryDeck,
					});
				}
			}
		}

		// Sort by Lapses Descending
		return leeches.sort((a, b) => b.lapses - a.lapses);
	}

	async suspendCard(cardId: number): Promise<boolean> {
		return this.ankiRepo.suspendCards([cardId]);
	}

	async unsuspendCard(cardId: number): Promise<boolean> {
		return this.ankiRepo.unsuspendCards([cardId]);
	}
}
