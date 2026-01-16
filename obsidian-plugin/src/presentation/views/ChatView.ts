import { ItemView, WorkspaceLeaf, setIcon, Notice, MarkdownRenderer } from 'obsidian';
import AretePlugin from '@/main';
import { AgentResponse } from '@application/services/AgentService';

export const CHAT_VIEW_TYPE = 'arete-chat-view';

interface Message {
	role: 'user' | 'assistant';
	content: string;
	action?: string;
	suggestions?: string[];
}

export class ChatView extends ItemView {
	plugin: AretePlugin;
	messages: Message[] = [];
	isLoading = false;

	constructor(leaf: WorkspaceLeaf, plugin: AretePlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType() {
		return CHAT_VIEW_TYPE;
	}

	getDisplayText() {
		return 'Arete AI Assistant';
	}

	getIcon() {
		return 'bot';
	}

	async onOpen() {
		this.render();
	}

	async onClose() {
		// Cleanup if needed
	}

	async sendMessage(text: string) {
		if (!text.trim() || this.isLoading) return;

		this.messages.push({ role: 'user', content: text });
		this.isLoading = true;
		this.render();

		try {
			const res = await this.plugin.agentService.chat(text);
			this.messages.push({
				role: 'assistant',
				content: res.chat_message,
				action: res.action_taken || undefined,
				suggestions: res.suggested_questions,
			});
		} catch (error) {
			new Notice(`Error: ${error.message}`);
			this.messages.push({
				role: 'assistant',
				content: `Sorry, I encountered an error: ${error.message}`,
			});
		} finally {
			this.isLoading = false;
			this.render();
		}
	}

	render() {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('arete-chat-container');

		const chatContent = container.createDiv({ cls: 'arete-chat-messages' });

		// Handle clicks on internal links
		chatContent.addEventListener('click', (e) => {
			const target = e.target as HTMLElement;
			const link = target.closest('.internal-link') as HTMLElement;
			if (link) {
				const href = link.getAttribute('data-href');
				if (href) {
					e.preventDefault();
					this.app.workspace.openLinkText(href, '', true);
				}
			}
		});

		this.messages.forEach((msg) => {
			const msgEl = chatContent.createDiv({
				cls: `arete-chat-message arete-chat-message-${msg.role}`,
			});

			if (msg.role === 'assistant') {
				const header = msgEl.createDiv({ cls: 'arete-chat-message-header' });
				setIcon(header, 'bot');
				header.createSpan({ text: 'Arete' });
			}

			const contentEl = msgEl.createDiv({ cls: 'arete-chat-message-content' });
			MarkdownRenderer.render(this.app, msg.content, contentEl, '', this);

			if (msg.action) {
				const actionEl = msgEl.createDiv({ cls: 'arete-chat-message-action' });
				actionEl.createSpan({ text: '⚙️ ', cls: 'arete-action-icon' });
				const actionContent = actionEl.createSpan();
				MarkdownRenderer.render(this.app, msg.action, actionContent, '', this);
			}

			if (msg.role === 'assistant' && msg.suggestions && msg.suggestions.length > 0) {
				const suggContainer = msgEl.createDiv({ cls: 'arete-chat-suggestions' });
				msg.suggestions.forEach((sugg) => {
					const btn = suggContainer.createEl('button', {
						cls: 'arete-chat-suggestion-btn',
						text: sugg,
					});
					btn.onclick = () => this.sendMessage(sugg);
				});
			}
		});

		if (this.isLoading) {
			const loadingEl = chatContent.createDiv({ cls: 'arete-chat-loading' });
			loadingEl.createSpan({ text: 'Thinking...' });
		}

		// Scroll to bottom
		setTimeout(() => {
			chatContent.scrollTop = chatContent.scrollHeight;
		}, 10);

		// Input area
		const inputWrapper = container.createDiv({ cls: 'arete-chat-input-wrapper' });
		const inputEl = inputWrapper.createEl('textarea', {
			cls: 'arete-chat-input',
			attr: { placeholder: 'Ask me anything about your learning...' },
		});

		inputEl.onkeydown = (e) => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				this.sendMessage(inputEl.value);
				inputEl.value = '';
			}
		};

		const sendBtn = inputWrapper.createEl('button', { cls: 'arete-chat-send-btn' });
		setIcon(sendBtn, 'send');
		sendBtn.onclick = () => {
			this.sendMessage(inputEl.value);
			inputEl.value = '';
		};
	}
}
