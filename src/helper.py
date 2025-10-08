import os
from pathlib import Path
from loguru import logger
import toml

def get_project_name_from_pyproject(pyproject_path: Path = None, default: str = "greek-room-api") -> str:
    """
    Reads the project name from pyproject.toml if available.
    Falls back to default if not found.
    """
    if pyproject_path is None:
        # Traverse upwards to find pyproject.toml
        current_path = Path(__file__).resolve() if '__file__' in globals() else Path.cwd().resolve()
        for parent in [current_path] + list(current_path.parents):
            candidate = parent / "pyproject.toml"
            if candidate.exists():
                pyproject_path = candidate
                break
    if pyproject_path and pyproject_path.exists():
        try:
            data = toml.load(pyproject_path)
            # Try PEP 621 style first
            if "project" in data and "name" in data["project"]:
                return data["project"]["name"]
            # Try poetry style
            if "tool" in data and "poetry" in data["tool"] and "name" in data["tool"]["poetry"]:
                return data["tool"]["poetry"]["name"]
        except Exception:
            pass
    return default

PROJECT_NAME = get_project_name_from_pyproject()

def get_project_root(project_name: str = PROJECT_NAME) -> Path:
    """
    Returns the absolute path to the root of the given project folder.

    The function searches for the project folder by traversing upwards from the current
    directory until it finds a directory named `project_name`. This works in both .py
    scripts and Jupyter Notebook environments.

    Parameters:
        project_name (str): The name of the project folder to find.

    Returns:
        Path: The absolute path to the project folder.

    Raises:
        FileNotFoundError: If the project folder is not found in the current path hierarchy.
    """
    try:
        current_path = Path(__file__).resolve()
    except NameError:
        current_path = Path.cwd().resolve()

    # Traverse upwards until you find the project folder
    for parent in current_path.parents:
        if parent.name == project_name:
            if parent.parent.name == project_name:
                return parent.parent
            else:
                return parent

    raise FileNotFoundError(
        f"Could not find the '{project_name}' folder in the current path hierarchy."
    )

PROJECT_ROOT = get_project_root()
logger.info(f"Project root path: {PROJECT_ROOT}")