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
			python_path: 'python3',
			arete_script_path: '',
			debug_mode: false,
			backend: 'auto',
			workers: 4,
			anki_connect_url: 'http://localhost:8765',
			anki_media_dir: '',
			renderer_mode: 'obsidian',
			stats_algorithm: 'sm2',
			stats_lapse_threshold: 3,
			stats_ease_threshold: 2100,
			stats_difficulty_threshold: 0.9,
			ui_expanded_decks: [],
			ui_expanded_concepts: [],
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
		service.settings.anki_connect_url = 'http://anki:8765';
		service.settings.anki_media_dir = '/anki/media';
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
		service.settings.arete_script_path = '/path/to/o2a/main.py';
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
		service.settings.arete_script_path = '/usr/local/bin/o2a-custom';
		service.settings.debug_mode = true;
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
