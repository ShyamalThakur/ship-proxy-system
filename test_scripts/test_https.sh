#!/bin/bash

# HTTPS Test Script for Ship Proxy System
# Tests HTTPS tunneling via CONNECT method

PROXY="http://localhost:8080"

echo " Ship Proxy System - HTTPS Test Suite"
echo "======================================="
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
    if curl -s --connect-timeout 2 -x $PROXY https://httpbin.org/get > /dev/null 2>&1; then
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

# Test 1: Basic HTTPS GET
run_test "Basic HTTPS GET" \
    "curl -s -x $PROXY https://httpbin.org/get" \
    "httpbin.org"

# Test 2: HTTPS with popular site
run_test "HTTPS GET - Google" \
    "curl -s -x $PROXY https://www.google.com/" \
    "Google"

# Test 3: HTTPS POST
run_test "HTTPS POST with JSON" \
    "curl -s -x $PROXY -X POST -H 'Content-Type: application/json' -d '{\"https\":\"test\"}' https://httpbin.org/post" \
    "https.*test"

# Test 4: HTTPS with authentication headers
run_test "HTTPS with custom headers" \
    "curl -s -x $PROXY -H 'Authorization: Bearer test-token' https://httpbin.org/bearer" \
    "authenticated.*true"

# Test 5: HTTPS PUT
run_test "HTTPS PUT" \
    "curl -s -x $PROXY -X PUT -d 'secure data' https://httpbin.org/put" \
    "secure data"

# Test 6: HTTPS DELETE
run_test "HTTPS DELETE" \
    "curl -s -x $PROXY -X DELETE https://httpbin.org/delete" \
    "httpbin.org"

# Test 7: Different HTTPS sites
run_test "HTTPS - GitHub API" \
    "curl -s -x $PROXY https://api.github.com/users/octocat" \
    "octocat"

# Test 8: HTTPS with query parameters
run_test "HTTPS with query params" \
    "curl -s -x $PROXY 'https://httpbin.org/get?secure=true&test=https'" \
    "secure.*true"

# Test 9: HTTPS HEAD request
run_test "HTTPS HEAD request" \
    "curl -s -I -x $PROXY https://httpbin.org/get" \
    "Content-Type"

# Test 10: Multiple HTTPS requests
echo " Testing: Multiple HTTPS requests (sequential processing)"
echo "Running 3 concurrent HTTPS requests..."
(
    curl -s -x $PROXY https://httpbin.org/delay/1 > /tmp/https_test1.out &
    curl -s -x $PROXY https://httpbin.org/get > /tmp/https_test2.out &
    curl -s -x $PROXY https://httpbin.org/uuid > /tmp/https_test3.out &
    wait
)

if [ -s /tmp/https_test1.out ] && [ -s /tmp/https_test2.out ] && [ -s /tmp/https_test3.out ]; then
    echo " PASS: All concurrent HTTPS requests completed"
else
    echo " FAIL: Some concurrent HTTPS requests failed"
fi

# Cleanup
rm -f /tmp/https_test*.out

# Test 11: Mixed HTTP and HTTPS
echo " Testing: Mixed HTTP and HTTPS requests"
echo "Running mixed protocol requests..."
(
    curl -s -x $PROXY http://httpbin.org/get > /tmp/mixed_http.out &
    curl -s -x $PROXY https://httpbin.org/get > /tmp/mixed_https.out &
    wait
)

if [ -s /tmp/mixed_http.out ] && [ -s /tmp/mixed_https.out ]; then
    echo " PASS: Mixed HTTP/HTTPS requests completed"
else
    echo " FAIL: Mixed protocol requests failed"
fi

# Cleanup
rm -f /tmp/mixed_*.out

echo ""
echo " HTTPS Test Suite Complete!"
echo "============================="

# Test 12: HTTPS Error handling
run_test "HTTPS Error handling - Invalid certificate site" \
    "curl -s -k -x $PROXY https://self-signed.badssl.com/" \
    ""

echo ""
echo " Tip: HTTPS tunneling uses CONNECT method for establishing secure tunnels"
echo " Each HTTPS connection creates a new tunnel through the proxy"
echo " Check proxy logs to see CONNECT requests being processed"
