export interface AretePluginSettings {
	pythonPath: string;
	areteScriptPath: string;
	debugMode: boolean;
	backend: 'auto' | 'apy' | 'ankiconnect';
	workers: number;
	ankiConnectUrl: string;
	ankiMediaDir: string;
	rendererMode: 'obsidian' | 'anki';
}

export const DEFAULT_SETTINGS: AretePluginSettings = {
	pythonPath: 'python3',
	areteScriptPath: '',
	debugMode: false,
	backend: 'auto',
	workers: 4,
	ankiConnectUrl: 'http://localhost:8765',
	ankiMediaDir: '',
	rendererMode: 'obsidian',
};
