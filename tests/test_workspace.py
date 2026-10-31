import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.config import workspace_path
from src.init_workspace import initialize


class WorkspaceTests(unittest.TestCase):
    def test_private_path_and_invalid_config(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'PERMITRAG_WORKSPACE': folder}):
                self.assertEqual(workspace_path('keys/token_key.txt'), Path(folder) / 'keys/token_key.txt')
        for value in ('', 'relative/path'):
            with patch.dict(os.environ, {'PERMITRAG_WORKSPACE': value}):
                with self.assertRaises(ValueError):
                    workspace_path('data/users.json')

    def test_empty_workspace_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = initialize(Path(folder) / 'private')
            self.assertEqual((root / 'data/users.json').read_text().strip(), '[]')
            self.assertEqual(list((root / 'data/docs').iterdir()), [])
            with self.assertRaises(FileExistsError):
                initialize(root)
            self.assertEqual((root / 'data/users.json').read_text().strip(), '[]')
