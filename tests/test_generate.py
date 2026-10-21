import unittest
from pathlib import Path

import generate


class CategorisationTests(unittest.TestCase):
    def test_department_resolves_ambiguous_title(self):
        self.assertEqual(generate.role_group("Director - Technical Accounting", "Finance"), "Operations")
        self.assertEqual(generate.role_group("Brand Design Lead", "Marketing"), "Sales & Marketing")

    def test_audio_and_engineering_departments(self):
        self.assertEqual(generate.role_group("Partnerships Manager", "Music"), "Music & Audio")
        self.assertEqual(generate.role_group("Principal Engineer", "Product Development"), "Engineering")
        self.assertEqual(generate.role_group("Embedded Software Engineer", "Engineering / ADAM Audio"), "Engineering")

    def test_operations_departments(self):
        self.assertEqual(generate.role_group("Factory Floor", "Manufacturing"), "Operations")
        self.assertEqual(generate.role_group("Director of Procurement", "Procurement"), "Operations")
        self.assertEqual(generate.role_group("Post Silicon Project Manager", "Program Management Organization (PMO)"), "Operations")

    def test_salary_extracts_fact_not_surrounding_prose(self):
        self.assertEqual(generate.salary_value("<p>Pay is $94,952 - $118,690 per year.</p>"), "$94,952 - $118,690")
        self.assertEqual(generate.salary_value("<p>Salary: £26250 pa</p>"), "£26250 pa")
        self.assertEqual(generate.salary_value("<p>Salary: $50K-$55K with benefits</p>"), "$50K-$55K")
        self.assertEqual(generate.salary_value("<p>Salary: Depending on experience</p><p>Budget responsibility: £25000</p>"), "Not posted")
        self.assertEqual(generate.salary_value("<p>Compensation discussed later.</p>"), "Not posted")


class PublishedPageTests(unittest.TestCase):
    def test_method_page_is_generated(self):
        generate.main()
        page = (Path(__file__).parents[1] / "docs" / "method.html").read_text()
        self.assertIn("Signal Chain Jobs is run by pip, an AI agent", page)
        self.assertIn("correction or removal", page)
        self.assertEqual(page.count("<tr><th scope=\"row\">"), 11)


if __name__ == "__main__":
    unittest.main()
