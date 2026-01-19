import { AreteClient } from '@/infrastructure/arete/AreteClient';
import { requestUrl, RequestUrlParam } from 'obsidian';

jest.mock('obsidian', () => ({
	requestUrl: jest.fn(),
	Notice: jest.fn(),
}));

describe('AreteClient', () => {
	let client: AreteClient;
	const mockRequestUrl = requestUrl as unknown as jest.Mock;

	beforeEach(() => {
		client = new AreteClient({
			anki_connect_execution_path: '',
			anki_connect_url: 'http://localhost:8765',
			backend: 'direct',
			execution_mode: 'server',
			server_port: 8000,
			template_root: '',
			vault_root: '',
			obsidian_api_key: 'test',
		} as any);
		(client as any).url = 'http://localhost:8000';
		mockRequestUrl.mockReset();
	});

	describe('getDeckNames', () => {
		it('should return deck names on success', async () => {
			mockRequestUrl.mockResolvedValue({
				status: 200,
				json: { decks: ['Deck A', 'Deck B'] },
			});

			const decks = await client.getDeckNames();
			expect(decks).toEqual(['Deck A', 'Deck B']);
			expect(mockRequestUrl).toHaveBeenCalledWith(
				expect.objectContaining({
					url: 'http://127.0.0.1:8000/anki/decks',
					method: 'POST',
				}),
			);
		});

		it('should return empty list on failure', async () => {
			mockRequestUrl.mockRejectedValue(new Error('Network Error'));
			const decks = await client.getDeckNames();
			expect(decks).toEqual([]);
		});
	});

	describe('buildStudyQueue', () => {
		it('should returns queue result on success', async () => {
			const mockServerResponse = {
				deck: 'Target',
				due_count: 5,
				total_with_prereqs: 7,
				queue: [
					{ position: 1, id: 'A', title: 'Card A', file: 'a.md', is_prereq: true },
					{ position: 2, id: 'B', title: 'Card B', file: 'b.md', is_prereq: false },
				],
			};

			const expectedResult = {
				deck: 'Target',
				dueCount: 5,
				totalWithPrereqs: 7,
				queue: [
					{ position: 1, id: 'A', title: 'Card A', file: 'a.md', isPrereq: true },
					{ position: 2, id: 'B', title: 'Card B', file: 'b.md', isPrereq: false },
				],
			};

			mockRequestUrl.mockResolvedValue({
				status: 200,
				json: mockServerResponse,
			});

			const result = await client.buildStudyQueue('Target', 3, 20);
			expect(result).toEqual(expectedResult);
			expect(mockRequestUrl).toHaveBeenCalledWith(
				expect.objectContaining({
					url: 'http://127.0.0.1:8000/queue/build',
					method: 'POST',
					body: JSON.stringify({
						deck: 'Target',
						depth: 3,
						max_cards: 20,
						backend: 'direct',
						anki_connect_url: 'http://localhost:8765',
					}),
				}),
			);
		});

		it('should return null on failure', async () => {
			mockRequestUrl.mockRejectedValue(new Error('Build failed'));
			// buildStudyQueue throws on server error (invokeServer throws), so we expect it to throw
			await expect(client.buildStudyQueue(null, 2, 50)).rejects.toThrow('Build failed');
		});
	});

	describe('createQueueDeck', () => {
		it('should return true on success', async () => {
			mockRequestUrl.mockResolvedValue({
				status: 200,
				json: { ok: true },
			});

			const result = await client.createQueueDeck(['A', 'B']);
			expect(result).toBe(true);
			expect(mockRequestUrl).toHaveBeenCalledWith(
				expect.objectContaining({
					url: 'http://127.0.0.1:8000/queue/create-deck',
					method: 'POST',
					body: JSON.stringify({
						card_ids: ['A', 'B'],
						backend: 'direct',
						anki_connect_url: 'http://localhost:8765',
					}),
				}),
			);
		});

		it('should return false on failure', async () => {
			mockRequestUrl.mockRejectedValue(new Error('Create failed'));
			const result = await client.createQueueDeck([]);
			expect(result).toBe(false);
		});
	});
});
