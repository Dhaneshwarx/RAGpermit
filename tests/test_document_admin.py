import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src import document_admin as admin

TEXT = '---\ndoc_id: policy\ntitle: Policy\ndepartment: Executive\nclearance: 3\nallowed_roles: []\n---\n\n## Facts\n\nApproved content.'

class DocumentAdminTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.pathpatch=patch.object(admin,'workspace_path',side_effect=lambda p:self.root/p)
        self.pathpatch.start();self.addCleanup(self.pathpatch.stop)
        self.audit=patch.object(admin,'write_audit_entry');self.audit.start();self.addCleanup(self.audit.stop)

    def test_save_delete_and_path_validation(self):
        admin.change('owner','save','policy',TEXT)
        self.assertTrue(admin.dirty())
        self.assertEqual(len(admin.inventory()['documents']),1)
        with self.assertRaises(ValueError):admin.change('owner','save','../escape',TEXT)
        admin.change('owner','delete','policy')
        self.assertEqual(admin.inventory()['documents'],[])
        self.assertTrue(admin.dirty())

    def test_invalid_document_never_written(self):
        with self.assertRaises(ValueError):admin.change('owner','save','policy','no header')
        self.assertFalse(admin.dirty())

    def test_failed_rebuild_keeps_questions_blocked(self):
        admin.change('owner','save','policy',TEXT)
        with patch.object(admin,'embed_chunks',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):admin.reindex('owner')
        self.assertTrue(admin.dirty())

    def test_empty_rebuild_clears_stale_collection(self):
        admin.change('owner','save','policy',TEXT)
        admin.change('owner','delete','policy')
        with patch.object(admin,'open_store') as store,patch.object(admin,'rebuild_collection') as rebuild:
            self.assertEqual(admin.reindex('owner'),0)
            rebuild.assert_called_once_with(store.return_value)
            store.return_value.close.assert_called_once()
        self.assertFalse(admin.dirty())
