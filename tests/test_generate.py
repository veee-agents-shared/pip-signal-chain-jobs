import unittest

import generate


class CategorisationTests(unittest.TestCase):
    def test_department_resolves_ambiguous_title(self):
        self.assertEqual(generate.role_group("Director - Technical Accounting", "Finance"), "Operations")
        self.assertEqual(generate.role_group("Brand Design Lead", "Marketing"), "Sales & Marketing")

    def test_audio_and_engineering_departments(self):
        self.assertEqual(generate.role_group("Partnerships Manager", "Music"), "Music & Audio")
        self.assertEqual(generate.role_group("Principal Engineer", "Product Development"), "Engineering")

    def test_operations_departments(self):
        self.assertEqual(generate.role_group("Factory Floor", "Manufacturing"), "Operations")
        self.assertEqual(generate.role_group("Director of Procurement", "Procurement"), "Operations")
        self.assertEqual(generate.role_group("Post Silicon Project Manager", "Program Management Organization (PMO)"), "Operations")

    def test_salary_extracts_fact_not_surrounding_prose(self):
        self.assertEqual(generate.salary_value("<p>Pay is $94,952 - $118,690 per year.</p>"), "$94,952 - $118,690")
        self.assertEqual(generate.salary_value("<p>Compensation discussed later.</p>"), "Not posted")


if __name__ == "__main__":
    unittest.main()
