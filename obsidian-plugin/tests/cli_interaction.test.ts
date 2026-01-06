import './test-setup';
import { App, Notice } from 'obsidian';
import AretePlugin from '../main';
import { spawn } from 'child_process';
import { createMockChildProcess } from './test-setup';

describe('AretePlugin CLI Interaction', () => {
	let plugin: AretePlugin;
	let app: App;
	let mockChild: any;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue('/mock/vault/path');
		(app.vault as any).getMarkdownFiles = jest.fn().mockReturnValue([]);

		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.statusBarItem = plugin.addStatusBarItem() as any;

		plugin.settings = {
			pythonPath: 'python3',
			areteScriptPath: 'o2a/main.py',
			debugMode: false,
			backend: 'auto',
			workers: 4,
			ankiConnectUrl: 'http://localhost:8765',
			ankiMediaDir: '',
		};

		mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	test('runSync logs stdout output', async () => {
		const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {
			/* no-op */
		});
		const syncPromise = plugin.runSync();
		mockChild.stdout.emit('data', Buffer.from('Processing note 1\n'));
		mockChild.emit('close', 0);
		await syncPromise;
		expect(consoleSpy).toHaveBeenCalledWith(
			expect.stringContaining('STDOUT: Processing note 1'),
		);
		consoleSpy.mockRestore();
	});

	test('runSync handles successful completion', async () => {
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('completed successfully'));
	});

	test('checkVaultIntegrity success flow', async () => {
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([]);
		await plugin.checkVaultIntegrity();
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Integrity Check Passed'));
	});

	test('checkVaultIntegrity issues flow', async () => {
		const mockFile = { path: 'test.md' };
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([mockFile]);
		(app.metadataCache.getFileCache as jest.Mock).mockReturnValue({
			frontmatter: null,
			sections: [{ type: 'yaml' }],
		});
		(app.vault.read as jest.Mock).mockResolvedValue('---\ntest: true\n---\ncontent');
		await plugin.checkVaultIntegrity();
		expect(Notice).toHaveBeenCalledWith(
			expect.stringContaining('Found 1 files with Invalid Properties'),
		);
	});

	test('runCheck handles spawn error', async () => {
		const checkPromise = plugin.runCheck('/path/to/file.md');
		mockChild.emit('error', new Error('spawn error'));
		await checkPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Error: spawn error'));
	});

	test('runSync with specific backend', async () => {
		plugin.settings.backend = 'apy';
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['sync', '--backend', 'apy']),
			expect.any(Object),
		);
	});

	test('runSync with workers count', async () => {
		plugin.settings.workers = 8;
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['--workers', '8']),
			expect.any(Object),
		);
	});

	test('runSync handles general failure', async () => {
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 1);
		await syncPromise;
		expect(Notice).toHaveBeenCalledWith('arete sync failed! (Code 1). See log.');
	});

	test('runSync handles Anki not reachable', async () => {
		const syncPromise = plugin.runSync();
		mockChild.stderr.emit('data', 'Connection refused: AnkiConnect');
		mockChild.emit('close', 1);
		await syncPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Anki is not reachable'));
	});

	test('runSync handles missing dependencies', async () => {
		const syncPromise = plugin.runSync();
		mockChild.stderr.emit('data', 'ModuleNotFoundError: No module named typer');
		mockChild.emit('close', 1);
		await syncPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Dependencies missing'));
	});

	test('runSync with .py script path set', async () => {
		plugin.settings.areteScriptPath = '/path/to/script.py';
		plugin.settings.debugMode = true; // Cover debug flag too
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['-m', 'arete', '--verbose']),
			expect.objectContaining({ env: expect.objectContaining({ PYTHONPATH: '/path' }) }),
		);
	});

	test('runSync handles generic module error', async () => {
		const syncPromise = plugin.runSync();
		mockChild.stderr.emit('data', 'No module named o2a');
		mockChild.emit('close', 1);
		await syncPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Invalid Python environment'));
	});

	test('runSync handles no vault path', async () => {
		(app.vault.adapter as any).getBasePath = undefined;
		await plugin.runSync();
		expect(Notice).toHaveBeenCalledWith('Error: Cannot determine vault path.');
	});

	test('runSync logs stdout/stderr', async () => {
		const syncPromise = plugin.runSync();
		mockChild.stdout.emit('data', 'Sync progress 50%');
		mockChild.stderr.emit('data', 'Some warning');
		mockChild.emit('close', 0);
		await syncPromise;
		// No specific assertion needed, just exercising the code paths
	});

	test('runCheck handles success', async () => {
		const checkPromise = plugin.runCheck('/path/to/file.md');
		mockChild.stdout.emit(
			'data',
			JSON.stringify({ ok: true, stats: { deck: 'Default', cards_found: 2 } }),
		);
		mockChild.emit('close', 0);
		await checkPromise;
		// Helper mock from test-setup should handle creating modal
	});

	test('runCheck handles invalid JSON', async () => {
		const checkPromise = plugin.runCheck('/path/to/file.md');
		mockChild.stdout.emit('data', 'Invalid JSON Output');
		mockChild.emit('close', 0);
		await checkPromise;
		expect(Notice).toHaveBeenCalledWith('Check failed. See console.');
	});

	test('runCheck with .py script path set', async () => {
		plugin.settings.areteScriptPath = '/path/to/script.py';
		const checkPromise = plugin.runCheck('/path/to/file.md');
		mockChild.emit('close', 0);
		await checkPromise;
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['-m', 'arete', 'check-file']),
			expect.objectContaining({ env: expect.objectContaining({ PYTHONPATH: '/path' }) }),
		);
	});

	test('testConfig success', async () => {
		const testPromise = plugin.testConfig();
		mockChild.emit('close', 0);
		await testPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Python found'));
	});

	test('testConfig failure', async () => {
		const testPromise = plugin.testConfig();
		mockChild.emit('close', 1);
		await testPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Python command failed'));
	});

	test('testConfig spawn error', async () => {
		const testPromise = plugin.testConfig();
		mockChild.emit('error', new Error('ENOENT'));
		await testPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Invalid Python Path'));
	});

	test('runFix success with .py script', async () => {
		plugin.settings.areteScriptPath = '/path/to/script.py';
		const fixPromise = plugin.runFix('/path/to/file.md');
		mockChild.emit('close', 0);
		await fixPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('auto-fixed'));
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['-m', 'arete', 'fix-file', '/path/to/file.md']),
			expect.objectContaining({
				env: expect.objectContaining({ PYTHONPATH: expect.any(String) }),
			}),
		);
	});

	test('runFix failure', async () => {
		const fixPromise = plugin.runFix('/path/to/file.md');
		mockChild.emit('close', 1);
		await fixPromise;
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Fix failed'));
	});

	test('runFix success with module execution', async () => {
		plugin.settings.areteScriptPath = 'python'; // Not ending in .py
		const fixPromise = plugin.runFix('/path/to/file.md');
		mockChild.emit('close', 0);
		await fixPromise;
		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['-m', 'arete', 'fix-file', '/path/to/file.md']),
			expect.any(Object),
		);
	});

	test('testConfig handles synchronous error', async () => {
		// Mock spawn to throw immediately to hit the catch block in testConfig
		(spawn as jest.Mock).mockImplementation(() => {
			throw new Error('Sync spawn error');
		});
		await plugin.testConfig();
		expect(Notice).toHaveBeenCalledWith(expect.stringContaining('Error: Sync spawn error'));
	});

	test('runSync with custom binary script (non-py)', async () => {
		// e.g. compiled binary or internal command
		plugin.settings.areteScriptPath = '/usr/local/bin/arete-custom';
		plugin.settings.debugMode = true; // hit debug branch too
		const syncPromise = plugin.runSync();
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			expect.any(String),
			expect.arrayContaining(['/usr/local/bin/arete-custom', '--verbose', 'sync']), // args pushed in specific order
			expect.any(Object),
		);
	});

	test('runSync handles synchronous spawn exception', async () => {
		(spawn as jest.Mock).mockImplementation(() => {
			throw new Error('Sync spawn immediate failure');
		});
		await plugin.runSync();
		expect(Notice).toHaveBeenCalledWith(
			expect.stringContaining('Exception: Sync spawn immediate failure'),
		);
	});
});
