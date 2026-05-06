import os
import sys
import time
import argparse

# Default path and depth (used when no CLI arguments are provided)
# Paste a Windows path between the r"..." quotes — no escaping needed.
default_path = r"C:\Users\lugr\AppData\Local"
default_depth = 1

# Update the in-place progress line every N files scanned (set to 0 to disable).
log_interval = 5000


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


class ScanProgress:
    """Single-line status that overwrites itself; cleared before final output."""
    def __init__(self, interval, total_folders):
        self.interval = interval
        self.total_folders = total_folders
        self.folder_idx = 0
        self.current = ""
        self.files = 0
        self.bytes = 0
        self.start = time.time()
        self._last_files = 0
        self._line_len = 0

    def set_folder(self, idx, rel_path):
        self.folder_idx = idx
        self.current = rel_path or "."
        self._render()

    def tick(self, size):
        self.files += 1
        self.bytes += size
        if self.interval and self.files - self._last_files >= self.interval:
            self._last_files = self.files
            self._render()

    def _render(self):
        if not self.interval:
            return
        msg = (
            f"[{self.folder_idx}/{self.total_folders}] {self.current} "
            f"| {self.files:,} files | {format_size(self.bytes)}"
        )
        pad = max(0, self._line_len - len(msg))
        sys.stderr.write("\r" + msg + (" " * pad))
        sys.stderr.flush()
        self._line_len = len(msg)

    def clear(self):
        if self.interval and self._line_len:
            sys.stderr.write("\r" + " " * self._line_len + "\r")
            sys.stderr.flush()
            self._line_len = 0


def get_folder_size(path, progress=None):
    total_size = 0
    for root, _dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                total_size += size
                if progress is not None:
                    progress.tick(size)
            except OSError:
                continue
    return total_size


def collect_folders(root_path, max_depth):
    """Yield (depth, absolute_path) for every folder to measure, in display order."""
    yield 0, root_path
    if max_depth < 1:
        return
    for current_root, dirs, _ in os.walk(root_path):
        rel = os.path.relpath(current_root, root_path)
        current_depth = 0 if rel == '.' else len(rel.split(os.sep))
        if current_depth >= max_depth:
            dirs[:] = []
            continue
        dirs.sort()
        for d in dirs:
            yield current_depth + 1, os.path.join(current_root, d)


def list_folder_sizes(root_path, max_depth):
    if not os.path.exists(root_path):
        raise FileNotFoundError(f"Path does not exist: {root_path}")
    if not os.path.isdir(root_path):
        raise NotADirectoryError(f"Path is not a directory: {root_path}")

    root_path = os.path.abspath(root_path)
    folders = list(collect_folders(root_path, max_depth))

    progress = ScanProgress(log_interval, len(folders))
    results = []
    started = time.time()

    for idx, (_depth, path) in enumerate(folders, 1):
        rel = os.path.relpath(path, root_path)
        progress.set_folder(idx, rel)
        try:
            size = get_folder_size(path, progress)
        except OSError:
            size = 0
        results.append((rel, size))

    progress.clear()

    for rel, size in results:
        print(f"{format_size(size)}\t{rel}")

    elapsed = time.time() - started
    print(
        f"\n{progress.files:,} files | {format_size(progress.bytes)} | "
        f"{len(results)} folders | {elapsed:.1f}s",
        file=sys.stderr,
    )
    return results


def parse_args():
    parser = argparse.ArgumentParser(
        description="List folders and their sizes under a Windows path up to a configurable depth."
    )
    parser.add_argument(
        'path',
        nargs='?',
        default=None,
        help=f"Root folder path (default: {default_path})",
    )
    parser.add_argument(
        '-d', '--depth',
        type=int,
        default=None,
        help=f"Maximum depth of subfolders to list (default: {default_depth})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_path = args.path if args.path is not None else default_path
    target_depth = args.depth if args.depth is not None else default_depth

    if target_depth < 0:
        print("Error: depth must be >= 0", file=sys.stderr)
        sys.exit(1)

    try:
        list_folder_sizes(target_path, target_depth)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
