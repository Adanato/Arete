import '../../test-setup';
import { App, TFile } from 'obsidian';
import { StatsService, AnkiCardStats } from '@application/services/StatsService';
import { AretePluginSettings } from '@domain/settings';

describe('StatsService', () => {
	let app: App;
	let settings: AretePluginSettings;
	let service: StatsService;

	beforeEach(() => {
		app = new App();
		// Mock vault and metadata cache
		app.vault.getMarkdownFiles = jest.fn().mockReturnValue([]);
		app.metadataCache.getFileCache = jest.fn().mockReturnValue({});
		
		settings = {
			python_path: 'python3',
			backend: 'auto',
			anki_connect_url: 'http://localhost:8765',
			stats_algorithm: 'sm2',
			stats_lapse_threshold: 3,
			stats_ease_threshold: 2100,
			stats_difficulty_threshold: 0.9,
		} as any;

		service = new StatsService(app, settings);
	});

	test('refreshStats aggregates cards correctly by file and prioritizes YAML deck', async () => {
		// 1. Mock Vault Files
		const file1 = { path: 'concept1.md', basename: 'Concept 1' } as TFile;
		const file2 = { path: 'concept2.md', basename: 'Concept 2' } as TFile;
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([file1, file2]);

		// 2. Mock Metadata Cache (Cards in frontmatter)
		(app.metadataCache.getFileCache as jest.Mock).mockImplementation((f) => {
			if (f.path === 'concept1.md') {
				return {
					frontmatter: {
						deck: 'YAML Deck', // Should override Anki
						cards: [
							{ nid: '101', front: 'C1 Card 1' },
							{ nid: '102', front: 'C1 Card 2' },
						]
					}
				};
			}
			if (f.path === 'concept2.md') {
				return {
					frontmatter: {
						// No deck in YAML
						cards: [
							{ nid: '201', front: 'C2 Card 1' },
						]
					}
				};
			}
			return {};
		});

		// 3. Mock Anki Fetch (Mocking the network call)
		const mockAnkiStats: AnkiCardStats[] = [
			{ noteId: 101, cardId: 1, lapses: 5, ease: 1500, interval: 1, due: 0, reps: 10, averageTime: 5000, deckName: 'Anki Deck A' },
			{ noteId: 102, cardId: 2, lapses: 0, ease: 2500, interval: 10, due: 0, reps: 2, averageTime: 4000, deckName: 'Anki Deck A' },
			{ noteId: 201, cardId: 3, lapses: 0, ease: 2300, interval: 5, due: 0, reps: 3, averageTime: 6000, deckName: 'Anki Deck B' },
		];
		
		service.fetchAnkiCardStats = jest.fn().mockResolvedValue(mockAnkiStats);

		// 4. Run Refresh
		const stats = await service.refreshStats();

		// 5. Verify Results
		expect(stats.length).toBe(2);
		
		// Concept 1 (Has YAML Deck)
		const c1 = stats.find(s => s.filePath === 'concept1.md');
		expect(c1).toBeDefined();
		expect(c1?.primaryDeck).toBe('YAML Deck'); // Should be from YAML
		expect(c1?.totalCards).toBe(2);
		expect(c1?.problematicCardsCount).toBe(1);

		// Concept 2 (No YAML Deck)
		const c2 = stats.find(s => s.filePath === 'concept2.md');
		expect(c2).toBeDefined();
		expect(c2?.primaryDeck).toBe('Anki Deck B'); // Should be from Anki
		expect(c2?.totalCards).toBe(1);
	});

	test('handles files with no linked cards gracefully', async () => {
		const file1 = { path: 'empty.md', basename: 'Empty' } as TFile;
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([file1]);
		(app.metadataCache.getFileCache as jest.Mock).mockReturnValue({});

		const stats = await service.refreshStats();
		expect(stats.length).toBe(0);
	});
});
