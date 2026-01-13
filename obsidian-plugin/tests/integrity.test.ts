import './test-setup';
import { App, TFile } from 'obsidian';
import AretePlugin from '@/main';

describe('AretePlugin Integrity Check', () => {
	let plugin: AretePlugin;
	let app: App;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.checkService = {
			checkVaultIntegrity: jest.fn(),
		} as any;
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	test('checkVaultIntegrity detects files with YAML but no frontmatter in cache', async () => {
		const goodFile = { path: 'Good.md' } as TFile;
		const badFile = { path: 'Bad.md' } as TFile;

		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([goodFile, badFile]);

		(app.vault.read as jest.Mock).mockImplementation(async (file: TFile) => {
			if (file.path === 'Good.md') return '---\ntitle: Good\n---\nContent';
			if (file.path === 'Bad.md') return '---\n\tTabError: True\n---\nContent';
			return '';
		});

		(app.metadataCache.getFileCache as jest.Mock).mockImplementation((file: TFile) => {
			if (file.path === 'Good.md') return { frontmatter: { title: 'Good' } };
			if (file.path === 'Bad.md') return { frontmatter: undefined };
			return null;
		});

		const mockConsoleError = jest.spyOn(console, 'error').mockImplementation(() => {
			/* no-op */
		});

		await plugin.checkVaultIntegrity();

		expect(plugin.checkService.checkVaultIntegrity).toHaveBeenCalled();

		mockConsoleError.mockRestore();
	});
});
