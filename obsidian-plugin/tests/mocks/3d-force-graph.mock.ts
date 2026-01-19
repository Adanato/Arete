// Mock for 3d-force-graph to avoid ESM issues in Jest
const ForceGraph3D = jest.fn().mockImplementation(() => {
	const graphInstance = {
		width: jest.fn().mockReturnThis(),
		height: jest.fn().mockReturnThis(),
		graphData: jest.fn().mockReturnThis(),
		nodeLabel: jest.fn().mockReturnThis(),
		nodeColor: jest.fn().mockReturnThis(),
		nodeVal: jest.fn().mockReturnThis(),
		linkColor: jest.fn().mockReturnThis(),
		linkWidth: jest.fn().mockReturnThis(),
		linkDirectionalArrowLength: jest.fn().mockReturnThis(),
		linkDirectionalArrowRelPos: jest.fn().mockReturnThis(),
		onNodeClick: jest.fn().mockReturnThis(),
		onNodeHover: jest.fn().mockReturnThis(),
		d3Force: jest.fn().mockReturnThis(),
		_destructor: jest.fn(),
	};
	return graphInstance;
});

export default ForceGraph3D;
