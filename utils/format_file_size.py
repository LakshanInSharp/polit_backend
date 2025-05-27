

 # Utility function to format file size (optional)
def format_size(size: int) -> str:
        """Convert bytes to a human-readable format (KB, MB, GB)."""
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"  # In case of larger sizes