import os
import hashlib

def compute_sha1(file_path, block_size=65536):
    """
    Compute the SHA1 hash of a file.

    Args:
        file_path (str): Path to the file.
        block_size (int): Size of blocks to read from the file.

    Returns:
        str: The hexadecimal SHA1 hash of the file.
    """
    sha1 = hashlib.sha1()
    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(block_size)
                if not data:
                    break
                sha1.update(data)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
    return sha1.hexdigest()

def compute_hashes_recursive(directory):
    """
    Recursively compute SHA1 hashes for each file in the directory.

    Args:
        directory (str): The root directory to start scanning.

    Returns:
        dict: A dictionary mapping file paths to their SHA1 hashes.
    """
    hashes = {}

    def recurse(current_dir):
        for entry in os.listdir(current_dir):
            full_path = os.path.join(current_dir, entry)
            if os.path.isfile(full_path):
                file_hash = compute_sha1(full_path)
                if file_hash is not None:
                    hashes[full_path] = file_hash
            elif os.path.isdir(full_path):
                recurse(full_path)

    recurse(directory)
    return hashes

# Example usage:
if __name__ == '__main__':
    directory = '/path/to/your/directory'  # Replace with the path to your directory
    file_hashes = compute_hashes_recursive(directory)
    for path, hash_val in file_hashes.items():
        print(f"{path}: {hash_val}")
