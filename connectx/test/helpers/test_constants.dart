/// Shared test constants for consistent test timing across all test files

// Test timing constants for faster test execution
const testDeviceCheckInterval = Duration(milliseconds: 50);
const testInputChangeDebounce = Duration(milliseconds: 10);
// Wait duration accounts for device check interval + debounce + processing overhead
const testWaitDuration = Duration(milliseconds: 70);
