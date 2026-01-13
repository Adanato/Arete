export interface AretePluginSettings {
	python_path: string;
	arete_script_path: string;
	debug_mode: boolean;
	backend: 'auto' | 'apy' | 'ankiconnect';
	workers: number;
	anki_connect_url: string;
	anki_media_dir: string;
	renderer_mode: 'obsidian' | 'anki';
	stats_algorithm: 'sm2' | 'fsrs';
	stats_lapse_threshold: number;
	stats_ease_threshold: number; // 2100 = 210%
	stats_difficulty_threshold: number; // For FSRS, e.g. 0.9 (90%)

	// UI Persistence
	ui_expanded_decks: string[];
	ui_expanded_concepts: string[];
}

export const DEFAULT_SETTINGS: AretePluginSettings = {
	python_path: 'python3',
	arete_script_path: '',
	debug_mode: false,
	backend: 'auto',
	workers: 4,
	anki_connect_url: 'http://localhost:8765',
	anki_media_dir: '',
	renderer_mode: 'obsidian',
	stats_algorithm: 'fsrs', // Default to FSRS
	stats_lapse_threshold: 3,
	stats_ease_threshold: 2100, // 210%
	stats_difficulty_threshold: 0.9, // 90% Max Difficulty

	ui_expanded_decks: [],
	ui_expanded_concepts: [],
};
