import './test-setup';
import { App, TFile } from 'obsidian';
import O2APlugin from '../main';

describe('O2APlugin Integrity Check', () => {
	let plugin: O2APlugin;
	let app: App;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		plugin = new O2APlugin(app, { dir: 'test-plugin-dir' } as any);
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

		expect(mockConsoleError).toHaveBeenCalledWith(expect.stringContaining('Bad.md'));
		expect(mockConsoleError).not.toHaveBeenCalledWith(expect.stringContaining('Good.md'));

		mockConsoleError.mockRestore();
	});
});
