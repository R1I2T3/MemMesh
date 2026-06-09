import logging
import sys

def setup_logging(level: str = "INFO"):
    # Configure handler with custom format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %Y %H:%M:%S",
    )
    
    root_logger = logging.getLogger()
    
    # Remove existing handlers to prevent duplicate logging
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    # Set up stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set log level
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Quiet noisy libraries
    noisy_loggers = [
        "neo4j",
        "weaviate",
        "urllib3",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
