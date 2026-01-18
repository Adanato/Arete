import '../../test-setup';
import { App, TFile, Notice } from 'obsidian';
import { GraphService } from '@application/services/GraphService';

describe('GraphService', () => {
	let service: GraphService;
	let app: App;
	let settings: any;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		settings = {
			graph_coloring_enabled: true,
			graph_tag_prefix: 'arete/retention',
		};
		service = new GraphService(app, settings);
	});

	test('calculateRetentionState returns correct levels', () => {
		expect(service.calculateRetentionState({ score: 0.05 } as any)).toBe('high');
		expect(service.calculateRetentionState({ score: 0.15 } as any)).toBe('med');
		expect(service.calculateRetentionState({ score: 0.25 } as any)).toBe('low');
	});

	test('updateGraphTags adds tag to frontmatter', async () => {
		const file = { path: 'test.md' } as TFile;
		const stats = { score: 0.25 } as any; // low

		(app.fileManager.processFrontMatter as jest.Mock).mockImplementation((f, cb) => {
			const fm = { tags: ['existing'] };
			cb(fm);
			expect(fm.tags).toContain('arete/retention/low');
			expect(fm.tags).not.toContain('arete/retention/high');
			expect(fm.tags).toContain('existing');
		});

		await service.updateGraphTags(file, stats);
		expect(app.fileManager.processFrontMatter).toHaveBeenCalled();
	});

	test('updateGraphTags handles string tags', async () => {
		const file = { path: 'test.md' } as TFile;
		const stats = { score: 0.05 } as any; // high

		(app.fileManager.processFrontMatter as jest.Mock).mockImplementation((f, cb) => {
			const fm = { tags: 'single-string' };
			cb(fm);
			expect(fm.tags).toEqual(['single-string', 'arete/retention/high']);
		});

		await service.updateGraphTags(file, stats);
	});

	test('updateGraphTags returns early if disabled', async () => {
		settings.graph_coloring_enabled = false;
		await service.updateGraphTags({} as any, {} as any);
		expect(app.fileManager.processFrontMatter).not.toHaveBeenCalled();
	});

	test('clearGraphTags removes prefix matching tags', async () => {
		const file = { path: 'test.md' } as TFile;

		(app.fileManager.processFrontMatter as jest.Mock).mockImplementation((f, cb) => {
			const fm = { tags: ['arete/retention/high', 'other'] };
			cb(fm);
			expect(fm.tags).toEqual(['other']);
		});

		await service.clearGraphTags(file);
	});

	test('clearGraphTags handles string tags', async () => {
		const file = { path: 'test.md' } as TFile;

		(app.fileManager.processFrontMatter as jest.Mock).mockImplementation((f, cb) => {
			const fm = { tags: 'arete/retention/high' };
			cb(fm);
			expect(fm.tags).toEqual([]);
		});

		await service.clearGraphTags(file);
	});

	test('clearAllTags iterates through vault markdown files', async () => {
		const files = [{ path: '1.md' }, { path: '2.md' }] as TFile[];
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue(files);
		service.clearGraphTags = jest.fn().mockResolvedValue(undefined);

		await service.clearAllTags();
		expect(service.clearGraphTags).toHaveBeenCalledTimes(2);
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Cleared tags from 2 files'));
	});

	test('updateSettings updates internal settings', () => {
		const newSettings = { ...settings, graph_tag_prefix: 'new/prefix' };
		service.updateSettings(newSettings);
		expect(service.settings.graph_tag_prefix).toBe('new/prefix');
	});
});
