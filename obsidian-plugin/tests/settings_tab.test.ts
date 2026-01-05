import './test-setup';
import { App, Setting } from 'obsidian';
import AretePlugin, { AreteSettingTab } from '../main';

describe('AreteSettingTab Interaction Tests', () => {
	let plugin: AretePlugin;
	let app: App;
	let settingTab: AreteSettingTab;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.settings = {
			areteScriptPath: '/old/path',
			pythonPath: 'python',
			debugMode: false,
			backend: 'auto',
			workers: 4,
		} as any;
		plugin.saveSettings = jest.fn().mockResolvedValue(undefined);
		plugin.testConfig = jest.fn().mockResolvedValue(undefined);
		settingTab = new AreteSettingTab(app, plugin);

		(app as any).setting = {
			openTabById: jest.fn(),
			activeTab: {
				searchComponent: { setValue: jest.fn() },
				updateHotkeyVisibility: jest.fn(),
			},
		};
		(app as any).commands = {
			listCommands: jest.fn().mockReturnValue([]),
			findCommand: jest.fn().mockReturnValue({ hotkeys: [] }),
		};
	});

	const findSettingByName = (name: string) => {
		return (Setting as jest.Mock).mock.results
			.map((r) => r.value)
			.find((s) => s.setName.mock.calls.some((c: any) => c[0] === name));
	};

	test('Python Executable setting updates correctly', async () => {
		settingTab.display();
		const setting = findSettingByName('Python Executable');
		expect(setting).toBeDefined();

		await setting.mockText._onChange('new-python');
		expect(plugin.settings.pythonPath).toBe('new-python');
		expect(plugin.saveSettings).toHaveBeenCalled();
	});

	test('Arete Script Path setting updates correctly', async () => {
		settingTab.display();
		const setting = findSettingByName('Arete Script Path');
		expect(setting).toBeDefined();

		await setting.mockText._onChange('/new/script/path.py');
		expect(plugin.settings.areteScriptPath).toBe('/new/script/path.py');
		expect(plugin.saveSettings).toHaveBeenCalled();
	});

	test('Debug Mode toggle updates correctly', async () => {
		settingTab.display();
		const setting = findSettingByName('Debug Mode');
		expect(setting).toBeDefined();

		await setting.mockToggle._onChange(true);
		expect(plugin.settings.debugMode).toBe(true);
		expect(plugin.saveSettings).toHaveBeenCalled();
	});

	test('Anki Backend dropdown updates correctly', async () => {
		settingTab.display();
		const setting = findSettingByName('Anki Backend');
		expect(setting).toBeDefined();

		await setting.mockDropdown._onChange('apy');
		expect(plugin.settings.backend).toBe('apy');
		expect(plugin.saveSettings).toHaveBeenCalled();
	});

	test('Parallel Workers slider updates correctly', async () => {
		settingTab.display();
		const setting = findSettingByName('Parallel Workers');
		expect(setting).toBeDefined();

		await setting.mockSlider._onChange(8);
		expect(plugin.settings.workers).toBe(8);
		expect(plugin.saveSettings).toHaveBeenCalled();
	});

	test('Hotkey Configure button opens correct tab', async () => {
		// Mock a command for the hotkey button
		((app as any).commands.listCommands as jest.Mock).mockReturnValue([
			{ id: 'arete-sync', name: 'Sync' },
		]);
		((app as any).commands.findCommand as jest.Mock).mockReturnValue({
			name: 'Sync',
			hotkeys: [{ modifiers: ['Mod', 'Shift'], key: 'S' }],
		});

		settingTab.display();
		const syncSetting = findSettingByName('Sync');
		expect(syncSetting).toBeDefined();

		await syncSetting.mockButton._onClick();
		expect((app as any).setting.openTabById).toHaveBeenCalledWith('hotkeys');
		expect((app as any).setting.activeTab.searchComponent.setValue).toHaveBeenCalledWith(
			'arete',
		);
	});

	test('Test Config button calls plugin method', async () => {
		settingTab.display();
		const testBtn = findSettingByName('Test Configuration');
		expect(testBtn).toBeDefined();
		await testBtn.mockButton._onClick();
		expect(plugin.testConfig).toHaveBeenCalled();
	});

	test('Open Sample Modal button works', async () => {
		plugin.settings.debugMode = true;
		settingTab.display();
		const debugSetting = findSettingByName('Check Results (Debug)');
		expect(debugSetting).toBeDefined();

		await debugSetting.mockButton._onClick();
		// Just verify it doesn't crash
	});
});
