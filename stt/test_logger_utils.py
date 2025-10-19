#!/usr/bin/env python3
"""
Unit tests for logger_utils module.

Tests JSON log formatting, request ID generation/propagation, and context handling.
"""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from logger_utils import (
    get_logger,
    generate_request_id,
    generate_operation_id,
    set_request_id,
    get_request_id,
    clear_request_id,
    add_request_id_header,
    extract_request_id_from_headers
)


class TestLoggerUtils(unittest.TestCase):
    """Test cases for logger_utils module."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing request ID
        clear_request_id()

    def tearDown(self):
        """Clean up after tests."""
        clear_request_id()

    def test_generate_request_id_format(self):
        """Test request ID generation returns correct format."""
        req_id = generate_request_id()

        # Should be 8 characters
        self.assertEqual(len(req_id), 8)

        # Should be lowercase hex
        self.assertTrue(all(c in '0123456789abcdef' for c in req_id))

    def test_generate_request_id_uniqueness(self):
        """Test that generated request IDs are unique."""
        ids = set(generate_request_id() for _ in range(100))

        # Should generate 100 unique IDs
        self.assertEqual(len(ids), 100)

    def test_generate_operation_id_format(self):
        """Test operation ID generation returns correct format."""
        op_id = generate_operation_id()

        # Should be 8 characters
        self.assertEqual(len(op_id), 8)

        # Should be lowercase hex
        self.assertTrue(all(c in '0123456789abcdef' for c in op_id))

    def test_request_id_context(self):
        """Test request ID context management."""
        # Initially no request ID
        self.assertIsNone(get_request_id())

        # Set request ID
        req_id = "test1234"
        set_request_id(req_id)

        # Should retrieve the same ID
        self.assertEqual(get_request_id(), req_id)

        # Clear request ID
        clear_request_id()

        # Should be None again
        self.assertIsNone(get_request_id())

    def test_add_request_id_header(self):
        """Test adding request ID to HTTP headers."""
        headers = {"Content-Type": "application/json"}
        req_id = "test5678"

        # Add request ID header
        updated_headers = add_request_id_header(headers, req_id)

        # Should have X-Request-Id header
        self.assertIn("X-Request-Id", updated_headers)
        self.assertEqual(updated_headers["X-Request-Id"], req_id)

        # Original headers should still have Content-Type
        self.assertEqual(updated_headers["Content-Type"], "application/json")

    def test_add_request_id_header_from_context(self):
        """Test adding request ID from context when not provided."""
        headers = {}
        req_id = "context99"

        # Set request ID in context
        set_request_id(req_id)

        # Add header without explicit reqId
        updated_headers = add_request_id_header(headers)

        # Should use context request ID
        self.assertEqual(updated_headers["X-Request-Id"], req_id)

    def test_extract_request_id_from_headers(self):
        """Test extracting request ID from HTTP headers."""
        req_id = "extract12"

        # Test standard case
        headers = {"X-Request-Id": req_id}
        extracted = extract_request_id_from_headers(headers)
        self.assertEqual(extracted, req_id)

    def test_extract_request_id_case_insensitive(self):
        """Test case-insensitive header extraction."""
        req_id = "casetest1"

        # Test different case variations
        test_cases = [
            {"x-request-id": req_id},
            {"X-REQUEST-ID": req_id},
            {"x-Request-Id": req_id},
        ]

        for headers in test_cases:
            extracted = extract_request_id_from_headers(headers)
            self.assertEqual(extracted, req_id, f"Failed for headers: {headers}")

    def test_extract_request_id_missing(self):
        """Test extracting request ID when header is missing."""
        headers = {"Content-Type": "application/json"}
        extracted = extract_request_id_from_headers(headers)
        self.assertIsNone(extracted)

    def test_logger_json_output(self):
        """Test that logger outputs valid JSON."""
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger = get_logger("test")
            req_id = "json1234"
            set_request_id(req_id)

            # Log a message
            logger.info("Test message", duration_ms=123)

            # Get output
            output = captured_output.getvalue()

            # Parse as JSON
            log_entry = json.loads(output.strip())

            # Verify schema
            self.assertIn("ts", log_entry)
            self.assertEqual(log_entry["level"], "info")
            self.assertEqual(log_entry["reqId"], req_id)
            self.assertEqual(log_entry["msg"], "Test message")
            self.assertIn("meta", log_entry)
            self.assertEqual(log_entry["meta"]["duration_ms"], 123)

        finally:
            sys.stdout = old_stdout

    def test_logger_levels(self):
        """Test different log levels."""
        old_stdout = sys.stdout

        try:
            levels = ["debug", "info", "warn", "error"]

            for level in levels:
                sys.stdout = captured_output = StringIO()

                logger = get_logger("test")
                getattr(logger, level if level != "warn" else "warn")(f"Test {level} message")

                output = captured_output.getvalue()
                log_entry = json.loads(output.strip())

                self.assertEqual(log_entry["level"], level)
                self.assertEqual(log_entry["msg"], f"Test {level} message")

        finally:
            sys.stdout = old_stdout

    def test_logger_with_metadata(self):
        """Test logging with various metadata types."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger = get_logger("test")

            # Log with different metadata types
            logger.info("Metadata test",
                       string_val="test",
                       int_val=42,
                       float_val=3.14,
                       bool_val=True)

            output = captured_output.getvalue()
            log_entry = json.loads(output.strip())

            meta = log_entry["meta"]
            self.assertEqual(meta["string_val"], "test")
            self.assertEqual(meta["int_val"], 42)
            self.assertAlmostEqual(meta["float_val"], 3.14)
            self.assertEqual(meta["bool_val"], True)

        finally:
            sys.stdout = old_stdout

    def test_logger_no_reqid(self):
        """Test logging without request ID set."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger = get_logger("test")
            logger.info("No reqId test")

            output = captured_output.getvalue()
            log_entry = json.loads(output.strip())

            # reqId should be null/None
            self.assertIsNone(log_entry["reqId"])

        finally:
            sys.stdout = old_stdout


if __name__ == "__main__":
    # Run tests
    unittest.main()
