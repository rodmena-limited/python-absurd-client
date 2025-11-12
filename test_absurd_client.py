"""Basic test to verify the package structure."""
import uuid
from absurd_client import AbsurdClient

def test_client_creation():
    """Test that we can create an AbsurdClient instance."""
    client = AbsurdClient(queue_name="test_queue")
    assert client.queue_name == "test_queue"
    print("✓ AbsurdClient can be instantiated with a queue name")

def test_client_default_queue():
    """Test client with default queue."""
    import os
    # Temporarily set default queue
    original_value = os.environ.get('ABSURD_DEFAULT_QUEUE')
    os.environ['ABSURD_DEFAULT_QUEUE'] = 'default_test_queue'
    
    client = AbsurdClient()
    assert client.queue_name == "default_test_queue"
    print("✓ AbsurdClient uses default queue from environment")
    
    # Restore original value
    if original_value is not None:
        os.environ['ABSURD_DEFAULT_QUEUE'] = original_value
    else:
        os.environ.pop('ABSURD_DEFAULT_QUEUE', None)

def test_invalid_queue_name():
    """Test that invalid queue names are rejected."""
    try:
        AbsurdClient(queue_name="invalid-queue-name")
        assert False, "Should have raised ValueError for invalid queue name"
    except ValueError:
        print("✓ Invalid queue names are properly rejected")
    
    try:
        AbsurdClient(queue_name="valid_queue_name")
        print("✓ Valid queue names are accepted")
    except ValueError:
        assert False, "Valid queue name was incorrectly rejected"

if __name__ == "__main__":
    test_client_creation()
    test_client_default_queue()
    test_invalid_queue_name()
    print("\nAll tests passed!")
