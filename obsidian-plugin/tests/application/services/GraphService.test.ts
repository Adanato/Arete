import { GraphService } from '@/application/services/GraphService';
import { AretePluginSettings, DEFAULT_SETTINGS } from '@/domain/settings';
import { ConceptStats } from '@/application/services/StatsService';
import { App, TFile } from 'obsidian';

describe('GraphService', () => {
	let app: App;
	let settings: AretePluginSettings;
	let service: GraphService;
	let mockFile: TFile;
	let processFrontMatterMock: jest.Mock;

	beforeEach(() => {
		processFrontMatterMock = jest.fn((file, cb) => {
			const frontmatter: any = { tags: [] };
			cb(frontmatter);
			return Promise.resolve();
		});

		app = {
			fileManager: {
				processFrontMatter: processFrontMatterMock,
			},
			vault: {
				getMarkdownFiles: jest.fn().mockReturnValue([]),
			},
		} as unknown as App;

		settings = { ...DEFAULT_SETTINGS, graph_coloring_enabled: true };
		service = new GraphService(app, settings);
		mockFile = { path: 'test.md' } as TFile;
	});

	describe('calculateRetentionState', () => {
		it('should return high for good stats', () => {
			const stats = { score: 0.05 } as ConceptStats; // 5% problematic
			expect(service.calculateRetentionState(stats)).toBe('high');
		});

		it('should return med for warning stats', () => {
			const stats = { score: 0.15 } as ConceptStats; // 15% problematic
			expect(service.calculateRetentionState(stats)).toBe('med');
		});

		it('should return low for critical stats', () => {
			const stats = { score: 0.25 } as ConceptStats; // 25% problematic
			expect(service.calculateRetentionState(stats)).toBe('low');
		});
	});

	describe('updateGraphTags', () => {
		it('should add tag if enabled', async () => {
			const stats = { score: 0.25 } as ConceptStats; // Low
			await service.updateGraphTags(mockFile, stats);

			expect(processFrontMatterMock).toHaveBeenCalled();
			const cb = processFrontMatterMock.mock.calls[0][1];
			const fm: { tags: string[] } = { tags: [] };
			cb(fm);
			expect(fm.tags).toContain('arete/retention/low');
		});

		it('should not add tag if disabled', async () => {
			service.settings.graph_coloring_enabled = false;
			const stats = { score: 0.25 } as ConceptStats;
			await service.updateGraphTags(mockFile, stats);

			expect(processFrontMatterMock).not.toHaveBeenCalled();
		});

		it('should replace existing retention tags', async () => {
			const stats = { score: 0.05 } as ConceptStats; // High
			
			// Mock existing frontmatter with 'low' tag
			processFrontMatterMock.mockImplementation((file, cb) => {
				const fm = { tags: ['arete/retention/low', 'other/tag'] };
				cb(fm);
				// Verify inside callback result
				expect(fm.tags).not.toContain('arete/retention/low');
				expect(fm.tags).toContain('arete/retention/high');
				expect(fm.tags).toContain('other/tag');
				return Promise.resolve();
			});

			await service.updateGraphTags(mockFile, stats);
		});
	});

	describe('clearGraphTags', () => {
		it('should remove all retention tags', async () => {
			processFrontMatterMock.mockImplementation((file, cb) => {
				const fm = { tags: ['arete/retention/low', 'keep-me'] };
				cb(fm);
				expect(fm.tags).toEqual(['keep-me']);
				return Promise.resolve();
			});

			await service.clearGraphTags(mockFile);
		});
	});
});
