"""Real local-weight checks; opt in with RUN_REAL_EMBEDDINGS=1 after download."""
import importlib.util
import math
import os
import tempfile
import unittest


class EmbeddingContractTests(unittest.TestCase):
    def test_module_provides_embedder(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.rag_embeddings'))

    def test_unknown_model_fails_before_loading(self):
        from assistant.rag_embeddings import LocalEmbedder
        with self.assertRaisesRegex(ValueError, 'model'):
            LocalEmbedder('unknown')

    def test_missing_local_weights_explains_download(self):
        from assistant.rag_embeddings import LocalEmbedder
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'download'):
                LocalEmbedder('e5', cache_dir=directory)


@unittest.skipUnless(os.environ.get('RUN_REAL_EMBEDDINGS') == '1', 'requires downloaded real model weights')
class RealEmbeddingTests(unittest.TestCase):
    def test_both_real_models(self):
        from assistant.rag_embeddings import LocalEmbedder
        for key, dimension in [('e5', 384), ('bge', 512)]:
            with self.subTest(model=key):
                model = LocalEmbedder(key)
                self.assertEqual(model.signature['dimension'], dimension)
                self.assertEqual(len(model.signature['revision']), 40)
                self.assertEqual(model.format_passage('轴承'), 'passage: 轴承' if key == 'e5' else '轴承')
                self.assertEqual(model.format_query('轴承'), 'query: 轴承' if key == 'e5' else '为这个句子生成表示以用于检索相关文章：轴承')
                inputs = [model.format_query('轴承温度过高'), model.format_passage('轴承过热应检查润滑和负载。'), model.format_passage('香蕉是一种水果。')]
                vectors = model.embed(inputs)
                self.assertEqual(len(vectors), 3)
                for vector in vectors:
                    self.assertEqual(len(vector), dimension)
                    self.assertTrue(all(math.isfinite(x) for x in vector))
                    self.assertAlmostEqual(sum(x*x for x in vector), 1.0, places=5)
                dot = lambda a,b: sum(x*y for x,y in zip(a,b))
                self.assertGreater(dot(vectors[0], vectors[1]), dot(vectors[0], vectors[2]))
                # Compare to the published Transformer recipe on exact supplied inputs.
                import torch
                with torch.inference_mode():
                    encoded = model.tokenizer(inputs, padding=True, truncation=False, return_tensors='pt')
                    hidden = model._model(**encoded).last_hidden_state
                    if key == 'e5':
                        mask = encoded['attention_mask']
                        pooled = hidden.masked_fill(~mask[..., None].bool(), 0.0).sum(1) / mask.sum(1)[..., None]
                    else:
                        pooled = hidden[:, 0]
                    expected = torch.nn.functional.normalize(pooled, p=2, dim=1)
                self.assertTrue(torch.allclose(torch.tensor(vectors), expected, atol=1e-6))
                # Exactly 512 tokens is accepted; the next token must fail.
                boundary = ' '.join(['a'] * 510)
                self.assertEqual(len(model.tokenizer.encode(boundary)), 512)
                self.assertEqual(len(model.embed([boundary])[0]), dimension)
                with self.assertRaisesRegex(ValueError, '512'):
                    model.embed([boundary + ' a'])
                single = model.embed(inputs[:1])[0]
                self.assertLess(max(abs(a-b) for a,b in zip(single,vectors[0])), 1e-5)
                self.assertEqual(model.embed([]), [])
                long_text = model.format_passage('轴承 ' * 600)
                self.assertGreater(len(model.tokenizer.encode(long_text, verbose=False)), 512)
                with self.assertRaisesRegex(ValueError, '512'):
                    model.embed([long_text])
                with self.assertRaises((ValueError, TypeError)):
                    model.embed('not a list')
