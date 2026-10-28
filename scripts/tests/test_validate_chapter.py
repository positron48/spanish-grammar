"""Exercise the actual chapter validator without modifying the course files."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FillBlankValidationTest(unittest.TestCase):
    def validate(self, *, hint=None, answer=None):
        source = next((ROOT / 'chapters').glob('075*/05-final.json'))
        chapter = json.loads(source.read_text())
        question = next(q for q in chapter['question_bank']['questions'] if q['type'] == 'fill_blank')
        if hint is not None:
            question['prompt'] += ' (' + hint + ')'
        if answer is not None:
            question['correct_answer'] = answer
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / 'scripts').mkdir()
            for filename in ('validate-chapter.sh', 'chapter-utils.sh'):
                shutil.copy(ROOT / 'scripts' / filename, tmp / 'scripts' / filename)
            shutil.copy(ROOT / '02-chapter-schema.json', tmp / '02-chapter-schema.json')
            target = tmp / 'chapters' / chapter['id']
            target.mkdir(parents=True)
            (target / '05-final.json').write_text(json.dumps(chapter, ensure_ascii=False))
            result = subprocess.run(['bash', str(tmp / 'scripts/validate-chapter.sh'), chapter['id']], capture_output=True, text=True)
            report = json.loads((target / '05-validation.json').read_text())
        return result, report, question

    def test_context_only_fill_blank_is_valid(self):
        result, report, _ = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hint_must_not_reveal_answer(self):
        chapter = json.loads(next((ROOT / 'chapters').glob('075*/05-final.json')).read_text())
        answer = next(q['correct_answer'] for q in chapter['question_bank']['questions'] if q['type'] == 'fill_blank')
        result, _, _ = self.validate(hint=answer)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('в скобках указана та же форма', result.stdout)

    def test_multiword_answer_still_rejected(self):
        result, _, _ = self.validate(answer='two words')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('должен быть одним словом', result.stdout)


if __name__ == '__main__':
    unittest.main()
