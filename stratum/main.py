"""Main orchestrator and CLI entry point for Stratum."""


def run() -> None:
    """CLI entry point wired via pyproject.toml [project.scripts]."""

    """ Notes on what we do in this task
    
    Process:

    --config PATH and --dry-run flag.
    
    Write a PID file to ~/.stratum/stratum.pid on startup; remove it on clean exit.
    - note we will have to have careful handling of PID file on error

    The scan loop: 
        * during loop: log scan progress with the stdlib logging module (not print statements).
        -> for each FileRecord from scanner.scan() 
        -> hash with hasher 
        -> classify with tagger
        -> check index 
        -> emit suggestion if duplicate 
        -> insert hash into index.

    Print a summary line at the end: files scanned, duplicates found, suggestions written, time elapsed.

    """
