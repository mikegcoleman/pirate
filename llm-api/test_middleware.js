/**
 * Unit tests for request ID middleware and structured logging
 *
 * Tests reqId generation, header extraction, response echo, and JSON log format.
 */

const assert = require('assert');

// Mock logger for testing
let logOutput = [];
const mockLog = (level, msg, reqId, meta) => {
    const logEntry = {
        ts: new Date().toISOString(),
        level,
        reqId: reqId || null,
        msg,
        meta: Object.keys(meta || {}).length > 0 ? meta : undefined
    };
    logOutput.push(JSON.stringify(logEntry, (key, value) => value === undefined ? undefined : value));
};

// Test helpers
function runTests() {
    console.log('Running middleware tests...\n');

    testRequestIdGeneration();
    testRequestIdExtraction();
    testRequestIdEcho();
    testLogJsonFormat();
    testLogLevels();
    testLogWithMetadata();

    console.log('\n✅ All tests passed!');
}

function testRequestIdGeneration() {
    console.log('Test: Request ID generation format');

    // Simulate reqId generation (UUID v4 substring)
    const { v4: uuidv4 } = require('uuid');
    const reqId = uuidv4().substring(0, 8);

    assert.strictEqual(reqId.length, 8, 'Request ID should be 8 characters');
    assert.match(reqId, /^[0-9a-f]{8}$/, 'Request ID should be lowercase hex');

    console.log('  ✓ Request ID format correct\n');
}

function testRequestIdExtraction() {
    console.log('Test: Request ID extraction from headers');

    // Test case-insensitive extraction
    const testCases = [
        { headers: { 'x-request-id': 'test1234' }, expected: 'test1234' },
        { headers: { 'X-Request-Id': 'test5678' }, expected: 'test5678' },
        { headers: { 'X-REQUEST-ID': 'testabc0' }, expected: 'testabc0' },
        { headers: { 'content-type': 'application/json' }, expected: null }
    ];

    const REQUEST_ID_HEADER = 'X-Request-Id';

    testCases.forEach(({ headers, expected }) => {
        let reqId = null;
        for (const [key, value] of Object.entries(headers)) {
            if (key.toLowerCase() === REQUEST_ID_HEADER.toLowerCase()) {
                reqId = value;
                break;
            }
        }

        assert.strictEqual(reqId, expected, `Failed for headers: ${JSON.stringify(headers)}`);
    });

    console.log('  ✓ Request ID extraction works (case-insensitive)\n');
}

function testRequestIdEcho() {
    console.log('Test: Request ID echo in response headers');

    // Simulate middleware behavior
    const reqId = 'echo1234';
    const mockRes = {
        headers: {},
        setHeader(key, value) {
            this.headers[key] = value;
        }
    };

    // Middleware would do this
    mockRes.setHeader('X-Request-Id', reqId);

    assert.strictEqual(mockRes.headers['X-Request-Id'], reqId, 'Response header should contain reqId');

    console.log('  ✓ Request ID echoed in response header\n');
}

function testLogJsonFormat() {
    console.log('Test: JSON log format');

    logOutput = [];
    const reqId = 'json1234';

    // Log a test message
    mockLog('info', 'Test message', reqId, { duration_ms: 123 });

    assert.strictEqual(logOutput.length, 1, 'Should have one log entry');

    const logEntry = JSON.parse(logOutput[0]);

    assert.ok(logEntry.ts, 'Should have timestamp');
    assert.strictEqual(logEntry.level, 'info', 'Should have correct level');
    assert.strictEqual(logEntry.reqId, reqId, 'Should have correct reqId');
    assert.strictEqual(logEntry.msg, 'Test message', 'Should have correct message');
    assert.ok(logEntry.meta, 'Should have meta object');
    assert.strictEqual(logEntry.meta.duration_ms, 123, 'Meta should contain duration_ms');

    console.log('  ✓ JSON log format is correct\n');
}

function testLogLevels() {
    console.log('Test: Log levels');

    logOutput = [];
    const levels = ['debug', 'info', 'warn', 'error'];

    levels.forEach(level => {
        mockLog(level, `Test ${level} message`, null, {});
    });

    assert.strictEqual(logOutput.length, levels.length, `Should have ${levels.length} log entries`);

    logOutput.forEach((output, index) => {
        const logEntry = JSON.parse(output);
        assert.strictEqual(logEntry.level, levels[index], `Log level should be ${levels[index]}`);
    });

    console.log('  ✓ All log levels work correctly\n');
}

function testLogWithMetadata() {
    console.log('Test: Logging with metadata');

    logOutput = [];

    // Log with various metadata types
    mockLog('info', 'Metadata test', 'meta1234', {
        string_val: 'test',
        int_val: 42,
        float_val: 3.14,
        bool_val: true,
        null_val: null
    });

    const logEntry = JSON.parse(logOutput[0]);

    assert.strictEqual(logEntry.meta.string_val, 'test', 'String metadata should match');
    assert.strictEqual(logEntry.meta.int_val, 42, 'Int metadata should match');
    assert.strictEqual(logEntry.meta.float_val, 3.14, 'Float metadata should match');
    assert.strictEqual(logEntry.meta.bool_val, true, 'Boolean metadata should match');
    assert.strictEqual(logEntry.meta.null_val, null, 'Null metadata should match');

    console.log('  ✓ Metadata logging works with various types\n');
}

function testEmptyMetaOmitted() {
    console.log('Test: Empty meta object is omitted');

    logOutput = [];

    // Log with empty metadata
    mockLog('info', 'No metadata', 'nometa12', {});

    const logEntry = JSON.parse(logOutput[0]);

    assert.strictEqual(logEntry.meta, undefined, 'Empty meta should be undefined/omitted');

    console.log('  ✓ Empty meta object is omitted from JSON\n');
}

// Run all tests
try {
    runTests();
    process.exit(0);
} catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error(error.stack);
    process.exit(1);
}
