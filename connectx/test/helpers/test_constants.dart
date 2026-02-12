/// Shared test constants for consistent test timing across all test files

// Test timing constants for faster test execution
// These values are significantly shorter than production values to speed up tests:
// - Production: 3000ms device check, 300ms debounce
// - Test: 50ms device check, 10ms debounce
const testDeviceCheckInterval = Duration(milliseconds: 50);
const testInputChangeDebounce = Duration(milliseconds: 10);

// Wait duration for tests to ensure async operations complete before assertions
// This is a conservative estimate that accounts for:
// - Device check callback triggering (up to 50ms)
// - Debounce timer firing (10ms)  
// - Async operation processing overhead (10ms buffer)
// Total: 70ms (worst-case assumption that operations run sequentially)
const testWaitDuration = Duration(milliseconds: 70);
