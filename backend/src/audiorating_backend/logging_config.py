
import logging

def setup_logging():
    """Configure application-wide logging.

    Returns:
        None: This function configures the global logging system in place.
    """
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
