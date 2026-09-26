import json
import unittest
from unittest.mock import MagicMock, patch

from context_translation import phrases, translate
from subtitles import translate_cues, TranslationUnavailable


class ContextTranslationTests(unittest.TestCase):
    def test_words_are_grouped_without_crossing_silence_or_sentence_end(self):
        cues = [(0, 200, 'This'), (200, 400, 'makes'), (400, 800, 'it freeze.'),
                (3000, 3500, 'Then it moves.')]
        self.assertEqual(phrases(cues), [(0, 800, 'This makes it freeze.'), (3000, 3500, 'Then it moves.')])

    def response(self, rows, status=200, finish='stop'):
        session = MagicMock()
        response = session.post.return_value.__enter__.return_value
        response.status_code = status
        response.iter_content.return_value = [json.dumps({'choices': [{
            'finish_reason': finish, 'message': {'content': json.dumps({'translations': rows})}}]}).encode()]
        return session

    def test_full_context_one_request_and_readable_timed_translation(self):
        cues = [(0, 500, 'It'), (500, 1000, 'can freeze.'), (4000, 5000, 'Then it moves.')]
        session = self.response([{'id': 0, 'text': 'Può restare completamente immobile.'},
                                 {'id': 1, 'text': 'Poi si muove.'}])
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            result = translate(cues, session, 'en')
        session.post.assert_called_once()
        request = session.post.call_args.kwargs['json']
        self.assertEqual(len(json.loads(request['messages'][1]['content'])['captions']), 2)
        self.assertEqual(' '.join(t for _, _, t in result), 'Può restare completamente immobile. Poi si muove.')
        self.assertEqual(result[0][0], 0)
        self.assertEqual(result[-1][1], 5000)
        self.assertFalse(any(start < 4000 and end > 1000 for start, end, _ in result))

    def test_incomplete_reordered_or_quota_responses_do_not_return_partial_translation(self):
        for rows, status, finish in (([], 200, 'stop'), ([{'id': 1, 'text': 'Ciao'}], 200, 'stop'),
                                     ([{'id': 0, 'text': 'Ciao'}], 429, 'stop'),
                                     ([{'id': 0, 'text': 'Ciao'}], 200, 'length')):
            with self.subTest(status=status, rows=rows), patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
                with self.assertRaises(ValueError):
                    translate([(0, 1000, 'Hello.')], self.response(rows, status, finish), 'en')

    def test_context_failure_does_not_silently_revert_to_isolated_word_model(self):
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}), \
             patch('context_translation.translate', side_effect=ValueError('quota')), \
             patch('local_translation.translate') as local:
            with self.assertRaises(TranslationUnavailable):
                translate_cues([(0, 1000, 'Hello.')], MagicMock(), 'en')
            local.assert_not_called()


if __name__ == '__main__':
    unittest.main()
