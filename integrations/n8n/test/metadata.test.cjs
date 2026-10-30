const test = require('node:test');
const assert = require('node:assert/strict');
const { nodes, credentials } = require('../index.js');
const nodeDescription = new nodes[0]().description;
const credential = new credentials[0]();

test('package exports the AutoIXB node and API credential', () => {
	assert.equal(nodes.length, 1);
	assert.equal(nodeDescription.name, 'autoIXB');
	assert.equal(credentials.length, 1);
	assert.equal(credential.name, 'autoIxbApi');
});

test('node includes explicit profile selection and run status operations', () => {
	const properties = nodeDescription.properties;
	const names = new Set(properties.map((property) => property.name));
	assert.ok(names.has('profileMode'));
	assert.ok(names.has('allowAllProfiles'));
	assert.ok(names.has('waitForCompletion'));
	assert.ok(names.has('runId'));
});
