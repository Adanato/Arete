/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
	forbidden: [
		// Domain Isolation: Domain cannot import from any outer layer
		{
			name: 'domain-isolation',
			comment: 'Domain layer must be pure and cannot depend on outer layers',
			severity: 'error',
			from: { path: '^src/domain' },
			to: { path: '^src/(application|infrastructure|presentation)' },
		},
		// Infrastructure cannot import from Presentation
		{
			name: 'infrastructure-no-presentation',
			comment: 'Infrastructure cannot depend on Presentation',
			severity: 'error',
			from: { path: '^src/infrastructure' },
			to: { path: '^src/presentation' },
		},
		// Application cannot import from Presentation
		{
			name: 'application-no-presentation',
			comment: 'Application cannot depend on Presentation',
			severity: 'error',
			from: { path: '^src/application' },
			to: { path: '^src/presentation' },
		},
		// Circular dependencies (ignore main.ts which must import views for registration)
		{
			name: 'no-circular',
			comment: 'Circular dependencies are not allowed',
			severity: 'warn',
			from: { pathNot: '^src/main\\.ts$' },
			to: { circular: true },
		},
	],
	options: {
		doNotFollow: {
			path: 'node_modules',
		},
		tsPreCompilationDeps: true,
		tsConfig: {
			fileName: 'tsconfig.json',
		},
		enhancedResolveOptions: {
			exportsFields: ['exports'],
			conditionNames: ['import', 'require', 'node', 'default'],
		},
		reporterOptions: {
			dot: {
				collapsePattern: 'node_modules/(@[^/]+/[^/]+|[^/]+)',
			},
		},
	},
};
