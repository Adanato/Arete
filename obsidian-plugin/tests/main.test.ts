import './test-setup';
import { App, Notice } from 'obsidian';
import O2APlugin from '../main';
import { spawn } from 'child_process';
import { createMockChildProcess } from './test-setup';

describe('O2APlugin', () => {
	let plugin: O2APlugin;
	let app: App;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue('/mock/vault/path');

		plugin = new O2APlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.statusBarItem = plugin.addStatusBarItem() as any;

		plugin.settings = {
			pythonPath: 'python3',
			o2aScriptPath: '',
			debugMode: false,
			backend: 'auto',
			workers: 4,
			ankiConnectUrl: 'http://localhost:8765',
			ankiMediaDir: '',
		};
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	test('loadSettings and saveSettings flow', async () => {
		(plugin as any).loadData = jest.fn().mockResolvedValue({ pythonPath: 'custom-python' });
		(plugin as any).saveData = jest.fn().mockResolvedValue(undefined);

		await plugin.loadSettings();
		expect(plugin.settings.pythonPath).toBe('custom-python');

		plugin.settings.debugMode = true;
		await plugin.saveSettings();
		expect((plugin as any).saveData.mock.calls[0][0].debugMode).toBe(true);
	});

	test('runSync for a specific file', async () => {
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync(false, '/mock/path/file.md', true);
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--force', '--workers', '4', '/mock/path/file.md'],
			expect.any(Object),
		);
	});

	test('runSync with all flags and custom settings', async () => {
		plugin.settings.ankiConnectUrl = 'http://anki:8765';
		plugin.settings.ankiMediaDir = '/anki/media';
		plugin.settings.backend = 'apy';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync(true, null, true);
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			expect.arrayContaining([
				'--prune',
				'--force',
				'--backend',
				'apy',
				'--anki-connect-url',
				'http://anki:8765',
				'--anki-media-dir',
				'/anki/media',
			]),
			expect.any(Object),
		);
	});

	test('runSync with .py script path', async () => {
		plugin.settings.o2aScriptPath = '/path/to/o2a/main.py';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({
				env: expect.objectContaining({ PYTHONPATH: '/path/to' }),
			}),
		);
	});

	test('runCheck calls o2a check-file', async () => {
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const checkPromise = plugin.runCheck('/mock/path/file.md');
		mockChild.emit('close', 0);
		await checkPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'check-file', '/mock/path/file.md', '--json'],
			expect.any(Object),
		);
	});

	test('runCheck with .py script path', async () => {
		plugin.settings.o2aScriptPath = '/path/to/o2a/main.py';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const checkPromise = plugin.runCheck('/mock/path/file.md');
		mockChild.emit('close', 0);
		await checkPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'check-file', '/mock/path/file.md', '--json'],
			expect.objectContaining({
				env: expect.objectContaining({ PYTHONPATH: '/path/to' }),
			}),
		);
	});

	test('commands are registered and callback triggers runSync/runCheck', async () => {
		await plugin.onload();
		const commands = (global as any).registeredCommands;
		expect(commands['o2a-sync']).toBeDefined();
		expect(commands['o2a-check-file']).toBeDefined();
		expect(commands['o2a-check-integrity']).toBeDefined();
		expect(commands['o2a-sync-current-file']).toBeDefined();
		expect(commands['o2a-sync-prune']).toBeDefined();

		// Test o2a-sync command
		plugin.runSync = jest.fn().mockResolvedValue(undefined);
		commands['o2a-sync'].callback();
		expect(plugin.runSync).toHaveBeenCalled();

		// Test o2a-check-file command
		const mockView = {
			file: { path: 'test.md' },
		};
		plugin.runCheck = jest.fn().mockResolvedValue(undefined);
		commands['o2a-check-file'].editorCallback(null, mockView);
		expect(plugin.runCheck).toHaveBeenCalled();

		// Test o2a-sync-prune
		commands['o2a-sync-prune'].callback();
		expect(plugin.runSync).toHaveBeenCalledWith(true);
	});

	test('runSync spawns python process with correct arguments', async () => {
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({ cwd: '/mock/vault/path' }),
		);
	});

	test('sync current file command', async () => {
		await plugin.onload();
		const commands = (global as any).registeredCommands;
		(app.workspace.getActiveFile as jest.Mock).mockReturnValue({ path: 'test.md' });
		plugin.runSync = jest.fn().mockResolvedValue(undefined);

		await commands['o2a-sync-current-file'].callback();
		expect(plugin.runSync).toHaveBeenCalledWith(
			false,
			expect.stringContaining('test.md'),
			true,
		);
	});

	test('sync current file command error paths', async () => {
		await plugin.onload();
		const commands = (global as any).registeredCommands;

		// 1. No active file
		(app.workspace.getActiveFile as jest.Mock).mockReturnValue(null);
		await commands['o2a-sync-current-file'].callback();
		expect(Notice).toHaveBeenCalledWith('No active file to sync.');

		// 2. No base path
		(app.workspace.getActiveFile as jest.Mock).mockReturnValue({ path: 'test.md' });
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue(null);
		await commands['o2a-sync-current-file'].callback();
		expect(Notice).toHaveBeenCalledWith('Error: Cannot resolve file path.');
	});

	test('check vault integrity command', async () => {
		await plugin.onload();
		const commands = (global as any).registeredCommands;
		plugin.checkVaultIntegrity = jest.fn();

		commands['o2a-check-integrity'].callback();
		expect(plugin.checkVaultIntegrity).toHaveBeenCalled();
	});

	test('runSync with custom binary script path', async () => {
		plugin.settings.o2aScriptPath = '/usr/local/bin/o2a-custom';
		plugin.settings.debugMode = true;
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			[
				'/usr/local/bin/o2a-custom',
				'--verbose',
				'sync',
				'--workers',
				'4',
				'/mock/vault/path',
			],
			expect.any(Object),
		);
	});
});
