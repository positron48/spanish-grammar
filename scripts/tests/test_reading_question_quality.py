import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reading_catalog_maintain import reading_question_issues


class QuestionQualityTest(unittest.TestCase):
    def question(self, **overrides):
        return {'id': 'q1', 'type': 'true_false', 'prompt': 'Хулия идёт в библиотеку.', 'explanation': 'Она хочет вернуть книгу.', 'correct_answer': 'true', **overrides}

    def test_reports_non_russian_and_unfinished_templates(self):
        self.assertTrue(reading_question_issues([self.question(prompt='Julia va a la biblioteca.')]))
        self.assertTrue(reading_question_issues([self.question(explanation='Necesita devolver un libro.')]))
        for prompt in ['План связан с вернуть книгу.', 'Хулия идёт один/одна.']:
            self.assertTrue(reading_question_issues([self.question(prompt=prompt)]))

    def test_accepts_complete_russian_and_rejects_invalid_answer(self):
        self.assertEqual(reading_question_issues([self.question()]), [])
        self.assertTrue(reading_question_issues([self.question(correct_answer='yes')]))


if __name__ == '__main__':
    unittest.main()
