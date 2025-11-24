
import logging

def setup_logging():
    """Set up consistent logging configuration for the entire application"""
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
