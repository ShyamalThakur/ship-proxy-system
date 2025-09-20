#!/bin/bash

# HTTP Test Script for Ship Proxy System
# Tests various HTTP methods and scenarios

PROXY="http://localhost:8080"

echo " Ship Proxy System - HTTP Test Suite"
echo "======================================"
echo "Proxy: $PROXY"
echo ""

# Function to run test and check result
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_pattern="$3"
    
    echo " Testing: $test_name"
    echo "Command: $command"
    
    # Run the command and capture output
    output=$(eval $command 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        if [ -n "$expected_pattern" ]; then
            if echo "$output" | grep -q "$expected_pattern"; then
                echo " PASS: Response contains expected pattern"
            else
                echo " FAIL: Expected pattern not found in response"
                echo "Output: $output"
            fi
        else
            echo " PASS: Command executed successfully"
        fi
    else
        echo " FAIL: Command failed with exit code $exit_code"
        echo "Output: $output"
    fi
    echo ""
}

# Wait for proxy to be ready
echo "⏳ Waiting for proxy to be ready..."
for i in {1..30}; do
    if curl -s --connect-timeout 2 -x $PROXY http://httpbin.org/get > /dev/null 2>&1; then
        echo " Proxy is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo " Proxy not responding after 30 seconds"
        exit 1
    fi
    sleep 1
done
echo ""

# Test 1: Basic HTTP GET
run_test "Basic HTTP GET" \
    "curl -s -x $PROXY http://httpbin.org/get" \
    "httpbin.org"

# Test 2: HTTP GET with httpforever.com (as specified in requirements)
run_test "HTTP GET - httpforever.com" \
    "curl -s -x $PROXY http://httpforever.com/" \
    "HTTP"

# Test 3: HTTP POST
run_test "HTTP POST with JSON data" \
    "curl -s -x $PROXY -X POST -H 'Content-Type: application/json' -d '{\"test\":\"data\"}' http://httpbin.org/post" \
    "test.*data"

# Test 4: HTTP PUT
run_test "HTTP PUT" \
    "curl -s -x $PROXY -X PUT -d 'test data' http://httpbin.org/put" \
    "test data"

# Test 5: HTTP DELETE
run_test "HTTP DELETE" \
    "curl -s -x $PROXY -X DELETE http://httpbin.org/delete" \
    "httpbin.org"

# Test 6: HTTP HEAD
run_test "HTTP HEAD" \
    "curl -s -I -x $PROXY http://httpbin.org/get" \
    "Content-Type"

# Test 7: HTTP OPTIONS
run_test "HTTP OPTIONS" \
    "curl -s -X OPTIONS -x $PROXY http://httpbin.org/get" \
    ""

# Test 8: Large response
run_test "Large response handling" \
    "curl -s -x $PROXY http://httpbin.org/base64/$(echo 'large test data that should be handled properly by the proxy system' | base64 | tr -d '\n')" \
    "large test data"

# Test 9: Custom headers
run_test "Custom headers" \
    "curl -s -x $PROXY -H 'X-Test-Header: test-value' http://httpbin.org/headers" \
    "X-Test-Header.*test-value"

# Test 10: Query parameters
run_test "Query parameters" \
    "curl -s -x $PROXY 'http://httpbin.org/get?param1=value1&param2=value2'" \
    "param1.*value1"

# Test 11: Multiple concurrent requests (sequential processing test)
echo " Testing: Sequential processing of concurrent requests"
echo "Running 3 concurrent requests..."
(
    curl -s -x $PROXY http://httpbin.org/delay/1 > /tmp/test1.out &
    curl -s -x $PROXY http://httpbin.org/get > /tmp/test2.out &
    curl -s -x $PROXY http://httpbin.org/ip > /tmp/test3.out &
    wait
)

if [ -s /tmp/test1.out ] && [ -s /tmp/test2.out ] && [ -s /tmp/test3.out ]; then
    echo " PASS: All concurrent requests completed"
else
    echo " FAIL: Some concurrent requests failed"
fi

# Cleanup
rm -f /tmp/test*.out

echo ""
echo " HTTP Test Suite Complete!"
echo "=============================="

# Test 12: Error handling
run_test "Error handling - Invalid URL" \
    "curl -s -x $PROXY http://invalid-domain-that-does-not-exist.com/" \
    ""

echo " Tip: Check the proxy logs for detailed information about request processing"
echo " All requests should be processed sequentially over a single TCP connection"
