export class App {
	vault: any = {
		adapter: {
			getBasePath: jest.fn(() => '/mock/vault/path'),
		},
	};
}

export class Plugin {
	app: App;
	settings: any = {};

	constructor(app: App) {
		this.app = app;
	}

	loadData() {
		return Promise.resolve({});
	}
	saveData() {
		return Promise.resolve();
	}
	/* eslint-disable @typescript-eslint/no-empty-function */
	addRibbonIcon() {}
	addCommand() {}
	addSettingTab() {}
	/* eslint-enable @typescript-eslint/no-empty-function */
}

export class PluginSettingTab {
	/* eslint-disable @typescript-eslint/no-empty-function */
	constructor(app: App, plugin: Plugin) {}
	display() {}
	/* eslint-enable @typescript-eslint/no-empty-function */
}

export class Setting {
	/* eslint-disable @typescript-eslint/no-empty-function */
	constructor(containerEl: any) {}
	/* eslint-enable @typescript-eslint/no-empty-function */
	setName() {
		return this;
	}
	setDesc() {
		return this;
	}
	addText() {
		return this;
	}
}

export class Notice {
	/* eslint-disable @typescript-eslint/no-empty-function */
	constructor(message: string) {}
	/* eslint-enable @typescript-eslint/no-empty-function */
}

export class FileSystemAdapter {}
