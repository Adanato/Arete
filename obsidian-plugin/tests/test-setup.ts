import { EventEmitter } from 'events';

// 1. Mock child_process and fs globally
jest.mock('child_process', () => ({
	spawn: jest.fn(),
}));

jest.mock('fs', () => ({
	appendFileSync: jest.fn(),
	readFileSync: jest.fn(),
	writeFileSync: jest.fn(),
	existsSync: jest.fn(),
}));

// Mock factories that return fresh instances
export const createMockElement = (tag?: string, opts?: any): any => {
	const el: any = {
		tag,
		addClass: jest.fn().mockReturnThis(),
		removeClass: jest.fn().mockReturnThis(),
		empty: jest.fn().mockReturnThis(),
		setText: jest.fn().mockReturnThis(),
		setButtonText: jest.fn().mockReturnThis(),
		setDisabled: jest.fn().mockReturnThis(),
		addEventListener: jest.fn().mockImplementation(function (this: any, name, cb) {
			this._listeners = this._listeners || {};
			this._listeners[name] = cb;
			return this;
		}),
		createDiv: jest.fn().mockImplementation((o) => createMockElement('div', o)),
		createEl: jest.fn().mockImplementation((t, o) => createMockElement(t, o)),
		createSpan: jest.fn().mockImplementation((o) => createMockElement('span', o)),
		appendChild: jest.fn().mockReturnThis(),
		removeChild: jest.fn().mockReturnThis(),
		...opts,
	};
	return el;
};

export const createMockSetting = (): any => {
	const mock: any = {
		setName: jest.fn().mockReturnThis(),
		setDesc: jest.fn().mockReturnThis(),
		addText: jest.fn().mockImplementation((cb: any) => {
			const mockText: any = {
				setPlaceholder: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockImplementation((ocb: any) => {
					mockText._onChange = ocb;
					return mockText;
				}),
			};
			cb(mockText);
			mock.mockText = mockText;
			return mock;
		}),
		addToggle: jest.fn().mockImplementation((cb: any) => {
			const mockToggle: any = {
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockImplementation((ocb: any) => {
					mockToggle._onChange = ocb;
					return mockToggle;
				}),
			};
			cb(mockToggle);
			mock.mockToggle = mockToggle;
			return mock;
		}),
		addDropdown: jest.fn().mockImplementation((cb: any) => {
			const mockDropdown: any = {
				addOption: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockImplementation((ocb: any) => {
					mockDropdown._onChange = ocb;
					return mockDropdown;
				}),
			};
			cb(mockDropdown);
			mock.mockDropdown = mockDropdown;
			return mock;
		}),
		addSlider: jest.fn().mockImplementation((cb: any) => {
			const mockSlider: any = {
				setLimits: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				setDynamicTooltip: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockImplementation((ocb: any) => {
					mockSlider._onChange = ocb;
					return mockSlider;
				}),
			};
			cb(mockSlider);
			mock.mockSlider = mockSlider;
			return mock;
		}),
		addButton: jest.fn().mockImplementation((cb: any) => {
			const mockButton: any = {
				setButtonText: jest.fn().mockReturnThis(),
				onClick: jest.fn().mockImplementation((ocb: any) => {
					mockButton._onClick = ocb;
					return mockButton;
				}),
			};
			cb(mockButton);
			mock.mockButton = mockButton;
			return mock;
		}),
	};
	return mock;
};

// Make factories available to jest.mock
(global as any).mockCreateMockElement = createMockElement;
(global as any).mockCreateMockSetting = createMockSetting;

jest.mock('obsidian', () => {
	return {
		App: jest.fn().mockImplementation(() => ({
			vault: {
				adapter: { getBasePath: jest.fn() },
				getMarkdownFiles: jest.fn().mockReturnValue([]),
				read: jest.fn(),
				on: jest.fn(),
			},
			workspace: {
				getActiveFile: jest.fn(),
				getActiveViewOfType: jest.fn(),
				on: jest.fn(),
			},
			metadataCache: {
				getFileCache: jest.fn(),
				on: jest.fn(),
			},
			commands: {
				findCommand: jest.fn(),
				listCommands: jest.fn().mockReturnValue([]),
			},
			setting: {
				openTabById: jest.fn(),
			},
		})),
		Plugin: class {
			app: any;
			manifest: any;
			constructor(app: any, manifest: any) {
				this.app = app;
				this.manifest = manifest;
			}
			addStatusBarItem() {
				return (global as any).mockCreateMockElement('div');
			}
			addRibbonIcon() {
				return (global as any).mockCreateMockElement('div');
			}
			addCommand(cmd: any) {
				(global as any).registeredCommands = (global as any).registeredCommands || {};
				(global as any).registeredCommands[cmd.id] = cmd;
				return cmd;
			}
			addSettingTab() {
				return {};
			}
			loadData() {
				return Promise.resolve({});
			}
			saveData() {
				return Promise.resolve();
			}
			registerEvent() {
				/* no-op */
			}
			registerView() {
				/* no-op */
			}
			registerEditorExtension() {
				/* no-op */
			}
		},
		PluginSettingTab: class {
			app: any;
			plugin: any;
			containerEl = (global as any).mockCreateMockElement('div');
			constructor(app: any, plugin: any) {
				this.app = app;
				this.plugin = plugin;
			}
		},
		Setting: jest.fn().mockImplementation(() => (global as any).mockCreateMockSetting()),
		Notice: jest.fn(),
		Modal: class {
			app: any;
			contentEl = (global as any).mockCreateMockElement('div');
			constructor(app: any) {
				this.app = app;
			}
			open() {
				/* no-op */
			}
			close() {
				/* no-op */
			}
		},
		FileSystemAdapter: class {},
		setIcon: jest.fn(),
		MarkdownView: class {},
		Editor: class {},
		TFile: class {},
		ItemView: class {
			contentEl = (global as any).mockCreateMockElement('div');
			constructor(leaf: any) {
				/* no-op */
			}
		},
		MarkdownRenderer: {
			render: jest.fn(),
		},
		requestUrl: jest.fn(),
	};
});

export const createMockChildProcess = () => {
	const child: any = new EventEmitter();
	child.stdout = new EventEmitter();
	child.stderr = new EventEmitter();
	return child;
};
