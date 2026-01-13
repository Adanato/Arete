import '../../test-setup';
import { App } from 'obsidian';
import { StatsService } from '@application/services/StatsService';
import { AretePluginSettings } from '@domain/settings';
import { requestUrl } from 'obsidian';

// Mock requestUrl
jest.mock('obsidian', () => {
	return {
		...jest.requireActual('obsidian'),
		requestUrl: jest.fn(),
		Notice: jest.fn(),
	};
});

describe('StatsService Integration', () => {
	let app: App;
	let settings: AretePluginSettings;
	let service: StatsService;

	beforeEach(() => {
		app = new App();
		settings = {
			python_path: 'python3',
			backend: 'auto',
			anki_connect_url: 'http://localhost:8765',
			stats_algorithm: 'fsrs', // Test FSRS path
			stats_lapse_threshold: 3,
			stats_ease_threshold: 2100,
			stats_difficulty_threshold: 0.9,
		} as any;
		service = new StatsService(app, settings);
		(requestUrl as jest.Mock).mockClear();
	});

	test('fetchAnkiCardStats calls getFSRSStats and merges difficulty', async () => {
		const nids = [101, 102];

		// Mock 1: findCards
		(requestUrl as jest.Mock).mockResolvedValueOnce({
			json: { result: [1, 2] },
		});

		// Mock 2: cardsInfo (Standard Stats)
		(requestUrl as jest.Mock).mockResolvedValueOnce({
			json: {
				result: [
					{
						cardId: 1,
						note: 101,
						lapses: 0,
						factor: 0,
						interval: 10,
						due: 0,
						reps: 5,
						deckName: 'Deck A',
						difficulty: 0,
					}, // difficulty 0 ignored if FSRS fetched
					{
						cardId: 2,
						note: 102,
						lapses: 0,
						factor: 0,
						interval: 10,
						due: 0,
						reps: 5,
						deckName: 'Deck A',
						difficulty: 0,
					},
				],
			},
		});

		// Mock 3: getFSRSStats (Custom Action)
		(requestUrl as jest.Mock).mockResolvedValueOnce({
			json: {
				result: [
					{ cardId: 1, difficulty: 8.5 }, // 8.5 / 10 = 0.85
					{ cardId: 2, difficulty: 3.0 }, // 3.0 / 10 = 0.30
				],
			},
		});

		const stats = await service.fetchAnkiCardStats(nids);

		expect(stats.length).toBe(2);

		// Verify Card 1
		expect(stats[0].cardId).toBe(1);
		expect(stats[0].difficulty).toBe(0.85); // Normalized

		// Verify Card 2
		expect(stats[1].cardId).toBe(2);
		expect(stats[1].difficulty).toBe(0.3); // Normalized

		// Verify calls
		expect(requestUrl).toHaveBeenCalledTimes(3);
		const fsrsCall = (requestUrl as jest.Mock).mock.calls[2][0];
		expect(JSON.parse(fsrsCall.body).action).toBe('getFSRSStats');
	});

	test('fetchAnkiCardStats handles missing FSRS data gracefully', async () => {
		const nids = [101];

		// Mock 1: findCards
		(requestUrl as jest.Mock).mockResolvedValueOnce({
			json: { result: [1] },
		});

		// Mock 2: cardsInfo (Standard Stats)
		(requestUrl as jest.Mock).mockResolvedValueOnce({
			json: {
				result: [
					{
						cardId: 1,
						note: 101,
						lapses: 0,
						factor: 0,
						interval: 10,
						due: 0,
						reps: 5,
						deckName: 'Deck A',
						difficulty: 0.5,
					}, // Info fallback
				],
			},
		});

		// Mock 3: getFSRSStats (Fails or null)
		(requestUrl as jest.Mock).mockRejectedValueOnce(new Error('Action not found'));

		const stats = await service.fetchAnkiCardStats(nids);

		expect(stats.length).toBe(1);
		expect(stats[0].difficulty).toBe(0.5); // Fallback to info.difficulty
	});
});
