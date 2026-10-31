import unittest
from src.authorization import validate_user, can_read
from src.retrieval import build_access_filter

class JuniorAccessTests(unittest.TestCase):
    def test_clearance_and_department_boundaries(self):
        junior=validate_user({'user_id':'Arjun','department':'Engineering','role':'Junior Engineer','clearance':1})
        def doc(department,clearance):
            return {'department':department,'clearance':clearance,'allowed_roles':[]}
        self.assertTrue(can_read(junior,doc('Engineering',1)))
        self.assertTrue(can_read(junior,doc('ALL',0)))
        self.assertFalse(can_read(junior,doc('Engineering',2)))
        self.assertFalse(can_read(junior,doc('Finance',1)))
        intern=validate_user({'user_id':'Kavin','department':'Engineering','role':'Intern','clearance':0})
        self.assertFalse(can_read(intern,doc('Engineering',1)))
        self.assertEqual(build_access_filter(junior).must[0].range.lte,1)
