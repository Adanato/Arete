module.exports = {
	preset: 'ts-jest',
	testEnvironment: 'node',
	moduleFileExtensions: ['ts', 'js'],
	transform: {
		'^.+\\.ts$': 'ts-jest',
	},
	testMatch: ['**/tests/**/*.test.ts'],
	collectCoverage: true,
	coverageThreshold: {
		global: {
			branches: 80,
			functions: 92,
			lines: 95,
			statements: 94,
		},
	},
	moduleNameMapper: {
		'^@/(.*)$': '<rootDir>/src/$1',
		'^@domain/(.*)$': '<rootDir>/src/domain/$1',
		'^@application/(.*)$': '<rootDir>/src/application/$1',
		'^@infrastructure/(.*)$': '<rootDir>/src/infrastructure/$1',
		'^@presentation/(.*)$': '<rootDir>/src/presentation/$1',
	},
};
