/**
 * TypeScript types for dependency graph.
 *
 * These mirror the Python domain/graph.py types for frontend use.
 */

/**
 * A node in the dependency graph representing a single card.
 */
export interface CardNode {
	/** Stable Arete ID (e.g., arete_01JH8Y3ZK4QJ9W6E2N8F6M0P5R) */
	id: string;
	/** Display name (typically the Front field or filename) */
	title: string;
	/** Path to source markdown file */
	filePath: string;
	/** Line number in source file for navigation */
	lineNumber: number;
}

/**
 * Edge types for dependencies.
 */
export type EdgeType = 'requires' | 'related';

/**
 * An edge in the dependency graph.
 */
export interface DependencyEdge {
	type: EdgeType;
	fromId: string;
	toId: string;
}

/**
 * Complete dependency graph for a vault.
 */
export interface DependencyGraph {
	nodes: Map<string, CardNode>;
	requires: Map<string, string[]>; // id → [prereq ids]
	related: Map<string, string[]>; // id → [related ids]
}

/**
 * Result of a local graph query centered on a specific card.
 */
export interface LocalGraphResult {
	center: CardNode;
	prerequisites: CardNode[];
	dependents: CardNode[];
	related: CardNode[];
	links: DependencyEdge[]; // All edges in the subgraph
	cycles: string[][]; // Groups of co-requisite card IDs
}

/**
 * Helper class for building and querying dependency graphs.
 */
export class DependencyGraphBuilder {
	private nodes: Map<string, CardNode> = new Map();
	private requires: Map<string, string[]> = new Map();
	private related: Map<string, string[]> = new Map();

	addNode(node: CardNode): void {
		this.nodes.set(node.id, node);
		if (!this.requires.has(node.id)) {
			this.requires.set(node.id, []);
		}
		if (!this.related.has(node.id)) {
			this.related.set(node.id, []);
		}
	}

	addRequires(fromId: string, toId: string): void {
		const prereqs = this.requires.get(fromId) || [];
		if (!prereqs.includes(toId)) {
			prereqs.push(toId);
			this.requires.set(fromId, prereqs);
		}
	}

	addRelated(fromId: string, toId: string): void {
		const rels = this.related.get(fromId) || [];
		if (!rels.includes(toId)) {
			rels.push(toId);
			this.related.set(fromId, rels);
		}
	}

	getPrerequisites(cardId: string): string[] {
		return this.requires.get(cardId) || [];
	}

	getDependents(cardId: string): string[] {
		const dependents: string[] = [];
		for (const [id, prereqs] of this.requires) {
			if (prereqs.includes(cardId)) {
				dependents.push(id);
			}
		}
		return dependents;
	}

	getRelated(cardId: string): string[] {
		return this.related.get(cardId) || [];
	}

	getNode(cardId: string): CardNode | undefined {
		return this.nodes.get(cardId);
	}

	hasNode(cardId: string): boolean {
		return this.nodes.has(cardId);
	}

	getAllNodes(): CardNode[] {
		return Array.from(this.nodes.values());
	}

	toGraph(): DependencyGraph {
		return {
			nodes: new Map(this.nodes),
			requires: new Map(this.requires),
			related: new Map(this.related),
		};
	}
}
