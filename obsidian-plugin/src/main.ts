import {
	Editor,
	MarkdownView,
	Notice,
	Plugin,
	FileSystemAdapter,
	TFile,
	WorkspaceLeaf,
} from 'obsidian';
import { EditorView } from '@codemirror/view';
import * as path from 'path';

import { AretePluginSettings, DEFAULT_SETTINGS } from '@domain/settings';

import { CardYamlEditorView, YAML_EDITOR_VIEW_TYPE } from '@presentation/views/CardYamlEditorView';
import { DashboardView, DASHBOARD_VIEW_TYPE } from '@presentation/views/DashboardView';
import { ChatView, CHAT_VIEW_TYPE } from '@presentation/views/ChatView';
import { AreteSettingTab } from '@presentation/settings/SettingTab';
import { SyncService } from '@application/services/SyncService';
import { CheckService } from '@application/services/CheckService';
import { AgentService } from '@application/services/AgentService';
import { TemplateRenderer } from '@application/services/TemplateRenderer';
import { StatsService, StatsCache } from '@application/services/StatsService';
import { GraphService } from '@application/services/GraphService';
import { LinkCheckerService } from '@application/services/LinkCheckerService';
import { LeechService } from '@application/services/LeechService';
import { ServerManager } from '@application/services/ServerManager';
import { AreteClient } from '@infrastructure/arete/AreteClient';
import {
	createCardGutter,
	highlightCardEffect,
} from '@presentation/extensions/CardGutterExtension';

interface AreteData extends AretePluginSettings {
	statsCache?: StatsCache;
}

export default class AretePlugin extends Plugin {
	settings: AretePluginSettings;
	statsCache: StatsCache;
	statusBarItem: HTMLElement;
	syncService: SyncService;
	checkService: CheckService;
	statsService: StatsService;
	graphService: GraphService;
	linkCheckerService: LinkCheckerService;
	leechService: LeechService;
	serverManager: ServerManager;
	agentService: AgentService;
	areteClient: AreteClient;
	templateRenderer: TemplateRenderer;
	private syncOnSaveTimeout: ReturnType<typeof setTimeout> | null = null;

