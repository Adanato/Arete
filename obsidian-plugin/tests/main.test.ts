import { App, Plugin } from 'obsidian';
import O2APlugin from '../main';
import { spawn } from 'child_process';
import { EventEmitter } from 'events';

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

// Mock child_process
jest.mock('child_process');

describe('O2APlugin', () => {
	let plugin: O2APlugin;
	let app: App;

	beforeEach(() => {
		app = new App();
		// Mock Vault & Adapter
		app.vault = {
			adapter: {
				getBasePath: jest.fn().mockReturnValue('/mock/vault/path'),
			},
		} as any;
		plugin = new O2APlugin(app, {} as any);
		(plugin as any).app = app; // Fix: Mock Plugin doesn't assign app
		// Helper to mock addStatusBarItem since it's used in runSync now
		plugin.addStatusBarItem = jest.fn().mockReturnValue({
			setText: jest.fn(),
			empty: jest.fn(),
			createSpan: jest.fn(),
			title: '',
		});
		plugin.statusBarItem = plugin.addStatusBarItem();

		// Initialize manifest for logging setup
		(plugin as any).manifest = { dir: 'test-plugin-dir' };

		plugin.settings = {
			pythonPath: 'python3',
			o2aScriptPath: '',
			debugMode: false,
			backend: 'auto',
			workers: 4,
		};
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	test('runSync spawns python process with correct arguments', async () => {
		const result = new EventEmitter();
		(result as any).stdout = new EventEmitter();
		(result as any).stderr = new EventEmitter();
		(spawn as jest.Mock).mockReturnValue(result);

		await plugin.runSync();

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({ cwd: '/mock/vault/path' }),
		);
	});

	test('runSync with prune flag spawns process with --prune', async () => {
		const result = new EventEmitter();
		(result as any).stdout = new EventEmitter();
		(result as any).stderr = new EventEmitter();
		(spawn as jest.Mock).mockReturnValue(result);

		await plugin.runSync(true);

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--prune', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({ cwd: '/mock/vault/path' }),
		);
	});

	test('runSync with force flag (Sync Current Note) spawns process with --force', async () => {
		const result = new EventEmitter();
		(result as any).stdout = new EventEmitter();
		(result as any).stderr = new EventEmitter();
		(spawn as jest.Mock).mockReturnValue(result);

		// runSync(prune, targetPath, force)
		await plugin.runSync(false, '/mock/vault/path/Note.md', true);

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			// Note: --force is added, and target path is specific file
			['-m', 'o2a', 'sync', '--force', '--workers', '4', '/mock/vault/path/Note.md'],
			expect.objectContaining({ cwd: '/mock/vault/path' }),
		);
	});

	test('runSync with Debug Mode enabled adds --verbose', async () => {
		plugin.settings.debugMode = true;

		const result = new EventEmitter();
		(result as any).stdout = new EventEmitter();
		(result as any).stderr = new EventEmitter();
		(spawn as jest.Mock).mockReturnValue(result);

		await plugin.runSync();

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--verbose', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({ cwd: '/mock/vault/path' }),
		);
	});

	test('runSync with custom python path and script path', async () => {
		plugin.settings.pythonPath = '/usr/bin/python3';
		plugin.settings.o2aScriptPath = '/path/to/o2a/main.py';

		const result = new EventEmitter();
		(result as any).stdout = new EventEmitter();
		(result as any).stderr = new EventEmitter();
		(spawn as jest.Mock).mockReturnValue(result);

		await plugin.runSync();

		expect(spawn).toHaveBeenCalledWith(
			'/usr/bin/python3',
			['-m', 'o2a', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({
				cwd: '/mock/vault/path',
				env: expect.objectContaining({
					PYTHONPATH: '/path/to', // /path/to/o2a/main.py -> dir: /path/to/o2a -> root: /path/to
				}),
			}),
		);
	});
});
