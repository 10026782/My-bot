"""ליבת השוואת מסלולים, שלב 1 (PATH_ENGINE_ARCHITECTURE_SPEC §6): ליבה משותפת + מודול הלוואות + מודול כספים נזילים + משווה ניטרלי. טהור וקריאה בלבד;
אין endpoint, flag, סכמה או UI בשלב זה."""

from .comparator import break_even, compare_paths, describe_inputs, evaluate_path, sensitivity
from .core import make_frame, validate_path_result

__all__ = ["break_even", "compare_paths", "describe_inputs", "evaluate_path", "make_frame", "sensitivity", "validate_path_result"]