	async onload() {
		console.log('[Arete] Plugin Loading...');

		try {
			await this.loadSettings();
			console.log('[Arete] Settings loaded:', this.settings);

			// Initialize Services
			// Initialize Services
			this.areteClient = new AreteClient(this.settings);
			this.templateRenderer = new TemplateRenderer(this.app, this.areteClient);
			this.templateRenderer.setMode(this.settings.renderer_mode);
			this.syncService = new SyncService(this.app, this.settings, (msg: string) => {
				console.log(msg); // Default logger
			});
			this.checkService = new CheckService(this.app, this); // CheckService needs plugin for runFix callback
			this.statsService = new StatsService(this.app, this.settings, this.statsCache);
			this.graphService = new GraphService(this.app, this.settings);

			// Initialize New Dashboard Services
			this.linkCheckerService = new LinkCheckerService(this.app, this);
			this.leechService = new LeechService(this.app, this.areteClient);
			this.serverManager = new ServerManager(this.app, this.settings, this.manifest);
			this.agentService = new AgentService(this.settings);

			// Start Server (background) if enabled
			this.serverManager.start(true);

			// Auto-refresh stats on startup
			this.app.workspace.onLayoutReady(async () => {
				if (this.settings.execution_mode === 'server') {
					await this.serverManager.start();
				}
				console.log('[Arete] Refreshing stats on startup...');
				this.statsService
					.refreshStats()
					.then(async (results) => {
						// Updated to receive results
						console.log('[Arete] Stats refresh complete, notifying views...');

						// 1. Update Graph Tags (if enabled)
						if (this.settings.graph_coloring_enabled) {
							console.log('[Arete] Updating Graph Tags...');
							for (const concept of results) {
								const file = this.app.vault.getAbstractFileByPath(concept.filePath);
								if (file instanceof TFile) {
									await this.graphService.updateGraphTags(file, concept);
								}
							}
							new Notice('Graph tags updated.');
						}

						// 2. Refresh YAML Editor
						const yamlLeaf =
							this.app.workspace.getLeavesOfType(YAML_EDITOR_VIEW_TYPE)[0];
						if (yamlLeaf) {
							const view = yamlLeaf.view as CardYamlEditorView;
							if (view.renderToolbar) {
								view.renderToolbar();
							}
						}
					})
					.catch((err) => {
						console.error('[Arete] Failed to auto-refresh stats:', err);
					});
			});

			console.log('[Arete] Services initialized');

			// Register Views
			this.registerView(YAML_EDITOR_VIEW_TYPE, (leaf) => new CardYamlEditorView(leaf, this));
			this.registerView(DASHBOARD_VIEW_TYPE, (leaf) => new DashboardView(leaf, this));
			this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, this));
		} catch (e) {
			console.error('[Arete] Failed to initialize plugin services:', e);
			new Notice('Arete Plugin failed to initialize! Check console.');
		}

		// 1. Status Bar Setup
		this.statusBarItem = this.addStatusBarItem();
		this.statusBarItem.addClass('mod-clickable');
		this.statusBarItem.addEventListener('click', () => this.runSync());
		this.updateStatusBar('idle');

		// 2. Ribbon Icon
		this.addRibbonIcon('sheets-in-box', 'Sync to Anki (Arete)', (evt: MouseEvent) => {
			this.runSync();
		});

		this.addRibbonIcon('refresh-cw', 'Force Sync All (Arete)', (evt: MouseEvent) => {
			this.runSync(false, null, true);
		});

		this.addRibbonIcon('layout-dashboard', 'Arete Dashboard', (evt: MouseEvent) => {
			this.activateDashboardView();
		});

		this.addRibbonIcon('bot', 'Arete AI Assistant', (evt: MouseEvent) => {
			this.activateChatView();
		});

		// 3. Commands
		this.addCommand({
			id: 'arete-sync',
			name: 'Sync',
			hotkeys: [{ modifiers: ['Mod', 'Shift'], key: 'A' }],
			callback: () => {
				this.runSync();
			},
		});

		this.addCommand({
			id: 'arete-check-file',
			name: 'Check Current File',
			editorCallback: (editor: Editor, view: MarkdownView) => {
				if (view.file) {
					const vaultAdapter = this.app.vault.adapter as FileSystemAdapter;
					const basePath = vaultAdapter.getBasePath ? vaultAdapter.getBasePath() : null;
					if (basePath) {
						const fullPath = path.join(basePath, view.file.path);
						this.runCheck(fullPath);
					} else {
						new Notice('Error: Cannot determine vault path.');
					}
				}
			},
		});

		this.addCommand({
			id: 'arete-check-integrity',
			name: 'Debug: Vault Integrity Check',
			callback: () => {
				this.checkVaultIntegrity();
			},
		});

		this.addCommand({
			id: 'arete-sync-current-file',
			name: 'Sync Current File',
			callback: () => {
				const activeFile = this.app.workspace.getActiveFile();
				if (activeFile) {
					const vaultAdapter = this.app.vault.adapter as FileSystemAdapter;
					const basePath = vaultAdapter.getBasePath ? vaultAdapter.getBasePath() : null;
					if (basePath) {
						const maxPath = path.join(basePath, activeFile.path);
						this.runSync(false, maxPath, true);
					} else {
						new Notice('Error: Cannot resolve file path.');
					}
				} else {
					new Notice('No active file to sync.');
				}
			},
		});

		this.addCommand({
			id: 'arete-sync-prune',
			name: 'Sync (Prune Deleted Cards)',
			callback: () => {
				this.runSync(true);
			},
		});

		this.addCommand({
			id: 'arete-sync-force-all',
			name: 'Sync (Force Re-upload All)',
			callback: () => {
				this.runSync(false, null, true);
			},
		});

		this.addCommand({
			id: 'arete-open-dashboard',
			name: 'Open Dashboard',
			callback: () => {
				this.activateDashboardView();
			},
		});

		this.addCommand({
			id: 'arete-graph-clear',
			name: 'Graph: Clear Retention Tags',
			callback: async () => {
				await this.graphService.clearAllTags();
			},
		});

		this.addCommand({
			id: 'arete-sync-stats',
			name: 'Sync Stats (Refresh Anki Data)',
			callback: async () => {
				new Notice('Refreshing Arete stats...');
				const results = await this.statsService.refreshStats();

				// Post-refresh updates (Graph Tags + YAML Editor)
				if (this.settings.graph_coloring_enabled) {
					for (const concept of results) {
						const file = this.app.vault.getAbstractFileByPath(concept.filePath);
						if (file instanceof TFile) {
							await this.graphService.updateGraphTags(file, concept);
						}
					}
					new Notice('Graph tags updated.');
				}

				// Refresh YAML Toolbar
				const yamlLeaf = this.app.workspace.getLeavesOfType(YAML_EDITOR_VIEW_TYPE)[0];
				if (yamlLeaf) {
					const view = yamlLeaf.view as CardYamlEditorView;
					if (view.renderToolbar) {
						view.renderToolbar();
					}
				}
				new Notice('Stats refreshed.');
			},
		});

		// 4. Settings
		this.addSettingTab(new AreteSettingTab(this.app, this));

		// 5. Ribbon Icon and Commands
		this.addRibbonIcon('file-code', 'Open YAML Editor', () => {
			this.activateYamlEditorView();
		});

		this.addCommand({
			id: 'open-yaml-editor',
			name: 'Open YAML Editor',
			callback: () => {
				this.activateYamlEditorView();
			},
		});

		// 6. Card Gutter Extension
		this.registerEditorExtension(
			createCardGutter(
				(cardIndex) => {
					this.highlightCardLines(cardIndex);
					this.activateYamlEditorView(cardIndex);
				},
				(nid, cid) => {
					// Lookup enriched stats for this card from StatsService cache
					const activeFile = this.app.workspace.getActiveFile();
					if (!activeFile) return null;
					const conceptStats = this.statsService.getCache().concepts[activeFile.path];
					if (!conceptStats || !conceptStats.cardStats) return null;

					// Try to find by CID first, then by NID
					if (cid && conceptStats.cardStats[cid]) {
						return conceptStats.cardStats[cid];
					}
					if (nid && conceptStats.cardStats[nid]) {
						return conceptStats.cardStats[nid];
					}
					return null;
				},
				this.settings.stats_algorithm,
			),
		);

		// 7. Sync on Save (Debounced)
		this.registerEvent(
			this.app.vault.on('modify', (file) => {
				if (!this.settings.sync_on_save) return;
				if (!file.path.endsWith('.md')) return;

				// Clear existing timeout
				if (this.syncOnSaveTimeout) {
					clearTimeout(this.syncOnSaveTimeout);
				}

				// Debounce sync
				this.syncOnSaveTimeout = setTimeout(async () => {
					const vaultAdapter = this.app.vault.adapter as FileSystemAdapter;
					const basePath = vaultAdapter.getBasePath ? vaultAdapter.getBasePath() : null;
					if (basePath) {
						const fullPath = path.join(basePath, file.path);
						if (this.settings.debug_mode) {
							console.log('[Arete] Sync on save triggered for:', file.path);
						}
						await this.runSync(false, fullPath, false);
					}
				}, this.settings.sync_on_save_delay);
			}),
		);
	}

	// Highlight card lines in editor (permanent until different card is clicked)
	highlightCardLines(cardIndex: number) {
		// Use getMostRecentLeaf to find the editor (works when called from sidebar)
		const leaf = this.app.workspace.getMostRecentLeaf();
		if (!leaf || !(leaf.view instanceof MarkdownView)) return;

		// @ts-expect-error - accessing internal editor
		const cm = leaf.view.editor.cm as EditorView;
		if (cm) {
			cm.dispatch({
				effects: highlightCardEffect.of({ cardIndex }),
			});
		}
	}

	async activateChatView() {
		const { workspace } = this.app;

		let leaf: WorkspaceLeaf | null = null;
		const leaves = workspace.getLeavesOfType(CHAT_VIEW_TYPE);

		if (leaves.length > 0) {
			leaf = leaves[0];
		} else {
			leaf = workspace.getRightLeaf(false);
			await leaf.setViewState({ type: CHAT_VIEW_TYPE, active: true });
		}

		workspace.revealLeaf(leaf);
	}

	async activateDashboardView() {
		const { workspace } = this.app;
		let leaf = workspace.getLeavesOfType(DASHBOARD_VIEW_TYPE)[0];

		if (!leaf) {
			const rightLeaf = workspace.getRightLeaf(false);
			if (rightLeaf) {
				await rightLeaf.setViewState({
					type: DASHBOARD_VIEW_TYPE,
					active: true,
				});
			}
			leaf = workspace.getLeavesOfType(DASHBOARD_VIEW_TYPE)[0];
		}

		if (leaf) {
			workspace.revealLeaf(leaf);
		}
	}

	async activateYamlEditorView(focusCardIndex?: number) {
		const { workspace } = this.app;
		let leaf = workspace.getLeavesOfType(YAML_EDITOR_VIEW_TYPE)[0];

		if (!leaf) {
			const rightLeaf = workspace.getRightLeaf(false);
			if (rightLeaf) {
				await rightLeaf.setViewState({
					type: YAML_EDITOR_VIEW_TYPE,
					active: true,
				});
			}
			leaf = workspace.getLeavesOfType(YAML_EDITOR_VIEW_TYPE)[0];
		}

		if (leaf) {
			workspace.revealLeaf(leaf);
			if (focusCardIndex !== undefined) {
				const view = leaf.view as CardYamlEditorView;
				if (view?.focusCard) {
					view.focusCard(focusCardIndex);
				}
			}
		}
	}

	syncYamlEditorToCard(cardIndex: number) {
		const { workspace } = this.app;
		const leaf = workspace.getLeavesOfType(YAML_EDITOR_VIEW_TYPE)[0];
		if (leaf) {
			const view = leaf.view as CardYamlEditorView;
			if (view?.focusCard) {
				view.focusCard(cardIndex);
			}
		}
	}

	onunload() {
		if (this.statusBarItem) {
			this.statusBarItem.empty();
		}
		if (this.serverManager) {
			this.serverManager.stop();
		}
	}

	updateStatusBar(state: 'idle' | 'syncing' | 'error' | 'success', msg?: string) {
		if (!this.statusBarItem) return;
		this.statusBarItem.empty();

		if (state === 'idle') {
			// Show last sync time
			const lastSync = this.settings.last_sync_time;
			if (lastSync) {
				const ago = this.formatTimeAgo(lastSync);
				this.statusBarItem.setText(`🃏 ${ago}`);
				this.statusBarItem.title = 'Click to sync to Anki';
			} else {
				this.statusBarItem.setText('🃏 Arete');
				this.statusBarItem.title = 'Never synced. Click to sync.';
			}
			return;
		}

		if (state === 'syncing') {
			this.statusBarItem.createSpan({ cls: 'arete-sb-icon', text: '🔄 ' });
			this.statusBarItem.createSpan({ text: 'Syncing...' });
		} else if (state === 'success') {
			this.statusBarItem.setText('✅ Synced');
			setTimeout(() => this.updateStatusBar('idle'), 3000);
		} else if (state === 'error') {
			this.statusBarItem.setText('❌ Error');
			this.statusBarItem.title = msg || 'Check logs';
		}
	}

	private formatTimeAgo(timestamp: number): string {
		const now = Date.now();
		const diff = now - timestamp;
		const minutes = Math.floor(diff / 60000);
		const hours = Math.floor(diff / 3600000);
		const days = Math.floor(diff / 86400000);

		if (minutes < 1) return 'Just now';
		if (minutes < 60) return `${minutes}m ago`;
		if (hours < 24) return `${hours}h ago`;
		return `${days}d ago`;
	}

	// Notification helper with severity-based duration
	notify(message: string, severity: 'info' | 'success' | 'warning' | 'error' = 'info') {
		const durations = { info: 4000, success: 3000, warning: 6000, error: 10000 };
		new Notice(message, durations[severity]);
	}

	// Delegate to SyncService
	async runSync(prune = false, targetPath: string | null = null, force = false) {
		await this.syncService.runSync(prune, targetPath, force, this.updateStatusBar.bind(this));
		// Update last sync time on success
		this.settings.last_sync_time = Date.now();
		await this.saveSettings();
	}

	// Delegate to CheckService
	async runCheck(filePath: string) {
		await this.checkService.runCheck(filePath);
	}

	async runFix(filePath: string) {
		await this.checkService.runFix(filePath);
	}

	async checkVaultIntegrity() {
		await this.checkService.checkVaultIntegrity();
	}

	async testConfig() {
		await this.checkService.testConfig();
	}

	async loadSettings() {
		const data = await this.loadData();
		this.settings = Object.assign({}, DEFAULT_SETTINGS, data);
		this.statsCache = data?.statsCache;
	}

	async saveSettings() {
		await this.saveData({ ...this.settings, statsCache: this.statsCache });
		// Update services with new settings
		this.syncService.settings = this.settings;
		this.checkService.settings = this.settings;
		if (this.statsService) {
			this.statsService.settings = this.settings;
		}
		if (this.graphService) {
			this.graphService.updateSettings(this.settings);
		}
	}

	async saveStats() {
		if (this.statsService) {
			this.statsCache = this.statsService.getCache();
			await this.saveSettings();
		}
	}
}
