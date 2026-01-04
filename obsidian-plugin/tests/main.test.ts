import './test-setup';
import { App } from 'obsidian';
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

	test('runSync with Debug Mode enabled adds --verbose', async () => {
		plugin.settings.debugMode = true;
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'o2a', '--verbose', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.any(Object),
		);
	});
});
