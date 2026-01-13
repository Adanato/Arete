import '../../test-setup';
import { App, Notice } from 'obsidian';
import { spawn } from 'child_process';
import { createMockChildProcess } from '../../test-setup';
import { SyncService } from '@application/services/SyncService';
import { AretePluginSettings } from '@domain/settings';

describe('SyncService', () => {
	let service: SyncService;
	let app: App;
	let settings: AretePluginSettings;
	let updateStatusBar: jest.Mock;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue('/mock/vault/path');

		settings = {
			pythonPath: 'python3',
			areteScriptPath: '',
			debugMode: false,
			backend: 'auto',
			workers: 4,
			ankiConnectUrl: 'http://localhost:8765',
			ankiMediaDir: '',
			rendererMode: 'obsidian',
		};

		updateStatusBar = jest.fn();

		service = new SyncService(app, settings, { dir: 'test-plugin-dir' });
	});

	test('runSync for a specific file', async () => {
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = service.runSync(false, '/mock/path/file.md', true, updateStatusBar);
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'arete', 'sync', '--force', '--workers', '4', '/mock/path/file.md'],
			expect.any(Object),
		);
		expect(updateStatusBar).toHaveBeenCalledWith('syncing');
		expect(updateStatusBar).toHaveBeenCalledWith('success');
	});

	test('runSync with all flags and custom settings', async () => {
		service.settings.ankiConnectUrl = 'http://anki:8765';
		service.settings.ankiMediaDir = '/anki/media';
		service.settings.backend = 'apy';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = service.runSync(true, null, true, updateStatusBar);
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
		service.settings.areteScriptPath = '/path/to/o2a/main.py';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = service.runSync(false, null, false, updateStatusBar);
		mockChild.emit('close', 0);
		await syncPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'arete', 'sync', '--workers', '4', '/mock/vault/path'],
			expect.objectContaining({
				env: expect.objectContaining({ PYTHONPATH: '/path/to' }),
			}),
		);
	});

	test('runSync with custom binary script path', async () => {
		service.settings.areteScriptPath = '/usr/local/bin/o2a-custom';
		service.settings.debugMode = true;
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const syncPromise = service.runSync(false, null, false, updateStatusBar);
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
