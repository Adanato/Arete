export const createMockSetting = () => {
	const mock: any = {
		setName: jest.fn().mockReturnThis(),
		setDesc: jest.fn().mockReturnThis(),
		addText: jest.fn().mockImplementation((cb) => {
			const mockText = {
				setPlaceholder: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockReturnThis(),
			};
			cb(mockText);
			mock.mockText = mockText;
			return mock;
		}),
		addToggle: jest.fn().mockImplementation((cb) => {
			const mockToggle = {
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockReturnThis(),
			};
			cb(mockToggle);
			mock.mockToggle = mockToggle;
			return mock;
		}),
		addDropdown: jest.fn().mockImplementation((cb) => {
			const mockDropdown = {
				addOption: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockReturnThis(),
			};
			cb(mockDropdown);
			mock.mockDropdown = mockDropdown;
			return mock;
		}),
		addSlider: jest.fn().mockImplementation((cb) => {
			const mockSlider = {
				setLimits: jest.fn().mockReturnThis(),
				setValue: jest.fn().mockReturnThis(),
				setDynamicTooltip: jest.fn().mockReturnThis(),
				onChange: jest.fn().mockReturnThis(),
			};
			cb(mockSlider);
			mock.mockSlider = mockSlider;
			return mock;
		}),
		addButton: jest.fn().mockImplementation((cb) => {
			const mockButton = {
				setButtonText: jest.fn().mockReturnThis(),
				onClick: jest.fn().mockReturnThis(),
			};
			cb(mockButton);
			mock.mockButton = mockButton;
			return mock;
		}),
	};
	return mock;
};

export const createMockObsidian = () => {
	return {
		App: jest.fn().mockImplementation(() => ({
			vault: {
				adapter: { getBasePath: jest.fn() },
				getMarkdownFiles: jest.fn().mockReturnValue([]),
				read: jest.fn(),
			},
			workspace: {
				getActiveFile: jest.fn(),
			},
			metadataCache: {
				getFileCache: jest.fn(),
			},
			commands: {
				findCommand: jest.fn(),
			},
		})),
		Plugin: class {},
		PluginSettingTab: class {
			app: any;
			plugin: any;
			containerEl = {
				empty: jest.fn(),
				createEl: jest.fn().mockReturnValue({}),
				createDiv: jest.fn().mockReturnValue({}),
				createSpan: jest.fn().mockReturnValue({}),
			};
			constructor(app: any, plugin: any) {
				this.app = app;
				this.plugin = plugin;
			}
		},
		Setting: jest.fn().mockImplementation(() => createMockSetting()),
		Notice: jest.fn(),
		Modal: class {
			contentEl = {
				addClass: jest.fn(),
				createDiv: jest.fn().mockImplementation(() => ({
					createEl: jest.fn().mockReturnValue({}),
					createSpan: jest.fn().mockReturnValue({}),
					createDiv: jest.fn().mockReturnThis(),
					addEventListener: jest.fn(),
				})),
				createEl: jest.fn().mockImplementation(() => ({
					createEl: jest.fn().mockReturnValue({}),
					createSpan: jest.fn().mockReturnValue({}),
					createDiv: jest.fn().mockReturnThis(),
					addEventListener: jest.fn(),
				})),
				empty: jest.fn(),
			};
			constructor() {
				/* no-op */
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
	};
};
