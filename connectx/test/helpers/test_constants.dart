/// Shared test constants for consistent test timing across all test files

// Test timing constants for faster test execution
// These values are significantly shorter than production values to speed up tests:
// - Production: 3000ms device check, 300ms debounce
// - Test: 50ms device check, 10ms debounce
const testDeviceCheckInterval = Duration(milliseconds: 50);
const testInputChangeDebounce = Duration(milliseconds: 10);

// Wait duration accounts for device check interval + debounce + processing overhead
// Calculation: 50ms (device check) + 10ms (debounce) + 10ms (processing/async overhead) = 70ms
// This ensures async operations complete before assertions run
const testWaitDuration = Duration(milliseconds: 70);
