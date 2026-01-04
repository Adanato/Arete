import { App, Plugin, TFile } from 'obsidian';
import O2APlugin from '../main';

// Mock obsidian module
jest.mock('obsidian', () => ({
	App: jest.fn(),
	Plugin: class {},
	PluginSettingTab: class {},
	Setting: class {
		setName() {
			return this;
		}
		setDesc() {
			return this;
		}
		addText() {
			return this;
		}
		addButton() {
			return this;
		}
	},
	Notice: jest.fn(),
	Modal: class {
		/* eslint-disable @typescript-eslint/no-empty-function */
		constructor() {}
		open() {}
		close() {}
		/* eslint-enable @typescript-eslint/no-empty-function */
	},
	FileSystemAdapter: class {},
}));

// Mock child_process and console
jest.mock('child_process');
const mockConsoleWarn = jest.spyOn(console, 'warn').mockImplementation(() => undefined);
const mockConsoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
const mockConsoleLog = jest.spyOn(console, 'log').mockImplementation(() => undefined);

describe('O2APlugin Integrity Check', () => {
	let plugin: O2APlugin;
	let app: App;

	beforeEach(() => {
		app = new App();

		// Mock Vault
		app.vault = {
			getMarkdownFiles: jest.fn(),
			read: jest.fn(),
		} as any;

		// Mock MetadataCache
		app.metadataCache = {
			getFileCache: jest.fn(),
		} as any;

		plugin = new O2APlugin(app, {} as any);
		// Manually assign app since our mock Plugin class doesn't do it
		(plugin as any).app = app;

		// Mock UI notices
		(plugin as any).Notice = jest.fn();
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	test('checkVaultIntegrity detects files with YAML but no frontmatter in cache', async () => {
		// Setup Files
		const goodFile = { path: 'Good.md' } as TFile;
		const badFile = { path: 'Bad.md' } as TFile;
		const noYamlFile = { path: 'NoYaml.md' } as TFile;

		// Mock getMarkdownFiles
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([goodFile, badFile, noYamlFile]);

		// Mock read content
		(app.vault.read as jest.Mock).mockImplementation(async (file: TFile) => {
			if (file.path === 'Good.md') return '---\ntitle: Good\n---\nContent';
			if (file.path === 'Bad.md') return '---\n\tTabError: True\n---\nContent'; // Invalid property
			if (file.path === 'NoYaml.md') return '# Just Content';
			return '';
		});

		// Mock getFileCache
		(app.metadataCache.getFileCache as jest.Mock).mockImplementation((file: TFile) => {
			if (file.path === 'Good.md') return { frontmatter: { title: 'Good' } };
			if (file.path === 'Bad.md') return { frontmatter: undefined }; // Simulate parsing failure
			if (file.path === 'NoYaml.md') return {};
			return null;
		});

		// Run Check
		await plugin.checkVaultIntegrity();

		// Assertions
		// Good file: Should pass (no warning)
		expect(mockConsoleError).not.toHaveBeenCalledWith(expect.stringContaining('Good.md'));

		// Bad file: Should FAIL (warning logged)
		expect(mockConsoleError).toHaveBeenCalledWith(expect.stringContaining('Bad.md'));
		expect(mockConsoleError).toHaveBeenCalledWith(
			expect.stringContaining('Obsidian Cache has no frontmatter'),
		);

		// NoYaml file: Should pass (skipped)
		expect(mockConsoleError).not.toHaveBeenCalledWith(expect.stringContaining('NoYaml.md'));
	});
});
